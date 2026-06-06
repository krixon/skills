---
name: spec
description: Turn the current conversation context into a tracker artifact sized to the change — a lean agent-brief for a single-slice change (routing to `pickup`) or a full PRD for a multi-slice change (routing to `slice`). Use when the user wants to spec work out from the current context.
argument-hint: "[optional focus for the spec]"
---

Produce a tracker artifact from the current conversation context and codebase understanding, sized to the change. Do NOT interview the user — synthesize what you already know.

Issues live in GitHub; use the `gh` CLI ([../GITHUB.md](../GITHUB.md) for commands and the label list).

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout, and respect any ADRs in the area you're touching.

2. **Assess decomposability.** Decide whether the change is one vertical slice or many. A single vertical slice cuts end-to-end through every layer (schema, API, UI, tests) as one grabbable piece; if the work naturally breaks into several such slices with dependencies between them, it's multi-slice. Branch on this — the lean path below for one slice, the full PRD for many.

### Single slice → lean agent-brief

Emit the shared agent brief from [../contracts/agent-brief.md](../contracts/agent-brief.md) verbatim as the issue body. A lean single-slice issue has no parent and no blockers, so there are no relations to record. Run **no seam check**: `pickup`/`tdd` pick seams downstream, exactly as they do for a slice.

Apply the AFK/HITL label decision in [../contracts/agent-brief.md](../contracts/agent-brief.md).

Create the issue (`gh issue create`) with that label. Write its prose per [../../WRITING.md](../../WRITING.md) → *Issues & findings*: lead with the problem, plainly, no hedging where you know.

### Multiple slices → full PRD

Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. Check with the user that these seams match their expectations.

Write the PRD using the template below, then create the issue (`gh issue create`). The parent PRD carries the **category label only** (`enhancement` / `bug`) and **no readiness label** — it isn't actionable as-is; `slice` produces the actionable children, each with its own `ready-for-agent`/`ready-for-human` label. Write its prose per [../../WRITING.md](../../WRITING.md) → *Docs*: task-first, declarative, no marketing tone.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They go stale fast.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`, picking the default for the shape you produced.

- **artifact:** a lean agent-brief issue (single slice) or a full PRD issue (multiple slices)
- **default:** conditional on shape — lean agent-brief → `pickup` (implement the ready issue); full PRD → `slice` (cut the PRD into tracer-bullet issues)
- **alternatives:** lean path → `slice` · stop; full path → stop
- **auto:** stage for both shapes — synthesise the artifact and stop. On the multi-slice path the seam check is a human gate; unattended, record the seams you chose and flag them unconfirmed rather than proceeding to `slice`.
