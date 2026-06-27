# Isolation

Every edit to this repo — through a skill, a direct request, or an ad-hoc change alike — is made on its own branch, never on a detached `main`. Two stances place that branch, and the default holds unless a stance is chosen:

- **strict worktree** (default) — the branch lives in its own worktree under `.claude/worktrees/<slug>`; the repo-root checkout stays read-only on `main`. No two sessions share a working tree, so concurrent work is collision-proof. This is what the work-producing skills (`pickup`, `patch`, `tdd`, `diagnose`, `write-skill`, `release`) and the `auto` loop build on.
- **branch-in-primary** — the branch is checked out in the primary checkout itself, no separate worktree. It keeps warm working-directory state (`node_modules`, build caches, language-server indexes) that a fresh worktree throws away, at the cost of the read-only-root invariant: it is **single-session only**, since a second session switching the primary checkout's branch would collide. Opt in for solo, IDE-bound, or disk-tight work; the concurrency guarantee is strict mode's alone (ADR 0010).

The stances differ only in *where the branch lives*. Branch naming, rebasing, and the route to `main` are common to both.

## Selecting the stance

The `worktree` command group (`${CLAUDE_PLUGIN_ROOT}/bin/worktree`) owns the mechanics; a stance is selected per invocation, with a per-repo default:

- `--isolation worktree|branch` on `worktree create` / `teardown` — the explicit choice for one task.
- `$ISOLATION_MODE` — the repo's standing default when the flag is absent.
- unset → `worktree`.

## A branch is the unit of work

One branch per issue or task. Name it `<kind>/<issue>-<slug>` when there's a tracker issue, `<kind>/<slug>` when there isn't:

- `fix/142-null-deref-on-empty-cart`
- `feat/87-csv-export`
- `chore/bump-eslint`

Kinds: `feat fix chore docs refactor`. Pick the kind from the artifact, not the mood — a bug fix is `fix`, a new behavior is `feat`, a pure restructure is `refactor`.

## Strict worktree (default)

Read and explore the repo root freely; the gate is the first edit. The moment you would change a file, the branch goes in a worktree and the repo-root checkout stays on `main`, untouched. The always-on `worktree-only-edits` hook is the backstop: it denies any edit landing in the main checkout while it holds `main`.

Create the worktree under `.claude/worktrees/<slug>` on its branch; when the branch already exists — a resumed PR, or a claim that created the ref before the worktree (`pickup`) — check it out instead, fetching it first if it's only on the remote. `worktree create` performs whichever case applies and returns the worktree `path`.

## Branch-in-primary

The branch is checked out in the primary checkout, which becomes the work surface — so the `worktree-only-edits` hook permits edits there precisely because the checkout is off `main`. `worktree create --isolation branch` checks the branch out (creating it from `main`, or checking out an existing local/remote ref) and returns `path` as the repo root, so a caller keys off the returned `path` without knowing the stance.

With no separate directory to make collisions structurally impossible, `create` enforces a precondition in its place: the primary checkout must be **clean and on `main`**. A dirty tree or an already-checked-out feature branch halts with a `conflict` outcome rather than switching — the compare-and-swap a worktree gets for free, and what makes a second concurrent branch-mode `create` halt instead of colliding.

## Rebasing a branch onto a moved base

When the base advances under an open PR and the branch no longer replays cleanly, `worktree rebase` replays it onto `main` without squashing — so the commits stay individual deltas — and force-pushes with `--force-with-lease` (which refuses if the remote moved under you). On conflict it aborts and halts with the conflicting paths; resolving the replay is the rework path's job (`pickup`), not the command's. The rebase runs in whichever tree holds the branch — the worktree, or the primary checkout under branch-in-primary.

## Reaching main, then teardown

A branch reaches `main` one of two ways, neither editing a detached `main`:

- **Reviewed work** — everything `pickup` produces → a PR a human merges; `land` performs the merge.
- **A release** — `release` pushes its version bump and `v<new>` tag straight to `main` from its worktree. A release *marks* `main` rather than proposing a change to it, so it needs no PR — only the same isolation.

When the work lands, `worktree teardown` closes the lifecycle for the stance it ran under: strict worktree removes the worktree and deletes the branch; branch-in-primary returns the primary checkout to `main` and deletes the branch (halting on a dirty tree rather than stranding uncommitted work). `land` tears down after a merge, `release` after its push, and `land` adds the cleanup only a merged PR needs: deleting the remote branch and fast-forwarding local `main`.
