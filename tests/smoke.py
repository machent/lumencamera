"""End-to-end GTK, photos, EOS finalization and shutdown using a test camera."""
import os
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME'] = str(Path(tmp.name) / 'config')
from app import CameraApp, GLib, Gdk, GdkPixbuf, Gst

app = CameraApp(demo=True)
failures = []
phase = 0
photo = None
video = None

def error(message):
    failures.append(message)
    print('ERROR:', message, flush=True)
    app.window.close_now()


def tick():
    global phase, photo, video
    w = app.window
    if w is None:
        return True
    w.error = error
    try:
        if phase == 0 and w.pixbuf:
            w.settings.values.update(folder=tmp.name, filename='test')
            w.take_photo()
            photo = w.last_saved
            pix = GdkPixbuf.Pixbuf.new_from_file(str(photo))
            assert (pix.get_width(), pix.get_height()) == (1280, 720)
            w.take_photo()
            assert w.last_saved != photo
            w.settings.values['photo_format'] = 'jpeg'
            w.take_photo()
            assert GdkPixbuf.Pixbuf.new_from_file(str(w.last_saved)).get_width() == 1280
            screen = Gdk.pixbuf_get_from_window(w.get_window(), 0, 0, w.get_allocated_width(), w.get_allocated_height())
            screen.savev(str(ROOT.parent / 'lumen-camera-preview.png'), 'png', [], [])
            # Exercise hardware UI widgets and disabled manual controls.
            from core import parse_controls
            w.render_controls(parse_controls('''
 focus_automatic_continuous 0x009a090c (bool) : default=1 value=1
 focus_absolute 0x009a090a (int) : min=0 max=255 step=5 default=0 value=0 flags=inactive
 sharpness 0x0098091b (int) : min=0 max=10 step=1 default=3 value=3
 exposure_auto 0x009a0901 (menu) : min=0 max=3 default=3 value=3
   1: Manual Mode
   3: Aperture Priority Mode
'''))
            assert not w.control_widgets['focus_absolute'].get_sensitive()
            w.toggle_record()
            assert w.recording
            assert not w.camera_combo.get_sensitive()
            phase = 1
            return True
        if phase == 1 and w.recording and w.pixbuf and __import__('time').monotonic() - w.started_at > 2:
            video = w.record_path
            w.finish_record()
            phase = 2
            return True
        if phase == 2 and not w.recording and w.pixbuf:
            assert video.exists() and video.stat().st_size > 10000
            # Decode every video frame through GStreamer; invalid/incomplete files fail.
            decoder = Gst.parse_launch('filesrc name=file ! matroskademux ! vp8dec ! fakesink sync=false')
            decoder.get_by_name('file').set_property('location', str(video))
            decoder.set_state(Gst.State.PLAYING)
            message = decoder.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            decoder.set_state(Gst.State.NULL)
            assert message and message.type == Gst.MessageType.EOS, 'Recorded WebM failed decoding'
            # Test the optional audio branch with a synthetic source.
            # This verifies encoding/muxing without claiming microphone hardware testing.
            w.settings.values['audio'] = True
            original_parse = Gst.parse_launch
            Gst.parse_launch = lambda description: original_parse(description.replace('pulsesrc do-timestamp=true', 'audiotestsrc is-live=true'))
            w.toggle_record()
            phase = 3
            return True
        if phase == 3 and w.recording and w.pixbuf and __import__('time').monotonic() - w.started_at > 1:
            w.on_close()
            phase = 4
            return False
    except Exception as exc:
        error(repr(exc))
        return False
    return True

def timeout():
    error('Smoke test timed out')
    return False

GLib.timeout_add(200, tick)
GLib.timeout_add_seconds(25, timeout)
app.run(['smoke'])
assert phase == 4 and not failures, (phase, failures)
assert len(list(Path(tmp.name).glob('*.webm'))) == 2
import gi
gi.require_version('GstPbutils', '1.0')
from gi.repository import GstPbutils
discoverer = GstPbutils.Discoverer.new(5 * Gst.SECOND)
info = discoverer.discover_uri((Path(tmp.name) / 'test_001.webm').as_uri())
assert info.get_audio_streams(), 'Audio recording has no audio stream'
assert info.get_video_streams(), 'Audio recording has no video stream'
print('PASS: GTK preview, PNG/JPEG, collision safety, controls UI, VP8/WebM decoding, EOS and close during recording')
tmp.cleanup()
