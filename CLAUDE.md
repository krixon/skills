# Claude Skills

A library of Claude Code agent skills, intended to ultimately be packaged and distributed as a Claude Code plugin.

@VOICE.md
@SECURITY.md

## Layout

- `skills/<skill-name>/SKILL.md` — one directory per skill; `SKILL.md` is the required entry point. Real location at the plugin root (where marketplace installs discover skills); `.claude/skills/` is a symlink to it so this repo loads them live during development.
- Optional per-skill files: `REFERENCE.md`, `EXAMPLES.md`, `scripts/`.
- `skills/HANDOVER.md` — the per-hop handover contract skills use to chain (and that `auto` walks). The skill graph lives here: trace a chain by following each skill's `default` hop. Start from the README **I want to…** table to find a chain's head.
- `skills/DELEGATION.md` — the shared rule for keeping the working window bounded by pushing interior work into subagents; referenced by the skills with heavy interiors (`auto`, `pickup`, the audits).
- `skills/AUDIT-METHOD.md` — the shared method behind the `audit-*` skills (static-first stance, the map-risk → map-current-state → fan-out-and-score → emit-finding process, the fan-out threshold, the handover row); each audit `SKILL.md` references it and adds its own risk lens, dimension, and sub-dimensions.
- `VOICE.md` — how to talk to the user in chat (imported above, always on). `WRITING.md` — how to write durable prose artifacts (commits, comments, issues, ADRs, docs); referenced by the skills that produce each. `ISOLATION.md` — how work is kept off your live checkout (read-only repo-root checkout, always a worktree, branch naming, teardown); referenced by the work-producing skills. `SECURITY.md` — the untrusted-external-content boundary (data-not-instructions, no shell interpolation); shipped always-on via the `hooks/security-boundary.sh` `UserPromptSubmit` hook (the distribution path; the `@SECURITY.md` import above is dev-local discoverability), with the command-level mechanics in `skills/GITHUB.md`.

When you add a skill, update `README.md` in the same change: add it to the **Skills** list, and update the **I want to…** table if it heads or joins a workflow chain — a new row, or an edit to an existing one.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org): `<type>[scope]: <description>`. Types: `feat fix chore docs refactor test` (same vocabulary as the branch kinds in `ISOLATION.md`). Subject in imperative mood, lower-case, no trailing period; breaking changes get a `!` before the colon or a `BREAKING CHANGE:` footer. Write the message body per `WRITING.md`.

## Pull requests

Open PRs as the configured bot account, never as the maintainer — identity comes from `GITHUB_BOT_ACCOUNT` / `GITHUB_BOT_TOKEN_CMD` (this repo: `krixon-bot`); command and rationale in `skills/GITHUB.md` → "PR identity".

## Goal

- Build out a collection of skills, then package them as a distributable Claude Code plugin (intended to add a `plugin.json`/marketplace manifest as the library matures).

## Agent skills

### Issue tracker

Issues and PRs live in GitHub `krixon/skills` via the `gh` CLI. GitHub-only, no tracker abstraction. Commands and the literal label list are in `skills/GITHUB.md`.

### Domain docs

Skills ground in whatever documentation a project already has, discovered through the in-context project `CLAUDE.md` — they impose no layout, taxonomy, or methodology. They use the project's established vocabulary, respect its recorded decisions, and surface conflicts; with nothing documented, they proceed silently. The one artifact a skill persists to the repo is an ADR, offered sparingly on the three-criteria gate and following the project's lead. This repo records its own decisions under `docs/adr/`.
