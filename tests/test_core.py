import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Settings, reserve_output, parse_controls, parse_modes, capture_source, restore_camera_defaults, session_backend, configure_display_backend

class CoreTests(unittest.TestCase):
    def test_session_backend_and_native_selection(self):
        for environment, expected in [
                ({'XDG_SESSION_TYPE': 'x11', 'WAYLAND_DISPLAY': 'stale', 'DISPLAY': ':0'}, 'x11'),
                ({'XDG_SESSION_TYPE': 'wayland', 'DISPLAY': ':0', 'GDK_BACKEND': 'x11'}, 'wayland'),
                ({'WAYLAND_DISPLAY': 'wayland-1', 'DISPLAY': ':0'}, 'wayland'),
                ({'DISPLAY': ':0', 'GDK_BACKEND': 'wayland'}, 'x11'),
                ({}, None)]:
            with self.subTest(environment=environment):
                env = dict(environment)
                self.assertEqual(session_backend(env), expected)
                self.assertEqual(configure_display_backend(env), expected)
                if expected:
                    self.assertEqual(env['GDK_BACKEND'], expected)
                else:
                    self.assertNotIn('GDK_BACKEND', env)
    def test_collision_and_safe_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = reserve_output(tmp, '../same/name', 'png')
            a.write_bytes(b'keep')
            b = reserve_output(tmp, '../same/name', 'png')
            self.assertNotEqual(a, b)
            self.assertEqual(a.parent, Path(tmp))
            self.assertEqual(a.read_bytes(), b'keep')
            self.assertTrue(b.name.endswith('_001.png'))

    def test_persistence_and_bad_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config/settings.json'
            settings = Settings(path)
            settings.values['folder'] = '/test/path'
            settings.save()
            self.assertEqual(Settings(path).values['folder'], '/test/path')
            path.write_text('{broken')
            self.assertTrue(Settings(path).values['filename'])
            path.write_text('{"mirror": "no", "audio": true}')
            self.assertTrue(Settings(path).values['mirror'])
            self.assertTrue(Settings(path).values['audio'])

    def test_camera_controls(self):
        controls = parse_controls('''
                   brightness 0x00980900 (int) : min=-64 max=64 step=1 default=0 value=4
         white_balance_temperature_auto 0x0098090c (bool) : default=1 value=1
                exposure_auto 0x009a0901 (menu) : min=0 max=3 default=3 value=3
                                1: Manual Mode
                                3: Aperture Priority Mode
               focus_absolute 0x009a090a (int) : min=0 max=255 step=5 default=0 value=10 flags=inactive
                     sharpness 0x0098091b (int) : min=0 max=10 step=1 default=3 value=3
''')
        self.assertEqual(len(controls), 5)
        self.assertEqual(controls[2]['choices'][3], 'Aperture Priority Mode')
        self.assertIn('inactive', controls[3]['flags'])
        self.assertEqual(controls[0]['min'], -64)

    def test_modes(self):
        modes = parse_modes('''
 [0]: 'MJPG' (Motion-JPEG, compressed)
        Size: Discrete 1280x720
                Interval: Discrete 0.033s (30.000 fps)
                Interval: Discrete 0.067s (15.000 fps)
 [1]: 'YUYV' (YUYV 4:2:2)
        Size: Discrete 640x480
                Interval: Discrete 0.033s (30.000 fps)
 [2]: 'H264' (H.264)
        Size: Discrete 1920x1080
                Interval: Discrete 0.033s (30.000 fps)
''')
        self.assertEqual(len(modes), 3)
        self.assertIn('jpegdec', capture_source('/dev/video0', modes[0]))
        self.assertIn('format=YUY2', capture_source('/dev/video0', modes[2]))

    def test_restore_defaults_rechecks_manual_controls(self):
        values = dict(focus_auto=1, focus_absolute=45, sharpness=9)
        writes = []
        def read():
            return parse_controls(f'''
 focus_auto 0x009a090c (bool) : default=0 value={values['focus_auto']}
 focus_absolute 0x009a090a (int) : min=0 max=255 step=5 default=0 value={values['focus_absolute']} {'flags=inactive' if values['focus_auto'] else ''}
 sharpness 0x0098091b (int) : min=0 max=10 step=1 default=3 value={values['sharpness']}
 serial 0x00980900 (int) : default=0 value=3 flags=read-only
''')
        def write(name, value):
            writes.append((name, value))
            values[name] = value
        result = restore_camera_defaults(read, write)
        self.assertEqual(writes, [('sharpness', 3), ('focus_auto', 0), ('focus_absolute', 0)])
        self.assertEqual(result['failed'], [])
        self.assertEqual(result['skipped'], [])

    def test_restore_defaults_partial_failure_and_unavailable_controls(self):
        controls = parse_controls('''
 brightness 0x00980900 (int) : min=-64 max=64 step=1 default=0 value=4
 sharpness 0x0098091b (int) : min=0 max=10 step=1 default=3 value=9
 focus_absolute 0x009a090a (int) : default=0 value=20 flags=inactive
 locked 0x00980901 (int) : default=0 value=1 flags=grabbed
''')
        def write(name, value):
            if name == 'brightness':
                raise RuntimeError('camera rejected value')
        result = restore_camera_defaults(lambda: controls, write)
        self.assertEqual(result['restored'], ['sharpness'])
        self.assertEqual(result['skipped'], ['focus_absolute'])
        self.assertEqual(result['failed'], ['brightness: camera rejected value'])

if __name__ == '__main__':
    unittest.main()
