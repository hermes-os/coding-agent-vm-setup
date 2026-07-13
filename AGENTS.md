READ ~/.agents/AGENTS.md BEFORE ANYTHING (skip if missing).

# Coding Agent VM Setup

This repository installs a portable, model-neutral engineering system and
restores Codex and Claude Code authentication on fresh or cloud machines.

## Architecture

- `agent-system/`: canonical policy, shared skills, hooks, helpers, installer,
  and validation tests.
- `bootstrap.sh`: best-effort self-update, system installation, and independent
  credential restoration.
- `claude-code/`: Claude Code credential and remote-control helpers.
- `codex/`: Codex configuration and credential helpers.
- `lib/`: shared shell utilities.

Keep secrets out of the repository. Host files are adapters; workflow policy
belongs in `agent-system/AGENTS.md` or the owning skill.

## Verification

Run `./agent-system/validate.sh`. For installed-state proof, run
`agent-system-doctor --repo "$PWD"` after `./agent-system/install.sh`.

## Delivery

`main` is the portable VM baseline. Keep commits narrowly scoped and preserve
bootstrap compatibility with macOS and Linux.
