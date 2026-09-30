#!/usr/bin/env bash
set -euo pipefail
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/lumen-camera"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
NO_LAUNCH=0
DEMO=0
TERMINAL=0
for arg in "$@"; do
    case "$arg" in
        --no-launch) NO_LAUNCH=1 ;;
        --demo) DEMO=1 ;;
        --terminal) TERMINAL=1 ;;
        --uninstall)
            rm -f "$BIN_DIR/lumen-camera" "$DESKTOP_DIR/io.github.machent.LumenCamera.desktop" "$ICON_DIR/io.github.machent.LumenCamera.svg"
            rm -rf -- "$APP_DIR"
            printf 'Lumen Camera removed. Settings and captured files were kept.\n'
            exit 0 ;;
        --install) ;;
        *) printf 'Unknown installer option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

notify() {
    if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v zenity >/dev/null; then
        zenity --info --title='Lumen Camera' --text="$1" 2>/dev/null || true
    elif [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v kdialog >/dev/null; then
        kdialog --title 'Lumen Camera' --msgbox "$1" 2>/dev/null || true
    else
        printf '%s\n' "$1"
    fi
}

need_deps=0
/usr/bin/python3 - <<'PY' >/dev/null 2>&1 || need_deps=1
import gi
import cairo
gi.require_version('Gtk','3.0')
gi.require_version('Gst','1.0')
gi.require_version('GstVideo','1.0')
from gi.repository import Gtk,Gst,GstVideo
Gst.init(None)
for element in ['v4l2src','videoconvert','appsink','jpegdec','vp8enc','webmmux','pulsesrc','vorbisenc']:
    assert Gst.ElementFactory.find(element), element
PY
command -v v4l2-ctl >/dev/null || need_deps=1
if [[ "$need_deps" == 1 ]]; then
    if command -v dnf >/dev/null; then
        deps=(dnf install -y python3 python3-gobject python3-cairo gtk3 gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good v4l-utils)
    elif command -v apt-get >/dev/null; then
        deps=(apt-get install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good v4l-utils)
    else
        notify 'Install Python 3, PyGObject, GTK 3, GStreamer base/good plugins and v4l-utils, then run the installer again.'
        exit 1
    fi
    approved=0
    if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v zenity >/dev/null; then
        if zenity --question --title='Lumen Camera' --text='Lumen Camera needs system camera and GTK dependencies. Install them now? An administrator password may be requested.' 2>/dev/null; then approved=1; fi
    elif [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v kdialog >/dev/null; then
        if kdialog --title 'Lumen Camera' --yesno 'Install the system camera and GTK dependencies? An administrator password may be requested.' 2>/dev/null; then approved=1; fi
    elif [[ -t 0 ]]; then
        read -r -p 'Install required system dependencies? [y/N] ' reply
        [[ "$reply" =~ ^[yY]([eE][sS])?$ ]] && approved=1
    else
        # Preserve this extracted payload until the terminal child completes.
        for terminal in konsole gnome-terminal kgx x-terminal-emulator xterm; do
            if command -v "$terminal" >/dev/null; then
                case "$terminal" in
                    konsole) "$terminal" --nofork -e bash "$SOURCE/install.sh" "$@" --terminal ;;
                    gnome-terminal) "$terminal" --wait -- bash "$SOURCE/install.sh" "$@" --terminal ;;
                    kgx) "$terminal" --wait -- bash "$SOURCE/install.sh" "$@" --terminal ;;
                    *) "$terminal" -e bash "$SOURCE/install.sh" "$@" --terminal ;;
                esac
                exit $?
            fi
        done
        notify 'Please run this .run file in a terminal to install the required dependencies.'
        exit 1
    fi
    [[ "$approved" == 1 ]] || exit 0
    if [[ "$(id -u)" == 0 ]]; then
        "${deps[@]}"
    elif [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v pkexec >/dev/null; then
        pkexec "${deps[@]}"
    elif [[ -t 0 ]]; then
        sudo "${deps[@]}"
    else
        notify 'Run this installer in a terminal so sudo can request your password.'
        exit 1
    fi
fi
mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"
# Source and package paths are separate, ready for future system packages.
for file in app.py core.py style.css icon.svg README.md LICENSE launcher.sh; do
    install -m 644 "$SOURCE/$file" "$APP_DIR/$file"
done
chmod 755 "$APP_DIR/launcher.sh"
/usr/bin/python3 - "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" <<'PY'
import os, shlex, sys
from pathlib import Path
app, binary, desktop = map(Path, sys.argv[1:])
launcher = binary / 'lumen-camera'
launcher.write_text('#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(app / 'app.py')) + ' "$@"\n')
launcher.chmod(0o755)
def desktop_quote(value):
    # Desktop Exec escaping is different from shell escaping.
    value = value.replace('\\', '\\\\\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    return '"' + value + '"'
(desktop / 'io.github.machent.LumenCamera.desktop').write_text('[Desktop Entry]\nType=Application\nName=Lumen Camera\nComment=Webcam photos, videos and camera controls\nExec=' + desktop_quote(str(launcher)) + '\nIcon=io.github.machent.LumenCamera\nTerminal=false\nCategories=AudioVideo;Video;Photography;\nStartupNotify=true\nStartupWMClass=Lumen Camera\n')
PY
install -m 644 "$SOURCE/icon.svg" "$ICON_DIR/io.github.machent.LumenCamera.svg"
if command -v update-desktop-database >/dev/null; then update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true; fi
if [[ "$NO_LAUNCH" == 1 ]]; then
    printf 'Installed Lumen Camera to %s\n' "$APP_DIR"
    exit 0
fi
if [[ "$DEMO" == 1 ]]; then
    exec "$BIN_DIR/lumen-camera" --demo
else
    exec "$BIN_DIR/lumen-camera"
fi
