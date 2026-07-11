#!/usr/bin/env bash
# Print base64(gzip(auth.json)) for storing as Cursor secret CODEX_AUTH_JSON_B64.
# Gzip keeps ChatGPT OAuth payloads under Cursor My Secrets' ~4096 char limit.
# Run on a VM where `codex login status` succeeds.
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
AUTH="${CODEX_HOME}/auth.json"

if [[ ! -f "$AUTH" ]]; then
  echo "Missing ${AUTH}. Run: codex login --device-auth" >&2
  exit 1
fi

python3 - "$AUTH" <<'PY'
import base64, gzip, json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
# Drop empty API-key placeholder from ChatGPT OAuth exports.
if data.get("auth_mode") == "chatgpt" and not data.get("OPENAI_API_KEY"):
    data = {k: v for k, v in data.items() if k != "OPENAI_API_KEY"}
raw = json.dumps(data, separators=(",", ":")).encode()
compressed = gzip.compress(raw)
b64 = base64.b64encode(compressed).decode()
print(b64)
print(f"# json={len(raw)} gzip={len(compressed)} b64={len(b64)}", file=sys.stderr)
PY

echo "Paste into Cursor secret CODEX_AUTH_JSON_B64." >&2
