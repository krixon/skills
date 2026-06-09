---
name: pickup
description: Pick up a triaged issue and implement it — route by artifact kind (code → tdd/diagnose, skill → write-skill, docs → author vs WRITING.md, config → update-config), work on a branch, open a PR. Use when the user wants to start, grab, or implement a ready issue ("pick up #42", "work the next ready issue"). AFK (ready-for-agent) issues can run unattended; HITL (ready-for-human) issues are driven with the user.
argument-hint: "[issue # to pick up, or blank for the next ready issue]"
---

# Pickup

Take a triaged, ready issue and turn it into working code. `pickup` is the bridge from tracker to branch: read the agent brief as the contract, route to the right implementation skill, work on a branch, open a PR. It does not triage, design, or merge.

Issue mechanics route through [../ISSUES.md](../ISSUES.md), which selects the tracker binding; PR, branch, and review mechanics live in [../GITHUB.md](../GITHUB.md) — the concepts, commands, and label list.

## Process

### 1. Select the issue

- **By reference** — the user passes an issue number/URL. Fetch it.
- **Next ready** — no argument, take **rework before new work**:
  1. **Rework** — an open PR you own, by either check, in priority order:
     - **Changes requested or unresolved thread** (the rework and unresolved-thread queries — see [../GITHUB.md](../GITHUB.md)). The unresolved-thread half catches a review that carries only questions — a comment-only review never registers as changes requested, but its open thread still needs you. **Actionable when a thread is still unresolved, or — for a review with changes requested and no thread — when the review postdates HEAD.** A thread-less review you have pushed past is delivered and awaiting re-review; a threaded one stays actionable until you resolve each thread as you address it (step 5).
     - **Conflicting against the base** (the conflicting query — see [../GITHUB.md](../GITHUB.md)), evaluated **last**. The base moved and the branch no longer replays cleanly. **Always actionable** while it reports conflicting — no thread or timestamp to clear; the rebase-and-resolve flow (step 5) clears it. Judge it from a **current** mergeability check, not a stale one: a since-landed sibling PR can leave an earlier reading showing the branch clean when it now conflicts ([../GITHUB.md](../GITHUB.md) → *Find conflicting* carries how to get a settled reading).

     Resume the oldest actionable one via *Resuming a PR sent back for changes* (step 5).
  2. **New work** — only once **no** open owned PR is in rework, the conflicting check made against a current mergeability per the trigger above: a stale reading hides a PR that needs rebasing and sends you straight past it. Then query issues labelled `ready-for-agent` and not `in-progress`, then `ready-for-human` and not `in-progress`, oldest first.

  Confirm which you're taking unless running unattended.

**Skip anything blocked.** Read the issue's blocked by dependencies (see [../ISSUES.md](../ISSUES.md) → *Issue relations*). If any blocker is still open, the slice isn't grabbable — skip it and take the next. Skip `in-progress` issues too: already claimed by another run. Refuse anything in `needs-triage` / `needs-info` — not specified yet; send it back to `/triage`.

### 2. Gate on HITL / AFK

The readiness label is the autonomy contract:

- **`ready-for-agent` (AFK)** — fully specified, no human needed. Proceed. The brief *is* the approved plan, so it satisfies the planning gate that `tdd`/`diagnose` would otherwise seek from a human.
- **`ready-for-human` (HITL)** — carries a judgment step that can't be delegated (the brief says why: design decision, external access, manual testing). Surface it and drive the user through it. **Never clear an HITL gate unattended** — under `auto`, stop here and report; do not claim it.

### 3. Claim it

Claim by **creating the issue's branch ref first** — before the labels, before any code. The branch name is the deterministic one `pickup` derives per [../../ISOLATION.md](../../ISOLATION.md), and the create is the claim of record because it is atomic: creating a ref that already exists is rejected (see [../GITHUB.md](../GITHUB.md) → *Concurrency claims*), and that rejection *is* the coordination.

