# Grill Method

The shared interview engine behind the grilling skills. Each skill that grills (`design`, and others to come) fills in its own **lens** — what it challenges the plan against — while the mechanism of the interview lives here once.

A grill session is an **interview**: walk down each branch of the plan one decision at a time, resolving dependencies between decisions until you and the user reach a shared understanding. It is interactive by nature — there is no safe unattended default, so `auto` never enters it.

Ground in the project's documentation first — its established vocabulary and recorded decisions, as the in-context project `CLAUDE.md` points to them — so the questions use the project's terms. With nothing documented, work from the plan and the code.

## Mechanism

### Ask one question at a time

Ask a single question, then wait for feedback before continuing. Don't batch questions or run ahead of the user's answers — each answer shapes the next branch you walk.

### Recommend an answer to each question

For every question, give your recommended answer with the reasoning behind it. The user reacts to a position rather than starting from a blank page.

### Explore, don't ask

When a question can be answered by reading the codebase, read it instead of asking. Reserve questions for what the code can't tell you — intent, trade-offs, decisions not yet made.

### Offer an ADR sparingly

Offer to record an ADR only when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful.
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons.

If any of the three is missing, skip the ADR. Follow the project's lead on where decisions are recorded rather than scaffolding a layout it doesn't use. Use the format in [contracts/adr.md](contracts/adr.md).

## Handover

End an interactive run by rendering the skill's handover row as one `AskUserQuestion`, per [HANDOVER.md](HANDOVER.md). Each grilling skill declares its own row.
