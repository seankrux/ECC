#!/usr/bin/env bash
# Compute the sha256 digest for a skill file referenced in
# /.well-known/agent-skills/index.json. Paste the hex digest into the
# matching "sha256" field.
#
# Usage: ./gen-sha256.sh path/to/SKILL.md
set -euo pipefail

file="${1:?usage: gen-sha256.sh <file>}"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$file" | awk '{print $1}'
else
  shasum -a 256 "$file" | awk '{print $1}'
fi