- **Ref created** → the claim is held. Only now set `in-progress` and self-assign — the human-visible signal per [../../CONCURRENCY.md](../../CONCURRENCY.md), bound in [../ISSUES.md](../ISSUES.md). The label and assignee follow the ref; they don't arbitrate.
- **Ref already exists** (the create is rejected) → a lost claim. **Yield silently** — skip this issue and take the next ready one (step 1). A lost claim is clean: no labels were touched, nothing to roll back, no thrash, no wall.

**Keep the `ready-for-agent`/`ready-for-human` label** once you've claimed: it's the durable autonomy decision, and a later rework round (a PR sent back for changes) reads it to know whether the rework is AFK-safe.

### 4. Load the brief

The contract is the **agent brief**: read the brief comment if the issue has one (triage-promoted issues), otherwise the issue body (sliced issues — `slice` writes the body in the brief shape). Either way it follows [../contracts/agent-brief.md](../contracts/agent-brief.md). Explore the codebase **fresh** — the brief is durable, so trust its interfaces and acceptance criteria over any stale paths. Use the project's established vocabulary and respect its recorded decisions in the area.

No brief and a thin body → wall (step 6). The issue isn't ready; return it to `/triage` to have one written.

### 5. Implement — in a worktree

Work in a worktree on its own branch — never the repo-root checkout (see [../../ISOLATION.md](../../ISOLATION.md)). The branch ref already exists — step 3 created it as the claim — so check it out rather than re-creating it (mechanic in [../../ISOLATION.md](../../ISOLATION.md)). Route by **artifact kind** — what the brief targets — then, for code, by category role. `tdd` and `diagnose` are *code* loops; non-code work routes elsewhere:

- **code · `bug`** → `diagnose` — build the feedback loop, fix, regression-test.
- **code · `enhancement`** → `tdd` — red→green per behavior in the brief's acceptance criteria.
- **skill** (a `SKILL.md` + bundled resources) → `write-skill` — structure and progressive disclosure are the rubric, not red-green.
- **docs/prose** (ADRs, READMEs, comments) → author directly against [../../WRITING.md](../../WRITING.md). No test loop.
- **config/harness** (`settings.json`, hooks, keybindings) → `update-config` / `keybindings-help`.

Infer the kind from the brief's target when it isn't stated. Drive the implementation skill with the brief: its acceptance criteria are the behaviors to satisfy, its interfaces are the seams.

**Delegation (window hygiene).** On the **AFK** path, run the implementation skill as a subagent; per the contract's standing terse-return rule it returns the smallest sufficient reference — the PR number/URL, not its diff — which keeps `pickup`'s window bounded across the loop. On the **HITL** path, delegate by *where* the judgment step sits, not by the label: front-loaded and end-of-run judgment delegate the mechanical implementation, continuous pairing stays inline (background its noisy output). [../DELEGATION.md](../DELEGATION.md) → `pickup` carries the three cases and why the cut falls there.

**Resuming a PR sent back for changes.** If you arrived here from a PR with review activity (step 1), don't start fresh: check out its existing branch, and read the review (see [../GITHUB.md](../GITHUB.md) → *Read the review*) as an **addendum** to the original brief — the brief's acceptance criteria still hold, the review is the delta.

**Resuming a conflicting PR (rebase).** Check out the branch in your worktree, rebase it onto the base without squashing (mechanic in [../../ISOLATION.md](../../ISOLATION.md) → *Rebasing a branch onto a moved base*), resolve **every** conflict the replay raises, and force-push. Comment naming the paths you resolved (per [../GITHUB.md](../GITHUB.md) → *Body formatting*), then stop — the force-push sends the PR back for re-review, the human gate that keeps the trigger AFK-safe. The issue stays `in-progress`.

If a conflict can't be resolved without a design call, don't wall to `needs-triage` (step 6) — the work is done, only the rebase is stuck. Leave the PR open and the issue `in-progress`, comment naming the unresolvable hunks, and report for a human.

