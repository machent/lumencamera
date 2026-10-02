# SPDX-License-Identifier: GPL-3.0-only
"""V4L2 loopback output, following OBS's Linux virtual-camera approach.

Reference: obsproject/obs-studio, plugins/linux-v4l2/v4l2-output.c.
The independently written Python/GStreamer implementation uses the same kernel
module, output capability checks and YUY2 format. OBS itself is not required.
"""
import fcntl
import logging
import os
import re
import shutil
import struct
import subprocess
import time
from pathlib import Path

VIDIOC_QUERYCAP = 0x80685600
V4L2_CAP_VIDEO_OUTPUT = 0x00000002
V4L2_CAP_DEVICE_CAPS = 0x80000000
CAPABILITY = struct.Struct('=16s32s32sIII3I')
LOG = logging.getLogger('lumencamera.virtual')


def is_loopback_driver(driver):
    return 'v4l2loopback' in re.sub(r'[\s_-]', '', driver.casefold())


def query_device(path):
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        buffer = bytearray(CAPABILITY.size)
        fcntl.ioctl(fd, VIDIOC_QUERYCAP, buffer, True)
        driver, card, _bus, _version, caps, device_caps, *_ = CAPABILITY.unpack(buffer)
        actual = device_caps if caps & V4L2_CAP_DEVICE_CAPS else caps
        text = lambda value: value.split(b'\0', 1)[0].decode('utf-8', errors='replace')
        return dict(path=str(path), name=text(card), driver=text(driver),
                    output=bool(actual & V4L2_CAP_VIDEO_OUTPUT))
    finally:
        os.close(fd)


def virtual_devices(device_root=Path('/dev')):
    found = []
    paths = [p for p in Path(device_root).glob('video*') if re.fullmatch(r'video\d+', p.name)]
    for path in sorted(paths, key=lambda p: int(p.name[5:])):
        try:
            info = query_device(path)
            if is_loopback_driver(info['driver']) and info['output']:
                found.append(info)
        except OSError:
            continue
    # Prefer the camera created by Lumen Camera over another idle loopback.
    return sorted(found, key=lambda info: 'lumencamera' not in info['name'].replace(' ', '').casefold())


