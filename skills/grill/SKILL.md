---
name: grill
description: Interview the user relentlessly about a plan or design until reaching shared understanding, challenging it against the existing domain model, sharpening terminology, and offering an ADR when a load-bearing decision crystallises. Use when user wants to stress-test a plan or design, get grilled, or mentions "grill me".
argument-hint: "[plan or design to grill]"
---

## What to do

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask one question at a time, waiting for feedback before continuing.

If a question can be answered by exploring the codebase, explore it instead.

## Domain awareness

Ground in the project's documentation — its established vocabulary and recorded decisions, as the in-context project `CLAUDE.md` points to them. Use the project's terms; respect decisions already recorded. With none present, work from the plan and the code.

## During the session

### Challenge against established terms

When the user uses a term that conflicts with the project's established language, call it out immediately. "The project defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. Surface any contradiction: "Your code cancels entire Orders, but you said partial cancellation is possible — which is right?"

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Follow the project's lead on where decisions are recorded rather than scaffolding a layout it doesn't use. Use the format in [../contracts/adr.md](../contracts/adr.md).

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a plan stress-tested against the domain model, terminology sharpened, with an ADR offered inline where a decision warrants it
- **default:** `slice` — synthesise the resolved plan into agent-brief issues (one, or N under a lean epic)
- **alternatives:** stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — grilling is an interview; `auto` never enters it.
