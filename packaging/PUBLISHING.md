# Packaging and publishing

The initial public version is **1.0**. The package name is **lumencamera**.

## Current status

This repository contains the application source, an RPM specification, a Debian package builder and build validation workflow. The 1.0 release workflow publishes the Debian and binary RPM packages from validated build run `36786873828`, targeting its exact source commit. Signed APT and DNF repositories are live at https://machent.github.io/lumencamera/. Installation from the public repositories passed on Ubuntu 24.04 and Fedora 44. See [repository setup](repositories/README.md) for maintenance.

## Local packages

On Fedora, install the RPM build tool and build:

```bash
sudo dnf install rpm-build python3
python3 packaging/build_packages.py rpm
```

This produces a noarch binary RPM and a source RPM in `dist/`. The RPM specification does not wrap or execute the `.run` installer.

On Ubuntu, install the Debian package tool and build:

```bash
sudo apt install dpkg python3
python3 packaging/build_packages.py deb
```

The Debian package architecture is `all`. A maintainer contact can be set with the `DEB_MAINTAINER` environment variable; the default is the repository owner GitHub no-reply address.

Install a locally built Debian package with:

```bash
sudo apt install ./dist/lumencamera_1.0-1_all.deb
```

## Distribution

1. GitHub Releases carries the 1.0 `.deb`, binary `.rpm` and SHA-256 checksums, with automatic source downloads. Other installer formats may be added later.
2. A signed DNF repository hosts the noarch Fedora package on GitHub Pages.
3. A signed APT repository hosts the Debian package, package indices, Release metadata, InRelease signature and public signing key on GitHub Pages.

APT and DNF repository publication use a dedicated maintainer-owned signing key stored in the `LUMENCAMERA_SIGNING_KEY` Actions secret. Private keys never belong in the source tree. The hosted RPM copies are signed without replacing the original release assets.

## Versions

Update `VERSION` in `core.py` and `Version:` in `packaging/lumencamera.spec` together. Tag the corresponding release commit as `vVERSION` when publishing. The Debian package version is `VERSION-1`; RPMs use `VERSION-1` plus the build distribution suffix. A packaging-only rebuild should increase the package revision instead of moving an existing tag.
