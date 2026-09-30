#!/usr/bin/env bash
set -e
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/python3 "$APP_DIR/app.py" "$@"
