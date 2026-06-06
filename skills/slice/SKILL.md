---
name: slice
description: Turn a plan, conversation context, or an existing issue into one agent-brief issue or N linked agent-brief issues under a lean epic, via tracer-bullet vertical slices. Use when user wants to convert a plan into issues, spec work out from the current context, create implementation tickets, or break work down. Un-investigated audit observations go through `capture` instead.
argument-hint: "[plan, conversation, or issue to slice]"
---

# Slice

Turn a plan, the current conversation context, or an existing issue into independently-grabbable agent-brief issues using vertical slices (tracer bullets). Synthesize from what you already know — do NOT interview the user.

Issues live in GitHub; use the `gh` CLI ([../GITHUB.md](../GITHUB.md) for commands and the label list).

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes an issue reference (issue number, URL, or path) as an argument, fetch it (`gh issue view <n> --comments`) and read its full body and comments. Synthesize the change from this context and your codebase understanding; don't interview the user for it.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the state of the code. Issue titles and descriptions should use the project's established vocabulary, and respect its recorded decisions in the area you're touching.

### 3. Draft vertical slices

**Assess decomposability first.** A single vertical slice cuts end-to-end through every layer (schema, API, UI, tests) as one grabbable piece. If the work is one such slice, the breakdown is a single agent-brief issue — there is no epic and no children. If it naturally breaks into several slices with dependencies between them, it's multi-slice: a lean epic parent with N linked children.

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

Branch on the breakdown shape.

**Single slice, source was an existing issue.** Slicing was a no-op — it didn't decompose anything, and a lone new issue would only duplicate the source. Create nothing. Carry the original source issue forward as the result and hand it to the next hop as if it were the slice output, telling the user the run was a no-op.

**Single slice, source was conversation context or a plan.** There is nothing to duplicate — emit one agent-brief issue (`gh issue create`) using the body template below, with no parent and no blockers. Label by the AFK/HITL decision in [../contracts/agent-brief.md](../contracts/agent-brief.md). Carry it forward to the next hop.

**Two or more slices.** Publish a lean **epic** parent plus a child agent-brief issue per slice.

For each child slice, create an issue (`gh issue create`). Use the issue body template below. Label by the AFK/HITL decision in [../contracts/agent-brief.md](../contracts/agent-brief.md). Publish children in dependency order (blockers first) so a blocked slice's blockers already exist when you record the dependency.

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

#### The epic parent

A multi-part parent is a lean **epic**, not a heavyweight document: goal, out-of-scope, and the child list, nothing more. Create it (`gh issue create`) with the body template below and the **`epic`** label plus the category label (`enhancement` / `bug`). The epic carries **no readiness label** — it isn't actionable as-is; its children carry the `ready-for-agent` / `ready-for-human` labels. Write its prose per [../../WRITING.md](../../WRITING.md) → *Docs*: task-first, declarative, no marketing tone. The child list is realized as native GitHub sub-issues (below), so the body's child list is a plain summary, not the source of truth for the relation.

<epic-template>
## Epic

**Goal:** what the whole change delivers, from the user's perspective — one or two sentences
**Out of scope:** what this epic does NOT cover
**Children:** a short summary line per slice (the authoritative relation is the native sub-issue link)

</epic-template>

#### Link the slices

**Link each child with native relations** (commands in [../GITHUB.md](../GITHUB.md) → *Issue relations*). Both relation APIs key writes on an issue's internal **id**, not its number, so resolve each id with `gh api repos/{owner}/{repo}/issues/<number> --jq .id` after `gh issue create` returns the number, and pass it as a typed integer (`-F`, not `-f` — a string returns HTTP 422):

- **Parent** — make each child a sub-issue of the epic: resolve the child's id, then `gh api repos/{owner}/{repo}/issues/<epic-number>/sub_issues -F sub_issue_id=<child-id>`.
- **Blocked by** — for each blocking slice, resolve the blocker's id and record the dependency on the blocked child: `gh api repos/{owner}/{repo}/issues/<child-number>/dependencies/blocked_by -F issue_id=<blocker-id>`. Publishing blockers first guarantees the blocker exists when you write the dependency.

Seam choice is not slice's job — `pickup`/`tdd` pick seams downstream, the same for every child.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`, picking the default for the shape you produced.

- **artifact:** one agent-brief issue (single slice), or N tracer-bullet child issues under a lean epic — children labelled `ready-for-agent` (AFK) / `ready-for-human` (HITL) by type; or, when a single-slice breakdown duplicated an existing source issue, no new issue and the original source issue carried forward unchanged
- **default:** `pickup` — implement a ready issue
- **alternatives:** stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — the granularity/dependency quiz (step 4) is the judgment and has no safe default; `auto` never enters it.
