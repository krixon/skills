---
name: audit-security
description: Sweep a codebase for security exposure and surface each as a finding. Static-first, no scanner required. Use when the user wants a security audit, to find vulnerabilities, check authz/access control, hunt injection sinks or exposed secrets, or asks "what's exposed?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Security Audit

Find where the code leaves the system **exposed to attack**, and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *risk-weighted* exposure, not a lint dump — target weaknesses where exploitation matters.

**Scope vs `/security-review`.** `audit-security` is a **standing-repo producer**: it sweeps the whole repo (or a focused path) on demand and emits findings for the tracker. `/security-review` is a **diff gate**: it reviews only changed code at PR time and blocks the merge. Same dimension, orthogonal trigger.

## Risk lens (step 1)

Rank code by attack surface:

- **Trust boundaries** — where untrusted input crosses in: request handlers, deserialisers, file/CLI parsers, message consumers.
- **Sensitive operations** — auth, money, data access, command/query execution, file and network egress.
- **Churn** — frequently changed code (`git log`) drifts from its original security assumptions.

## Current state: map mitigations (step 2)

For the high-risk code, find what already defends it: validation, parameterised queries, authz checks, output encoding, secret-management. A mitigation existing somewhere is not coverage — trace whether it guards *this* path. Consume a scanner report here if one exists.

## Sub-dimensions to sweep (step 3)

- **Vulnerable patterns** — unsafe deserialisation, weak crypto, SSRF, path traversal, missing TLS verification.
- **Authz / access control** — missing or wrong ownership checks, IDOR, privilege escalation, unguarded admin paths.
- **Injection sinks** — untrusted input reaching SQL, shell, template, or LDAP execution without parameterisation/escaping.
- **Exposed secrets** — credentials, keys, or tokens committed to the tree or logged.

## Dimension (step 4)

- **Dimension** — `security` (the sub-dimension goes in the title/evidence, e.g. "SQL injection in …", "missing ownership check in …" — never as a new top-level dimension)
- **Suggested category** — usually `bug` (an exploitable weakness is a defect); a hardening that prevents a class of future exposure is an `enhancement`
- **Where** — the exposed module / type / function
- **Evidence** — the untrusted-input-to-sink path or missing guard, and why it's exploitable

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
