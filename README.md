# Lumen Camera

A modern webcam app for Fedora and Ubuntu with camera selection, photo capture, video recording, adjustable camera controls, and customizable filenames and save folders.

**Version 1.0** includes the corrected, compact titlebar buttons.

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

Add the repository once, then install and update LumenCamera through your package manager.

Fedora:

```bash
curl -fsSL https://machent.github.io/lumencamera/lumencamera.repo -o /tmp/lumencamera.repo
sudo install -m 0644 /tmp/lumencamera.repo /etc/yum.repos.d/lumencamera.repo
sudo dnf install lumencamera
```

Ubuntu (amd64 and arm64):

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://machent.github.io/lumencamera/lumencamera-signing-key.asc -o /tmp/lumencamera.asc
sudo install -m 0644 /tmp/lumencamera.asc /etc/apt/keyrings/lumencamera.asc
curl -fsSL https://machent.github.io/lumencamera/lumencamera.sources -o /tmp/lumencamera.sources
sudo install -m 0644 /tmp/lumencamera.sources /etc/apt/sources.list.d/lumencamera.sources
sudo apt update
sudo apt install lumencamera
```

Open **Lumen Camera** from the application menu or run `lumencamera`.
Future published versions arrive through `sudo dnf upgrade` or `sudo apt upgrade`.

The [repository website](https://machent.github.io/lumencamera/) hosts the setup files and public signing key. APT metadata, RPM packages and DNF metadata are signed. Repository installation was tested on Ubuntu 24.04 and Fedora 44.

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

## Build installers and packages

Build the self-extracting user installer:

```bash
python3 build_run.py
```

Build a Debian package with `dpkg-deb` installed:

```bash
python3 packaging/build_packages.py deb
```

Build an RPM and source RPM with `rpmbuild` installed:

```bash
python3 packaging/build_packages.py rpm
```

The package name and native-package launcher are `lumencamera`. Package output goes to `dist/`. Native packages declare their dependencies and install the application under `/usr/share/lumencamera`, with an application-menu entry and `/usr/bin/lumencamera` launcher.

The `.run` installer instead installs for the current user and uses `~/.local/bin/lumen-camera`. It asks before installing missing dependencies. Run it without sudo.

See [packaging/PUBLISHING.md](packaging/PUBLISHING.md) for publication status and package instructions. GitHub Releases provides the 1.0 Debian and Fedora packages. Signed APT and DNF repositories are hosted on GitHub Pages; maintainer instructions are in [repository setup](packaging/repositories/README.md).

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
