"""Real GStreamer output + GTK integration, without loading a kernel module."""
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
temp = tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME'] = str(Path(temp.name) / 'config')
from app import CameraApp, GLib, Gdk, Gst, Gtk
from virtual_camera import VirtualCameraOutput


def test_sink():
    sink = Gst.ElementFactory.make('appsink')
    sink.set_property('max-buffers', 2)
    sink.set_property('drop', True)
    return sink


errors = []
# Exercise the actual production v4l2sink creation path. /dev/null deliberately
# fails the V4L2 device open; no kernel device or module is needed. The enum must
# select implemented MMAP output, never GStreamer's no-op read/write path.
production_sinks = []
real_make = Gst.ElementFactory.make


def capture_make(factory, name):
    element = real_make(factory, name)
    if factory == 'v4l2sink':
        production_sinks.append(element)
    return element


production = VirtualCameraOutput(errors.append)
with patch('virtual_camera.query_device', return_value=dict(driver='v4l2 loopback', output=True)), patch.object(Gst.ElementFactory, 'make', side_effect=capture_make):
    try:
        production.start('/dev/null', 10, 4)
    except RuntimeError:
        pass
    else:
        raise AssertionError('A non-video device must fail startup')
assert len(production_sinks) == 1
assert production_sinks[0].get_property('io-mode').value_nick == 'mmap'
assert not production.running and production.pipeline is None

sink = test_sink()
output = VirtualCameraOutput(errors.append, sink=sink)
output.start('/unused-test-device', 10, 4)
# Ensure downstream device allocation queries never reach conversion upstream.
# Probe the real linked sink, rather than only checking the property value.
allocation_queries = []


def observe_allocation(_pad, info):
    query = info.get_query()
    if query and query.type == Gst.QueryType.ALLOCATION:
        allocation_queries.append(query)
    return Gst.PadProbeReturn.OK


probe = sink.get_static_pad('sink').add_probe(Gst.PadProbeType.QUERY_DOWNSTREAM, observe_allocation)
boundary = output.pipeline.get_by_name('output')
caps = Gst.Caps.from_string('video/x-raw,format=YUY2,width=10,height=4,framerate=30/1')
# A query sent directly to the consumer proves the probe is active.
boundary.get_static_pad('src').peer_query(Gst.Query.new_allocation(caps, True))
assert allocation_queries, 'Allocation query probe did not observe the consumer'
allocation_queries.clear()
boundary.get_static_pad('sink').query(Gst.Query.new_allocation(caps, True))
assert not allocation_queries, 'The device buffer pool leaked into upstream conversion'
sink.get_static_pad('sink').remove_probe(probe)
# RGB rows deliberately include padding. The left half is red, right is blue.
row = bytes([255, 0, 0] * 5 + [0, 0, 255] * 5 + [0, 0])
frame = (row * 4, 10, 4, 32)


def sample_after(frame, mirror):
    # Drain queued samples, then allow videorate and renegotiation to settle.
    while sink.emit('try-pull-sample', 0):
        pass
    sample = None
    for _ in range(8):
        output.push(frame, mirror)
        time.sleep(0.04)
        candidate = sink.emit('try-pull-sample', 0)
        if candidate:
            sample = candidate
    assert sample, 'No virtual-camera frame arrived'
    assert sample.get_caps().get_structure(0).get_string('format') == 'YUY2'
    buffer = sample.get_buffer()
    return bytes(buffer.extract_dup(0, buffer.get_size())), sample.get_caps()


data, caps = sample_after(frame, False)
assert data[3] > data[1] + 80, 'Red should be on the left'
data, _ = sample_after(frame, True)
assert data[1] > data[3] + 80, 'Mirrored blue should be on the left'
data, _ = sample_after(None, False)
assert max(data[0::2]) < 25, 'Restart gaps must produce black'
data, caps = sample_after((bytes([0, 255, 0] * 16), 4, 4, 12), False)
assert caps.get_structure(0).get_value('width') == 10, 'Output format must remain stable across source changes'
output.stop()
assert not output.running and output.pipeline is None and not errors, errors

app = CameraApp(demo=True)
phase = 0
active = None
record_path = None
created = []
failures = []


def factory(callback):
    result = VirtualCameraOutput(callback, sink=test_sink())
    created.append(result)
    return result


def error(message):
    failures.append(message)
    app.window.close_now()


def tick():
    global phase, active, record_path
    w = app.window
    if w is None:
        return True
    w.error = error
    try:
        if phase == 0 and w.pixbuf:
            assert w.virtual_button.get_label() == 'Start virtual camera'
            assert w.virtual_button.get_sensitive()
            w.settings.values.update(folder=temp.name, filename='virtual-record')
            w.virtual_button.clicked()
            phase = 1
        elif phase == 1 and w.virtual_output:
            active = w.virtual_output
            assert w.virtual_button.get_label() == 'Stop virtual camera'
            assert w.camera_combo.get_sensitive()
            w.settings.values['mirror'] = False
            with patch.object(w, 'recording_options', return_value=dict(audio=False, microphone='default', device=None)):
                w.toggle_record()
            assert w.recording and w.virtual_output is active and active.running
            record_path = w.record_path
            phase = 2
        elif phase == 2 and w.pixbuf and time.monotonic() - w.started_at > 1.5:
            assert active.frames_sent > 20 and active.mirrored is False
            w.settings.values['mirror'] = True
            w.finish_record()
            phase = 3
        elif phase == 3 and not w.recording and w.pixbuf:
            assert active.running and active.mirrored is True
            assert record_path.stat().st_size > 10000
            assert w.camera_combo.get_sensitive()
            screen = Gdk.pixbuf_get_from_window(w.get_window(), 0, 0, w.get_allocated_width(), w.get_allocated_height())
            if screen:
                screen.savev(str(Path(os.environ.get('RUNNER_TEMP', str(ROOT.parent))) / 'lumen-virtual-camera-preview.png'), 'png', [], [])
            # An output failure must leave the capture pipeline running.
            active.message(None, Gst.Message.new_eos(active.pipeline))
            assert w.virtual_output is None and w.pipeline is not None
            w.virtual_button.clicked()
            phase = 4
        elif phase == 4 and w.virtual_output:
            w.virtual_button.clicked()
            assert w.virtual_output is None and not created[-1].running
            w.virtual_button.clicked()
            phase = 5
        elif phase == 5 and w.virtual_output:
            w.close_now()
            assert all(not x.running for x in created)
            phase = 6
            return False
    except Exception as exc:
        error(repr(exc))
        return False
    return True


GLib.timeout_add(100, tick)
GLib.timeout_add_seconds(20, lambda: error('Virtual-camera smoke test timed out'))
with patch('app.discover_virtual_devices', return_value=[dict(path='/unused-test-device', name='LumenCamera')]), patch('app.VirtualCameraOutput', side_effect=factory):
    app.run(['virtual-camera-smoke'])
assert phase == 6 and not failures, (phase, failures)
print('PASS: production sink uses MMAP, blocks device allocation queries and rejects invalid devices; real YUY2 output, padded RGB, mirroring, black gaps, source resizing; GTK start/stop, simultaneous MKV recording, restart, error isolation, close cleanup')
temp.cleanup()
