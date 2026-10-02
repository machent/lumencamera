"""Check the real Settings button, animation and cleanup with a fake game."""
import sys
import os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cairo
from app import CameraApp, MysteryButton, Gtk, GLib, Gdk, APP_ID, running_on_wayland

expect_wayland = len(sys.argv) > 1 and sys.argv[1] == 'wayland'

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
        assert running_on_wayland() == expect_wayland
        assert os.environ['GDK_BACKEND'] == ('wayland' if expect_wayland else 'x11')
        assert GLib.get_prgname() == APP_ID
        assert Gdk.get_program_class() == APP_ID
        assert Gtk.Window.get_default_icon_list(), 'Explicit window icon must load'
        if not expect_wayland:
            import subprocess
            import gi
            gi.require_version('GdkX11', '3.0')
            from gi.repository import GdkX11
            xid = GdkX11.X11Window.get_xid(w.get_window())
            properties = subprocess.check_output(['xprop', '-id', str(xid), 'WM_CLASS', '_NET_WM_ICON'], text=True)
            assert APP_ID in properties and 'not found' not in properties
        with patch('app.settings_encounter', side_effect=['fedora', None]) as encounter, \
             patch('app.launch_hijack') as launch:
            launch.return_value.poll.return_value = 0
            seen = []
            def inspect():
                dialog = next(x for x in Gtk.Window.list_toplevels() if x.get_title() == 'Settings')
                try:
                    buttons = [x for x in descendants(dialog) if isinstance(x, MysteryButton)]
                    if not seen and expect_wayland:
                        assert len(buttons) == 1
                        mystery = buttons[0]
                        assert mystery.animation and mystery.frame > 0
                        assert mystery.get_accessible().get_name() == '?????'
                        assert len(mystery.frames) == 24
                        frames = [bytes(x.get_data()) for x in mystery.frames]
                        assert len(set(frames)) == 24, 'Glitch frames must animate'
                        stride = mystery.frames[0].get_stride()
                        # The aura above the button face must move, too.
                        aura = [x[5 * stride:15 * stride] for x in frames]
                        assert len(set(aura)) > 12, 'Aura must glitch independently'
                        # Wayland intentionally does not allow arbitrary window
                        # screenshots; render the GTK widget into our surface.
                        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, dialog.get_allocated_width(), dialog.get_allocated_height())
                        dialog.draw(cairo.Context(surface))
                        screen = Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.get_width(), surface.get_height())
                        preview_directory = Path(os.environ.get('RUNNER_TEMP', str(Path(__file__).resolve().parents[2])))
                        screen.savev(str(preview_directory / 'lumen-easter-egg-preview.png'), 'png', [], [])
                        mystery.clicked()
                        launch.assert_called_once_with('fedora')
                        seen.append(mystery)
                    else:
                        assert not buttons
                        if not expect_wayland:
                            encounter.assert_not_called()
                            launch.assert_not_called()
                except Exception as error:
                    failure.append(repr(error))
                finally:
                    dialog.response(Gtk.ResponseType.CANCEL)
                return False
            GLib.timeout_add(450, inspect)
            w.open_settings()
            if expect_wayland:
                assert seen[0].animation is None
            GLib.timeout_add(200, inspect)
            w.open_settings()
        print('PASS: native backend, application identity, icon and Settings eligibility' + ('/animation/cleanup on Wayland' if expect_wayland else ' with no mystery button on X11'), flush=True)
    except Exception as error:
        failure.append(repr(error))
    w.close_now()
    return False


GLib.timeout_add(200, test)
GLib.timeout_add_seconds(15, lambda: (failure.append('Timed out'), app.window.close_now(), False)[-1])
app.run(['egg-smoke'])
assert not failure, failure
