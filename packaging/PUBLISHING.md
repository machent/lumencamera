# Packaging and publishing

The initial public version is **1.0**. The package name is **lumencamera**.

## Current status

This repository contains the application source, an RPM specification, a Debian package builder and build validation workflow. The 1.0 release workflow publishes the Debian and binary RPM packages from validated build run `36786873828`, targeting its exact source commit. Hosted package repositories are not configured yet. Do not advertise COPR or APT install commands until those services have been published and tested.

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

## Planned distribution

1. GitHub Releases carries the 1.0 `.deb`, binary `.rpm` and SHA-256 checksums, with automatic source downloads. Other installer formats may be added later.
2. Fedora COPR will build and sign RPMs and provide a DNF repository.
3. A signed APT repository will host the Debian package and its package indices, Release metadata, InRelease signature and public signing key. GitHub Pages can host those static repository files.

APT repository publication needs a maintainer-owned signing key and Pages configuration. The private signing key belongs in a protected GitHub Actions secret, never in the source tree. RPM release downloads also need a package-signing plan; COPR can handle signing for the hosted Fedora repository.

## Versions

Update `VERSION` in `core.py` and `Version:` in `packaging/lumencamera.spec` together. Tag the corresponding release commit as `vVERSION` when publishing. The Debian package version is `VERSION-1`; RPMs use `VERSION-1` plus the build distribution suffix. A packaging-only rebuild should increase the package revision instead of moving an existing tag.
