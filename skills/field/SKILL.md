---
name: field
description: Field one or more questions put to the agent — form a reasoned answer to each and converge with the user on a shared understanding, one question at a time. Use when the user directs questions at you ("field these questions", "work through these review questions with me"), or when `pickup` hands over questions raised on a PR review.
argument-hint: "[one or more questions to field]"
---

Field each question put to you until we reach a shared understanding. Work the questions one at a time, in order — your input *is* the questions; there's nothing to fetch or classify.

For each question: explore the code or context as needed, then lead with your reasoned answer and the rationale behind it — you answer first and I react. You owe a position — don't turn the question back on me, I asked it. Then pressure-test that answer the way design pressure-tests a plan: surface the assumptions it rests on, mark what you verified versus what you're inferring, flag where you're uncertain and say what would resolve it, and invite me to push back. Converge before moving to the next question.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** shared understanding on the questions (in the conversation) — plus, where an agreed answer implies a change, the resulting change deltas.
- **default:** — (terminal; the understanding lives in the conversation, there's nothing to publish). **Embedded** (a parent skill passed the `embedded` mode and will consume the result): don't render this prompt — return the converged answers and any change deltas to the caller.
- **alternatives:** stop

**Interactive-only** (per [../HANDOVER.md](../HANDOVER.md)) — a question needs the human; there's no safe unattended default, so `auto` never enters it.
