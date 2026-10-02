# SPDX-License-Identifier: GPL-3.0-only
"""Turn the accepted warning into a compact video, then finish on real EOS."""
import time
from pathlib import Path
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gst, GstVideo

VIDEO_PATH = Path(__file__).resolve().parent / 'easter-eggs' / 'tape-zero.webm'


class EasterEggVideo:
    def __init__(self, dialog, complete, error, path=VIDEO_PATH, audio_sink=None):
        self.dialog = dialog
        self.complete = complete
        self.error = error
        self.path = Path(path)
        self.audio_sink = audio_sink
        self.pipeline = None
        self.bus = None
        self.frame = self.frame_seen = self.pixbuf = None
        self.phase = 'loading'
        self.finished = False
        self.right_control = False
        self.frames_shown = 0
        self.resize_steps = 0
        self.tick = self.deadline = None
        self.handlers = []

    def start(self):
        # This is the original confirmation window, not a replacement window.
        self.handlers = [self.dialog.connect('delete-event', lambda *_: True),
                         self.dialog.connect('key-press-event', self.key_press),
                         self.dialog.connect('key-release-event', self.key_release),
                         self.dialog.connect('focus-out-event', self.focus_out),
                         self.dialog.connect('destroy', lambda *_: self.finish(False))]
        self.dialog.set_decorated(False)
        self.dialog.set_title('')
        self.dialog.set_resizable(True)
        self.dialog.get_style_context().add_class('easter-video')
        box = self.dialog.get_content_area()
        for child in box.get_children():
            child.destroy()
        self.dialog.get_action_area().hide()
        box.set_spacing(0)
        for setter in (box.set_margin_top, box.set_margin_bottom, box.set_margin_start, box.set_margin_end):
            setter(0)
        self.art = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.art.set_size_request(1, 1)
        self.art.get_accessible().set_name('Video. Right Control plus Escape cancels playback.')
        self.art.connect('draw', self.draw)
        box.pack_start(self.art, True, True, 0)
        self.art.show()
        self.dialog.set_size_request(1, 1)
        self.start_size = self.dialog.get_size()
        self.tick = GLib.timeout_add(16, self.animate)
        try:
            if not self.path.is_file():
                raise FileNotFoundError('The optional video file is missing.')
            self.pipeline = Gst.ElementFactory.make('playbin', 'easter-video')
            if self.pipeline is None:
                raise RuntimeError('Video playback is unavailable.')
            sink = Gst.parse_bin_from_description('videoconvert ! video/x-raw,format=RGB ! appsink name=frames emit-signals=true max-buffers=1 drop=true sync=true wait-on-eos=false', True)
            frames = sink.get_by_name('frames')
            frames.connect('new-sample', self.sample)
            frames.connect('new-preroll', self.preroll)
            self.pipeline.set_property('video-sink', sink)
            if self.audio_sink is not None:
                self.pipeline.set_property('audio-sink', self.audio_sink)
            self.pipeline.set_property('flags', 3)  # Video/audio; no subtitles.
            self.pipeline.set_property('uri', self.path.resolve().as_uri())
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect('message', self.message)
            self.deadline = GLib.timeout_add_seconds(8, self.load_timeout)
            if self.pipeline.set_state(Gst.State.PAUSED) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError('The video could not be opened.')
        except (OSError, RuntimeError, GLib.Error) as exc:
            self.finish(False, str(exc))

    def load_timeout(self):
        self.deadline = None
        self.finish(False, 'The video did not finish loading.')
        return False

    def key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Control_R:
            self.right_control = True
        elif event.keyval == Gdk.KEY_Escape and self.right_control:
            self.finish(False)
        # Suppress GTK Dialog's Escape binding and app/window shortcuts.
        return True

    def key_release(self, _widget, event):
        if event.keyval == Gdk.KEY_Control_R:
            self.right_control = False
        return True

    def focus_out(self, *_):
        self.right_control = False
        return False

    def preroll(self, sink):
        return self.capture(sink.emit('pull-preroll'))

    def sample(self, sink):
        return self.capture(sink.emit('pull-sample'))

    def capture(self, sample):
        if sample is None:
            return Gst.FlowReturn.EOS
        info = GstVideo.VideoInfo.new_from_caps(sample.get_caps())
        buffer = sample.get_buffer()
        ok, mapped = buffer.map(Gst.MapFlags.READ)
        if ok:
            try:
                self.frame = (bytes(mapped.data), info.width, info.height, info.stride[0])
            finally:
                buffer.unmap(mapped)
        return Gst.FlowReturn.OK

    def message(self, _bus, message):
        if self.finished:
            return
        if message.type == Gst.MessageType.ERROR:
            error, _ = message.parse_error()
            self.finish(False, 'Video playback failed: ' + error.message)
        elif message.type == Gst.MessageType.EOS and self.phase == 'playing':
            self.finish(True)
        elif message.type == Gst.MessageType.ASYNC_DONE and self.phase == 'loading':
            if self.frame is None:
                self.finish(False, 'The file has no playable video.')
                return
            if self.deadline is not None:
                GLib.source_remove(self.deadline)
                self.deadline = None
            _, width, height, _ = self.frame
            display = self.dialog.get_display()
            monitor = display.get_monitor_at_window(self.dialog.get_window())
            area = monitor.get_workarea()
            scale = min(640 / width, area.width * 0.7 / width, area.height * 0.7 / height)
            self.target_size = (round(width * scale), round(height * scale))
            self.resize_started = time.monotonic()
            self.phase = 'resizing'

    def animate(self):
        if self.finished:
            return False
        if self.phase == 'resizing':
            progress = min(1, (time.monotonic() - self.resize_started) / 0.42)
            ease = 1 - (1 - progress) ** 3
            self.dialog.resize(*(round(a + (b - a) * ease) for a, b in zip(self.start_size, self.target_size)))
            self.resize_steps += 1
            if progress == 1:
                self.phase = 'playing'
                if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                    self.finish(False, 'The video could not start playing.')
                    return False
        if self.phase == 'playing' and self.frame is not self.frame_seen and self.frame is not None:
            data, width, height, stride = self.frame
            self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB, False, 8, width, height, stride)
            self.frame_seen = self.frame
            self.frames_shown += 1
        self.art.queue_draw()
        return True

    def draw(self, area, cr):
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        if self.pixbuf is not None and self.phase == 'playing':
            width, height = area.get_allocated_width(), area.get_allocated_height()
            scale = min(width / self.pixbuf.get_width(), height / self.pixbuf.get_height())
            cr.translate((width - self.pixbuf.get_width() * scale) / 2, (height - self.pixbuf.get_height() * scale) / 2)
            cr.scale(scale, scale)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
        return False

    def finish(self, completed, error=None):
        if self.finished:
            return
        self.finished = True
        self.phase = 'finished'
        for name in ('tick', 'deadline'):
            source = getattr(self, name)
            if source is not None:
                GLib.source_remove(source)
                setattr(self, name, None)
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
        if self.bus is not None:
            self.bus.disconnect_by_func(self.message)
            self.bus.remove_signal_watch()
            self.bus = None
        for handler in self.handlers:
            self.dialog.disconnect(handler)
        self.handlers = []
        self.dialog.destroy()
        if error:
            self.error(error)
        self.complete(completed)
