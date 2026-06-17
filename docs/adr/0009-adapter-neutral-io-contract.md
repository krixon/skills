# 0009 — The adapter speaks one neutral I/O contract: an opaque id, a two-zone envelope, two axes, and closed vocabularies

## Status

Accepted. Extends ADR 0008 — it specifies the data contract 0008 left implicit; it does not retire any part of it.

## Context

ADR 0008 moved deterministic mechanics into the code adapter and committed to "issue id treated as an opaque string", but never specified the *shape* of the data crossing the adapter boundary. Verifying the tracker adapter against live backends — Jira `ORPL`, GitHub `krixon/skills` — found each backend echoing its tool's native JSON: the GitHub backend returns `gh`'s raw fields and a bare `{url}` from create, keyed by `--number`; the Jira backend returns acli's `{key, fields}`, keyed by `--key`. There is no contract — only two backends relaying their tool's output.

A skill consuming that has to know which it is talking to: whether an id is an integer `number` or a string `key`, that Jira's `done` means the same as GitHub's `closed`, that a no-op is a `noop: true` flag here and a free-text `reason` there. That is precisely the tracker-awareness 0008's "binding catalogues collapse to a glossary" promised to remove. The adapter sealed the *command* seam but left the *data* seam open.

The live drive surfaced two further realities the contract has to answer:

- Some backend data has no neutral concept at all — a Jira Epic's mandatory "Investment Category" custom field is meaningless on GitHub.
- Some such fields carry a per-case judgment, not a configure-once value: which Investment Category is correct differs case by case. The adapter binary has no TTY, and ADR 0008 already forbids a command from prompting.

## Decision

Every value crossing the adapter boundary, in or out, conforms to one contract. The core concepts are neutral — they are the only things a skill adapts on; adapter-specifics may ride along, but strictly as non-load-bearing information.

### One opaque `id`

A single opaque string `id` is the only identifier in or out. The input argument `--id` replaces `--number` and `--key`; the backend coerces internally (GitHub does `int(id)`). A skill holds the `id` it received and hands it straight back to the next call, never knowing whether it is an integer or a key. The native identifier and any URL live in the `info` sidecar below.

### A two-zone envelope

Each result is two zones. Neutral contract fields sit at the **top level**. All adapter-specific data sits under one reserved key, **`info`**, and is informational — nothing branches on it. So GitHub `issue view` returns `{"id": "227", "state": "open", "title": …, "labels": […], "info": {"url": …, "number": 227}}` and Jira the same shape with `key` and `issue_type` under `info`. The neutral path stays terse, and `info` is read for display only, never branched on.

Issue *content* is neutral and sits at the top level too: `body`, and `comments` on a detail read (`issue view`), are where an agent brief lives, so they are contract fields, not `info` — each comment a neutral `{author, body, created_at}` with its native id/url quarantined in a per-comment `info`. A summary read (`issue list`) omits both to stay lean; the detail read carries them.

### Two axes, selected independently

"Tracker" conflates two backends. The **issue-tracker axis** (GitHub Issues vs Jira) owns issues, relations, labels, and issue state; the **code-host axis** (GitHub PRs vs a future host) owns PRs, reviews, the branch-ref claim, and merge. They are selected independently: `$ISSUE_TRACKER` drives only the tracker axis. A repo tracking issues in Jira still raises PRs on GitHub, so a PR's contract is neutral across *code hosts* and does not vary with `$ISSUE_TRACKER`; Jira implements the tracker axis only. Neutrality is claimed per axis.

### Closed neutral vocabularies

Every enum a skill branches on is a closed, lower-snake, documented vocabulary; each backend maps its native values *in*, and an unmapped native value is an error, not a pass-through. `issue.state` is `{open, closed}` — Jira's `done` category maps to `closed`; the workflow's real state machine (`needs-triage`, `in-progress`, …) lives in labels, which carry across neutrally, not in tracker status. Review decision is `{approved, changes_requested, review_required}`; merge state `{mergeable, conflicting, unknown}`.

