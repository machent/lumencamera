#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build .deb or .rpm directly from the source tree, without the .run installer."""
import argparse
import ast
import hashlib
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version():
    tree = ast.parse((ROOT / 'core.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets):
            value = ast.literal_eval(node.value)
            if not re.fullmatch(r'\d+(?:\.\d+)*', value):
                raise ValueError('VERSION must be a numeric release version')
            return value
    raise ValueError('VERSION was not found')


def put(source, dest, mode=0o644):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    dest.chmod(mode)


def source_archive(out):
    ver = version()
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'lumencamera-{ver}.tar.gz'
    with tarfile.open(target, 'w:gz') as archive:
        for file in sorted(ROOT.rglob('*')):
            relative = file.relative_to(ROOT)
            if not file.is_file() or any(part in ('.git', '__pycache__', 'dist') for part in relative.parts) or file.suffix == '.pyc':
                continue
            archive.add(file, arcname=f'lumencamera-{ver}/{relative}')
    return target


def deb(out):
    ver = version()
    with tempfile.TemporaryDirectory(prefix='lumencamera-deb-') as tmp:
        stage = Path(tmp) / 'stage'
        for name in ('app.py', 'core.py', 'easter_egg.py', 'video_easter.py', 'virtual_camera.py', 'style.css'):
            put(ROOT / name, stage / 'usr/share/lumencamera' / name)
        for file in (ROOT / 'easter-eggs').rglob('*'):
            if file.is_file():
                put(file, stage / 'usr/share/lumencamera/easter-eggs' / file.relative_to(ROOT / 'easter-eggs'),
                    0o755 if file.suffix == '.run' else 0o644)
        put(ROOT / 'packaging/lumencamera', stage / 'usr/bin/lumencamera', 0o755)
        put(ROOT / 'packaging/io.github.machent.LumenCamera.desktop', stage / 'usr/share/applications/io.github.machent.LumenCamera.desktop')
        put(ROOT / 'icon.svg', stage / 'usr/share/icons/hicolor/scalable/apps/io.github.machent.LumenCamera.svg')
        put(ROOT / 'README.md', stage / 'usr/share/doc/lumencamera/README.md')
        copyright = stage / 'usr/share/doc/lumencamera/copyright'
        copyright.write_text((ROOT / 'LICENSE').read_text())
        for directory in stage.rglob('*'):
            if directory.is_dir():
                directory.chmod(0o755)
        meta = stage / 'DEBIAN'
        meta.mkdir(mode=0o755)
        size = (sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()) + 1023) // 1024
        # Use the repository owner GitHub no-reply address unless overridden.
        maintainer = os.environ.get('DEB_MAINTAINER', 'machent <110301374+machent@users.noreply.github.com>')
        if '\n' in maintainer or '\r' in maintainer:
            raise ValueError('Invalid maintainer field')
        (meta / 'control').write_text(f'''Package: lumencamera
Version: {ver}-1
Section: video
Priority: optional
Architecture: amd64
Maintainer: {maintainer}
Installed-Size: {size}
Depends: python3 (>= 3.9), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-gstreamer-1.0, gir1.2-gst-plugins-base-1.0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, v4l-utils, v4l2loopback-dkms, v4l2loopback-utils, pkexec
Homepage: https://github.com/machent/lumencamera
Description: Webcam photos, videos and hardware camera controls
 Native GTK webcam application with camera selection, PNG/JPEG photos,
 Matroska recording with selectable microphone audio, virtual camera output,
 hardware camera controls
 and customizable output filenames and folders.
''')
        (meta / 'control').chmod(0o644)
        target = out / f'lumencamera_{ver}-1_amd64.deb'
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(stage), str(target)], check=True)
        return [target]


def rpm(out):
    ver = version()
    spec = (ROOT / 'packaging/lumencamera.spec').read_text()
    if not re.search(r'^Version:\s+' + re.escape(ver) + r'\s*$', spec, re.M):
        raise ValueError('RPM spec and application VERSION differ')
    with tempfile.TemporaryDirectory(prefix='lumencamera-rpm-') as tmp:
        top = Path(tmp)
        for name in ('SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'RPMS', 'SRPMS'):
            (top / name).mkdir()
        archive = source_archive(top / 'SOURCES')
        put(ROOT / 'packaging/lumencamera.spec', top / 'SPECS/lumencamera.spec')
        subprocess.run(['rpmbuild', '-ba', '--define', f'_topdir {top}', str(top / 'SPECS/lumencamera.spec')], check=True)
        results = []
        for directory in ('RPMS', 'SRPMS'):
            for path in sorted((top / directory).rglob('*.rpm')):
                result = out / path.name
                shutil.copyfile(path, result)
                results.append(result)
        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=('deb', 'rpm', 'source'))
    parser.add_argument('--out', default=str(ROOT / 'dist'))
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = [source_archive(out)] if args.kind == 'source' else globals()[args.kind](out)
    for path in results:
        print(path)


if __name__ == '__main__':
    main()
