#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Lumen Camera: GTK3 / GStreamer desktop camera for Linux."""
import argparse
import concurrent.futures
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, Gst, GstVideo
from core import Settings, VERSION, APP_ID, reserve_output, parse_controls, parse_modes, mode_id, mode_label, capture_source
from easter_egg import settings_encounter, launch_hijack

Gst.init(None)


def v4l(device, *args):
    result = subprocess.run(['v4l2-ctl', '-d', device, *args], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Camera did not accept this command.')
    return result.stdout


def camera_inventory():
    devices = []
    for device in sorted(glob.glob('/dev/video[0-9]*'), key=lambda s: int(s[10:])):
        try:
            info = v4l(device, '--info')
            caps = info.split('Device Caps', 1)[-1]
            if 'Video Capture' not in caps:
                continue
            name = Path('/sys/class/video4linux', Path(device).name, 'name').read_text().strip()
            devices.append((device, name))
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            continue
    return devices


def label(text, style=None):
    item = Gtk.Label(label=text, xalign=0)
    item.set_line_wrap(True)
    if style:
        item.get_style_context().add_class(style)
    return item


def button(text, action, style=None):
    item = Gtk.Button(label=text)
    item.connect('clicked', action)
    if style:
        item.get_style_context().add_class(style)
    return item


class MysteryButton(Gtk.Button):
    """A small, keyboard-accessible animated glitch glyph, with no dialog."""
    def __init__(self, action):
        super().__init__()
        self.get_accessible().set_name('?????')
        self.get_style_context().add_class('mystery-button')
        self.connect('clicked', action)
        self.art = Gtk.DrawingArea()
        self.art.set_size_request(132, 34)
        self.art.connect('draw', self.draw_glitch)
        self.add(self.art)
        self.frame = 0
        self.animation = None
        self.connect('map', self.start_animation)
        self.connect('unmap', self.stop_animation)
        self.connect('destroy', self.stop_animation)

    def start_animation(self, *_):
        if self.animation is None:
            self.animation = GLib.timeout_add(90, self.animate)

    def stop_animation(self, *_):
        if self.animation is not None:
            GLib.source_remove(self.animation)
            self.animation = None

    def animate(self):
        self.frame += 1
        self.art.queue_draw()
        return True

    def draw_glitch(self, area, cr):
        cr.select_font_face('monospace', 0, 1)
        cr.set_font_size(22)
        width = cr.text_extents('?????')[4]
        x = (area.get_allocated_width() - width) / 2
        y = (area.get_allocated_height() + 16) / 2
        jitter = (self.frame % 7 == 0)
        for dx, dy, color in [(-2 if jitter else -1, 0, (0.25, 0.92, 0.95)),
                              (2 if jitter else 1, 1, (0.97, 0.31, 0.65)),
                              (0, 0, (0.93, 0.92, 1.0))]:
            cr.set_source_rgb(*color)
            cr.move_to(x + dx, y + dy)
            cr.show_text('?????')
        if jitter:
            cr.set_source_rgba(0.15, 0.09, 0.25, 0.9)
            cr.rectangle(7, 7 + (self.frame * 3 % 20), area.get_allocated_width() - 14, 2)
            cr.fill()
        return False


def window_button(name, action, maximized=None):
    """Draw compact titlebar glyphs independently of the system icon theme."""
    item = Gtk.Button()
    item.set_tooltip_text(name)
    item.get_accessible().set_name(name)
    item.get_style_context().add_class('window-control')
    if name == 'Close':
        item.get_style_context().add_class('close-control')
    icon = Gtk.DrawingArea()
    icon.set_size_request(16, 16)
    icon.set_halign(Gtk.Align.CENTER)
    icon.set_valign(Gtk.Align.CENTER)

    def draw(widget, cr):
        color = item.get_style_context().get_color(item.get_state_flags())
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.set_line_width(1.5)
        cr.translate((widget.get_allocated_width() - 16) / 2,
                     (widget.get_allocated_height() - 16) / 2)
        if name == 'Minimize':
            cr.move_to(3, 11.5)
            cr.line_to(13, 11.5)
        elif name == 'Close':
            cr.move_to(3.5, 3.5)
            cr.line_to(12.5, 12.5)
            cr.move_to(12.5, 3.5)
            cr.line_to(3.5, 12.5)
        elif maximized and maximized():
            cr.move_to(5.5, 5.5)
            cr.line_to(5.5, 2.5)
            cr.line_to(13.5, 2.5)
            cr.line_to(13.5, 10.5)
            cr.line_to(10.5, 10.5)
            cr.rectangle(2.5, 5.5, 8, 8)
        else:
            cr.rectangle(3.5, 3.5, 9, 9)
        cr.stroke()
        return False

    icon.connect('draw', draw)
    item.add(icon)
    item.connect('clicked', action)
    return item


class CameraWindow(Gtk.ApplicationWindow):
    def __init__(self, application, demo=False):
        super().__init__(application=application, title='Lumen Camera')
        self.set_default_size(1180, 760)
        self.set_size_request(830, 550)
        self.settings = Settings()
        self.demo = demo
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.pipeline = None
        self.bus = None
        self.frame = None
        self.pixbuf = None
        self.frame_seen = None
        self.recording = False
        self.finalizing = False
        self.record_path = None
        self.closing = False
        self.closed = False
        self.device = None
        self.mode = None
        self.devices = []
        self.modes = []
        self.controls = []
        self.control_widgets = {}
        self.debounce = {}
        self.generation = 0
        self.last_saved = None
        self.started_at = 0
        self.finalize_timer = None
        self.updating = False

        self.connect('delete-event', self.on_close)
        header = Gtk.HeaderBar(title='Lumen Camera', subtitle='Photo & video studio', show_close_button=False)
        window_controls = Gtk.Box(spacing=6, margin_start=6)
        self.minimize_button = window_button('Minimize', lambda *_: self.iconify())
        self.maximize_button = window_button('Maximize', self.toggle_maximize, self.is_maximized)
        self.close_button = window_button('Close', lambda *_: self.close())
        for control in (self.minimize_button, self.maximize_button, self.close_button):
            window_controls.pack_start(control, False, False, 0)
        header.pack_end(window_controls)
        self.connect('window-state-event', self.update_window_controls)
        header.pack_end(button('Settings', self.open_settings))
        header.pack_end(button('Open folder', self.open_folder))
        self.set_titlebar(header)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(root)
        content = Gtk.Box(spacing=18, margin=20)
        root.pack_start(content, True, True, 0)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.pack_start(left, True, True, 0)
        self.preview = Gtk.DrawingArea()
        self.preview.get_style_context().add_class('preview')
        self.preview.set_size_request(440, 300)
        self.preview.connect('draw', self.draw_preview)
        left.pack_start(self.preview, True, True, 0)
        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        self.photo_button = button('Take photo', self.take_photo, 'primary')
        self.record_button = button('Record video', self.toggle_record, 'primary')
        actions.pack_start(self.photo_button, False, False, 0)
        actions.pack_start(self.record_button, False, False, 0)
        left.pack_start(actions, False, False, 0)
        self.time_label = label('Ready when you are', 'dim')
        self.time_label.set_halign(Gtk.Align.CENTER)
        left.pack_start(self.time_label, False, False, 0)
        side_scroll = Gtk.ScrolledWindow()
        side_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        side_scroll.set_size_request(310, -1)
        content.pack_start(side_scroll, False, False, 0)
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.sidebar.get_style_context().add_class('sidebar')
        side_scroll.add(self.sidebar)
        self.sidebar.pack_start(label('Your camera', 'title'), False, False, 0)
        self.sidebar.pack_start(label('CAMERA', 'section'), False, False, 0)
        self.camera_combo = Gtk.ComboBoxText()
        self.camera_combo.connect('changed', self.camera_changed)
        for cell in self.camera_combo.get_cells():
            cell.set_property('ellipsize', 3)
            cell.set_property('max-width-chars', 26)
        self.sidebar.pack_start(self.camera_combo, False, False, 0)
        self.refresh_button = button('Refresh cameras', self.refresh_cameras)
        self.sidebar.pack_start(self.refresh_button, False, False, 0)
        self.sidebar.pack_start(label('RESOLUTION & FRAME RATE', 'section'), False, False, 0)
        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.connect('changed', self.mode_changed)
        self.sidebar.pack_start(self.mode_combo, False, False, 0)
        self.sidebar.pack_start(label('CAMERA CONTROLS', 'section'), False, False, 0)
        self.controls_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.sidebar.pack_start(self.controls_box, False, False, 0)
        self.sidebar.pack_start(label('Controls depend on your webcam. Manual focus and exposure may require their automatic modes to be off.', 'dim'), False, False, 0)
        self.status_label = label('Looking for cameras…', 'status')
        self.status_label.set_ellipsize(3)
        root.pack_end(self.status_label, False, False, 0)
        self.show_all()
        self.photo_button.set_sensitive(False)
        self.record_button.set_sensitive(False)
        self.preview_tick = GLib.timeout_add(33, self.update_preview)
        self.clock_tick = GLib.timeout_add(250, self.update_clock)
        self.refresh_cameras()

    def toggle_maximize(self, *_):
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    def update_window_controls(self, *_):
        name = 'Restore' if self.is_maximized() else 'Maximize'
        self.maximize_button.set_tooltip_text(name)
        self.maximize_button.get_accessible().set_name(name)
        self.maximize_button.queue_draw()
        return False

    def status(self, message):
        self.status_label.set_text(message)
        self.status_label.set_tooltip_text(message)

    def error(self, message):
        self.status(message)
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE, text='Lumen Camera')
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def background(self, work, done, generation=None):
        future = self.pool.submit(work)
        def finish():
            if self.closed or (generation is not None and generation != self.generation):
                return False
            try:
                value = future.result()
            except Exception as exc:
                done(None, str(exc))
            else:
                done(value, None)
            return False
        future.add_done_callback(lambda _: GLib.idle_add(finish))

    def refresh_cameras(self, *_):
        if self.recording or self.finalizing:
            return
        self.refresh_button.set_sensitive(False)
        self.status('Looking for cameras…')
        def complete(devices, error):
            self.refresh_button.set_sensitive(True)
            self.updating = True
            self.devices = devices or []
            if self.demo:
                self.devices = [('demo', 'Demo camera')]
            previous = self.device or self.settings.values['camera']
            self.camera_combo.remove_all()
            for path, name in self.devices:
                self.camera_combo.append(path, f'{name} ({Path(path).name})')
            self.camera_combo.set_active_id(previous)
            if self.camera_combo.get_active() < 0 and self.devices:
                self.camera_combo.set_active(0)
            self.updating = False
            if self.devices:
                self.camera_changed()
            else:
                self.generation += 1
                self.stop_pipeline()
                self.device = None
                self.render_controls([])
                self.status('No camera found. Connect a webcam, check its permissions, then refresh.')
        self.background(camera_inventory if not self.demo else lambda: [], complete)

    def camera_changed(self, *_):
        if self.updating or self.recording or self.finalizing:
            return
        self.device = self.camera_combo.get_active_id()
        self.generation += 1
        generation = self.generation
        self.stop_pipeline()
        if not self.device:
            return
        self.status('Reading camera capabilities…')
        self.mode_combo.set_sensitive(False)
        device = self.device
        def work():
            if self.demo:
                return [], []
            return parse_modes(v4l(device, '--list-formats-ext')), parse_controls(v4l(device, '--list-ctrls-menus'))
        def complete(value, error):
            self.modes, controls = value if value else ([], [])
            self.updating = True
            self.mode_combo.remove_all()
            self.mode_combo.append('automatic', 'Automatic')
            for mode in self.modes:
                self.mode_combo.append(mode_id(mode), mode_label(mode))
            selected = self.settings.values['mode'] if device == self.settings.values['camera'] else ''
            self.mode_combo.set_active_id(selected)
            if self.mode_combo.get_active() < 0:
                best = next((m for m in self.modes if m['width'] == 1280 and m['height'] == 720 and m['fps_num'] / m['fps_den'] <= 30), None)
                self.mode_combo.set_active_id(mode_id(best))
            self.updating = False
            self.mode_combo.set_sensitive(True)
            self.render_controls(controls)
            self.mode_changed()
            if error:
                self.status('Using automatic capture. Camera details unavailable: ' + error)
        self.background(work, complete, generation)

    def mode_changed(self, *_):
        if self.updating or self.recording or self.finalizing or not self.device:
            return
        selected = self.mode_combo.get_active_id()
        self.mode = next((m for m in self.modes if mode_id(m) == selected), None)
        self.settings.values.update(camera=self.device, mode=selected or '')
        self.save_settings()
        self.start_pipeline()

    def render_controls(self, controls):
        for child in self.controls_box.get_children():
            self.controls_box.remove(child)
        self.controls = controls
        self.control_widgets.clear()
        if not controls:
            self.controls_box.pack_start(label('No adjustable controls reported.' if not self.demo else 'Demo camera has no hardware controls.', 'dim'), False, False, 0)
        priority = ['focus_automatic_continuous', 'focus_auto', 'focus_absolute', 'sharpness', 'exposure_auto', 'auto_exposure', 'exposure_absolute', 'brightness', 'contrast', 'saturation', 'white_balance_automatic', 'white_balance_temperature']
        for control in sorted(controls, key=lambda c: priority.index(c['name']) if c['name'] in priority else len(priority)):
            name = control['name']
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            title = name.replace('_', ' ').capitalize()
            row.pack_start(label(title), False, False, 0)
            if control['kind'] == 'bool':
                widget = Gtk.Switch(halign=Gtk.Align.START)
                widget.set_active(bool(control['value']))
                widget.connect('notify::active', lambda w, p, n=name: self.schedule_control(n, int(w.get_active())))
            elif control['kind'] in ('menu', 'intmenu'):
                widget = Gtk.ComboBoxText()
                for key, choice in control['choices'].items():
                    widget.append(str(key), choice)
                widget.set_active_id(str(control['value']))
                widget.connect('changed', lambda w, n=name: self.schedule_control(n, int(w.get_active_id())) if w.get_active_id() else None)
            else:
                widget = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, control.get('min', 0), max(control.get('min', 0) + 1, control.get('max', 100)), max(1, control.get('step', 1)))
                widget.set_digits(0)
                widget.set_value(control['value'])
                widget.set_value_pos(Gtk.PositionType.RIGHT)
                widget.connect('value-changed', lambda w, n=name: self.schedule_control(n, int(w.get_value())))
            widget.set_sensitive(not any(flag in control['flags'] for flag in ('inactive', 'disabled', 'read-only', 'grabbed')))
            widget.set_tooltip_text(name + (' · ' + control['flags'] if control['flags'] else ''))
            self.control_widgets[name] = widget
            row.pack_start(widget, False, False, 0)
            self.controls_box.pack_start(row, False, False, 0)
        self.controls_box.show_all()

    def schedule_control(self, name, value):
        if self.updating or not self.device:
            return
        if name in self.debounce:
            GLib.source_remove(self.debounce.pop(name))
        device, generation = self.device, self.generation
        def execute():
            self.debounce.pop(name, None)
            if device != self.device or generation != self.generation:
                return False
            def finished(result, error):
                if error:
                    self.status('Control was not applied: ' + error)
                else:
                    self.status(name.replace('_', ' ').capitalize() + ' updated')
                self.refresh_controls()
            self.background(lambda: v4l(device, '--set-ctrl', f'{name}={value}'), finished, generation)
            return False
        self.debounce[name] = GLib.timeout_add(200, execute)

    def refresh_controls(self):
        if self.demo or not self.device:
            return
        device, generation = self.device, self.generation
        def finished(controls, error):
            if error:
                return
            self.updating = True
            for c in controls:
                widget = self.control_widgets.get(c['name'])
                if widget is None or c['name'] in self.debounce:
                    continue
                if c['kind'] == 'bool':
                    widget.set_active(bool(c['value']))
                elif c['kind'] in ('menu', 'intmenu'):
                    widget.set_active_id(str(c['value']))
                else:
                    widget.set_value(c['value'])
                widget.set_sensitive(not any(f in c['flags'] for f in ('inactive', 'disabled', 'read-only', 'grabbed')))
            self.updating = False
        self.background(lambda: parse_controls(v4l(device, '--list-ctrls-menus')), finished, generation)

    def start_pipeline(self, path=None):
        self.stop_pipeline()
        self.frame = self.pixbuf = self.frame_seen = None
        if not self.device:
            return False
        source = capture_source(self.device, self.mode, self.demo)
        description = source + ' ! videoconvert ! tee name=t t. ! queue leaky=downstream max-size-buffers=2 ! videoconvert ! video/x-raw,format=RGB ! appsink name=preview emit-signals=true max-buffers=1 drop=true sync=false wait-on-eos=false'
        if path:
            description += ' t. ! queue ! videoconvert ! video/x-raw,format=I420 ! vp8enc deadline=1 cpu-used=8 threads=4 target-bitrate=6000000 ! webmmux name=mux ! filesink name=recordfile'
            if self.settings.values['audio']:
                description += ' pulsesrc do-timestamp=true ! queue ! audioconvert ! audioresample ! vorbisenc ! queue ! mux.'
        try:
            self.pipeline = Gst.parse_launch(description)
            if path:
                self.pipeline.get_by_name('recordfile').set_property('location', str(path))
            self.pipeline.get_by_name('preview').connect('new-sample', self.on_sample)
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus_handler = self.bus.connect('message', self.on_message)
            if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError('The camera could not start. It may be busy or the selected mode is unsupported.')
            self.status('Starting camera…')
            return True
        except Exception as exc:
            self.stop_pipeline()
            self.error(str(exc))
            return False

    def stop_pipeline(self):
        if self.bus:
            self.bus.disconnect(self.bus_handler)
            self.bus.remove_signal_watch()
            self.bus = None
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        self.frame = self.pixbuf = self.frame_seen = None
        self.photo_button.set_sensitive(False)
        self.record_button.set_sensitive(False)
        self.preview.queue_draw()

    def on_sample(self, sink):
        sample = sink.emit('pull-sample')
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

    def update_preview(self):
        if self.closed:
            return False
        frame = self.frame
        if frame is not None and frame is not self.frame_seen:
            data, width, height, stride = frame
            self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB, False, 8, width, height, stride)
            if self.settings.values['mirror']:
                self.pixbuf = self.pixbuf.flip(True)
            first = self.frame_seen is None
            self.frame_seen = frame
            self.preview.queue_draw()
            self.photo_button.set_sensitive(not self.finalizing)
            self.record_button.set_sensitive(not self.finalizing)
            if first:
                self.status(('Recording to ' + str(self.record_path)) if self.recording else f'Live · {width} × {height}')
        return True

    def draw_preview(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_source_rgb(0.03, 0.045, 0.07)
        cr.paint()
        if self.pixbuf:
            ratio = min(width / self.pixbuf.get_width(), height / self.pixbuf.get_height())
            cr.translate((width - ratio * self.pixbuf.get_width()) / 2, (height - ratio * self.pixbuf.get_height()) / 2)
            cr.scale(ratio, ratio)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
        else:
            cr.set_source_rgb(0.59, 0.65, 0.75)
            cr.select_font_face('Sans')
            cr.set_font_size(18)
            text = 'Camera preview'
            ext = cr.text_extents(text)
            cr.move_to((width - ext.width) / 2, height / 2)
            cr.show_text(text)
        return False

    def take_photo(self, *_):
        if not self.pixbuf or self.finalizing:
            return
        path = None
        try:
            fmt = self.settings.values['photo_format']
            fmt = fmt if fmt in ('png', 'jpeg') else 'png'
            path = reserve_output(self.settings.values['folder'], self.settings.values['filename'], 'jpg' if fmt == 'jpeg' else 'png')
            self.pixbuf.savev(str(path), fmt, ['quality'] if fmt == 'jpeg' else [], ['95'] if fmt == 'jpeg' else [])
            self.last_saved = path
            self.status('Photo saved: ' + str(path))
        except Exception as exc:
            if path:
                path.unlink(missing_ok=True)
            self.error('Could not save photo: ' + str(exc))

    def lock_capture_settings(self, locked):
        for widget in (self.camera_combo, self.mode_combo, self.refresh_button):
            widget.set_sensitive(not locked)

    def toggle_record(self, *_):
        if self.finalizing:
            return
        if self.recording:
            self.finish_record()
            return
        if not self.pixbuf:
            return
        path = None
        try:
            path = reserve_output(self.settings.values['folder'], self.settings.values['filename'], 'webm')
            self.record_path = path
            self.recording = True
            if not self.start_pipeline(path):
                self.recording = False
                self.record_path = None
                path.unlink(missing_ok=True)
                self.start_pipeline()
                return
            self.started_at = time.monotonic()
            self.record_button.set_label('Stop recording')
            self.record_button.set_sensitive(True)
            self.record_button.get_style_context().add_class('recording')
            self.lock_capture_settings(True)
        except Exception as exc:
            self.recording = False
            self.record_path = None
            if path:
                path.unlink(missing_ok=True)
            self.error('Could not start recording: ' + str(exc))

    def finish_record(self):
        if not self.pipeline or self.finalizing:
            return
        self.finalizing = True
        self.record_button.set_sensitive(False)
        self.photo_button.set_sensitive(False)
        self.status('Finishing video…')
        # EOS lets the muxer write duration and seek information before closing.
        self.pipeline.send_event(Gst.Event.new_eos())
        self.finalize_timer = GLib.timeout_add_seconds(15, self.finalize_timeout)

    def finalize_timeout(self):
        self.finalize_timer = None
        self.complete_record(False, 'Video finalization timed out. The file may be incomplete: ' + str(self.record_path))
        return False

    def complete_record(self, success, error=None):
        path = self.record_path
        if self.finalize_timer:
            GLib.source_remove(self.finalize_timer)
            self.finalize_timer = None
        self.stop_pipeline()
        self.recording = self.finalizing = False
        self.record_path = None
        self.record_button.set_label('Record video')
        self.record_button.get_style_context().remove_class('recording')
        self.lock_capture_settings(False)
        if success:
            self.last_saved = path
        if self.closing:
            if error:
                print(error, file=sys.stderr)
            self.close_now()
            return
        self.start_pipeline()
        self.status('Video saved: ' + str(path) if success else error or 'Recording failed.')
        if error:
            self.error(error)

    def on_message(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            detail = 'Camera error: ' + error.message
            if self.recording:
                detail += '\nRecording may be incomplete: ' + str(self.record_path)
                self.complete_record(False, detail)
            else:
                self.stop_pipeline()
                self.error(detail + '\nTry another mode, close other camera apps, or refresh the camera list.')
        elif message.type == Gst.MessageType.EOS and self.recording:
            self.complete_record(True)

    def update_clock(self):
        if self.closed:
            return False
        if self.recording:
            elapsed = int(time.monotonic() - self.started_at)
            self.time_label.set_text(f'● REC  {elapsed // 60:02d}:{elapsed % 60:02d}' + (' · finishing' if self.finalizing else ''))
        else:
            self.time_label.set_text('PNG / JPEG photos · WebM video')
        return True

    def save_settings(self):
        try:
            self.settings.save()
        except OSError as exc:
            self.status('Settings could not be saved: ' + str(exc))

    def open_folder(self, *_):
        try:
            folder = Path(self.settings.values['folder']).expanduser()
            folder.mkdir(parents=True, exist_ok=True)
            Gio.AppInfo.launch_default_for_uri(folder.resolve().as_uri(), None)
        except Exception as exc:
            self.error('Could not open folder: ' + str(exc))

    def open_settings(self, *_):
        dialog = Gtk.Dialog(title='Settings', transient_for=self, modal=True)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Save', Gtk.ResponseType.OK)
        dialog.set_default_size(540, 380)
        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        folder = Gtk.Entry(text=self.settings.values['folder'])
        filename = Gtk.Entry(text=self.settings.values['filename'])
        box.pack_start(label('Save folder', 'section'), False, False, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(folder, True, True, 0)
        def browse(*_):
            chooser = Gtk.FileChooserDialog(title='Choose save folder', transient_for=dialog, action=Gtk.FileChooserAction.SELECT_FOLDER)
            chooser.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Select', Gtk.ResponseType.OK)
            chooser.set_filename(str(Path(folder.get_text()).expanduser()))
            if chooser.run() == Gtk.ResponseType.OK:
                folder.set_text(chooser.get_filename())
            chooser.destroy()
        row.pack_start(button('Browse', browse), False, False, 0)
        box.pack_start(row, False, False, 0)
        box.pack_start(label('Filename (without extension)', 'section'), False, False, 0)
        box.pack_start(filename, False, False, 0)
        box.pack_start(label('Use a fixed name or date codes: %Y year, %m month, %d day, %H hour, %M minute, %S second. Existing files get a numbered suffix.', 'dim'), False, False, 0)
        formats = Gtk.ComboBoxText()
        formats.append('png', 'PNG · lossless')
        formats.append('jpeg', 'JPEG · smaller files')
        formats.set_active_id(self.settings.values['photo_format'])
        box.pack_start(formats, False, False, 0)
        mirror = Gtk.CheckButton(label='Mirror preview and saved photos')
        mirror.set_active(self.settings.values['mirror'])
        box.pack_start(mirror, False, False, 0)
        audio = Gtk.CheckButton(label='Record audio from the default microphone')
        audio.set_active(self.settings.values['audio'])
        audio.set_sensitive(not self.recording)
        box.pack_start(audio, False, False, 0)
        box.pack_start(label('Video keeps the original camera orientation. Audio uses the system default input.', 'dim'), False, False, 0)
        family = settings_encounter()
        if family:
            mystery = MysteryButton(lambda *_: self.start_easter_egg(family))
            mystery.set_halign(Gtk.Align.END)
            box.pack_start(mystery, False, False, 0)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            try:
                path = Path(folder.get_text()).expanduser()
                if not str(path).strip() or not folder.get_text().strip():
                    raise ValueError('Choose a save folder.')
                path.mkdir(parents=True, exist_ok=True)
                test = reserve_output(str(path), '.lumen-write-test', 'tmp')
                test.unlink()
                self.settings.values.update(folder=str(path.resolve()), filename=filename.get_text() or 'Capture_%Y-%m-%d_%H-%M-%S', photo_format=formats.get_active_id() or 'png', mirror=mirror.get_active(), audio=audio.get_active())
                self.save_settings()
                self.frame_seen = None
                break
            except Exception as exc:
                self.error('Invalid save folder: ' + str(exc))
        dialog.destroy()

    def start_easter_egg(self, family):
        try:
            process = launch_hijack(family)
            # Retain/reap the child without terminating it when this window exits.
            def reap():
                return process.poll() is None
            GLib.timeout_add_seconds(2, reap)
        except (OSError, RuntimeError) as exc:
            self.status(str(exc))

    def on_close(self, *_):
        if self.recording or self.finalizing:
            self.closing = True
            if not self.finalizing:
                self.finish_record()
            return True
        self.close_now()
        return True

    def close_now(self):
        if self.closed:
            return
        self.closed = True
        self.stop_pipeline()
        for source in self.debounce.values():
            GLib.source_remove(source)
        self.debounce.clear()
        GLib.source_remove(self.preview_tick)
        GLib.source_remove(self.clock_tick)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.destroy()


class CameraApp(Gtk.Application):
    def __init__(self, demo=False):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE if demo else Gio.ApplicationFlags.FLAGS_NONE)
        self.demo = demo
        self.window = None

    def do_activate(self):
        if self.window is None:
            css = Gtk.CssProvider()
            css.load_from_path(str(Path(__file__).with_name('style.css')))
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.window = CameraWindow(self, self.demo)
        self.window.present()


def main():
    parser = argparse.ArgumentParser(description='Lumen Camera')
    parser.add_argument('--demo', action='store_true', help='Use a synthetic camera for testing')
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args()
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', True)
    app = CameraApp(args.demo)
    return app.run([sys.argv[0]])


if __name__ == '__main__':
    sys.exit(main())
