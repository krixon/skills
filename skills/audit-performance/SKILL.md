---
name: audit-performance
description: Sweep a codebase for performance hazards on hot paths — N+1 data access, per-iteration allocation or IO in loops, unbounded reads, missing caching or indexing, blocking calls in async contexts — and surface each as a finding. Static-first, no profiler or benchmark required. Use when the user wants to audit performance, find slow paths, hunt N+1 queries or unbounded reads, or asks "what's slow?" / "what won't scale?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Performance Audit

Find where a **path plausibly hot carries a performance hazard** — work that scales badly with input or load — and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *risk-weighted* hazards on hot paths, not micro-optimisations on cold code. A redundant allocation in a once-at-startup path is noise; the same allocation per request, per row, or per event is the concern. Findings name the hazard and the hot-path evidence — why this path matters — never a style preference.

## Risk lens (step 1)

Map the codebase's hot paths from its entry points and loop structure, then rank by how often the work runs and how it scales:

- **Per-request / per-event** — request handlers, message consumers, render loops, anything that runs once per unit of incoming work and multiplies a single hazard across traffic.
- **Loops and recursion** — per-iteration work inside a loop, especially one whose bound grows with input or a collection size.
- **Data-volume paths** — code that fetches, scans, or transforms collections whose size is caller- or data-driven, where cost grows with the row count.

Rank by exposure — a hazard on a per-request path scaling with input outranks one on a cold or fixed-size path.

## Current state: confirm the path is hot and unmitigated (step 2)

For each candidate, confirm two things before it counts: the path is genuinely hot, and nothing already absorbs the cost. A mitigation existing *somewhere* is not the same as guarding *this* path — trace whether it applies:

- A cache, memoisation, or batch/eager-load that already collapses the repeated work.
- An index or query plan that already makes the access cheap.
- A bound, limit, or pagination that already caps the result set.
- A path that runs once or over a fixed small size — cost that never scales is not a hazard.

## Sub-dimensions to sweep (step 3)

- **N+1 data access** — a query, fetch, or remote call issued per row of a prior result instead of once in a batch.
- **Per-iteration allocation or IO** — allocation, IO, or expensive computation inside a loop that could be hoisted, batched, or amortised.
- **Unbounded reads** — collection fetches with no pagination or limit, loading data whose size grows with the dataset.
- **Missing caching or indexing** — repeated identical computation or a lookup whose access pattern demands an index but has none.
- **Blocking in async contexts** — a synchronous or blocking call inside an async path, stalling the event loop or starving the pool.

Drop low-confidence noise — a hazard on cold code, or one a mitigation already covers, is not a finding.

## Dimension (step 4)

- **Dimension** — `performance` (the sub-dimension goes in the title/evidence, e.g. "N+1 query loading order line items per order in …", "unbounded fetch of all users in …" — never as a new top-level dimension)
- **Suggested category** — `enhancement` (hardening a hot path against a hazard); a hazard already degrading production latency or exhausting a resource is a `bug`
- **Where** — the hot path's module / type / function
- **Evidence** — the hazard, why the path is hot (the hotness justification, not a style claim), that no mitigation covers it, and how the cost scales

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
