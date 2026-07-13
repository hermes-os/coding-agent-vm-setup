# Coding Agent VM Setup

Portable, model-agnostic setup for running AI coding agents on a cloud dev VM
(Cursor Cloud, Codespaces, a plain Linux box — anything). Drop this repo on any
VM, for any project. Nothing here is tied to a specific codebase.

Each agent has its own section and its own subdirectory so the tooling never
gets confused between them.

| Layer | Status | Location |
|-------|--------|----------|
| [Shared agent system](#shared-agent-system) | ready | `agent-system/` |
| [Claude Code](#claude-code) | ready | `claude-code/` |
| [Codex CLI](#codex-cli) | ready | `codex/` |

---

## Cursor Cloud boot snippet

Add this to your Cursor environment **update/install script** (platform UI — not in an app repo). Pair with `npm install` (or your project's dependency step) in the same script.

**One-liner** (clone/update, then bootstrap):

```bash
npm install   # Ashwren or your app — omit on non-Node projects
REPO=~/coding-agent-vm-setup
[ -d "$REPO/.git" ] || git clone https://github.com/hermes-os/coding-agent-vm-setup "$REPO"
CLAUDE_PROJECT_DIR=/workspace "$REPO/bootstrap.sh"
```

[`bootstrap.sh`](bootstrap.sh) owns self-update, so the snippet only clones when missing. It runs: best-effort `git pull` → optional scoped push remote → install the shared agent system → restore Claude → restore Codex. A failed credential restore does not block the other agent.

**Secrets** (Cursor My Secrets — never commit):

| Secret | Purpose |
|--------|---------|
| `CLAUDE_CODE_CREDENTIALS_B64` | Claude Code OAuth (minimal `claudeAiOauth` JSON) |
| `CODEX_AUTH_JSON_B64` | Codex ChatGPT OAuth (`auth.json`, gzip+base64 export) |
| `SHARED_REPO_TOKEN` | Fine-grained PAT: **Contents R/W** on `hermes-os/coding-agent-vm-setup` only |

### Scoped GitHub push from Cloud VMs

Cursor injects a global `git config insteadOf` that rewrites `https://github.com/` to `cursor[bot]`, which cannot push to your org. **Do not** set a global `GH_TOKEN` / `GITHUB_TOKEN` secret — that overrides Cursor's bot auth for all repos (including Ashwren) and can break the agent.

Instead, `bootstrap.sh` sets **only this repo's** `origin` to a token URL (does not match the `https://github.com/` prefix, so it bypasses the rewrite):

```bash
# handled inside bootstrap.sh when SHARED_REPO_TOKEN is set
git -C ~/coding-agent-vm-setup remote set-url origin \
  "https://x-access-token:${SHARED_REPO_TOKEN}@github.com/hermes-os/coding-agent-vm-setup.git"
```

Create the PAT at GitHub → Settings → Developer settings → Fine-grained tokens → repository access: **only** `coding-agent-vm-setup` → Permissions: **Contents → Read and write**. Set an expiry (e.g. 90 days). The token is stored in plaintext in that repo's `.git/config` (same as Cursor's own injection); fine-grained scope limits blast radius.

**tmux on Cursor VMs:** scripts use [`lib/tmux.sh`](lib/tmux.sh) — auto-selects `/exec-daemon/tmux.portal.conf` when present, else plain `tmux`.

---

## Shared agent system

[`agent-system/`](agent-system/) is the portable source of truth shared by
Codex, Claude Code, and Cursor. It follows Peter Steinberger's public
`agent-scripts` architecture: one terse global rules file, dynamically loaded
skills, pointer-style repository instructions, skill-owned hooks, concise
handoff/pickup, and one active plan for genuinely multi-session projects.

The imported system is intentionally model-neutral and excludes Peter's
personal accounts, machine routing, OpenClaw-only infrastructure, and pinned
reviewer models. Upstream references used for this snapshot:

- `steipete/agent-scripts` at `d42cf80a3206db86270a75414b8f8a62cd389ccb`
- `openclaw/agent-skills` at `4664d27da471d1cb71bebdd9845dc8a6c56d6bbe`
- `behavior-validator` is vendored from `openclaw/agent-skills` under its MIT
  license. The path-scoped commit pattern is adapted from `agent-scripts`
  under its MIT license; the remaining skills are lean host-neutral workflows.

### Installed catalog

- `handoff`: compact pause/resume evidence.
- `pickup`: reconstruct current state and continue.
- `delegate`: write a portable, model-neutral role assignment.
- `review`: findings-first independent plan/diff/code review, with the model
  assigned in the task prompt.
- `behavior-validator`: Peter's source-blind user-visible behavior contract.
- `fix-issue`: reproduce, repair, test, and complete authorized issue delivery.
- `land`: verify and complete commit/push/merge delivery without repeated gates.
- `release`: prepare, publish, and verify repository-native releases.
- `portfolio`: reconstruct and coordinate work across repositories without a
  persistent diary.
- `maintain-skills`: validate skill structure, hooks, duplicates, and metadata
  context cost.
- `capabilities`: generate the current host tool and skill inventory on demand.

Repo-specific workflows stay in their owning repo. For example, Ashwren's
`books` roles and hooks live in `.agents/skills/books`, not in this global
catalog.

### Host wiring

Run directly on any machine:

```bash
./agent-system/install.sh
```

The installer is idempotent and creates these adapters:

- `~/.agents/AGENTS.md`, `skills/`, `hooks/`, and `bin/docs-list`
- `~/.codex/AGENTS.md`, global prompts, and hook configuration
- `~/.claude/CLAUDE.md`, `AGENTS.md`, flat skills, commands, and hooks
- `~/.cursor/rules/global-engineering.mdc`, commands, and hooks
- `~/.local/bin/docs-list`, `agent-docs-list`, `agent-system-doctor`,
  `committer`, `agent-skill-audit`, `agent-capabilities`, and
  `agent-repo-inventory`

It disables Claude auto-memory and Codex memories, removes host model pins so
models remain task-prompt assignments, preserves unrelated host settings, and
removes known legacy plugin config. Set
`AGENT_SYSTEM_PRUNE_LEGACY=1` to remove known Cal/reviewer files during an
upgrade; `bootstrap.sh` enables that cleanup on VMs.

### Repository pointer

Each repo keeps a small project guide beginning with:

```text
READ ~/.agents/AGENTS.md BEFORE ANYTHING (skip if missing).
```

Keep product facts below that line. Use `CLAUDE.md -> AGENTS.md`; store product
skills in `.agents/skills/<name>` and expose those to Claude with per-skill
symlinks only when needed. Cursor and Codex discover the root `AGENTS.md` and
`.agents/skills` directly.

Large cross-cutting projects get one `docs/plan/<project>.md`. Ordinary tasks
get no plan file. Run `agent-docs-list` to list `summary` and `read_when`
metadata without loading every document.

Validate the portable layer with:

```bash
./agent-system/validate.sh
```

Validation includes shell and Python syntax, strict skill and hook auditing,
installer/doctor integration, helper behavior, and host adapter tests. GitHub
Actions runs the same gate for changes to the portable system.

### Standard invocations

The installer adds one managed source block to Bash and Zsh startup files.
After opening a new shell, ordinary interactive commands use these defaults:

- `claude`: starts the session with Remote Control and
  `bypassPermissions` enabled.
- `codex`: ensures the durable Remote Control daemon is running, then starts
  the TUI with approvals, sandboxing, and managed hook-trust prompts bypassed.

Native user config also persists Claude `bypassPermissions` and Codex
`approval_policy = "never"` plus `sandbox_mode = "danger-full-access"`, so
noninteractive and explicitly invoked workflows inherit the same permission
policy. Utility commands such as `doctor`, `login`, `update`, `claude -p`, and
`codex exec` do not start Remote Control. Set `AGENT_REMOTE_CONTROL=0` for a
one-command opt-out. This baseline assumes a user-owned, trusted machine;
change these defaults before installing it on a shared host.

---

## Claude Code

Scripts in [`claude-code/`](claude-code/):

| File | Purpose |
|------|---------|
| `restore-claude-credentials.sh` | Rehydrate `~/.claude/.credentials.json` from a base64 env secret so a fresh VM session authenticates without an interactive login. |
| `start-remote-control.sh` | Launch bypass-permissions Remote Control in a persistent `tmux` session so a phone/laptop can drive the VM. |

### Why this works on a VM with no inbound network

Claude Code is a headless Node CLI — no GUI needed. **Remote Control dials
outbound over HTTPS 443**: the VM opens a persistent connection up to Claude,
and your phone/laptop talks to Claude, which relays commands back down that
outbound channel. Because the VM reaches *out* (rather than you reaching *in*),
it needs no public inbound route, no port forwarding, and no SSH relay.

### One-time setup

1. On a machine where Claude Code is already logged in, capture the credentials:

   ```bash
   base64 -w0 ~/.claude/.credentials.json
   ```

   (Remote Control needs the **full** credentials JSON, including
   `claudeAiOauth.refreshToken` — not just an OAuth token.)

2. Store that base64 string as a **secret env var** named
   `CLAUDE_CODE_CREDENTIALS_B64` in your VM platform's secret manager. Do **not**
   commit it or paste it into a chat/log.

   > Some platforms cap secret length (e.g. ~4096 chars). If you hit the limit,
   > store a minimal credentials JSON containing only the `claudeAiOauth` block.

3. Have your VM run `claude-code/restore-claude-credentials.sh` on boot / session start.

### Usage

```bash
# Rehydrate credentials for the current project directory:
CLAUDE_PROJECT_DIR="$PWD" ./claude-code/restore-claude-credentials.sh

# Start Remote Control (customize the name shown in the app):
RC_NAME="My VM" CLAUDE_PROJECT_DIR="$PWD" ./claude-code/start-remote-control.sh
```

Then open the **Code** tab in the Claude mobile app, or visit
<https://claude.ai/code>, on a device signed into the same Claude account.

### Requirements & caveats

- **Real OAuth login required.** Remote Control needs a Pro/Max/Team/Enterprise
  plan login. `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` are
  inference-only and **cannot** start Remote Control — leave them unset for RC
  sessions. (Team/Enterprise orgs must enable Remote Control in admin settings.)
- **Keep the tmux pane alive.** Detaching (`Ctrl-b d`) is fine; killing the pane
  or going offline more than ~10 minutes ends the session.
- **Never commit the credential blob.** It's a long-lived secret. Keep it in the
  platform secret store only. See `.gitignore`.
- **Optional SSH** is a separate concern: raw inbound SSH would need an outbound
  relay (Tailscale userspace, cloudflared, reverse SSH). Remote Control does not.

---

## Codex CLI

Scripts in [`codex/`](codex/):

| File | Purpose |
|------|---------|
| `install-standalone.sh` | Install the official standalone Codex package required by the managed Remote Control daemon. |
| `ensure-codex-config.sh` | Force `cli_auth_credentials_store = "file"` so credentials live in `auth.json` (required on headless VMs). |
| `restore-codex-credentials.sh` | Rehydrate `~/.codex/auth.json` from base64 secret `CODEX_AUTH_JSON_B64`. |
| `start-remote-control.sh` | Start the durable Codex app-server with Remote Control enabled. |
| `start-device-auth.sh` | Launch `codex login --device-auth` in tmux (headless OAuth). |
| `export-codex-auth-b64.sh` | Print base64 of `auth.json` for the Cursor secret (after login). |

### Headless OAuth (device code)

On a VM with no browser, use **device auth** (not the localhost redirect flow):

```bash
./codex/ensure-codex-config.sh
./codex/start-device-auth.sh
# Open https://auth.openai.com/codex/device and enter the one-time code from the log
```

After `codex login status` shows logged in:

```bash
./codex/export-codex-auth-b64.sh   # gzip+base64 → store as secret CODEX_AUTH_JSON_B64 (~3.5k chars)
```

### Persist on fresh VMs

1. Store the export output as **`CODEX_AUTH_JSON_B64`** in your platform secret manager.
2. On boot / session start:

```bash
./codex/ensure-codex-config.sh
./codex/restore-codex-credentials.sh
```

3. Verify: `codex login status` and `codex exec "say ok"`.

### Requirements & caveats

- **ChatGPT subscription or API key** — device auth uses ChatGPT login; API-key login uses a different `auth.json` shape (also supported by restore).
- **File storage only for restore** — keyring/Secret Service credentials cannot be rehydrated from a secret; `ensure-codex-config.sh` sets `file`.
- **Secret size** — ChatGPT OAuth `auth.json` exceeds Cursor My Secrets' ~4096 char limit when base64-encoded raw; `export-codex-auth-b64.sh` gzip-compresses first (~3464 chars). `restore-codex-credentials.sh` accepts gzip or plain JSON payloads.
- **Never commit `auth.json` or the b64 blob.**

---

## Codex (CLI + Desktop) — legacy note

Desktop-specific remote workflows may be documented here later. CLI auth + restore above is sufficient for Cloud Agent VMs.

---

## Security

Scripts read credentials from the environment and write `chmod 600` files. No
secret value is ever stored in this repo. `.gitignore` blocks common secret
filenames as a backstop.
