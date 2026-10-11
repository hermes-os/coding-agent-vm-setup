# Changelog

This file records user-visible changes to the coding-agent VM setup.

## Unreleased

### Added

- Add an opt-in Hermes worker bridge with an isolated immutable template and a
  documented exact-session/failure contract; the bridge now guards native
  resume metadata, bounds child pipes, isolates the child environment, and
  ignores sticky Hermes profiles. Provider, model, and effort remain
  job-specific. Existing Codex and Claude invocations remain unchanged.

### Changed

- Advance the exact shared-system pin to include governed-workspace checks and
  the current global delivery and continuity policy.
- Add changelog coverage to the VM validation workflow.

### Fixed

- `validate.sh` and `bootstrap.sh` inject `safe.directory` for the
  root checkout and `agent-system` submodule via exact `GIT_CONFIG_COUNT`
  environment entries, so the gate and bootstrap path work on VMs where both
  directories are owned by another user and global/system Git config is
  disabled.
- Restrict the Hermes worker to the reviewed direct-provider registry of the
  exact root-owned staged runtime. External-process and worker-state provider
  plugins are rejected before execution, ambient binary/Python-path injection
  is ignored, and the staged interpreter runs in isolated mode.

## 2026-07-13

### Added

- Split VM bootstrap, authentication restoration, and invocation adapters from
  the independently versioned portable coding-agent system.
- Pin the shared system as an exact Git submodule and validate it through the
  VM integration gate on macOS and Linux.
