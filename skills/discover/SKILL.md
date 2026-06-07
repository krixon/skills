---
name: discover
description: Grill the user about a product idea before any technical design — challenge that the problem is real, sharpen who it serves, weigh its value against the cost of inaction, force the non-goals, and define how success is known. Use when starting fresh on a problem worth validating before designing a solution, or when the user wants product discovery / to pressure-test whether work is worth doing.
argument-hint: "[the problem or idea to validate]"
---

# Discover

Grill the user about a problem before any solution is designed, until you both agree it is worth solving and for whom. The interview mechanism is shared and lives in [../GRILL-METHOD.md](../GRILL-METHOD.md); this skill carries the product lens — it interrogates the problem, not the implementation.

## Grounding

Ground in the project's product and project documentation — what it's for, who it serves, the bets already placed — as the in-context project `CLAUDE.md` points to them. This is the product surface, not the code internals: read the README, the product docs, the recorded decisions, not the call graph. With none present, work from what the user tells you.

## The lens

### Challenge that the problem is real

Don't accept the problem as stated. Who hits it, how often, and what does it cost them today? Press for evidence over assertion — a problem nobody can point to a real instance of is a guess. "You say users struggle with X — when did that last happen, and to whom?"

### Sharpen the user/segment

Force a specific user or segment. "Everyone" is not a segment. Narrow from the population to the people who feel this acutely enough to change behaviour, and name them in the project's own terms.

### Probe value versus cost-of-inaction

Weigh what solving this is worth against what happens if it's left alone. Surface the alternatives the user is implicitly rejecting — build it, buy it, or the workaround they already use. If the cost of inaction is low or an existing workaround suffices, say so; that is a finding, not a failure.

### Force the non-goals

Pin down what this explicitly will *not* do. An unbounded problem can't be designed against. Make the user name the adjacent problems this leaves on the table.

### Define success

Name the signal that says this worked — observable, and ideally measurable. "How will you know, without asking anyone, that this solved the problem?" A problem with no success signal can't be validated as solved.

## The framing block

End a converged run by emitting one compact framing block — the baton this skill hands forward. Persist it nowhere; it lives in the conversation and is passed to `design` as its input argument. Keep it tight:

- **Problem** — what's wrong and who hits it.
- **User/segment** — the specific people it serves.
- **Value + cost-of-inaction** — what solving it is worth, and what leaving it costs.
- **Non-goals** — what it explicitly won't do.
- **Success signal** — the observable that says it worked.
- **Why this over alternatives** — build/buy/workaround, and why this one.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a validated problem framing — the framing block above, ready to seed technical design
- **default:** `design` — grill the solution to this framing against the domain model; pass the framing block as its input
- **alternatives:** `slice`, stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — discovery is an interview; `auto` never enters it.
