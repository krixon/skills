# 7. Bot identity: a conditional gh form guarded by an env-validation hook

Status: Accepted

## Context

A repo can configure a machine account (`$GITHUB_BOT_ACCOUNT`, `$GITHUB_BOT_TOKEN_CMD`) so PRs open as a bot rather than the maintainer — GitHub forbids self-approval, so a maintainer-authored PR can't be approved by that maintainer, and a separate bot author is what keeps the review loop possible. When no bot is configured, `gh` should run as whatever account it is already authenticated as, with zero extra setup — the multi-dev default the plugin ships.

So identity is an optional layer with two valid states: **both vars set** (bot) and **both unset** (default `gh`). The danger is the third shape — one var without the other, or either set but empty — where a `gh` call silently falls through to the wrong account. PR #173 is the recorded instance: a PR opened as the maintainer because the call ran without the token.

Closing that silent-fallback gap reliably, without imposing setup on the multi-dev majority, defeated four runtime mechanisms in turn:

- **A `PreToolUse` Bash hook scanning command strings** for `gh pr create` and write patterns. False-positived on every doc, commit message, issue body, and skill line that *named* the command — the data-vs-instruction ambiguity of a shell string can't be closed by matching the string.
- **A `bin/gh` PATH shim** shadowing the system `gh`, acting on argv (which bash splits before the shim runs, so data tokens never trip it). But it activates only if something puts the plugin's `bin/` ahead of `gh` on PATH, and the plugin manifest has no `bin` field and Claude Code has no mechanism that adds one. The shim ran nowhere in plugin-install; in dev it depended on a PATH prepend that (next item) broke.
- **A PATH override in `.claude/settings.json` env** to force `bin/` onto PATH. Broke every hook, because env-block values don't interpolate `${PATH}` — PATH became the literal `<repo>/bin:${PATH}` and system binaries vanished (#174 → reverted #175).
- **`GH_CONFIG_DIR` isolation** and the **canonical-form rewrite** (mandatory two vars, `GH_TOKEN=$(eval …)` prefixed onto all ~37 literals). The first needs a per-repo isolation directory the next consumer won't replicate; the second forces every multi-dev user to configure the vars they were trying to avoid, and was rejected on review for exactly that.

The common shape: each layer tried to *catch the agent issuing a `gh` call without the right prefix*, and each either false-positived, rested on a PATH mechanism that doesn't exist, or imposed setup the multi-dev case must not carry.

## Decision

Keep the two-var **conditional** form as the contract in `skills/GITHUB.md`, and guard only the one state that can't be expressed as a copy-paste literal — the half-configured one — with a hook that reads the **environment**, not the command.

- `GITHUB.md` documents the conditional literal: prefix `gh` writes with `GH_TOKEN=$(eval "$GITHUB_BOT_TOKEN_CMD")` and filter rework on `--author "$GITHUB_BOT_ACCOUNT"` when the bot is configured; drop both when it isn't. Both valid states are a literal the agent copies.
- `hooks/gh-identity.sh`, a `PreToolUse(Bash)` hook, classifies the two vars: both unset → allow (default `gh`); both set and non-empty → allow (bot); anything else → **deny**, naming which var is wrong, before any shell command runs. It reads the env only — there is no command matching to false-positive on, so a `gh` phrase appearing as data is inert.
- The `bin/gh` shim and its test are deleted. It never activated in plugin-install and its dev activation was reverted; it was dead code.

The hook is registered in `hooks/hooks.json` (`${CLAUDE_PLUGIN_ROOT}`) and mirrored in `.claude/settings.json` (`${CLAUDE_PROJECT_DIR}`), matching the existing dual-registered hooks.

## Considered Options

- **The four runtime mechanisms above** — command-scanning hook, PATH shim, PATH override, `GH_CONFIG_DIR`/canonical-form. Rejected for the reasons in *Context*: false positives, a missing PATH mechanism, broken interpolation, or setup the multi-dev case must not carry.
- **Documented rule only**, no hook — the three branches written in `GITHUB.md` for the agent to apply. Rejected: the dangerous half-configured branch would then depend on the agent noticing, which is the failure the whole history is about. The hook is the one branch that must be enforced rather than described.
- **An env-validation hook gating only the half-configured state** (accepted). The two copy-paste-able states stay in the contract where the agent already reads them; the one un-expressible state — a misconfiguration, not an agent choice — is the only thing enforced, and it's enforced on env, dodging both the false-positive and PATH-dependency traps.

## Consequences

The half-configured state stops loudly at the first shell command, with a message naming the offending var — no silent wrong-identity PR from a partial config. The two valid states are untouched, so multi-dev keeps its zero-config default and the bot setup stays two env vars.

The hook denies *all* Bash while half-configured, not just `gh` — the price of reading the env rather than the command. That blast radius is bounded to a genuinely broken configuration (a fully-unset or fully-set repo is never blocked), and refusing to proceed until it's fixed is the intended "stop and report".

The residual gap the rejected mechanisms chased — the agent issuing a `gh` write without the prefix while *fully* configured — is not closed by this hook. It surfaces visibly at PR-approval time (the maintainer can't self-approve a PR that opened under their own identity), which is the recoverable failure the earlier, more invasive layers each broke something to prevent.
