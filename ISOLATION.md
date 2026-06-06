# Isolation

How work is kept off your live checkout. One invariant: the repo-root checkout is read-only — every change is made in a worktree on its own branch, never in the tree you're sitting in. The work-producing skills (`pickup`, `tdd`, `diagnose`, `write-skill`, `release`) and the `auto` loop follow it.

## The repo-root checkout is read-only

Read, explore, and run in the repo root freely. The gate is the first *edit*, not the commit: the moment you would change a file, you do it in a worktree on its own branch, never in the repo-root checkout. This holds without exception — code, docs, and releases alike — and it makes concurrent sessions collision-proof, since no two ever share a working tree.

The repo root stays on the default branch (`main` / `master`), clean. Nothing edits or commits there; `main` advances only when a worktree's branch reaches it (below). Override only on an explicit instruction to work in the repo root ("just do it on main here") — and that approval doesn't carry to the next task.

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
