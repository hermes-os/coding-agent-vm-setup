#!/usr/bin/env bash
# Restore Claude Code OAuth credentials from an environment secret so any fresh
# VM session can authenticate Claude Code (including Remote Control).
#
# Provide the secret CLAUDE_CODE_CREDENTIALS_B64 as the base64 encoding of a
# valid ~/.claude/.credentials.json. The FULL credentials JSON (with a
# claudeAiOauth.refreshToken) is required for Remote Control and token refresh.
# CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY alone are inference-only and
# cannot start Remote Control — do not rely on them here.
#
# Optional:
#   CLAUDE_PROJECT_DIR  Project directory to pre-trust (default: current dir).
#                       Pre-accepting workspace trust lets `claude
#                       remote-control` start without an interactive prompt.
set -euo pipefail

if [[ -z "${CLAUDE_CODE_CREDENTIALS_B64:-}" ]]; then
  echo "CLAUDE_CODE_CREDENTIALS_B64 not set; nothing to restore." >&2
  exit 0
fi

mkdir -p "${HOME}/.claude"
CRED="${HOME}/.claude/.credentials.json"
TMP="${CRED}.tmp.$$"

printf '%s' "$CLAUDE_CODE_CREDENTIALS_B64" | base64 -d > "$TMP"

# Validate the payload before overwriting any existing credentials.
python3 - "$TMP" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
if "claudeAiOauth" not in data or not data["claudeAiOauth"].get("refreshToken"):
    raise SystemExit("invalid Claude credentials payload: missing claudeAiOauth.refreshToken")
PY

chmod 600 "$TMP"
mv "$TMP" "$CRED"

# Pre-accept workspace trust for the project dir so remote-control starts
# non-interactively. Defaults to the current directory when unset.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CLAUDE_JSON="${HOME}/.claude.json"
if [[ -f "$CLAUDE_JSON" ]]; then
  PROJECT_DIR="$PROJECT_DIR" python3 - <<'PY'
import json, os
path = os.path.expanduser("~/.claude.json")
proj = os.environ["PROJECT_DIR"]
with open(path) as f:
    data = json.load(f)
data.setdefault("projects", {}).setdefault(proj, {})["hasTrustDialogAccepted"] = True
with open(path, "w") as f:
    json.dump(data, f, indent=2)
PY
fi

echo "Claude Code credentials restored to ${CRED} (trust set for ${PROJECT_DIR})."
