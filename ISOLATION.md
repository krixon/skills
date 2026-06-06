# Isolation

How work is kept off your live checkout. One invariant, binding on **every** edit to this repo — through a skill, a direct request, or an ad-hoc change alike: the repo-root checkout is read-only. Every change is made in a worktree on its own branch, never in the tree you're sitting in. The work-producing skills (`pickup`, `tdd`, `diagnose`, `write-skill`, `release`) and the `auto` loop build on this, but they don't own it and nothing is exempt by not going through one of them — the invariant precedes the skills.

## The repo-root checkout is read-only

Read, explore, and run in the repo root freely. The gate is the first *edit*, not the commit: the moment you would change a file — any file, for any reason — you do it in a worktree on its own branch, never in the repo-root checkout. This holds without exception — code, docs, and releases alike — and it makes concurrent sessions collision-proof, since no two ever share a working tree.

A `PreToolUse` hook (`hooks/worktree-only-edits.sh`) enforces this: it denies any `Edit`/`Write`/`NotebookEdit` whose target lands inside the main checkout but outside `.claude/worktrees/`. The rule is the contract; the hook is the backstop for when an agent reads the rule as documentation rather than instruction.

The repo root stays on the default branch (`main` / `master`), clean. Nothing edits or commits there; `main` advances only when a worktree's branch reaches it (below).

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
