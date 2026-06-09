# Issues

The single point of indirection for issue mechanics. Skills link here — not to a tracker binding directly — for anything that creates, reads, labels, claims, relates, or closes an issue, so a second tracker plugs in by adding a binding rather than editing every issue-touching skill.

## Selector

`SKILL_TRACKER` names the binding, defaulting to `github`. The `github` default routes all issue mechanics to the issue sections of [GITHUB.md](GITHUB.md) — *Issues*, *Issue relations*, and the issue half of *Concurrency claims* (the advisory assignee claim). With no selector set, behavior is the GitHub-tracker behavior those sections define.

An issue id is opaque: skills carry it as `<id>` and never assume a shape. The `github` binding's ids are integers (`42`); a project-keyed binding's are `PROJ-42`. Branch naming follows in [ISOLATION.md](../ISOLATION.md).

## What stays in GITHUB.md

Only issue mechanics route through here. PR, branch-ref, tag, and review-thread mechanics — and PR identity — are code-hosting concerns that live in [GITHUB.md](GITHUB.md) regardless of the issue tracker, and skills link there for them directly. The literal `gh` commands and the workflow label strings stay inside `GITHUB.md` per ADR 0004; this file routes to them, it does not restate them.
