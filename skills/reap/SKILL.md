---
name: reap
description: Sweep workflow state for staleness and propose cleanup, one human-confirmed action at a time — abandoned claims, quiet needs-info issues, orphaned worktrees and branches, and epics whose children have all closed. Human-invoked only. Use when the maintainer wants to tidy up stale workflow state, reap abandoned claims, clear orphaned worktrees, says "reap" / "clean up the workflow" / "sweep for staleness", or notices a crashed run left an issue stuck in-progress.
argument-hint: "[threshold overrides, e.g. claim=48h needs-info=7d; blank uses the defaults]"
---

# Reap

Sweep the workflow's state machine for staleness and propose cleanup, one action at a time. A crashed `pickup` leaves its issue claimed forever; the unattended drain skips it on every pass ([../CONCURRENCY.md](../CONCURRENCY.md): the claim never expires on its own, and clearing it is a human's call, never a timer's). A `needs-info` issue never heard back sits open indefinitely. Worktrees and branches orphaned by failed runs linger on disk. An epic whose children have all closed stays open. `reap` is the hand a human lends to those — it finds the staleness, the human authorises each fix.

`reap` is **human-invoked only**. It never runs from `auto`, `loop`, or `schedule`: every action it proposes mutates shared state another live session might own, and only a human can tell an abandoned claim from one a session is still holding (the trade in [../CONCURRENCY.md](../CONCURRENCY.md) — never yank work from under a live session). It is **interactive-only** (per [../HANDOVER.md](../HANDOVER.md) → *Autonomy*) for that reason: it proposes, the human confirms each action, nothing mutates unconfirmed. Same posture as `land`.

Issues, PRs, and their relations live in GitHub; [../GITHUB.md](../GITHUB.md) is the binding for every read and write below. The teardown of a worktree and branch follows [../../ISOLATION.md](../../ISOLATION.md).

## Thresholds

Two classes age out on a clock. Both defaults are overridable by the skill argument (`claim=48h`, `needs-info=7d`); an unrecognised key or an absent argument leaves the default.

- **Abandoned claim** — `claim`, default **24h**, measured from the claim timestamp the tracker records.
- **Quiet needs-info** — `needs-info`, default **14d**, measured from the issue's last activity.

The worktree and epic classes carry no clock — they age on a state change (a PR merged/closed, an epic's last child closed), not on elapsed time.

## Process

### 1. Sweep the four classes

Read-only. Gather every candidate before proposing anything, so the human sees the whole picture in one pass.

- **Abandoned claims** — issues carrying `in-progress` (see [../GITHUB.md](../GITHUB.md) → *Concurrency claims* for the assignee and claim-timestamp reads). A claim is a **candidate** when it has **no open PR** referencing the issue **and** its claim timestamp is older than the `claim` threshold. An issue with an open PR is in review, not abandoned — never a candidate. Skip ones claimed inside the threshold: a live session may hold them.
- **Quiet needs-info** — open issues labelled `needs-info` (see [../GITHUB.md](../GITHUB.md) → *Issues*) whose last activity predates the `needs-info` threshold.
- **Orphaned worktrees and branches** — local worktrees and branches (`git worktree list`, `git branch`) whose PR has **merged or closed**, or whose branch has no PR and no longer exists on the remote. Match a worktree's branch to its PR by the branch name `pickup` derives ([../../ISOLATION.md](../../ISOLATION.md)); read PR state per [../GITHUB.md](../GITHUB.md) → *PRs and rework*. A worktree whose PR is still open is live work — never a candidate.
- **Stale epics** — open epics (see [../GITHUB.md](../GITHUB.md) → *Labels*) every one of whose sub-issues is now closed (read the children per [../GITHUB.md](../GITHUB.md) → *Issue relations*; an epic with no children, or any open child, is not a candidate).

### 2. Present the proposals

Render every candidate as one numbered list, grouped by class, each line naming the proposed action:

- **Abandoned claim** → release the claim and strip `in-progress` (remove the assignee and the label — [../GITHUB.md](../GITHUB.md) → *Concurrency claims*, *Issues*). State who held it and since when, so the human can recognise a claim they want to keep.
- **Quiet needs-info** → the human's choice of a re-ping comment or a close (offer both; default to the re-ping). Name how long it's been quiet.
- **Orphaned worktree/branch** → tear it down per [../../ISOLATION.md](../../ISOLATION.md) (`git worktree remove`, then `git branch -D`). Name the PR's state (merged/closed) that makes it safe.
- **Stale epic** → close the epic ([../GITHUB.md](../GITHUB.md) → *Issues*). Show the sub-issue list you checked (number and state of each) — the evidence every child is closed.

If no class turns up a candidate, say so and stop — there's nothing to reap.

### 3. Confirm and act, per item

**Nothing mutates without a confirmation for that item.** Walk the list and confirm each action independently — the human may accept some and decline others. Skip a declined item, leaving its state untouched. Re-read the deciding signal immediately before each mutation (the claim timestamp, the PR state, the children) — the sweep in step 1 may have gone stale while the human decided, and a claim taken since, or a PR reopened, must not be reaped. One item's mutation failing must not abort the rest: attempt each independently, collect failures, report them.

### 4. Report

The cleanup report: per class, the actions taken (with the item each touched), the items the human declined, and any mutation that failed with its reason. Nothing to hand to — the state is tidied. There is no artifact to chain onward.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** the cleanup report — stale workflow state released, re-pinged, torn down, or closed at the maintainer's call
- **default:** — (terminal; the state is tidied)
- **alternatives:** `stop`

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md) → *Autonomy*) — each action mutates shared state another live session may own, and only a human can tell an abandoned claim from a held one, so `auto` must never enter it.
