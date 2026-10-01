#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
umask 077
output=${1:-"$HOME/lumencamera-signing"}
mkdir -p "$output"
output=$(realpath "$output")
if [[ -e $output/private-key.asc ]]; then
  echo "Key already exists: $output/private-key.asc." >&2
  exit 1
fi
signing_home=$(mktemp -d)
export GNUPGHOME="$signing_home"
trap 'gpgconf --kill gpg-agent 2>/dev/null || true; rm -rf "$signing_home"' EXIT
gpg --batch --pinentry-mode loopback --passphrase '' --quick-generate-key \
  'LumenCamera repository <110301374+machent@users.noreply.github.com>' rsa3072 sign 0
fingerprint=$(gpg --batch --with-colons --list-secret-keys | awk -F: '$1=="fpr" {print $10;exit}')
gpg --batch --armor --export-secret-keys "$fingerprint" > "$output/private-key.asc"
gpg --batch --armor --export "$fingerprint" > "$output/public-key.asc"
printf '%s\n' "$fingerprint" > "$output/fingerprint.txt"
printf 'Created signing key. Fingerprint: %s\nPrivate key: %s/private-key.asc\n' "$fingerprint" "$output"
