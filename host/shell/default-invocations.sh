# VM interactive launch behavior. Set AGENT_REMOTE_CONTROL=0 for a one-command
# opt-out without changing the shared system or this host adapter.
claude() {
  "$HOME/.agents/bin/agent-claude" "$@"
}

codex() {
  "$HOME/.agents/bin/agent-codex" "$@"
}
