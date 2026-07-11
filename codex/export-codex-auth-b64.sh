#!/usr/bin/env bash
# Print base64(auth.json) for storing as Cursor secret CODEX_AUTH_JSON_B64.
# Run on a VM where `codex login status` succeeds.
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
AUTH="${CODEX_HOME}/auth.json"

if [[ ! -f "$AUTH" ]]; then
  echo "Missing ${AUTH}. Run: codex login --device-auth" >&2
  exit 1
fi

python3 - "$AUTH" <<'PY'
import base64, json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
raw = json.dumps(data, separators=(",", ":")).encode()
print(base64.b64encode(raw).decode())
PY

echo "Paste into Cursor secret CODEX_AUTH_JSON_B64 (check 4096 char limit)." >&2
