# Lumen Camera

A modern webcam app for Fedora and Ubuntu with camera selection, photo capture, video recording, adjustable camera controls, and customizable filenames and save folders.

**Version 1.0** includes the corrected, compact titlebar buttons.

The current `main` branch also includes an **unreleased HIJACK easter egg**:
opening Settings on KDE Plasma 6 and a Fedora/Ubuntu-based system has a 20%
chance to reveal an animated `?????` button. Clicking launches the matching
non-rebooting HIJACK game immediately as a separate process; closing the camera
app does not close the game. No confirmation dialog appears. Game files are
optional and are not included in this snapshot. Add your non-rebooting games at
`easter-eggs/HIJACK-FEDORA.run` and `easter-eggs/HIJACK-UBUNTU.run` before building.
See [game file locations](easter-eggs/README.md). The published v1.0 release is
unchanged. HIJACK may contain flashing visuals and loud audio.

## Features

- Choose a webcam and its advertised resolution, frame rate and capture format.
- Take PNG or JPEG photos at the capture resolution.
- Record VP8 WebM video, with optional audio from the system default microphone.
- Adjust supported camera controls in the main sidebar, including focus, autofocus, sharpness, exposure, brightness and white balance.
- Configure the save folder, filename pattern, photo format and preview/photo mirroring.
- Preserve existing captures with numbered filename suffixes.
- Open the output folder and see recording time in the main window.

Camera controls depend on the device. Unsupported controls are omitted; unavailable or read-only controls are disabled. Manual focus and exposure may require switching their automatic modes off.

## Install from the package repository

Follow the distribution setup steps on the [installation website](https://machent.github.io/lumencamera/), then install LumenCamera:

Fedora: `sudo dnf install lumencamera`

Ubuntu: `sudo apt install lumencamera`

Open **Lumen Camera** from the application menu or run `lumencamera`.
Future versions arrive through your usual system updates.

## Install version 1.0 from a package file

Download the package for your distribution from [GitHub Releases](https://github.com/machent/lumencamera/releases/tag/v1.0).

Ubuntu / Debian, from the download folder:

```bash
sudo apt install ./lumencamera_1.0-1_all.deb
```

Fedora, from the download folder:

```bash
sudo dnf install ./lumencamera-1.0-1*.noarch.rpm
```

Open Lumen Camera from the application menu or run `lumencamera`. The release includes SHA-256 checksums. Signed APT and DNF repositories are also available as described above.

## Run from source

Install the dependencies for your distribution, then run:

```bash
/usr/bin/python3 app.py
```

Fedora:

```bash
sudo dnf install python3 python3-gobject python3-cairo gtk3 gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good v4l-utils
```

Ubuntu:

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good v4l-utils
```

Use the system Python interpreter, which provides the distribution's GI bindings. The app supports X11 and Wayland sessions with direct access to V4L2 camera devices.

## Build the user installer

```bash
python3 build_run.py
```

The `.run` installs for the current user under `~/.local/share/lumen-camera` and uses `~/.local/bin/lumen-camera`. Run it without sudo.

## Settings and captures

The default output folder is `~/Pictures/Lumen Camera`. Settings are stored in `$XDG_CONFIG_HOME/lumen-camera/settings.json`, normally `~/.config/lumen-camera/settings.json`.

The default filename is `Capture_%Y-%m-%d_%H-%M-%S`. Date placeholders include `%Y` (year), `%m` (month), `%d` (day), `%H` (hour), `%M` (minute) and `%S` (second). Fixed filenames also work; existing files receive a numbered suffix.

Mirroring affects the preview and saved photos. Videos retain the camera's original orientation.

## Development and validation

```bash
/usr/bin/python3 -m unittest discover -s tests -v
xvfb-run -a /usr/bin/python3 tests/smoke.py
```

The smoke test uses a synthetic camera to exercise preview, PNG/JPEG photos, filename collision handling, camera-control widgets, WebM encoding/decoding, synthetic audio encoding and closing during recording. It requires the application dependencies plus Xvfb.

The initial app was tested with a synthetic camera on Ubuntu 24.04. Physical cameras, actual microphones and Fedora hardware still need device testing. Version 1.0 includes the titlebar correction from the earlier 1.0.1 development build.

If a camera is disconnected, busy or denied, reconnect it, close other camera applications, and use Refresh cameras. Try Automatic or another advertised mode if the selected format is unavailable.

## License

[GNU General Public License v3](LICENSE).
