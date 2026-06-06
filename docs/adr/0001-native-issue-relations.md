# 0001 — Native issue relations for parent/child and blocked-by

## Status

Accepted

## Context

`slice` cuts a PRD into child issues, each with a parent (the PRD) and zero or more blocking siblings. These links were recorded as issue-body prose: a `## Parent` section and a `## Blocked by` section. `pickup` decided grabbability by parsing the `## Blocked by` section, and nothing read the parent link — so once every child of a PRD landed, the parent PRD stayed open indefinitely.

Prose links are brittle. A free-text reference isn't machine-checkable: a renamed or renumbered issue silently rots the link, parsing depends on the exact heading, and GitHub's own views (sub-issue progress, dependency badges, the "blocked" indicator) stay blind to relations expressed only in body text. The closing of a parent has no signal to hang off.

GitHub now exposes both relations in its REST data model — sub-issues (`issues/{n}/sub_issues`) and issue dependencies (`issues/{n}/dependencies/blocked_by`) — reachable via `gh api`.

## Decision

Express parent/child and blocked-by as native GitHub relations, not body prose.

- `slice` makes each child a native **sub-issue** of the parent PRD and records each blocker as a native issue **dependency**. The child body is the bare agent brief — no `## Parent` or `## Blocked by` section.
- `pickup` sources blocked state from `dependencies/blocked_by`, skipping a slice while any blocker is open.
- `land`, after closing a child, reads the parent's `sub_issues`; when all are closed and the parent is still open it prompts the human to close the parent.

Both relation APIs key writes on an issue's internal id (not its number), passed as a typed integer (`-F issue_id` / `-F sub_issue_id`); a string returns HTTP 422. The `gh api` incantations live in `skills/GITHUB.md`.

The alternative — keeping prose and adding a parent-closing parser — was rejected: it doubles down on brittle text parsing, stays invisible to GitHub's native views, and still can't survive a renumber.

## Consequences

Grabbability and parent-completion are now machine-checked against GitHub's data model, and GitHub's native sub-issue and dependency views reflect the real graph. The relation lives in one place rather than duplicated into body text.

The change spans `slice`, `pickup`, and `land` and must ship atomically: a half-migrated pipeline — say `slice` writing native relations while `pickup` still parses prose — mis-detects blocked state.

Existing prose-linked issues are not migrated; the change is forward-looking. Writing a relation requires resolving an issue's id before the write, an extra `gh api` call per link.
