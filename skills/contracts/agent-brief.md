# Writing Agent Briefs

An agent brief is a structured comment posted on a GitHub issue when it moves to `ready-for-agent`. It is the authoritative specification that an AFK agent will work from. The original issue body and discussion are context — the agent brief is the contract.

Write its prose per [../../WRITING.md](../../WRITING.md) → *Issues & findings*: lead with the problem, plainly, no hedging where you know. Run the subtract pass before posting.

## Principles

### Durability over precision

The issue may sit while the codebase changes underneath it. Write the brief so it survives files being renamed, moved, or refactored.

- **Do** describe interfaces, types, and behavioral contracts
- **Do** name specific types, function signatures, or config shapes that the agent should look for or modify
- **Don't** reference file paths — they go stale
- **Don't** reference line numbers
- **Don't** assume the current implementation structure will remain the same

### Behavioral, not procedural

Describe **what** the system should do, not **how** to implement it. The agent will explore the codebase fresh and make its own implementation decisions.

- **Good:** "The `SkillConfig` type should accept an optional `schedule` field of type `CronExpression`"
- **Bad:** "Open src/types/skill.py and add a schedule field on line 42"
- **Good:** "When a user runs `/triage` with no arguments, they should see a summary of issues needing attention"
- **Bad:** "Add a switch statement in the main handler function"

### Complete acceptance criteria

The agent needs to know when it's done. Every brief needs concrete acceptance criteria, each independently verifiable.

- **Good:** "Running `gh issue list --label needs-triage` returns issues that have been through initial classification"
- **Bad:** "Triage should work correctly"

### Explicit scope boundaries

State what is out of scope. This stops the agent gold-plating or making assumptions about adjacent features.

## AFK/HITL label decision

A brief moves an issue to one of two readiness labels. Label `ready-for-agent` if an agent can clear the change end-to-end. Label `ready-for-human` if it carries a judgement step a human must make — an architectural decision, a design review, external access. For a `ready-for-human` issue, note in the brief *why* a human is needed, so `pickup` can drive them through it.

## Template

<agent-brief-template>

## Agent Brief

**Category:** bug / enhancement
**Summary:** one-line description of what needs to happen

**Current behavior:**
Describe what happens now. For bugs, this is the broken behavior. For enhancements, this is the status quo the feature builds on.

**Desired behavior:**
Describe what should happen after the agent's work is complete. Be specific about edge cases and error conditions.

**Key interfaces:**
- `TypeName` — what needs to change and why
- `functionName()` return type — what it currently returns vs what it should return
- Config shape — any new configuration options needed

**Acceptance criteria:**
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] Specific, testable criterion 3

**Out of scope:**
- Thing that should NOT be changed or addressed in this issue
- Adjacent feature that might seem related but is separate

</agent-brief-template>

## Examples

### Good agent brief (bug)

<agent-brief-example>

## Agent Brief

**Category:** bug
**Summary:** Skill description truncation drops mid-word, producing broken output

**Current behavior:**
When a skill description exceeds 1024 characters, it is truncated at exactly 1024 characters regardless of word boundaries. This produces descriptions that end mid-word (e.g. "Use when the user wants to confi").

**Desired behavior:**
Truncation should break at the last word boundary before 1024 characters and append "..." to indicate truncation.

**Key interfaces:**
- The `SkillMetadata` type's `description` field — no type change needed, but the validation/processing logic that populates it needs to respect word boundaries
- Any function that reads SKILL.md frontmatter and extracts the description

**Acceptance criteria:**
- [ ] Descriptions under 1024 chars are unchanged
- [ ] Descriptions over 1024 chars are truncated at the last word boundary before 1024 chars
- [ ] Truncated descriptions end with "..."
- [ ] The total length including "..." does not exceed 1024 chars

**Out of scope:**
- Changing the 1024 char limit itself
- Multi-line description support

</agent-brief-example>

### Good agent brief (enhancement)

<agent-brief-example>

## Agent Brief

**Category:** enhancement
**Summary:** Surface prior rejections during triage so the maintainer doesn't re-litigate a closed `wontfix`

**Current behavior:**
When a feature request is rejected, the issue is closed with a `wontfix` label and the reason in the close comment. Triaging a new issue does not check whether a similar request was already rejected, so the maintainer re-evaluates ground already covered.

**Desired behavior:**
During triage, the prior-rejection check queries closed `wontfix` issues and surfaces any whose close comment resembles the incoming request, so the maintainer sees the earlier decision and its reason before deciding.

**Key interfaces:**
- The triage gather-context step runs `gh issue list --label wontfix --state closed` and matches incoming issues against the results by concept similarity
- The surfaced match links the prior issue and quotes its close-comment reason

**Acceptance criteria:**
- [ ] Triage queries closed `wontfix` issues during gather-context
- [ ] A new issue resembling a prior rejection surfaces the match with a link and the recorded reason
- [ ] No match found leaves triage unchanged

**Out of scope:**
- Automated matching (human confirms the match)
- Reopening previously rejected features
- Bug reports (only enhancement rejections carry a rejection reason worth matching)

</agent-brief-example>
