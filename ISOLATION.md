# Isolation

How work is isolated from the default branch and from your live checkout. Branches keep commits off `main`; worktrees keep concurrent work out of your working tree. The work-producing skills (`pickup`, `tdd`, `diagnose`, `write-skill`) and the `auto` loop follow this; it's the same `branch → gate → PR → human merge` invariant stated once.

## The default branch is protected

Never commit to the default branch (`main` / `master`). Branch before the first commit. Reading, exploring, and editing the working tree are fine — the gate is the *commit*, not the edit. Override only on an explicit instruction to work on or commit to `main` ("commit straight to main", "no branch"). Approval to commit to `main` once does not carry to the next task.

The one standing carve-out is **`release`**: it commits the version bump (`chore(release): v<new>`) and its annotated `v<new>` tag directly to `main`, because a release *marks* `main` rather than proposing a change to it. The carve-out is narrow and guarded — `release` aborts to a release PR if `main` is dirty or the push is rejected, never forcing (see [skills/release/SKILL.md](skills/release/SKILL.md)). No other skill commits to `main`.

## A branch is the unit of work

One branch per issue or task. Name it `<kind>/<issue>-<slug>` when there's a tracker issue, `<kind>/<slug>` when there isn't:

- `fix/142-null-deref-on-empty-cart`
- `feat/87-csv-export`
- `chore/bump-eslint`

Kinds: `feat fix chore docs refactor`. Pick the kind from the artifact, not the mood — a bug fix is `fix`, a new behavior is `feat`, a pure restructure is `refactor`.

## Branch vs worktree

A branch and a worktree solve different problems. Default to a branch; reach for a worktree only when work runs **concurrently**.

- **Sequential, interactive, you're watching** → a branch in the main working tree. Simplest; switch with `git switch -c`.
- **Concurrent or background / AFK** — parallel issues, an `auto` run, a scheduled or looped agent, anything you shouldn't have to babysit in your live checkout → a **git worktree**, so the work never disturbs the tree you're sitting in. The harness supports this directly: `isolation: "worktree"` on a spawned agent, and the `worktree.bgIsolation` setting for background tasks.

A worktree is not a substitute for branching — it's a branch *plus* its own directory. Concurrent work still lands on its own named branch inside the worktree, and still goes through the gate to a PR.
