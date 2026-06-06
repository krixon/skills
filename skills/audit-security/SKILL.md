---
name: audit-security
description: Sweep a codebase for security exposure and surface each as a finding. Static-first, no scanner required. Use when the user wants a security audit, to find vulnerabilities, check authz/access control, hunt injection sinks or exposed secrets, or asks "what's exposed?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Security Audit

Find where the code leaves the system **exposed to attack**, and surface each as a finding. `audit-security` is a producer: it audits, then hands findings to `capture`. It does not file issues itself.

The aim is *risk-weighted* exposure, not a lint dump. Target weaknesses where exploitation matters.

Read the project's domain glossary (`CONTEXT.md`) and any ADRs in the area first, so finding titles use the project's vocabulary.

**Scope vs `/security-review`.** `audit-security` is a **standing-repo producer**: it sweeps the whole repo (or a focused path) on demand and emits findings for the tracker. `/security-review` is a **diff gate**: it reviews only changed code at PR time and blocks the merge. Same dimension, orthogonal trigger.

## Method: static-first

Reason from the code. Never require running a scanner — that makes the skill non-portable; if a gitleaks or semgrep report is already in the repo or CI, consume it as a signal. Missing some vulnerability classes is acceptable: the cull and `triage` are downstream gates, and the target is high-risk exposure, not completeness. No runtime/dynamic probing.

## Process

### 1. Map risk

Walk the codebase. Above ~25 files in scope, fan out `Explore` subagents (one per area) so the reads never land in the main window; at or below that, explore inline (see [../DELEGATION.md](../DELEGATION.md)). Rank code by attack surface:

- **Trust boundaries** — where untrusted input crosses in: request handlers, deserialisers, file/CLI parsers, message consumers.
- **Sensitive operations** — auth, money, data access, command/query execution, file and network egress.
- **Churn** — frequently changed code (`git log`) drifts from its original security assumptions.

### 2. Map current mitigations

For the high-risk code, find what already defends it: validation, parameterised queries, authz checks, output encoding, secret-management. A mitigation existing somewhere is not coverage — trace whether it guards *this* path. Consume a scanner report here if one exists.

### 3. Fan out finders, then score

Above the fan-out threshold, spawn parallel finder agents over the high-risk areas, each returning candidate exposures; below it, find inline. Sweep at least these sub-dimensions:

- **Vulnerable patterns** — unsafe deserialisation, weak crypto, SSRF, path traversal, missing TLS verification.
- **Authz / access control** — missing or wrong ownership checks, IDOR, privilege escalation, unguarded admin paths.
- **Injection sinks** — untrusted input reaching SQL, shell, template, or LDAP execution without parameterisation/escaping.
- **Exposed secrets** — credentials, keys, or tokens committed to the tree or logged.

Then score each candidate for **confidence** (genuinely exploitable?) and **severity** (blast radius?). Drop low-confidence noise.

### 4. Emit findings

Shape each surviving exposure into the six-field finding contract in [../capture/FINDING-FORMAT.md](../capture/FINDING-FORMAT.md):

- **Dimension** — `security` (the sub-dimension goes in the title/evidence, e.g. "SQL injection in …", "missing ownership check in …" — never as a new top-level dimension)
- **Suggested category** — usually `bug` (an exploitable weakness is a defect); a hardening that prevents a class of future exposure is an `enhancement`
- **Where** — module / type / function (path as of-audit)
- **Evidence** — the untrusted-input-to-sink path or missing guard, and why it's exploitable
- **Severity** / **Confidence** — from step 3

## Handover

Hand off per [../HANDOVER.md](../HANDOVER.md). Never file issues yourself. End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** findings (in [../capture/FINDING-FORMAT.md](../capture/FINDING-FORMAT.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
- **auto:** advance
