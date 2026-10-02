# HIJACK easter egg payloads

The standalone game files belong here when building LumenCamera:

```text
easter-eggs/HIJACK-FEDORA.run
easter-eggs/HIJACK-UBUNTU.run
```

Use these exact filenames and mark them executable with `chmod +x`. The supplied
files must match the computer architecture. Supporting files, if needed, also
belong in this directory; the game starts with this directory as its working
directory. Self-contained executables are recommended, since LumenCamera does
not install HIJACK's Python or Qt dependencies at launch.

The installer and native package builders include this directory automatically.
The games are optional: the webcam app works without them. If a mystery button
is clicked while its game file is missing, the camera app reports that in its
status bar. Test installers may omit the game binaries; installing one over an
existing `.run` installation preserves its game files.

On an installed `.run` version, the equivalent location is
`${XDG_DATA_HOME:-~/.local/share}/lumen-camera/easter-eggs/`. The usual path is
`~/.local/share/lumen-camera/easter-eggs/`. Native packages use
`/usr/share/lumencamera/easter-eggs/`.

Each opening of Settings on KDE Plasma 6 on Wayland with a Fedora/Ubuntu-based system has
an independent 20% chance to reveal the animated `?????` button. Other desktop
environments, Plasma versions and distribution families never reveal it. X11
sessions never reveal it either.
The button has a purple highlight and hand cursor on hover. Clicking opens a
confirmation with a glitching information icon and text warning that the game
may reboot the computer. This is an interactive HIJACK game, despite the
fictional "watch this video" wording. Save your work before choosing **Yes**.
**No**, Escape, and closing the warning do not start the game. **Yes** consumes
the button for this process, silently animates its CRT shutdown, and turns the
same window black before smoothly resizing it to the bundled video's 4:3 ratio.
The video is `easter-eggs/tape-zero.webm`, converted from the supplied
"DOORS - Tape Zero - Raw Footage [ROBLOX].mp4" to VP8/Vorbis for the existing
GStreamer dependencies. Keep it alongside the game files when building.

During playback the window has no close button and ignores Alt+F4, Escape, and
Left Ctrl + Escape. **Right Ctrl + Escape** is the cancellation shortcut: it
stops the clip and cancels a pending game launch before playback position
**0:09.50**. At **0:09.50**, the selected game starts in its own session/process;
the video continues until **0:10.90**, when playback stops and the window closes.
The player's media position controls both times, excluding loading and resize.
Cancelling after 0:09.50 does not stop the already-running game. A missing or
unplayable clip prevents a launch that has not happened yet. Fully restart Lumen Camera to allow another encounter. Closing LumenCamera or
Settings after launching does not stop HIJACK. The game includes flashing
visuals and may contain loud audio.
