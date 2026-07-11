#!/usr/bin/env bash
# Start headless Codex device OAuth in tmux. User opens the printed URL and
# enters the one-time code, then auth.json is written under ~/.codex/.
#
# Optional:
#   CODEX_AUTH_TMUX_SESSION  tmux session name (default: codex-auth)
#   CODEX_PROJECT_DIR        working directory (default: $PWD)
#   TMUX_CONFIG              tmux config file (auto: Cursor portal conf if present)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/tmux.sh
source "${SCRIPT_DIR}/../lib/tmux.sh"

SESSION="${CODEX_AUTH_TMUX_SESSION:-codex-auth}"
PROJECT_DIR="${CODEX_PROJECT_DIR:-$PWD}"

"${SCRIPT_DIR}/ensure-codex-config.sh"

if vm_tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION' already exists. Attach with:"
  vm_tmux_attach_hint "$SESSION"
  exit 0
fi

LOG="/tmp/codex-oauth.log"
rm -f "$LOG"
vm_tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR" -- bash -l
vm_tmux send-keys -t "$SESSION:0.0" \
  "script -q -f $LOG -c 'codex login --device-auth'" C-m

echo "Codex device auth starting in tmux '$SESSION'."
echo "Watch:"
vm_tmux_attach_hint "$SESSION"
echo "Or:    tail -f $LOG"
echo
echo "After login succeeds, export secret with:"
echo "  ${SCRIPT_DIR}/export-codex-auth-b64.sh"
