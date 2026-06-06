---
name: audit-type-safety
description: Audit a codebase for loose typing at its seams — `any`, over-broad or untyped signatures, missing contracts at public and cross-module boundaries — and surface each as a finding. Static-first, consumes an existing type-checker report but never requires one. Use when the user wants to find loose types, check type safety at seams, or asks "where are the untyped boundaries?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Type-Safety Audit

Find where **loose typing at a seam** weakens the contract a caller relies on, and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens and dimension below.

The aim is *seam-weighted* findings, not an `any`-count — target the boundaries where a loose type misleads a caller across a module or public edge, not every local that could be tighter.

## Risk lens (step 1)

Rank loose typing by **seam exposure** — a loose public or cross-module boundary outranks a loose internal local:

- **Exposure** — public API, exported/cross-module signatures, and serialization boundaries leak a loose type to callers who can't see the implementation.
- **Looseness** — `any`, untyped parameters/returns, over-broad unions, and missing contracts (no declared shape where one is expected) erode what the type promises.
- **Churn** — frequently changed seams (`git log`) drift from their original contract as callers multiply.

## Current state: confirm the seam is loose (step 2)

For each candidate, confirm the seam is *genuinely* loose — not narrowed downstream. A broad signature backed by entry validation is not the same exposure. Check whether the boundary is already tightened by an overload, a type guard, runtime validation, or a typed wrapper at the edge; if it is, the caller's contract holds and there is no finding. Consume a type-checker report (e.g. `mypy`, `tsc`, `pyright`) here if one is present.

## Dimension (step 4)

- **Dimension** — `type-safety`
- **Suggested category** — `enhancement` ("tighten the contract at X")
- **Where** — the loose module / type / function at the seam
- **Evidence** — the loose signature, the seam it exposes, and the caller it misleads — and that no downstream guard narrows it

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape, `Source: audit-type-safety`)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
