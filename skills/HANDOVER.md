# Handover

The shared contract for how one skill hands work to the next. A **workflow** is a chain of skills linked by these handovers; the chain emerges from the links, not from a controller. Every producer/transform skill ends with a `## Handover` section declaring its row, and renders that row as a single `AskUserQuestion` when run interactively.

## Declaration

Each skill's `## Handover` section carries exactly these fields:

- **artifact** — what the skill passes forward (e.g. findings, an epic, needs-triage issues).
- **default** — the recommended next skill. Becomes option 1, marked `(Recommended)`. `—` if terminal.
- **alternatives** — other valid hops, plus `stop`.

## Interactive rendering

At the end of the skill, render the row as one `AskUserQuestion`:

- **question:** `<artifact> ready. What next?`
- **header:** `Next step`
- **options:** the **default** first, labelled `<skill> (Recommended)` with a one-line description of what it does; then **Run under `/auto`** when the condition below holds; then each **alternative**; then `Stop here`. When the default is terminal (`—`), `Stop here` leads as the recommended option and the alternatives follow.

**Run under `/auto`** is a derived option, not a declared one — no skill lists it in its row, and the row schema gains no field for it. It appears **iff taking the default hop would not immediately halt `auto`**: the default skill is not interactive-only, and the artifact does not sit at a gate label. Its meaning is "go AFK from here": delegate the rest of the chain to `auto` starting at the default hop, running to the next halt, rather than walking it one interactive step at a time. Choosing it invokes `/auto <default-skill> <target>` (e.g. `/auto pickup 27`); the plain default option, by contrast, takes a single interactive hop. It sits **after the default, before the alternatives**.

That one condition is the whole rule — there is no separate per-skill flag behind it. For a labelled work-item the readiness label decides through it: a `ready-for-agent` issue sits at no gate label, so the default hop into `pickup` is enterable and the option shows; a `ready-for-human` issue sits at a gate label, so `auto` would halt and the option does not show. For an unlabelled artifact (findings, a report) only the default skill's interactive-only status matters.

This is an action, not a closing summary — every skill ends by *firing* this `AskUserQuestion`, never by describing the next step in prose.

Same shape in every skill — consistent wording is the point. The user picks the hop; the skill then invokes that skill (via the Skill tool) or stops.

## Autonomy: one property, two gates

`auto` (see [auto/SKILL.md](auto/SKILL.md)) walks the default chain without asking. It needs to know only where it must *not* go, and that comes from two things — a property of skills and a pair of tracker labels. These are `auto`'s two stop conditions; nothing else halts it.

**Interactive-only skills.** A skill is **interactive-only** when it contains a human loop — an interview, a judgment quiz, or an approval step — with no safe unattended default. `auto` never enters one. The set is `grill`, `deepen`, `triage`, `slice`, `field`, `release`, and `land`. This is the one place that property is defined; the handover row carries no autonomy field.

**Gate labels.** Two tracker labels are an autonomous run's only halt points: `needs-triage` (a finding awaiting a human's triage decision) and `ready-for-human` (a slice whose implementation carries a judgment a human must make). `auto` never acts on an artifact sitting at either — it leaves the work staged there and stops. The readiness label likewise carries the work item's autonomy: `ready-for-human` (HITL) gates; its counterpart `ready-for-agent` (AFK) does not, so an AFK issue runs unattended through `pickup` and its implement loop.

**Internal gates** — a gate *inside* a skill (a cull, a green-bar, a grilling loop), which has no default hop to take — are not this contract's concern. Each skill resolves its own: an interactive-only skill by holding for the human, every other skill by an unattended default stated **in its own body** (e.g. *"skip the interactive cull, file survivors with confidence ≥ medium"*). Stop-and-stage is the default policy — push through an internal gate unattended only when it is genuinely safe and reversible, and say so where it's declared.
