# Native GitHub relations for parent/child and blocked-by issue links

`slice` decomposes a PRD into child issues, each carrying a link to its parent and to its blockers. We record those links as GitHub's native relations — parent/child as **sub-issues**, blocked-by as **issue dependencies**, reached through `gh api` — rather than as prose sections in the issue body. We chose this so the tooling can trust the link: a relation the API guarantees, not free-form text a parser has to recover.

## Considered options

- **Prose `## Parent` / `## Blocked by` sections** (the prior convention) — simple, greppable, no dependency on recent GitHub features, portable to any forge. Rejected: the link is not machine-guaranteed, so nothing could reliably decide when a parent's children were all done. The gap it left — a parent PRD that no skill ever closed — is what prompted this decision.
- **Native sub-issues + dependencies** (chosen) — machine-guaranteed relations, visible in the GitHub UI (sub-issue progress, dependency blocking), and bodies collapse to the bare agent brief.

## Consequences

- The pipeline depends on two recent GitHub features (sub-issues, issue dependencies) and the `gh api` REST endpoints behind them (`issues/{n}/sub_issues`, `issues/{n}/dependencies/blocked_by`). This is a deliberate deviation from the repo's otherwise plain-`gh` grain.
- Writing a relation takes the target issue's internal **id**, not its number — `slice` resolves the id after `gh issue create`.
- Three skills read the relations rather than the body: `slice` creates them, `pickup` reads `dependencies/blocked_by` for grabbability, `land` reads the parent's sub-issues to detect completion and prompt to close.
- Existing prose-linked issues are not migrated; the switch is forward-looking.
