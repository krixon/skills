---
name: patch
description: Ship a small fix straight from a conversation — no tracked issue — through a worktree branch to a no-issue PR a human lands. Use when the maintainer wants a quick, obvious fix shipped now and filing an issue would be ceremony: a typo, a doc correction, a one-line config tweak, a comment cleanup. Human-invoked only. For anything needing a decision, use `design`; for work worth tracking, use `slice`; for an issue already on the tracker, use `pickup`.
argument-hint: "[short description of the fix, or describe it in the conversation]"
---

# Patch

Ship a small fix the maintainer hands you live, through a worktree branch to a no-issue PR a human lands. The contract is the conversation, not a brief — so a typo or a one-line correction reaches `main` without a tracked issue.

PRs live in GitHub (see [../GITHUB.md](../GITHUB.md)).

`patch` is **human-invoked only**. `auto` never runs it: the fix lives only in the conversation, with no brief to run from. The maintainer naming the fix is the authorising act.

## When it's a patch — and when it isn't

A patch is for a change small and obvious enough that a tracked issue would be ceremony, carrying **no decision worth recording**. The gate, before touching anything:

- **Trivial and obvious** → patch: a typo, a stale doc line, a comment cleanup, a one-line config tweak the maintainer described.
- **Needs a decision or design** → not a patch. Stop and route to `design`.
- **Worth tracking** → not a patch. File it: `/capture` for an observation, `/triage` for an incoming report. `patch` leaves no tracker trail by design, so anything that should be findable later doesn't belong here.

When in doubt, it isn't a patch.

## Process

### 1. Pin the change

Restate the change in one line and confirm it's the whole of it. The conversation is the contract — the scope you pin here is the scope you ship. If it grows past one obvious change while you work, stop and re-route per the gate above.

### 2. Isolate

Work in a worktree on its own branch, never the repo-root checkout (see [../../ISOLATION.md](../../ISOLATION.md)). There's no issue number, so the branch is `<kind>/<slug>`.

### 3. Make the change

Then clear the **review gate** adapted to the artifact kind, proportional to the change:

- **code** → `/code-review` + `/security-review`.
- **skill / docs / prose** → a writing-rubric pass against [../../WRITING.md](../../WRITING.md) (plus `write-skill`'s structure check for a skill).
- **config/harness** → `verify` — does the setting take effect / the hook fire.

A one-line doc or comment fix needs only the writing pass; don't spawn heavyweight reviewers at a typo. Match the gate to the size.

### 4. Open the PR

Commit (per [../../WRITING.md](../../WRITING.md)), push, open a PR **as the configured bot identity when one is set** ([../GITHUB.md](../GITHUB.md) → *PR identity* — unconfigured, your normal identity applies). Lead the body with a marker declaring the absence of an issue, where an issue-driven PR would carry a closing reference to its issue:

```
No-issue: <one-line reason this ships without a tracked issue>
```

`land` reads that marker and treats the missing issue as **expected**. Write the rest of the body per [../GITHUB.md](../GITHUB.md). Then leave it: a human reviews and lands. Do **not** merge.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** an open no-issue PR (body led by `No-issue:`), awaiting human review
- **default:** — (terminal; a human reviews, lands via `land`, and the worktree is torn down there)
- **alternatives:** `verify` · `/code-review` · stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — `auto` never starts it and nothing hands into it.
