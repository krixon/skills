#!/usr/bin/env bash
# Portable across macOS (bash 3.2, BSD coreutils) and Linux (bash 4+, GNU): only
# mkdir/rm and parameter defaults, no GNU-only flags, no bash 4 features.
#
# Toggle caveman mode's activation marker. The model runs this when it enters or
# leaves caveman mode; the UserPromptSubmit hook (hooks/caveman-reminder.sh) reads
# the marker each turn and reinjects the rules, so the mode survives context growth
# instead of decaying after the activation turn falls out of the model's attention.
#
#   caveman-state.sh on    # entering caveman mode
#   caveman-state.sh off   # leaving it
#
# The marker lives under $HOME (not $TMPDIR — that differs between the model's tool
# shell and the harness-spawned hook on macOS, so they'd disagree on the path). It
# is session-scoped on CLAUDE_CODE_SESSION_ID so concurrent sessions don't leak the
# mode into one another; the hook keys on the same id (preferring this env var, then
# its stdin session_id). With no session id we fall back to a shared "global" marker
# — single-session correct, no isolation. A path mismatch degrades to the prior
# behavior (mode doesn't persist) rather than misfiring.
set -euo pipefail

action="${1:-}"
dir="${HOME:-/tmp}/.claude/caveman"
marker="${dir}/${CLAUDE_CODE_SESSION_ID:-global}.on"

case "$action" in
  on)  mkdir -p "$dir"; : > "$marker" ;;
  off) rm -f "$marker" ;;
  *)   echo "usage: caveman-state.sh on|off" >&2; exit 2 ;;
esac
