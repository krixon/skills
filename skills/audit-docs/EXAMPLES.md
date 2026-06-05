# Examples

## Worked self-test: the #16 drift

The drift `audit-docs` exists to catch, replayed against the repo state before it was corrected by hand (in #16). Walking the process surfaces it as a finding.

**Setup.** `capture`'s docs listed `deepen` among the audit skills that feed it findings, while `deepen`'s own handover and the workflow graph routed `deepen` to the *design* track (`deepen → to-prd → slice`) — never to `capture`. The prose claimed a producer the graph contradicted.

**1. Map claims.** From `capture/SKILL.md`: an audit skill (`audit-coverage`, `audit-security`, `deepen`) produces findings that `capture` consumes — a claim that `deepen` is a finding producer into `capture`.

**2. Locate the backing code.** `deepen`'s `## Handover` block: `default: to-prd` toward the design track — no `capture` hop. `WORKFLOWS.md`'s "Reaching a ready state" graph routes `deepen → to-prd`, not `deepen → capture`. Two sources contradict the claim.

**3. Score.** Confidence **high** — the handover and the graph independently agree `deepen` does not feed `capture`. Severity **medium** — an agent wiring the pipeline from `capture`'s description would connect the wrong producer.

**4. Emit.**

<finding-issue-template>

## Finding

**Dimension:** docs-drift
**Suggested category:** bug
**Severity:** medium
**Confidence:** high

**Where:** `capture` description / cold-start suggestion (path as of audit: `skills/capture/SKILL.md`), contradicting `deepen`'s handover (`skills/deepen/SKILL.md`)

**Evidence:**
`capture` lists `deepen` as a finding producer, but `deepen`'s handover routes to `to-prd` (the design track), never to `capture`, and the `WORKFLOWS.md` graph agrees. A reader wiring the pipeline from `capture`'s docs would connect the wrong source.

**Source:** audit-docs

</finding-issue-template>

This is the contradiction a docs audit reduces to: a claim in one artifact, the code (or graph) in another that disagrees, scored and emitted for `capture`.
