---
name: auto
description: Run a skill workflow unattended — walk the handover chain taking the recommended hop at each step, without asking. Use when the user wants to run a pipeline head-down (e.g. "auto audit-coverage", "run an audit chain autonomously", or from a schedule/loop). Stops and stages work at the first human gate.
argument-hint: "<start-skill> [target/scope]"
---

# Auto

Run a workflow unattended. A workflow is a chain of skills linked by handovers (see [../HANDOVER.md](../HANDOVER.md)); `auto` walks that chain from a starting skill, **taking the recommended hop at each handover without asking**, until a stop condition halts it. Then it stops and reports what it staged.

`auto` is the seam that turns the interactive skill chain into an autonomous run. `/schedule` and `/loop` invoke it for hands-off execution.

## Invocation

`/auto <start> [target]`

- **start** — the skill to begin from. Name it directly: `audit-coverage`, `audit-security`, `audit-docs`, or any other chain head. Run one audit per invocation; to sweep several, invoke `auto` once per audit.
- **target** — scope passed to the start skill (a path, area, or left blank for the whole codebase).

Issues and PRs live in GitHub via `gh` ([../GITHUB.md](../GITHUB.md)); the labels are fixed.

## How it walks the chain

`auto` has exactly **two stop conditions** (defined once in *Autonomy* in [../HANDOVER.md](../HANDOVER.md)):

1. **Interactive-only skill** — a skill that contains a human loop: `grill`, `deepen`, `triage`, `slice`, `field`, `release`, `land`. `auto` never enters one.
2. **Gate label** — an artifact sitting at `needs-triage` or `ready-for-human`. `auto` never acts on one; it leaves the work staged there.

The walk, for each skill in turn:

1. **Run it** unattended, resolving its internal gates by the unattended defaults declared in its own body (stop-and-stage when none is safe — see Rules).
2. **Look at its default hop.** Continue into the next skill (invoke it via the Skill tool) *unless* a stop condition holds — the default skill is interactive-only, or the artifact now sits at a gate label. On either, **halt and report** what's staged. A terminal default (`—`) ends the walk the same way.

Refuse before starting if **start** itself is interactive-only, or if the start target already sits at a gate label (e.g. `/auto pickup` on a `ready-for-human` issue) — there's nothing to run unattended. Say so and name the human step: run the interactive skill yourself, or `/triage` the gated issue.

## Rules

- **No questions.** Never call `AskUserQuestion`. The chain advances by taking each default hop; a skill's internal gates are cleared by its declared unattended default or not at all.
- **Delegate by interior cost, not by default.** `auto` carries no delegation rule of its own — it follows each skill's own delegation profile (see [../DELEGATION.md](../DELEGATION.md)). A cheap hop (findings in → issues out) runs inline; a heavy interior (an audit over a large tree, a `tdd`/`diagnose` loop) delegates to a subagent so its reads and test/log output never land in the main window. Pass the prior artifact in; take the next artifact out. Delegating is for window hygiene, not visibility — nobody watching is no reason to isolate a hop whose interior is already small.
- **Stop-and-stage is the policy.** Only push through an internal gate when the skill declares it safe (and says why). When in doubt, stop and stage.
- **Stage, don't decide.** An autonomous run accretes reviewable artifacts (issues in `needs-triage`, a report, a branch) — it does not make irreversible or judgment calls a human would normally own.
- **Isolate every editing hop.** A hop that changes files (`pickup` and its implement loop) runs in a worktree on its own branch, never the repo-root checkout — the single invariant, no different unattended (see [../../ISOLATION.md](../../ISOLATION.md)). Nobody's watching, so the run must not disturb the tree you'll return to.
- **Bounded.** Honour the `target` scope; don't widen it mid-run.

## Draining the ready queue (`/loop /auto pickup`)

Wrapping `auto pickup` in a dynamic-mode `/loop` (no interval) drains the whole ready queue in one unattended run — each loop iteration runs `auto pickup`, which takes the next unit of work and opens or updates a PR. Its pacing and context discipline:

- **Let `pickup` choose; don't hand it an issue number.** Its step 1 takes **rework before new work** — an owned PR sent back for changes or with an unresolved thread first, then the oldest `ready-for-agent` issue not `in-progress`. Deriving the queue in the loop and passing a number bypasses that scan: rework PRs sit on `in-progress` issues, which a `ready-for-agent` minus `in-progress` query excludes, so feedback rounds get skipped. Re-invoke bare `auto pickup` each iteration.
- **Don't pace between units.** While work remains, run the next `auto pickup` immediately — no wake-up between units.
- **Hold no state in the conversation.** The queue is durable in the tracker — owned PRs needing rework, plus `ready-for-agent` minus `in-progress`. Re-derive it each iteration rather than remembering it, so the drain stays correct across a long session the harness summarises or compacts.
- **Run one drain at a time.** `in-progress` locks *new* work — the next-ready query skips it — but a rework round runs on an already-`in-progress` issue, so the label can't claim it: two concurrent drains would race the same rework PR. Sequential iterations within one loop are safe; don't launch a second `/loop /auto pickup` on the same tracker.
- **Keep each iteration's footprint small.** `pickup` delegates its implementation to a subagent on the AFK path (see [../DELEGATION.md](../DELEGATION.md)); only the PR reference returns to the loop. That, with holding no state, is what bounds the window over a queue of any length.
- **When the queue is dry, poll with backoff.** Don't terminate on the first empty query — the queue refills as a human triages more. Schedule the next wake-up on a widening ladder: `60s → 5m → 15m → 30m → 1h`, then hold at 1h. Finding any ready issue resets the ladder — drain hard again, re-entering backoff only once dry.
- **Give up after a day idle.** After 24 consecutive hourly (ceiling) polls find nothing, stop scheduling and end the loop; re-launch to resume. Tunable.

## Report

When the run halts, emit a summary:

- the chain walked (skill → skill → …) and where it stopped
- artifacts produced, with references (issue numbers, file paths, branch)
- **what's staged for a human**, and which skill to run next to pick it up

Example: `/auto audit-coverage src/billing` walks `audit-coverage` → `capture`, files the survivors as `needs-triage`, and stops — `capture`'s output sits at the `needs-triage` gate label and its default hop `triage` is interactive-only. The summary lists the filed issues and says `/triage` is the next human step.
