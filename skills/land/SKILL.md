---
name: land
description: Land approved pull requests — merge each approved, mergeable, bot-owned PR, strip its issue's in-progress label, then tear down the local worktree and branch. Human-invoked only. Use when the maintainer has approved a PR and wants it merged and cleaned up, says "land it" / "land the approved PRs" / "merge and clean up", or just approved a PR review.
argument-hint: "[PR number to land just that one, or leave blank to sweep every approved PR]"
---

# Land

Merge the PRs a human has **approved**, then clean up after them. `land` is the terminal hop of the implement loop: `pickup` opens a PR and stops, a human reviews and approves, and `land` executes the merge the approval authorised — then tidies the trail it leaves: strips the issue's `in-progress` label, removes the local worktree, deletes the branch.

`land` is **human-invoked only**. It never runs from `auto`, `loop`, or `schedule`: merging is outward-facing and hard to reverse, and the system keeps the final merge a human act (`land` is interactive-only — see *Autonomy* in [../HANDOVER.md](../HANDOVER.md)). The approval is the gate; `land` is the hand that turns it, not a way around it.

## Guardrails

`land` merges a PR only when it clears every one of these — anything that fails a check is skipped with the reason, never forced:

- **Approved** — `reviewDecision` is `APPROVED`. Never on `CHANGES_REQUESTED`, `REVIEW_REQUIRED`, or no review.
- **Mergeable** — `mergeable` is `MERGEABLE` and `mergeStateStatus` is `CLEAN`: no conflicts, required checks green. Skip `CONFLICTING` / `BLOCKED` / `UNKNOWN`.
- **Bot-owned** — authored by `$GH_PR_BOT_ACCOUNT`, the agent's identity (see *PR identity* in [../GITHUB.md](../GITHUB.md)). `land` does not merge a human's PR. When `GH_PR_BOT_ACCOUNT` is unset (multi-dev), there is no separate bot identity — drop this check and merge any approved, mergeable PR.

## Process

### 1. Select the PRs

- **Sweep (no argument)** — every approved, mergeable, bot-owned PR:
  `gh pr list --state open --author "$GH_PR_BOT_ACCOUNT" --json number,title,reviewDecision,mergeable,headRefName --jq '[.[] | select(.reviewDecision == "APPROVED")]'` — drop `--author` when `GH_PR_BOT_ACCOUNT` is unset, to sweep every approved PR regardless of author.
- **One PR (number passed)** — that PR alone; verify it clears the guardrails before going on.

Re-check mergeability per PR at merge time (`gh pr view <n> --json mergeable,mergeStateStatus`) — a swept list goes stale the moment `main` moves.

### 2. Confirm only when something is unusual

Default to proceeding: a single approved, mergeable, bot-owned PR lands without a prompt — the guardrails already cleared it. Pause to confirm — listing the PRs about to land, number, title, and the issue each closes — only when one of these holds:

