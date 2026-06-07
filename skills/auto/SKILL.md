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
- **Derive the next unit in a subagent; return only the decision.** The per-iteration rework scan is dense — it reads every open bot PR's review state — so run it in a subagent that returns one line: `rework #N kind=changes-requested|thread` for an actionable PR, `new #N` when none is actionable and an issue is ready, or `dry` when nothing is. The scan output never enters the main window; the loop acts on the decision alone. Use one `gh api graphql` over **all** open bot PRs for compact per-PR state — `{number, unresolvedCount, lastReviewAt, lastReviewState, headAt}` — narrowing server-side (`review:changes-requested`) before the thread check. Fetch review-thread *bodies* for the one PR being picked up only — that's `pickup`'s classify step (step 1), not the scan. The decision stays identical to `pickup`'s rule: rework before new; a threaded review actionable while any thread is unresolved; a thread-less `CHANGES_REQUESTED` actionable only when it postdates HEAD (`lastReviewAt > headAt`).
- **Don't pace between units.** While work remains, run the next `auto pickup` immediately — no wake-up between units.
- **Hold no state in the conversation.** The queue is durable in the tracker — owned PRs needing rework, plus `ready-for-agent` minus `in-progress`. Re-derive it each iteration rather than remembering it, so the drain stays correct across a long session the harness summarises or compacts.
- **Run one drain at a time.** `in-progress` locks *new* work — the next-ready query skips it — but a rework round runs on an already-`in-progress` issue, so the label can't claim it: two concurrent drains would race the same rework PR. Sequential iterations within one loop are safe; don't launch a second `/loop /auto pickup` on the same tracker.
- **Keep each iteration's footprint small.** The delegation contract's standing terse-return rule binds here ([../DELEGATION.md](../DELEGATION.md)): `pickup`'s AFK implementation hop returns the smallest sufficient reference — the PR number/URL, not its diff — and this loop narrates each unit in a line. That, with holding no state, is what bounds the window over a queue of any length.
- **Report context size every iteration.** Run [`scripts/report-ctx.sh`](scripts/report-ctx.sh) at every iteration boundary — including dry/derive-only polls that do no work — so window growth stays visible across the drain. A dry poll still grows the window — its tracker queries, and once the derive is delegated, the subagent's spawn and returned decision — so reporting only after work-doing iterations would hide real growth between them. It resolves the transcript by session id (not mtime) and prints the raw token sum; render it as `ctx: <round(n/1000)>K` (e.g. `156000` → `ctx: 156K`), or `ctx: ?K` when it prints nothing. Rising fast across iterations means state is leaking into the window despite delegation, so the window-hygiene bullets above — holding no state, the delegated derive, the small per-iteration footprint — are failing somewhere; investigate before continuing the drain.
- **Cap the window if a context cap is set.** Optional, off by default: when an env var holds a raw integer token count, halt the drain once the reported context reaches it; unset, the drain never halts on size (report-only, as above). Evaluate the cap at the iteration boundary, on the figure just reported, and **only after an iteration that did work** — a dry poll still reports its `ctx` (the bullet above) but never halts, since there's nothing in flight to halt. When `ctx >= cap`, stop scheduling further wake-ups and end the loop; don't skip one iteration and continue. The loop holds no conversational state and re-derives the queue from the tracker, so a fresh `/loop /auto pickup` resumes where it stopped at a clean window. Report the halt with the figure, the cap, the count still queued, and the restart, e.g. `ctx: 152K >= cap 150K, halting drain — N issues remain in the queue, restart with /loop /auto pickup in a fresh session`. This catches absolute exhaustion; the rate heuristic above catches an early leak — keep both.
- **When the queue is dry, poll with backoff.** Don't terminate on the first empty query — the queue refills as a human triages more. Schedule the next wake-up on a widening ladder: `60s → 5m → 15m → 30m → 1h`, then hold at 1h. Finding any ready issue resets the ladder — drain hard again, re-entering backoff only once dry. Each poll, dry or not, still reports its `ctx` at the boundary; only the cap-halt is work-gated (the two bullets above).
- **Give up after a day idle.** After 24 consecutive hourly (ceiling) polls find nothing, stop scheduling and end the loop; re-launch to resume. Tunable.

## Report

When the run halts, emit a summary:

- the chain walked (skill → skill → …) and where it stopped
- artifacts produced, with references (issue numbers, file paths, branch)
- **what's staged for a human**, and which skill to run next to pick it up

Example: `/auto audit-coverage src/billing` walks `audit-coverage` → `capture`, files the survivors as `needs-triage`, and stops — `capture`'s output sits at the `needs-triage` gate label and its default hop `triage` is interactive-only. The summary lists the filed issues and says `/triage` is the next human step.
