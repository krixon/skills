---
name: audit-dead-code
description: Sweep a codebase for dead code — unreachable branches, never-called functions, orphaned modules — and surface each as a finding. Static-first, no tool run required. Use when the user wants to find dead code, hunt unreachable or unused code, find orphaned modules, or asks "what's unused?" / "what can we delete?".
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Dead-Code Audit

Find code that **can never be reached or is never referenced** — and surface each region as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *risk-weighted* removal candidates, not a raw unused-symbol dump — target regions where carrying dead code costs the most to keep or most misleads a reader.

## Risk lens: reachability and reference (step 1)

Rank candidates by the **blast radius of being wrong** — both ways. A region that *looks* live but isn't, on exported or public surface, outranks a private one-liner: it misleads every reader and agent that trusts the surface. Rank by:

- **Surface** — exported / public symbols that look like live API but have no caller outrank internal-only ones.
- **Size and reach** — an orphaned module or a large unreachable branch outranks a dead one-liner.
- **Churn** — code recently touched but never reached is a stronger removal signal than long-stable code that may have an off-tree consumer.

## Current state: confirm it's genuinely unreachable (step 2)

Before flagging, prove the region is actually dead. A reference existing *somewhere* does not make this path live; trace whether the reference reaches. Check for what keeps a symbol alive:

- **Dynamic / reflective callers** — string-keyed dispatch, registries, reflection, dependency injection, serialisation hooks.
- **Entry points** — `main`, CLI/route registration, framework lifecycle hooks, plugin manifests, scheduled jobs.
- **Test-only use** — referenced only by tests; note it, but a symbol that exists *solely* to be tested is itself a removal candidate.
- **Re-exports** — a barrel/`__init__`/index that re-exports the symbol keeps it public even with no in-tree caller.

Consume a dead-code report (a linter's unused-symbol output, coverage showing an unreached branch) as a signal here if one exists — never require running one.

## Sub-dimensions to sweep (step 3)

- **Unreachable branches** — code after an unconditional return/throw, conditions that can't be true, guards that subsume each other.
- **Never-called functions** — defined symbols with no caller, dynamic or static, and no re-export keeping them public.
- **Orphaned modules** — whole files imported by nothing and reachable from no entry point.
- **Dead config / constants** — flags, options, or constants that no code path reads.

Drop low-confidence noise — a symbol you can't confirm is unreferenced (plausible dynamic use you can't trace) is not a finding.

## Dimension (step 4)

- **Dimension** — `dead-code` (the sub-dimension goes in the title/evidence, e.g. "orphaned module …", "unreachable branch in …" — never as a new top-level dimension)
- **Suggested category** — `enhancement` (removal / cleanup); a dead path that hides a live bug — a guard that was meant to fire but can't — is a `bug`
- **Where** — the dead module / type / function
- **Evidence** — why the region is unreachable or unreferenced, the live paths you ruled out, and what removing it buys

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
