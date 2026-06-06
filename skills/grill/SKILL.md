---
name: grill
description: Interview the user relentlessly about a plan or design until reaching shared understanding, challenging it against the existing domain model, sharpening terminology, and updating documentation (CONTEXT.md, ADRs) inline as decisions crystallise. Use when user wants to stress-test a plan or design, get grilled, or mentions "grill me".
argument-hint: "[plan or design to grill]"
---

## What to do

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask one question at a time, waiting for feedback before continuing.

If a question can be answered by exploring the codebase, explore it instead.

## Domain awareness

During codebase exploration, also look for existing documentation:

### File structure

Single-context repo: `CONTEXT.md` + `docs/adr/` at the root. Multi-context repo: a `CONTEXT-MAP.md` at the root points to a per-context `CONTEXT.md` + `docs/adr/` under each `src/<context>/`, with root `docs/adr/` holding system-wide decisions.

Create files lazily — only when you have something to write: `CONTEXT.md` when the first term resolves, `docs/adr/` when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. Surface any contradiction: "Your code cancels entire Orders, but you said partial cancellation is possible — which is right?"

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch — capture them as they happen. Use the format in [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](ADR-FORMAT.md).

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a plan stress-tested against the domain model, with `CONTEXT.md`/ADRs updated inline
- **default:** `spec` — synthesise the resolved plan into a PRD
- **alternatives:** `slice` · stop
- **auto:** never — grilling is an interview.
