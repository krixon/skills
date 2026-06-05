# Finding Format

The contract between an **audit** (the producer) and `capture` (the sink). Any skill that surfaces problems — `audit-coverage`, future audits, or an ad-hoc human sweep — emits findings in this shape, and `capture` consumes them.

A finding is an **un-investigated, judgment-gated observation**: something an audit scored past a confidence threshold, or a human explicitly flagged. It is NOT designed work. Keep it lean — acceptance criteria, key interfaces, and implementation steps are the *agent brief*, which `triage` writes if and when the finding is promoted. Don't pre-empt that here.

Write every prose field per [../../WRITING.md](../../WRITING.md) → *Issues & findings*: lead with the problem and impact, give a concrete location, mark assumed vs verified, no speculation dressed as fact.

## Fields

Every finding carries exactly these six fields:

- **Title** — one-line problem statement. Becomes the issue title.
- **Dimension** — which audit surfaced it: `test-gap`, `architecture`, `security`, `docs-drift`, `dead-code`, `debt`, … Drives grouping and, downstream, labels.
- **Where** — the location, named by **module / type / function**, never by line number (it goes stale — same rule as `../triage/AGENT-BRIEF.md`). A file path is allowed only as an "as-of-audit" pointer in parentheses, not as the anchor.
- **Evidence** — what was observed that makes this a real, worth-tracking problem: the untested high-risk path, the missing error case, the smell. This justifies the finding during the cull. A one-line *direction* may be appended, but not a full solution.
- **Suggested category** — `bug` or `enhancement`, mapping straight onto `triage`'s category roles.
- **Severity** — does it matter: `low` / `medium` / `high`.
- **Confidence** — how sure the audit is that it's real: `low` / `medium` / `high`.

Severity and confidence together order the cull: a high-severity, high-confidence finding leads.

## Issue body

When `capture` files a survivor, it renders this body. Severity and confidence go on **separate lines**. Examples use Python.

<finding-issue-template>

## Finding

**Dimension:** test-gap
**Suggested category:** enhancement
**Severity:** medium
**Confidence:** high

**Where:** `OrderTotals.calculate` (path as of audit: `src/orders/totals.py`)

**Evidence:**
The discount branch is never exercised — no test constructs an order with a discount, so the rounding logic there is unverified.

**Instances** *(only when clustered)*:
- `order_totals.calculate` — discount branch has no test
- `order_totals.apply_tax` — zero-rate path untested

**Source:** audit-coverage

</finding-issue-template>

- The **title** becomes the issue title.
- **Instances** appears only on a clustered issue (several findings sharing one root). Otherwise omit it.
- **Source** names the producing audit (`audit-coverage`, `audit-security`, `audit-docs`, ad-hoc) so `triage` knows this came from a sweep, not a human reporter. Undated — the tracker timestamps the issue.
