---
name: audit-resource-leak
description: Sweep a codebase for resource-leak sites — acquired handles, connections, contexts, or locks with no guaranteed release on every path — and surface each as a finding. Static-first, no leak detector required. Use when the user wants to find resource leaks, hunt unclosed handles or connections, check for missing with/defer/finally, or asks "what leaks?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Resource-Leak Audit

Find where the code **acquires a resource without guaranteeing its release on every path**, and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *risk-weighted* leaks, not a raw list of every `open(` — target acquire sites whose leak compounds under load.

## Risk lens (step 1)

Find acquire sites — file handles, DB/network connections, contexts, locks, semaphores, OS handles, subprocesses — and rank by under-load exposure:

- **Hot paths** — request handlers, message consumers, anything per-request or per-event, where a leak per call exhausts the pool or fd limit fast.
- **Loops** — acquisition inside a loop or recursion multiplies a single missed release.
- **Long-lived processes** — daemons and workers where leaks accumulate instead of dying with a short-lived process.

## Current state: trace release on every path (step 2)

For each acquire site, confirm the resource is released on **every** path, not only the happy one. A close on success that an exception or early `return` skips is still a leak. Release counts as guaranteed when a context manager (`with`), `defer`, `finally`, `try`-with-resources, or RAII owns it — or when ownership transfers to a caller that closes it. A bare close call on the happy path does not. Where the language has no scope-guard idiom, trace the error and early-return paths by hand.

## Sub-dimensions to sweep (step 3)

- **File handles** — files, sockets, pipes, OS descriptors opened without a scope guard.
- **Connections** — DB, HTTP, or pool connections checked out but not returned on error.
- **Contexts / locks** — locks, semaphores, transactions, or contexts acquired without a guaranteed release, also risking deadlock.
- **Subprocesses / OS handles** — spawned processes, temp files, or handles never waited on or cleaned up.

Drop low-confidence noise — a handle the runtime reclaims immediately at scope exit, or one a guard already covers, is not a finding.

## Dimension (step 4)

- **Dimension** — `resource-leak` (the sub-dimension goes in the title/evidence, e.g. "DB connection leaked on error in …", "file handle unclosed on early return in …" — never as a new top-level dimension)
- **Suggested category** — `enhancement` (guarding an acquire site against a leak); a leak already exhausting a pool or fd limit in production is a `bug`
- **Where** — the acquire site's module / type / function
- **Evidence** — the resource acquired, the path that skips release, and the under-load exposure

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
