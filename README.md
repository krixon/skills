# Skills

A library of [Claude Code](https://claude.com/claude-code) agent skills for engineering workflows — planning, issue triage, audits, TDD, diagnosis, and skill authoring. Packaged as a Claude Code plugin.

## Install

From the GitHub repo:

```
/plugin marketplace add krixon/skills
/plugin install skills@krixon
```

Or install from a local checkout:

```
git clone git@github.com:krixon/skills.git ~/dev/skills
```

Then in Claude Code:

```
/plugin marketplace add ~/dev/skills
/plugin install skills@krixon
```

Skills are namespaced once installed: `/skills:diagnose`, `/skills:tdd`, etc.

## Requirements

The workflow skills drive a small code adapter under `bin/` ([ADR 0008](docs/adr/0008-deterministic-mechanics-code-adapter.md)) that shells out to a few tools. On the machine that runs the skills you need:

- `git`
- `gh` (the GitHub CLI), authenticated
- Python 3.8 or newer

Each command requires only the tools it actually uses — the `worktree` group is pure git, so it doesn't need `gh`. The adapter binaries ship executable — a marketplace install is a git clone, which reproduces the committed file mode, so no `chmod` and no install step is needed. When a prerequisite is absent the adapter stops on its first call with a named halt on stderr — a JSON envelope whose `reason` is `adapter substrate check failed` and whose `missing` list names each absent prerequisite — rather than a cryptic exec error.

Targets macOS/Linux.

## I want to…

Start from the task, not the skill. Each entry is the head of a chain — run the command and it hands you to the next hop. Trace a chain by following each skill's handover `default` hop ([skills/HANDOVER.md](skills/HANDOVER.md)).

| I want to… | Run | …and the path from there |
|---|---|---|
| Validate a problem before designing a solution | `/discover` — grills the problem itself: who it serves, its value vs cost-of-inaction, its non-goals, how success is known | discover → `design` → `slice` → ready issues on the tracker |
| Stress-test a plan or design | `/design` — challenges it against the project's domain model, sharpens terminology, offers an ADR where one is warranted | design → `slice` → ready issues on the tracker |
| Turn a plan or this conversation into issues | `/slice` | one agent-brief issue, or N independently-grabbable issues under a lean epic, each marked `ready-for-agent` (AFK) or `ready-for-human` (HITL) |
| Find architecture / refactoring opportunities | `/deepen` | candidates + report surfaced → `design` to design the chosen one |
| Find what's not tested | `/audit-coverage` | findings → `capture` → `needs-triage` |
| Run a security audit | `/audit-security` | findings → `capture` → `needs-triage` |
| Check the docs haven't drifted | `/audit-docs` | findings → `capture` → `needs-triage` |
| Find swallowed errors / check error handling | `/audit-error-handling` | findings → `capture` → `needs-triage` |
| Find dead or unused code | `/audit-dead-code` | findings → `capture` → `needs-triage` |
| Find resource leaks (unclosed handles) | `/audit-resource-leak` | findings → `capture` → `needs-triage` |
| Harvest TODOs / find tech debt | `/audit-debt` | findings → `capture` → `needs-triage` |
| Find critical paths running blind | `/audit-observability` | findings → `capture` → `needs-triage` |
| Find performance hazards on hot paths | `/audit-performance` | findings → `capture` → `needs-triage` |
| Audit third-party dependency health | `/audit-deps` | findings → `capture` → `needs-triage` |
| File findings or observations as issues | `/capture` | deduped `needs-triage` issues for a human to `triage` |
| Triage incoming issues | `/triage` | each routed to `ready-for-agent`, `ready-for-human`, `needs-info`, or `wontfix` |
| Start implementing a ready issue | `/pickup` | claims it → routes by kind to `tdd` / `diagnose` / `write-skill` / docs / config → review gate → opens a PR carrying a [review-aid](skills/REVIEW-AID.md) coverage summary |
| Ship a small fix with no tracked issue | `/patch` | branch in a worktree → review gate → a no-issue PR (body led by `No-issue:`, with a degraded [review-aid](skills/REVIEW-AID.md) summary) a human lands; human-invoked, for fixes too small to file |
| Build a feature test-first | `/tdd` | red-green-refactor loop (usually reached via `pickup`) |
| Debug a hard bug or perf regression | `/diagnose` | reproduce → minimise → fix → regression test (usually reached via `pickup`) |
| Ask questions on a PR review (not just request changes) | Comment them on the PR, then `/pickup` | `pickup`'s rework query catches the unresolved thread → routes the questions to `field`, where the agent works each to a converged answer with you → the answers post back to the thread |
| Merge an approved PR | `/land` | merges, strips `in-progress`, deletes the branch/worktree (human-invoked only) → offers `retro` after a brief-carrying land |
| Harvest process learnings from a just-merged item | `/retro` | reads the original brief against the merged PR → process-feedback findings → `capture` → `needs-triage`; filing nothing is the common, first-class outcome |
| Clean up stale workflow state | `/reap` | sweeps abandoned claims, quiet `needs-info`, orphaned worktrees/branches, and emptied epics → proposes each fix, confirms per item (human-invoked only) |
| Write a new skill | `/write-skill` | scaffolds structure + progressive disclosure |
| Run a whole pipeline unattended | `/auto <skill>` (e.g. `/auto audit-coverage`) | walks the chain head-down, halting at the first human gate |
| Drain the whole `ready-for-agent` queue unattended | `/loop /auto pickup` (no interval) | picks up each ready issue in turn, then polls on a backoff for more — see [Draining the queue unattended](#draining-the-queue-unattended) |
| Hand off the session to a fresh agent | `/handoff` | a compact handoff doc persisted to a well-known location; a fresh session's `/handoff` discovers and resumes it with no pasted path |

## Draining the queue unattended

`/loop /auto pickup` (dynamic mode — no interval) drains the whole `ready-for-agent` queue in one sitting: each loop iteration picks up the next ready issue and opens a PR, back-to-back with no idle between them. The queue lives in the tracker (`ready-for-agent` minus `in-progress`), not the conversation, so the loop re-derives it each iteration and stays correct across a long session the harness may compact.

When the queue runs dry the loop doesn't stop — it polls on a widening backoff (`60s → 5m → 15m → 30m → 1h`, then hourly), resets to a hard drain the moment a newly-triaged issue appears, and gives up only after ~a day of finding nothing. Operating details are in [skills/auto/SKILL.md](skills/auto/SKILL.md).

## Skills

Each skill below links to its fuller entry in the [skills reference](docs/skills-reference.md) — what it does, when to reach for it, and an example.

### Planning & specs
- **[discover](docs/skills-reference.md#discover)** — grill you about a problem before any solution is designed: challenge that it's real, sharpen who it serves, weigh value against the cost of inaction, force the non-goals, and define how success is known; the head of the planning chain, upstream of `design`.
- **[design](docs/skills-reference.md#design)** — grill you relentlessly about a plan or technical design until shared understanding, resolving each decision branch while challenging it against the domain model, sharpening terminology, and offering an ADR where a decision warrants it.
- **[field](docs/skills-reference.md#field)** — field questions put to the agent and converge on shared understanding; the dual of design, run on PR-review rework.
- **[slice](docs/skills-reference.md#slice)** — turn a plan, the current conversation, or an existing issue into one agent-brief issue or N tracer-bullet issues under a lean epic.

### Audits
- **[audit-coverage](docs/skills-reference.md#audits)** — audit for high-risk untested paths; static-first, surfaces findings to `capture`.
- **[audit-security](docs/skills-reference.md#audits)** — sweep for security exposure (authz, injection, secrets); static-first, surfaces findings to `capture`.
- **[audit-docs](docs/skills-reference.md#audits)** — find documentation that has drifted from the code (stale vocabulary, violated decisions, README/behavior claims); static-first, surfaces findings to `capture`.
- **[audit-error-handling](docs/skills-reference.md#audits)** — sweep for error-handling defects (swallowed errors, bare catch-alls, critical calls with no failure path); judges handling quality, not test presence; static-first, surfaces findings to `capture`.
- **[audit-dead-code](docs/skills-reference.md#audits)** — sweep for dead code (unreachable branches, never-called functions, orphaned modules); static-first, surfaces findings to `capture`.
- **[audit-resource-leak](docs/skills-reference.md#audits)** — sweep for acquire sites (handles, connections, contexts, locks) with no guaranteed release on every path; static-first, surfaces findings to `capture`.
- **[audit-debt](docs/skills-reference.md#audits)** — harvest in-code debt markers (TODO/FIXME/HACK/XXX and known shortcuts) clustered by area; static-first, surfaces findings to `capture`.
- **[audit-observability](docs/skills-reference.md#audits)** — find critical paths (money, auth, data mutation, external calls) running blind with no log, metric, or trace; static-first, surfaces findings to `capture`.
- **[audit-performance](docs/skills-reference.md#audits)** — find performance hazards on hot paths (N+1 data access, per-iteration allocation or IO, unbounded reads, missing caching or indexing, blocking in async); static-first, surfaces findings to `capture`.
- **[audit-deps](docs/skills-reference.md#audits)** — audit third-party dependency health (outdated majors, known advisories, abandoned upstreams, license drift) from manifests and lockfiles; static-first, surfaces findings to `capture`.
- **[deepen](docs/skills-reference.md#deepen)** — find architecture/refactoring opportunities informed by the project's domain language and recorded decisions.

### Build & fix
- **[pickup](docs/skills-reference.md#pickup)** — claim a ready issue and implement it, routing by artifact kind through the review gate to an open PR carrying a [review-aid](skills/REVIEW-AID.md) coverage summary.
- **[patch](docs/skills-reference.md#patch)** — ship a small fix straight from a conversation, no tracked issue: worktree branch → review gate → a no-issue PR (`No-issue:` marker, degraded [review-aid](skills/REVIEW-AID.md) summary) a human lands; human-invoked.
- **[tdd](docs/skills-reference.md#tdd)** — red-green-refactor loop, integration-test first.
- **[diagnose](docs/skills-reference.md#diagnose)** — disciplined loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test.
- **[retro](docs/skills-reference.md#retro)** — a post-merge work retro: read a landed item's original brief against the merged PR, surface where brief and reality diverged, and file the process-feedback gaps worth acting on through `capture`; reached from `land` after a brief-carrying merge, filing nothing when nothing rises to a process issue.

### Commands

Commands are the entry points over the `bin/` adapter ([ADR 0008](docs/adr/0008-deterministic-mechanics-code-adapter.md)) — thin wrappers that hold no mechanics, invoked the same way as a skill (`/land`). Two shapes: **pure commands** that never launch an agent (`land`, `reap`), and **command-launches-agent** that reach a synthesis step handed to an agent — in-session by the host agent, or a subagent under `auto` (`capture`, `triage`).

- **[capture](docs/skills-reference.md#capture)** — turn audit findings or ad-hoc observations into deduped `needs-triage` issues: the dedupe and filing run in `bin/capture`, an agent shapes raw observations into findings where the input isn't already shaped (command-launches-agent).
- **[triage](docs/skills-reference.md#triage)** — drive issues through the triage state machine by label: the queue/candidate present, the advisory claim, and the state transitions run in `bin/triage`, an agent evaluates the issue and drafts the promoted brief (command-launches-agent, interactive-only).
- **[land](docs/skills-reference.md#land)** — merge approved PRs, strip `in-progress`, and tear down the branch/worktree; pure command, human-invoked only.
- **[reap](docs/skills-reference.md#reap)** — sweep workflow state for staleness — abandoned claims, quiet `needs-info`, orphaned worktrees/branches, emptied epics — and clean each up one human-confirmed action at a time; pure command, human-invoked only.

### Meta & session
- **[auto](docs/skills-reference.md#auto)** — run a skill workflow unattended, walking the handover chain until the first human gate.
- **[write-skill](docs/skills-reference.md#write-skill)** — author new skills with proper structure and progressive disclosure.
- **[zoom-out](docs/skills-reference.md#zoom-out)** — map the relevant modules and callers a layer up, in the project's established vocabulary.
- **[handoff](docs/skills-reference.md#handoff)** — compact the conversation into a handoff doc at a well-known location for a fresh agent; a fresh session's `/handoff` discovers and resumes the latest pending doc.
- **[caveman](docs/skills-reference.md#caveman)** — ultra-compressed output mode; drops filler, keeps technical accuracy.

## Layout

- `skills/<name>/SKILL.md` — one directory per skill; `SKILL.md` is the entry point. Optional `REFERENCE.md`, `EXAMPLES.md`, `scripts/`. Real location at the plugin root, where marketplace installs discover them.
- `commands/<name>.md` — collapsed pure commands (ADR 0008): thin wrappers over the `bin/` adapter, distinct from the agent-native skills.
- `.claude/skills/` and `.claude/commands/` — symlink farms mirroring `skills/` and `commands/` so this repo also loads them live during development; regenerated by `bin/relink-dev-skills.sh`.
- `.claude-plugin/plugin.json` — plugin manifest (name `skills`).
- `.claude-plugin/marketplace.json` — single-plugin marketplace (name `karl`).
