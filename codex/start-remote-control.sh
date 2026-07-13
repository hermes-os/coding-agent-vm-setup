#!/usr/bin/env bash
# Start Codex's durable app-server with Remote Control enabled.
set -euo pipefail

for candidate in \
  "$HOME/.codex/packages/standalone/current/bin/codex" \
  "$HOME/.codex/packages/standalone/current/codex" \
  "$HOME/.local/bin/codex"; do
  if [[ -x "$candidate" ]]; then
    exec "$candidate" remote-control start
  fi
done

echo "Codex standalone install not found; run codex/install-standalone.sh first." >&2
exit 1