def discover_virtual_devices(cancel=None):
    """Load an installed module as OBS does; never install/unload a module."""
    if not Path('/sys/module/v4l2loopback').exists():
        LOG.info('Loading the installed v4l2loopback module with exclusive_caps=1')
        search = os.environ.get('PATH', '') + ':/usr/sbin:/sbin'
        modinfo = shutil.which('modinfo', path=search)
        modprobe = shutil.which('modprobe', path=search)
        if not modinfo or not modprobe or subprocess.run([modinfo, 'v4l2loopback'], capture_output=True, timeout=5).returncode:
            raise RuntimeError('Virtual camera requires the installed v4l2loopback kernel module (the same dependency used by OBS). Install or build it for your running kernel, then try again.')
        pkexec = shutil.which('pkexec')
        if not pkexec:
            raise RuntimeError('Load v4l2loopback first with exclusive_caps=1. Automatic loading needs PolicyKit (pkexec).')
        process = subprocess.Popen([pkexec, modprobe, 'v4l2loopback', 'exclusive_caps=1',
                                    'card_label=LumenCamera Virtual Camera'], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 120
        while True:
            if cancel is not None and cancel.is_set():
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise RuntimeError('Virtual camera startup cancelled.')
            try:
                _stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    raise RuntimeError('Administrator authorization timed out.')
        if process.returncode:
            raise RuntimeError('Could not load v4l2loopback: ' + (stderr.strip() or 'administrator authorization was cancelled'))
    found = virtual_devices()
    if not found:
        raise RuntimeError('No writable, idle v4l2loopback camera was found. Stop any OBS virtual-camera output and check device permissions, then try again. For Discord/WebRTC, the device should use exclusive_caps=1.')
    LOG.info('Available loopback outputs: %s', ', '.join(item['path'] + ' (' + item['name'] + ')' for item in found))
    return found


class VirtualCameraOutput:
    """Independent output pipeline; camera/recording restarts do not close it."""
    def __init__(self, on_error, sink=None):
        from gi.repository import GLib, Gst, GstVideo
        self.GLib, self.Gst, self.GstVideo = GLib, Gst, GstVideo
        self.on_error = on_error
        self.test_sink = sink
        self.pipeline = self.bus = self.handler = self.source = self.flip = None
        self.running = False
        self.input_size = None
        self.mirrored = None
        self.frames_sent = 0

    def start(self, device, width, height, mirror=False):
        Gst = self.Gst
        self.stop()
        if self.test_sink is None:
            info = query_device(device)
            if not is_loopback_driver(info['driver']) or not info['output']:
                raise RuntimeError('The selected virtual camera is busy or is not a v4l2loopback output device.')
        self.width, self.height = width + width % 2, height
        self.frames_sent = 0
        self.blank_stride = (self.width * 3 + 3) & ~3
        self.blank = bytes(self.blank_stride * self.height)
        try:
            self.pipeline = Gst.parse_launch(
                f'appsrc name=frames is-live=true format=time do-timestamp=true block=false '
                f'! queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 '
                f'! videoflip name=mirror ! videoconvert ! videoscale add-borders=true '
                f'! videorate ! video/x-raw,format=YUY2,width={self.width},height={self.height},framerate=30/1,pixel-aspect-ratio=1/1 '
                # Do not let conversion/videorate retain the device's small
                # MMAP pool. Loopbacks configured by OBS may provide only two
                # buffers; keep conversion allocations independent so the sink
                # always has a free device buffer into which it can copy.
                f'! identity name=output drop-allocation=true')
            self.source = self.pipeline.get_by_name('frames')
            self.source.set_property('max-bytes', 0)
            if self.source.find_property('max-buffers'):
                self.source.set_property('max-buffers', 2)
                self.source.set_property('leaky-type', 2)
            self.flip = self.pipeline.get_by_name('mirror')
            self.set_mirror(mirror)
            sink = self.test_sink or Gst.ElementFactory.make('v4l2sink', 'virtual-device')
            if sink is None:
                raise RuntimeError('GStreamer v4l2sink is unavailable. Install the GStreamer good plugins.')
            if self.test_sink is None:
                sink.set_property('device', device)
                # GStreamer's RW output path is an unimplemented write() stub
                # that returns OK without sending frames. Use its supported
                # MMAP/queue/STREAMON output path instead of OBS's direct write().
                sink.set_property('io-mode', 2)  # mmap
                LOG.info('Starting %s: %s, YUY2 %dx%d at 30 fps, io-mode=mmap', device, Gst.version_string(), self.width, self.height)
            sink.set_property('sync', False)
            sink.set_property('async', False)
            self.pipeline.add(sink)
            if not self.pipeline.get_by_name('output').link(sink):
                raise RuntimeError('Could not connect the virtual camera output.')
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.handler = self.bus.connect('message', self.message)
            self.running = True
            if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError('The virtual camera could not start. It may already be in use.')
        except Exception:
            self.stop()
            raise

    def set_mirror(self, mirror):
        if self.flip is not None and mirror != self.mirrored:
            self.flip.set_property('method', 4 if mirror else 0)
            self.mirrored = mirror

    def push(self, frame, mirror=False):
        if not self.running:
            return
        Gst, GstVideo = self.Gst, self.GstVideo
        self.set_mirror(mirror)
        data, width, height, stride = frame if frame is not None else (self.blank, self.width, self.height, self.blank_stride)
        if (width, height) != self.input_size:
            self.source.set_property('caps', Gst.Caps.from_string(f'video/x-raw,format=RGB,width={width},height={height},framerate=30/1,pixel-aspect-ratio=1/1'))
            self.input_size = (width, height)
        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.duration = Gst.SECOND // 30
        GstVideo.buffer_add_video_meta_full(buffer, GstVideo.VideoFrameFlags.NONE,
                                            GstVideo.VideoFormat.RGB, width, height, 1,
                                            [0, 0, 0, 0], [stride, 0, 0, 0])
        result = self.source.emit('push-buffer', buffer)
        if result != Gst.FlowReturn.OK:
            self.stop()
            self.on_error('Virtual camera output stopped: ' + result.value_nick)
        else:
            self.frames_sent += 1
            if self.frames_sent == 1:
                LOG.info('First preview frame queued for virtual-camera output')

    def message(self, _bus, message):
        if not self.running:
            return
        if message.type == self.Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            LOG.error('Output failed in %s: %s\n%s', message.src.get_name(), error.message, debug or 'No additional GStreamer details')
            self.stop()
            self.on_error('Virtual camera error: ' + error.message)
        elif message.type == self.Gst.MessageType.EOS:
            self.stop()
            self.on_error('Virtual camera output ended.')
        elif message.type == self.Gst.MessageType.STATE_CHANGED and message.src == self.pipeline:
            _old, state, _pending = message.parse_state_changed()
            LOG.info('Output pipeline state: %s', state.value_nick)

    def stop(self):
        self.running = False
        if self.bus is not None:
            self.bus.disconnect(self.handler)
            self.bus.remove_signal_watch()
            self.bus = self.handler = None
        if self.pipeline is not None:
            LOG.info('Stopping output (%d preview frames queued)', self.frames_sent)
            self.pipeline.set_state(self.Gst.State.NULL)
        self.pipeline = self.source = self.flip = None
        self.input_size = self.mirrored = None
