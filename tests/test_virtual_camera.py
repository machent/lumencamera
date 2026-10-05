import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
            'video11': dict(driver='v4l2loopback', output=True, name='LumenCamera'),
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
        expected = [dict(path='/dev/video10', name='LumenCamera')]
        with patch('virtual_camera.Path.exists', return_value=True), patch('virtual_camera.virtual_devices', return_value=expected), patch('virtual_camera.subprocess.Popen') as spawn:
            self.assertEqual(vc.discover_virtual_devices(), expected)
            spawn.assert_not_called()

    def test_missing_dependency_has_useful_error_and_installs_nothing(self):
        with patch('virtual_camera.Path.exists', return_value=False), patch('virtual_camera.shutil.which', return_value=None), patch('virtual_camera.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'v4l2loopback'):
                vc.discover_virtual_devices()
            spawn.assert_not_called()

    def test_existing_obs_gets_a_separate_named_device(self):
        obs = dict(path='/dev/video0', name='OBS Virtual Camera')
        lumen = dict(path='/dev/video1', name='LumenCamera')
        process = Mock(returncode=0)
        process.communicate.return_value = ('/dev/video1\n', '')
        with patch('virtual_camera.Path.exists', return_value=True), \
             patch('virtual_camera.virtual_devices', side_effect=[[obs], [obs, lumen]]), \
             patch('virtual_camera._named_device_exists', return_value=False), \
             patch('virtual_camera.shutil.which', side_effect=lambda command, **kw: '/usr/bin/' + command), \
             patch('virtual_camera.subprocess.run', return_value=Mock(stdout='', stderr='\t/usr/bin/v4l2loopback-ctl add {<flags>} [<outputdevice>]\n')), \
             patch('virtual_camera.subprocess.Popen', return_value=process) as spawn:
            self.assertEqual(vc.discover_virtual_devices(), [lumen])
            self.assertEqual(spawn.call_args.args[0],
                ['/usr/bin/pkexec', '/usr/bin/v4l2loopback-ctl', 'add', '-n', 'LumenCamera', '-x', '1'])

    def test_busy_named_device_does_not_create_duplicates_or_use_obs(self):
        with patch('virtual_camera.Path.exists', return_value=True), \
             patch('virtual_camera.virtual_devices', return_value=[dict(path='/dev/video0', name='OBS Virtual Camera')]), \
             patch('virtual_camera._named_device_exists', return_value=True), \
             patch('virtual_camera.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'busy or not writable'):
                vc.discover_virtual_devices()
            spawn.assert_not_called()

    def test_legacy_control_utility_gives_safe_upgrade_guidance(self):
        with patch('virtual_camera.Path.exists', return_value=True), \
             patch('virtual_camera.virtual_devices', return_value=[]), \
             patch('virtual_camera._named_device_exists', return_value=False), \
             patch('virtual_camera.shutil.which', return_value='/usr/bin/v4l2loopback-ctl'), \
             patch('virtual_camera.subprocess.run', return_value=Mock(stdout='Commands: set-fps', stderr='')), \
             patch('virtual_camera.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, '0.13 or newer'):
                vc.discover_virtual_devices()
            spawn.assert_not_called()

    def test_missing_control_utility_does_not_fall_back_to_obs(self):
        with patch('virtual_camera.Path.exists', return_value=True), \
             patch('virtual_camera.virtual_devices', return_value=[dict(path='/dev/video0', name='OBS Virtual Camera')]), \
             patch('virtual_camera._named_device_exists', return_value=False), \
             patch('virtual_camera.shutil.which', return_value=None), \
             patch('virtual_camera.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'v4l2loopback-utils'):
                vc.discover_virtual_devices()
            spawn.assert_not_called()

    def test_fresh_module_uses_exact_label_and_exclusive_caps(self):
        lumen = dict(path='/dev/video2', name='LumenCamera')
        with patch('virtual_camera.Path.exists', return_value=False), \
             patch('virtual_camera.virtual_devices', side_effect=[[], [lumen]]), \
             patch('virtual_camera.shutil.which', side_effect=lambda command, **kw: '/usr/sbin/' + command), \
             patch('virtual_camera.subprocess.run', return_value=Mock(returncode=0)), \
             patch('virtual_camera._authorize') as authorize:
            self.assertEqual(vc.discover_virtual_devices(), [lumen])
            authorize.assert_called_once_with(['/usr/sbin/modprobe', 'v4l2loopback',
                'exclusive_caps=1', 'card_label=LumenCamera'], None)

    def test_udev_delay_is_retried(self):
        expected = [dict(path='/dev/video2', name='LumenCamera')]
        with patch('virtual_camera._named_outputs', side_effect=[[], expected]), \
             patch('virtual_camera.time.sleep') as sleep:
            self.assertEqual(vc._wait_named_outputs(), expected)
            sleep.assert_called_once_with(0.05)

    def test_denied_authorization_reports_failure(self):
        process = Mock(returncode=126)
        process.communicate.return_value = ('', 'Not authorized')
        with patch('virtual_camera.shutil.which', return_value='/usr/bin/pkexec'), \
             patch('virtual_camera.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(RuntimeError, 'Not authorized'):
                vc._authorize(['v4l2loopback-ctl', 'add'])

    def test_cancelled_start_does_not_spawn(self):
        cancel = Mock()
        cancel.is_set.return_value = True
        with patch('virtual_camera.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                vc.discover_virtual_devices(cancel)
            spawn.assert_not_called()

    def test_cancel_during_authorization_reaps_process(self):
        cancel = Mock()
        cancel.is_set.side_effect = [False, True]
        process = Mock()
        with patch('virtual_camera.shutil.which', return_value='/usr/bin/pkexec'), \
             patch('virtual_camera.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                vc._authorize(['v4l2loopback-ctl', 'add'], cancel)
            process.terminate.assert_called_once()
            process.communicate.assert_called_once_with(timeout=2)

    def test_authorization_timeout_reaps_process(self):
        process = Mock()
        process.communicate.side_effect = [vc.subprocess.TimeoutExpired('pkexec', 0.2), ('', '')]
        with patch('virtual_camera.shutil.which', return_value='/usr/bin/pkexec'), \
             patch('virtual_camera.subprocess.Popen', return_value=process), \
             patch('virtual_camera.time.monotonic', side_effect=[0, 121]):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                vc._authorize(['v4l2loopback-ctl', 'add'])
            process.kill.assert_called_once()
            self.assertEqual(process.communicate.call_count, 2)


if __name__ == '__main__':
    unittest.main()
