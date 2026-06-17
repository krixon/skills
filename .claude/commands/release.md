---
name: release
description: Cut a plugin version release — derive the bump from the commits landed since the last tag, push the bump plus an annotated tag to main from a worktree, then optionally publish a GitHub release. Human-invoked only. Use when the maintainer wants to release, cut a version, bump the plugin version, or publish accumulated changes; land offers it after a merge once material changes have accrued.
argument-hint: "[blank to derive the bump and confirm before applying]"
allowed-tools: Bash(*/.claude/skills/release/scripts/version:*)
---

# Release

Version the published plugin. A **release** covers the batch of material changes landed on `main` since the previous release — not one bump per merge. Releasing is distinct from landing: `land` merges a PR; `release` versions the accumulation of merges. Batching is the point — `land` offers `/release` after a merge, but the maintainer decides when enough has accrued to cut one.

`release` is **repo-local** (ADR 0005): bumping *this* plugin's version is specific to this repo, so the command and its `version` binary live under `.claude/`, outside the distributable, and never ship to plugin consumers. It is **human-invoked only**: it makes a version-number judgment and pushes the bump straight to `main`, neither safe unattended. It never runs from `auto`, `loop`, or `schedule`.

The mechanics live in the repo-local `version` binary (ADR 0008): it derives the bump from the Conventional-Commit range, applies it in a throwaway worktree, and publishes the GitHub release — all in tested code. This wrapper names only that one binary and carries the lone human decisions: when to cut a release, and whether to publish it.

## Derive

Run `version derive` and render the proposed release. Read-only:

- `${CLAUDE_PLUGIN_ROOT}/.claude/skills/release/scripts/version derive` — present the bump and the grouped notes the range carries.

!`"$CLAUDE_PLUGIN_ROOT/.claude/skills/release/scripts/version" derive --format text`

Read the result: a no-op (no material change since the last release — say so and stop, no empty bump) or an `increment` (`major` / `minor` / `patch`) with the `new_version` and the grouped `notes` it covers. Present the derived version and the material changes to the maintainer, then **wait for confirmation** — `release` never applies a bump silently.

## Apply

On confirmation, run `version apply`:

- `${CLAUDE_PLUGIN_ROOT}/.claude/skills/release/scripts/version apply` — it re-derives over the fetched `origin/main` tip (so a sibling that landed since the derive can't leave it tagging a stale range), bumps `.claude-plugin/plugin.json`, commits, annotates the `v<new>` tag with the grouped notes, and pushes the bump and tag to `main` in one fast-forward — all from a throwaway worktree it tears down regardless of outcome. On a rejected push (branch protection, or `main` moved under it) it does not force: it tears down and reports.

Render the result — `released v<new>`, or the rejection reason.

## Publish

Once the tag is on `main`, offer to publish a GitHub release for it — offered, not automatic, since `release` is human-invoked and the publish is a separate, outward-facing write. On confirmation, run `version publish`:

- `${CLAUDE_PLUGIN_ROOT}/.claude/skills/release/scripts/version publish --tag v<new>` — it publishes the release carrying the same grouped notes, passed out-of-band on stdin (pipe the notes in, never as an argument). Declining skips it with no error; the tag and bump already stand on `main`.

## Handover

Per [../skills/HANDOVER.md](../skills/HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a released version — bumped `plugin.json` and an annotated `v<new>` tag on `main` carrying grouped release notes, optionally with a GitHub release for the tag
- **default:** — (terminal; the release is cut)
- **alternatives:** stop

**Interactive-only** (per [../skills/HANDOVER.md](../skills/HANDOVER.md)) — it makes a version-number judgment and pushes the bump straight to `main`, neither safe unattended, so `auto` never enters it.
