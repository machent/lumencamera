#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build an architecture-independent, checksummed self-extracting .run."""
import hashlib
from core import VERSION
import io
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parent
output = root.parent / f'Lumen-Camera-{VERSION}.run'
buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
    for path in sorted(root.rglob('*')):
        if path.is_file() and not any(part in ('__pycache__', 'dist', '.git') for part in path.relative_to(root).parts) and path.suffix != '.pyc':
            archive.add(path, arcname=str(path.relative_to(root)))
payload = buffer.getvalue()
digest = hashlib.sha256(payload).hexdigest()
header = '''#!/usr/bin/env bash
# Lumen Camera __VERSION__, Fedora / Ubuntu, GPL v3 license
set -euo pipefail
case "${1:-}" in
    --help|-h)
        printf '%s\\n' 'Lumen Camera __VERSION__' 'Usage: bash Lumen-Camera-__VERSION__.run [--no-launch] [--demo]' '       bash Lumen-Camera-__VERSION__.run --extract DIRECTORY' '       bash Lumen-Camera-__VERSION__.run --uninstall'
        exit 0 ;;
esac
PAYLOAD_LINE="$(awk '/^__LUMEN_PAYLOAD__$/ {print NR + 1; exit}' "$0")"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lumen-camera.XXXXXXXX")"
trap 'rm -rf -- "$WORK_DIR"' EXIT
tail -n +"$PAYLOAD_LINE" "$0" > "$WORK_DIR/payload.tar.gz"
EXPECTED_SHA='DIGEST'
ACTUAL_SHA="$(sha256sum "$WORK_DIR/payload.tar.gz")"
if [[ "${ACTUAL_SHA%% *}" != "$EXPECTED_SHA" ]]; then
    printf 'Installer checksum failed. Download the file again.\\n' >&2
    exit 1
fi
mkdir "$WORK_DIR/app"
tar -xzf "$WORK_DIR/payload.tar.gz" -C "$WORK_DIR/app" --no-same-owner
if [[ "${1:-}" == '--extract' ]]; then
    [[ $# == 2 ]] || { printf 'Usage: --extract DIRECTORY\\n' >&2; exit 2; }
    mkdir -p -- "$2"
    cp -R "$WORK_DIR/app/." "$2/"
    printf 'Extracted Lumen Camera source to %s\\n' "$2"
    exit 0
fi
bash "$WORK_DIR/app/install.sh" "$@"
exit $?
__LUMEN_PAYLOAD__
'''.replace('DIGEST', digest).replace('__VERSION__', VERSION)
output.write_bytes(header.encode() + payload)
output.chmod(0o755)
source = root.parent / f'Lumen-Camera-{VERSION}-source.tar.gz'
with tarfile.open(source, 'w:gz') as archive:
    for path in sorted(root.rglob('*')):
        if path.is_file() and not any(part in ('__pycache__', 'dist', '.git') for part in path.relative_to(root).parts) and path.suffix != '.pyc':
            archive.add(path, arcname='lumen-camera/' + str(path.relative_to(root)))
print(output, output.stat().st_size, 'bytes')
print(source, source.stat().st_size, 'bytes')
