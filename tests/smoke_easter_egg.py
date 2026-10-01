"""Check the real Settings button, animation and cleanup with a fake game."""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import CameraApp, MysteryButton, Gtk, GLib, Gdk

app = CameraApp(demo=True)
failure = []


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def test():
    if app.window is None:
        return True
    w = app.window
    try:
        with patch('app.settings_encounter', side_effect=['fedora', None]), \
             patch('app.launch_hijack') as launch:
            launch.return_value.poll.return_value = 0
            seen = []
            def inspect():
                dialog = next(x for x in Gtk.Window.list_toplevels() if x.get_title() == 'Settings')
                try:
                    buttons = [x for x in descendants(dialog) if isinstance(x, MysteryButton)]
                    if not seen:
                        assert len(buttons) == 1
                        mystery = buttons[0]
                        assert mystery.animation and mystery.frame > 0
                        assert mystery.get_accessible().get_name() == '?????'
                        screen = Gdk.pixbuf_get_from_window(dialog.get_window(), 0, 0, dialog.get_allocated_width(), dialog.get_allocated_height())
                        screen.savev(str(Path(__file__).resolve().parents[2] / 'lumen-easter-egg-preview.png'), 'png', [], [])
                        mystery.clicked()
                        launch.assert_called_once_with('fedora')
                        seen.append(mystery)
                    else:
                        assert not buttons
                except Exception as error:
                    failure.append(repr(error))
                finally:
                    dialog.response(Gtk.ResponseType.CANCEL)
                return False
            GLib.timeout_add(450, inspect)
            w.open_settings()
            assert seen[0].animation is None
            GLib.timeout_add(200, inspect)
            w.open_settings()
        print('Settings eligibility, animation, immediate launch and cleanup passed', flush=True)
    except Exception as error:
        failure.append(repr(error))
    w.close_now()
    return False


GLib.timeout_add(200, test)
GLib.timeout_add_seconds(15, lambda: (failure.append('Timed out'), app.window.close_now(), False)[-1])
app.run(['egg-smoke'])
assert not failure, failure
