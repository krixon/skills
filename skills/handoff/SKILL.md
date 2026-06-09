---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up. Use when the user wants to hand off, wrap up, or summarise the session so a fresh agent can continue the work.
argument-hint: "What will the next session be used for?"
---

# Handoff

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS — not the current workspace.

Include a "suggested skills" section listing skills the agent should invoke.

Do not duplicate content already captured in other artifacts (epics, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

## Offer durable learnings to memory

After the doc is written and before the handover question, offer to persist the session's **durable learnings** to the harness memory mechanism — the facts that outlive this work item and would serve any future session, not the session state the handoff doc already carries.

The doc and memory split the session's knowledge by lifespan. The doc holds what the **next** agent needs to resume *this* work — task progress, open threads, the files in flight — and is consumed once. Memory holds what **every** future session should know regardless of the work item. Offer only the second kind:

- **Durable — offer it.** A standing fact about the user (a preference or constraint they hold across work), the project (an invariant, a recorded decision, a convention the session surfaced), or how to work (a correction to the agent's approach that should stick).
- **Session state — never offer it.** Task progress, the file list, what's half-done, the next step. That is the handoff doc's job, and a memory of it rots the moment the work moves.
- **A workaround for a defect — never offer it.** A learning that compensates for a skill, hook, or doc not doing its job belongs in that artifact, not in memory. Surface it as something to fix at the source. Honor the project's recorded decision on this where one exists (discovered via the in-context project `CLAUDE.md`).

Before offering, read the harness's existing memories and check each candidate against them: when one refines a memory already held, offer it as an **update** to that entry rather than a duplicate. Then present the surviving candidates as one `AskUserQuestion` (multi-select), each with a one-line rationale for why it's durable — nothing persists without the user's pick. Persist each approved candidate through the memory mechanism exactly as the harness documents it (a file-based memory directory with an index), used per the harness's own contract.

**No memory mechanism available → skip this step silently** and go straight to the handover question.

## Handover

Per [../HANDOVER.md](../HANDOVER.md).

- **artifact:** a handoff doc in the OS temp directory, plus any approved durable learnings persisted to memory
- **default:** — (terminal; a fresh agent reads the doc)
- **alternatives:** stop
