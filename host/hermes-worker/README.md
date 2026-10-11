# Hermes worker adapter

This directory contains the opt-in host-owned Hermes bridge and its single
immutable worker template. The bridge is not installed, scheduled, or wired
into the existing Codex/Claude adapters by default.

See [behavior-contract.md](behavior-contract.md) for the exact stdin/JSONL
interface, state rules, upstream CLI assumptions, disposable smoke procedure,
and the future root-owned runner/broker seam.

The per-access templates [config.read.yaml](config.read.yaml) and [config.write.yaml](config.write.yaml) are copied read-only into a fresh
per-work-order `HERMES_HOME`; it is never edited in place or cloned from an
existing assistant profile. The bridge adds Hermes' `.no-bundled-skills`
marker and its own exact-session binding state to that home; both are
per-work-order state, not shared profile content. Worker-state provider plugin
directories are rejected: executable provider code comes only from the staged
deployment, never from the worker-writable runtime home.

On resume, a run whose `config.yaml` matches any root-owned, read-only
`config*.yaml` in this directory is upgraded to the current per-access template;
anything else is rejected as `unsafe_runtime_home`. The superseded files
(`config.yaml`, `config.read.v1.yaml`, `config.*.v2-20260930.yaml`) exist only for
that purpose: [config.yaml](config.yaml) is the original single template, so
keep it (and the other versioned files) installed for as long as runs started on
them may be resumed.

Provider and model are selected per work order. Provider admission is a
reviewed snapshot of the pinned release's direct HTTP/API/OAuth/SDK provider
names and aliases; external-process transports and names absent from that
snapshot are rejected before Hermes starts. Model names are not allowlisted or
pinned to roles.

The child environment is an explicit allowlist. It carries the broker's
runtime/toolchain values and the pinned Hermes provider/tool credentials by
documented variable name, but no ambient Hermes model, profile, prompt,
catalog, plugin, or turn-limit variables. `HERMES_HOME`,
`HERMES_SUPERVISED_CHILD`, `PWD`, and `TERMINAL_CWD` are bridge-owned; the
last two directory values are pinned to the broker-assigned working directory.
The root-owned runner/broker must launch the bridge with `UMask=0077` (or an
equivalent private process umask): the bridge rejects native state databases
and ownership sidecars that are group/world accessible. The bridge ignores
ambient Hermes executable and `PATH` selection, verifies the exact root-owned
staged launcher, interpreter, virtual environment, and source/import trees,
requires their symlinks to stay inside those trees, then runs that interpreter
in isolated mode.
