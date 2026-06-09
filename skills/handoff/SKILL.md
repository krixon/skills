---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up, or resume from a pending one. Use when the user wants to hand off, wrap up, or summarise the session so a fresh agent can continue — or when a fresh session invokes /handoff to pick up where the last left off.
argument-hint: "What will the next session be used for? (write mode) — or blank in a fresh session to resume"
---

# Handoff

Carry work across a session boundary. `handoff` has two modes, and which one runs is **detected from the session, never passed as a flag**: a session carrying meaningful prior context **writes** a handoff doc; a fresh one with none **resumes** from a pending doc.

## The well-known location

Handoff docs live at a stable per-project path so neither mode needs the human to name it: `.claude/handoffs/` under the project's agent config dir (the in-context project `CLAUDE.md` names the dir if it differs). One doc per handoff, named `<UTC-timestamp>-<slug>.md` (e.g. `2026-06-09T14-30-00Z-rate-limiter.md`) so the newest sorts last and the slug reads at a glance.

This directory is the durable channel that replaces the pasted path — a writing session leaves the doc here, a resuming one finds it here. Exclude it from version control by default: ensure `.claude/handoffs/` is in `.gitignore`, since a handoff captures one session's transient state, not a repo artifact. A project wanting shared handoffs opts in by removing that line. Create the directory on first write.

## Mode detection

Decide write vs resume from whether the current session carries meaningful prior context — work done, files touched, a problem being worked:

- **Active context** → **write mode**. There is something to hand off.
- **No meaningful context** (fresh session, nothing done yet) → **resume mode** if the well-known location holds a pending doc; otherwise tell the user there's nothing to resume and stop.

Arguments describing the next session's focus are an explicit write intent — take write mode regardless.

## Write mode

Compact the conversation into a handoff doc and persist it to the well-known location.

- **Reference, don't duplicate.** Point at artifacts captured elsewhere (epics, plans, ADRs, issues, commits, diffs) by path or URL; don't restate them.
- **Suggested skills.** Include a section listing the skills the next agent should invoke to continue.
- **Redact.** Strip API keys, passwords, tokens, and personally identifiable information — the doc is durable and may be shared.
- **Tailor to the focus.** If the user passed arguments, treat them as what the next session will work on and shape the doc to it.
- Write it per [../../WRITING.md](../../WRITING.md) → *Docs*: task-first and declarative, leading with where the work stands and what's next.

Save to `.claude/handoffs/<UTC-timestamp>-<slug>.md`, creating the directory (and its `.gitignore` entry) if absent. Report the path.

## Resume mode

A fresh session picks up the most recent pending handoff with no path input:

1. **Detect.** List pending docs — the `.md` files directly under `.claude/handoffs/`, newest first; the `consumed/` subdir is the archive and never counts as pending.
2. **Offer.** One pending doc → offer to resume from it. More than one → list them (timestamp + slug) and let the user pick. None → nothing to resume; stop.
3. **Load.** Read the chosen doc and adopt it as working context: continue from where the writer left off, invoking the doc's suggested skills.
4. **Mark consumed.** Once loaded, move the doc to `.claude/handoffs/consumed/` so it is **never offered again**. Archiving over deleting keeps an audit trail; deleting also satisfies "not offered again" if the project prefers.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). `handoff` is **interactive-only** — the resume offer is a human choice with no safe unattended default, and the skill spans a session boundary — so `auto` never enters it.

- **artifact:** a persisted handoff doc (write mode), or a loaded working context (resume mode)
- **default:** — (terminal; write hands to a future session, resume to the doc's suggested skills)
- **alternatives:** stop
