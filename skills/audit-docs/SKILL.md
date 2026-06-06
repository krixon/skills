---
name: audit-docs
description: Audit a codebase for documentation that has drifted out of sync with the code — stale CONTEXT.md vocabulary, violated ADR decisions, README/behavior claims the code no longer backs — and surface each as a finding. Static-first, no tool run required. Use when the user wants to check the docs are still accurate, find stale docs, or asks "is the documentation still accurate?" / "what drifted from CONTEXT.md / the ADRs?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Docs Audit

Find where the **prose no longer matches the code** — documented claims the implementation has outgrown — and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *factual drift* — a doc that contradicts the code — not writing quality. A stale claim that misleads a reader or an agent is the target; an awkward sentence that is still true is not.

The project's domain vocabulary and recorded decisions (per [../CONVENTIONS.md](../CONVENTIONS.md)) are both the claims to check *and* the vocabulary finding titles use. With neither present, the audit degrades to README and docstring claims; if there is nothing documented to contradict, report nothing rather than invent docs to audit.

## Risk lens: map claims (step 1)

Walk the documentation and collect concrete, checkable assertions — a glossary term's definition, an ADR's decision, a README's described command or flag, a docstring's stated behavior. Skip aspirational or roadmap prose: only claims the code is supposed to back right now. Rank by how badly a stale claim would mislead.

## Current state: locate the backing code (step 2)

For each claim, find the code that should make it true. A claim with no corresponding code is itself a signal (dead doc). Trace whether the code *actually* honors the claim — a term still used with the same meaning, an ADR's decision still implemented, a documented flag still wired, the described output still produced. A doc and code merely sitting near each other is not agreement.

## Sub-dimensions to sweep (step 3)

- **Stale glossary** — a `CONTEXT.md` term or definition the code no longer uses, or now uses to mean something else.
- **Violated ADR** — a decision in `docs/adr/` the implementation no longer honors.
- **README / doc behavior** — described behavior, flags, commands, or outputs that no longer match the code.
- **Dead doc** — documentation for a feature, path, or option that no longer exists.

Drop low-confidence noise — a doc that is loose but not wrong is not a finding.

## Dimension (step 4)

- **Dimension** — `docs-drift` (the sub-dimension goes in the title/evidence, e.g. "stale glossary term …", "README flag … no longer wired" — never as a new top-level dimension)
- **Suggested category** — usually `enhancement` ("realign the doc with X"); a doc that actively misleads into wrong behavior is a `bug`
- **Where** — the doc and the code it contradicts, named by section / term / module
- **Evidence** — the documented claim, the code that contradicts it, and who it misleads

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
