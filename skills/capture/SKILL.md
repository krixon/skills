---
name: capture
description: Turn audit findings or ad-hoc observations into needs-triage issues on the issue tracker, deduped and culled. Use when an audit skill (audit-coverage, audit-security, audit-docs) produced findings, the user says "file these as issues" / "capture what we found", or lists problems to track. For designed work use `slice`; to promote issues use `triage`.
argument-hint: "[findings to capture, or leave blank to use conversation context]"
---

# Capture

Turn **findings** into `needs-triage` issues. A pure sink — it never audits the codebase itself. It consumes findings that already exist (from an audit skill, or flagged by the user in conversation) and feeds them to the **front** of the triage pipeline. It does not write agent briefs, set `ready-for-*`, or decompose work — `triage` promotes from `needs-triage`, and `slice` handles designed work.

Issues live in GitHub; use the `gh` CLI ([../GITHUB.md](../GITHUB.md) for commands and the label list).

## What a finding is

A finding is an **un-investigated, judgment-gated observation** — an audit scored it past a confidence threshold, or a human explicitly flagged it. A raw, un-vetted suggestion is neither and should not be captured. The full contract (fields + issue body) is in [finding format](../contracts/finding.md).

## Process

### 1. Gather findings

- **Audit-fed** — an audit skill hands you findings already in `../contracts/finding.md` shape. Use them as-is.
- **Ad-hoc** — the user points at observations in the conversation, or passes them as an argument. Shape each into the six fields ([finding format](../contracts/finding.md)), inferring dimension/category/severity/confidence and confirming anything ambiguous.

If invoked cold with nothing to capture, don't start sweeping — ask what to capture, or suggest running an audit skill (`audit-coverage`, `audit-security`, `audit-docs`) first.

### 2. Dedup against open issues — before offering anything

Query open issues (`gh issue list` / search — see [../GITHUB.md](../GITHUB.md)) and match each finding against **open** issues by title and `Where`. Drop anything already tracked; never offer the user work that already exists. Flag near-matches so the user decides.

### 3. Cluster

Where several findings share one root cause, or grouping them is otherwise sensible, collapse them into one finding with an `Instances` list ([finding format](../contracts/finding.md)). Otherwise one finding = one issue.

### 4. Present for cull

Show the surviving findings as a numbered list, ordered by severity then confidence. For each: title, dimension, where, severity, confidence, and a one-line evidence summary. Mark flagged near-matches from step 2.

Ask the user which to file, which to drop, and whether any clustering should change. The cull is a **precision gate** ("is this real and worth tracking?") — it is not triage's job of deciding category/state/brief. Iterate until approved.

This is an internal gate. Run unattended (under `auto`), skip the interactive cull and file every deduped survivor with **confidence ≥ medium** — `needs-triage` is a review queue, so filing there is reversible and `triage` is the real human gate.

### 5. File survivors as `needs-triage`

For each approved finding, create an issue using the body template in [finding format](../contracts/finding.md). Apply **two labels**: `needs-triage`, and the suggested category (`bug` / `enhancement`) — front-loading `triage`'s work; `triage` overrides if the guess is wrong.

Report what was filed, with issue references, and note that `triage` will promote them from here.

## Handover

Hand off per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** `needs-triage` issues
- **default:** `triage` — promotes them out of `needs-triage`
- **alternatives:** stop
