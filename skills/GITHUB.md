# GitHub

Issues and PRs for this repo live in GitHub `krixon/skills`. The skills use the `gh` CLI directly — there is no tracker abstraction; skills name `gh` and the literal labels below. `gh` infers the repo from the `origin` remote when run inside this clone. This file is the command reference for the verbose incantations; short commands are spelled out inline where used.

## Body formatting

Every body passed to `gh` — issue, comment, PR description — renders as GitHub-Flavored Markdown with the newline extension on, so a newline inside a paragraph becomes a `<br>`. Never hard-wrap body prose. Write each paragraph and each list item as one unbroken physical line and let GitHub soft-wrap to the reader's viewport; separate paragraphs and list items with a blank line. Column-wrapping a body — right for commit messages, where git doesn't soft-wrap — renders here as ragged, prematurely-broken text. This is the inverse of the commit-message rule in [../WRITING.md](../WRITING.md): wrap commit bodies, never wrap tracker bodies.

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

## PR identity

The agent opens PRs as the **`krixon-bot`** machine account, never as the maintainer — GitHub forbids approving your own PR, and the maintainer (`krixon`) is the approver. Commits and branch pushes stay under the maintainer's identity (SSH `origin`); only the PR-create call switches identity. The bot token is a classic PAT (`repo` scope) in the macOS Keychain; read it inline per command:

```
GH_TOKEN=$(security find-generic-password -s krixon-bot -w) gh pr create …
```

Prefixing `GH_TOKEN` is atomic per command — it never mutates the active `gh` account, so the maintainer's session is untouched. Because the bot is the author, rework queries filter on `--author krixon-bot`, **not** `@me` (which resolves to the maintainer and would never match the bot's PRs).

A `PreToolUse` hook (`hooks/require-bot-pr.sh`, shipped with the plugin via `hooks/hooks.json`) blocks any `gh pr create` that lacks a `GH_TOKEN=` prefix, so the rule holds even for an ad-hoc PR opened outside the skill chain. The hook is generic — inert until `GH_PR_BOT_ACCOUNT` names the bot account. This repo sets it to `krixon-bot` in `.claude/settings.json`, which also wires the hook for local dev sessions. `CLAUDE.md` carries the short form; this file is the full reference.

## PRs and rework

- **Open a PR**: `GH_TOKEN=$(security find-generic-password -s krixon-bot -w) gh pr create --title "..." --body "Closes #<n>"`. Opens as `krixon-bot`. The issue stays `in-progress`; the open PR is the review state.
- **Find rework** — bot-owned PRs the maintainer has sent back with changes requested:
  `gh pr list --state open --author krixon-bot --json number,title,reviewDecision,headRefName,body --jq '[.[] | select(.reviewDecision == "CHANGES_REQUESTED")]'`
- **Read the review** — the comments that form the rework brief:
  `gh pr view <n> --comments` (or `--json reviews,comments`).
- **Update a PR**: push more commits to its branch; the open PR tracks the branch, no re-create needed.

## Review threads (questions)

A review can carry *questions* aimed at the agent, not change requests — usually a `COMMENT`-state review, so `reviewDecision` stays null and the **unresolved thread** is the signal. `pickup` triggers rework on "changes requested **or** any unresolved thread", hands questions to `field`, and resolves each thread as it posts the answer (see [pickup/SKILL.md](pickup/SKILL.md)).

- **Find unresolved threads** on a PR (run per open bot-owned PR to decide whether it needs resume):
  `gh api graphql -f query='query($owner:String!,$repo:String!,$pr:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$pr){reviewThreads(first:100){nodes{id isResolved comments(first:1){nodes{databaseId body path author{login}}}}}}}}' -F owner=<owner> -F repo=<repo> -F pr=<n> --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)'`
- **Reply to a thread** — post the converged answer onto the question's thread (`<comment-id>` is the `databaseId` of the thread's first comment from the query above): `gh api repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body="..."` (`{owner}/{repo}` resolve to the current repo).
- **Resolve a thread** after answering (`<thread-id>` is the node `id` from the query above): `gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -F id=<thread-id>`.
