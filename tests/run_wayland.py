"""Run the GTK smoke test on a real headless Wayland compositor."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='lumen-wayland-') as temp:
    runtime = Path(temp)
    env = dict(os.environ, XDG_RUNTIME_DIR=temp, WAYLAND_DISPLAY='lumen-test-wayland',
               XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='KDE', KDE_SESSION_VERSION='6',
               GDK_BACKEND='x11')
    env.pop('DISPLAY', None)
    # Deliberately supply the wrong inherited GDK_BACKEND: app startup must
    # replace it with the login session's native Wayland backend.
    log = runtime / 'weston.log'
    process = subprocess.Popen(['weston', '--backend=headless-backend.so', '--renderer=pixman',
                                '--socket=lumen-test-wayland', '--idle-time=0', '--no-config',
                                '--width=1280', '--height=900', '--log=' + str(log)],
                               env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while not (runtime / 'lumen-test-wayland').exists():
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Test Wayland compositor failed: ' + (log.read_text() if log.exists() else 'no log'))
            time.sleep(0.05)
        result = subprocess.run([sys.executable, str(ROOT / 'tests/smoke_easter_egg.py'), 'wayland'],
                                cwd=ROOT, env=dict(env, WAYLAND_DEBUG='client'),
                                capture_output=True, text=True, timeout=25)
        assert result.returncode == 0, result.stdout + result.stderr[-5000:]
        assert 'set_app_id("io.github.machent.LumenCamera")' in result.stderr, 'Wayland protocol did not receive the installed desktop entry ID'
        print(result.stdout, end='')
        print('PASS: compositor received LumenCamera app_id for desktop icon lookup')
    finally:
        process.terminate()
        process.wait(timeout=5)
