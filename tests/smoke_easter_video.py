"""Actual bundled video, CRT frames, right-control cancellation and playback-timeline actions.

Never executes a HIJACK binary; every child launch is mocked.
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cairo
from app import CameraApp, MysteryButton, Gtk, Gdk, GLib, Gst
from video_easter import EasterEggVideo, VIDEO_PATH, HIJACK_START_NS, VIDEO_END_NS

app = CameraApp(demo=True)
failure = []


def test():
    if app.window is None:
        return True
    window = app.window
    with patch('app.launch_hijack') as launch:
        launch.return_value.poll.return_value = 0
        try:
            # Use the real bundled clip with clocked audio; launch must occur
            # at 9.50s with the window still open, and video must stop at 10.90s.
            dialog = Gtk.Dialog(title='Test video', transient_for=window, modal=True)
            dialog.set_default_size(642, 230)
            mystery = MysteryButton(lambda *_: None)
            dialog.get_content_area().pack_start(mystery, False, False, 0)
            dialog.show_all()
            completed = []
            def finish(completion):
                assert not dialog.get_visible()
                completed.append(completion)
                window.finish_easter_video(completion)
                loop.quit()
            audio = Gst.ElementFactory.make('fakesink')
            audio.set_property('sync', True)
            launched_at = []
            def timed_launch():
                try:
                    assert dialog.get_visible() and video.phase == 'playing'
                    assert HIJACK_START_NS <= video.last_position < HIJACK_START_NS + 250 * Gst.MSECOND
                    launched_at.append(video.last_position)
                    window.launch_easter_game('fedora')
                except Exception as exc:
                    failure.append(repr(exc))
            video = EasterEggVideo(dialog, finish, failure.append, audio_sink=audio, launch=timed_launch)
            window.easter_video = video
            window.easter_used = True
            loop = GLib.MainLoop()
            start = time.monotonic()
            video.start()
            # CRT animation starts on the Settings button, independently of
            # the video. Exercise its output without needing a physical screen.
            test_button = MysteryButton(lambda *_: None)
            test_button.frames = test_button.build_frames(190, 78)
            test_button.shutdown()
            assert not test_button.get_sensitive()
            class Area:
                def get_allocated_width(self): return 190
                def get_allocated_height(self): return 78
            crt = []
            for elapsed in (0.02, 0.22, 0.34, 0.5):
                test_button.crt_started = time.monotonic() - elapsed
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 190, 78)
                test_button.draw_glitch(Area(), cairo.Context(surface))
                crt.append(bytes(surface.get_data()))
            assert len(set(crt)) == 4 and not any(crt[-1]), 'CRT must collapse to a blank surface'
            test_button.destroy()
            inspected = []
            def inspect():
                if video.phase != 'playing':
                    return True
                try:
                    assert window.easter_video is video
                    assert video.resize_steps > 4
                    assert video.target_size == (640, 480)
                    assert tuple(dialog.get_size()) == video.target_size
                    assert not dialog.get_decorated()
                    assert dialog.get_content_area().get_margin_top() == 0
                    launch.assert_not_called()
                    # Real GTK key signals: Escape/left Ctrl do not cancel.
                    def key(kind, value):
                        event = Gdk.Event.new(kind)
                        event.keyval = value
                        event.window = dialog.get_window()
                        return dialog.emit('key-press-event' if kind == Gdk.EventType.KEY_PRESS else 'key-release-event', event)
                    key(Gdk.EventType.KEY_PRESS, Gdk.KEY_Escape)
                    key(Gdk.EventType.KEY_PRESS, Gdk.KEY_Control_L)
                    key(Gdk.EventType.KEY_PRESS, Gdk.KEY_Escape)
                    key(Gdk.EventType.KEY_RELEASE, Gdk.KEY_Control_L)
                    key(Gdk.EventType.KEY_PRESS, Gdk.KEY_F4)
                    event = Gdk.Event.new(Gdk.EventType.DELETE)
                    event.window = dialog.get_window()
                    assert dialog.emit('delete-event', event)
                    assert window.on_close() is True and not window.closed
                    assert not video.finished and dialog.get_visible()
                    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, dialog.get_allocated_width(), dialog.get_allocated_height())
                    dialog.draw(cairo.Context(surface))
                    directory = Path(os.environ.get('RUNNER_TEMP', str(Path(__file__).resolve().parents[2])))
                    surface.write_to_png(str(directory / 'lumen-easter-video-preview.png'))
                    inspected.append(True)
                except Exception as exc:
                    failure.append(repr(exc))
                    video.finish(False)
                return False
            GLib.timeout_add(1500, inspect)
            def timeout():
                if not video.finished:
                    failure.append('Full clip timed out')
                    video.finish(False)
                return False
            timer = GLib.timeout_add_seconds(18, timeout)
            loop.run()
            GLib.source_remove(timer)
            assert inspected and completed == [True]
            assert len(launched_at) == 1
            assert VIDEO_END_NS <= video.last_position < VIDEO_END_NS + 250 * Gst.MSECOND
            assert video.last_position - launched_at[0] >= Gst.SECOND, 'The video must keep running after HIJACK starts'
            video.animate()
            video.finish(True)
            assert video.frames_shown > 100 and video.tick is None and video.deadline is None
            assert video.pipeline.get_state(0)[1] == Gst.State.NULL
            launch.assert_called_once_with('fedora')
            launch.reset_mock()
            # Cancellation shortcut is specifically the right Control key;
            # focus loss clears it, and repeated cleanup never launches a game.
            dialog = Gtk.Dialog(transient_for=window, modal=True)
            dialog.show_all()
            done = []
            video = EasterEggVideo(dialog, done.append, failure.append, audio_sink=audio, launch=lambda: window.launch_easter_game('fedora'))
            video.start()
            def press(value):
                event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
                event.keyval = value
                event.window = dialog.get_window()
                dialog.emit('key-press-event', event)
            press(Gdk.KEY_Control_R)
            video.focus_out()
            press(Gdk.KEY_Escape)
            assert not video.finished
            press(Gdk.KEY_Control_R)
            press(Gdk.KEY_Escape)
            assert video.finished and done == [False] and video.tick is None
            video.finish(True)
            assert done == [False]
            # Missing files are failures, never completion.
            done = []
            errors = []
            dialog = Gtk.Dialog(transient_for=window)
            dialog.show_all()
            video = EasterEggVideo(dialog, done.append, errors.append, path=VIDEO_PATH.with_name('missing.webm'), launch=lambda: window.launch_easter_game('fedora'))
            video.start()
            assert done == [False] and errors
            launch.assert_not_called()
            # Closing Lumen Camera while a clip is active also cancels it.
            dialog = Gtk.Dialog(transient_for=window)
            dialog.show_all()
            video = EasterEggVideo(dialog, window.finish_easter_video, failure.append, audio_sink=audio, launch=lambda: window.launch_easter_game('fedora'))
            window.easter_video = video
            video.start()
            window.close_now()
            assert video.finished and video.pipeline.get_state(0)[1] == Gst.State.NULL
            launch.assert_not_called()
            print('PASS: bundled 4:3 video, smooth resize, CRT shutdown, launch at 9.50s/stop at 10.90s, close-key handling, Right Ctrl+Escape, error and close cleanup', flush=True)
        except Exception as exc:
            failure.append(repr(exc))
    window.close_now()
    return False


GLib.timeout_add(200, test)
app.run(['easter-video-smoke'])
assert not failure, failure
