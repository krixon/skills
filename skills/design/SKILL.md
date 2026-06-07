---
name: design
description: Grill the user relentlessly about a plan or technical design until reaching shared understanding, challenging it against the existing domain model, sharpening terminology, and offering an ADR when a load-bearing decision crystallises. Use when user wants to stress-test a plan or design, get grilled, or mentions "grill me".
argument-hint: "[plan or design to grill]"
---

# Design

Grill the user about a plan or technical design until you both reach a shared understanding, challenging it against the project's domain model and sharpening its terminology. The interview mechanism is shared — ask one question at a time, recommend an answer to each, explore the codebase rather than asking, and offer an ADR only on the three-criteria gate — and lives in [../GRILL-METHOD.md](../GRILL-METHOD.md). This skill carries the technical and domain-model lens.

## Domain awareness

Ground in the project's documentation — its established vocabulary and recorded decisions, as the in-context project `CLAUDE.md` points to them. Use the project's terms; respect decisions already recorded. With none present, work from the plan and the code.

## The lens

### Challenge against established terms

When the user uses a term that conflicts with the project's established language, call it out immediately. "The project defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. Surface any contradiction: "Your code cancels entire Orders, but you said partial cancellation is possible — which is right?"

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a plan stress-tested against the domain model, terminology sharpened, with an ADR offered inline where a decision warrants it
- **default:** `slice` — synthesise the resolved plan into agent-brief issues (one, or N under a lean epic)
- **alternatives:** stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — grilling is an interview; `auto` never enters it.
