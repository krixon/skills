#!/usr/bin/env bash
# Portable across macOS (bash 3.2, BSD coreutils) and Linux (bash 4+, GNU): no
# assoc arrays/mapfile/case-modification, no GNU-only coreutils flags.
#
# UserPromptSubmit hook: inject the untrusted-external-content boundary as context
# on every turn, ungated. A skill's instruction enters context once at invocation
# and loses salience as the conversation grows; the boundary is a security rule that
# must hold whether or not any skill is loaded, so it is re-stated each turn rather
# than gated on a marker.
#
# SECURITY.md at the plugin root is the single source — the hook reads it rather than
# embedding a copy, so the human-editable file stays authoritative.
#
# Fail open: the boundary is advisory context, not enforcement. A missing or
# unreadable SECURITY.md, a malformed payload, or an absent jq must skip injection
# for this turn, never abort — a non-zero exit would surface a hook error on every
# prompt and wedge the session. Skipping one turn's advisory context is the safe
# failure; blocking every prompt is not.
set -euo pipefail

cat >/dev/null || true   # drain stdin; payload is unused, but the event supplies it

root="${CLAUDE_PLUGIN_ROOT:-}"
[ -n "$root" ] || exit 0
boundary_file="${root}/SECURITY.md"
[ -r "$boundary_file" ] || exit 0

boundary=$(cat "$boundary_file" 2>/dev/null || true)
[ -n "$boundary" ] || exit 0

jq -n --arg c "$boundary" \
  '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}' \
  2>/dev/null || exit 0
