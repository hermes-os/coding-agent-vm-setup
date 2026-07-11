#!/usr/bin/env bash
# Restore Codex CLI auth from Cursor secret CODEX_AUTH_JSON_B64 (base64 of
# ~/.codex/auth.json). Requires file-based storage — see ensure-codex-config.sh.
#
# ChatGPT OAuth via `codex login --device-auth` writes auth.json with refresh
# tokens; Codex refreshes automatically during use.
#
# Optional:
#   CODEX_HOME  Codex config dir (default: ~/.codex)
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"

if [[ -z "${CODEX_AUTH_JSON_B64:-}" ]]; then
  echo "CODEX_AUTH_JSON_B64 not set; nothing to restore." >&2
  exit 0
fi

mkdir -p "$CODEX_HOME"
AUTH_FILE="${CODEX_HOME}/auth.json"
TMP="${AUTH_FILE}.tmp.$$"

printf '%s' "$CODEX_AUTH_JSON_B64" | base64 -d > "$TMP"

python3 - "$TMP" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
# ChatGPT login stores tokens; API-key login uses a different shape — accept both.
if not isinstance(data, dict) or len(data) == 0:
    raise SystemExit("invalid Codex auth.json payload: expected non-empty JSON object")
PY

chmod 600 "$TMP"
mv "$TMP" "$AUTH_FILE"

echo "Codex auth restored to ${AUTH_FILE}"
