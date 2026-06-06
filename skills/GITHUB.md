# GitHub

Issues and PRs for this repo live in GitHub `krixon/skills`. The skills use the `gh` CLI directly — there is no tracker abstraction; skills name `gh` and the literal labels below. `gh` infers the repo from the `origin` remote when run inside this clone. This file is the command reference for the verbose incantations; short commands are spelled out inline where used.

## Body formatting

Every body passed to `gh` — issue, comment, PR description — renders as GitHub-Flavored Markdown with the newline extension on, so a newline inside a paragraph becomes a `<br>`. Never hard-wrap body prose. Write each paragraph and each list item as one unbroken physical line and let GitHub soft-wrap to the reader's viewport; separate paragraphs and list items with a blank line. Column-wrapping a body — right for commit messages, where git doesn't soft-wrap — renders here as ragged, prematurely-broken text. This is the inverse of the commit-message rule in [../WRITING.md](../WRITING.md): wrap commit bodies, never wrap tracker bodies.

## Labels

Two **category** labels: `bug`, `enhancement`.

One **structure** label (`slice` owns it):

- `epic` — a lean multi-slice parent issue holding its sliced children as sub-issues

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

## Issue relations

Parent/child and blocked-by links live in GitHub's native data model, not in issue-body prose. Both APIs key writes on an issue's internal **id**, not its issue number — resolve it with `gh api repos/{owner}/{repo}/issues/<number> --jq .id` (`{owner}/{repo}` resolve to the current repo).

- **Sub-issues** — the parent/child relation. The parent epic holds its sliced children as sub-issues.
  - **Add a child**: `gh api repos/{owner}/{repo}/issues/<parent-number>/sub_issues -F sub_issue_id=<child-id>` — `sub_issue_id` is the child's resolved id and must be a typed integer (`-F`); passing it as a string (`-f`) returns HTTP 422.
  - **List children**: `gh api repos/{owner}/{repo}/issues/<parent-number>/sub_issues --jq '.[] | {number, state}'`.
  - **Remove a child**: `gh api -X DELETE repos/{owner}/{repo}/issues/<parent-number>/sub_issue -F sub_issue_id=<child-id>`.
  - **Read a child's parent**: `gh api repos/{owner}/{repo}/issues/<child-number>/parent --jq .number` — the parent lives at the dedicated `/parent` endpoint, not as a field on the issue payload. 404s (non-zero exit) when the child has no parent.
- **Dependencies** — the blocked-by relation. An issue blocked by another can't be grabbed until the blocker closes.
  - **Add a blocker**: `gh api repos/{owner}/{repo}/issues/<number>/dependencies/blocked_by -F issue_id=<blocker-id>` — `issue_id` is the blocker's resolved id and must be a typed integer (`-F`); a string (`-f`) returns HTTP 422.
  - **List blockers**: `gh api repos/{owner}/{repo}/issues/<number>/dependencies/blocked_by --jq '.[] | {number, state}'`.
  - **List blocking** (the inverse): `gh api repos/{owner}/{repo}/issues/<number>/dependencies/blocking`.

## PR identity

Identity is configured by two env vars, so the plugin ships bot-neutral and the bot dance is a solo-dev opt-in. When `GH_PR_BOT_ACCOUNT` is set, the agent opens PRs as that machine account, never as the maintainer — GitHub forbids approving your own PR, so a separate author keeps the maintainer free to approve. Commits and branch pushes stay under the maintainer's identity (SSH `origin`); only the PR-create call switches identity, by prefixing a bot token. `GH_PR_BOT_TOKEN_CMD` is a shell command that prints that token; evaluate it inline per call so the token never persists:

```
GH_TOKEN=$(eval "$GH_PR_BOT_TOKEN_CMD") gh pr create …
```

Prefixing `GH_TOKEN` is atomic per command — it never mutates the active `gh` account, so the maintainer's session is untouched. Because the bot is the author, rework queries filter on `--author "$GH_PR_BOT_ACCOUNT"`, **not** `@me` (which resolves to the maintainer and would never match the bot's PRs).

**Unconfigured (multi-dev).** With `GH_PR_BOT_ACCOUNT` unset there is no bot dance: skills open PRs under the agent's normal identity (no `GH_TOKEN` prefix), rework and `land` queries drop the `--author` filter and match any open PR, and the `require-bot-pr.sh` hook is inert. This is the default the plugin ships; setting the two vars opts a solo-dev repo into the bot indirection.

**This repo's values**: `GH_PR_BOT_ACCOUNT=krixon-bot`, with `GH_PR_BOT_TOKEN_CMD` reading a classic PAT (`repo` scope) from the macOS Keychain — both set in `.claude/settings.json`, which holds the keychain incantation.

## PRs and rework

- **Open a PR**: `GH_TOKEN=$(eval "$GH_PR_BOT_TOKEN_CMD") gh pr create --title "..." --body "Closes #<n>"` — drop the `GH_TOKEN` prefix when `GH_PR_BOT_ACCOUNT` is unset. Opens as the bot (or normal identity); the issue stays `in-progress`; the open PR is the review state.
- **Find rework** — bot-owned PRs the maintainer has sent back with changes requested:
  `gh pr list --state open --author "$GH_PR_BOT_ACCOUNT" --json number,title,reviewDecision,headRefName,body --jq '[.[] | select(.reviewDecision == "CHANGES_REQUESTED")]'` — drop `--author` when `GH_PR_BOT_ACCOUNT` is unset, to match any open PR.
- **Read the review** — the comments that form the rework brief:
  `gh pr view <n> --comments` (or `--json reviews,comments`).
- **Update a PR**: push more commits to its branch; the open PR tracks the branch, no re-create needed.

## Review threads (questions)

A review can carry *questions* aimed at the agent, not change requests — usually a `COMMENT`-state review, so `reviewDecision` stays null and the **unresolved thread** is the signal. `pickup` triggers rework on "changes requested **or** any unresolved thread", hands questions to `field`, and resolves each thread as it posts the answer (see [pickup/SKILL.md](pickup/SKILL.md)).

- **Find unresolved threads** on a PR (run per open bot-owned PR to decide whether it needs resume):
  `gh api graphql -f query='query($owner:String!,$repo:String!,$pr:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$pr){reviewThreads(first:100){nodes{id isResolved comments(first:1){nodes{databaseId body path author{login}}}}}}}}' -F owner=<owner> -F repo=<repo> -F pr=<n> --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)'`
- **Reply to a thread** — post the converged answer onto the question's thread (`<comment-id>` is the `databaseId` of the thread's first comment from the query above): `gh api repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body="..."` (`{owner}/{repo}` resolve to the current repo).
- **Resolve a thread** after answering (`<thread-id>` is the node `id` from the query above): `gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -F id=<thread-id>`.
