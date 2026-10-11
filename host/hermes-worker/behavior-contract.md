# Hermes worker bridge contract

`host/bin/agent-hermes-worker` is an opt-in, one-task adapter. It reads the
task only from stdin and emits one JSON object per line on stdout.

Required selection is explicit: `--provider`, `--model`, `--effort`,
`--access read|write`, `--runtime-home`, `--broker-session-id`, and exactly one
of `--fresh-session` or `--resume-session NATIVE_SESSION_ID`. Provider values
are case-insensitively matched against the reviewed direct-transport names and
aliases in the bridge. External-process profiles and unreviewed names are
rejected with `provider_transport_denied` before the native runtime or any
provider helper starts. This admission policy does not constrain model names:
provider, model, and effort remain per-work-order choices.

The bridge refuses to start unless the caller is inside the existing managed
worker boundary (`AGENT_WORKER_MANAGED=1`) and the inherited
`AGENT_ACCESS_MODE` equals the requested access. This check is an integration
precondition, not filesystem isolation. The root-owned broker must continue to
provide the systemd and repository read/write boundary.

The fresh path creates a new mode-0700 runtime home and copies the checked-in per-access
`config.read.yaml` or `config.write.yaml` as a mode-0400 `config.yaml`. It also writes the immutable
`.no-bundled-skills` marker, so Hermes' startup seeding installs only its
canonical `hermes-agent` procedure instead of the full bundled catalog. Resume
requires an existing mode-0700 home owned by the caller with the byte-identical
template and marker. State is never copied from another profile. The template
has no provider fallback, disables persistent memory and user profiles, leaves
external skill directories empty, and exposes only `file`, `search`, `terminal`,
and `skills` toolsets. The `skills` toolset is the only procedural-skill loading
surface; delegation, messaging, scheduling, account, and code-execution
toolsets are not enabled. The template also keeps `plugins.enabled` empty. The
bridge rejects a `plugins` path in the worker-writable runtime home, closing the
upstream model-provider override path on fresh and resumed work orders.

The child command is the documented Hermes CLI shape:

```text
/opt/agent-worker-hermes/.../source/.venv/bin/python -I \
  /opt/agent-worker-hermes/.../source/.venv/bin/hermes chat \
  --oneshot --query-file - --quiet \
  --provider PROVIDER --model MODEL --reasoning EFFORT \
  --toolsets file,search,terminal,skills [--resume NATIVE_SESSION_ID --no-restore-cwd] [--yolo]
```

`--yolo` is present only for `--access write`; the external broker remains the
actual write policy. The task is never placed in argv. The bridge removes
ambient Hermes model/profile/config, prompt, turn-limit, bundled-skill/plugin,
optional-catalog, project-plugin, TUI, and delegated-child overrides by
constructing a child environment from an explicit allowlist. It retains the
broker's OS/toolchain values, `TERMINAL_*` backend settings other than the
bridge-pinned `TERMINAL_CWD`, and the staged runtime's documented provider and
applicable tool-auth names. Unknown `HERMES_*` and generic token variables are
not inherited. `HERMES_HOME` and `HERMES_SUPERVISED_CHILD=1` are always set by
the bridge, while `PWD` and `TERMINAL_CWD` are set to the assigned repository
directory. Provider credential values are passed by name without being read or
logged by the bridge; the broker still owns credential policy.

The Hermes command is not selected from `AGENT_HERMES_BIN` or inherited
`PATH`. It is pinned to release
`9caa21336d278b614e99a58e302f48894ff0dbd7` under
`/opt/agent-worker-hermes/releases/`, and the bridge verifies the root-owned,
worker-nonwritable launcher, every import-affecting entry in the staged source
and interpreter trees, their contained symlinks, Python linkage, and exact
3.11.16 interpreter before each launch. Python isolated mode (`-I`)
ignores ambient `PYTHONPATH`, user site packages, and other `PYTHON*` import
overrides. The staged source and dependencies are deployment-owned executable
code; `HERMES_HOME`, `state.db`, skills, and bridge bindings remain
worker-owned state and are never accepted as provider code. Upgrades must stage
a new root-owned release and update the path, reviewed provider admission
snapshot, source-classification regression, and upstream assumptions together.

Events are:

- `started`: selected provider, model, effort, access, broker UUID, and fresh
  or resume mode;
- `session`: the native Hermes `session_id` parsed from the child, never the
  broker UUID;
- `final`: the non-empty child result and the last native session ID;
- `error`: a stable error code and redacted message.

