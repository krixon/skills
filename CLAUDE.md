# Claude Skills

A library of Claude Code agent skills, intended to ultimately be packaged and distributed as a Claude Code plugin.

@VOICE.md

## Layout

- `skills/<skill-name>/SKILL.md` — one directory per skill; `SKILL.md` is the required entry point. Real location at the plugin root (where marketplace installs discover skills); `.claude/skills/` is a symlink to it so this repo loads them live during development.
- Optional per-skill files: `REFERENCE.md`, `EXAMPLES.md`, `scripts/`.
- `skills/WORKFLOWS.md` — how the skills compose into the dev loop: named workflows and where each runs unattended. Start here to understand the pipeline.
- `skills/HANDOVER.md` — the per-hop handover contract skills use to chain (and that `auto` walks).
- `VOICE.md` — how to talk to the user in chat (imported above, always on). `WRITING.md` — how to write durable prose artifacts (commits, comments, issues, ADRs, docs); referenced by the skills that produce each. `ISOLATION.md` — how work is kept off the default branch and out of your live checkout (branch-first, naming, branch vs worktree); referenced by the work-producing skills.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org): `<type>[scope]: <description>`. Types: `feat fix chore docs refactor test` (same vocabulary as the branch kinds in `ISOLATION.md`). Subject in imperative mood, lower-case, no trailing period; breaking changes get a `!` before the colon or a `BREAKING CHANGE:` footer. Write the message body per `WRITING.md`.

## Pull requests

Always open PRs as the `krixon-bot` machine account, never as the maintainer — GitHub forbids approving your own PR, and `krixon` is the approver. This holds for ad-hoc PRs too, not only those opened through a skill: `GH_TOKEN=$(security find-generic-password -s krixon-bot -w) gh pr create …`. Commits and pushes stay under `krixon`; only the `pr create` call switches identity. A `PreToolUse` hook (`hooks/require-bot-pr.sh`, shipped with the plugin) blocks any `gh pr create` lacking a `GH_TOKEN=` prefix; it activates off the `GH_PR_BOT_ACCOUNT` env var, set to `krixon-bot` for this repo in `.claude/settings.json`. The hook is generic — the `krixon-bot` binding lives only in that local settings file, never in the distributed plugin. Full reference: `skills/GITHUB.md` → "PR identity".

## Goal

- Build out a collection of skills, then package them as a distributable Claude Code plugin (intended to add a `plugin.json`/marketplace manifest as the library matures).

## Agent skills

### Issue tracker

Issues and PRs live in GitHub `krixon/skills` via the `gh` CLI. GitHub-only, no tracker abstraction. Commands and the literal label list are in `skills/GITHUB.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. Engineering skills read `CONTEXT.md` vocabulary and respect ADRs in the area they touch; if either is absent, proceed silently (`grill-with-docs` creates them lazily).
