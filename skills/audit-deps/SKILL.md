---
name: audit-deps
description: Sweep a codebase for unhealthy third-party dependencies — outdated majors on load-bearing deps, versions with known advisories, abandoned upstreams, and license drift — and surface each as a finding. Static-first, reads manifests and lockfiles, no installs or tool runs required. Use when the user wants to audit dependencies, find outdated or vulnerable deps, check for abandoned upstreams, or asks "what are we depending on that's risky?".
argument-hint: "[path or manifest to focus on, or leave blank for the whole codebase]"
---

# Dependency-Health Audit

Find where the project **depends on third-party code that has gone stale, vulnerable, abandoned, or license-incompatible**, and surface each as a finding. Run the shared audit method in [../AUDIT-METHOD.md](../AUDIT-METHOD.md) with the lens, sub-dimensions, and dimension below.

The aim is *risk-weighted* dependency findings, not a raw list of every out-of-date package — target the dependencies whose staleness or exposure actually reaches the project.

## Risk lens (step 1)

Read the project's manifests and lockfiles (`package.json` / lockfile, `requirements.txt` / `poetry.lock` / `Pipfile.lock`, `go.mod` / `go.sum`, `Cargo.toml` / `Cargo.lock`, `Gemfile.lock`, and the like) and rank declared dependencies by how much their failure costs:

- **Load-bearing** — deps a core path imports directly: the web framework, the DB driver, the auth/crypto library, the parser handling untrusted input. A problem here reaches production.
- **Direct over transitive** — a direct dependency the project chose and can move; a transitive one is pinned by a parent and is the parent's finding, not a standalone one unless it carries an active advisory.
- **Exposed surface** — anything parsing, deserializing, or fetching untrusted external input, where a known advisory is reachable rather than theoretical.

## Current state: trace what actually reaches the project (step 2)

For each high-risk dependency, confirm the concern actually applies here, not just upstream in the abstract. An advisory in a code path the project never calls, a major version behind that the project pins deliberately (recorded in a comment or ADR), or a dual-licensed dep used under its permissive terms is **not** a finding. Trace the declared version against the lockfile's resolved version, and check the project's recorded decisions before flagging a deliberate pin.

## Sub-dimensions to sweep (step 3)

- **Outdated majors** — a load-bearing dependency one or more major versions behind current, where the gap accrues breaking-change and security risk.
- **Known advisories** — a resolved version matching a published security advisory. This sub-dimension needs the network (an advisory database); **degrade gracefully offline** — when the lookup is unavailable, say so and lower the confidence rather than failing the sweep.
- **Abandoned upstreams** — a dependency whose source looks unmaintained: archived repository, no release in years, an open-but-dead issue tracker. Network-dependent in the same way; degrade offline.
- **License drift** — a dependency whose license is incompatible with the project's, or that changed license in a version the project would adopt on upgrade.

Drop low-confidence noise — a dev-only dependency a major behind, or a deliberate pin the project documents, is not a finding.

## Network degradation

The manifest/lockfile analysis is fully static and always runs. The advisory- and upstream-health sub-dimensions consult the network when it's available — never as a requirement (per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Static-first*). With no network, emit the static findings, note in the run that advisory and abandonment checks were skipped, and mark any finding that would have relied on a lookup with **confidence `low`** so the cull weighs it accordingly. Package-manager audit tooling may be consulted when already present, but is never required.

## Dimension (step 4)

- **Dimension** — `deps` (the sub-dimension goes in the title/evidence, e.g. "outdated major on the DB driver in …", "known advisory in the resolved version of …" — never as a new top-level dimension)
- **Suggested category** — `enhancement` (bringing a dependency current or off an abandoned upstream); a dependency carrying a live, reachable advisory is a `bug`
- **Where** — the dependency named in the manifest, plus the manifest/lockfile as the as-of-audit pointer
- **Evidence** — the declared and resolved versions, the gap or advisory or license fact, and the load-bearing path that makes it reach the project

## Handover

Per [../AUDIT-METHOD.md](../AUDIT-METHOD.md) → *Handover*.

- **artifact:** findings (in [../contracts/finding.md](../contracts/finding.md) shape)
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`
- **alternatives:** stop (review the findings yourself first)
