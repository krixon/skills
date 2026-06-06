#!/usr/bin/env bash
# UserPromptSubmit hook: while caveman mode is active, reinject its rules on every
# turn. caveman ships as a single SKILL.md whose instruction enters context once at
# invocation and is never re-presented, so as the conversation grows it loses
# salience and the default voice reasserts. This hook re-states the rules each turn,
# gated by a session-scoped marker that skills/caveman/scripts/caveman-state.sh
# writes on activation and removes on deactivation.
#
# Inert unless a marker for this session exists, so it costs nothing when caveman is
# off. Resolution mirrors caveman-state.sh: prefer CLAUDE_CODE_SESSION_ID (the key
# the state script writes under, when it is inherited here too), then the stdin
# session_id, then a shared "global" marker. The marker dir is $HOME-anchored, not
# $TMPDIR, so writer and reader agree on the path.
#
# Fail open: a malformed or empty payload must never abort this hook — a non-zero
# exit would surface a hook error on every turn, even when caveman is off.
set -euo pipefail

payload=$(cat || true)

# Prefer the env session id (matches the state script's key when inherited); fall
# back to parsing the stdin session_id. jq must not abort the hook, hence the guard.
sid="${CLAUDE_CODE_SESSION_ID:-}"
if [ -z "$sid" ]; then
  sid=$(jq -r '.session_id // empty' <<<"$payload" 2>/dev/null || true)
fi

dir="${HOME:-/tmp}/.claude/caveman"

marker=""
for key in "$sid" global; do
  [ -n "$key" ] || continue
  if [ -f "${dir}/${key}.on" ]; then
    marker="${dir}/${key}.on"
    break
  fi
done
[ -n "$marker" ] || exit 0   # caveman not active for this session — inject nothing

read -r -d '' reminder <<'EOF' || true
Caveman mode is ACTIVE. Respond terse like a smart caveman — all technical
substance stays, only fluff dies. Drop articles (a/an/the), filler
(just/really/basically/actually/simply), pleasantries, and hedging. Fragments OK.
Short synonyms; abbreviate common terms (DB/auth/config/req/res/fn/impl); arrows
for causality (X -> Y). Keep technical terms, code blocks, and quoted errors
exact. Drop the style only for security warnings, irreversible-action
confirmations, or when asked to clarify, then resume. Off only when the user says
"stop caveman" or "normal mode".
EOF

jq -n --arg c "$reminder" \
  '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
