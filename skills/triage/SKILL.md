---
name: triage
description: Triage issues through a state machine driven by triage roles. Use when user wants to create an issue, triage issues, review incoming bugs or feature requests, prepare issues for an AFK agent, or manage issue workflow.
argument-hint: "[issue # or what to triage]"
---

# Triage

Move issues through a small state machine of triage labels, using the `gh` CLI ([../GITHUB.md](../GITHUB.md)).

## Reference docs

- [../contracts/agent-brief.md](../contracts/agent-brief.md) — how to write durable agent briefs

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

Every triaged issue carries exactly one category label and one state label. If state labels conflict, flag it and ask the maintainer before doing anything else.

State transitions: an unlabeled issue normally goes to `needs-triage` first; from there it moves to `needs-info`, `ready-for-agent`, `ready-for-human`, or `wontfix`. `needs-info` returns to `needs-triage` once the reporter replies. `pickup` then drives the execution tail: `ready-for-*` → `in-progress` (claim) → open PR (the review state, no label) → closed (human merge); a human requesting changes on the PR sends it back to `pickup` for another round on the same branch. A walled `pickup` returns `in-progress` → `needs-triage` with an attempt report — the failure circuit-breaker, landing the issue back at the human gate rather than retrying forever. The maintainer can override at any time — flag transitions that look unusual and ask before proceeding.

## Invocation

The maintainer invokes `/triage` and describes what they want in natural language. Interpret the request and act. Examples:

- "Show me anything that needs my attention"
- "Let's look at #42"
- "Move #42 to ready-for-agent"
- "What's ready for agents to pick up?"

## Show what needs attention

Query open issues (`gh issue list`) and present three buckets, oldest first:

1. **Unlabeled** — never triaged.
2. **`needs-triage`** — evaluation in progress.
3. **`needs-info` with reporter activity since the last triage notes** — needs re-evaluation.

Show counts and a one-line summary per issue. Let the maintainer pick.

## Triage a specific issue

1. **Gather context.** Read the full issue (body, comments, labels, reporter, dates). Parse any prior triage notes — or a `pickup` attempt report, if the issue returned here walled — so you don't re-ask resolved questions and you address the recorded blocker. Explore the codebase using the project's established vocabulary, respecting recorded decisions in the area. Query prior rejections (`gh issue list --label wontfix --state closed`, see [../GITHUB.md](../GITHUB.md)) and surface any whose close comment resembles this issue.

2. **Recommend.** Tell the maintainer your category and state recommendation with reasoning, plus a brief codebase summary relevant to the issue. Wait for direction.

3. **Reproduce (bugs only).** Before any grilling, attempt reproduction: read the reporter's steps, trace the relevant code, run tests or commands. Report what happened — successful repro with code path, failed repro, or insufficient detail (a strong `needs-info` signal). A confirmed repro makes a stronger agent brief.

4. **Grill (if needed).** If the issue needs fleshing out, run a `/grill` session.

5. **Apply the outcome:**
   - `ready-for-agent` — post an agent brief comment ([../contracts/agent-brief.md](../contracts/agent-brief.md)).
   - `ready-for-human` — same structure as an agent brief, but note why it can't be delegated (judgment calls, external access, design decisions, manual testing).
   - `needs-info` — post triage notes (template below).
   - `wontfix` (bug) — polite explanation, then close.
   - `wontfix` (enhancement) — add the `wontfix` label, then close with the reason in the close comment (`gh issue close <n> --comment "..."`). The label plus the reason on the closed issue *is* the rejection record — a later triage finds it via `gh issue list --label wontfix --state closed`. If a closed `wontfix` issue already covers this request, link to it from the comment rather than re-deciding.
   - `needs-triage` — apply the role. Optional comment if there's partial progress.

## Quick state override

If the maintainer says "move #42 to ready-for-agent", trust them and apply the role directly. Confirm what you're about to do (role changes, comment, close), then act. Skip grilling. If moving to `ready-for-agent` without a grilling session, ask whether they want to write an agent brief.

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

- **artifact:** triaged issues (one category + one state label)
- **default:** — (terminal; promotion to `ready-for-*` is the maintainer's call)
- **alternatives:** `pickup`, for an issue promoted to `ready-for-agent`/`ready-for-human` · stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — `triage`'s state decisions need human judgment; `auto` never enters it.
