---
name: cover
description: Audit a codebase for high-risk untested paths and surface them as findings. Static-first, no instrumented coverage run required. Use when the user wants to find test gaps, audit coverage, find untested critical paths, or asks "what's not tested?". Architecture counterpart is `deepen`; both feed `capture`.
argument-hint: "[path or area to focus on, or leave blank for the whole codebase]"
---

# Cover

Find where the test suite leaves **high-risk paths unexercised**, and surface each as a finding. `cover` is a producer: it audits, then hands findings to `capture`, which dedups, culls, and files them as `needs-triage` issues. It does not file issues itself.

The aim is *risk-weighted* gaps, not raw uncovered-line count — a flood of trivial misses is noise. Target paths where being untested matters.

Read the project's domain glossary (`CONTEXT.md`) and any ADRs in the area first, so finding titles use the project's vocabulary.

## Method: static-first

Reason from the code and the tests. If the repo already produces a coverage report, consume it as a signal — but never require running an instrumented pass (it's language- and project-specific, slow, and often broken; mandating it makes the skill non-portable). The risk of static reasoning missing runtime-only paths is acceptable: the cull and `triage` are downstream gates, and the target is high-risk gaps, not completeness.

## Process

### 1. Map risk

Walk the codebase. Above ~25 files in scope, fan out `Explore` subagents (one per area) so the reads never land in the main window; at or below that, explore inline for visibility (see *Context & delegation* in [../WORKFLOWS.md](../WORKFLOWS.md)). Rank code by risk:

- **Criticality** — money, auth, data integrity, external side effects.
- **Complexity** — branchy logic, error handling, edge cases.
- **Churn** — frequently changed code (`git log`) breaks more often.

### 2. Map coverage

For the high-risk code, find what the tests exercise. A test file existing for a module is not coverage — trace which *branches and error paths* are hit. Consume a coverage report here if one exists.

### 3. Fan out finders, then score

Following the `code-review` pattern: above the fan-out threshold, spawn parallel finder agents over the high-risk areas, each returning candidate gaps; below it, find inline. Then, for each candidate, a separate scoring pass assigns **confidence** (is this genuinely untested?) and **severity** (does the gap matter?). Drop low-confidence noise.

### 4. Emit findings

Shape each surviving gap into the six-field finding contract in [../capture/FINDING-FORMAT.md](../capture/FINDING-FORMAT.md):

- **Dimension** — `test-gap`
- **Suggested category** — usually `enhancement` ("add coverage for X"); a gap that already masks a likely defect is a `bug`
- **Where** — module / type / function (path as of-audit)
- **Evidence** — the untested high-risk path and why it matters
- **Severity** / **Confidence** — from step 3

## Handover

Hand off per [../HANDOVER.md](../HANDOVER.md). Never file issues yourself. End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** findings (in [../capture/FINDING-FORMAT.md](../capture/FINDING-FORMAT.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
- **auto:** advance
