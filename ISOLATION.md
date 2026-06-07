# Isolation

One invariant, binding on **every** edit to this repo — through a skill, a direct request, or an ad-hoc change alike: the repo-root checkout is read-only; every change is made in a worktree on its own branch. The work-producing skills (`pickup`, `patch`, `tdd`, `diagnose`, `write-skill`, `release`) and the `auto` loop build on this but don't own it — it precedes them, and nothing is exempt by skipping them.

## The repo-root checkout is read-only

Read and explore the repo root freely; the gate is the first edit. The moment you would change a file, do it in a worktree on its own branch. This holds without exception — code, docs, releases alike — and makes concurrent sessions collision-proof, since no two share a working tree.

## A branch is the unit of work

One branch per issue or task, in its own worktree. Name it `<kind>/<issue>-<slug>` when there's a tracker issue, `<kind>/<slug>` when there isn't:

- `fix/142-null-deref-on-empty-cart`
- `feat/87-csv-export`
- `chore/bump-eslint`

Kinds: `feat fix chore docs refactor`. Pick the kind from the artifact, not the mood — a bug fix is `fix`, a new behavior is `feat`, a pure restructure is `refactor`.

Create the worktree under `.claude/worktrees/<slug>`:

```
git worktree add .claude/worktrees/<slug> -b <kind>/<slug> main
```

When the branch already exists — a resumed PR, or a claim that created the ref before the worktree (`pickup`) — check it out instead of creating it: drop `-b` and name the existing branch, fetching it first if it's only on the remote.

```
git worktree add .claude/worktrees/<slug> <kind>/<slug>
```

## Rebasing a branch onto a moved base

When the base branch advances under an open PR and the branch no longer replays cleanly, rebase it onto the base from its worktree — without squashing, so the commits stay individual deltas:

```
git rebase main
```

Resolve every conflict the replay raises, then force-push. A rebase rewrites the commits, so a plain push is rejected as non-fast-forward; `--force-with-lease` pushes the rewrite but refuses if the remote moved under you:

```
git push --force-with-lease
```

## Reaching main, then teardown

A branch reaches `main` one of two ways, both from its worktree, neither touching the repo-root checkout:

- **Reviewed work** — everything `pickup` produces → a PR a human merges; `land` performs the merge.
- **A release** — `release` pushes its version bump and `v<new>` tag straight to `main` from its worktree. A release *marks* `main` rather than proposing a change to it, so it needs no PR — only the same isolation.

When the work lands, tear the worktree down:

```
git worktree remove <path>
git branch -D <branch>
```

This closes the worktree lifecycle — `land` does it after a merge, `release` after its push — and leaves the repo-root checkout exactly as you left it. (`land` adds the cleanup only a merged PR needs: deleting the remote branch and fast-forwarding local `main`.)
