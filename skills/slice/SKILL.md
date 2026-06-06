---
name: slice
description: Break a plan, spec, or PRD into independently-grabbable issues on the tracker via tracer-bullet vertical slices. Use when user wants to convert a plan into issues, create implementation tickets, or break work down. Un-investigated audit observations go through `capture` instead.
argument-hint: "[plan, spec, or PRD to slice]"
---

# Slice

Break a plan into independently-grabbable issues using vertical slices (tracer bullets).

Issues live in GitHub; use the `gh` CLI ([../GITHUB.md](../GITHUB.md) for commands and the label list).

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes an issue reference (issue number, URL, or path) as an argument, fetch it (`gh issue view <n> --comments`) and read its full body and comments.

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

### 5. Publish the issues to GitHub

If the approved breakdown is a single slice, slicing was a no-op — it didn't decompose anything, and a lone new issue would only duplicate the source. Create nothing. Carry the original source issue forward as the result and hand it to the next hop as if it were the slice output, telling the user the run was a no-op. Only publish when the breakdown is two or more slices.

For each approved slice, create an issue (`gh issue create`). Use the issue body template below. Label by the AFK/HITL decision in [../contracts/agent-brief.md](../contracts/agent-brief.md).

Publish issues in dependency order (blockers first) so a blocked slice's blockers already exist when you record the dependency.

The child's body is the **agent brief** alone — `pickup` reads it origin-blind, the same shape it gets from a triage-promoted issue. Follow the brief in [../contracts/agent-brief.md](../contracts/agent-brief.md) (behavioral, durable, no file paths). Parent and blocked-by links are native GitHub relations, not body prose; record them after creating the issue (below).

<issue-template>
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

</issue-template>

If a prototype produced a snippet that encodes a decision more precisely than prose (state machine, reducer, schema, type shape), inline its decision-rich parts under **Key interfaces** and note it came from a prototype.

**Link the slice with native relations** (commands in [../GITHUB.md](../GITHUB.md) → *Issue relations*). Both relation APIs key writes on an issue's internal **id**, not its number, so resolve each id with `gh api repos/{owner}/{repo}/issues/<number> --jq .id` after `gh issue create` returns the number, and pass it as a typed integer (`-F`, not `-f` — a string returns HTTP 422):

- **Parent** — when the source was an existing issue (the PRD), make each child a sub-issue of it: resolve the child's id, then `gh api repos/{owner}/{repo}/issues/<parent-number>/sub_issues -F sub_issue_id=<child-id>`. Omit when the source wasn't an existing issue.
- **Blocked by** — for each blocking slice, resolve the blocker's id and record the dependency on the blocked child: `gh api repos/{owner}/{repo}/issues/<child-number>/dependencies/blocked_by -F issue_id=<blocker-id>`. Publishing blockers first guarantees the blocker exists when you write the dependency.

Do NOT close or modify any parent issue's body, labels, or state — adding a sub-issue relation is the only parent write.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** tracer-bullet issues, labelled `ready-for-agent` (AFK) / `ready-for-human` (HITL) by type — or, when the breakdown was a single slice, no new issue and the original source issue carried forward unchanged
- **default:** `pickup` — implement a ready issue
- **alternatives:** stop
- **auto:** never — the granularity/dependency quiz (step 4) is the judgment and has no safe default.
