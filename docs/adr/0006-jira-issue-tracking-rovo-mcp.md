# 0006 — Jira issue tracking via Rovo MCP: router file, category-based resolution

## Status

Accepted — extends ADR 0004 by activating the deferred split it described.

## Context

ADR 0004 established tracker-neutral skills with `GITHUB.md` as the single binding, and explicitly named the rename-or-split as "the cheap mechanical step deferred to the day a second tracker actually lands." A concrete repo now uses Jira for issues; PRs stay on GitHub. The approved Atlassian connector (Rovo MCP) is available, so the Jira side speaks through MCP tools rather than REST.

## Decision

1. **Router file.** `skills/ISSUES.md` (~10 lines) is the single point of indirection skills link to for issue mechanics. It names the selector (`$ISSUE_TRACKER`, default `github`) and routes to one of two bindings. Skills never name the selector and never link directly to a binding for issue work.

2. **Sibling binding.** A new `skills/JIRA.md` lives alongside `GITHUB.md`. `GITHUB.md` is unchanged — still authoritative for repos using GitHub for both issues and PRs. PR, branch, tag, and review-thread mechanics always live in `GITHUB.md`, regardless of selector.

3. **Rovo MCP, not REST.** `JIRA.md` names MCP tools as bindings. Authentication is handled by the MCP server; no Jira token env var on the skill side.

4. **Two config knobs.** `JIRA_CLOUD_ID` and `JIRA_PROJECT_KEY` are the only per-repo config the skills require. No transition-id config. No status-name config.

5. **Native-primitive concept mapping.** Category and structure labels map to Jira issue types (`bug` → Bug, `enhancement` → Task/Story, `epic` → Epic). Execution and closure states map to Jira statuses. Triage states (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`) stay as Jira labels — coordination flags, not workflow.

6. **Category-based resolution.** Status reads and transitions resolve by Jira's platform-stable `statusCategory.key` (`new` / `indeterminate` / `done`), never by status name or transition id. This survives any project-level workflow renaming and removes the need to cache per-project metadata.

7. **Self-contained close on merge.** `land` transitions the linked issue via the MCP after merge, gating on the issue's current category (already `done` → no-op). This covers the human-merged-in-UI path and races with the Jira-GitHub app's Smart Commit transitions identically.

8. **Issue id as opaque string; branch name is the truth-of-record link.** Skills refer to "issue \<id\>"; bindings render. Branch name carries the id verbatim (`feat/PROJ-42-slug`); `land` parses it back to identify the issue. PR title embeds the key inside the Conventional-Commits description (`feat(scope): PROJ-42 ...`), preserving CC grammar and keeping the squash-merge commit message clean. The bare key gives free Jira-GitHub-app linking without depending on the integration being installed.

9. **Per-session human auth gate.** The Rovo MCP authenticates per session via `/mcp`. `auto` treats an unauthenticated MCP as a hard stop-and-stage, the same shape as the existing `ready-for-human` HITL gate.

## Considered Options

- **Full neutral glossary file plus two binding files.** Rejected: the speculative structure ADR 0004 deliberately deferred. Skill prose is already tracker-neutral; hoisting a third file adds churn without earning its keep until a third tracker arrives.

- **Per-skill env-var resolution.** Each issue-touching `SKILL.md` resolves `$ISSUE_TRACKER` and links both bindings. Rejected: sprays the selector and binding pair across ~7 files, exactly the duplication ADR 0004 removed.

- **Transition-id config per consuming repo.** Rejected: ids are project-local and rename freely; a cached id silently goes stale when an admin reworks the workflow. Category-based resolution is fresh, project-portable, and survives renames.

- **All-as-labels mapping** (label-emulate Jira like GitHub). Rejected: an Epic rendered as a label doesn't appear as an Epic in any Jira view; status-as-label breaks JQL workflow filters. Native primitives carry semantics labels can't.

- **Depend on the Jira-GitHub Smart Commit `#close`.** Rejected: async, hard for `land` to verify, and creates dual code paths conditioned on whether the integration is installed with action permissions. The Smart-Commit linking benefit comes free from a bare key in the PR body without depending on it for state changes.

- **Title-prefixed key (`[PROJ-42] feat(...): ...`).** Rejected: breaks Conventional-Commits grammar and lands the bracketed key in `main`'s commit history after squash. Embedded in the description preserves both.

## Consequences

The selector lives in exactly one file. Adding, swapping, or splitting trackers later is a one-file edit to `ISSUES.md`. Existing GitHub-tracker repos are untouched.

Consuming Jira projects must have at least one status in each platform category (`new` / `indeterminate` / `done`) — universal in practice. They need no custom statuses or transitions configured for the skills to work.

`auto` gains one new stop condition (unauthenticated MCP). Bounded and explicit.

The affected skill set is `pickup`, `slice`, `triage`, `capture`, `land`, `patch`, `auto`. Most changes are mechanical: `<n>` → `<id>` and prose softening from "issue #N" to "the issue". Two semantic changes: `land` gains a Jira transition path; the branch-id regex in selection sites accepts both `42` and `PROJ-42` shapes.

`GITHUB.md` keeps its name and the implicit "default-tracker" reading. A consumer who picks Jira reads `JIRA.md` for issues and `GITHUB.md` for code — the file names remain literally what they describe.
