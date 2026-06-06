---
name: pickup
description: Pick up a triaged issue and implement it — route by artifact kind (code → tdd/diagnose, skill → write-skill, docs → author vs WRITING.md, config → update-config), work on a branch, open a PR. Use when the user wants to start, grab, or implement a ready issue ("pick up #42", "work the next ready issue"). AFK (ready-for-agent) issues can run unattended; HITL (ready-for-human) issues are driven with the user.
argument-hint: "[issue # to pick up, or blank for the next ready issue]"
---

# Pickup

Take a triaged, ready issue and turn it into working code. `pickup` is the bridge from tracker to branch: read the agent brief as the contract, route to the right implementation skill, work on a branch, open a PR. It does not triage, design, or merge.

Issues and PRs live in GitHub; use the `gh` CLI ([../GITHUB.md](../GITHUB.md) for commands and the label list).

## Process

### 1. Select the issue

- **By reference** — the user passes an issue number/URL. Fetch it.
- **Next ready** — no argument, take **rework before new work**:
  1. **Rework** — an open PR you own with changes requested *or any unresolved review thread* (`gh pr list … CHANGES_REQUESTED`, plus the unresolved-thread query, see [../GITHUB.md](../GITHUB.md)). The unresolved-thread half catches a review that carries only questions — a `COMMENT`-state review never sets `CHANGES_REQUESTED`, but its open thread still needs you. Resume the oldest via *Resuming a PR sent back for changes* (step 5).
  2. **New work** — otherwise query issues labelled `ready-for-agent` and not `in-progress`, then `ready-for-human` and not `in-progress`, oldest first.

  Confirm which you're taking unless running unattended.

**Skip anything blocked.** Read the issue's native dependencies — `gh api repos/{owner}/{repo}/issues/<n>/dependencies/blocked_by` ([../GITHUB.md](../GITHUB.md) → *Issue relations*). If any blocker is still open, the slice isn't grabbable — skip it and take the next. Skip `in-progress` issues too: already claimed by another run. Refuse anything in `needs-triage` / `needs-info` — not specified yet; send it back to `/triage`.

### 2. Gate on HITL / AFK

The readiness label is the autonomy contract:

- **`ready-for-agent` (AFK)** — fully specified, no human needed. Proceed. The brief *is* the approved plan, so it satisfies the planning gate that `tdd`/`diagnose` would otherwise seek from a human.
- **`ready-for-human` (HITL)** — carries a judgment step that can't be delegated (the brief says why: design decision, external access, manual testing). Surface it and drive the user through it. **Never clear an HITL gate unattended** — under `auto`, stop here and report; do not claim it.

### 3. Claim it

Add `in-progress` before touching code, so the loop and any parallel agents don't re-grab in-flight work — this is `pickup`'s claim (the "next ready" query excludes anything already `in-progress`). **Keep the `ready-for-agent`/`ready-for-human` label**: it's the durable autonomy decision, and a later rework round (a PR sent back for changes) reads it to know whether the rework is AFK-safe.

### 4. Load the brief

The contract is the **agent brief**: read the brief comment if the issue has one (triage-promoted issues), otherwise the issue body (sliced issues — `slice` writes the body in the brief shape). Either way it follows [../contracts/agent-brief.md](../contracts/agent-brief.md). Explore the codebase **fresh** — the brief is durable, so trust its interfaces and acceptance criteria over any stale paths. Consult the project's domain vocabulary and recorded decisions in the area (per [../CONVENTIONS.md](../CONVENTIONS.md)).

No brief and a thin body → wall (step 6). The issue isn't ready; return it to `/triage` to have one written.

### 5. Implement — in a worktree

Work in a worktree on its own branch — never the repo-root checkout (see [../../ISOLATION.md](../../ISOLATION.md)). Route by **artifact kind** — what the brief targets — then, for code, by category role. `tdd` and `diagnose` are *code* loops; non-code work routes elsewhere:

- **code · `bug`** → `diagnose` — build the feedback loop, fix, regression-test.
- **code · `enhancement`** → `tdd` — red→green per behavior in the brief's acceptance criteria.
- **skill** (a `SKILL.md` + bundled resources) → `write-skill` — structure and progressive disclosure are the rubric, not red-green.
- **docs/prose** (`CONTEXT.md`, ADRs, READMEs, comments) → author directly against [../../WRITING.md](../../WRITING.md). No test loop.
- **config/harness** (`settings.json`, hooks, keybindings) → `update-config` / `keybindings-help`.

