---
name: retro
description: Run a post-merge work retro on a landed item — read its original agent brief against the merged PR, surface where brief and reality diverged, and file the process-feedback gaps worth acting on to the tracker. Use after `land` merges a brief-carrying PR and you want the work to teach the next brief; reached as an alternative hop from `land`'s handover. Process feedback only — never durable knowledge or memory.
argument-hint: "[the landed issue, or its merged PR]"
---

# Retro

Run a post-merge **work retro** on a single landed item. Read the original agent brief against what shipped, find where brief and reality diverged, and route the divergences worth acting on to the tracker — where they re-enter the machinery that writes the next brief. Most lands teach nothing worth filing; finishing clean having filed nothing is the **common, first-class outcome** — never manufacture filler.

Reached as an alternative hop from `land`'s handover, after a successful land that closed a brief-carrying issue. Because the implement loop halts before `land` and `land` is human-invoked only, `retro` only ever runs interactively — it never reaches `auto`.

## Scope boundary — load-bearing

`retro` harvests **process feedback only**: a brief-vs-reality gap that suggests improving the brief-writing machinery — the [agent-brief contract](../contracts/agent-brief.md), a skill, or the triage step. A worth-filing learning reads like *"the agent-brief contract should require X — the brief for #N missed it and the work had to backfill."*

It does **not** harvest durable knowledge — facts about the user, the project, or how to work. That is a separate, already-rejected concern ([ADR 0010](../../docs/adr/0010-retro-harvests-process-learnings-to-the-tracker.md)): context must not be machine-confined, so there is no memory sink here. Keeping `retro` to process feedback is what makes it distinct. Do not let it drift into a general knowledge harvester — a gap that teaches *the project* something, not *the brief-writing machinery* something, is out of scope.

## Process

### 1. Gather the brief and what shipped — via the code host, no worktree

`land` tears the worktree down before this handover, so `retro` sources everything from the tracker and code host — **never the filesystem**. There is no local checkout to read.

- **The original brief.** For a triage-promoted issue, the brief is the agent-brief comment on the now-closed issue; for a sliced issue, it is the issue body. Read the closed issue with its comments ([../GITHUB.md](../GITHUB.md) → *Issues*).
- **What shipped.** The merged PR's **diff** and its **review** — read through the code host ([../GITHUB.md](../GITHUB.md) → *PRs and rework*). The diff is what the work did; the review is where a human already flagged a gap.

If invoked without a landed, brief-carrying item, stop and say so — there is nothing to retro on an item that carried no brief.

### 2. Diff brief against reality

Read the brief as the contract it was, then read the diff and review as the verdict on it. Surface where they diverged:

- **Acceptance criteria** the work met by going outside what the brief asked, or that proved wrong, missing, or untestable as written.
- **Scope** the brief drew that reality crossed — work the brief omitted that the PR had to add, or out-of-scope lines the brief failed to fence.
- **Interfaces / behavior** the brief specified that the code contradicts, and rework the **review** forced that a sharper brief would have pre-empted.

### 3. Keep only the process-feedback gaps

Filter every divergence through the scope boundary above. A gap survives only if acting on it improves the **brief-writing machinery** — the agent-brief contract, a skill, or triage. Discard the rest: a one-off implementation detail, a fact about the project, anything that teaches no repeatable lesson about how the next brief should be written. Most divergences die here, and that is correct.

### 4. Decide what clears the bar — the synthesis

For each surviving gap, judge whether it is worth a tracked process-improvement issue. This judgment is `retro`'s reason to be a skill: a gap clears the bar only when the same brief-writing weakness would recur and a contract/skill/triage change would prevent it. A gap unique to this one item, or already covered by an existing convention, does not clear it.

**Empty is the common case.** When nothing clears the bar, file nothing and report that the land taught no process learning. Do not lower the bar to produce an issue.

### 5. File the survivors through capture

Shape each surviving learning as a **finding** ([../contracts/finding.md](../contracts/finding.md)) and hand it to `capture` — reuse the capture path; never reimplement issue creation.

- **Title** — the one-line process problem; becomes the issue title.
- **Dimension** — `process`.
- **Where** — the brief-writing machinery the gap points at: the agent-brief contract, the named skill, or the triage step (the `process` dimension's target, not a code location — see [../contracts/finding.md](../contracts/finding.md)).
- **Evidence** — the brief-vs-reality gap, naming the landed item (*"the brief for #N …"*) and what the work had to backfill or rework as a result.
- **Suggested category** — `enhancement` (a process improvement); **Severity** / **Confidence** per the finding contract.
- **Source** — `retro`.

The findings arrive at `capture` pre-shaped (like an audit's), so it skips straight to dedupe and the cull. They land as `needs-triage` for a human to triage later.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End the run by rendering this row as one `AskUserQuestion`.

- **artifact:** process-feedback findings ([../contracts/finding.md](../contracts/finding.md) shape) — or none, when the land taught no process learning
- **default:** `capture` — dedups against open issues, culls, files survivors as `needs-triage`. When the result is empty, the run is terminal: there is nothing to file; report it and stop
- **alternatives:** stop

`retro` is **not** interactive-only ([../HANDOVER.md](../HANDOVER.md) → *Autonomy*) — its synthesis has an unattended default (file nothing). It never reaches `auto` regardless, because it is only ever entered by hand from `land`'s post-merge handover.
