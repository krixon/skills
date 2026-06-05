# GitHub

Issues and PRs for this repo live in GitHub `krixon/skills`. The skills use the `gh` CLI directly — there is no tracker abstraction; skills name `gh` and the literal labels below. `gh` infers the repo from the `origin` remote when run inside this clone. This file is the command reference for the verbose incantations; short commands are spelled out inline where used.

## Labels

Two **category** labels: `bug`, `enhancement`.

Five maintainer **state** labels (driven through `triage`):

- `needs-triage` — needs maintainer evaluation
- `needs-info` — waiting on the reporter for more information
- `ready-for-agent` — fully specified, ready for an AFK agent
- `ready-for-human` — needs human implementation
- `wontfix` — will not be actioned

One execution **state** label (`pickup` owns it):

- `in-progress` — claimed by `pickup`, implementation underway

There is **no** review-state label. A claimed issue (`in-progress`) with an open PR *is* "in review"; once a human requests changes the PR carries that signal (see *Rework* below).

## Issues

- **Create**: `gh issue create --title "..." --body "..."` (heredoc for multi-line bodies).
- **Read**: `gh issue view <n> --comments`.
- **List**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` — add `--label` / `--state` filters as needed.
- **Comment**: `gh issue comment <n> --body "..."`.
- **Label**: `gh issue edit <n> --add-label "..."` / `--remove-label "..."`.
- **Close**: `gh issue close <n> --comment "..."`.

## PRs and rework

- **Open a PR**: `gh pr create --title "..." --body "Closes #<n>"`. The issue stays `in-progress`; the open PR is the review state.
- **Find rework** — PRs you own that a human has sent back with changes requested:
  `gh pr list --state open --author @me --json number,title,reviewDecision,headRefName,body --jq '[.[] | select(.reviewDecision == "CHANGES_REQUESTED")]'`
- **Read the review** — the comments that form the rework brief:
  `gh pr view <n> --comments` (or `--json reviews,comments`).
- **Update a PR**: push more commits to its branch; the open PR tracks the branch, no re-create needed.
