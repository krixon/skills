# 2. Release policy

Status: Accepted

## Context

`.claude-plugin/plugin.json` carried a pinned `version` with no mechanism to bump it, so the published plugin's version froze while material changes accumulated on `main`. Once the plugin is consumed from the marketplace, that leaves consumers unable to tell one release from the next.

Two placements for a bump were on the table: per-merge in `land`, or a dedicated step. Per-merge bumping races across parallel PRs — two branches landing close together compute the next version against the same base and collide — and it widens `land` from a narrow merge hop into a release tool. Bumping inside feature PRs (`pickup`) carries the same race and couples the version to a branch that may land out of order.

## Decision

Releases are **batched and cut by a dedicated `release` skill**, not bumped per-merge. One release covers the material changes landed since the previous release.

- The increment is **derived from the Conventional-Commit types** in range — `feat` → minor, `fix`/`refactor`/`perf` → patch, `!`/`BREAKING CHANGE` → breaking — and **confirmed by a human** before it applies, never silent.
- **Pre-1.0** (major `0`), a breaking change bumps minor and `feat` bumps minor; `fix` bumps patch. Cutting `1.0.0` is a manual decision, never auto-derived.
- `release` **commits the bump directly to `main` and creates an annotated `v<version>` tag** — a narrow carve-out to the "never commit to `main`" norm, guarded against a dirty or branch-protected `main`: it aborts to a release PR rather than forcing.
- Materiality excludes `docs` and `chore`; a range with no material change is a no-op, not an empty bump.

We rejected per-merge bumping in `land` and version bumping inside feature PRs for the races above, and kept `land` a narrow merge hop.

## Consequences

The annotated `v<version>` tag is the authoritative release marker — `release` computes its range from the last tag, not from `plugin.json` history. `land` surfaces `/release` after a merge once material changes have accrued, keeping releasing visible without making it automatic; no `auto`/`loop`/`schedule` path cuts a release. A published GitHub Release object and a generated changelog are deferred until marketplace consumption needs them. `.claude-plugin/marketplace.json` has no version field and stays untouched.
