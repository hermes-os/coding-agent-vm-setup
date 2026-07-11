#!/usr/bin/env bash
# Ensure ~/.codex/config.toml forces file-based credential storage so auth can
# be rehydrated from CODEX_AUTH_JSON_B64 on headless VMs (no OS keyring).
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
CONFIG="${CODEX_HOME}/config.toml"
mkdir -p "$CODEX_HOME"

if [[ ! -f "$CONFIG" ]]; then
  printf '%s\n' 'cli_auth_credentials_store = "file"' > "$CONFIG"
  echo "Created ${CONFIG} (file-based auth storage)"
  exit 0
fi

if grep -q '^cli_auth_credentials_store' "$CONFIG" 2>/dev/null; then
  # Normalize to file if set to keyring/auto on a headless VM snapshot.
  if grep -qE 'cli_auth_credentials_store\s*=\s*"(keyring|auto)"' "$CONFIG"; then
    sed -i 's/^cli_auth_credentials_store.*/cli_auth_credentials_store = "file"/' "$CONFIG"
    echo "Updated ${CONFIG} to file-based auth storage"
  fi
else
  printf '\n%s\n' 'cli_auth_credentials_store = "file"' >> "$CONFIG"
  echo "Appended file-based auth storage to ${CONFIG}"
fi
