# Grill Method

The shared interview engine behind the grilling skills. Each grilling skill (`design`, and others to come) supplies its own **lens** — what it challenges the plan against; the mechanism lives here.

A grill session is an interview: walk each branch of the plan one decision at a time, resolving dependencies between decisions until you and the user reach shared understanding. It is interactive — `auto` never enters it.

Ground in the project's documentation first — its vocabulary and recorded decisions, via the in-context project `CLAUDE.md` — so questions use the project's terms. With nothing documented, work from the plan and the code.

## Mechanism

### Ask one question at a time

Ask one question, then wait for feedback. Don't batch or run ahead — each answer shapes the next branch you walk.

### Recommend an answer to each question

Give your recommended answer and the reasoning behind it. The user reacts to a position, not a blank page.

### Explore, don't ask

When the codebase answers a question, read it instead of asking. Reserve questions for what the code can't tell you — intent, trade-offs, decisions not yet made.

### Offer an ADR sparingly

Offer to record an ADR only when all three hold:

1. **Hard to reverse** — changing your mind later is costly.
2. **Surprising without context** — a future reader will wonder "why this way?"
3. **The result of a real trade-off** — genuine alternatives existed and you picked one for specific reasons.

Missing any one → skip the ADR. Follow the project's lead on where decisions are recorded; don't scaffold a layout it doesn't use. Use the format in [contracts/adr.md](contracts/adr.md).

## Handover

End an interactive run by rendering the skill's handover row as one `AskUserQuestion`, per [HANDOVER.md](HANDOVER.md). Each grilling skill declares its own row.
