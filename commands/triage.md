---
name: triage
description: Triage issues through a state machine driven by triage roles. Use when user wants to create an issue, triage issues, review incoming bugs or feature requests, prepare issues for an AFK agent, or manage issue workflow.
argument-hint: "[issue # or what to triage]"
allowed-tools: Bash(*/bin/triage:*)
---

# Triage

Move issues through a small state machine of triage labels — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix` — promoting a brief on the way to a `ready-*` state. The human gate at the end of the findings chain: promotion to a `ready-*` label is the maintainer's call.

`triage` is a **command that launches an agent** (ADR 0008): the deterministic surface — present the queue and a candidate, take/release the advisory claim, apply the state-machine label transitions, promote a brief — lives in the `bin/triage` command; the one step that needs a model is reached separately. This wrapper names only that binary — never a tracker call or a git mutation.

**The present→synthesis→act boundary** (copying the [`capture`](capture.md) reference). The label transitions are deterministic — strip the old state, add the new, reconcile category and priority, file the body — so they live in `bin/triage transition` / `reject`, not behind the agent. The genuine synthesis sits *between* present and act: evaluating the issue, deciding which transition it takes, and drafting the brief or the notes the transition carries. **In-session the host agent does it directly**; **under `auto` a spawned subagent does it** (per ADR 0008's spawn model — never a headless `claude -p`). triage is **interactive-only** ([../skills/HANDOVER.md](../skills/HANDOVER.md)): its state decisions need a human, so `auto` never enters it of its own accord.

The five maintainer-owned state labels, the two category labels (`bug` / `enhancement`), and the priority labels (`priority:high` / `priority:low`, at most one, set only on the maintainer's call) are the full vocabulary — the list and its ownership are in [../skills/GITHUB.md](../skills/GITHUB.md). `in-progress` is `pickup`'s, never triage's; a transition never touches it. Every triaged issue ends with one category label and one maintainer-owned state label; two maintainer-owned states at once, or two priorities, is a conflict — flag it and ask before acting.

## 1. Present the queue or the candidate

The maintainer invokes `/triage` and describes what they want in natural language ("show me what needs attention", "let's look at #42", "move #42 to ready-for-agent"). Interpret the request, then read the relevant surface:

- `${CLAUDE_PLUGIN_ROOT}/bin/triage present` — the actionable queue, bucketed (never-triaged, `needs-triage`, `needs-info`), with a separate **claimed / active elsewhere** bucket for any issue another session holds (the holders and since-when ride each row). A claimed issue is held aside even when it otherwise qualifies — honouring the claim is what stops two sessions triaging to divergent decisions ([../skills/CONCURRENCY.md](../skills/CONCURRENCY.md)). Render the actionable buckets oldest-first for the maintainer to pick from; show the claimed bucket as context, not as work.
- `${CLAUDE_PLUGIN_ROOT}/bin/triage present --id <n>` — one candidate's full context (body, comments, labels) plus its current claim holder and since-when, so you evaluate and the maintainer sees who holds it before a claim is taken.

A `needs-info` issue is surfaced whether or not the reporter has replied — deciding whether reporter activity since the last notes warrants re-evaluation is your judgment over the candidate's comments, not a filter the queue applies.

## 2. Claim, then evaluate (the synthesis)

Before working an issue, take the advisory claim:

- `${CLAUDE_PLUGIN_ROOT}/bin/triage claim --id <n>` — takes the assignee claim, **halting** if the issue is already held (it surfaces the holders and since-when) so the maintainer decides: proceed anyway, reap the stale claim, or pick other work. The binary never resolves "me", so your own existing claim reads as held too — pass `--force` to proceed in every authorised case (your own claim, or a deliberate take-over). With `--force` the claim is taken regardless; re-claiming an issue you already hold is a safe no-op.

Then do the model work present can't: read the full issue, parse any prior triage notes or a walled `pickup` attempt report (so you don't re-ask resolved questions and you address the recorded blocker), reproduce a bug where you can, explore the codebase in the project's established vocabulary, and check prior rejections (closed `wontfix` issues whose close reason resembles this one). Recommend a category and state with reasoning, and wait for the maintainer's direction. If the issue needs fleshing out, run a `/design` session. **In-session you do this directly; under `auto` a subagent does it and returns the decided transition and the drafted brief/notes for the loop to apply.**

## 3. Apply the decided transition

Pass exactly the transition the maintainer confirmed to `bin/triage`. The brief, notes, or rejection reason rides **out-of-band** — write it to a file and redirect it on stdin, never interpolated into the command string ([../SECURITY.md](../SECURITY.md)):

- **Promote** to a `ready-*` state — the body is the agent brief ([../skills/contracts/agent-brief.md](../skills/contracts/agent-brief.md)): `${CLAUDE_PLUGIN_ROOT}/bin/triage transition --id <n> --state ready-for-agent --category <bug|enhancement> [--priority priority:high|priority:low] < <brief.md>`. Use `ready-for-human` when the work can't be delegated (judgment calls, external access, design decisions, manual testing) — same brief shape, noting why. Leave priority unset (the default middle tier) unless the maintainer calls for one.
- **Defer** for more information: `${CLAUDE_PLUGIN_ROOT}/bin/triage transition --id <n> --state needs-info < <notes.md>` — the body is the triage notes (capture everything resolved during grilling under "established so far" so the work isn't lost; questions specific and actionable). Template below.
- **Reject**: `${CLAUDE_PLUGIN_ROOT}/bin/triage reject --id <n> --category <bug|enhancement> < <reason.md>` — applies `wontfix` and closes with the reason. The label plus the reason on the closed issue *is* the rejection record; a later triage finds it by querying closed `wontfix` issues. If a closed `wontfix` issue already covers this request, link to it in the reason rather than re-deciding.

Each transition strips the old maintainer-owned state, adds the new, reconciles the category and priority, and files the body as a comment — it reports the exact label diff. The brief and notes are *your* synthesis; the binary only files them.

For a quick override ("move #42 to ready-for-agent"), trust the maintainer and apply the transition directly — claim first, skip grilling, and ask whether they want a brief written before promoting without one.

## 4. Release the claim

On a clean exit — the issue left in a resting state another session could resume — drop the claim so it stops reading as held:

- `${CLAUDE_PLUGIN_ROOT}/bin/triage release --id <n>` — covers a claim you took over by reaping as much as one you opened with. A `reject` closes the issue, which *is* a clean exit; release with it.

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

## Handover

Per [../skills/HANDOVER.md](../skills/HANDOVER.md), `triage` is the human gate at the end of the findings chain. End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** triaged issues
- **default:** — (terminal; promotion to `ready-*` is the maintainer's call)
- **alternatives:** `pickup`, for an issue promoted to `ready-for-agent`/`ready-for-human` · stop

**Interactive-only** (per [../skills/HANDOVER.md](../skills/HANDOVER.md)) — `triage`'s state decisions need human judgment; `auto` never enters it.
