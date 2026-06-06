# Writing

Rules for durable prose — commit messages, code comments, issues, findings, ADRs, docs. Companion to [VOICE.md](VOICE.md): that governs how you talk to the user in chat; this governs what you leave behind in the repo and tracker.

Unlike voice, these don't apply every turn. A prose-producing skill `@`-references this file at the point it writes, and the reader skips sections that don't apply.

## Core

The one rule everything else serves: **if it doesn't need saying, don't say it; when it does, say it plainly.**

- Cut what the artifact survives without — filler words, throat-clearing, restating the obvious, summaries of what's already visible.
- Lead with the conclusion, then the support. Active, declarative voice.
- No hedging when you know. Reserve *might / could / likely / seems* for genuine uncertainty, and say what would resolve it.
- Mark assumed vs verified. Distinguish what you checked from what you're inferring; don't imply you checked when you didn't.
- Never fabricate — no invented APIs, paths, flags, numbers, or citations.
- Write the current truth, not the change that produced it. In standing artifacts — code, comments, docs, ADRs, issues — no *this no longer / updated to / previously / now uses / renamed from*. Describe what *is*, as if it had always been so. History is git's job; reach for the past only when a past state is load-bearing for understanding the present (the commit message is the one place change itself belongs).

### The subtract pass

A required action, not a property to aim for. The rules above describe good prose; this is how you get there. The first draft always carries weight the writer can't see while writing it — the pass is where you find it.

After drafting any artifact, before emitting: re-read and delete every word, sentence, and section it survives without. Cut any sentence that restates the title, the diff, or the sentence before it. Collapse a hedge into the claim it surrounds. If nothing got shorter, you didn't run the pass.

A finding's evidence line, before and after:

> Before: *It appears that the discount branch may potentially never actually be exercised by the current test suite, which basically means that the rounding logic living there is essentially left completely unverified at this point in time.* (38 words)
>
> After: *The discount branch is never exercised, so its rounding logic is unverified.* (12 words)

The cut removed hedges (*appears / may / potentially*), filler (*actually / basically / essentially / completely*), and a temporal clause that said nothing (*at this point in time*) — no fact was lost.

## Commit messages

- Imperative subject line — "Fix race in capture dedup", not "Fixed" / "Fixes" / "This commit fixes". One line, no trailing period, ~50 chars.
- Body explains *why*, not what the diff already shows — the reader can see *what* changed; give them the reason.
- Skip the body when the subject is self-evident. Don't pad a one-line change with a paragraph.
- No "as requested", "per discussion", "various fixes". Say the actual change.

## Code comments

- Comment the *why*, never narrate the *what*. If the code says what it does, a comment repeating it is noise — delete it.
- Earn the comment: non-obvious intent, a constraint that isn't visible locally, why the obvious approach was rejected, a workaround and the thing it works around.
- No commented-out code, no changelog comments ("fixed X", "now handles Y"), no attributions — that's what git is for.
- Don't point outward at usage. A comment naming who calls this, or where it's used — even loosely ("called from the worker", "used by the API layer") — rots the instant a caller moves, and it's find-references' job, not the code's. Describe what this code guarantees, not who relies on it.
- Keep them true. A stale comment is worse than none; update or delete it when the code moves.

## Issues & findings

- Lead with the problem and its impact, not the backstory. First line should tell the reader what's wrong and why it matters.
- Concrete location and repro — file, line, the steps or input that triggers it. A finding without a location is a guess.
- Mark assumed vs verified. "Throws on null `user`" (verified) reads differently from "likely unsafe under concurrent writes" (inferred) — label which.
- No speculation dressed as fact, no severity inflation. State what you observed; if you didn't confirm the impact, say so.
- Don't hard-wrap a body bound for a GitHub issue, comment, or PR. Write one paragraph per physical line — GitHub turns mid-paragraph newlines into `<br>`, so column-wrapped text renders ragged. Commit bodies are the opposite (wrap those). See [skills/GITHUB.md](skills/GITHUB.md) → *Body formatting*.

## ADRs

- Structure: context → decision → consequences. What forces the choice, what you chose, what it costs.
- Record the tradeoff and the rejected alternatives, not a justification of the winner. The value of an ADR is knowing *why not the other thing*.
- Past tense for the decision once made ("We chose X"); present for the standing consequence.
- Don't sell. An ADR documents a choice for the next reader; it isn't persuasion.

## Docs

- Task-first and declarative. The reader wants to do a thing — open with how, not with history or motivation they didn't ask for.
- No marketing tone, no *simply / just / easy / powerful*. If a step is easy the reader will find it so; saying it makes the hard ones feel like failures.
- Show the command or code, then the one line of why it's shaped that way if it isn't obvious. Don't wrap the whole page in prose.
- Keep examples runnable and real — no `foo` / `bar` placeholders where a concrete value would teach more.
