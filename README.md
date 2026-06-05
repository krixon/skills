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

## Skills

### Planning & specs
- **grill** — interview you relentlessly about a plan until shared understanding, resolving each decision branch.
- **grill-with-docs** — grilling that challenges your plan against the domain model and updates CONTEXT.md / ADRs inline.
- **to-prd** — turn the current conversation into a PRD and publish it as a GitHub issue.
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
- **tdd** — red-green-refactor loop, integration-test first.
- **diagnose** — disciplined loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test.

### Meta & session
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
