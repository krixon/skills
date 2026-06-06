# Isolation

How work is isolated from the default branch and from your live checkout. Branches keep commits off `main`; worktrees keep work out of the primary working tree when its single slot is already taken. The work-producing skills (`pickup`, `tdd`, `diagnose`, `write-skill`) and the `auto` loop follow this; it's the same `branch → gate → PR → human merge` invariant stated once.

## The default branch is protected

Never commit to the default branch (`main` / `master`). Branch before the first commit. Reading, exploring, and editing the working tree are fine — the gate is the *commit*, not the edit. Override only on an explicit instruction to work on or commit to `main` ("commit straight to main", "no branch"). Approval to commit to `main` once does not carry to the next task.

## A branch is the unit of work

One branch per issue or task. Name it `<kind>/<issue>-<slug>` when there's a tracker issue, `<kind>/<slug>` when there isn't:

- `fix/142-null-deref-on-empty-cart`
- `feat/87-csv-export`
- `chore/bump-eslint`

Kinds: `feat fix chore docs refactor`. Pick the kind from the artifact, not the mood — a bug fix is `fix`, a new behavior is `feat`, a pure restructure is `refactor`.

## Branch vs worktree

The **primary working tree** holds at most one active branch. That is the one-occupant invariant: the single permitted occupant is the solo, sequential branch a human `git switch -c` into and keeps in the live tree for visibility. Every task started while that slot is taken is isolated in its own worktree.

A worktree is not a substitute for branching — it's a branch *plus* its own directory. Worktree work still lands on its own named branch and still goes through the gate to a PR.

### Occupied

The primary tree is **occupied** iff it is *not* (clean working tree *and* on the default branch). Two distinct things occupy it, and either is enough:

- **Uncommitted changes on any branch — including the default.** A dirty tree is occupied even on `main`. There is no exploratory-write exemption: need to write, isolate.
- **Any non-default branch checked out, even when clean.** A clean feature-branch checkout still counts — the tree may be mid-read and about to be edited, and that branch is the one occupant.

Free is the complement: clean *and* on the default branch. Only then is the primary tree available to take.

### Detection

Before starting any committable work, test the **primary working tree** — the original clone, the top entry of `git worktree list` (linked worktrees live under `.git/worktrees`). It is free iff both hold:

```
git -C <primary> status --porcelain     # empty
git -C <primary> branch --show-current   # equals the default branch
```

Resolve the default branch dynamically — `git symbolic-ref refs/remotes/origin/HEAD` — never hardcode `main`.

- **Free** → take the primary tree: `git switch -c <branch>`. The solo occupant, in the live tree, where you can watch it.
- **Occupied** → create a worktree. The work runs isolated and never disturbs the occupant.

Unattended callers (`auto`, an AFK `pickup`) skip the check and always worktree — nobody is watching the primary tree to take it deliberately.

### Worktree location

Create worktrees at `.claude/worktrees/<branch-slug>`, not an arbitrary path. Creation and teardown agree on this location so a landed branch's worktree can be found and removed. The harness also supports `isolation: "worktree"` on a spawned agent and the `worktree.bgIsolation` setting for background tasks.
