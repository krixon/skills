---
name: land
description: Land approved pull requests — merge each approved, bot-owned PR that is ready to merge, strip its issue's in-progress label, then tear down the local worktree and branch. Human-invoked only. Use when the maintainer has approved a PR and wants it merged and cleaned up, says "land it" / "land the approved PRs" / "merge and clean up", or just approved a PR review.
argument-hint: "[PR number to land just that one, or leave blank to sweep every approved PR]"
allowed-tools: Bash(*/bin/land:*)
---

# Land

Merge the PRs a human has approved, then clean up after them. `land` is the terminal hop of the implement loop: `pickup` opens a PR, a human reviews and approves, and `land` executes the merge the approval authorised — then strips the issue's `in-progress` label, removes the worktree, and deletes the branch.

The mechanics live in the `bin/land` command (ADR 0008): it classifies, merges, strips, tears down, and syncs `main` in tested code. This wrapper names only that one binary — never a tracker call, a repository mutation, or another adapter — and carries the lone human decision: when to land.

`land` is **human-invoked only**. It never runs from `auto`, `loop`, or `schedule` — merging is outward-facing and hard to reverse, so the final merge stays a human act. The approval is the gate; this command is the hand that turns it.

## Plan

Run `bin/land plan` and render its buckets:

- `${CLAUDE_PLUGIN_ROOT}/bin/land plan` — sweep every approved PR; append `--pr <n>` to plan just one.

!`${CLAUDE_PLUGIN_ROOT}/bin/land plan`

Read the JSON: `landable` (number, title, method, the issues it closes, and any `unusual` flags), `rework` (conflicting or behind — these go to `pickup`, never landed here), `skip` (with a reason: stale approval, not ready, no allowed merge method), and `merged` (already merged in the UI — cleanup only). Show the maintainer the landable set and what each closes; name the rework and skipped PRs with their reasons.

## Confirm only when unusual

Default to proceeding: a single approved, bot-owned PR that is ready to merge lands without a prompt — the classification already cleared it. Pause to confirm — listing the PRs about to land, number, title, and the issue each closes — only when `plan`'s `unusual` list is non-empty:

- `multi-pr` — more than one PR will land in this invocation.
- `no-issue` — a landable PR carries neither a closing reference nor a leading `No-issue:` marker, so cleanup can't strip `in-progress` with confidence. A PR whose body leads with `No-issue:` declares the absence as intentional — `plan` does not flag it, and it lands without a prompt.

A maintainer who already said to land without asking waives even these.

## Apply

On confirmation (or straight away when nothing is unusual), run `bin/land apply` with a `--pr <n>` for **each** PR the maintainer confirmed in plan — `${CLAUDE_PLUGIN_ROOT}/bin/land apply --pr <n> [--pr <n> …]`. Pass the numbers on every path, including the single landable PR; `apply` binds to exactly the PRs you pass — a closed allowlist. It re-checks readiness and approval-covers-HEAD at merge time (the selection goes stale the moment `main` moves) and drops any PR that went stale with a reason, confirms the closing references, strips `in-progress` on each closed issue, tears down the local worktree and branch where one exists, and fast-forwards local `main` once.

Never run a bare `bin/land apply`: with no `--pr` it halts. `apply` acts only on the numbers you confirmed and never re-derives the approved set, so a PR approved between plan and apply can't slip into the batch — the merge stays bound to what the human saw.

Render its `results`: per PR, merged or skipped-with-reason, the issues closed, whether the worktree was torn down. A PR that landed with no linked issue and no `No-issue:` marker is reported, its issue left for the maintainer.

## Offer the epic close-out

`apply` returns `epic_close_candidates`: parent epics whose every sub-issue is now closed (`land` never closes an epic itself). For each, show the maintainer the sub-issue list and **recommend closing** — the work it tracked is complete. On confirmation, run `bin/land close-epic --number <n>` — `${CLAUDE_PLUGIN_ROOT}/bin/land close-epic --number <n>`; it re-verifies every child is still closed and halts rather than closing if one reopened. Leave the epic open if declined.

## Handover

Hand off per [../skills/HANDOVER.md](../skills/HANDOVER.md) → *Autonomy*. End the run by rendering this row as one `AskUserQuestion`.

- **artifact:** merged PRs — issues closed and de-labelled, branches and worktrees cleaned
- **default:** — (terminal; the work is merged and the trail is clean)
- **alternatives:**
  - [`retro`](../skills/retro/SKILL.md) — a post-merge work retro on a just-landed item, reading its brief against the merged PR to harvest process learnings to the tracker. Offered **only when this land closed a brief-carrying issue** — one whose body or comments hold an agent brief ([../skills/contracts/agent-brief.md](../skills/contracts/agent-brief.md)); a land that closed no such issue has nothing to retro, so don't offer it. When more than one brief-carrying issue landed, name the item to retro.
  - the project's **release process**, surfaced only when the project's `CLAUDE.md` documents one — offered after a land so accumulated changes can be versioned. Discover it from the in-context `CLAUDE.md`; never hunt the tree for a release command.
  - otherwise just `stop`

**Interactive-only** (see *Autonomy* in [../skills/HANDOVER.md](../skills/HANDOVER.md)) — merging is the human-authorised act `auto` must not take, and the implement loop halts before it. The conditional `retro` and release-process alternatives do not change this: a post-merge retro and cutting a release are each their own human-invoked act, never reached unattended.
