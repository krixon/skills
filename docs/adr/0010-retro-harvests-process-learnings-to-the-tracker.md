# 0010 — A post-merge retro harvests process learnings to the tracker, as a skill off `land`

## Status

Accepted. Implements #187; records why the machine-local-memory shape of #183 stays rejected.

## Context

`land` is the terminal hop of the implement loop, and nothing downstream of it harvests what the work taught. Where the agent brief was wrong, where code reality contradicted it, what a future brief should say differently — all of it evaporates with the session. The brief-writing machinery (the agent-brief contract, the skills, the triage step) gets no feedback from the work it specified, so the same brief weakness recurs.

A retro on a landed item can close that loop, but only if three questions are answered: **what** does it harvest, **where** does the result go, and **what form** does the retro itself take. Each had a plausible alternative, and #183 already picked the losing one for the first.

## Decision

A post-merge **work retro** reads a landed item's original brief against the merged PR (diff + review, via the code host — `land` tears the worktree down first), surfaces brief-vs-reality divergences, and files the worth-keeping ones to the tracker as `needs-triage` process-improvement findings, reusing the `capture` path. It is a **skill** (`retro`), reached as an alternative hop from `land`'s handover after a brief-carrying land. Empty — nothing clears the bar to file — is the common, first-class outcome.

Three decisions, each against a real alternative:

**What it harvests — process feedback only, not durable knowledge.** `retro` harvests *brief-vs-reality gaps that should improve the brief-writing machinery* — and nothing else. It explicitly does **not** harvest durable knowledge (facts about the user, the project, or how to work). That second concern is #183, and it was rejected: its sink was a machine-local memory, and context must not be machine-confined. Folding durable-knowledge harvesting into `retro` would resurrect the rejected shape under a new name. Keeping `retro` to process feedback is what makes it a distinct, accepted thing rather than #183 in disguise.

**Sink — the tracker.** A worth-filing learning lands as a `needs-triage` item, re-entering the same flow that writes future briefs.

**Form — a skill, off `land`.** Deciding where brief and reality diverged and whether a gap is worth filing is agent-native synthesis (ADR 0008 bucket 3), so `retro` is a skill, not command mechanics. It sits as an *offered* alternative on `land`'s handover, never auto-run and never inside the `land` binary.

## Considered Options

**Sink — where a learning goes.**

- **The tracker** (chosen). The learning re-enters the machinery that writes briefs, where a human triages it like any other proposed work. It is reversible (a `needs-triage` item can be closed), visible, and already has a filing path (`capture`).
- **The repo** (a durable doc — a conventions file, an ADR). Rejected as the default sink: most learnings are a single data point, not yet a decision, and writing each straight to a standing artifact skips the human triage gate that decides whether the lesson generalises. A learning that *does* generalise can still become an ADR or a doc change — but downstream of triage, as a piece of designed work, not as `retro`'s direct output.
- **Machine-local memory** (the #183 shape). Rejected — and the rejection is load-bearing, not incidental. A memory sink confines the learning to one machine, off the tracker, invisible to the team and to the next agent on another box. Context must not be machine-confined. This is the concern `retro` is explicitly *not*, and recording it here is what stops a future change quietly re-adding it.

**Form — what the retro is.**

- **A skill off `land`** (chosen). The synthesis is real model work, and an offered hop keeps the human in the loop where the work already pauses (`land` is human-invoked only).
- **Folded into the session-handoff skill.** Rejected: `handoff` carries an in-flight session across a boundary; a post-merge retro is a distinct act on a *completed* item, gated differently (it runs after the merge, not at session wrap), and bundling them would blur two unrelated triggers.
- **Command mechanics inside `land`.** Rejected: `land` is a pure command — deterministic mechanics only (ADR 0008). Brief-vs-reality synthesis is not deterministic; putting it in the `bin/land` binary would break that command's contract and force a synthesis step into code that must stay mechanical. `retro` also must not make `land` *run* it — the retro stays an offered alternative, so a land is never gated on a retro.

## Consequences

- The implement loop gains a feedback edge: `land` → (alternative) `retro` → `capture` → `needs-triage` → `triage`. Process weaknesses in the brief machinery now have a path back to where briefs are written.
- `retro` is reachable only interactively, from `land`'s post-merge handover — it never enters `auto`, and it carries no autonomy obligation because the gate is `land`'s.
- The line against machine-local memory is recorded, so a future "let's also remember project facts" proposal meets a written rejection rather than re-litigating #183 from scratch. Durable knowledge worth keeping still has a home — through triage into an ADR or doc — but never as `retro`'s direct, machine-confined output.
