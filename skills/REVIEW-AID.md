# Review aid

The shared convention for what a bot PR carries to assist a human's approve decision. Any bot PR opened for human review carries a **review-aid** section in its body — a coverage summary that lets the maintainer approve from a known-coverage account rather than from a cold read of the diff. The maintainer is the throughput ceiling of the unattended drain loop; the gap between "a PR is open" and "I can approve it" grows with queue depth, and this section closes it.

This is coverage **visibility**, not a second review. It does not re-run the bug hunt — the `/code-review` + `/security-review` gate already did that at PR-open ([pickup/SKILL.md](pickup/SKILL.md) step 6, [patch/SKILL.md](patch/SKILL.md) step 3). It reports what that gate found and how the diff maps to the contract; it adds no new judgment. That is why it lives in the PR body, not in a standalone skill.

## The section

A `## Review aid` heading at the foot of the PR body, below the `Closes #<n>` / `No-issue:` line and the prose. Three parts, in order:

1. **Acceptance-criterion coverage** — one row per criterion from the brief, each marked **met** / **partial** / **unmet** with `file:line` evidence pointing at where the diff satisfies it. A `partial` or `unmet` row states what is missing. The maintainer reads this against the brief's acceptance list to confirm the contract is honored.
2. **Residual risk** — what the agent is uncertain about: a judgment call it made, a path it couldn't exercise, an assumption the brief didn't settle. Empty is a valid value — say "none" rather than omitting the part. This is where the agent surfaces what a cold diff read would miss.
3. **Gate disposition** — the `/code-review` + `/security-review` outcome: **clean**, or **findings-found-and-fixed** with a line per finding and how it was addressed. The maintainer learns the gate ran and what it changed, not just that a gate exists.

## Degraded form

A PR opened without an agent brief — `patch`, which ships from the conversation — has no acceptance criteria to map. It carries parts 2 and 3 only: residual risk and gate disposition. The acceptance-criterion part is dropped, not faked. The heading and the remaining two parts are unchanged, so the maintainer reads the same section shape whichever skill opened the PR.

## Refresh, not append

On a rework round the PR body's section is **overwritten in place**, never appended. `pickup` re-runs the gate at each rework round (step 6), so the disposition, coverage, and risk are re-derived against the current diff and replace the prior section. The body carries one review-aid section reflecting the current state, not a changelog of past rounds — history is the PR's commit and review timeline, not the body.

## Scope

The aid sits **before** approval; it changes nothing downstream. `land` merges only what the maintainer approved and reads no part of this section — its surface is unchanged. The convention binds the two skills that open a bot PR for review (`pickup`, `patch`); it adds no skill and no label.
