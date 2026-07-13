#!/usr/bin/env bash
# Launch Claude Code Remote Control in a persistent tmux session so a phone or
# laptop can drive this VM. Remote Control dials OUTBOUND over HTTPS 443, so the
# VM needs no public inbound route, port forwarding, or SSH relay.
#
# Prerequisite: a real OAuth login must already be in place — run
# ./restore-claude-credentials.sh (or `claude auth login --claudeai`) first.
# Do NOT export ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN: they are
# inference-only and cannot establish a Remote Control session.
#
# Optional:
#   RC_TMUX_SESSION  tmux session name (default: claude-rc)
#   RC_NAME          Display name shown in claude.ai / the app (default: Cloud Dev VM)
#   CLAUDE_PROJECT_DIR  Directory the session runs in (default: current dir)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/tmux.sh
source "${SCRIPT_DIR}/../lib/tmux.sh"

SESSION="${RC_TMUX_SESSION:-claude-rc}"
RC_NAME="${RC_NAME:-Cloud Dev VM}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

if vm_tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION' already exists. Attach with:"
  vm_tmux_attach_hint "$SESSION"
  exit 0
fi

vm_tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
vm_tmux send-keys -t "$SESSION" \
  "claude remote-control --name \"$RC_NAME\" --permission-mode bypassPermissions" C-m

echo "Remote Control launching in tmux session '$SESSION'"
echo "  project: $PROJECT_DIR"
echo "  name:    $RC_NAME"
echo
echo "Watch it:"
vm_tmux_attach_hint "$SESSION"
echo "  (detach with Ctrl-b then d; do NOT kill the pane)"
echo "Connect at: https://claude.ai/code   or the Claude mobile app > Code tab"
echo
echo "Keep the tmux pane alive. Detaching is fine; more than ~10 min offline ends the session."
