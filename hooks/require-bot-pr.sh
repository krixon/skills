#!/usr/bin/env bash
# Portable across macOS (bash 3.2, BSD coreutils) and Linux (bash 4+, GNU): sed -E
# and grep -E with POSIX classes, no GNU-only flags, no bash 4 features.
#
# PreToolUse(Bash) guard: when a repo opens PRs as a dedicated bot account — so a
# human can approve them, since GitHub forbids approving your own PR — an agent
# must not open a PR as the logged-in (approver) account.
#
# Generic and inert by default. It activates only when GH_PR_BOT_ACCOUNT names the
# bot account, so the plugin ships without assuming any particular account. Enable
# it per repo, e.g. in that repo's .claude/settings.json:
#   { "env": { "GH_PR_BOT_ACCOUNT": "your-bot-login" } }
# then open PRs with that account's token:
#   GH_TOKEN=<token for the bot> gh pr create …
set -euo pipefail

bot="${GH_PR_BOT_ACCOUNT:-}"
[ -n "$bot" ] || exit 0   # no bot account configured — nothing to enforce

cmd=$(jq -r '.tool_input.command // ""')

# Only PR creation chooses an author; reopen/edit/merge keep the existing one.
# A command cannot be invoked from inside a quote, so drop quoted spans first:
# that removes the phrase when it appears as data — an issue body that documents
# the incantation, a grep searching for it — while leaving every real invocation
# intact, in any position (after a pipe, xargs, time, &&, …). An unquoted bare
# mention still trips it, which is the safe direction for a guard.
unquoted=$(sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g" <<<"$cmd")
grep -qE '(^|[^[:alnum:]_-])gh[[:space:]]+pr[[:space:]]+create([^[:alnum:]_-]|$)' <<<"$unquoted" || exit 0

# An explicit GH_TOKEN= on the command means identity was supplied rather than
# defaulting to the logged-in account. That is the signal we require.
grep -qE '(^|[[:space:]])GH_TOKEN=' <<<"$cmd" && exit 0

reason="Open the PR as the ${bot} account, not the logged-in account — GitHub forbids approving your own PR, so the author cannot also be the approver. Re-run supplying ${bot}'s token, which switches identity for this one command only:

  GH_TOKEN=<token for ${bot}> gh pr create …

(This check is active because GH_PR_BOT_ACCOUNT=${bot}.)"

jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
