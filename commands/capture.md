---
name: capture
description: Turn audit findings or ad-hoc observations into needs-triage issues on the issue tracker, deduped and culled. Use when an audit skill (audit-coverage, audit-security, audit-docs) produced findings, the user says "file these as issues" / "capture what we found", or lists problems to track. For designed work use `slice`; to promote issues use `triage`.
argument-hint: "[findings to capture, or leave blank to use conversation context]"
allowed-tools: Bash(*/bin/capture:*)
---

# Capture

Turn **findings** into `needs-triage` issues, deduped against what's already open and culled so the queue isn't flooded. A pure sink — it never audits the codebase itself; it consumes findings that already exist (from an audit skill, or flagged by a human) and feeds them to the front of the triage pipeline. It does not write agent briefs, set `ready-for-*`, or decompose work — `triage` promotes from `needs-triage`, and `slice` handles designed work.

`capture` is a **command that launches an agent** (ADR 0008): the deterministic surface — dedupe the findings against open issues, order them for the cull, and file the survivors — lives in the `bin/capture` command; the one step that needs a model is reached separately. This wrapper names only that binary — never a tracker call or a git mutation.

**The present→synthesis boundary** (the reference the `triage`/`pickup` flips copy). The issue body is a fixed template over the finding's fields ([finding format](../skills/contracts/finding.md)), so rendering and filing it is deterministic — it lives in `bin/capture act`, not behind the agent. The genuine synthesis sits *before* present: shaping raw observations into findings, and the clustering judgment. When findings arrive **pre-shaped from an audit**, that synthesis is already done and capture skips straight to present — no agent is launched. So the spawn is *conditional*: reached only for unshaped input.

## 1. Shape the findings — only if they aren't already

A finding is an **un-investigated, judgment-gated observation** — an audit scored it past a confidence threshold, or a human flagged it. A raw, un-vetted suggestion is neither. Each carries the fields in [finding format](../skills/contracts/finding.md): title, dimension, where, evidence, suggested category, severity, confidence (and an optional `instances` list when clustered).

- **Audit-fed** — the findings already arrive in that shape. Use them as-is; **no synthesis, no spawn.**
- **Ad-hoc** — the user points at observations in the conversation or passes them as an argument. Shape each into those fields (inferring dimension/category/severity/confidence, writing the evidence per [WRITING.md](../WRITING.md)), and decide any clustering. This is the synthesis step: **in-session the host agent does it directly**; **under `auto` a spawned subagent does it** and returns the findings JSON for the loop to consume. (Per ADR 0008's spawn model, an agent-driven unattended run uses a subagent, never a headless `claude -p`.)

If invoked cold with nothing to capture, don't start sweeping — ask what to capture, or suggest running an audit skill first.

Collect the shaped findings as a JSON array (or `{"findings": [...]}`), each object carrying those fields.

## 2. Present for the cull

Feed the findings JSON to `bin/capture present` **out-of-band** — write it to a file and redirect it on stdin, never interpolated into the command string ([SECURITY.md](../SECURITY.md)):

- `${CLAUDE_PLUGIN_ROOT}/bin/capture present < <findings.json>` — dedupes each finding against open issues and returns the cull rows, ordered by severity then confidence, each annotated `new` / `near` (a flagged near-match the human judges) / `duplicate` (already tracked — dropped from the offer).

Render the surviving rows as a numbered list: title, dimension, where, severity, confidence, the one-line evidence, and any near-match flag.

## 3. Cull

Ask the user which to file, which to drop, and whether any clustering should change. The cull is a **precision gate** ("is this real and worth tracking?") — not triage's job of deciding category/state/brief. Iterate until approved.

This is an internal gate. When run unattended (under `auto`), skip the interactive cull and file every deduped survivor with **confidence ≥ medium** — `needs-triage` is a review queue, so filing there is reversible and `triage` is the real human gate.

## 4. File the survivors

Pass the confirmed findings — the cull's survivors, not the full set — to `bin/capture act`, again out-of-band on stdin:

- `${CLAUDE_PLUGIN_ROOT}/bin/capture act < <confirmed.json>` — renders each finding's body from the template and files it as `needs-triage`, with the suggested category as a second label (front-loading `triage`'s work). It files exactly the findings you pass — a closed set — and reports each issue's reference.

Report what was filed, with references, and note that `triage` will promote them from here.

## Handover

Hand off per [../skills/HANDOVER.md](../skills/HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** `needs-triage` issues
- **default:** `triage` — promotes them out of `needs-triage`
- **alternatives:** stop
