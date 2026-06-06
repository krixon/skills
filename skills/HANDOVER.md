# Handover

The shared contract for how one skill hands work to the next. A **workflow** is a chain of skills linked by these handovers; the chain emerges from the links, not from a controller. Every producer/transform skill ends with a `## Handover` section declaring its row, and renders that row as a single `AskUserQuestion` when run interactively.

## Declaration

Each skill's `## Handover` section carries exactly these fields:

- **artifact** — what the skill passes forward (e.g. findings, a PRD, needs-triage issues).
- **default** — the recommended next skill. Becomes option 1, marked `(Recommended)`. `—` if terminal.
- **alternatives** — other valid hops, plus `stop`.
- **auto** — what the `auto` wrapper does at this skill (see below).

## Interactive rendering

At the end of the skill, render the row as one `AskUserQuestion`:

- **question:** `<artifact> ready. What next?`
- **header:** `Next step`
- **options:** the **default** first, labelled `<skill> (Recommended)` with a one-line description of what it does; then **Run under `/auto`** when the derived condition below holds; then each **alternative**; then `Stop here`. When the default is terminal (`—`), `Stop here` leads as the recommended option and the alternatives follow.

**Run under `/auto`** is a derived option, not a declared one — no skill lists it in its row, and the row schema gains no field for it. It appears iff the default hop's `auto` directive resolves to `advance` or `stage` *for the current artifact* — i.e. the chain past this gate is safe to run unattended. Its meaning is "go AFK from here": delegate the rest of the chain to `auto` starting at the default hop, running to the next human gate, rather than walking it one interactive step at a time. Choosing it invokes `/auto <default-skill> <target>` (e.g. `/auto pickup 27`); the plain default option, by contrast, takes a single interactive hop. It sits **after the default, before the alternatives**.

The trigger is that one derived condition, never a separate per-skill flag. For a labelled work-item the readiness label folds into it through the default skill's directive: `pickup`'s directive is conditional on the label, so a `ready-for-agent` issue makes the hop enterable and the option shows, while a `ready-for-human` issue resolves to `never` and it does not. For an unlabelled artifact (findings, a report) the directive alone decides. When the default hop is a `never` skill, the option never appears.

This is an action, not a closing summary — every skill ends by *firing* this `AskUserQuestion`, never by describing the next step in prose.

Same shape in every skill — consistent wording is the point. The user picks the hop; the skill then invokes that skill (via the Skill tool) or stops.

## The `auto` directive

`auto` (see [auto/SKILL.md](auto/SKILL.md)) walks the default chain without asking, so each skill declares how it behaves unattended. One of:

- **advance** — safe to run unattended; `auto` runs it, then takes the **default** hop and continues to the next skill.
- **stage** — `auto` runs it unattended (applying any noted defaults for internal gates), then **stops**. Its artifact is left staged for a human; the default hop is the human's call. Use for the designated hand-back point of an autonomous run.
- **never** — interactive-only (it contains a human loop with no safe default). `auto` will not enter it. If a chain's default hop points at a `never` skill, `auto` halts before it.

Two kinds of gate exist, and they map onto these directives:

1. **Handover gates** (between skills) — cleared by taking the **default**. `advance` clears them silently.
2. **Internal gates** (inside a skill — a cull, a green-bar, a grilling loop) — there is no "default" to take. A skill resolves each one either by a declared unattended default (note it in the `auto` field, e.g. *"skip the interactive cull, file survivors with confidence ≥ medium"*) or by being `stage`/`never`. **Stop-and-stage is the default policy**: only push through an internal gate unattended when it's genuinely safe and reversible, and say so in the declaration.
