---
name: auto
description: Run a skill workflow unattended — walk the handover chain taking the recommended hop at each step, without asking. Use when the user wants to run a pipeline head-down (e.g. "auto cover", "run the findings workflow autonomously", or from a schedule/loop). Stops and stages work at the first human gate.
argument-hint: "<start-skill or workflow name> [target/scope]"
---

# Auto

Run a workflow unattended. A workflow is a chain of skills linked by handovers (see [../HANDOVER.md](../HANDOVER.md)); `auto` walks that chain from a starting skill, **taking the recommended hop at each handover without asking**, until it reaches a skill it can't clear unattended. Then it stops and reports what it staged.

`auto` is the seam that turns the interactive skill chain into an autonomous run. `/schedule` and `/loop` invoke it for hands-off execution.

## Invocation

`/auto <start> [target]`

- **start** — the skill to begin from, or a workflow alias. Aliases:
  - `findings` → start at `cover` (audit → file to `needs-triage`)
- **target** — scope passed to the start skill (a path, area, or left blank for the whole codebase).

If the tracker/label setup the chain needs isn't present, stop and say to run `/setup-skills` — don't guess.

## How it walks the chain

For each skill, read its `## Handover` block and act on the `auto` directive:

1. **advance** — run the skill unattended, applying any internal-gate defaults it declares. Then take its **default** hop and continue into the next skill (invoke it via the Skill tool).
2. **stage** — run the skill unattended (with its declared defaults), then **stop**. Its artifact is the hand-back point; the default hop is left for a human.
3. **never** — do **not** enter it. If you arrive here by following a default hop, halt before running it and stage what the previous skill produced.

Refuse immediately if **start** itself is a `never` skill (e.g. `deepen`, `grill`) — those contain a human loop and can't run unattended. Say so and suggest running them interactively.

## Rules

- **No questions.** Never call `AskUserQuestion`. Handover gates are cleared by taking the default; internal gates are cleared by the skill's declared unattended default or not at all.
- **Delegate every hop.** Run each skill as a subagent and keep only its handover artifact in the main session — the window then scales with the number of artifacts, not the work to produce them (see *Context & delegation* in [../WORKFLOWS.md](../WORKFLOWS.md)). Pass the prior artifact in; take the next artifact out. No visibility cost — nobody watches a live `auto` run.
- **Stop-and-stage is the policy.** Only push through an internal gate when the skill declares it safe (and says why). When in doubt, stop and stage.
- **Stage, don't decide.** An autonomous run accretes reviewable artifacts (issues in `needs-triage`, a report, a branch) — it does not make irreversible or judgment calls a human would normally own.
- **Isolate when staging code.** A hop that produces commits (`pickup` and its implement loop) runs on its own branch in a worktree, never your live checkout — nobody's watching, so the run must not disturb the tree you'll return to. See [../../ISOLATION.md](../../ISOLATION.md).
- **Bounded.** Honour the `target` scope; don't widen it mid-run.

## Report

When the run halts, emit a summary:

- the chain walked (skill → skill → …) and where it stopped
- artifacts produced, with references (issue numbers, file paths, branch)
- **what's staged for a human**, and which skill to run next to pick it up

Example: `/auto findings src/billing` walks `cover` → `capture`, files the survivors as `needs-triage`, and stops (because `capture` is `stage` and `triage` is `never`). The summary lists the filed issues and says `/triage` is the next human step.
