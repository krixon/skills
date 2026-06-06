---
name: grill
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
argument-hint: "[plan or design to grill]"
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask one question at a time.

If a question can be answered by exploring the codebase, explore it instead.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a stress-tested plan (shared understanding in the conversation)
- **default:** `spec` — synthesise the resolved plan into a PRD
- **alternatives:** `slice` · stop
- **auto:** never — grilling is an interview.
