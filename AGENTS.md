READ ~/.agents/AGENTS.md BEFORE ANYTHING (skip if missing).

# Coding Agent VM Setup

This repository adapts the shared engineering system to fresh or cloud
machines and restores Codex and Claude Code authentication.

## Architecture

- `agent-system/`: exact Git submodule pin of `hermes-os/coding-agent-system`.
  Do not edit shared policy here; update and verify the pin deliberately.
- `host/`: VM-owned invocation and shell adapters. These remain independently
  versioned because VM launch behavior differs from a local workstation.
- `bootstrap.sh`: best-effort self-update, system installation, and independent
  credential restoration.
- `claude-code/`: Claude Code credential and remote-control helpers.
- `codex/`: Codex configuration and credential helpers.
- `lib/`: shared shell utilities.

Keep secrets out of the repository. Shared workflow policy belongs in the
submodule or an owning product skill; VM authentication and launch behavior
belong here.

## Verification

Run `./validate.sh`. It verifies the exact shared pin, shared system gate, VM
adapter behavior, bootstrap wiring, shell syntax, and repository hygiene.

## Delivery

`main` is the VM baseline. Keep commits narrowly scoped, preserve bootstrap
compatibility with macOS and Linux, and never float the shared submodule.
