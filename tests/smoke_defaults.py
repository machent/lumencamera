"""Exercise confirmation, cancel, asynchronous reset and driver errors in GTK."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import CameraApp, Gtk, GLib
from core import parse_controls

app = CameraApp(demo=True)
failures, writes = [], []
values = dict(brightness=9, sharpness=8, focus_auto=1, focus_absolute=40)
phase = 0
original_settings = None


def fake_v4l(device, command, *args):
    assert device == '/dev/video-test'
    if command == '--list-ctrls-menus':
        return f'''
 brightness 0x00980900 (int) : min=0 max=10 step=1 default=3 value={values['brightness']}
 sharpness 0x0098091b (int) : min=0 max=10 step=1 default=2 value={values['sharpness']}
 focus_auto 0x009a090c (bool) : default=0 value={values['focus_auto']}
 focus_absolute 0x009a090a (int) : min=0 max=255 step=5 default=0 value={values['focus_absolute']} {'flags=inactive' if values['focus_auto'] else ''}
 readonly 0x00980901 (int) : default=0 value=3 flags=read-only
'''
    assert command == '--set-ctrl'
    name, value = args[0].split('=')
    writes.append((name, int(value)))
    if name == 'sharpness':
        raise RuntimeError('Driver rejected sharpness')
    values[name] = int(value)
    return ''


def respond(response):
    dialogs = [x for x in Gtk.Window.list_toplevels() if isinstance(x, Gtk.MessageDialog)]
    assert len(dialogs) == 1
    assert dialogs[0].get_property('text') == 'Restore camera defaults?'
    dialogs[0].response(response)
    return False


def tick():
    global phase, original_settings
    if app.window is None or not app.window.pixbuf:
        return True
    w = app.window
    try:
        if phase == 0:
            assert not w.defaults_button.get_sensitive(), 'Demo defaults must be disabled'
            original_settings = dict(w.settings.values)
            w.demo = False
            w.device = '/dev/video-test'
            w.render_controls(parse_controls(fake_v4l(w.device, '--list-ctrls-menus')))
            assert w.defaults_button.get_sensitive()
            GLib.timeout_add(50, respond, Gtk.ResponseType.CANCEL)
            w.defaults_button.clicked()
            assert not writes and not w.defaults_busy, 'Cancel must not write to camera'
            w.schedule_control('brightness', 10)
            GLib.timeout_add(50, respond, Gtk.ResponseType.ACCEPT)
            w.defaults_button.clicked()
            assert w.defaults_busy and not w.debounce
            assert not w.camera_combo.get_sensitive()
            assert not w.defaults_button.get_sensitive()
            phase = 1
        elif phase == 1 and not w.defaults_busy:
            assert writes == [('brightness', 3), ('sharpness', 2), ('focus_auto', 0), ('focus_absolute', 0)], writes
            assert w.control_widgets['brightness'].get_value() == 3
            assert w.control_widgets['focus_absolute'].get_value() == 0
            assert not w.control_widgets['readonly'].get_sensitive()
            assert w.camera_combo.get_sensitive() and w.defaults_button.get_sensitive()
            assert 'Driver rejected sharpness' in w.status_label.get_text()
            assert w.settings.values == original_settings
            phase = 2
            w.close_now()
            return False
    except Exception as exc:
        failures.append(repr(exc))
        w.close_now()
        return False
    return True


def timeout():
    failures.append('Defaults smoke test timed out')
    if app.window:
        app.window.close_now()
    return False


with patch('app.v4l', side_effect=fake_v4l):
    GLib.timeout_add(200, tick)
    GLib.timeout_add_seconds(15, timeout)
    app.run(['defaults-smoke'])
assert phase == 2 and not failures, (phase, failures)
print('PASS: Camera Defaults confirmation, cancel, driver defaults, dependent controls and partial errors')
