#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Select native and architecture-independent Debian package stanzas."""
import sys


def select_packages(text, architecture):
    allowed = {architecture, 'all'}
    selected = []
    for stanza in text.strip().split('\n\n'):
        fields = dict(line.split(': ', 1) for line in stanza.splitlines()
                      if ': ' in line and not line.startswith((' ', '\t')))
        if fields.get('Architecture') in allowed:
            selected.append(stanza)
    return '\n\n'.join(selected) + ('\n\n' if selected else '')


if __name__ == '__main__':
    sys.stdout.write(select_packages(sys.stdin.read(), sys.argv[1]))
