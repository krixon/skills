---
name: audit-observability
description: Sweep a codebase for critical paths that run blind — no log, metric, or trace at any layer — and surface each as a finding. Static-first, no tracing or metrics tool required. Use when the user wants to find observability gaps, check what's instrumented, find paths that fail silently, or asks "what's not logged?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Observability Audit

Find where a **critical path runs blind** — emitting nothing an operator could use to see it ran, succeeded, or failed — and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, layers, and dimension below.

The aim is *risk-weighted* blind spots, not a coverage count — target the paths where flying blind costs the most. A silent log-everywhere module is not the concern; a silent auth or payment path is.

## Risk lens (step 1)

Rank code by what an operator pays for not seeing it:

- **Money** — payment, billing, refund, ledger mutation.
- **Auth** — login, token issue/verify, permission decisions.
- **Data mutation** — writes, deletes, migrations, state transitions.
- **External calls** — outbound requests, queue publishes, third-party APIs that can fail or stall.

Rank by criticality — a silent auth path outranks a silent read.

## Current state: map instrumentation (step 2)

For each high-risk path, confirm it emits nothing at **any** layer. Instrumentation one layer up means the path is not blind:

- A wrapping middleware, decorator, aspect, or interceptor already logging the call.
- A framework-level request/response log or access log covering the route.
- A metric or trace span opened by a caller that encloses this path.

A log line sitting elsewhere in the module is not coverage — trace whether the *specific* critical operation, and its failure branch, is observable. Consume a tracing or metrics report here if one exists; never require running one.

## Layers to sweep (step 3)

- **Log** — no record the operation ran, succeeded, or failed; a swallowed exception with no log is the sharpest case.
- **Metric** — no counter, gauge, or timer, so rate, latency, and error volume are invisible.
- **Trace** — no span, so the path can't be followed across service boundaries.

A path blind at one layer but covered at another is usually not a finding — judge by whether an operator could answer "did this run, and did it fail?".

## Dimension (step 4)

- **Dimension** — `observability` (the layer goes in the title/evidence, e.g. "payment capture emits no log or metric", "swallowed exception in token refresh" — never as a new top-level dimension)
- **Suggested category** — `enhancement` (instrumenting a blind path adds capability; the audit surfaces the gap, it never adds the instrumentation)
- **Where** — the blind module / type / function
- **Evidence** — the critical operation, that it emits nothing at any layer (including one layer up), and what an operator loses by it being blind

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
