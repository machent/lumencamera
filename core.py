# SPDX-License-Identifier: GPL-3.0-only
"""Hardware-independent configuration, naming and V4L2 parsing."""
import datetime
import json
import os
import re
import tempfile
from pathlib import Path

VERSION = '1.2'
APP_ID = 'io.github.machent.LumenCamera'


def session_backend(env=None):
    """Prefer the login session type; DISPLAY also exists in Wayland sessions."""
    env = os.environ if env is None else env
    session = env.get('XDG_SESSION_TYPE', '').strip().lower()
    if session in ('wayland', 'x11'):
        return session
    if env.get('WAYLAND_DISPLAY'):
        return 'wayland'
    if env.get('DISPLAY'):
        return 'x11'
    return None


def configure_display_backend(env=None):
    """Select one native GTK backend before GTK initializes its display."""
    env = os.environ if env is None else env
    backend = session_backend(env)
    if backend:
        env['GDK_BACKEND'] = backend
    return backend


def default_settings():
    pictures = Path.home() / 'Pictures'
    return dict(folder=str(pictures / 'Lumen Camera'), filename='Capture_%Y-%m-%d_%H-%M-%S',
                photo_format='png', mirror=True, audio=False, microphone='default', camera='', mode='')


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'lumen-camera/settings.json'
        self.values = default_settings()
        try:
            values = json.loads(self.path.read_text())
            for key, value in values.items():
                if key in self.values and type(value) is type(self.values[key]):
                    self.values[key] = value
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.settings-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(self.values, stream, indent=2)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def reserve_output(folder, pattern, extension):
    directory = Path(folder).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    base = datetime.datetime.now().strftime(pattern.strip() or 'Capture_%Y-%m-%d_%H-%M-%S')
    base = re.sub(r'[/\\\x00-\x1f]', '_', base).strip(' .')[:180] or 'Capture'
    for number in range(100000):
        suffix = f'_{number:03d}' if number else ''
        path = directory / f'{base}{suffix}.{extension}'
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return path
        except FileExistsError:
            continue
    raise OSError('Too many files with this filename. Choose another filename in Settings.')


def parse_controls(text):
    controls = []
    current = None
    for line in text.splitlines():
        match = re.match(r'\s*(\w+)\s+0x[0-9a-f]+\s+\(([^)]+)\)\s*:\s*(.*)', line)
        if match:
            name, kind, details = match.groups()
            if kind not in ('int', 'bool', 'menu', 'intmenu'):
                current = None
                continue
            current = dict(name=name, kind=kind, choices={}, flags=details.split('flags=')[-1] if 'flags=' in details else '')
            for key in ('min', 'max', 'step', 'default', 'value'):
                value = re.search(r'\b' + key + r'=(-?\d+)', details)
                if value:
                    current[key] = int(value.group(1))
            if 'value' in current:
                controls.append(current)
        elif current:
            choice = re.match(r'\s*(-?\d+):\s*(.+)', line)
            if choice:
                current['choices'][int(choice.group(1))] = choice.group(2)
    return controls


RAW_FORMATS = {'YUYV': 'YUY2', 'UYVY': 'UYVY', 'NV12': 'NV12', 'YU12': 'I420', 'RGB3': 'RGB', 'BGR3': 'BGR', 'GREY': 'GRAY8'}


def restore_camera_defaults(read_controls, write_control):
    """Restore driver defaults, rechecking availability after auto-mode changes."""
    targets = {c['name']: c['default'] for c in read_controls()
               if 'default' in c and not any(f in c['flags'] for f in ('disabled', 'read-only', 'grabbed'))}
    restored, failed = [], []
    pending = dict(targets)
    # Manual values first: restoring an auto mode may deactivate them. A second
    # pass handles controls that become available when an auto default is off.
    for _ in range(2):
        controls = sorted(read_controls(), key=lambda c: 'auto' in c['name'])
        for c in controls:
            name = c['name']
            if name not in pending or any(f in c['flags'] for f in ('inactive', 'disabled', 'read-only', 'grabbed')):
                continue
            value = pending.pop(name)
            try:
                write_control(name, value)
            except Exception as exc:
                failed.append(f'{name}: {exc}')
            else:
                restored.append(name)
    return dict(restored=restored, failed=failed, skipped=list(pending))


def parse_modes(text):
    modes = []
    fourcc = None
    size = None
    for line in text.splitlines():
        fmt = re.search(r"\[\d+\]: '([^']+)'", line)
        if fmt:
            fourcc, size = fmt.group(1), None
        match = re.search(r'Size: Discrete (\d+)x(\d+)', line)
        if match:
            size = tuple(map(int, match.groups()))
        interval = re.search(r'Interval: Discrete ([0-9.]+)s \(([0-9.]+) fps\)', line)
        if interval and size and (fourcc in RAW_FORMATS or fourcc in ('MJPG', 'JPEG')):
            from fractions import Fraction
            fps = Fraction(interval.group(2)).limit_denominator(1001)
            mode = dict(format=fourcc, width=size[0], height=size[1], fps_num=fps.numerator, fps_den=fps.denominator)
            if mode not in modes:
                modes.append(mode)
    return sorted(modes, key=lambda m: (m['width'] * m['height'], m['fps_num'] / m['fps_den'], m['format']), reverse=True)


def mode_id(mode):
    if not mode:
        return 'automatic'
    return '{format}:{width}x{height}:{fps_num}/{fps_den}'.format(**mode)


def mode_label(mode):
    return '{} × {} · {:g} fps · {}'.format(mode['width'], mode['height'], mode['fps_num'] / mode['fps_den'], mode['format'])


def capture_source(device, mode=None, demo=False):
    if demo:
        return 'videotestsrc is-live=true pattern=smpte ! video/x-raw,width=1280,height=720,framerate=30/1'
    # Device is selected from enumerated /dev nodes, never interpreted by a shell.
    source = 'v4l2src device="{}" do-timestamp=true'.format(device.replace('\\', '\\\\').replace('"', '\\"'))
    if mode:
        caps = 'width={width},height={height},framerate={fps_num}/{fps_den}'.format(**mode)
        if mode['format'] in ('MJPG', 'JPEG'):
            return source + ' ! image/jpeg,' + caps + ' ! jpegdec'
        return source + ' ! video/x-raw,format=' + RAW_FORMATS[mode['format']] + ',' + caps
    return source + ' ! decodebin'