The broker UUID is correlation/ownership metadata. A native Hermes session ID
is returned by Hermes and is the only value accepted by `--resume-session`.
Resume always passes that exact value to `--resume`; `latest`, `current`, and
`last` are rejected. Resume also disables Hermes' recorded-directory restore so
the broker-selected repository working directory remains authoritative. If
Hermes rotates its native ID, the bridge reports the new native ID and retains
`resumed_from_native_session_id` rather than relabeling either identity.

Before a resume child is started, the bridge opens the native Hermes
`HERMES_HOME/state.db` read-only and checks the exact session row, transcript,
effective CWD, and persisted `model_config.yolo_mode`. It follows the staged
Hermes 0.21.0 compression-descendant rules (including branch/delegate/reset/
tool exclusions) and rejects missing, empty, cyclic, unrelated, or
working-directory-mismatched state. It does not trust `--no-restore-cwd` to
override Hermes' native restore helper. A read resume is rejected if native
metadata would restore YOLO, and a resume must match the bridge-owned
`bridge-state.json` binding for the same broker UUID, access mode, and assigned
CWD. Hermes is still invoked with the requested native ID, never the resolved
descendant ID and never `latest`; an emitted ID is accepted only when it is in
that native lineage. A successful fresh or resumed run records native IDs in
that sidecar for the next exact continuation. The sidecar is correlation and
ownership state, not a replacement for the root broker's filesystem boundary.

The bridge uses nonblocking pipe reads with an 8 MiB result cap and a 256 KiB
diagnostic-line cap. Input writes are also nonblocking. On cancellation,
oversize output (stdout or stderr), direct-child exit, or failure it signals
the private process group, drains for at most two seconds, force-kills the
group if necessary, and closes the pipes; there is no global task deadline or
default turn cap. Empty output, missing native identity, oversized output,
provider failure, malformed setup, and interruption are errors and return
nonzero. Child stderr is not forwarded, so provider diagnostics and task text
do not become bridge logs.

The root-owned runner/broker must provide a private process umask equivalent to
systemd `UMask=0077`. Native Hermes creates `state.db` during a run, and the
bridge intentionally rejects a database with group/world permission bits;
disposable unit-test databases set their mode explicitly so test results do
not depend on the shell's umask.

## Coordinator smoke procedure

After Hermes is installed and authenticated by the coordinator, use a
disposable mode-0700 directory and a real managed broker/runner invocation.
The command below is a shape check only; it is intentionally not run by this
repository worker and it must not be used to bypass the broker boundary:

```sh
smoke_root="$(mktemp -d)"
chmod 700 "$smoke_root"
runtime_home="$smoke_root/hermes-home"
broker_session_id="$(uuidgen)"
AGENT_WORKER_MANAGED=1 \
  AGENT_ACCESS_MODE=read \
  host/bin/agent-hermes-worker \
    --provider PROVIDER --model MODEL --effort medium --access read \
    --runtime-home "$runtime_home" --broker-session-id "$broker_session_id" \
    --fresh-session <<'TASK'
Return a short readiness result and do not modify the repository.
TASK
```

For acceptance, the coordinator must run the same command through the
root-owned runner/broker so the repository mount and ownership checks are
active, then verify a second invocation uses the exact emitted native session
ID with `--resume-session`. Clean up the disposable directory afterward. A
successful fixture test is not a live model or broker acceptance result.

## Upstream assumptions

The adapter is pinned in code to the staged Hermes Agent v0.21.0 runtime
(Python 3.11.16), release source directory
`/opt/agent-worker-hermes/releases/9caa21336d278b614e99a58e302f48894ff0dbd7/source`,
whose inspected upstream source commit is
`245e48008fa814b3251f50755eb656bd9fb86cb1`. The resume preflight depends on
that release's read-only SQLite `sessions`/`messages` schema and native
compression resolution. Provider admission depends on its source registry,
aliases, authentication type, and client-construction hooks. Recheck those
surfaces, the interpreter/import layout, exact CLI options, schema, and restore
helpers together when upgrading Hermes:

- <https://hermes-agent.nousresearch.com/docs/llms.txt>
- <https://hermes-agent.nousresearch.com/docs/reference/cli-commands>
- <https://hermes-agent.nousresearch.com/docs/user-guide/profiles>
- <https://hermes-agent.nousresearch.com/docs/user-guide/configuration>

The current live root-owned runner and broker do not yet list Hermes as an
agent. Future integration must add only a provider-child seam that launches
this adapter inside the existing unit with the assigned repository as its CWD,
passes the managed-boundary environment and broker UUID, stores the emitted
native ID separately from the broker UUID, and preserves the runtime home plus
`bridge-state.json` for exact resume. The root-owned broker must continue to
enforce OS read-only/write mounts and single ownership; this bridge's profile
state and tool flags are not filesystem security. This repository does not
modify that live code.
