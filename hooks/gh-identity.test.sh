#!/usr/bin/env bash
# Tests for the gh-identity PreToolUse guard. The guard reads the two bot-identity
# env vars and either stays silent + exits 0 (ALLOW) or emits a JSON object with
# permissionDecision:"deny" (DENY). It ignores stdin and the command entirely, so a
# test only has to set the env and feed an arbitrary Bash payload.
#
# The matrix is the whole contract: both-unset and both-set-non-empty ALLOW; every
# other combination (one without the other, either set-but-empty) DENY.
set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
hook="$here/gh-identity.sh"

pass=0
fail=0

# run <desc> <want: allow|deny> <acct-mode> <acct-val> <tok-mode> <tok-val>
# mode is "unset" (var not exported) or "set" (exported to the given value, which
# may be empty). A fixed Bash payload is fed on stdin to prove the command is ignored.
run() {
  local desc="$1" want="$2" am="$3" av="$4" tm="$5" tv="$6"
  local payload out got
  payload="$(jq -n '{tool_name:"Bash", tool_input:{command:"gh pr create --title x"}}')"
  out="$(
    unset GITHUB_BOT_ACCOUNT GITHUB_BOT_TOKEN_CMD
    [ "$am" = set ] && export GITHUB_BOT_ACCOUNT="$av"
    [ "$tm" = set ] && export GITHUB_BOT_TOKEN_CMD="$tv"
    printf '%s' "$payload" | "$hook" 2>&1
  )"
  if grep -q '"permissionDecision":"deny"' <<<"$out" || grep -q '"permissionDecision": "deny"' <<<"$out"; then
    got=deny
  else
    got=allow
  fi
  if [ "$got" = "$want" ]; then
    pass=$((pass+1)); printf 'PASS  %s\n' "$desc"
  else
    fail=$((fail+1))
    printf 'FAIL  %s  (got %s, want %s)\n' "$desc" "$got" "$want"
    printf '      output: %s\n' "$out"
  fi
}

# Valid: both unset → no bot → fall through to default gh.
run "both unset is allowed (no bot, default gh)" \
    allow unset "" unset ""

# Valid: both set and non-empty → bot fully configured.
run "both set non-empty is allowed (bot configured)" \
    allow set "krixon-bot" set "security find-generic-password -s krixon-bot -w"

# Half-configured: account without token.
run "account set, token unset is denied" \
    deny set "krixon-bot" unset ""

# Half-configured: token without account.
run "token set, account unset is denied" \
    deny unset "" set "gh auth token"

# Half-configured: account set but empty (the keychain/eval-miss shape).
run "account set-but-empty is denied" \
    deny set "" set "gh auth token"

# Half-configured: token set but empty.
run "token set-but-empty is denied" \
    deny set "krixon-bot" set ""

# Half-configured: both set but empty.
run "both set-but-empty is denied" \
    deny set "" set ""

# Half-configured: account unset, token set-but-empty (one defined, one not, and empty).
run "account unset, token set-but-empty is denied" \
    deny unset "" set ""

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" = 0 ]
