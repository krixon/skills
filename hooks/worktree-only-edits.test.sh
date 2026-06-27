#!/usr/bin/env bash
# Tests for the worktree-only-edits PreToolUse guard. The guard reads tool-input
# JSON on stdin and either stays silent + exits 0 (ALLOW) or emits a JSON object
# with permissionDecision:"deny" (DENY). We stage a throwaway git repo as the
# "main checkout", craft a Write/Edit payload pointing at a path inside it, run the
# hook with PWD set to that repo, and assert the verdict from its stdout.
#
# The load-bearing case is the `..`-traversal bypass (#110): a path spelled
# `.claude/worktrees/../README.md` lexically prefix-matches the worktrees allow-glob
# but resolves into the main checkout — it MUST be denied, not allowed.
set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
hook="$here/worktree-only-edits.sh"

# A throwaway "main checkout": a real git repo so the hook's git rev-parse resolves
# a root, with a .claude/worktrees/<slug> dir standing in for a sanctioned worktree.
repo="$(mktemp -d)"
# macOS mktemp hands back /var/... which is a symlink to /private/var; canonicalize
# so our expectations match what the hook's canonicalization will produce.
repo="$(cd "$repo" && pwd -P)"
# Init on main with a commit so HEAD resolves to `main` — the hook's branch-state
# check (ADR 0010) denies edits only while the main checkout holds main, so the
# default-branch name must be deterministic, not left to init.defaultBranch.
git -C "$repo" init -q -b main
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
mkdir -p "$repo/.claude/worktrees/somework"
: > "$repo/seed.txt"
git -C "$repo" add seed.txt
git -C "$repo" commit -qm seed
outside="$(mktemp -d)"
outside="$(cd "$outside" && pwd -P)"
trap 'rm -rf "$repo" "$outside"' EXIT

pass=0
fail=0

# run <desc> <want: allow|deny> <tool> <path-field> <path-value>
# Feeds a crafted payload on stdin with PWD=$repo so the hook resolves $repo as the
# main checkout. Captures stdout; presence of permissionDecision:"deny" => DENY.
run() {
  local desc="$1" want="$2" tool="$3" field="$4" value="$5"
  local payload out got
  payload="$(jq -n --arg t "$tool" --arg f "$field" --arg v "$value" \
    '{tool_name:$t, tool_input:{($f):$v}}')"
  out="$(cd "$repo" && printf '%s' "$payload" | "$hook" 2>&1)"
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

# AC1 + AC6 (regression): `..`-traversal out of the worktrees dir into the main
# checkout must be DENIED. This is the bug — pre-fix it is wrongly allowed.
run "traversal out of worktrees into main checkout is denied" \
    deny Write file_path ".claude/worktrees/../README.md"

# AC1 variant: deeper traversal landing in main checkout, still denied.
run "traversal via worktree slug back into main is denied" \
    deny Write file_path ".claude/worktrees/somework/../../src/app.js"

# AC2: a genuine worktree path is still ALLOWED.
run "genuine existing worktree path is allowed" \
    allow Write file_path ".claude/worktrees/somework/file.txt"

# AC4: a NEW (non-existent) file inside a worktree is allowed (canonicalization
# must handle a path whose final component does not yet exist).
run "new non-existent file inside worktree is allowed" \
    allow Write file_path ".claude/worktrees/somework/sub/new-file.txt"

# AC3: a bare main-checkout file is still DENIED.
run "bare main-checkout file is denied" \
    deny Write file_path "README.md"

# AC3 variant via absolute path into main checkout.
run "absolute main-checkout file is denied" \
    deny Write file_path "$repo/docs/guide.md"

# AC5: a write outside the repo entirely is ALLOWED.
run "absolute path outside the repo is allowed" \
    allow Write file_path "$outside/scratch.txt"

# AC5 variant: traversal that climbs out of the repo entirely is allowed.
run "traversal escaping the repo entirely is allowed" \
    allow Write file_path "../../../tmp-outside-$$/x.txt"

# Tool coverage: Edit on a traversal path is denied too.
run "Edit on traversal path is denied" \
    deny Edit file_path ".claude/worktrees/../config.yaml"

# Tool coverage: NotebookEdit uses notebook_path, traversal still denied.
run "NotebookEdit traversal via notebook_path is denied" \
    deny NotebookEdit notebook_path ".claude/worktrees/../analysis.ipynb"

# No path on the call => not our concern => allowed (hook exits 0 silently).
run "empty path is allowed (not our concern)" \
    allow Write file_path ""

# ADR 0010 branch-in-primary: with the main checkout on a feature branch, edits to
# it are sanctioned branch-mode work and ALLOWED. The same paths denied above (while
# on main) flip to allow here — the main checkout's branch is the whole signal.
git -C "$repo" checkout -q -b feat/branch-mode
run "main-checkout file allowed while on a feature branch" \
    allow Write file_path "README.md"
run "absolute main-checkout file allowed while on a feature branch" \
    allow Write file_path "$repo/docs/guide.md"
git -C "$repo" checkout -q main

# Back on main, the same edit is denied again — the loosening is branch-scoped, not
# a permanent relaxation of the backstop.
run "main-checkout file denied again once back on main" \
    deny Write file_path "README.md"

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" = 0 ]
