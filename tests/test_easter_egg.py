"""Eligibility and process-lifetime checks; these never run HIJACK."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from easter_egg import eligible_family, settings_encounter, launch_hijack

KDE6 = {'XDG_CURRENT_DESKTOP': 'KDE', 'KDE_SESSION_VERSION': '6', 'XDG_SESSION_TYPE': 'wayland'}


class EasterEggTests(unittest.TestCase):
    def test_distribution_and_desktop_matrix(self):
        for release, family in [('ID=fedora', 'fedora'), ('ID=ubuntu', 'ubuntu'),
                                ('ID=bazzite\nID_LIKE="fedora"', 'fedora'),
                                ('ID=linuxmint\nID_LIKE="ubuntu debian"', 'ubuntu'),
                                ('ID=debian', None), ('ID=arch', None), ('ID="broken', None)]:
            with self.subTest(release=release):
                self.assertEqual(eligible_family(KDE6, release), family)
                for env in ({'XDG_CURRENT_DESKTOP': 'GNOME', 'KDE_SESSION_VERSION': '6'},
                            {'XDG_CURRENT_DESKTOP': 'KDE', 'KDE_SESSION_VERSION': '5'}, {}):
                    self.assertIsNone(eligible_family(env, release))

    def test_missing_version_uses_running_desktop_version_command(self):
        with patch('easter_egg.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'plasmashell 6.7.0\n', '')):
            self.assertEqual(eligible_family({'XDG_CURRENT_DESKTOP': 'KDE', 'XDG_SESSION_TYPE': 'wayland'}, 'ID=fedora'), 'fedora')
        with patch('easter_egg.subprocess.run', side_effect=FileNotFoundError):
            self.assertIsNone(eligible_family({'XDG_CURRENT_DESKTOP': 'KDE', 'XDG_SESSION_TYPE': 'wayland'}, 'ID=fedora'))

    def test_x11_never_rolls_even_with_kde6_and_a_wayland_variable(self):
        env = dict(KDE6, XDG_SESSION_TYPE='x11', WAYLAND_DISPLAY='wayland-0', DISPLAY=':0')
        with patch('easter_egg.random.random') as draw:
            self.assertIsNone(settings_encounter(env, 'ID=fedora'))
            draw.assert_not_called()
        self.assertIsNone(eligible_family({'XDG_CURRENT_DESKTOP': 'KDE', 'KDE_SESSION_VERSION': '6'}, 'ID=fedora'))

    def test_each_opening_rolls_and_exact_boundary(self):
        values = iter([0.199999, 0.2, 0.0, 0.99])
        draw = lambda: next(values)
        self.assertEqual([settings_encounter(KDE6, 'ID=ubuntu', draw) for _ in range(4)],
                         ['ubuntu', None, 'ubuntu', None])
        with patch('easter_egg.random.random') as random_draw:
            self.assertIsNone(settings_encounter({}, 'ID=fedora'))
            random_draw.assert_not_called()

    def test_selected_file_and_detached_launch_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            games = root / 'easter-eggs'
            games.mkdir()
            for family in ('fedora', 'ubuntu'):
                path = games / ('HIJACK-' + family.upper() + '.run')
                path.write_text('#!/bin/sh\nexit 0\n')
                with patch('easter_egg.eligible_family', return_value=family), \
                     patch.dict(os.environ, {'XDG_CACHE_HOME': str(root / 'cache')}), \
                     patch('easter_egg.subprocess.Popen') as popen:
                    launch_hijack(family, root)
                    args, options = popen.call_args
                    self.assertEqual(args[0], [str(path)])
                    self.assertTrue(options['start_new_session'])
                    self.assertTrue(options['close_fds'])
                    self.assertEqual(options['cwd'], str(games))
                    self.assertTrue(os.access(path, os.X_OK))
            with patch('easter_egg.eligible_family', return_value=None):
                with self.assertRaises(RuntimeError):
                    launch_hijack('fedora', root)

    def test_child_survives_its_launching_process(self):
        with tempfile.TemporaryDirectory(prefix='lumen detached test ') as tmp:
            root = Path(tmp)
            (root / 'easter-eggs').mkdir()
            result = root / 'child-finished.json'
            game = root / 'easter-eggs/HIJACK-FEDORA.run'
            game.write_text(f'#!{sys.executable}\nimport time,os,json\nfrom pathlib import Path\ntime.sleep(0.7)\nPath({str(result)!r}).write_text(json.dumps({{"pid":os.getpid(),"sid":os.getsid(0)}}))\n')
            code = f'from unittest.mock import patch\nfrom easter_egg import launch_hijack\nwith patch("easter_egg.eligible_family", return_value="fedora"):\n p=launch_hijack("fedora", {str(root)!r})\n print(p.pid,flush=True)\n'
            env = dict(os.environ, XDG_CACHE_HOME=str(root / 'cache'))
            parent = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1],
                                    env=env, capture_output=True, text=True, timeout=5, check=True)
            pid = int(parent.stdout.strip())
            deadline = time.monotonic() + 5
            while not result.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(result.exists(), 'Detached child did not finish after launcher exited')
            data = json.loads(result.read_text())
            self.assertEqual(data, {'pid': pid, 'sid': pid})


if __name__ == '__main__':
    unittest.main()
