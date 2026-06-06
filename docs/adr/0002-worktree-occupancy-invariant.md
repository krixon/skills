# 0002 — Worktree isolation keys on primary-tree occupancy

## Status

Accepted

## Context

Work is kept off the default branch and off the live checkout by branches and worktrees. The decision of *which* — a branch in the primary working tree, or an isolated worktree — needs a single, testable criterion the work-producing skills (`pickup`, `tdd`, `diagnose`, `write-skill`) and the `auto` loop can all apply identically.

Keying the choice on whether work runs *concurrently* is not testable from the tree: a skill can't see what other agents intend, and "concurrent" is a judgment, not a state. It also left an exploratory-write grey area — edits made "just to look around" on the live tree had no clear home.

## Decision

The decision criterion is **occupancy of the primary working tree**, not concurrency.

The primary working tree holds at most one active branch — the **one-occupant invariant**. It is **occupied** iff it is *not* (clean working tree *and* on the default branch). Two distinct conditions occupy it, either sufficient:

- uncommitted changes on *any* branch, including the default — there is no exploratory-write exemption;
- *any* non-default branch checked out, *even when clean* — a clean feature-branch checkout still counts, because the tree may be mid-read and about to be edited.

While occupied, every newly-started task is worktree-isolated. Detection runs before any committable work: the primary tree is free iff `git -C <primary> status --porcelain` is empty and `git -C <primary> branch --show-current` equals the default branch, with the default resolved via `git symbolic-ref refs/remotes/origin/HEAD` rather than hardcoded. Free means take the primary tree (`git switch -c`); occupied means create a worktree. Unattended callers (`auto`, an AFK `pickup`) skip the check and always worktree.

Worktrees are created at `.claude/worktrees/<branch-slug>`; creation and teardown agree on this location so a landed branch's worktree can be found and removed. The mechanics live in one place — `ISOLATION.md` → *Branch vs worktree* — and the consuming skills reference it.

## Considered options

- **A — one deliberate occupant (chosen).** The single permitted occupant is the solo, sequential branch a human switches into and keeps in the primary tree for visibility. Worktrees are the necessary evil reserved for work started while that slot is taken.
- **B — primary tree always clean-on-default, all writing in worktrees.** Maximal isolation: the live tree never carries work; every task gets a worktree.

A was chosen over B because solo single-file work wants the visibility of the live tree — watching a small change happen in the checkout you're sitting in is worth keeping one occupant, and B's blanket isolation pays a worktree's overhead even when nobody else is competing for the tree.

## Consequences

The branch-vs-worktree choice is now a mechanical predicate any skill can evaluate against the primary tree's state, not a judgment about concurrency. The exploratory-write grey area is closed: a dirty default-branch tree is occupied, so the next task isolates.

The contract tightens — a *clean* non-default checkout counts as occupied even though nothing is written yet. This isolates a task that a concurrency rule would have allowed onto the live tree, the deliberate price of treating the one occupant as the tree's reserved slot.

Existing checkouts are not migrated or enforced; the invariant governs newly-started work, and no tooling programmatically enforces occupancy.
