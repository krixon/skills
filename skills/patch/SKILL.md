---
name: patch
description: Ship a small fix straight from a conversation — no tracked issue — through a worktree branch to a no-issue PR a human lands. Use when the maintainer wants a quick, obvious fix shipped now and filing an issue would be ceremony: a typo, a doc correction, a one-line config tweak, a comment cleanup. Human-invoked only. For anything needing a decision or worth tracking, use `slice`; for an issue already on the tracker, use `pickup`.
argument-hint: "[short description of the fix, or describe it in the conversation]"
---

# Patch

Ship a small fix the maintainer hands you live — no tracker issue between conversation and branch. `patch` is the issue-less twin of `pickup`: same worktree-branch-PR spine, but the contract is the conversation, not a brief, and the PR closes no issue. It exists so a typo or a one-line correction doesn't have to pass through `triage` to reach `main`.

Issues and PRs live in GitHub; use the `gh` CLI ([../GITHUB.md](../GITHUB.md)).

`patch` is **human-invoked only**. `auto` never runs it: there is no brief to run from — the fix lives only in the conversation — and no skill hands into it. The maintainer naming the fix is the authorising act.

## When it's a patch — and when it isn't

A patch is for a change small and obvious enough that a tracked issue would be pure ceremony, and that carries **no decision worth recording**. The gate, before touching anything:

- **Trivial and obvious** → patch: a typo, a stale doc line, a comment cleanup, a one-line config tweak the maintainer described.
- **Needs a decision or design** → not a patch. Stop and route to `grill` (stress-test it) or `slice` (spec it). If you'd want an ADR or a record of *why*, it isn't a patch.
- **Worth tracking, or a real bug needing diagnosis** → not a patch. File it: `slice` for designed work, `/triage` for an incoming report. `patch` leaves no tracker trail by design, so anything that should be findable later doesn't belong here.

When in doubt, it isn't a patch — the safe direction is to file an issue and let `pickup` take it.

## Process

### 1. Pin the fix

Restate the change in one line and confirm it's the whole of it. The conversation is the contract — there's no brief to fall back on, so the scope you pin here is the scope you ship. If it grows past one obvious change while you work, stop and re-route per the gate above.

### 2. Branch — in a worktree

Work in a worktree on its own branch, never the repo-root checkout (see [../../ISOLATION.md](../../ISOLATION.md)). No issue number, so the branch is `<kind>/<slug>`:

```
git worktree add .claude/worktrees/<slug> -b <kind>/<slug> main
```

Pick `<kind>` from the artifact — `fix docs chore refactor`.

### 3. Make the fix, clear the review gate

Make the change, then clear the **review gate** adapted to the artifact kind — the same gate `pickup` runs, proportional to the change:

- **code** → `/code-review` + `/security-review`.
- **skill / docs / prose** → a writing-rubric pass against [../../WRITING.md](../../WRITING.md) (plus `write-skill`'s structure check for a skill).
- **config/harness** → `verify` — does the setting take effect / the hook fire.

A one-line doc or comment fix needs only the writing pass; don't spawn heavyweight reviewers at a typo. Match the gate to the size.

### 4. Open the PR — no issue, declared

Commit (per [../../WRITING.md](../../WRITING.md)), push, open a PR **as the bot, not your active account** ([../GITHUB.md](../GITHUB.md) → *PR identity*). The body's **leading line declares the absence of an issue**, in the slot where an issue-driven PR carries `Closes #<n>`:

```
No-issue: <one-line reason this ships without a tracked issue>
```

`land` reads that marker and treats the missing issue as **expected** — no prompt, nothing to strip or close (see [../land/SKILL.md](../land/SKILL.md)). Write the rest of the body per [../GITHUB.md](../GITHUB.md). Then leave it: a human reviews and lands. Do **not** merge.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** an open no-issue PR (body led by `No-issue:`), awaiting human review
- **default:** — (terminal; a human reviews, lands via `land`, and the worktree is torn down there)
- **alternatives:** `verify` · `/code-review` · stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — `patch` runs from a live maintainer instruction with no brief, so `auto` never starts it and nothing hands into it.
