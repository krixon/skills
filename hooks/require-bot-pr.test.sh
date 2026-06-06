#!/usr/bin/env bash
# Hook-level tests for require-bot-pr.sh. Feeds crafted tool_input.command JSON to
# the hook on stdin and asserts allow (exit 0, no deny JSON) vs deny (deny JSON).
# Run: bash hooks/require-bot-pr.test.sh
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/require-bot-pr.sh"

pass=0
fail=0

# run <account> <command-string> -> sets OUT to hook stdout
run() {
  local account="$1" command="$2"
  OUT=$(printf '%s' "$command" | jq -Rs '{tool_input:{command:.}}' \
    | GH_PR_BOT_ACCOUNT="$account" bash "$hook")
}

# Allowed = empty stdout (no deny JSON). Denied = deny JSON present.
is_deny() { grep -q '"permissionDecision": *"deny"' <<<"$OUT"; }

expect_allow() {
  local name="$1"
  if [ -z "$OUT" ] && ! is_deny; then
    printf 'ok   - %s (allow)\n' "$name"; pass=$((pass+1))
  else
    printf 'FAIL - %s (expected allow, got: %s)\n' "$name" "$OUT"; fail=$((fail+1))
  fi
}

expect_deny() {
  local name="$1"
  if is_deny; then
    printf 'ok   - %s (deny)\n' "$name"; pass=$((pass+1))
  else
    printf 'FAIL - %s (expected deny, got: %s)\n' "$name" "$OUT"; fail=$((fail+1))
  fi
}

# A literal space in the create phrase, so the source carries no real invocation
# unless the test intends one.
SP=' '

# --- heredoc-data allowed: the create phrase rides in a heredoc body ----------
run krixon-bot "$(printf 'gh issue comment 85 <<%sEOF%s\nbrief: then run the create command  gh pr%screate --fill\nEOF\n' "'" "'" "$SP")"
expect_allow "heredoc body (quoted delimiter) carrying create phrase"

run krixon-bot "$(printf 'gh issue comment 85 <<EOF\nbrief: gh pr%screate --fill\nEOF\n' "$SP")"
expect_allow "heredoc body (bare delimiter) carrying create phrase"

run krixon-bot "$(printf 'gh issue comment 85 <<-%sEND%s\n\tbrief: gh pr%screate --fill\n\tEND\n' "'" "'" "$SP")"
expect_allow "heredoc body (<<- with leading tabs, arbitrary delimiter) carrying create phrase"

run krixon-bot "$(printf 'gh issue comment 85 << EOF\nbrief: gh pr%screate --fill\nEOF\n' "$SP")"
expect_allow "heredoc body (space before delimiter word) carrying create phrase"

run krixon-bot "$(printf 'gh issue comment 85 <<"EOF"\nbrief: gh pr%screate --fill\nEOF\n' "$SP")"
expect_allow "heredoc body (double-quoted delimiter) carrying create phrase"

# --- quoted-data allowed: the create phrase rides in a quoted span ------------
run krixon-bot "$(printf "gh issue comment 85 --body 'run gh pr%screate --fill yourself'" "$SP")"
expect_allow "single-quoted span carrying create phrase"

run krixon-bot "$(printf 'gh issue comment 85 --body "run gh pr%screate --fill yourself"' "$SP")"
expect_allow "double-quoted span carrying create phrase"

# --- grep-literal allowed -----------------------------------------------------
run krixon-bot "$(printf "grep -r 'gh pr%screate' ." "$SP")"
expect_allow "grep over the create literal (quoted)"

# --- bare invocation denied (leading position) --------------------------------
run krixon-bot "$(printf 'gh pr%screate --fill' "$SP")"
expect_deny "bare leading invocation"

# --- non-leading invocation denied --------------------------------------------
run krixon-bot "$(printf 'true && gh pr%screate --fill' "$SP")"
expect_deny "invocation after &&"

run krixon-bot "$(printf 'echo x | gh pr%screate --fill' "$SP")"
expect_deny "invocation after |"

run krixon-bot "$(printf 'time gh pr%screate --fill' "$SP")"
expect_deny "invocation after time"

run krixon-bot "$(printf 'echo x | xargs gh pr%screate --fill' "$SP")"
expect_deny "invocation after xargs"

# A real invocation that ALSO opens a heredoc must still deny (opener line kept).
run krixon-bot "$(printf 'gh pr%screate --fill --body-file - <<EOF\nbody text\nEOF\n' "$SP")"
expect_deny "real invocation that opens a heredoc"

# --- GH_TOKEN=-prefixed invocation allowed (escape hatch) ---------------------
run krixon-bot "$(printf 'GH_TOKEN=abc gh pr%screate --fill' "$SP")"
expect_allow "GH_TOKEN= prefixed invocation"

# --- unset-account inert ------------------------------------------------------
OUT=$(printf 'gh pr%screate --fill' "$SP" | jq -Rs '{tool_input:{command:.}}' \
  | env -u GH_PR_BOT_ACCOUNT bash "$hook")
expect_allow "unset GH_PR_BOT_ACCOUNT is inert"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
