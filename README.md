# Skills

A library of [Claude Code](https://claude.com/claude-code) agent skills for engineering workflows — planning, issue triage, audits, TDD, diagnosis, and skill authoring. Packaged as a Claude Code plugin.

## Install

From the GitHub repo (private — requires access):

```
/plugin marketplace add krixon/skills
/plugin install skills@karl
```

Or install from a local checkout:

```
git clone git@github.com:krixon/skills.git ~/dev/skills
```

Then in Claude Code:

```
/plugin marketplace add ~/dev/skills
/plugin install skills@karl
```

Skills are namespaced once installed: `/skills:diagnose`, `/skills:tdd`, etc.

## I want to…

Start from the task, not the skill. Each entry is the head of a chain — run the command and it hands you to the next hop. The full graph is in [skills/WORKFLOWS.md](skills/WORKFLOWS.md).

| I want to… | Run | …and the path from there |
|---|---|---|
| Stress-test a plan or design | `/grill` — challenges it against CONTEXT.md / ADRs and updates them inline | grilling → `spec` → `slice` → ready issues on the tracker |
| Turn this conversation into a spec | `/spec` | PRD published as an issue → `slice` |
| Break a plan or PRD into issues | `/slice` | independently-grabbable issues, each marked `ready-for-agent` (AFK) or `ready-for-human` (HITL) |
| Find architecture / refactoring opportunities | `/deepen` | seams surfaced → `spec` → `slice` |
| Find what's not tested | `/audit-coverage` | findings → `capture` → `needs-triage` |
| Run a security audit | `/audit-security` | findings → `capture` → `needs-triage` |
| Check the docs haven't drifted | `/audit-docs` | findings → `capture` → `needs-triage` |
| File findings or observations as issues | `/capture` | deduped `needs-triage` issues for a human to `triage` |
| Triage incoming issues | `/triage` | each routed to `ready-for-agent`, `ready-for-human`, `needs-info`, or `wontfix` |
| Start implementing a ready issue | `/pickup` | claims it → routes by kind to `tdd` / `diagnose` / `write-skill` / docs / config → review gate → opens a PR |
| Build a feature test-first | `/tdd` | red-green-refactor loop (usually reached via `pickup`) |
| Debug a hard bug or perf regression | `/diagnose` | reproduce → minimise → fix → regression test (usually reached via `pickup`) |
| Answer questions raised on a PR review | `/field` | work through each to shared understanding → back to `pickup` for the rework round |
| Merge an approved PR | `/land` | merges, strips `in-progress`, deletes the branch/worktree (human-invoked only) |
| Cut a plugin version release | `/release` | bumps `plugin.json`, commits to `main`, tags `v<new>` — batched and human-invoked; `land` offers it after a merge |
| Write a new skill | `/write-skill` | scaffolds structure + progressive disclosure |
| Run a whole pipeline unattended | `/auto <workflow>` (e.g. `/auto findings`) | walks the chain head-down, halting at the first human gate |
| Hand off the session to a fresh agent | `/handoff` | a compact handoff doc the next agent picks up |

## Skills

### Planning & specs
- **grill** — interview you relentlessly about a plan until shared understanding, resolving each decision branch while challenging it against the domain model and updating CONTEXT.md / ADRs inline.
- **field** — field questions put to the agent and converge on shared understanding; the dual of grill, run on PR-review rework.
- **spec** — turn the current conversation into a PRD and publish it as a GitHub issue.
- **slice** — break a plan, spec, or PRD into independently-grabbable tracer-bullet issues.

### Issue tracking
- **triage** — drive issues through a triage state machine by label.
- **capture** — turn audit findings or ad-hoc observations into needs-triage issues, deduped and culled.

### Audits
- **audit-coverage** — audit for high-risk untested paths; static-first, surfaces findings to `capture`.
- **audit-security** — sweep for security exposure (authz, injection, secrets); static-first, surfaces findings to `capture`.
- **audit-docs** — find documentation that has drifted from the code (stale CONTEXT.md vocabulary, violated ADRs, README/behavior claims); static-first, surfaces findings to `capture`.
- **deepen** — find architecture/refactoring opportunities informed by CONTEXT.md and ADRs.

### Build & fix
- **pickup** — claim a ready issue and implement it, routing by artifact kind through the review gate to an open PR.
- **tdd** — red-green-refactor loop, integration-test first.
- **diagnose** — disciplined loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test.
- **land** — merge an approved PR, strip `in-progress`, and tear down the branch/worktree; human-invoked only.
- **release** — cut a batched plugin version release: derive the bump from Conventional-Commit types, then bump `plugin.json`, commit to `main`, and tag `v<new>`; human-invoked only.

### Meta & session
- **auto** — run a skill workflow unattended, walking the handover chain until the first human gate.
- **write-skill** — author new skills with proper structure and progressive disclosure.
- **zoom-out** — map the relevant modules and callers a layer up, in the project's glossary vocabulary.
- **handoff** — compact the conversation into a handoff doc for a fresh agent.
- **caveman** — ultra-compressed output mode; drops filler, keeps technical accuracy.

## Layout

- `skills/<name>/SKILL.md` — one directory per skill; `SKILL.md` is the entry point. Optional `REFERENCE.md`, `EXAMPLES.md`, `scripts/`. Real location at the plugin root, where marketplace installs discover them.
- `.claude/skills/` — symlink to `skills/` so this repo also loads them live as project-local skills during development.
- `.claude-plugin/plugin.json` — plugin manifest (name `skills`).
- `.claude-plugin/marketplace.json` — single-plugin marketplace (name `karl`).

Targets macOS/Linux.
