# Coding Agent VM Setup

Portable, model-agnostic setup for running AI coding agents on a cloud dev VM
(Cursor Cloud, Codespaces, a plain Linux box — anything). Drop this repo on any
VM, for any project. Nothing here is tied to a specific codebase.

Each agent has its own section and its own subdirectory so the tooling never
gets confused between them.

| Agent | Status | Location |
|-------|--------|----------|
| [Claude Code](#claude-code) | ready | `claude-code/` |
| [Codex CLI](#codex-cli) | ready | `codex/` |

---

## Claude Code

Scripts in [`claude-code/`](claude-code/):

| File | Purpose |
|------|---------|
| `restore-claude-credentials.sh` | Rehydrate `~/.claude/.credentials.json` from a base64 env secret so a fresh VM session authenticates without an interactive login. |
| `start-remote-control.sh` | Launch Remote Control in a persistent `tmux` session so a phone/laptop can drive the VM. |

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
| `ensure-codex-config.sh` | Force `cli_auth_credentials_store = "file"` so credentials live in `auth.json` (required on headless VMs). |
| `restore-codex-credentials.sh` | Rehydrate `~/.codex/auth.json` from base64 secret `CODEX_AUTH_JSON_B64`. |
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
