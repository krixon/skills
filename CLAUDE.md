# Claude Skills

A library of Claude Code agent skills, intended to ultimately be packaged and distributed as a Claude Code plugin.

@VOICE.md

## Layout

- `skills/<skill-name>/SKILL.md` — one directory per skill; `SKILL.md` is the required entry point. Real location at the plugin root (where marketplace installs discover skills); `.claude/skills/` is a symlink to it so this repo loads them live during development.
- Optional per-skill files: `REFERENCE.md`, `EXAMPLES.md`, `scripts/`.
- `skills/HANDOVER.md` — the per-hop handover contract skills use to chain (and that `auto` walks). The skill graph lives here: trace a chain by following each skill's `default` hop. Start from the README **I want to…** table to find a chain's head.
- `skills/DELEGATION.md` — the shared rule for keeping the working window bounded by pushing interior work into subagents; referenced by the skills with heavy interiors (`auto`, `pickup`, the audits).
- `VOICE.md` — how to talk to the user in chat (imported above, always on). `WRITING.md` — how to write durable prose artifacts (commits, comments, issues, ADRs, docs); referenced by the skills that produce each. `ISOLATION.md` — how work is kept off your live checkout (read-only repo-root checkout, always a worktree, branch naming, teardown); referenced by the work-producing skills.

When you add a skill, update `README.md` in the same change: add it to the **Skills** list, and update the **I want to…** table if it heads or joins a workflow chain — a new row, or an edit to an existing one.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org): `<type>[scope]: <description>`. Types: `feat fix chore docs refactor test` (same vocabulary as the branch kinds in `ISOLATION.md`). Subject in imperative mood, lower-case, no trailing period; breaking changes get a `!` before the colon or a `BREAKING CHANGE:` footer. Write the message body per `WRITING.md`.

## Pull requests

Open PRs as the `krixon-bot` account, never as the maintainer — command and rationale in `skills/GITHUB.md` → "PR identity".

## Goal

- Build out a collection of skills, then package them as a distributable Claude Code plugin (intended to add a `plugin.json`/marketplace manifest as the library matures).

## Agent skills

### Issue tracker

Issues and PRs live in GitHub `krixon/skills` via the `gh` CLI. GitHub-only, no tracker abstraction. Commands and the literal label list are in `skills/GITHUB.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. Engineering skills read `CONTEXT.md` vocabulary and respect ADRs in the area they touch; if either is absent, proceed silently (`grill` creates them lazily).
