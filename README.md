# Lumen Camera

A modern webcam app for Fedora and Ubuntu with camera selection, photo capture, video recording, adjustable camera controls, and customizable filenames and save folders.

**Version 1.0** includes the corrected, compact titlebar buttons.

The current `main` branch includes an **unreleased HIJACK easter egg**:
opening Settings on KDE Plasma 6 on Wayland and a Fedora/Ubuntu-based system has
an independent 20% chance to reveal a `?????` button with animated tearing,
static and a glitching aura. Hovering turns its highlight purple and shows a
hand cursor. Clicking opens an animated information window with this warning:

> Are you sure you want to watch this video?  
> The video may reboot your system... >:)

Despite the fictional video wording, this launches the **interactive HIJACK
game, which can reboot your computer**. Save your work before choosing **Yes**.
**No**, Escape, or closing the warning cancels without launching anything.
Choosing **Yes** silently collapses the mystery button into a CRT scanline and
phosphor dot. The button stays unavailable until Lumen Camera is fully restarted,
even when Settings is reopened. The same warning window turns black, smoothly
resizes to a compact 4:3 window, and plays the bundled roughly 12-second video
with its audio. Its close button and Alt+F4 are disabled during playback.
**Right Ctrl + Escape** cancels the video and prevents HIJACK from starting;
Escape alone and Left Ctrl + Escape do not cancel it. Only normal video
completion closes the window and launches the matching game in a separate
process. Playback failures do not launch it. Closing Lumen Camera afterwards
does not stop the game. HIJACK contains flashing visuals and may contain
loud audio. The game payloads live in `easter-eggs/HIJACK-FEDORA.run` and
`easter-eggs/HIJACK-UBUNTU.run`; builds without those optional files still work
as a webcam app. See [game file locations](easter-eggs/README.md).

**v1.1 is on hold.** The published v1.0 release and package repositories are
unchanged.

## Features

- Choose a webcam and its advertised resolution, frame rate and capture format.
- Take PNG or JPEG photos at the capture resolution.
- Record VP8 Matroska (`.mkv`) video. Clicking **Record video** opens a dialog with **Record with microphone**; enable it to choose an audio input before starting. The app remembers your last choice.
- Adjust supported camera controls in the main sidebar, including focus, autofocus, sharpness, exposure, brightness and white balance.
- Restore the selected webcam's adjustable controls with **Camera Defaults**, after confirmation. Driver defaults are used; unavailable or read-only controls are skipped. Save settings and captures stay unchanged.
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

The app automatically uses native X11 in an X11 login session and native Wayland
in a Wayland login session. The mystery button is never shown on X11; on Wayland
its existing Plasma 6, distribution and 20% chance requirements still apply.
The window identity matches the installed desktop entry for the Lumen Camera icon.

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

The smoke test uses a synthetic camera to exercise preview, PNG/JPEG photos, filename collision handling, camera-control widgets, the recording dialog, microphone selection, Matroska encoding/decoding with and without audio, and closing during recording. It requires the application dependencies plus Xvfb.

The initial app was tested with a synthetic camera on Ubuntu 24.04. Physical cameras, actual microphones and Fedora hardware still need device testing. Version 1.0 includes the titlebar correction from the earlier 1.0.1 development build.

If a camera is disconnected, busy or denied, reconnect it, close other camera applications, and use Refresh cameras. Try Automatic or another advertised mode if the selected format is unavailable.

## License

[GNU General Public License v3](LICENSE).
