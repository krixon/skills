#!/usr/bin/env bash
# Portable across macOS (bash 3.2, BSD coreutils) and Linux (bash 4+, GNU): no
# assoc arrays/mapfile/case-modification, no GNU-only coreutils flags.
#
# PreToolUse(Bash) guard: bot identity is an all-or-nothing layer. GitHub identity
# is configured by two env vars — GITHUB_BOT_ACCOUNT and GITHUB_BOT_TOKEN_CMD
# (skills/GITHUB.md → PR identity). Exactly two states are valid:
#   - both unset             → no bot; gh runs as the default authed user (fall through)
#   - both set and non-empty → bot; gh writes carry the GH_TOKEN prefix / --author filter
# Every other combination — one var without the other, or either set but empty — is
# half-configured. That is where a silent fallback to the wrong identity hides (a PR
# opened as the maintainer instead of the bot), so the rule is stop and report, not
# guess. This hook detects only that half-configured state and denies; both valid
# states pass through untouched.
#
# It reads the ENVIRONMENT, never the command — a `gh` phrase appearing as data inside
# a command string can't trip it, and there is no per-command matching to false-positive
# on (the failure that sank the earlier command-scanning hook; ADR 0007). Matches Bash
# because that is the tool gh runs through. Registered in hooks/hooks.json.
set -euo pipefail

cat >/dev/null || true   # drain stdin; the env is the input, not the payload

# Distinguish unset from set-but-empty: ${VAR+x} expands to "x" only when VAR is set
# (even to ""), while -n tests non-empty. "Configured" means set AND non-empty.
acct_set="${GITHUB_BOT_ACCOUNT+x}"
tok_set="${GITHUB_BOT_TOKEN_CMD+x}"
acct_ok=""; [ -n "${GITHUB_BOT_ACCOUNT:-}" ] && acct_ok="x"
tok_ok="";  [ -n "${GITHUB_BOT_TOKEN_CMD:-}" ] && tok_ok="x"

# Both entirely unset → no bot configured → fall through to the default authed gh.
if [ -z "$acct_set" ] && [ -z "$tok_set" ]; then
  exit 0
fi
# Both set and non-empty → bot fully configured → proceed.
if [ -n "$acct_ok" ] && [ -n "$tok_ok" ]; then
  exit 0
fi

# Anything else is half-configured. Report each var's state precisely.
state() {
  if [ -z "$1" ]; then echo "unset"
  elif [ -z "$2" ]; then echo "set but empty"
  else echo "set"; fi
}
acct_state="$(state "$acct_set" "$acct_ok")"
tok_state="$(state "$tok_set" "$tok_ok")"

reason="GitHub bot identity is half-configured — stopping before any shell command runs. The two env vars must be set together and non-empty, or both left unset; no in-between (skills/GITHUB.md → PR identity).

  - GITHUB_BOT_ACCOUNT: ${acct_state}
  - GITHUB_BOT_TOKEN_CMD: ${tok_state}

Fix one of two ways in .claude/settings.json:
  - configure both — GITHUB_BOT_ACCOUNT to a gh login, GITHUB_BOT_TOKEN_CMD to a command that prints that account's token (a bot's PAT, or \"gh auth token\" for your own login); or
  - unset both — gh then runs as whatever account it is already authenticated as."

jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
