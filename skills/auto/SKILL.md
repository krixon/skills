---
name: auto
description: Run a skill workflow unattended — walk the handover chain taking the recommended hop at each step, without asking. Use when the user wants to run a pipeline head-down (e.g. "auto audit-coverage", "run the findings workflow autonomously", or from a schedule/loop). Stops and stages work at the first human gate.
argument-hint: "<start-skill or workflow name> [target/scope]"
---

# Auto

Run a workflow unattended. A workflow is a chain of skills linked by handovers (see [../HANDOVER.md](../HANDOVER.md)); `auto` walks that chain from a starting skill, **taking the recommended hop at each handover without asking**, until a stop condition halts it. Then it stops and reports what it staged.

`auto` is the seam that turns the interactive skill chain into an autonomous run. `/schedule` and `/loop` invoke it for hands-off execution.

## Invocation

`/auto <start> [target]`

- **start** — the skill to begin from, or a workflow alias. Aliases:
  - `findings` → start at `audit-coverage` (audit → file to `needs-triage`)
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
- **Delegate by interior cost, not by default.** `auto` carries no delegation rule of its own — it follows each skill's own delegation profile (see *Context & delegation* in [../WORKFLOWS.md](../WORKFLOWS.md)). A cheap hop (findings in → issues out) runs inline; a heavy interior (an audit over a large tree, a `tdd`/`diagnose` loop) delegates to a subagent so its reads and test/log output never land in the main window. Pass the prior artifact in; take the next artifact out. Delegating is for window hygiene, not visibility — nobody watching is no reason to isolate a hop whose interior is already small.
- **Stop-and-stage is the policy.** Only push through an internal gate when the skill declares it safe (and says why). When in doubt, stop and stage.
- **Stage, don't decide.** An autonomous run accretes reviewable artifacts (issues in `needs-triage`, a report, a branch) — it does not make irreversible or judgment calls a human would normally own.
- **Isolate when staging code.** A hop that produces commits (`pickup` and its implement loop) runs on its own branch in a worktree, never your live checkout — nobody's watching, so the run must not disturb the tree you'll return to. See [../../ISOLATION.md](../../ISOLATION.md).
- **Bounded.** Honour the `target` scope; don't widen it mid-run.

## Report

When the run halts, emit a summary:

- the chain walked (skill → skill → …) and where it stopped
- artifacts produced, with references (issue numbers, file paths, branch)
- **what's staged for a human**, and which skill to run next to pick it up

Example: `/auto findings src/billing` walks `audit-coverage` → `capture`, files the survivors as `needs-triage`, and stops — `capture`'s output sits at the `needs-triage` gate label and its default hop `triage` is interactive-only. The summary lists the filed issues and says `/triage` is the next human step.