Infer the kind from the brief's target when it isn't stated. Drive the implementation skill with the brief: its acceptance criteria are the behaviors to satisfy, its interfaces are the seams.

**Delegation (window hygiene — see [../DELEGATION.md](../DELEGATION.md)).** On the **AFK** path, run the implementation skill as a subagent and keep only its result; nobody's watching, and this keeps `pickup`'s window bounded across the whole loop. On the **HITL** path, run it inline so you can drive it, and background its noisy test/log output rather than letting it accumulate.

**Resuming a PR sent back for changes.** If you arrived here from a PR with review activity (step 1), don't start fresh: check out its existing branch, and read the review (`gh pr view <n> --comments`) as an **addendum** to the original brief — the brief's acceptance criteria still hold, the review is the delta.

**Classify each review comment by what an answer would produce.** A **change request** is satisfied by a diff — even when phrased as a question ("why are you swallowing this error?" wants it *fixed*). A **question** is aimed at you, the agent, and resolving it changes a shared *understanding*, not necessarily the code ("why this approach?", "did you consider Y?"). When a comment is genuinely both, treat it as a question first — the agreed answer may *then* spawn a change. When you can't tell, default to question: erring toward surfacing it to the maintainer is the safe direction.

- **Questions** → hand the whole set to `field` in `embedded` mode (its input *is* the questions; it returns the converged answers to you rather than prompting) and converge with the maintainer one at a time. Then **post each converged answer back to its review thread and resolve the thread** — the maintainer approves the draft before it posts (an outward write). Resolve the thread even when the answer produced no code change: an unresolved thread is what re-triggers the rework query (step 1), so resolving it is how a pure-question review closes out without an empty commit.
- **Change requests** → address them through the same implementation route as the original brief, *plus* any change an answer in the `field` pass spawned.

**Order: field first.** Run `field` and settle the questions before implementing change requests — a converged answer can reshape what a change should be. Then re-run the review gate (step 6) and push to the branch; the open PR updates in place — no new PR. A pure-question review with no resulting change skips straight to resolved threads — nothing to push.

**Autonomy.** Any question forces the whole rework round onto the HITL path, whatever the issue's label — `field` is interactive-only, and a change request can't be built on an unanswered question. Under `auto`, stop and stage: report the unresolved questions, implement nothing this pass. A change-request-only review keeps the issue's autonomy — AFK resumes unattended, HITL stops for the human.

### 6. Close the loop

**On success** — first clear the **review gate** before the PR, adapted to the artifact kind (mandatory on the AFK path, the user's choice on HITL). What TDD contributes is a gate that can fail before merge; that generalises:

- **code** → `/code-review` + `/security-review` as two parallel subagents, keeping only their findings lists.
- **skill / docs** → a writing-rubric review against [../../WRITING.md](../../WRITING.md) plus a structure/accuracy check (`write-skill`'s rubric for a skill). `/code-review` and `/security-review` don't apply to prose.
- **config** → `verify` — does the setting take effect / the hook fire.

Then open a PR referencing the issue (`Closes #N`) — or, on a rework round, push to the existing PR's branch — and hand to `verify` (run the app, confirm behavior). The issue stays `in-progress`; the open PR *is* the review state, and there's no review-state label to set. Leave the merge — and closing the issue — to a human. Do **not** merge or close the issue yourself; report what you built and where the PR is. A human requesting changes on the PR sends it back into this loop for another round (step 1).

**If you wall** — no test seam, ambiguous brief, broken build, or any blocker you can't clear — don't thrash. Move the issue to `needs-triage` (remove `in-progress` and the readiness label) and post an attempt report. This lands back at the human gate, the loop's circuit-breaker against infinite retry. Do **not** use `needs-info` (that's for reporter-info gaps).

<attempt-report-template>

## Attempt Report

**Outcome:** walled — needs maintainer input
**What I tried:** the approach taken and how far it got
**Where it walled:** the specific blocker (missing test seam, ambiguous acceptance criterion, build failure, …)
**To unblock:** what a human needs to decide, add, or clarify

</attempt-report-template>

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** an open PR (issue at `in-progress`), or a walled issue returned to `needs-triage` with an attempt report
- **default:** — (terminal; a human reviews and merges)
- **alternatives:** `verify` · `/code-review` · stop