- **Multi-PR sweep** — more than one PR will land in this invocation.
- **Stale against a moved `main`** — `main` advanced between selecting the PR and merging it (the swept list went stale, per step 1's re-check), so the approved diff now lands on a moved base. A PR that no longer re-checks `CLEAN` is skipped at the guardrail, not prompted.
- **No issue and none declared** — the PR carries neither a `Closes #` reference nor a `No-issue:` marker, so the cleanup in step 5 can't strip `in-progress` with confidence. A PR whose body leads with `No-issue:` (a `patch`, see [../patch/SKILL.md](../patch/SKILL.md)) declares the absence as intentional — that is **not** unusual; land it without a prompt.

A user who already said to land without asking waives even these.

### 3. Merge

A PR may already be **merged** — a human clicked merge in the UI. Check first (`gh pr view <n> --json state,mergedAt`); if it's merged, skip straight to cleanup. The rest of this step is for the PRs `land` itself merges.

Reduce the branch to its **logical set of commits — usually one** before it lands. Review-feedback rounds ("address review") are not logical seams; fold them in. Squash is the default:

```
gh pr merge <n> --squash --delete-branch
```

The PR title becomes the squashed commit's subject — already Conventional-Commit shaped. Only when the branch has genuinely separable logical seams — rare — keep them: reduce to just those commits and merge with `--rebase` instead. `--delete-branch` removes the remote branch — the repo does **not** auto-delete on merge — and the local branch. The PR body's `Closes #<issue>` closes the linked issue as the merge lands.

Run `land` from the repo-root checkout, which stays on `main` — not from inside the worktree you're landing. You can't remove a worktree you're standing in, nor delete a branch checked out in one; operating from the repo root keeps the cleanup in step 4 unobstructed.

### 4. Clean up locally

- **Worktree and branch** — the PR's work was isolated in a worktree on its own branch; tear it down per [../../ISOLATION.md](../../ISOLATION.md): if the head branch is checked out in a worktree (`git worktree list`), `git worktree remove <path>`, then `git branch -D <headRefName>` if `--delete-branch` left the local branch behind (it was checked out, or the merge happened in the GitHub UI). Then `git remote prune origin` — the cleanup a merged remote branch needs.
- **Local `main`** — bring the repo-root checkout (where `main` lives) current, so the next `pickup` branches from a fresh base rather than a stale one. There, `git fetch origin`, then fast-forward **only** when both guards pass — don't trust `--ff-only` to enforce them: the working tree is clean (`git status --porcelain` empty) and `main` has not diverged (`git merge-base --is-ancestor main origin/main` succeeds, so `main` is an ancestor of `origin/main`). When both hold, `git merge --ff-only origin/main`. Otherwise skip, leave `main` untouched, and name the reason in the report — dirty tree, or diverged (carries commits `origin` lacks). Never force, never create a merge commit.

### 5. Close out the issue

The `Closes #<n>` reference auto-closes the issue on merge; confirm it (`gh pr view <n> --json closingIssuesReferences`), then strip the now-spent execution label `pickup` set:

```
gh issue edit <n> --remove-label in-progress
```

If the PR's body leads with a `No-issue:` marker, it's an issue-less `patch` by design — there's no issue to close or de-label. Land it and move on; don't report it as an anomaly.

If the PR carries neither a closing reference nor a `No-issue:` marker, you can't name its issue with confidence — and stripping `in-progress` needs that same confidence. Don't touch any issue: report that the PR landed with no linked issue and no declaration, and leave it for the maintainer.

### 6. Close the parent epic when its last child lands

A sliced child is a native sub-issue of its parent epic; nothing closes that parent automatically. After closing the child, check whether it was the parent's last open child.

Read the closed child's parent, then the parent's sub-issues:

```
gh api repos/{owner}/{repo}/issues/<child-n>/parent --jq .number
gh api repos/{owner}/{repo}/issues/<parent-n>/sub_issues --jq '.[] | {number, state}'
```

The parent read 404s (non-zero exit) when the child has no parent — treat that as no parent, not an error. No parent, or the parent is already closed → nothing to do, move on. Otherwise, when **every** sub-issue is now closed and the parent is still open, prompt the maintainer to close it — `land` is human-invoked, so the prompt always faces a person. Show the sub-issue list you checked (number and state of each) and **recommend closing**: the work it tracked is complete. Close on confirmation (`gh issue close <parent-n> --comment "..."`); leave it open if declined. If any sub-issue is still open, don't prompt — the epic has children left to land.

### 7. Report

Per PR: merged ✓, its issue closed and `in-progress` stripped, worktree and branch removed — plus any PR skipped at a guardrail, named with the failing check. Note any parent epic closed (or left open at the maintainer's call) when a child was its last to land. State whether local `main` was fast-forwarded to `origin/main` or skipped, with the reason. There is nothing to hand to; the work is merged.

## Handover

Hand off per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** merged PRs — issues closed and de-labelled, branches and worktrees cleaned
- **default:** — (terminal; the work is merged and the trail is clean)
- **alternatives:** `release`, surfaced only when material commits (`feat fix refactor perf`, or a breaking change) have landed since the last `v*` tag — shown with a count (e.g. *"3 material changes since v0.1.0 — cut a release?"*); otherwise just `stop`

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — merging is the human-authorised act `auto` must not take, and the implement loop halts before it. The conditional `release` alternative does not change this: cutting a release is its own human-invoked act, never reached unattended.
