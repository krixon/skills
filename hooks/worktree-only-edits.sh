#!/usr/bin/env bash
# PreToolUse(Edit|MultiEdit|Write|NotebookEdit) guard: keep edits off the live
# repo-root checkout. This repo's isolation invariant (ISOLATION.md) is that the
# main working tree is read-only — every change is made in a worktree under
# .claude/worktrees/<slug> on its own branch. This hook enforces it: a write whose
# target resolves inside the main checkout but outside .claude/worktrees/ is denied.
#
# Generic and inert by default. It activates only when CLAUDE_WORKTREE_ONLY is set
# to a non-empty value, so the plugin ships without imposing worktree-only editing
# on consumers who edit main directly. Enable it per repo in that repo's
# .claude/settings.json:
#   { "env": { "CLAUDE_WORKTREE_ONLY": "1" } }
set -euo pipefail

[ -n "${CLAUDE_WORKTREE_ONLY:-}" ] || exit 0   # not enabled — nothing to enforce

input=$(cat)
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' <<<"$input")
[ -n "$path" ] || exit 0   # no path on this tool call — not our concern

# Absolute, lexical path. A textual prefix check is enough — symlinks and `..` are
# left unresolved, and erring toward a bare-path match is the safe direction here.
case "$path" in
  /*) abs="$path" ;;
  *)  abs="$PWD/$path" ;;
esac

# The MAIN checkout root, resolvable even from inside a worktree: --git-common-dir
# is the shared .git of the main checkout, and its parent is that checkout's root.
# So a worktree session can't edit main either. Fail open if git can't resolve it.
common=$(git -C "$PWD" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main_root=$(dirname "$common")
worktrees="$main_root/.claude/worktrees"

case "$abs" in
  "$main_root"/*) ;;        # inside the main checkout — keep checking
  *) exit 0 ;;              # outside the repo (temp dir, ~/.claude, …) — allowed
esac
case "$abs" in
  "$worktrees"/*) exit 0 ;; # inside a worktree — the sanctioned place — allowed
esac

reason="Refusing to edit the live repo-root checkout — it is read-only (ISOLATION.md). Make this change in a worktree on its own branch instead:

  git worktree add .claude/worktrees/<slug> -b <kind>/<slug> main

then edit the file under .claude/worktrees/<slug>/ and address it by that path. (This check is active because CLAUDE_WORKTREE_ONLY is set.)"

jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
