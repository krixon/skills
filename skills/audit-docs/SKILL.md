---
name: audit-docs
description: Audit a codebase for documentation that has drifted out of sync with the code — stale CONTEXT.md vocabulary, violated ADR decisions, README/behavior claims the code no longer backs — and surface each as a finding. Static-first, no tool run required. Use when the user wants to check the docs are still accurate, find stale docs, or asks "is the documentation still accurate?" / "what drifted from CONTEXT.md / the ADRs?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Docs Audit

Find where the **prose no longer matches the code** — documented claims the implementation has outgrown — and surface each as a finding. `audit-docs` is a producer: it audits, then hands findings to `capture`, which dedups, culls, and files them as `needs-triage` issues. It does not file issues itself.

The aim is *factual drift* — a doc that contradicts the code — not writing quality. A stale claim that misleads a reader or an agent is the target; an awkward sentence that is still true is not.

Read the project's domain glossary (`CONTEXT.md`) and any ADRs in the area first: they are both the claims to check *and* the vocabulary finding titles use. With neither present, the skill degrades to README and docstring claims; if there is nothing documented to contradict, report nothing rather than invent docs to audit.

## Method: static-first

Reason from the prose and the code that should back it. Never require running a tool — drift is a contradiction between two artifacts already in the tree, readable directly. Missing some drift is acceptable: the cull and `triage` are downstream gates, and the target is misleading staleness, not completeness.

## Process

### 1. Map claims

Walk the documentation. Above ~25 files in scope, fan out `Explore` subagents (one per doc area) so the reads never land in the main window; at or below that, explore inline (see [../DELEGATION.md](../DELEGATION.md)). Collect concrete, checkable assertions — a glossary term's definition, an ADR's decision, a README's described command or flag, a docstring's stated behavior. Skip aspirational or roadmap prose: only claims the code is supposed to back right now.

### 2. Locate the backing code

For each claim, find the code that should make it true. A claim with no corresponding code is itself a signal (dead doc). Trace whether the code *actually* honors the claim — a term still used with the same meaning, an ADR's decision still implemented, a documented flag still wired, the described output still produced. A doc and code merely sitting near each other is not agreement.

### 3. Fan out finders, then score

Above the fan-out threshold, spawn parallel finder agents over the documented areas, each returning candidate contradictions; below it, find inline. Sweep at least these sub-dimensions:

- **Stale glossary** — a `CONTEXT.md` term or definition the code no longer uses, or now uses to mean something else.
- **Violated ADR** — a decision in `docs/adr/` the implementation no longer honors.
- **README / doc behavior** — described behavior, flags, commands, or outputs that no longer match the code.
- **Dead doc** — documentation for a feature, path, or option that no longer exists.

Then score each candidate for **confidence** (genuine drift, not merely imprecise prose) and **severity** (does the staleness mislead a reader or an agent?). Drop low-confidence noise — a doc that is loose but not wrong is not a finding.

### 4. Emit findings

Shape each surviving contradiction into the six-field finding contract in [../contracts/finding.md](../contracts/finding.md):

- **Dimension** — `docs-drift` (the sub-dimension goes in the title/evidence, e.g. "stale glossary term …", "README flag … no longer wired" — never as a new top-level dimension)
- **Suggested category** — usually `enhancement` ("realign the doc with X"); a doc that actively misleads into wrong behavior is a `bug`
- **Where** — the doc and the code it contradicts, named by section / term / module (path as of-audit)
- **Evidence** — the documented claim, the code that contradicts it, and who it misleads
- **Severity** / **Confidence** — from step 3

## Handover

Hand off per [../HANDOVER.md](../HANDOVER.md). Never file issues yourself. End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
- **auto:** advance
