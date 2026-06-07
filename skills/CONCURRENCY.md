# Concurrency

How concurrent sessions coordinate so two never collide on the same work. The shared principle the skills reference rather than restate: [ISOLATION.md](../ISOLATION.md) keeps their working trees apart, this keeps their *claims* apart.

## Two classes of contention

A contended write is arbitrated by one of two mechanisms, chosen by whether a human watches it:

- **No human watching → natural compare-and-swap.** Where the write is atomic and the loser learns instantly, lean on the medium's own CAS — no extra protocol. Creating a branch ref, pushing a tag: the second writer is rejected by the operation itself, and that rejection *is* the coordination.
- **A human watching → advisory assignee claim.** Where the contended thing is a unit of work a person picks up — an issue — there's no atomic write to lose, so coordination is advisory: claim the issue by self-assigning, honor an existing claim by skipping.

CAS is exact but exists only where the medium provides it; the assignee claim is best-effort but covers the gap where selection, not a single write, is what races.

## The assignee claim

For work a session selects and then holds open across many writes (`pickup` taking an issue), the claim is the assignee:

- **Self-assign on entry** — claim the issue by assigning yourself the moment you take it, before any work.
- **Surface who and since-when on collision** — if it's already assigned to another session, don't grab it; report who holds it and since when (the assignment's timestamp).
- **Unassign on clean exit** — release the claim when you leave the work in a resting state another session could resume.

**No heartbeat, no time-box, no auto-reap.** The claim never expires on its own and nothing reaps a stale one. A session that dies holding a claim leaves it held; clearing it is a human's call, not a timer's. This trades automatic recovery for never yanking work from under a live session.

## Selection sites vs commit sites

The two classes attach at different points in a skill:

- **A selection site** chooses what to work on (the next-ready query, the rework scan). It **must honor claims** — filter out anything already claimed, so two sessions don't pick the same unit.
- **A commit site** performs the contended write (creating the branch ref, pushing a tag). It **carries CAS or the advisory claim** — either the write is atomic and self-arbitrating, or it's covered by the claim taken at selection.
