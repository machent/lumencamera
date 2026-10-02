import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import virtual_camera as vc


class VirtualCameraTests(unittest.TestCase):
    def test_device_caps_override_general_caps_and_fd_is_closed(self):
        def ioctl(_fd, request, buffer, mutate):
            self.assertEqual(request, vc.VIDIOC_QUERYCAP)
            buffer[:] = vc.CAPABILITY.pack(b'v4l2 loopback', b'Test camera', b'', 1,
                vc.V4L2_CAP_DEVICE_CAPS | vc.V4L2_CAP_VIDEO_OUTPUT, 1, 0, 0, 0)
        with patch('virtual_camera.os.open', return_value=42), patch('virtual_camera.fcntl.ioctl', side_effect=ioctl), patch('virtual_camera.os.close') as close:
            self.assertFalse(vc.query_device('/dev/video42')['output'])
            close.assert_called_once_with(42)
        with patch('virtual_camera.os.open', return_value=43), patch('virtual_camera.fcntl.ioctl', side_effect=OSError('busy')), patch('virtual_camera.os.close') as close:
            with self.assertRaises(OSError):
                vc.query_device('/dev/video43')
            close.assert_called_once_with(43)

    def test_only_writable_loopback_outputs_are_offered(self):
        devices = {
            'video0': dict(driver='uvcvideo', output=True, name='Physical camera'),
            'video2': dict(driver='v4l2 loopback', output=False, name='In-use camera'),
            'video9': OSError('permission denied'),
            'video10': dict(driver='v4l2 loopback', output=True, name='OBS Virtual Camera'),
            'video11': dict(driver='v4l2loopback', output=True, name='LumenCamera Virtual Camera'),
        }
        def query(path):
            value = devices[path.name]
            if isinstance(value, Exception):
                raise value
            return dict(value, path=str(path))
        with tempfile.TemporaryDirectory() as temp:
            for name in [*devices, 'video-not-a-device']:
                (Path(temp) / name).touch()
            with patch('virtual_camera.query_device', side_effect=query):
                found = vc.virtual_devices(Path(temp))
            self.assertEqual([Path(x['path']).name for x in found], ['video11', 'video10'])

    def test_loaded_module_is_reused_without_privileged_commands(self):
        expected = [dict(path='/dev/video10', name='OBS Virtual Camera')]
        with patch('virtual_camera.Path.exists', return_value=True), patch('virtual_camera.virtual_devices', return_value=expected), patch('virtual_camera.subprocess.Popen') as spawn:
            self.assertEqual(vc.discover_virtual_devices(), expected)
            spawn.assert_not_called()

    def test_missing_dependency_has_useful_error_and_installs_nothing(self):
        with patch('virtual_camera.Path.exists', return_value=False), patch('virtual_camera.shutil.which', return_value=None), patch('virtual_camera.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'v4l2loopback'):
                vc.discover_virtual_devices()
            spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
