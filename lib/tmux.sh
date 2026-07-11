# Shared tmux wrapper for cloud VMs (Cursor portal config) and plain Linux.
# Source from agent scripts: source "$(dirname "$0")/../lib/tmux.sh"
#
# Optional: TMUX_CONFIG=/path/to/tmux.conf overrides auto-detection.

vm_tmux() {
  local cfg="${TMUX_CONFIG:-}"
  if [[ -z "$cfg" && -f /exec-daemon/tmux.portal.conf ]]; then
    cfg=/exec-daemon/tmux.portal.conf
  fi
  if [[ -n "$cfg" ]]; then
    tmux -f "$cfg" "$@"
  else
    tmux "$@"
  fi
}

vm_tmux_attach_hint() {
  local session="$1"
  if [[ -n "${TMUX_CONFIG:-}" ]] || [[ -f /exec-daemon/tmux.portal.conf ]]; then
    echo "  tmux -f ${TMUX_CONFIG:-/exec-daemon/tmux.portal.conf} attach -t $session"
  else
    echo "  tmux attach -t $session"
  fi
}
