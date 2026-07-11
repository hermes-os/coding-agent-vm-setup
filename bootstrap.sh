#!/usr/bin/env bash
# Cursor Cloud / headless VM bootstrap: self-update this repo, restore agent
# credentials from Cursor secrets, optionally configure a scoped push remote.
#
# Intended usage (in Cursor environment update script, after first clone):
#   REPO=~/coding-agent-vm-setup
#   if [ -d "$REPO/.git" ]; then git -C "$REPO" pull --ff-only
#   else git clone https://github.com/hermes-os/coding-agent-vm-setup "$REPO"; fi
#   CLAUDE_PROJECT_DIR=/workspace "$REPO/bootstrap.sh"
#
# Secrets (Cursor My Secrets — never commit):
#   CLAUDE_CODE_CREDENTIALS_B64  Claude Code OAuth (minimal claudeAiOauth JSON)
#   CODEX_AUTH_JSON_B64          Codex auth.json (gzip+base64 for ChatGPT OAuth)
#   SHARED_REPO_TOKEN            Fine-grained PAT: Contents R/W on this repo only
#
# Optional env:
#   CLAUDE_PROJECT_DIR           Workspace to trust (default: /workspace if exists, else $PWD)
#   CODING_AGENT_VM_SETUP        Override repo root (default: this script's directory)
#   SHARED_REPO_SLUG             GitHub slug for push remote (default: hermes-os/coding-agent-vm-setup)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODING_AGENT_VM_SETUP="${CODING_AGENT_VM_SETUP:-$ROOT}"
SHARED_REPO_SLUG="${SHARED_REPO_SLUG:-hermes-os/coding-agent-vm-setup}"

if [[ -d "${CODING_AGENT_VM_SETUP}/.git" ]]; then
  git -C "${CODING_AGENT_VM_SETUP}" pull --ff-only
fi

if [[ -n "${SHARED_REPO_TOKEN:-}" ]]; then
  # Token-in-URL remote bypasses Cursor's global https://github.com/ insteadOf
  # rewrite (cursor[bot]). Scope the PAT to this repo only — do not set GH_TOKEN globally.
  git -C "${CODING_AGENT_VM_SETUP}" remote set-url origin \
    "https://x-access-token:${SHARED_REPO_TOKEN}@github.com/${SHARED_REPO_SLUG}.git"
  echo "Configured origin for ${SHARED_REPO_SLUG} (scoped PAT in local .git/config)."
else
  echo "SHARED_REPO_TOKEN not set; skipping vm-setup push remote." >&2
fi

if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
  if [[ -d /workspace ]]; then
    CLAUDE_PROJECT_DIR=/workspace
  else
    CLAUDE_PROJECT_DIR="$PWD"
  fi
fi
export CLAUDE_PROJECT_DIR

"${CODING_AGENT_VM_SETUP}/claude-code/restore-claude-credentials.sh"
"${CODING_AGENT_VM_SETUP}/codex/ensure-codex-config.sh"
"${CODING_AGENT_VM_SETUP}/codex/restore-codex-credentials.sh"

echo "Bootstrap complete (${CODING_AGENT_VM_SETUP})."
