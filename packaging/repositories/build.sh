#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail

if [[ $# != 4 || ! $1 =~ ^(apt|rpm)$ ]]; then
  echo 'Usage: build.sh apt|rpm PACKAGE_DIRECTORY SITE_DIRECTORY PRIVATE_KEY_FILE' >&2
  exit 2
fi
kind=$1
packages=$(realpath "$2")
site=$(realpath -m "$3")
key=$(realpath "$4")
mkdir -p "$site"
signing_home=$(mktemp -d)
export GNUPGHOME="$signing_home"
trap 'gpgconf --kill gpg-agent 2>/dev/null || true; rm -rf "$signing_home"' EXIT
gpg --batch --import "$key"
mapfile -t fingerprints < <(gpg --batch --with-colons --list-secret-keys | awk -F: '$1=="sec" {primary=1;next} primary && $1=="fpr" {print $10;primary=0}')
test "${#fingerprints[@]}" -eq 1
fingerprint=${fingerprints[0]}
gpg --batch --armor --export "$fingerprint" > "$site/lumencamera-signing-key.asc"
gpg --batch --export "$fingerprint" > "$site/lumencamera-signing-key.gpg"
printf '%s\n' "$fingerprint" > "$site/signing-key-fingerprint.txt"
base=https://machent.github.io/lumencamera

if [[ $kind == apt ]]; then
  mkdir -p "$site/apt/pool/main/l/lumencamera"
  shopt -s nullglob
  debs=("$packages"/*.deb)
  test "${#debs[@]}" -gt 0
  for deb in "${debs[@]}"; do
    test "$(dpkg-deb -f "$deb" Package)" = lumencamera
    case "$(dpkg-deb -f "$deb" Architecture)" in
      all|amd64|arm64) ;;
      *) echo "Unsupported Debian package architecture: $deb" >&2; exit 1 ;;
    esac
    cp "$deb" "$site/apt/pool/main/l/lumencamera/"
  done
  filter_script="$(dirname "$(realpath "$0")")/filter_packages.py"
  cd "$site/apt"
  # Native bundles include x86-64 games. Each index also retains older all packages.
  for arch in amd64 arm64 all; do
    directory="dists/stable/main/binary-$arch"
    mkdir -p "$directory"
    apt-ftparchive packages pool | python3 "$filter_script" "$arch" > "$directory/Packages"
    gzip -n -9 -c "$directory/Packages" > "$directory/Packages.gz"
    mkdir -p "$directory/by-hash/SHA256" "$directory/by-hash/SHA512"
    for file in Packages Packages.gz; do
      cp "$directory/$file" "$directory/by-hash/SHA256/$(sha256sum "$directory/$file" | cut -d' ' -f1)"
      cp "$directory/$file" "$directory/by-hash/SHA512/$(sha512sum "$directory/$file" | cut -d' ' -f1)"
    done
  done
  apt-ftparchive -o APT::FTPArchive::Release::Origin=LumenCamera \
    -o APT::FTPArchive::Release::Label=LumenCamera \
    -o APT::FTPArchive::Release::Suite=stable \
    -o APT::FTPArchive::Release::Codename=stable \
    -o 'APT::FTPArchive::Release::Architectures=amd64 arm64 all' \
    -o APT::FTPArchive::Release::Components=main \
    -o APT::FTPArchive::Release::Acquire-By-Hash=yes \
    release dists/stable > dists/stable/Release
  gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 --clearsign --output dists/stable/InRelease dists/stable/Release
  gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 --armor --detach-sign --output dists/stable/Release.gpg dists/stable/Release
  gpgv --keyring "$site/lumencamera-signing-key.gpg" dists/stable/InRelease
  cat > "$site/lumencamera.sources" <<EOF
Types: deb
URIs: $base/apt
Suites: stable
Components: main
Architectures: amd64 arm64
Signed-By: /etc/apt/keyrings/lumencamera.asc
EOF
else
  mkdir -p "$site/rpm/packages"
  shopt -s nullglob
  rpms=("$packages"/*.noarch.rpm "$packages"/*.x86_64.rpm)
  test "${#rpms[@]}" -gt 0
  for rpm_file in "${rpms[@]}"; do
    test "$(rpm -qp --qf '%{NAME}' "$rpm_file")" = lumencamera
    case "$(rpm -qp --qf '%{ARCH}' "$rpm_file")" in
      noarch|x86_64) ;;
      *) echo "Unsupported RPM architecture: $rpm_file" >&2; exit 1 ;;
    esac
    cp "$rpm_file" "$site/rpm/packages/"
  done
  rpmsign --define "_gpg_name $fingerprint" --define "_openpgp_sign_id $fingerprint" --define '_openpgp_sign gpg' --addsign "$site/rpm/packages/"*.rpm
  rpm --import "$site/lumencamera-signing-key.asc"
  rpm --checksig "$site/rpm/packages/"*.rpm
  createrepo_c --checksum sha256 "$site/rpm"
  gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 --armor --detach-sign --output "$site/rpm/repodata/repomd.xml.asc" "$site/rpm/repodata/repomd.xml"
  gpgv --keyring "$site/lumencamera-signing-key.gpg" "$site/rpm/repodata/repomd.xml.asc" "$site/rpm/repodata/repomd.xml"
  cat > "$site/lumencamera.repo" <<EOF
[lumencamera]
name=LumenCamera stable
baseurl=$base/rpm
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=$base/lumencamera-signing-key.asc
metadata_expire=1h
EOF
fi
