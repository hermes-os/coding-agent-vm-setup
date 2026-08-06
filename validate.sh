#!/usr/bin/env bash
# Validate the exact shared pin and the independently versioned VM adapter.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# In containerized or multi-user VMs the submodule directory may not be owned
# by the invoking user and the global git config may be read-only. Inject the
# safe.directory entry via the environment so it propagates to all child
# processes, including the shared-system submodule validation.
if [[ -n "${GIT_CONFIG_COUNT:-}" ]]; then
  idx=$GIT_CONFIG_COUNT
  eval "export GIT_CONFIG_KEY_${idx}=safe.directory"
  eval "export GIT_CONFIG_VALUE_${idx}=\"$ROOT/agent-system\""
  export GIT_CONFIG_COUNT=$((GIT_CONFIG_COUNT + 1))
else
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=safe.directory
  export GIT_CONFIG_VALUE_0="$ROOT/agent-system"
fi

expected="$(git -C "$ROOT" ls-files -s agent-system | awk '$1 == "160000" {print $2}')"
actual="$(git -C "$ROOT/agent-system" rev-parse HEAD)"
if [[ -z "$expected" || "$actual" != "$expected" ]]; then
  echo "agent-system submodule is missing or differs from the recorded pin" >&2
  exit 1
fi
if [[ -n "$(git -C "$ROOT/agent-system" status --porcelain)" ]]; then
  echo "agent-system submodule has local changes" >&2
  exit 1
fi

while IFS= read -r -d '' script; do
  bash -n "$script"
done < <(find "$ROOT" -path "$ROOT/.git" -prune -o -path "$ROOT/agent-system/.git" -prune -o -type f -name '*.sh' -print0)

python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py'
"$ROOT/agent-system/validate.sh"
"$ROOT/agent-system/bin/agent-repo-check" --repo "$ROOT"
git -C "$ROOT" diff --check
git -C "$ROOT" diff --cached --check

echo "VM agent setup validation passed."
