"""End-to-end GTK, photos, EOS finalization and shutdown using a test camera."""
import os
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME'] = str(Path(tmp.name) / 'config')
from app import CameraApp, GLib, Gdk, GdkPixbuf, Gst, Gtk
from unittest.mock import patch

app = CameraApp(demo=True)
failures = []
phase = 0
photo = None
video = None
microphone_calls = []


class FakeMicrophone:
    def __init__(self, frequency):
        self.frequency = frequency

    def create_element(self, name):
        microphone_calls.append(self.frequency)
        source = Gst.ElementFactory.make('audiotestsrc', name)
        source.set_property('is-live', True)
        source.set_property('freq', self.frequency)
        return source


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def configure_recording(audio=False, cancel=False):
    """Inspect the actual dialog and respond after async discovery completes."""
    dialog = app.window.record_dialog
    if dialog is None:
        return True
    check = next(x for x in descendants(dialog) if isinstance(x, Gtk.CheckButton))
    combo = next(x for x in descendants(dialog) if isinstance(x, Gtk.ComboBoxText))
    if len(combo.get_model()) < 3:
        return True
    try:
        assert check.get_label() == 'Record with microphone'
        assert not check.get_active() and not combo.get_sensitive()
        assert combo.get_parent().get_opacity() < 0.6
        if audio:
            check.set_active(True)
            assert combo.get_sensitive()
            combo.set_active_id('test-usb')
            def confirm():
                assert combo.get_parent().get_opacity() > 0.95
                screen = Gdk.pixbuf_get_from_window(dialog.get_window(), 0, 0, dialog.get_allocated_width(), dialog.get_allocated_height())
                screen.savev(str(Path(os.environ.get('RUNNER_TEMP', str(ROOT.parent))) / 'lumen-recording-preview.png'), 'png', [], [])
                dialog.response(Gtk.ResponseType.OK)
                return False
            GLib.timeout_add(250, confirm)
        else:
            dialog.response(Gtk.ResponseType.CANCEL if cancel else Gtk.ResponseType.OK)
    except Exception as exc:
        failures.append(repr(exc))
        dialog.response(Gtk.ResponseType.CANCEL)
    return False

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
            # Cancel must preserve settings and must not create a video file.
            old_settings = dict(w.settings.values)
            GLib.timeout_add(40, configure_recording, False, True)
            w.toggle_record()
            assert not w.recording and w.settings.values == old_settings
            assert not list(Path(tmp.name).glob('*.mkv'))
            GLib.timeout_add(40, configure_recording)
            w.toggle_record()
            assert w.recording
            assert w.record_path.suffix == '.mkv'
            assert w.pipeline.get_by_name('mux').get_factory().get_name() == 'matroskamux'
            assert w.pipeline.get_by_name('recordaudio') is None
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
            assert message and message.type == Gst.MessageType.EOS, 'Recorded MKV failed decoding'
            # Test the optional audio branch with a synthetic source.
            # This verifies encoding/muxing without claiming microphone hardware testing.
            GLib.timeout_add(40, configure_recording, True)
            w.toggle_record()
            assert w.pipeline.get_by_name('recordaudio').get_property('freq') == 880
            assert microphone_calls == [880], 'Only the selected microphone must be opened'
            assert w.settings.values['microphone'] == 'test-usb'
            assert w.settings.values['audio'] is True
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
with patch('app.microphone_inventory', return_value=[
        dict(id='test-built-in', name='Built-in microphone', device=FakeMicrophone(440)),
        dict(id='test-usb', name='USB microphone', device=FakeMicrophone(880))]):
    app.run(['smoke'])
assert phase == 4 and not failures, (phase, failures)
assert len(list(Path(tmp.name).glob('*.mkv'))) == 2
import gi
gi.require_version('GstPbutils', '1.0')
from gi.repository import GstPbutils
discoverer = GstPbutils.Discoverer.new(5 * Gst.SECOND)
silent = discoverer.discover_uri((Path(tmp.name) / 'test.mkv').as_uri())
assert not silent.get_audio_streams(), 'Microphone unchecked must produce video-only MKV'
info = discoverer.discover_uri((Path(tmp.name) / 'test_001.mkv').as_uri())
assert info.get_audio_streams(), 'Audio recording has no audio stream'
assert info.get_video_streams(), 'Audio recording has no video stream'
assert info.get_duration() > Gst.SECOND, 'Audio/video recording must have a valid duration'
print('PASS: GTK preview, PNG/JPEG, recording dialog, microphone selection, MKV with/without audio, EOS and close during recording')
tmp.cleanup()
