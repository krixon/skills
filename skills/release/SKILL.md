---
name: release
description: Cut a plugin version release — bump plugin.json and push the bump plus an annotated tag to main from a worktree — covering the batch of material changes landed since the previous release. Human-invoked only. Use when the maintainer wants to release, cut a version, bump the plugin version, or publish accumulated changes; land offers it after a merge once material changes have accrued.
argument-hint: "[target version to override the derived bump, or blank to derive it]"
---

# Release

Version the published plugin. A **release** covers the batch of material changes landed on `main` since the previous release — not one bump per merge. Releasing is distinct from landing: `land` merges a PR; `release` versions the accumulation of merges. Batching is the point — `land` offers `/release` after a merge, but the maintainer decides when enough has accrued to cut one.

`release` is **human-invoked only**: it makes a version-number judgment and pushes the bump straight to `main`, neither safe unattended. It never runs from `auto`, `loop`, or `schedule`.

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

On confirmation, do the whole thing in a worktree — the repo-root checkout is never touched (see [../../ISOLATION.md](../../ISOLATION.md)):

1. **Sync.** `git fetch origin`. The bump must build on the current tip; if `main` moved since you derived the range, re-derive (step 1) rather than tagging a stale tip.
2. **Worktree.** `git worktree add .claude/worktrees/release-v<new> -b chore/release-v<new> origin/main`.
3. In that worktree, edit `.claude-plugin/plugin.json` `version` to the new value.
4. Commit: `chore(release): v<new>`.
5. Annotated tag on that commit: `git tag -a v<new> -m "v<new>"`.
6. Push the bump and tag to `main` in one step: `git push origin HEAD:main --follow-tags` (a fast-forward, since the branch is based on `origin/main`). **If the push is rejected** — branch protection, or `main` moved under you — do **not** force it: tear the worktree down (step 7) and tell the maintainer. A `main` that rejects a direct push can't take a release this way.
7. **Tear down** per [../../ISOLATION.md](../../ISOLATION.md): `git worktree remove .claude/worktrees/release-v<new>`, then `git branch -D chore/release-v<new>`. No remote branch was created, so there's nothing to prune.

`.claude-plugin/marketplace.json` has no version field and is **not** touched.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a released version — bumped `plugin.json` and an annotated `v<new>` tag on `main`
- **default:** — (terminal; the release is cut)
- **alternatives:** stop
- **auto:** never — it makes a version-number judgment and pushes the bump straight to `main`, neither safe unattended.
