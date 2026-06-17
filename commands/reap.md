---
name: reap
description: Sweep workflow state for staleness and clean it up, one human-confirmed action at a time — abandoned claims, quiet needs-info issues, orphaned worktrees and branches, and epics whose children have all closed. Human-invoked only. Use when the maintainer wants to tidy up stale workflow state, reap abandoned claims, clear orphaned worktrees, says "reap" / "clean up the workflow" / "sweep for staleness", or notices a crashed run left an issue stuck in-progress.
argument-hint: "[threshold overrides, e.g. claim=48h needs-info=7d; blank uses the defaults]"
allowed-tools: Bash(*/bin/reap:*)
---

# Reap

Sweep the workflow's state machine for staleness and clean it up, one action at a time. A crashed `pickup` leaves its issue claimed forever; a `needs-info` issue never heard back sits open indefinitely; worktrees and branches orphaned by failed runs linger on disk; an epic whose children have all closed stays open. `reap` finds each, the human authorises each fix.

The mechanics live in the `bin/reap` command (ADR 0008): it sweeps the four staleness classes, re-reads each deciding signal at the moment it acts, releases, re-pings, tears down, and closes — in tested code. This wrapper names only that one binary — never a tracker call, a repository mutation, or another adapter — and carries the lone human decision: which stale items to reap.

`reap` is **human-invoked only**. It never runs from `auto`, `loop`, or `schedule`: every action mutates shared state another live session might own, and only a human can tell an abandoned claim from one a session is still holding. The same posture as `land`.

## Plan

Run `bin/reap plan` and render its candidates, grouped by class:

- `${CLAUDE_PLUGIN_ROOT}/bin/reap plan` — sweep with the default thresholds; append `--claim <dur>` / `--needs-info <dur>` (e.g. `48h`, `7d`) to override. An unrecognised duration leaves the default.

!`${CLAUDE_PLUGIN_ROOT}/bin/reap plan`

Read the JSON: `abandoned_claims` (number, title, who held it and since when), `quiet_needs_info` (number, title, how long quiet), `orphaned_worktrees` (path, branch, the PR state that makes it safe), and `stale_epics` (number, title, the sub-issue list evidencing every child is closed). Present each candidate as one numbered list, each line naming its proposed action and the evidence behind it, so the maintainer can recognise a claim they want to keep. If every class is empty, say there's nothing to reap and stop.

## Confirm and act, per item

**Nothing mutates without a confirmation for that item.** Walk the list and confirm each independently — the maintainer may accept some and decline others; skip a declined item, leaving its state untouched. On each confirmation, call the matching act, which re-reads the deciding signal before mutating and halts rather than reaping a claim taken since or an epic whose child reopened:

- **Abandoned claim** → `${CLAUDE_PLUGIN_ROOT}/bin/reap reap-claim --number <n>` (pass the same `--claim <dur>` used in the plan so the re-check applies the chosen threshold). It releases the claim and strips `in-progress`.
- **Quiet needs-info** → `${CLAUDE_PLUGIN_ROOT}/bin/reap reap-needs-info --number <n>` — default the maintainer's choice to a re-ping, offering close as the alternative. A re-ping passes the comment body out-of-band on stdin (`--body-file -`-style: pipe it in, never as an argument); `--action close` closes the issue instead.
- **Orphaned worktree/branch** → `${CLAUDE_PLUGIN_ROOT}/bin/reap reap-worktree --path <path> --branch <branch>`. It removes the worktree and deletes the branch.
- **Stale epic** → `${CLAUDE_PLUGIN_ROOT}/bin/reap reap-epic --number <n>`. It re-verifies every child is still closed and halts rather than closing if one reopened.

Render each act's result. One item's failure must not abort the rest — attempt each independently, collect the failures (a halt carries its reason), and report them.

## Report

The cleanup report: per class, the actions taken (with the item each touched), the items the maintainer declined, and any act that failed with its reason. The state is tidied; there is no artifact to chain onward.

## Handover

Hand off per [../skills/HANDOVER.md](../skills/HANDOVER.md) → *Autonomy*. End the run by rendering this row as one `AskUserQuestion`.

- **artifact:** the cleanup report — stale workflow state released, re-pinged, torn down, or closed at the maintainer's call
- **default:** — (terminal; the state is tidied)
- **alternatives:** `stop`

**Interactive-only** (see *Autonomy* in [../skills/HANDOVER.md](../skills/HANDOVER.md)) — each action mutates shared state another live session may own, and only a human can tell an abandoned claim from a held one, so `auto` never enters it.
