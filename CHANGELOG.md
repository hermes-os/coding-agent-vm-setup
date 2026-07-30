# Changelog

This file records user-visible changes to the coding-agent VM setup.

## Unreleased

### Changed

- Advance the exact shared-system pin to include governed-workspace checks and
  the current global delivery and continuity policy.
- Add changelog coverage to the VM validation workflow.

## 2026-07-13

### Added

- Split VM bootstrap, authentication restoration, and invocation adapters from
  the independently versioned portable coding-agent system.
- Pin the shared system as an exact Git submodule and validate it through the
  VM integration gate on macOS and Linux.
