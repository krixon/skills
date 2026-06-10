# 0008 — Deterministic workflow mechanics move into a code adapter; commands are the entry point, agents are spawned only for synthesis

## Status

Accepted.

Consolidates and replaces the earlier tracker-binding, Jira-binding, and bot-identity ADRs, removed in the same change because they record state this decision retires — hence the gaps at 0004, 0006, and 0007 in the sequence. The context worth keeping from them is captured below. The standing decisions they don't touch survive: native issue relations (0001), the release policy (0002), the untrusted-content security boundary (0003), and the dogfood symlink farm (0005); the adapter *implements* the first two, it does not obsolete them.

## Context

The workflow skills are mostly deterministic mechanics wrapped around a thin judgment core, and the mechanics are expressed as **prose the model must re-read and obey every run** rather than code that is simply correct. Three costs follow.

**Enforcement is probabilistic where it should be structural.** Bot-account identity is the proof. A repo can configure a machine account (`$GITHUB_BOT_ACCOUNT`, `$GITHUB_BOT_TOKEN_CMD`) so PRs open as a bot, not the maintainer — GitHub forbids self-approval, so a maintainer-authored PR can't be approved by that maintainer, and a separate bot author is what keeps the review loop possible. Closing the silent-fallback gap — where a `gh` write runs without the bot prefix and opens a PR under the wrong identity — defeated four runtime mechanisms in turn:

- a `PreToolUse` hook scanning command *strings* for `gh` write patterns — false-positived on every doc, commit, and skill line that merely *named* the command; the data-vs-instruction ambiguity of a shell string can't be matched away;
- a `bin/gh` PATH shim acting on argv — never activated, because the plugin manifest has no `bin` field and Claude Code adds nothing to PATH;
- a PATH override in `settings.json` env to force the shim onto PATH — broke every hook, because env values don't interpolate `${PATH}`;
- `GH_CONFIG_DIR` isolation and a canonical-form rewrite prefixing `GH_TOKEN=$(eval …)` onto all ~37 literals — the first needs a per-repo dir the next consumer won't replicate; the second forces every multi-dev user to configure vars they were trying to avoid.

The accepted resolution kept the conditional form in prose and guarded only the half-configured env state with a hook — leaving one gap open by design: *the agent issuing a `gh` write without the prefix while fully configured*. Every one of these mechanisms exists **only because the agent issues `gh` directly**. The identity is something the model can get wrong because the model makes the call.

**The prose carries correctness rules the model must recall.** The GitHub binding file (≈166 lines) is a catalogue of mechanics the skill is trusted to apply: drop `--author` when the bot is unset; re-query when `mergeable` may be stale; type `sub_issue_id` with `-F` or eat an HTTP 422; never fall through to `--merge`; check an approval covers HEAD; pass bodies out-of-band per the security boundary. Each is an invariant a function would hold unconditionally and the model holds only by remembering.

**It costs tokens.** The GitHub and Jira binding files, the claim mechanics in `CONCURRENCY.md`, and the git incantations in `ISOLATION.md` sit in context so skills can carry "how" alongside "what" and "why".

The design already keeps skills tracker-neutral — they express the workflow in concepts, and a single binding file names the tracker; a consuming repo that tracks issues in Jira routes through a second binding that speaks via the approved Rovo MCP connector. That neutrality is the right boundary; this decision moves it from prose into code and extends it across the last visible seam.

Underneath all of this is a sharper distinction than "deterministic vs judgment". There are **three** kinds of step:

1. **Deterministic execution** — pure mechanics.
2. **Human *decision*, deterministic execution** — the judgment is real but needs no *model*; it needs a person to choose to run the thing. "Is now the time to release" is human judgment whose execution is wholly mechanical.
3. **Model *synthesis*** — work whose execution itself requires a model: implementing, grilling, drafting slices, writing prose.

A skill (an agent) is justified only at (3). Both (1) and (2) are commands — for (2), the act of invoking *is* the judgment. The prior framing treated (2) as skill-worthy and paid for it in prose.

