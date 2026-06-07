#!/usr/bin/env bash
# PreToolUse(Edit|MultiEdit|Write|NotebookEdit) guard: keep edits off the live
# repo-root checkout. This repo's isolation invariant (ISOLATION.md) is that the
# main working tree is read-only — every change is made in a worktree under
# .claude/worktrees/<slug> on its own branch. This hook enforces it: a write whose
# target resolves inside the main checkout but outside .claude/worktrees/ is denied.
#
# Always enforces — the skill suite is built on worktree isolation (ISOLATION.md),
# so the guidance already drives every consumer into the model; this is its
# backstop, not an opt-in. Registered in hooks/hooks.json.
set -euo pipefail

input=$(cat)
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' <<<"$input")
[ -n "$path" ] || exit 0   # no path on this tool call — not our concern

# Canonical absolute path. The prefix check that follows is purely textual, so the
# target MUST be canonicalized first — collapse `.`/`..` and resolve symlinks — or
# the verdict tracks how the path is spelled, not where the write lands. A path like
# .claude/worktrees/../README.md would otherwise prefix-match the worktrees
# allow-glob yet resolve into the main checkout, slipping the guard (#110).
#
# canon() resolves WITHOUT requiring the target to exist: Write creates new files,
# so an existence-required resolver (BSD `realpath`, which also lacks `-m`) would
# fail on the common case and the hook would fall back to the raw path. Python's
# os.path.realpath ships on macOS and Linux, resolves existing symlinks, and
# collapses `..` lexically when the tail does not yet exist — the needed semantics.
# The path is passed as an argv element (never interpolated into code), so an
# attacker-chosen path is inert data here: no command substitution or glob over it.
canon() {
  python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

case "$path" in
  /*) abs="$path" ;;
  *)  abs="$PWD/$path" ;;
esac
abs=$(canon "$abs") || exit 0   # can't canonicalize — fail open, same stance as below

# The MAIN checkout root, resolvable even from inside a worktree: --git-common-dir
# is the shared .git of the main checkout, and its parent is that checkout's root.
# So a worktree session can't edit main either. Fail open if git can't resolve it.
# Canonicalize the root too so its symlinks match the canonicalized target above.
common=$(git -C "$PWD" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main_root=$(canon "$(dirname "$common")") || exit 0
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

then edit the file under .claude/worktrees/<slug>/ and address it by that path."

jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
