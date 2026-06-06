# Audit Method

The shared method behind the `audit-*` skills. Each audit (`audit-coverage`, `audit-security`, `audit-docs`) fills in its own **risk lens**, **current-state pass**, and **dimension**; everything common — the producer stance, the static-first method, the four-step process, the fan-out threshold, and the finding contract — lives here once.

An audit is a **producer**: it sweeps the repo (or a focused path), then hands findings to `capture`, which dedups against open issues, culls, and files survivors as `needs-triage`. It never files issues itself.

The aim is *risk-weighted* findings, not a raw dump — a flood of trivial hits is noise. Target the cases where the problem matters.

Consult the project's domain vocabulary and recorded decisions first (per [CONVENTIONS.md](CONVENTIONS.md)), so finding titles use the project's vocabulary.

## Static-first

Reason from the artifacts already in the tree — the code, the tests, the prose. If a relevant report is already present (a coverage report, a `gitleaks`/`semgrep` scan, CI output), consume it as a signal, but never *require* running a tool: an instrumented or scanner pass is language- and project-specific, slow, and often broken, and mandating it makes the skill non-portable. Missing some cases is acceptable — the cull and `triage` are downstream gates, and the target is high-risk findings, not completeness. No runtime or dynamic probing.

## Process

### 1. Map risk

Walk the codebase through the audit's risk lens. Above ~25 files in scope, fan out `Explore` subagents (one per area) so the reads never land in the main window; at or below that, explore inline for visibility (see [DELEGATION.md](DELEGATION.md)). Rank what you find by risk so the sweep targets where being wrong costs the most.

### 2. Map the current state

For the high-risk code, find what already addresses the audit's concern — the tests that exercise it, the mitigations that guard it, the code that should back a claim. A defence existing *somewhere* is not the same as guarding *this* path: trace whether it actually applies here. Consume a relevant report at this step if one exists.

### 3. Fan out finders, then score

Above the fan-out threshold (~25 files), spawn parallel finder agents over the high-risk areas — following the `code-review` pattern — each returning candidate findings; below it, find inline. Then a separate scoring pass assigns each candidate a **confidence** (is this genuinely a problem?) and a **severity** (does it matter?). Drop low-confidence noise.

### 4. Emit findings

Shape each surviving finding into the six-field finding contract in [contracts/finding.md](contracts/finding.md): **dimension**, **suggested category**, **where** (module / type / function, path as of-audit), **evidence**, **severity**, **confidence**. Each audit states its own dimension value and how it picks a category; severity and confidence come from step 3.

## Handover

Every audit hands off identically. Hand off per [HANDOVER.md](HANDOVER.md); never file issues yourself. End an interactive run by rendering the row as one `AskUserQuestion`.

- **artifact:** findings (in [contracts/finding.md](contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
