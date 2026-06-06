---
name: audit-debt
description: Harvest in-code debt markers (TODO/FIXME/HACK/XXX and known shortcuts) from a codebase and surface each as a finding, clustered by area. Static-first, no debt tool required. Use when the user wants to harvest TODOs, find tech debt, audit shortcuts, or asks "what's left to clean up?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Debt Audit

Harvest the **in-code debt markers** a codebase has accumulated — `TODO`, `FIXME`, `HACK`, `XXX`, and the project's own known shortcuts — and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens and dimension below.

The aim is *risk-weighted* debt — rank by the criticality of the area a marker sits in, never by marker count. A `FIXME` in the payment path outranks ten `TODO`s in a sample script.

## Risk lens (step 1)

Sweep for markers — `TODO`, `FIXME`, `HACK`, `XXX`, and any shortcut convention the project documents — then rank each by the **criticality of the area it sits in**: money, auth, data integrity, external side effects outrank cosmetic or test-scaffold code. The marker's own urgency (`FIXME`/`HACK` over `TODO`) breaks ties. Consume an existing marker report here if one is present (a `// FIXME` lint pass, a debt-tracker export); never require a tool to produce one.

## Current state: confirm the marker is live (step 2)

For each high-ranked marker, confirm it is still real before emitting:

- **Not already resolved** — the code the marker describes may have changed out from under it; a stale marker pointing at fixed code is noise, not debt.
- **Not already tracked** — a marker that names or duplicates an open issue is already on the tracker; drop it.

## Dimension (step 4)

- **Dimension** — `debt`
- **Suggested category** — `enhancement` (paying down a shortcut); a marker flagging a known-wrong behavior is a `bug`
- **Where** — the module / type / function the marker sits in
- **Evidence** — the marker text and the shortcut it records, plus why the area makes it worth paying down
- **Cluster** — fold related markers in one area into a single finding via the **Instances** block in [../contracts/finding.md](../contracts/finding.md), rather than one finding per line

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape, dimension `debt`, `Source: audit-debt`)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