## Decision

Move every deterministic mechanic into a code adapter that commands invoke. Skills shrink to their bucket-(3) synthesis core; bucket-(1) and bucket-(2) skills collapse into commands. The tracker becomes invisible to skills on **both** backends.

### The adapter surface

Three command groups, invoked by absolute path under `${CLAUDE_PLUGIN_ROOT}/bin/` — not via PATH (the failed shim showed Claude Code adds no `bin` to PATH; explicit plugin-root invocation sidesteps that). Substrate is a single **Python (stdlib-only) entry point** orchestrating `gh` and `git` as subprocesses: `gh` stays the GitHub backend (it owns the token dance, GraphQL, and merge-method discovery far better than a re-rolled REST client), while the Jira REST backend uses `urllib` + `json`, which *drops* `curl` and `jq` rather than adding a dependency. Bash was the first instinct but loses on the Jira REST backend's JSON shaping — the most error-prone code in the adapter and the part that must be unit-tested — and Python3 stdlib holds the zero-extra-install promise as well as bash on any macOS/Linux box. (Open question on substrate, below, resolved here.)

- **`tracker`** — the single namer of GitHub and Jira. Dispatches on `$ISSUE_TRACKER` (`github` | `jira`) to a `gh` backend or a Jira REST backend, both in code. **Identity is internal**: `tracker pr create` performs the `GH_TOKEN` dance itself; the agent never chooses an identity because it never issues the call. Covers issues (create/view/list/comment/label/close), relations (sub-issue, blocked-by), claims (advisory assign + branch-ref CAS), PR + review-thread mechanics, selection queries (`next`, `sweep-stale`, `rework`), and release publish.
- **`worktree`** — isolation. `create` / `rebase` / `teardown` / `sync-main`, names per ISOLATION.md. Pure git, tracker-agnostic. `rebase` has a **single owner** — the rework path (`pickup`); `land` never calls it (see *Commands present or act*).
- **`version`** — versioning. `derive` (range since last `v*` tag → classify → materiality filter → semver bump + grouped notes, per the release policy) and `apply` (worktree, bump, tag, push, teardown). Pure git + semver.

### Commands present or act; they never prompt

Every command is one of two stdin-free shapes: **present** (emit options as JSON/text, exit) or **act** (perform one mutation, exit). Interactivity is never the binary's job — it has no TTY in any agent context. Bodies always pass via stdin (`--body-file -`), so the security boundary's out-of-band rule becomes the only calling convention instead of a rule the model applies.

A pure command (the bucket-(1)/(2) commands below) **halts at synthesis** — on reaching a state only a model can resolve, it presents the blocker and exits; it never silently degrades into doing the synthesis, and it never spawns to cover it. That keeps `land` honestly a pure command: it merges what GitHub will merge (ready-to-merge, approval-covers-HEAD, bot-owned) and **never rebases** — rebasing a moved base is rework, owned solely by `pickup`, so `land` has no conflict trapdoor to meet. A clean, approved PR that is *behind and blocked* under up-to-date-required protection is therefore a **rework trigger** (alongside CONFLICTING/DIRTY), routed to `pickup`, not rebased in place by `land`. Only the designated commands (next section) spawn; the rest halt.

### The entry point inverts; agents are spawned, not wrapping

The human (or a loop) runs a **command**, not a skill. The command does the deterministic work, presents, and where bucket-(3) synthesis is reached, **launches an agent** with a constructed prompt. Three handoff modes:

