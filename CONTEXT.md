# Context

Domain vocabulary for this repo. Skills use these terms in issue titles, briefs, and prose; read them before writing tracker artifacts.

## Vocabulary

**Epic** — a lean parent issue `slice` emits when a change decomposes into several vertical slices: a goal, an out-of-scope boundary, and the child list, nothing more. It carries the `epic` label and a category label (`enhancement` / `bug`), and no readiness label — it isn't grabbable as written. It is the **parent** of the slices `slice` cuts under it.

**Slice** — a tracer-bullet issue: a thin vertical cut through every layer (schema, API, UI, tests) that is independently grabbable and demoable on its own. `slice` decomposes a change into slices, each labelled `ready-for-agent` (AFK) or `ready-for-human` (HITL); a multi-slice change groups them under an epic. A slice may be blocked by other slices; the blocked-by link is a native GitHub issue dependency.

**Parent** — the issue a slice descends from, its epic. The link is a native GitHub **sub-issue** relation: the slice is a sub-issue of its parent epic. `land` reads a parent's sub-issues to close it once they have all landed; an epic with no open sub-issues left is complete.

**Release** — A version increment of the published plugin (`.claude-plugin/plugin.json` `version`), cut deliberately by the `release` skill and covering the batch of material changes landed since the previous release — not one bump per merge. `land` offers to cut one after a merge; landing and releasing are distinct acts. *Avoid*: version bump, publish.

**Material change** — A landed change that affects the published plugin's surface or behaviour — the kind a release must version. Docs-only and chore merges are non-material. *Avoid*: significant change, breaking change.
