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
  1. **Rework** — an open PR you own with changes requested (`gh pr list … CHANGES_REQUESTED`, see [../GITHUB.md](../GITHUB.md)). Resume the oldest via *Resuming a PR sent back for changes* (step 5).
  2. **New work** — otherwise query issues labelled `ready-for-agent` and not `in-progress`, then `ready-for-human` and not `in-progress`, oldest first.

  Confirm which you're taking unless running unattended.

**Skip anything blocked.** If the brief/body's "Blocked by" section names issues that aren't closed, the slice isn't grabbable — skip it and take the next. Skip `in-progress` issues too: already claimed by another run. Refuse anything in `needs-triage` / `needs-info` — not specified yet; send it back to `/triage`.

### 2. Gate on HITL / AFK

The readiness label is the autonomy contract:

- **`ready-for-agent` (AFK)** — fully specified, no human needed. Proceed. The brief *is* the approved plan, so it satisfies the planning gate that `tdd`/`diagnose` would otherwise seek from a human.
- **`ready-for-human` (HITL)** — carries a judgment step that can't be delegated (the brief says why: design decision, external access, manual testing). Surface it and drive the user through it. **Never clear an HITL gate unattended** — under `auto`, stop here and report; do not claim it.

### 3. Claim it

Add `in-progress` before touching code, so the loop and any parallel agents don't re-grab in-flight work — this is `pickup`'s claim (the "next ready" query excludes anything already `in-progress`). **Keep the `ready-for-agent`/`ready-for-human` label**: it's the durable autonomy decision, and a later rework round (a PR sent back for changes) reads it to know whether the rework is AFK-safe.

### 4. Load the brief

The contract is the **agent brief**: read the brief comment if the issue has one (triage-promoted issues), otherwise the issue body (sliced issues — `slice` writes the body in the brief shape). Either way it follows [../triage/AGENT-BRIEF.md](../triage/AGENT-BRIEF.md). Explore the codebase **fresh** — the brief is durable, so trust its interfaces and acceptance criteria over any stale paths. Use `CONTEXT.md` vocabulary and respect ADRs in the area.

No brief and a thin body → wall (step 6). The issue isn't ready; return it to `/triage` to have one written.

### 5. Implement — branch first

Branch first; never commit to the default branch (see [../../ISOLATION.md](../../ISOLATION.md) — and isolate in a worktree when this `pickup` runs unattended or alongside other work). Route by **artifact kind** — what the brief targets — then, for code, by category role. `tdd` and `diagnose` are *code* loops; non-code work routes elsewhere:

- **code · `bug`** → `diagnose` — build the feedback loop, fix, regression-test.
- **code · `enhancement`** → `tdd` — red→green per behavior in the brief's acceptance criteria.
- **skill** (a `SKILL.md` + bundled resources) → `write-skill` — structure and progressive disclosure are the rubric, not red-green.
- **docs/prose** (`CONTEXT.md`, ADRs, READMEs, comments) → author directly against [../../WRITING.md](../../WRITING.md). No test loop.
- **config/harness** (`settings.json`, hooks, keybindings) → `update-config` / `keybindings-help`.

Infer the kind from the brief's target when it isn't stated. Drive the implementation skill with the brief: its acceptance criteria are the behaviors to satisfy, its interfaces are the seams.

**Delegation (window hygiene — see *Context & delegation* in [../WORKFLOWS.md](../WORKFLOWS.md)).** On the **AFK** path, run the implementation skill as a subagent and keep only its result; nobody's watching, and this keeps `pickup`'s window bounded across the whole loop. On the **HITL** path, run it inline so you can drive it, and background its noisy test/log output rather than letting it accumulate.

**Resuming a PR sent back for changes.** If you arrived here from a changes-requested PR (step 1), don't start fresh: check out its existing branch, and read the PR review comments (`gh pr view <n> --comments`) as an **addendum** to the original brief — the brief's acceptance criteria still hold, the review comments are the delta. Address them through the same implementation route, then re-run the review gate (step 6) and push to the branch; the open PR updates in place — no new PR. Autonomy is the issue's `ready-for-agent`/`ready-for-human` label: under `auto`, only AFK issues resume unattended — HITL rework stops for the human (see the handover).

### 6. Close the loop

**On success** — first clear the **review gate** before the PR, adapted to the artifact kind (mandatory on the AFK path, the user's choice on HITL — see [../WORKFLOWS.md](../WORKFLOWS.md)). What TDD contributes is a gate that can fail before merge; that generalises:

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
- **auto:** conditional on the issue's readiness label — `ready-for-agent` (AFK) → **stage** (claim, implement on a branch, open a PR, stop for review; never merge — and on a wall, return to `needs-triage` and stop). Covers **rework**: a later `auto` run resumes an AFK issue whose PR has changes requested, addresses the review, and stops again at the PR. `ready-for-human` (HITL) → **never**.
