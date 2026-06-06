# Context

Domain vocabulary for this repo. Skills use these terms in issue titles, briefs, and prose; read them before writing tracker artifacts.

## Vocabulary

**PRD** — a Product Requirements Document issue: the multi-slice spec `spec` emits when a change is too large for a single vertical slice. It carries a category label (`enhancement` / `bug`) and no readiness label — it isn't grabbable as written. It is the **parent** of the slices `slice` cuts from it.

**Slice** — a tracer-bullet issue: a thin vertical cut through every layer (schema, API, UI, tests) that is independently grabbable and demoable on its own. `slice` decomposes a PRD into slices, each labelled `ready-for-agent` (AFK) or `ready-for-human` (HITL). A slice may be blocked by other slices; the blocked-by link is a native GitHub issue dependency.

**Parent** — the issue a slice descends from, the PRD. The link is a native GitHub **sub-issue** relation: the slice is a sub-issue of its parent PRD. `land` reads a parent's sub-issues to close it once they have all landed; a PRD with no open sub-issues left is complete.
