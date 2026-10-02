#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Verify an extracted native package against its source without launching it."""
import ast
import hashlib
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
REQUIRED = (
    'app.py', 'core.py', 'easter_egg.py', 'video_easter.py', 'virtual_camera.py',
    'style.css', 'easter-eggs/HIJACK-FEDORA.run',
    'easter-eggs/HIJACK-UBUNTU.run', 'easter-eggs/tape-zero.webm',
)


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            sha.update(block)
    return sha.digest()


def verify(extracted):
    installed = extracted / 'usr/share/lumencamera'
    for name in REQUIRED:
        source = SOURCE / name
        packaged = installed / name
        if not source.is_file() or not packaged.is_file():
            raise RuntimeError(f'Missing bundle file: {name}')
        if digest(source) != digest(packaged):
            raise RuntimeError(f'Bundle content differs from source: {name}')
        if name.endswith('.run') and packaged.stat().st_mode & 0o111 != 0o111:
            raise RuntimeError(f'Bundled game is not executable: {name}')
    launcher = extracted / 'usr/bin/lumencamera'
    if not launcher.is_file() or not launcher.stat().st_mode & 0o111:
        raise RuntimeError('Missing or non-executable application launcher')
    for node in ast.parse((installed / 'core.py').read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'VERSION'
            for target in node.targets
        ):
            if ast.literal_eval(node.value) != '1.1':
                raise RuntimeError('Packaged application version is not 1.1')
            break
    else:
        raise RuntimeError('Packaged application version is missing')
    print('PASS: v1.1 runtime, both executable HIJACK games and video match source')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
