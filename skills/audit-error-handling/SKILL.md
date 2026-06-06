---
name: audit-error-handling
description: Sweep a codebase for error-handling defects — swallowed errors, bare catch-alls, and critical calls with no failure path — and surface each as a finding. Static-first, no linter required. Use when the user wants to find swallowed errors, check error handling, hunt empty catch blocks, or asks "what happens when this fails?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Error-Handling Audit

Find where the code **drops, masks, or ignores a failure**, and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *risk-weighted* error-handling quality, not a lint dump — target sites where an unhandled failure does real damage.

**Scope vs `audit-coverage`.** This judges error-handling *quality* — whether a failure is caught, surfaced, and recovered — not whether a path is *tested*. A swallowed error is a finding here even with a passing test suite; a missing test for an otherwise-sound handler belongs to `audit-coverage`. Do not duplicate test-gap findings.

## Risk lens (step 1)

Rank catch/except sites and failure-prone calls by the **blast radius of an unhandled failure**:

- **Critical paths** — money, auth, data-loss/integrity, irreversible external side effects. A swallowed failure here corrupts state or loses data silently.
- **Failure-prone calls** — I/O, network, deserialisation, subprocess, third-party APIs: calls that *will* fail in production.
- **Churn** — frequently changed code (`git log`) accretes hasty `try`/`catch` that drifts from sound handling.

## Current state: trace the failure path (step 2)

For each suspect site, confirm the error is **genuinely swallowed** before it counts — not logged, not rethrown, not handled by an upstream or downstream boundary. A handler existing *elsewhere* does not make this site safe: trace whether it reaches.

- Does an outer boundary catch it — middleware, an error decorator, a supervising caller, a framework default?
- Is the error surfaced to someone who can act — logged with context, returned, raised — or does control continue as if nothing failed?
- Is the catch scoped to what it can handle, or does it absorb everything including bugs it never anticipated?

A site whose failure is caught and acted on by a boundary that provably covers it is not a finding.

## Sub-dimensions to sweep (step 3)

- **Swallowed errors** — empty catch/except, catch-and-continue, errors logged-then-ignored where the caller proceeds on corrupt state, discarded return-code/error values.
- **Bare catch-alls** — `catch (Exception)` / bare `except:` / `catch (Throwable)` that masks failures it cannot handle, hiding bugs and making the system unobservable.
- **No failure path** — a critical call with no handling at all where an exception unwinds to an unsafe place (partial write, held lock, half-applied transaction), or a failure-prone call whose error is structurally impossible to observe.

Drop low-confidence noise — a deliberately-ignored error with a comment saying why, or a catch-all at a legitimate top-level boundary, is not a finding.

## Dimension (step 4)

- **Dimension** — `error-handling` (the sub-dimension goes in the title/evidence, e.g. "swallowed error in …", "bare catch-all masks …" — never as a new top-level dimension)
- **Suggested category** — `enhancement` (this is hardening a fragile path); a swallowed error that already produces wrong behavior or silent data loss is a `bug`
- **Where** — the swallowing module / type / function
- **Evidence** — the dropped/masked failure, the blast radius if it fires, and confirmation that no reachable boundary handles it

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