Outcomes get the same treatment. Every act or halt result a skill branches on carries a closed `outcome` code — `ok`, `noop`, `claim_lost`, `conflict`, `unsupported`, `not_found`, `unconfigured`, `needs_decision` — and any human-readable explanation goes in a non-branched `message`. This makes a halt machine-parseable rather than scrapeable, which the headless outcome-schema channel of ADR 0008 requires.

### Backend-mandated non-neutral input

A field the backend requires but the neutral surface has no concept for is handled in one of three classes, and the adapter never invents a business value:

1. **Field identity and requiredness** — *that* an Epic needs a given custom field — comes from operator configuration.
2. **A value fixed for the deployment** comes from configuration too (mirroring `JIRA_PROJECT` and the `JIRA_DONE_RESOLUTION` default), and the adapter sets it on the write.
3. **A value that is a per-case judgment** — the command **halts** with `outcome: needs_decision`, carrying the field, its discovered allowed values, and a human prompt. The judgment is made above the command (a human gate, or an agent synthesising), and the command is re-invoked with the chosen value through a generic opaque `--set <field>=<value>` passthrough that the adapter forwards verbatim.

The skill couriers an opaque value it does not interpret — neutrality is *semantic*. A skill with hard-coded knowledge of "Investment Category" would violate the contract; relaying a value the adapter asked for and a human answered does not, no more than carrying an opaque `id` does. This is the input-side mirror of the `info` sidecar: backend-specific output is quarantined into `info`; backend-specific required input is quarantined into operator config or a `needs_decision` round-trip — neither crosses the neutral per-call seam.

## Considered Options

- **Return each backend's native identifier under a name matching its own input arg** (`{number}` for GitHub, `{key}` for Jira). Rejected: it still forces the caller to know an id is an integer here and a string there — a half-measure that leaves the backend visible.
- **Per-key prefixing** (`x_url`, `_number`) instead of an `info` sidecar. Rejected: it scatters the core/extra boundary across field names, so no field's status is legible at a glance.
- **A nested `{core, info}` envelope.** Rejected: it taxes every consumer with a `.core.` prefix forever, when the whole point is that the neutral path is the cheap default.
- **A three-state `issue.state` exposing Jira's `indeterminate`.** Rejected: no skill reads a neutral "in progress" *status* — that signal lives in the `in-progress` *label* — and GitHub cannot produce one.
- **Free-text outcomes and reasons.** Rejected: it keeps skills string-matching prose and makes `halt` unparseable, the exact problem ADR 0008's headless channel was built to avoid.
- **A single flat tracker abstraction where PR/review are merely "unsupported on the Jira backend".** Rejected: it hides that a PR belongs to a different axis and invites the false expectation that `$ISSUE_TRACKER=jira` should yield Jira PRs.
- **The adapter guessing the per-case decided value, or prompting for it.** Rejected: guessing a business classification is worse than failing, and with no TTY, `halt` — not a prompt — is the architecture's answer.

## Consequences

Skills hold opaque ids and switch on neutral tokens with zero backend-awareness. The reviewable line is sharp: a skill that dereferences `.info.*` or `.message`, or branches on a raw native value, is reaching past the contract. Each backend is rewritten to *project* its tool's JSON into the contract rather than echo it, and the contract — not a tool's output — is what the adapter's tests assert.

`halt` becomes a structured channel: `needs_decision` in particular turns a missing per-case field into a parseable decision request the layer above resolves. A consequence at the workflow level: in a deployment that mandates a decided field, creating that issue type is inherently HITL — under `auto` the run stops at the `needs_decision` halt, consistent with how `auto` already stops at human gates.

This contract specifies *shape*; it does not reopen the Jira REST "closed door" ADR 0008 recorded — a deployment whose policy forbids managed service tokens still cannot use the Jira backend, contract or no. And the per-axis neutrality claim means a future code host (GitLab, Bitbucket) joins on the code-host axis without touching the tracker axis, and vice versa.
