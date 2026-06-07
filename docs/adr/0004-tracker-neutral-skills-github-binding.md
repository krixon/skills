# 0004 — Skills express the workflow in tracker-neutral terms; GITHUB.md is the sole GitHub binding

## Status

Accepted — supersedes the "GitHub-only, no tracker abstraction" stance recorded in `CLAUDE.md` and `skills/GITHUB.md`.

## Context

The tracker-touching skills (`land`, `pickup`, `triage`, `slice`, `capture`, `patch`, `auto`) reason directly over GitHub constructs: they name `gh` commands, GH API objects (`sub_issues`, `dependencies/blocked_by`), and review enums (`reviewDecision == APPROVED`, `mergeStateStatus`, `CHANGES_REQUESTED`) inline. The recorded decision was deliberate: GitHub is the only tracker, so an abstraction layer would be dead weight (`GITHUB.md`: "skills name `gh` and the literal labels").

Two things make that stance worth narrowing. First, the coupling is partly redundant *today*: `slice` re-spells the full `gh api .../sub_issues` incantations inline even though it already points at `GITHUB.md` for them, and `land` reasons in raw review enums where it means the concept "approved, mergeable". That is duplication and leaked vocabulary, independent of any second tracker. Second, `0001` already established that the `gh api` incantations live in `GITHUB.md` — the single-binding-file direction is precedent, not a new idea.

This is not a decision to support a second tracker. There is none, none is planned, and the plugin's eventual distribution is only a possibility. No config selector, no adapter dispatch, no second binding file is introduced.

## Decision

Skills express the workflow in tracker-neutral terms; `GITHUB.md` is the single file that names GitHub.

The boundary, by token class:

- **`gh` commands and GH API enums/objects** (`gh pr merge`, `reviewDecision`, `sub_issues`, `mergeStateStatus`) — move out of every `SKILL.md` into `GITHUB.md`. GH-specific *semantics* that wrap a command (a parent read 404ing means "no parent"; `Closes #n` auto-closing on merge) move with the command, so the skill says "find the parent epic, if any" and `GITHUB.md` owns the quirk.
- **Workflow label strings** (`ready-for-agent`, `in-progress`, `needs-triage`, `epic`) — stay named in skills. They are the workflow's own state machine, not a GitHub artifact; the binding (they are GH labels, set via `gh issue edit`) centralizes, the names do not.
- **Concept terms** (`approved`, `mergeable`, `parent epic`, `sub-issue`, `blocked-by`) — defined once in a glossary in `GITHUB.md`, used verbatim in skills as plain prose. Backticks stay reserved for literals (commands, enums, labels); a concept rendered in backticks is the smell that a binding is leaking into the skill.

`GITHUB.md` keeps its name. It *is* the GitHub binding; renaming or splitting into a neutral glossary file plus a binding file is the cheap mechanical step deferred to the day a second tracker actually lands — doing it now is the speculative structure the original decision rightly avoided.

## Considered Options

- **Leave it (the prior decision).** Rejected: it preserves live duplication (`slice`) and leaked review enums (`land`) that have no upside even under GitHub-only.
- **Full swappable adapter now** — config-selected binding, progressive-disclosure dispatch, neutral glossary file split from the GH binding (the issue as originally filed). Rejected: speculative generality for a consumer that does not exist; it is the structure the original stance was right to refuse.
- **Tier A only** (neutralize review/state vocabulary, leave commands inline). Viable and shippable alone, but leaves the `slice` command duplication unaddressed and the seam half-drawn.

## Consequences

The decoupling lands as a benefit today — DRY, one authoritative place for GH mechanics, skills readable as workflow rather than `gh` scripting — and leaves a clean later refactor to a real adapter (swap the one binding file, add a selector) without touching skills.

The change spans ~5 `SKILL.md` files plus `GITHUB.md` and carries a half-done-seam risk: if some skills go neutral while others keep naming `gh`, a reader cannot tell which vocabulary is authoritative — worse than either pole. It must land coherently, with an acceptance check that no `SKILL.md` names a `gh` command or GH enum and `GITHUB.md` is the only namer.

`GITHUB.md` now holds tracker-neutral concept definitions despite its GitHub-specific name — a minor dissonance accepted in exchange for not carrying premature structure.
