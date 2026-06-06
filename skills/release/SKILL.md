---
name: release
description: Cut a plugin version release — bump plugin.json, commit to main, and create an annotated tag — covering the batch of material changes landed since the previous release. Human-invoked only. Use when the maintainer wants to release, cut a version, bump the plugin version, or publish accumulated changes; land offers it after a merge once material changes have accrued.
argument-hint: "[target version to override the derived bump, or blank to derive it]"
---

# Release

Version the published plugin. A **release** covers the batch of material changes landed on `main` since the previous release — not one bump per merge. Releasing is distinct from landing: `land` merges a PR; `release` versions the accumulation of merges. Batching is the point — `land` offers `/release` after a merge, but the maintainer decides when enough has accrued to cut one.

`release` is **human-invoked only**: it makes a version-number judgment and commits directly to `main`, neither safe unattended. It never runs from `auto`, `loop`, or `schedule`.

## Process

### 1. Determine the range

The previous release is marked by an annotated git tag `v<version>` that `release` created — the authoritative marker, not `plugin.json` history. The range is `<last-tag>..main`. With no tag yet, it is all of `main` through HEAD.

### 2. Filter for materiality

Walk the Conventional-Commit subjects of the merges in range (`git log <last-tag>..main --first-parent`). **Material:** `feat fix refactor perf`, and any `!` / `BREAKING CHANGE`. **Non-material:** `docs chore`. If nothing material landed, `release` is a **no-op** — say so and stop. No empty bump.

### 3. Derive the increment, then confirm

Suggest the bump; never apply it silently:

- any `!` / `BREAKING CHANGE` → breaking
- else any `feat` → minor
- else (`fix` / `refactor` / `perf`) → patch

**Pre-1.0 rule** (while major is `0`): a breaking change bumps **minor** (`0.1.0`→`0.2.0`), `feat` bumps minor, `fix` bumps patch. Cutting `1.0.0` is a deliberate **manual** call — never auto-derived; the maintainer asks for it explicitly.

Present the derived version and the material changes it covers, then wait for confirmation. A version passed as the argument overrides the derived bump (still confirmed).

### 4. Apply the bump

On confirmation:

1. **Guard `main`.** It must be clean and current: abort if `git status --porcelain` is non-empty, and `git fetch` then confirm `main` has not diverged from `origin/main`. If it is dirty or diverged, abort and tell the maintainer to land a release PR instead.
2. Edit `.claude-plugin/plugin.json` `version` to the new value.
3. Commit directly to `main`: `chore(release): v<new>`. This is the standard release-commit carve-out to the "never commit to `main`" norm (see [../../ISOLATION.md](../../ISOLATION.md)).
4. Create an annotated tag: `git tag -a v<new> -m "v<new>"`.
5. Push the commit and tag. **If the push is rejected** (branch protection), do **not** force it — undo the local commit (`git reset --hard origin/main`) and direct the maintainer to land a release PR.

`.claude-plugin/marketplace.json` has no version field and is **not** touched.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a released version — bumped `plugin.json` and an annotated `v<new>` tag on `main`
- **default:** — (terminal; the release is cut)
- **alternatives:** stop
- **auto:** never — it makes a version-number judgment and takes the `main`-commit carve-out, neither safe unattended.