**Classify each review comment by what an answer would produce.** A **change request** is satisfied by a diff — even when phrased as a question ("why are you swallowing this error?" wants it *fixed*). A **question** is aimed at you, the agent, and resolving it changes a shared *understanding*, not necessarily the code ("why this approach?", "did you consider Y?"). When a comment is genuinely both, treat it as a question first — the agreed answer may *then* spawn a change. When you can't tell, default to question: erring toward surfacing it to the maintainer is the safe direction.

- **Questions** → hand the whole set to `field` in `embedded` mode (its input *is* the questions; it returns the converged answers to you rather than prompting) and converge with the maintainer one at a time. Then **post each converged answer back to its review thread and resolve the thread** — the maintainer approves the draft before it posts (an outward write). Resolve the thread even when the answer produced no code change: an unresolved thread is what re-triggers the rework query (step 1), so resolving it is how a pure-question review closes out without an empty commit. **Confirm each reply posted before resolving its thread, and isolate the threads from one another** (the reply-then-resolve mechanic — see [../GITHUB.md](../GITHUB.md) → *Review threads*): resolve a thread only once its reply is confirmed landed, so a silently-failed reply never leaves a thread resolved-but-unanswered — that state vanishes from the rework query and the question is lost. Attempt every thread independently; one thread's reply or resolve failing must not abort the rest. Collect the failures and report them at the end of the round so it can be re-run against the threads that didn't post.
- **Change requests** → address them through the same implementation route as the original brief, *plus* any change an answer in the `field` pass spawned. **Resolve each change-request thread once its fix is pushed** — an unresolved thread keeps re-surfacing the PR in the rework query (step 1), so resolving it is what clears an addressed review; the maintainer re-opens on re-review if a fix falls short.

**Order: field first.** Run `field` and settle the questions before implementing change requests — a converged answer can reshape what a change should be. Then re-run the review gate (step 6) and push to the branch; the open PR updates in place — no new PR. A pure-question review with no resulting change skips straight to resolved threads — nothing to push.

**Autonomy.** Any question forces the whole rework round onto the HITL path, whatever the issue's label — `field` is interactive-only, and a change request can't be built on an unanswered question. Under `auto`, stop and stage: report the unresolved questions, implement nothing this pass. A change-request-only review keeps the issue's autonomy — AFK resumes unattended, HITL stops for the human.

### 6. Close the loop

**On success** — first clear the **review gate** before the PR, adapted to the artifact kind (mandatory on the AFK path, the user's choice on HITL). What TDD contributes is a gate that can fail before merge; that generalises:

- **code** → `/code-review` + `/security-review` as two parallel subagents, keeping only their findings lists.
- **skill / docs** → a writing-rubric review against [../../WRITING.md](../../WRITING.md) plus a structure/accuracy check (`write-skill`'s rubric for a skill). `/code-review` and `/security-review` don't apply to prose.
- **config** → `verify` — does the setting take effect / the hook fire.

Then open a PR carrying a closing reference to the issue (the `Closes` line — see [../GITHUB.md](../GITHUB.md) → *PRs and rework*) **as the bot, not your active account** ([../GITHUB.md](../GITHUB.md) → *PR identity*) — a maintainer-authored PR can't be self-approved. On a rework round, push to the existing branch instead (no new PR, your normal identity). Then hand to `verify` (run the app, confirm behavior). The issue stays `in-progress`; the open PR *is* the review state, and there's no review-state label to set. Leave the merge — and closing the issue — to a human. Do **not** merge or close the issue yourself; report what you built and where the PR is. A human requesting changes on the PR sends it back into this loop for another round (step 1).

**If you wall** — no test seam, ambiguous brief, broken build, or any blocker you can't clear — don't thrash. Move the issue to `needs-triage` (remove `in-progress` and the readiness label), **delete the branch ref you created at claim time**, and post an attempt report. This lands back at the human gate, the loop's circuit-breaker against infinite retry. Do **not** use `needs-info` (that's for reporter-info gaps).

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
