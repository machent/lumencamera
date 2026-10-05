# Lumen Camera

**Version 1.2** names the virtual camera **LumenCamera**, including when an OBS
loopback device already exists. It includes virtual camera output, Matroska recording with optional
microphone audio, Camera Defaults, native X11/Wayland support, and the bundled
HIJACK easter egg. Download the `.deb` or `.rpm` from
[the v1.2 release](https://github.com/machent/lumencamera/releases/tag/v1.2).

A modern webcam app for Fedora and Ubuntu with camera selection, photo capture, video recording, adjustable camera controls, and customizable filenames and save folders.

**HIJACK easter egg (included in v1.2):**
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
resizes to a compact 4:3 window, and plays the bundled video with its audio.
**HIJACK starts at playback position 0:09.50**, while the video window is still
open. **At 0:10.90, playback stops and the window closes.** These times refer to
the video's media position; loading and the resize do not count.
The close button and Alt+F4 are disabled during playback. **Right Ctrl + Escape**
closes the video and cancels a pending launch before 0:09.50. After that point,
HIJACK is already running in a separate process, and cancelling the video or
closing Lumen Camera does not stop it. Escape alone and Left Ctrl + Escape do
not cancel playback. Playback failures before 0:09.50 prevent the launch.
HIJACK contains flashing visuals and may contain
loud audio. The game payloads live in `easter-eggs/HIJACK-FEDORA.run` and
`easter-eggs/HIJACK-UBUNTU.run`; builds without those optional files still work
as a webcam app. See [game file locations](easter-eggs/README.md).

The signed APT/DNF repositories include the complete **v1.2 x86-64 bundle**,
including both HIJACK games and the video. Existing installations can upgrade
through their package manager; setup and upgrade commands are on the
[installation website](https://machent.github.io/lumencamera/).

## Features

- Choose a webcam and its advertised resolution, frame rate and capture format.
- Take PNG or JPEG photos at the capture resolution.
- Record VP8 Matroska (`.mkv`) video. Clicking **Record video** opens a dialog with **Record with microphone**; enable it to choose an audio input before starting. The app remembers your last choice.
- Start/stop a virtual camera next to Record video to share the live preview with Discord or another camera app, while continuing to adjust camera controls or record.
- Adjust supported camera controls in the main sidebar, including focus, autofocus, sharpness, exposure, brightness and white balance.
- Restore the selected webcam's adjustable controls with **Camera Defaults**, after confirmation. Driver defaults are used; unavailable or read-only controls are skipped. Save settings and captures stay unchanged.
- Configure the save folder, filename pattern, photo format and preview/photo mirroring.
- Preserve existing captures with numbered filename suffixes.
- Open the output folder and see recording time in the main window.

Camera controls depend on the device. Unsupported controls are omitted; unavailable or read-only controls are disabled. Manual focus and exposure may require switching their automatic modes off.

## Virtual camera

This feature requires **v4l2loopback**, the kernel-module dependency used by
[OBS's Linux virtual camera](https://github.com/obsproject/obs-studio/blob/master/plugins/linux-v4l2/v4l2-output.c).
OBS itself is not required. The `.run` installer uses an existing v4l2loopback
module built for the running kernel. For source and `.run` installations, install
`v4l2loopback-dkms` and `v4l2loopback-utils` on Ubuntu, or
`akmod-v4l2loopback` and `v4l2loopback` from
[RPM Fusion Free](https://rpmfusion.org/Configuration) on Fedora. PolicyKit's
`pkexec` command is needed to load the installed module or create a named device
from the app.

The v1.2 native packages declare `v4l2loopback-dkms`, `v4l2loopback-utils` and `pkexec`
as Debian/Ubuntu dependencies, and `akmod-v4l2loopback`, `v4l2loopback` and `polkit` as Fedora
dependencies. APT/DNF installs these dependencies when installing v1.2 from the repositories or package files;
Fedora needs RPM Fusion Free enabled. Installing a kernel
module package does not replace the requirement for a module built and loadable
for the running kernel. The published v1.0 packages do not contain this feature.

1. Start the webcam preview, then click **Start virtual camera**.
2. The app reuses an idle device named exactly **LumenCamera**. If needed,
   administrator authorization loads the module or creates a separate device
   with `exclusive_caps=1` and that name. Existing OBS devices are left intact;
   busy or physical camera devices are never used.
3. Select **LumenCamera** in Discord or your other app after starting the output.
   Reopen its camera list or reload the page if necessary. Sites that filter
   virtual cameras may still omit it.
4. Click **Stop virtual camera** to stop sharing. Closing Lumen Camera also stops
   the output; it does not unload your kernel module.

On older modules/utilities without dynamic device support (such as Ubuntu 24.04's
0.12.x packages), start LumenCamera before OBS loads the module, after a reboot.
Adding a separate device while OBS already owns the loaded module requires
v4l2loopback and its utility version 0.13 or newer. The app reports this limitation
and never unloads the module automatically.

The output follows preview mirroring and the selected webcam's hardware settings.
It contains video only. Microphone choices in Record video apply to saved MKV
files; select a microphone separately in Discord.

The output is YUY2 at 30 fps, using the preview resolution when sharing starts
(odd widths are rounded up by one pixel). Changing cameras or capture modes keeps
that output format stable and scales/letterboxes new frames. Stop/start sharing
to adopt another output resolution. Short capture restarts send black frames so
the output stays connected. Recording may run at the same time.

For browser/WebRTC clients, the loopback module should be configured with
`exclusive_caps=1`; see the [v4l2loopback documentation](https://github.com/v4l2loopback/v4l2loopback).
If no writable device is found, stop another producer such as OBS, check access
to the video device, and try again. The app does not unload an existing module or
interrupt another producer. Device permissions and kernel-module setup remain
your system's configuration.

The implementation follows OBS's module-loading/device-selection approach with
independently written Python code and GStreamer's
[v4l2sink](https://gstreamer.freedesktop.org/documentation/video4linux2/v4l2sink.html)
in memory-mapped (`mmap`) mode. GStreamer's read/write output path does not
implement frame writing and must not be used for this sink. Conversion buffers
are allocated separately from the device's mmap pool, so conversion and frame
rate adjustment cannot consume the limited buffers supplied by the loopback.
Tests exercise the production sink configuration, allocation-query isolation,
real frame conversion and GTK behavior with an appsink substitute. The corrected
output has also been confirmed working on the maintainer's Fedora setup with an
existing OBS loopback device that provides two buffers.

Virtual-camera startup, device selection, output state and failures are logged
to the terminal. To capture detailed GStreamer output, close the app and run:

```bash
env GST_DEBUG_NO_COLOR=1 GST_DEBUG='2,v4l2*:5,appsrc:4' \
  "$HOME/.local/bin/lumen-camera" 2>&1 | tee "$HOME/lumen-virtual-camera.log"
```

## Install from the package repository

Follow the distribution setup steps on the [installation website](https://machent.github.io/lumencamera/), then install LumenCamera:

Fedora: `sudo dnf install lumencamera`

Ubuntu: `sudo apt install lumencamera`

Open **Lumen Camera** from the application menu or run `lumencamera`.
Future versions arrive through your usual system updates.

## Install version 1.2 from a package file

The complete v1.2 packages target **x86-64 (amd64)** because the bundled HIJACK
games contain x86-64 executables.

Download the package for your distribution from [GitHub Releases](https://github.com/machent/lumencamera/releases/tag/v1.2).

Ubuntu / Debian, from the download folder:

```bash
sudo apt install ./lumencamera_1.2-1_amd64.deb
```

Fedora, from the download folder:

```bash
sudo dnf install ./lumencamera-1.2-1*.x86_64.rpm
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

To choose custom installer and source-archive filenames:

```bash
python3 build_run.py --output-prefix Lumen-Camera-test
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
xvfb-run -a /usr/bin/python3 tests/smoke_virtual_camera.py
```

The smoke test uses a synthetic camera to exercise preview, PNG/JPEG photos, filename collision handling, camera-control widgets, the recording dialog, microphone selection, Matroska encoding/decoding with and without audio, and closing during recording. It requires the application dependencies plus Xvfb.

The initial app was tested with a synthetic camera on Ubuntu 24.04. Physical cameras, actual microphones and Fedora hardware still need device testing. Version 1.0 includes the titlebar correction from the earlier 1.0.1 development build.

If a camera is disconnected, busy or denied, reconnect it, close other camera applications, and use Refresh cameras. Try Automatic or another advertised mode if the selected format is unavailable.

## License

[GNU General Public License v3](LICENSE).
