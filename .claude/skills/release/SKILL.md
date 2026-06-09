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

### 3a. Render the release notes

From the **same** parsed commit set — no second scan over the range — render grouped notes. Group by Conventional-Commit type in fixed order: breaking changes first (any `!` / `BREAKING CHANGE`), then `feat`, then `fix`, then `docs`, then the remaining types. One line per commit, the line being its subject with the scope preserved (`fix(pickup): …`); no bodies, no hashes. These notes are the annotated tag's message body, and the body of the GitHub release offered in step 7.

### 4. Apply the bump

On confirmation, do the whole thing in a worktree — the repo-root checkout is never touched (see [../../../ISOLATION.md](../../../ISOLATION.md)):

1. **Sync.** `git fetch origin`. The bump must build on the current tip; if `main` moved since you derived the range, re-derive (step 1) rather than tagging a stale tip.
2. **Worktree.** `git worktree add .claude/worktrees/release-v<new> -b chore/release-v<new> origin/main`.
3. In that worktree, edit `.claude-plugin/plugin.json` `version` to the new value.
4. Commit: `chore(release): v<new>`.
5. Annotated tag on that commit, its message being the step-3a notes under a `v<new>` heading. Pass the message on a file so the grouped lines survive intact: `git tag -a v<new> -F <notes-file>` (or `-F -` from stdin). The subject line of the message is `v<new>`; the notes follow.
6. Push the bump and tag to `main` in one step: `git push origin HEAD:main --follow-tags` (a fast-forward, since the branch is based on `origin/main`). **If the push is rejected** — branch protection, or `main` moved under you — do **not** force it: tear the worktree down (step 8) and tell the maintainer. A `main` that rejects a direct push can't take a release this way.
7. **Offer the GitHub release.** Once the tag is pushed, offer to publish a GitHub release for `v<new>` carrying the step-3a notes (the command is in [../../../skills/GITHUB.md](../../../skills/GITHUB.md) → *Releases*). Offered, not automatic — `release` is human-invoked, so the publish is a separate yes. Declining skips it with no error; the tag and bump already stand on `main`.
8. **Tear down** per [../../../ISOLATION.md](../../../ISOLATION.md): `git worktree remove .claude/worktrees/release-v<new>`, then `git branch -D chore/release-v<new>`. No remote branch was created, so there's nothing to prune.

`.claude-plugin/marketplace.json` has no version field and is **not** touched.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a released version — bumped `plugin.json` and an annotated `v<new>` tag on `main` carrying grouped release notes, optionally with a GitHub release for the tag
- **default:** — (terminal; the release is cut)
- **alternatives:** stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — it makes a version-number judgment and pushes the bump straight to `main`, neither safe unattended, so `auto` never enters it.
