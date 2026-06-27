# 0010 — Isolation has two stances: strict worktree (default) and branch-in-primary

## Status

Proposed. Extends ADR 0008 (the `worktree` command group) and reframes ISOLATION.md from one invariant to two stances.

## Context

ISOLATION.md holds one invariant: the repo-root checkout is read-only, and every change is made in a worktree on its own branch. That invariant buys concurrency safety — no two sessions share a working tree, so the claim mechanics, `auto`, and CONCURRENCY.md are collision-proof — and ADR 0008 moved its git mechanics into the `worktree` command group (`create` / `rebase` / `teardown` / `sync-main`).

The single-session developer pays the invariant's cost without using what it buys. A fresh worktree starts empty of the working-directory state a project accretes: `node_modules`, virtualenvs, build caches, language-server indexes, `.env` files. Each new worktree forces a reinstall, a rebuild, and a cold IDE re-index; N concurrent tasks mean N copies of that state on disk. A developer on one machine who never runs two sessions against one repo pays this for a guarantee they never exercise.

Switching branches inside one checkout avoids all of it — `node_modules`, build artifacts, and IDE indexes live in the working directory and survive `git checkout`. But it deletes the invariant: the primary checkout is no longer read-only, and two sessions switching its branch collide.

## Decision

Isolation has two stances, selected per invocation with a per-repo default:

- **strict worktree** (default) — today's model, unchanged. Every change in `.claude/worktrees/<slug>` on its own branch; repo-root read-only; concurrency-safe.
- **branch-in-primary** — the change is made on a branch checked out in the primary checkout itself, no worktree. Single-session only: it forfeits the read-only-root invariant and the concurrency guarantee in exchange for preserving warm working-directory state.

Selection is `--isolation worktree|branch` on `worktree create`, overriding `$ISOLATION_MODE`, which defaults to `worktree` when unset. The flag is per-invocation so a caller opts one task into branch mode without changing the repo's stance; the env var sets that stance once for a repo whose owner always wants it.

Branch mode has no separate directory to make collisions structurally impossible, so it substitutes a precondition the adapter checks at `create`: the primary checkout must be clean and on `BASE`. A dirty tree or an already-checked-out feature branch halts with `outcome: conflict` instead of switching — the compare-and-swap the worktree's separate directory gave for free. Two concurrent branch-mode creates cannot both pass it: the second sees the first's branch and halts.

`worktree create` returns `path` under both stances — the worktree directory in strict mode, `repo_root` in branch mode — plus an `isolation` field. Downstream commands key off `path` and stay stance-agnostic: `rebase` operates on the path it is given (the branch is live there either way); `teardown` removes-and-deletes in strict mode and runs `checkout BASE; branch -D` in branch mode; `sync-main` is unchanged and correctly skips when a feature branch occupies the primary checkout.

ISOLATION.md stops asserting one invariant and frames the two stances and when each applies. Per ADR 0008 its git incantations had already moved to the adapter, so what remains to change is the conceptual frame.

### The backstop hook keys off branch state, not mode config

`hooks/worktree-only-edits.sh` is the always-on backstop for the read-only-root invariant: it denies any `Edit`/`Write` whose target resolves inside the main checkout but outside `.claude/worktrees/`. Branch mode edits the main checkout itself, so the hook as written blocks every branch-mode write. It also cannot see the stance: `--isolation` is an adapter argument and `$ISOLATION_MODE` is session env the hook would have to trust, neither a reliable signal at edit time.

So the hook keys off the one signal that is always present and always correct — the main checkout's current branch. The rule sharpens from "deny edits to the main checkout" to **"deny edits to the main checkout while it is on `BASE`; allow them on a feature branch."** This needs no mode knowledge: strict mode keeps the main checkout on `BASE`, so its edits stay denied and the guarantee is unchanged; branch mode sits the main checkout on a feature branch, so its edits are allowed. The branch state *is* the stance.

The cost: in strict mode, a feature branch manually checked out in the main checkout would now accept edits there. That state *is* branch mode — once the main checkout is off `BASE`, there is no read-only-root invariant left to protect, so there is no distinction the hook could honour. The guarantee it still enforces unconditionally is the one that matters: no edit to the main checkout while it holds `BASE`.

## Considered Options

- **One stance only (status quo, strict worktree).** Rejected: it makes the single-session developer pay worktree setup — reinstall, rebuild, re-index — for a concurrency guarantee they never use. IDE/tooling and disk overhead are the stated driver.
- **Replace worktrees with branch-in-primary outright.** Rejected: it deletes the guarantee `auto` and the claim mechanics depend on. The repo still runs concurrent sessions, so strict mode must remain and stay the default.
- **Env var only, no per-invocation flag.** Rejected: a repo that mostly runs concurrent worktree work may still want one task in branch mode without flipping the repo-wide stance. Per-invocation override with an env default serves both.
- **Auto-detect the stance** (branch mode when one session is live, worktree otherwise). Rejected: implicit and racy — "only one session" is not knowable without the coordination the worktree model exists to avoid, and a wrong guess switches the primary checkout's branch under a second session.
- **A new outcome code for the branch-mode precondition failure.** Rejected: the closed outcome vocabulary (ADR 0009) already carries `conflict`, and "the primary checkout's state conflicts with this op" is that shape — a state the command won't force past. No new token earns its place.
- **Gate the backstop hook on `$ISOLATION_MODE`.** Rejected: the hook fires per edit and would have to trust session env that the per-invocation `--isolation` flag never sets, so a flag-selected branch-mode session would still be blocked. Keying off the main checkout's branch needs no config and is correct under both selection paths.

## Consequences

The single-session developer opts a repo or a task into branch mode and keeps warm `node_modules`/build/IDE state across branches; the concurrent and unattended paths keep strict worktrees as the default, untouched. Mode selection is one resolver and one returned `path` field, so the rest of the workflow needs no per-stance branching beyond `teardown`'s two tails.

Branch mode is single-session by construction and says so. Choosing it in a repo that also runs concurrent sessions is the caller's risk, bounded by the clean-and-on-`BASE` precondition, which downgrades a silent collision into a `conflict` halt. Three surfaces learn the second stance, and no more: `worktree teardown` (a stranded feature branch in the primary checkout, torn down by `checkout BASE; branch -D`), `reap`'s orphaned-worktree sweep (which gains that same branch-mode shape), and the `worktree-only-edits` backstop hook (which re-bases its rule on the main checkout's branch, above).

CONCURRENCY.md's collision-proofness is a property of strict mode, not of isolation unconditionally. The claim mechanics (advisory assignee plus branch-ref CAS) are unchanged and apply in both stances — they coordinate *who works an issue*, independent of *where the working tree lives* — but the working-tree-level guarantee holds only under worktrees.
