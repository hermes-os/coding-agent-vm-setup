#!/usr/bin/env bash
# Start headless Codex device OAuth in tmux. User opens the printed URL and
# enters the one-time code, then auth.json is written under ~/.codex/.
#
# Optional:
#   CODEX_AUTH_TMUX_SESSION  tmux session name (default: codex-auth)
set -euo pipefail

SESSION="${CODEX_AUTH_TMUX_SESSION:-codex-auth}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/ensure-codex-config.sh"

if tmux -f /exec-daemon/tmux.portal.conf has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION' already exists. Attach with:"
  echo "  tmux -f /exec-daemon/tmux.portal.conf attach -t $SESSION"
  exit 0
fi

LOG="/tmp/codex-oauth.log"
rm -f "$LOG"
tmux -f /exec-daemon/tmux.portal.conf new-session -d -s "$SESSION" -c "${CODEX_PROJECT_DIR:-$PWD}" -- bash -l
tmux -f /exec-daemon/tmux.portal.conf send-keys -t "$SESSION:0.0" \
  "script -q -f $LOG -c 'codex login --device-auth'" C-m

echo "Codex device auth starting in tmux '$SESSION'."
echo "Watch: tmux -f /exec-daemon/tmux.portal.conf attach -t $SESSION"
echo "Or:    tail -f $LOG"
echo
echo "After login succeeds, export secret with:"
echo "  ${SCRIPT_DIR}/export-codex-auth-b64.sh"
