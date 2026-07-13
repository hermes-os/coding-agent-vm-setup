#!/usr/bin/env bash
# Cursor Cloud / headless VM bootstrap: self-update this repo, install the
# pinned shared agent system, restore credentials, and optionally configure a
# scoped push remote.
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
  # Self-update is best-effort: a non-fast-forward, an expired PAT, or being
  # offline must never block credential restore below.
  git -C "${CODING_AGENT_VM_SETUP}" pull --ff-only \
    || echo "self-update skipped (non-fast-forward or offline); using current checkout." >&2
fi

# The VM owns the pin; the shared repository owns policy and skills. Always
# materialize exactly the commit recorded by this checkout.
agent_system_ready=1
if ! git -C "${CODING_AGENT_VM_SETUP}" submodule sync --recursive; then
  echo "submodule sync failed; shared system installation will be skipped." >&2
  agent_system_ready=0
fi
if ! git -C "${CODING_AGENT_VM_SETUP}" submodule update --init --recursive; then
  echo "shared agent-system checkout failed; installation will be skipped." >&2
  agent_system_ready=0
fi
recorded_system_sha="$(
  git -C "${CODING_AGENT_VM_SETUP}" ls-files -s agent-system 2>/dev/null \
    | awk '$1 == "160000" {print $2}' \
    || true
)"
actual_system_sha="$(
  git -C "${CODING_AGENT_VM_SETUP}/agent-system" rev-parse HEAD 2>/dev/null || true
)"
system_status="$(
  git -C "${CODING_AGENT_VM_SETUP}/agent-system" status --porcelain 2>/dev/null \
    || printf 'unavailable\n'
)"
if [[ -z "$recorded_system_sha" || "$actual_system_sha" != "$recorded_system_sha" || -n "$system_status" ]]; then
  echo "shared agent-system is not the exact clean VM pin; installation will be skipped." >&2
  agent_system_ready=0
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

if [[ "$agent_system_ready" == "1" && -x "${CODING_AGENT_VM_SETUP}/agent-system/install.sh" ]]; then
  "${CODING_AGENT_VM_SETUP}/agent-system/install.sh" \
    --coordination-repo "${CODING_AGENT_VM_SETUP}" \
    --host-integration "${CODING_AGENT_VM_SETUP}/host" \
    || echo "Agent system install failed (continuing with credential restore)." >&2
else
  echo "Shared agent system is unavailable (continuing with credential restore)." >&2
fi

# Each restore is independent — one agent's missing/malformed secret must not
# block the other from authenticating.
"${CODING_AGENT_VM_SETUP}/claude-code/restore-claude-credentials.sh" \
  || echo "Claude credential restore failed (continuing)." >&2
"${CODING_AGENT_VM_SETUP}/codex/install-standalone.sh" \
  || echo "Codex standalone install failed (continuing)." >&2
"${CODING_AGENT_VM_SETUP}/codex/ensure-codex-config.sh" \
  || echo "Codex config setup failed (continuing)." >&2
"${CODING_AGENT_VM_SETUP}/codex/restore-codex-credentials.sh" \
  || echo "Codex credential restore failed (continuing)." >&2
"${CODING_AGENT_VM_SETUP}/codex/start-remote-control.sh" \
  || echo "Codex Remote Control startup failed (continuing)." >&2

echo "Bootstrap complete (${CODING_AGENT_VM_SETUP})."