- **Headless** (`claude -p "<brief>" --output-format json --json-schema <outcome-schema>`) — no human after launch (pickup-implement, drain loops). The spawner needs the run's outcome back, and `--json-schema` is the *only* reliable machine-parseable channel: it populates a validated `structured_output` the parent parses (e.g. `{pr_opened, pr_number, walled, reason}`); plain `--output-format json` returns the run's final assistant text in `result`, which the parent would otherwise have to scrape. So the outcome schema is part of the spawn contract, and the constructed brief instructs the agent to conform. Exit code is necessary-not-sufficient (non-zero = failure; zero does not guarantee a usable result).
- **Interactive terminal** (`exec claude "<seed>"`, shell-entry only) — the human drives from the first turn (triage, design). Possible *only* because the entry point is the human's shell; an interactive agent cannot be a child of a tool call.
- **In-session** — a slash command whose `!`bash-injection runs a *present* command and feeds its output into the turn; the agent renders the menu, the human picks **in chat** (the agent is the interactive surface), the agent then calls an *act* command. No spawn.

The command always owns isolation (`worktree create`, claim) *before* spawning, so the agent wakes already on its branch.

### Skills that remain, and skills that collapse

- **Collapse to a pure command (no agent):** `release`, `reap`, `land`, the work-offering menu.
- **Command launches agent:** `pickup`, `triage`, `capture` — present + transitions are commands; the synthesis is a spawned (or in-session) agent.
- **Stay agent-native skills:** `tdd`, `diagnose`, `design`, `discover`, `field`, `slice`, `deepen`, the `audit-*`, `write-skill`, `verify`. Synthesis from the first move.

## Considered Options

- **Status quo — prose bindings plus the env-validation hook.** Rejected: the bot-identity gap is unclosable in prose, and the token + correctness-recall costs persist.
- **A skill wraps the command** (skill stays the entry point, calls the adapter). Rejected: it can't perform the interactive-terminal handoff (a skill runs inside an agent loop, which has no TTY), and it keeps bucket-(2) work dressed as a skill.
- **Adapter for GitHub + git only; Jira issues stay on the Rovo MCP** (the conservative scope). Rejected — but for a sharper reason than "a partly-split model": **a CLI subprocess cannot reach an in-agent MCP tool.** MCP tools live in the model's tool loop; nothing invokes them from a spawned `bin/tracker` process. So routing Jira through the MCP was never the same shape as "the adapter dispatches to a backend" — on MCP the *agent* makes the call, on a CLI backend the *subprocess* does, and the two are architecturally incompatible. MCP was therefore never eligible to be an adapter backend at all; keeping it would mean the code-adapter inversion simply does not apply on Jira (the agent is back to naming tracker operations there). The symmetry that settles it: connector-mandated orgs cannot run a REST backend, but connector-*less* orgs cannot run the MCP — neither single substrate serves everyone, and only REST is reachable from the CLI.
- **Full coverage including a Jira REST backend** (chosen). REST is the only Jira backend the adapter can host, so it is also the only one that serves connector-less consumers; the agent never touches issue mechanics on either backend. Cost: it reintroduces a managed Jira credential (below), which closes the door for connector-mandated deployments — recorded, not hand-waved.

## Consequences

**The bot-identity gap closes structurally.** Identity is correct by construction — the agent has no `gh` call to mis-prefix. The `gh-identity.sh` hook retires; its env-validation (refuse the half-configured state) moves into the adapter's startup check, where it guards the Jira credential too.

**The binding catalogues collapse to a glossary.** The GitHub and Jira binding files lose their command bodies; what survives is the tracker-neutral concept glossary. The git incantations leave `ISOLATION.md` and the claim mechanics leave `CONCURRENCY.md`. Large token reduction across every workflow turn.

**The deterministic core becomes testable.** Merge-method discovery, the stale-`mergeable` re-query, semver derivation, branch naming — all gain real unit tests, impossible for prose.

