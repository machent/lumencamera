# SPDX-License-Identifier: GPL-3.0-only
"""Platform gating and detached launch for the optional HIJACK game."""
import os
import random
import re
import shlex
import subprocess
from pathlib import Path

GAME_FILES = {
    'fedora': 'HIJACK-FEDORA.run',
    'ubuntu': 'HIJACK-UBUNTU.run',
}


def system_family(os_release=None):
    """Use ID and ID_LIKE ancestry; plain Debian is not an Ubuntu derivative."""
    try:
        content = Path('/etc/os-release').read_text() if os_release is None else os_release
        values = {}
        for line in content.splitlines():
            key, separator, value = line.partition('=')
            if separator and key in ('ID', 'ID_LIKE'):
                values[key] = ' '.join(shlex.split(value)).lower()
        identity = values.get('ID', '')
        if identity in GAME_FILES:
            return identity
        ancestry = values.get('ID_LIKE', '').split()
        return next((family for family in GAME_FILES if family in ancestry), None)
    except (OSError, ValueError):
        return None


def eligible_family(env=None, os_release=None):
    env = os.environ if env is None else env
    desktop = re.split(r'[:;]', env.get('XDG_CURRENT_DESKTOP', '').lower())
    if 'kde' not in desktop and env.get('KDE_FULL_SESSION', '').lower() != 'true':
        return None
    family = system_family(os_release)
    if family is None:
        return None
    version = env.get('KDE_SESSION_VERSION', '')
    if not version:
        try:
            result = subprocess.run(['plasmashell', '--version'], capture_output=True,
                                    text=True, timeout=1, env=dict(env))
            match = re.search(r'plasmashell\s+(\d+)\.', result.stdout)
            version = match.group(1) if result.returncode == 0 and match else ''
        except (OSError, subprocess.TimeoutExpired):
            return None
    return family if version == '6' else None


def settings_encounter(env=None, os_release=None, draw=None):
    """One independent 20% roll for each eligible Settings opening."""
    family = eligible_family(env, os_release)
    if family and (draw or random.random)() < 0.2:
        return family
    return None


def launch_hijack(family, root=None):
    # Revalidate immediately before launch, including when invoked outside UI.
    if family not in GAME_FILES or eligible_family() != family:
        raise RuntimeError('HIJACK is available on Fedora/Ubuntu systems using KDE 6.')
    root = Path(root) if root else Path(__file__).resolve().parent
    game = root / 'easter-eggs' / GAME_FILES[family]
    if not game.is_file():
        raise FileNotFoundError(f'Optional game file is missing: {game.name}')
    if not os.access(game, os.X_OK):
        # Allows files copied into a source checkout without chmod. Installed
        # packages already set executable permissions while building/installing.
        game.chmod(game.stat().st_mode | 0o100)
    logdir = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'lumen-camera'
    logdir.mkdir(parents=True, exist_ok=True)
    with (logdir / 'hijack.log').open('ab') as log:
        process = subprocess.Popen([str(game.resolve())], cwd=str(game.parent.resolve()),
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   close_fds=True, start_new_session=True)
    return process
