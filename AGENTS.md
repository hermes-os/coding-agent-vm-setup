READ ~/.agents/AGENTS.md BEFORE ANYTHING (skip if missing).

# Coding Agent VM Setup

Sets up the shared coding-agent system on fresh or cloud machines and restores Codex and Claude Code sign-ins.

- `agent-system/` is a pinned Git submodule of `coding-agent-system`. Shared policy changes happen there; here you only move the pin, on purpose.
- `host/` holds VM launch and shell adapters. They differ from a workstation's, so they live here.
- `bootstrap.sh` must keep working on both macOS and Linux.
- Secrets never enter the repository; the scripts restore them from outside it.

## Gate
`./validate.sh`
