# Skills reference

A per-skill reference that sits between the [README's task table](../README.md#i-want-to) and each skill's full `SKILL.md`. The task table tells you which skill to run for a goal and where the chain leads; this page explains what each skill *is* — what it does, when to reach for it, and a concrete example. For the full mechanics of any skill, read its `skills/<name>/SKILL.md`. For the complete chain graph, see [skills/HANDOVER.md](../skills/HANDOVER.md).

Each entry names its default handover hop — the recommended next skill — on one line. The README and `HANDOVER.md` are canon for triggers and the full graph; this page links to them rather than restating them.

## Planning & specs

### discover

**What it does.** Grills you about a *problem*, one question at a time, before any solution is designed — the product phase upstream of `design`. It challenges that the problem is real, sharpens the user or segment it serves, weighs its value against the cost of inaction (and the build/buy/workaround alternatives), forces the non-goals, and defines the signal that says it's solved. It grounds against the project's product and project docs, not the code internals, and persists nothing — it ends by emitting a compact framing block in the conversation.

**When to reach for it.** You have a problem or idea and want to validate it's worth solving, and for whom, before committing to a design. The head of the planning chain: `discover → design → slice → pickup`.

**Example.** `/discover` — work through "is this a real problem, and who actually hits it?" until you have a framing block to hand to `design`.

**Chains to.** `design` — the framing block seeds the technical design and is passed as its input.

### design

**What it does.** Grills you about a plan or technical design, one decision branch at a time, until you both reach shared understanding. It challenges the plan against the project's existing domain model, sharpens loose terminology into the project's vocabulary, and offers an ADR when a load-bearing decision crystallises.

**When to reach for it.** You have a plan or design you want stress-tested before committing to it — somewhere the cost of a wrong assumption is high and you'd rather surface it now than in review.

**Example.** `/design` — then work through "should the cache invalidate on write or on read?" until the tradeoff is settled and recorded.

**Chains to.** `slice` — synthesise the resolved plan into agent-brief issues.

### field

**What it does.** Answers questions put *to* the agent. It forms a reasoned answer to each question, one at a time, and converges with you on a shared understanding. Where an agreed answer implies a code change, it returns the change deltas.

**When to reach for it.** You have questions you want the agent to resolve — most often the unresolved threads on a PR review — and you want each worked to a converged answer rather than answered off the cuff.

**Example.** `/field` the open questions on a PR review, agreeing each answer before it posts back to the thread.

**Chains to.** Terminal — the understanding lives in the conversation; nothing is published. (Reached from `pickup`'s rework path.)

### slice

**What it does.** Turns a plan, the current conversation, or an existing issue into tracked work: one agent-brief issue, or N tracer-bullet vertical slices under a lean epic. Each child issue is labelled `ready-for-agent` (AFK) or `ready-for-human` (HITL) by its type.

**When to reach for it.** You have a settled plan or a conversation that's ready to become tickets. Un-investigated audit observations go through `capture` instead.

**Example.** `/slice` a grilled plan into an epic with four independently-grabbable child issues.

**Chains to.** `pickup` — implement a ready issue.

## Issue tracking

### triage

**What it does.** Drives issues through a triage state machine by label, routing each to `ready-for-agent`, `ready-for-human`, `needs-info`, or `wontfix`. It's the human gate at the end of the findings chain — promotion to a `ready-*` label is the maintainer's call. Claims the issue it works (advisory assignee claim) and honors another session's claim, surfacing it in a separate "claimed / active elsewhere" bucket rather than offering it.

**When to reach for it.** You have incoming issues — bugs, feature requests, or `needs-triage` findings — to sort, or you want to prepare issues for an AFK agent to pick up.

**Example.** `/triage` the `needs-triage` queue, promoting the clear ones and asking for info on the rest.

**Chains to.** Terminal — the maintainer decides promotion; `pickup` is an alternative for an issue promoted to a `ready-*` label.

### capture

**What it does.** Turns audit findings or ad-hoc observations into `needs-triage` issues on the tracker, deduped against open issues and culled so the queue isn't flooded with noise. It never designs work — it files what was observed for a human to triage.

**When to reach for it.** An audit produced findings, or you've listed problems you want tracked. For designed work use `slice`; to promote the resulting issues use `triage`.

**Example.** `/capture` the findings from an `audit-security` run as deduped `needs-triage` issues.

**Chains to.** `triage` — promote them out of `needs-triage`.

## Audits

The nine `audit-*` skills are one method applied through nine risk lenses. Each is a static-first sweep — it reasons from the code, tests, and prose already in the tree, never requiring an instrumented run or a scanner (the shared method is in [skills/AUDIT-METHOD.md](../skills/AUDIT-METHOD.md)). Each maps risk through its lens, scores observations into findings carrying a severity and confidence, and hands them off identically: findings → `capture` → `needs-triage` → `triage`. None files issues itself.

They differ only by what they look for:

| Audit | Risk lens |
|---|---|
| `audit-coverage` | high-risk paths the test suite leaves unexercised |
| `audit-security` | exposure to attack — authz/access control, injection sinks, exposed secrets |
| `audit-docs` | prose that has drifted from the code — stale vocabulary, violated decisions, README/behavior claims the code no longer backs |
| `audit-error-handling` | dropped, masked, or ignored failures — swallowed errors, bare catch-alls, critical calls with no failure path |
| `audit-dead-code` | code that can never be reached or is never referenced — unreachable branches, never-called functions, orphaned modules |
| `audit-resource-leak` | resources acquired without a guaranteed release on every path — handles, connections, contexts, locks |
| `audit-debt` | in-code debt markers — `TODO`/`FIXME`/`HACK`/`XXX` and the project's own known shortcuts, clustered by area |
| `audit-observability` | critical paths running blind — money, auth, data mutation, or external calls with no log, metric, or trace at any layer |
| `audit-performance` | performance hazards on hot paths — N+1 data access, per-iteration allocation or IO in loops, unbounded reads, missing caching or indexing, blocking in async contexts |
| `audit-deps` | third-party dependency health from manifests and lockfiles — outdated majors on load-bearing deps, versions with known advisories, abandoned upstreams, license incompatibility or drift |

**Example.** `/audit-coverage src/billing` — sweep the billing module for untested high-risk paths and surface each as a finding.

**Chains to.** `capture` — dedup, cull, and file survivors as `needs-triage`.

### deepen

**What it does.** Finds architecture and refactoring opportunities in a codebase, grounded in the project's established domain language and recorded decisions. It surfaces candidates — places to consolidate tightly-coupled modules or make code more testable and AI-navigable — with an HTML report.

**When to reach for it.** You want to improve a codebase's structure rather than fix a defect, and you want the candidates ranked before committing to one.

**Example.** `/deepen` to surface refactoring candidates, then design the chosen one.

**Chains to.** `design` — design the chosen candidate, sharpening terminology and offering an ADR inline.

## Build & fix

### pickup

**What it does.** Claims a triaged issue and implements it, routing by artifact kind — code goes to `tdd` or `diagnose`, a skill to `write-skill`, docs to authoring, config to `update-config`. It works on a branch and opens a PR. AFK (`ready-for-agent`) issues run unattended; HITL (`ready-for-human`) issues are driven with you.

**When to reach for it.** A ready issue is on the tracker and you want it implemented.

**Example.** `/pickup #42` — or `/pickup` to grab the next ready issue.

**Chains to.** Terminal — a human reviews and merges the open PR.

### patch

**What it does.** Ships a small, obvious fix straight from the conversation with no tracked issue: a worktree branch through the review gate to a no-issue PR (body led by `No-issue:`) that a human lands. Human-invoked only.

**When to reach for it.** The fix is too small to be worth filing an issue — a typo, a doc correction, a one-line config tweak, a comment cleanup. For anything needing a decision use `design`; for work worth tracking use `slice`; for an issue already on the tracker use `pickup`.

**Example.** `/patch fix the typo in the install command in README.md`.

**Chains to.** Terminal — a human reviews and lands it via `land`, which tears down the worktree.

### tdd

**What it does.** Builds a feature or fixes a bug through the red-green-refactor loop, integration-test first: write a failing test, make it pass, refactor. The artifact is a tested feature on a branch at a green bar.

**When to reach for it.** You want test-first development for a feature or fix. Usually reached via `pickup`, but invokable directly.

**Example.** `/tdd add a per-user rate limit to the upload endpoint`.

**Chains to.** Terminal — open a PR for review.

### diagnose

**What it does.** A disciplined loop for hard bugs and performance regressions: reproduce, minimise, hypothesise, instrument, fix, regression-test. The artifact is a fix plus a regression test on a branch — or a documented missing-seam finding when the bug can't be reproduced.

**When to reach for it.** Something is broken, throwing, or failing, or a path got slower, and the cause isn't obvious. Usually reached via `pickup`, but invokable directly.

**Example.** `/diagnose the cart total is wrong when a discount applies`.

**Chains to.** Terminal — open a PR for review.

### land

**What it does.** Merges approved, bot-owned PRs that are ready to merge, strips each issue's `in-progress` label, then tears down the local worktree and branch. Human-invoked only.

**When to reach for it.** You've approved a PR and want it merged and the local state cleaned up.

**Example.** `/land` — or "land the approved PRs".

**Chains to.** Terminal — the work is merged and the trail is clean. After a merge it offers the project's release process, when the project's `CLAUDE.md` documents one.

### reap

**What it does.** Sweeps the workflow state machine for four classes of staleness and proposes a cleanup for each, mutating nothing without a per-item confirmation: claimed issues abandoned by a crashed run (no open PR, claim older than the threshold) → release the claim and strip `in-progress`; `needs-info` issues quiet past the threshold → re-ping or close; local worktrees and branches whose PR has merged or closed → tear down per the isolation contract; open epics whose sub-issues have all closed → close the epic. Thresholds (claim 24h, needs-info 14d) are overridable by argument. Human-invoked only, interactive-only — `auto` never enters it.

**When to reach for it.** A crashed `pickup` left an issue stuck `in-progress` and the drain keeps skipping it; orphaned worktrees are piling up; `needs-info` issues are going stale; or you just want to tidy the workflow's loose ends.

**Example.** `/reap` — or `/reap claim=48h needs-info=7d` to tighten the thresholds.

**Chains to.** Terminal — the state is tidied; there's no artifact to chain onward.

## Meta & session

### auto

**What it does.** Runs a skill workflow unattended, walking the handover chain from a starting skill and taking the recommended hop at each step without asking. It halts at the first human gate — an interactive-only skill or a `needs-triage`/`ready-for-human` label — and reports what it staged. It's the seam `/schedule` and `/loop` use for hands-off execution.

**When to reach for it.** You want a pipeline run head-down rather than stepped through one interactive hop at a time.

**Example.** `/auto audit-coverage` — sweep, capture findings, and halt at the `needs-triage` gate for a human to triage.

**Chains to.** Walks the default chain of whatever start skill it's given; stops and stages at the first gate.

### write-skill

**What it does.** Authors a new agent skill with the right structure — a concise `SKILL.md`, progressive disclosure into reference files when it would run long, and utility scripts for deterministic operations. It gathers requirements, drafts, and reviews the draft with you.

**When to reach for it.** You want to create a new skill and have it follow the library's conventions.

**Example.** `/write-skill` to scaffold a skill that audits API-endpoint naming conventions.

**Chains to.** Terminal — review the draft and iterate.

### zoom-out

**What it does.** Maps the relevant modules and callers one layer of abstraction up, in the project's established vocabulary, so you can see how a section of code fits the bigger picture. It runs as a forked `Explore` agent and returns a map.

**When to reach for it.** You don't know an area of code well and need orientation before diving in.

**Example.** `/zoom-out` while staring at a handler you've never seen, to get the surrounding module map.

**Chains to.** Terminal — returns a map to the conversation.

### handoff

**What it does.** Carries work across a session boundary in two modes detected from the session, not flagged. Write mode compacts the conversation into a handoff doc and persists it to a well-known per-project location (`.claude/handoffs/`, one timestamped doc per handoff, gitignored by default); it references existing artifacts (epics, plans, ADRs, issues, diffs) by path rather than duplicating them, and lists the skills the next agent should invoke. Resume mode — a fresh session with no prior context — discovers pending docs at that location, offers the latest (or lists all for a choice), loads the chosen one as working context, and marks it consumed so it's never re-offered.

**When to reach for it.** You're wrapping up a session and want continuity for whoever — or whatever — picks the work up next; or you're starting fresh and want to resume where the last session left off, without pasting a path.

**Example.** `/handoff continue wiring the rate-limiter into the upload path` (write); `/handoff` in a fresh session (resume).

**Chains to.** Terminal — interactive-only, so `auto` never enters it. Write hands to a future session; resume hands to the doc's suggested skills.

### caveman

**What it does.** An ultra-compressed output mode. It drops filler, articles, and pleasantries to cut token usage by roughly 75% while keeping full technical accuracy.

**When to reach for it.** You want terse output and are happy to trade prose for brevity.

**Example.** `/caveman` — or "talk like caveman" / "be brief".

**Persist across sessions.** Caveman's active marker is session-scoped, so it ends with the session. To start every session in caveman, add a `SessionStart` hook that arms it — in `.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "\"${CLAUDE_PROJECT_DIR}/skills/caveman/scripts/caveman-state.sh\" on" } ] }
    ]
  }
}
```

Each session re-arms its own marker; say "stop caveman" to drop it for the current session, or remove the hook to stop arming new ones.

**Chains to.** Terminal — a persistent output mode, not a workflow step.
