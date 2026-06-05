---
name: setup-skills
description: Scaffold the per-repo config (issue tracker, triage labels, domain doc layout) that the engineering skills assume. Run once before first using the issue, audit, or planning skills.
disable-model-invocation: true
---

# Setup Skills

Scaffold the per-repo configuration that the engineering skills assume:

- **Issue tracker** — the GitHub repo whose Issues hold this repo's work (via the `gh` CLI)
- **Triage labels** — the strings used for the seven canonical state roles
- **Domain docs** — where `CONTEXT.md` and ADRs live, and the consumer rules for reading them

This is prompt-driven, not a deterministic script. Explore, present what you found, confirm with the user, then write.

## Process

### 1. Explore

Read the repo's starting state. Read whatever exists; don't assume:

- `git remote -v` and `.git/config` — is this a GitHub repo? Which one?
- `AGENTS.md` and `CLAUDE.md` at the repo root — does either exist? Is there already an `## Agent skills` section in either?
- `CONTEXT.md` and `CONTEXT-MAP.md` at the repo root
- `docs/adr/` and any `src/*/docs/adr/` directories
- `docs/agents/` — does this skill's prior output already exist?

### 2. Present findings and ask

Summarise what's present and what's missing. Then walk the user through the three decisions **one at a time** — present a section, get the user's answer, then move to the next. Don't dump all three at once.

Assume the user does not know what these terms mean. Each section starts with a short explainer (what it is, why these skills need it, what changes if they pick differently). Then show the choices and the default.

**Section A — Issue tracker.**

> Explainer: the GitHub repo whose Issues hold this repo's work. `slice`, `triage`, `capture`, and `to-prd` read and write it via the `gh` CLI.

These skills track work in GitHub Issues. Read `git remote -v`: if a remote points at GitHub, propose that repo. Confirm it (the user may want a different repo, e.g. a separate tracker repo). If there's no GitHub remote, ask for the `owner/repo` to use; `gh` must be authenticated against it.

**Section B — Triage label vocabulary.**

> Explainer: `triage` and `pickup` move an issue through a state machine by applying labels. Map the canonical roles here to the strings your repo actually uses (e.g. `bug:triage` for `needs-triage`) so the skills apply existing labels instead of creating duplicates.

The seven canonical state roles — the maintainer drives the first five via `triage`, `pickup` drives the last two:

- `needs-triage` — maintainer needs to evaluate
- `needs-info` — waiting on reporter
- `ready-for-agent` — fully specified, AFK-ready (an agent can pick it up with no human context)
- `ready-for-human` — needs human implementation
- `wontfix` — will not be actioned
- `in-progress` — claimed by `pickup`, implementation underway
- `in-review` — PR open, awaiting human merge

Default: each role's string equals its name. Ask whether they want to override any. If their issue tracker has no existing labels, the defaults are fine — step 4 creates whichever of the seven are missing, so the tracker is ready for the first `capture`.

**Section C — Domain docs.**

> Explainer: `deepen`, `diagnose`, and `tdd` read `CONTEXT.md` for the project's domain language and `docs/adr/` for past decisions. They need to know whether the repo has one context or several, to look in the right place.

Confirm the layout:

- **Single-context** — one `CONTEXT.md` + `docs/adr/` at the repo root. Most repos are this.
- **Multi-context** — `CONTEXT-MAP.md` at the root pointing to per-context `CONTEXT.md` files (typically a monorepo).

### 3. Confirm and edit

Show the user a draft of:

- The `## Agent skills` block to add to whichever of `CLAUDE.md` / `AGENTS.md` is being edited (see step 4 for selection rules)
- The contents of `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md`

Let them edit before writing.

### 4. Write

**Pick the file to edit:**

- If `CLAUDE.md` exists, edit it.
- Else if `AGENTS.md` exists, edit it.
- If neither exists, ask the user which one to create — don't pick for them.

Never create `AGENTS.md` when `CLAUDE.md` already exists (or vice versa) — always edit the one that's already there.

If an `## Agent skills` block already exists in the chosen file, update its contents in-place rather than appending a duplicate. Don't overwrite user edits to the surrounding sections.

The block:

<agent-skills-template>

## Agent skills

### Issue tracker

[one-line summary of where issues are tracked]. See `docs/agents/issue-tracker.md`.

### Triage labels

[one-line summary of the label vocabulary]. See `docs/agents/triage-labels.md`.

### Domain docs

[one-line summary of layout — "single-context" or "multi-context"]. See `docs/agents/domain.md`.

</agent-skills-template>

Then write the three docs files using the seed templates in this skill folder as a starting point:

- [ISSUE-TRACKER-GITHUB.md](ISSUE-TRACKER-GITHUB.md) — GitHub issue tracker (record the `owner/repo`)
- [TRIAGE-LABELS.md](TRIAGE-LABELS.md) — label mapping
- [DOMAIN-DOCS.md](DOMAIN-DOCS.md) — domain doc consumer rules + layout

**Then bootstrap the labels in the tracker.** The docs file records what the strings *mean*; the tracker still needs the labels to *exist*, or the first `capture`/`triage`/`pickup` call walls when `gh issue create --label …` / `gh issue edit --add-label …` hits a missing label. List the tracker's labels (`gh label list`) and create any of the seven role strings not already present (`gh label create <string> --description "<role meaning>"`). Idempotent: skip labels that exist, never duplicate, and leave labels the repo uses for other purposes untouched.

### 5. Done

Tell the user setup is complete and which engineering skills read from these files. They can edit `docs/agents/*.md` directly later — re-run this skill only to switch issue trackers or restart from scratch.
