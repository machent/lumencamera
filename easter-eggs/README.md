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
**No**, Escape, and closing the warning do not start the game. Only **Yes**
launches the selected game in its own session/process. Closing LumenCamera or
Settings after launching does not stop HIJACK. The game includes flashing
visuals and may contain loud audio.
