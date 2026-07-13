#!/usr/bin/env bash
# Install the official standalone Codex package required by the durable
# app-server daemon. The upstream installer verifies the release checksum.
set -euo pipefail

current="$HOME/.codex/packages/standalone/current"
if [[ -x "$current/bin/codex" || -x "$current/codex" ]]; then
  echo "Codex standalone install already present."
  exit 0
fi

installer="$(mktemp)"
trap 'rm -f "$installer"' EXIT

if command -v curl >/dev/null 2>&1; then
  curl -fsSL https://chatgpt.com/codex/install.sh -o "$installer"
elif command -v wget >/dev/null 2>&1; then
  wget -q -O "$installer" https://chatgpt.com/codex/install.sh
else
  echo "curl or wget is required to install Codex." >&2
  exit 1
fi

CODEX_NON_INTERACTIVE=1 /bin/sh "$installer"
