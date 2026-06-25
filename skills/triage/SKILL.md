---
name: triage
description: Triage issues through a state machine driven by triage roles. Use when user wants to create an issue, triage issues, review incoming bugs or feature requests, prepare issues for an AFK agent, or manage issue workflow.
argument-hint: "[issue # or what to triage]"
---

# Triage

Move issues through a small state machine of triage labels. [../GITHUB.md](../GITHUB.md) is the binding — concepts, commands, and the label list.

## Reference docs

- [../contracts/agent-brief.md](../contracts/agent-brief.md) — how to write durable agent briefs
- [../CONCURRENCY.md](../CONCURRENCY.md) — how concurrent sessions coordinate; `triage` is a selection-and-hold site, so it takes the advisory assignee claim

## Labels

Two **category** labels:

- `bug` — something is broken
- `enhancement` — new feature or improvement

Six **state** labels. The maintainer owns the first five; `pickup` owns the execution tail (`in-progress`) — see [../pickup/SKILL.md](../pickup/SKILL.md). Full list in [../GITHUB.md](../GITHUB.md).

- `needs-triage` — maintainer needs to evaluate
- `needs-info` — waiting on reporter for more information
- `ready-for-agent` — fully specified, ready for an AFK agent
- `ready-for-human` — needs human implementation
- `wontfix` — will not be actioned
- `in-progress` — claimed by `pickup`, implementation underway

There is no review-state label: a claimed issue with an open PR *is* in review.

Every triaged issue ends with one category label and one of the five maintainer-owned state labels. A `ready-for-*` label alongside `in-progress` is a claimed issue, not a conflict. Two maintainer-owned state labels at once *is* a conflict: flag it and ask the maintainer before doing anything else.

A `ready-for-*` issue may also carry a **priority** label (`priority:high` / `priority:low`) that tips `pickup`'s new-work order within its state pool — see [../GITHUB.md](../GITHUB.md) → *Labels*. The default is **unlabelled** (the middle tier); add one only on the maintainer's call. **At most one** per issue — both at once is a conflict, the priority analogue of the exactly-one state rule: flag it and ask before proceeding.

State transitions: an unlabeled issue normally goes to `needs-triage` first; from there it moves to `needs-info`, `ready-for-agent`, `ready-for-human`, or `wontfix`. `needs-info` returns to `needs-triage` once the reporter replies. A walled `pickup` also returns an issue to `needs-triage`, with an attempt report — the circuit-breaker that lands it back at the human gate rather than retrying forever. The maintainer can override at any time — flag transitions that look unusual and ask before proceeding.

## Invocation

The maintainer invokes `/triage` and describes what they want in natural language. Interpret the request and act. Examples:

- "Show me anything that needs my attention"
- "Let's look at #42"
- "Move #42 to ready-for-agent"
- "What's ready for agents to pick up?"

## Show what needs attention

Query open issues (see [../GITHUB.md](../GITHUB.md) → *Issues*), reading each issue's assignees (see [../GITHUB.md](../GITHUB.md) → *Concurrency claims*), and present the actionable buckets, oldest first:

1. **Unlabeled** — never triaged.
2. **`needs-triage`** — evaluation in progress.
3. **`needs-info` with reporter activity since the last triage notes** — needs re-evaluation.

A **claimed** issue — one assigned to another session — is **never** offered in these actionable buckets, even when it otherwise qualifies: honoring the claim is what stops two sessions triaging the same issue to divergent decisions (see [../CONCURRENCY.md](../CONCURRENCY.md) → *Selection sites vs commit sites*). Surface claimed issues in a separate **claimed / active elsewhere** bucket — visible so the maintainer sees in-flight triage across sessions, but not actionable here. Show counts and a one-line summary per issue; for the claimed bucket, add who holds each and since when. Let the maintainer pick from the actionable buckets.

## Triage a specific issue