**Jira REST reintroduces a managed credential — the recorded cost of full coverage.** The current Jira binding chose the Rovo MCP precisely to avoid a Jira token. The REST backend needs one — a `JIRA_TOKEN_CMD`-style indirection mirroring `GITHUB_BOT_TOKEN_CMD`. For an org whose security policy *mandates* the approved Atlassian connector and forbids managed service tokens, this is not a trade-off to weigh — the Jira backend is a **closed door**, and that deployment's only paths are GitHub or a token exception. That cost is the accepted price of the only Jira backend a CLI adapter can reach (see Considered Options). The Jira design worth preserving moves intact into the REST backend: native-primitive concept mapping (category/structure labels → issue types, execution/closure states → statuses, triage states → labels), status reads and transitions resolved by the platform-stable `statusCategory.key` (never by status name or transition id, so a project workflow rename can't break it), issue id treated as an opaque string with the branch name as the truth-of-record link, and the key embedded in the PR title's Conventional-Commits description. The unauthenticated-MCP stop `auto` carried becomes an adapter-side token-presence check.

**The seam lands per-skill behind a pre-built adapter — not as an atomic repo cutover.** The incoherent state worth avoiding is a *single skill* speaking both vocabularies at once, not the repo having some flipped skills and some prose ones for a while. So the sequencing is: build the adapter first as **pure addition** (`bin/tracker`, `bin/worktree`, `bin/version` plus their unit tests, naming nothing in any skill — skills keep working on prose throughout), then flip skills to it **one at a time**, stripping the matching prose as the last referent of each binding section goes. The binding files shrink incrementally; no monster PR. Acceptance check, per skill: no `SKILL.md` or command names `gh`/`curl`/a Jira REST path or a git mutation, and none names *both* the adapter and a raw command — the adapter is the only namer within any flipped skill. (This is also how `slice` should cut the work: a foundational adapter-build epic, then one issue per skill flip.)

**Distribution needs no install hook.** Skills/commands invoke `${CLAUDE_PLUGIN_ROOT}/bin/tracker` by absolute path, which works in plugin-install and dev alike. The executable bit is the committed file mode: a marketplace install is a git clone, which reproduces the committed tree, so the entry-point binaries arrive executable with no install step. A regression test pins the invariant (every extensionless file directly under `bin/` is committed `100755`; the importable `bin/adapter/*.py` modules are `100644`). The substrate is verified at startup by `bin/adapter/preflight.py`, wired into each entry point ahead of the command — each declaring the tools it actually uses, so the pure-git `worktree` group requires only `git`, not `gh`. A missing prerequisite stops the run with the `cli.halt` envelope on stderr and a non-zero exit instead of a cryptic exec failure.

## Open questions

Resolved during the design session:

- **Runtime substrate** — resolved: Python stdlib entry point orchestrating `gh`/`git` subprocesses (see *The adapter surface*). Settled by the REST decision — the Jira backend's JSON shaping is what bash rots on.
- **Result hand-back from headless agents** — resolved: `claude -p --output-format json --json-schema <outcome-schema>`, with the schema as part of the spawn contract (see *Headless* handoff). `--json-schema`'s `structured_output` is the only reliable machine-parseable channel; plain `result` is free text. Exit code is necessary-not-sufficient.

Resolved during build:

- **Distribution / executable bit** — resolved: the executable bit is the committed file mode (a clone reproduces it), pinned by a regression test; the substrate is verified by a startup preflight in each entry point (see *Distribution needs no install hook* in Consequences). No plugin install hook needed.

Still open, to settle during build:

- **Slash-command `!`-injection permission portability** — prefix allow-rules *do* suppress the prompt, but they are matched against the **literal, pre-expansion** command string, and `${CLAUDE_PLUGIN_ROOT}` is not a documented substitution variable for permission strings (the documented one for bundled paths is `${CLAUDE_SKILL_DIR}`). So a portable `Bash(${CLAUDE_PLUGIN_ROOT}/bin/tracker:*)` rule likely won't match the expanded install path, and the expanded path varies per install. Spike at build time: confirm whether `CLAUDE_PLUGIN_ROOT` expands in permission matching; if not, fall back to a settings-level rule against the resolved path or route in-session `present` calls through the normal Bash tool rather than `!`-injection. (The env-prefix gotcha cuts in our favour — env prefixes are stripped before matching, and the adapter owns identity internally, so these calls carry no `GH_TOKEN=$(…)` prefix.)
