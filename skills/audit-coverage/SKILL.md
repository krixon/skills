---
name: audit-coverage
description: Audit a codebase for high-risk untested paths and surface them as findings. Static-first, no instrumented coverage run required. Use when the user wants to find test gaps, audit coverage, find untested critical paths, or asks "what's not tested?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Coverage Audit

Find where the test suite leaves **high-risk paths unexercised**, and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens and dimension below.

The aim is *risk-weighted* gaps, not raw uncovered-line count — target paths where being untested matters.

## Risk lens (step 1)

Rank code by:

- **Criticality** — money, auth, data integrity, external side effects.
- **Complexity** — branchy logic, error handling, edge cases.
- **Churn** — frequently changed code (`git log`) breaks more often.

## Current state: map coverage (step 2)

For the high-risk code, find what the tests exercise. A test file existing for a module is not coverage — trace which *branches and error paths* are hit. Consume a coverage report here if one exists.

## Dimension (step 4)

- **Dimension** — `test-gap`
- **Suggested category** — usually `enhancement` ("add coverage for X"); a gap that already masks a likely defect is a `bug`
- **Where** — the untested module / type / function
- **Evidence** — the untested high-risk path and why it matters

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
