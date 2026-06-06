# Conventions

Where a project's domain docs live, and the rule for consulting them. The shared convention point skills reference rather than hard-coding paths, so the plugin works in a project with a different — or absent — doc layout.

## Default locations

- **Domain vocabulary** → `CONTEXT.md` at the repo root. In a multi-context repo, a root `CONTEXT-MAP.md` points to a per-context `CONTEXT.md` under each `src/<context>/`. Shape: [contracts/context.md](contracts/context.md).
- **Recorded decisions** → `docs/adr/`, sequential `NNNN-slug.md`. In a multi-context repo, per-context decisions live in `docs/adr/` under each `src/<context>/`; root `docs/adr/` holds system-wide decisions. Shape: [contracts/adr.md](contracts/adr.md).
- **Rejected scope** → `.out-of-scope/`, one file per concept. Shape: [triage/OUT-OF-SCOPE.md](triage/OUT-OF-SCOPE.md).

## Overriding

These are defaults. A consuming project overrides them by naming alternate locations in its own `CLAUDE.md`; a skill reads the override there and otherwise falls back to the defaults above.

## The consult rule

Before using a domain term, consult the project's vocabulary so titles and prose match the established language. Respect the recorded decisions in the area you touch.

Degrade gracefully when the docs are absent: proceed silently, and create them lazily — only when there is something to write (a term resolved, a decision made, a scope rejected). Never hard-fail on a missing doc.