1. **Claim the issue.** Before working it, take the advisory assignee claim (see [../CONCURRENCY.md](../CONCURRENCY.md) → *The assignee claim*, bound to GitHub in [../GITHUB.md](../GITHUB.md) → *Concurrency claims*) — self-assign so a parallel session sees the issue is held and skips it. If it's **already claimed by another session**, don't grab it: surface who holds it and since when, then let the maintainer choose — proceed anyway (they accept the collision), reap the stale claim (clear it and take over — a human's call, since nothing auto-reaps), or pick other work. Your own existing claim is not a collision; just continue.

2. **Gather context.** Read the full issue (body, comments, labels, reporter, dates). Parse any prior triage notes — or a `pickup` attempt report, if the issue returned here walled — so you don't re-ask resolved questions and you address the recorded blocker. Explore the codebase using the project's established vocabulary, respecting recorded decisions in the area. Query prior rejections (closed issues labelled `wontfix` — see [../GITHUB.md](../GITHUB.md) → *Issues*) and surface any whose close comment resembles this issue.

3. **Recommend.** Tell the maintainer your category and state recommendation with reasoning, plus a brief codebase summary relevant to the issue. Wait for direction.

4. **Reproduce (bugs only).** Before any grilling, attempt reproduction: read the reporter's steps, trace the relevant code, run tests or commands. Report what happened — successful repro with code path, failed repro, or insufficient detail (a strong `needs-info` signal). A confirmed repro makes a stronger agent brief.

5. **Grill (if needed).** If the issue needs fleshing out, run a `/design` session.

6. **Apply the outcome:**
   - `ready-for-agent` — post an agent brief comment ([../contracts/agent-brief.md](../contracts/agent-brief.md)). Leave it at the default unlabelled priority unless the maintainer calls for `priority:high` / `priority:low` (above).
   - `ready-for-human` — same structure as an agent brief, but note why it can't be delegated (judgment calls, external access, design decisions, manual testing). Same priority default as `ready-for-agent`.
   - `needs-info` — post triage notes (template below).
   - `wontfix` (bug) — polite explanation, then close.
   - `wontfix` (enhancement) — add the `wontfix` label, then close with the reason in the close comment (see [../GITHUB.md](../GITHUB.md) → *Issues*). The label plus the reason on the closed issue *is* the rejection record — a later triage finds it by querying closed issues labelled `wontfix`. If a closed `wontfix` issue already covers this request, link to it from the comment rather than re-deciding.
   - `needs-triage` — apply the role. Optional comment if there's partial progress.

7. **Release the claim.** On clean exit — the issue left in a resting state another session could resume — unassign yourself (see [../GITHUB.md](../GITHUB.md) → *Concurrency claims*), so the issue stops reading as held. This covers a claim you took over by reaping just as much as one you opened the session with: either way it's yours until you exit. Closing a `wontfix` issue is a clean exit — release with it.

## Quick state override

If the maintainer says "move #42 to ready-for-agent", trust them and apply the role directly — claim it first and release on exit, same as a full triage. Confirm what you're about to do (role changes, comment, close), then act. Skip grilling. If moving to `ready-for-agent` without a grilling session, ask whether they want to write an agent brief.

## Needs-info template

<triage-notes-template>

## Triage Notes

**What we've established so far:**

- point 1
- point 2

**What we still need from you (@reporter):**

- question 1
- question 2

</triage-notes-template>

Capture everything resolved during grilling under "established so far" so the work isn't lost. Questions must be specific and actionable, not "please provide more info".

## Resuming a previous session

If prior triage notes exist on the issue, read them, check whether the reporter has answered any outstanding questions, and present an updated picture before continuing. Don't re-ask resolved questions.

## Handover

Per [../HANDOVER.md](../HANDOVER.md), `triage` is the human gate at the end of the findings chain. End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** triaged issues
- **default:** — (terminal; promotion to `ready-for-*` is the maintainer's call)
- **alternatives:** `pickup`, for an issue promoted to `ready-for-agent`/`ready-for-human` · stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — `triage`'s state decisions need human judgment; `auto` never enters it.
