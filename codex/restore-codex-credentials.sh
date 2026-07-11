#!/usr/bin/env bash
# Restore Codex CLI auth from Cursor secret CODEX_AUTH_JSON_B64 (base64 of
# ~/.codex/auth.json, optionally gzip-compressed). Requires file-based storage
# — see ensure-codex-config.sh.
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

python3 - "$TMP" <<'PY'
import base64, gzip, json, os, sys

out_path = sys.argv[1]
b64 = os.environ.get("CODEX_AUTH_JSON_B64", "")
if not b64:
    raise SystemExit("CODEX_AUTH_JSON_B64 empty")
raw = base64.b64decode(b64)
if raw[:2] == b"\x1f\x8b":
    raw = gzip.decompress(raw)
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    raise SystemExit(f"invalid Codex auth payload after decode: {e}") from e
if not isinstance(data, dict) or len(data) == 0:
    raise SystemExit("invalid Codex auth.json payload: expected non-empty JSON object")
with open(out_path, "w") as f:
    json.dump(data, f, separators=(",", ":"))
PY

chmod 600 "$TMP"
mv "$TMP" "$AUTH_FILE"

echo "Codex auth restored to ${AUTH_FILE}"
