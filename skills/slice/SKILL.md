---
name: slice
description: Break a plan, spec, or PRD into independently-grabbable issues on the tracker via tracer-bullet vertical slices. Use when user wants to convert a plan into issues, create implementation tickets, or break work down. Un-investigated audit observations go through `capture` instead.
argument-hint: "[plan, spec, or PRD to slice]"
---

# Slice

Break a plan into independently-grabbable issues using vertical slices (tracer bullets).

The issue tracker and triage label vocabulary should have been provided to you — run `/setup-skills` if not.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes an issue reference (issue number, URL, or path) as an argument, fetch it from the issue tracker and read its full body and comments.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the state of the code. Issue titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

### 3. Draft vertical slices

Break the plan into **tracer bullet** issues. Each issue is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

Slices may be 'HITL' or 'AFK'. HITL slices require human interaction, such as an architectural decision or a design review. AFK slices can be implemented and merged without human interaction. Prefer AFK over HITL where possible.

- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Blocked by**: which other slices (if any) must complete first
- **User stories covered**: which user stories this addresses (if the source material has them)

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?
- Are the correct slices marked as HITL and AFK?

Iterate until the user approves the breakdown.

### 5. Publish the issues to the issue tracker

For each approved slice, publish a new issue to the issue tracker. Use the issue body template below. Label by type: **AFK** slices → `ready-for-agent`; **HITL** slices → `ready-for-human` (they carry a judgment step an agent can't clear). For an HITL slice, note in the issue *why* a human is needed, so `pickup` can drive them through it.

Publish issues in dependency order (blockers first) so you can reference real issue identifiers in the "Blocked by" field.

Write each issue body as an **agent brief** so `pickup` reads it origin-blind — same shape it gets from a triage-promoted issue. Follow the brief in [../triage/AGENT-BRIEF.md](../triage/AGENT-BRIEF.md) (behavioral, durable, no file paths), wrapped with slice-specific Parent and Blocked-by sections:

<issue-template>
## Parent

A reference to the parent issue on the issue tracker (omit if the source wasn't an existing issue).

## Agent Brief

**Category:** bug / enhancement
**Summary:** one-line description of the slice
**Current behavior:** the status quo this slice builds on
**Desired behavior:** the end-to-end behavior the slice delivers — describe the vertical path, not layer-by-layer implementation
**Key interfaces:** types / signatures / config shapes to look for or add
**Acceptance criteria:**
- [ ] testable criterion 1
- [ ] testable criterion 2
**Out of scope:** what this slice does NOT touch

## Blocked by

A reference to the blocking issue(s), or "None — can start immediately".

</issue-template>

If a prototype produced a snippet that encodes a decision more precisely than prose (state machine, reducer, schema, type shape), inline its decision-rich parts under **Key interfaces** and note it came from a prototype.

Do NOT close or modify any parent issue.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** tracer-bullet issues, labelled `ready-for-agent` (AFK) / `ready-for-human` (HITL) by type
- **default:** `pickup` — implement a ready issue
- **alternatives:** stop
- **auto:** never — the granularity/dependency quiz (step 4) is the judgment and has no safe default.
