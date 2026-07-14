# Coding Agent VM Setup

Portable VM and cloud-host wiring for the shared, model-neutral engineering
system. This repository owns VM behavior; the shared policy and skills remain
independently versioned in
[`hermes-os/coding-agent-system`](https://github.com/hermes-os/coding-agent-system).

## Layers

| Layer | Ownership | Location |
|---|---|---|
| Shared policy, skills, hooks, and deterministic helpers | Shared repository, exact Git pin | `agent-system/` |
| VM invocation and shell behavior | This repository | `host/` |
| VM bootstrap and authentication restore | This repository | `bootstrap.sh`, `claude-code/`, `codex/`, `lib/` |

The VM and local workstation adapters intentionally live in different Git
repositories. Updating the shared submodule never silently replaces VM launch
behavior.

## Cursor Cloud

Use this in the environment update/install script:

```bash
npm install # omit outside Node projects
REPO=~/coding-agent-vm-setup
[ -d "$REPO/.git" ] || git clone https://github.com/hermes-os/coding-agent-vm-setup.git "$REPO"
CLAUDE_PROJECT_DIR=/workspace "$REPO/bootstrap.sh"
```

`bootstrap.sh` performs a best-effort fast-forward update, checks out the exact
shared-system submodule pin, installs it with the VM-owned host adapter, and
then restores each agent independently. One failed credential restore does not
block the other agent.

Store credentials only in the platform secret manager:

| Variable | Purpose |
|---|---|
| `CLAUDE_CODE_CREDENTIALS_B64` | Claude Code OAuth credentials JSON |
| `CODEX_AUTH_JSON_B64` | gzip+base64 Codex `auth.json` |
| `SHARED_REPO_TOKEN` | Optional fine-grained Contents R/W token for this VM repository only |

Do not add a global `GH_TOKEN` or `GITHUB_TOKEN` merely for this repository.
Cursor may use separate bot authentication for product repositories. When
`SHARED_REPO_TOKEN` is present, bootstrap scopes its token URL to this checkout's
`origin` only.

## Shared System Pin

`agent-system/` is a Git submodule, not a vendored copy. Bootstrap always runs:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

To update it deliberately:

```bash
git -C agent-system fetch origin
git -C agent-system checkout --detach <verified-sha>
git add agent-system
./validate.sh
```

Use a shared SHA whose own Linux and macOS validation is green. The VM gate
then proves that exact pin with VM bootstrap and adapter behavior.

## Standard Invocations

The shared installer receives `--host-integration "$REPO/host"`, so ordinary
VM shell commands use this repository's adapters:

- `claude` starts interactive work with Remote Control and
  `bypassPermissions` unless the command is administrative or noninteractive.
- `codex` prefers the standalone package, starts durable Remote Control when
  needed, and launches interactive work with approval, sandbox, and managed
  hook-trust prompts bypassed.

Set `AGENT_REMOTE_CONTROL=0` for a one-command opt-out. These defaults assume a
user-owned trusted VM.

## Claude Code

On an authenticated machine, encode the credentials file and store the result
as `CLAUDE_CODE_CREDENTIALS_B64`:

```bash
base64 < ~/.claude/.credentials.json | tr -d '\n'
```

Restore and start a persistent remote session with:

```bash
CLAUDE_PROJECT_DIR="$PWD" ./claude-code/restore-claude-credentials.sh
CLAUDE_PROJECT_DIR="$PWD" ./claude-code/start-remote-control.sh
```

Claude Remote Control requires a real Claude subscription OAuth login. An
Anthropic API key is not a substitute. The session runs in VM-aware `tmux` and
uses outbound HTTPS, so no inbound VM port is required.

## Codex CLI

For a headless first login:

```bash
./codex/install-standalone.sh
./codex/ensure-codex-config.sh
./codex/start-device-auth.sh
```

After `codex login status` succeeds, export the compressed credential payload:

```bash
./codex/export-codex-auth-b64.sh
```

Store that output as `CODEX_AUTH_JSON_B64`. Bootstrap restores it to file-backed
credential storage and starts the standalone Remote Control daemon. Do not
commit `auth.json`, credential JSON, base64 payloads, `.env` files, or tokenized
remote URLs.

## Validation

Run the complete VM gate:

```bash
./validate.sh
```

It checks:

- exact and clean shared-system submodule state;
- shared policy, skill, hook, installer, and helper tests;
- VM host-adapter invocation behavior;
- bootstrap argument and credential-restore ordering;
- fresh-home installation through the VM adapter;
- shell syntax, repository wiring, and whitespace.

GitHub Actions checks out submodules recursively and runs the same command.
