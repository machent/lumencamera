Name:           lumencamera
Version:        1.0
Release:        1%{?dist}
Summary:        Webcam photos, videos and hardware camera controls
License:        GPL-3.0-only
URL:            https://github.com/machent/lumencamera
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/lumencamera-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3 >= 3.9
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk3
Requires:       gstreamer1
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good
Requires:       v4l-utils
Requires:       akmod-v4l2loopback
Requires:       polkit

%description
Lumen Camera is a GTK desktop webcam application with camera and capture mode
selection, PNG/JPEG photos, Matroska recording with selectable microphone audio,
virtual camera output, hardware camera controls and customizable output filenames
and folders.

%prep
%autosetup -n lumencamera-%{version}

%build
# Pure Python application; no compilation step is needed.

%install
install -d %{buildroot}%{_datadir}/lumencamera
for file in app.py core.py easter_egg.py video_easter.py virtual_camera.py style.css; do
    install -m 0644 "$file" %{buildroot}%{_datadir}/lumencamera/
done
cp -R easter-eggs %{buildroot}%{_datadir}/lumencamera/
find %{buildroot}%{_datadir}/lumencamera/easter-eggs -type d -exec chmod 0755 {} +
find %{buildroot}%{_datadir}/lumencamera/easter-eggs -type f -exec chmod 0644 {} +
find %{buildroot}%{_datadir}/lumencamera/easter-eggs -type f -name '*.run' -exec chmod 0755 {} +
install -D -m 0755 packaging/lumencamera %{buildroot}%{_bindir}/lumencamera
install -D -m 0644 packaging/io.github.machent.LumenCamera.desktop %{buildroot}%{_datadir}/applications/io.github.machent.LumenCamera.desktop
install -D -m 0644 icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.machent.LumenCamera.svg

%files
%license LICENSE
%doc README.md
%{_bindir}/lumencamera
%{_datadir}/lumencamera/
%{_datadir}/applications/io.github.machent.LumenCamera.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.machent.LumenCamera.svg

%changelog
* Thu Oct 01 2026 Lumen Camera contributors - 1.0-1
- Initial RPM release, including compact titlebar window controls.
