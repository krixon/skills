"""The `triage` command group — drive issues through the triage state machine.

triage is a **command-launches-agent** (ADR 0008), and this binary is its
deterministic surface: *present* surfaces the actionable queue (or a single
candidate's full context) read-only; the act commands take/release the advisory
assignee claim and apply the state-machine label transitions. None makes a
model's judgment.

The synthesis triage needs — evaluating an issue, deciding which transition it
takes, and drafting the promoted brief or the notes that ride the transition —
sits between present and act, reached by the host agent in-session or a spawned
subagent under `auto` (never a headless `claude -p`; ADR 0008's spawn model). So
the binary presents the queue and the candidate, then applies exactly the
transition the agent decided — the brief/notes body rides stdin out-of-band
(SECURITY.md), never argv. That present→synthesis→act boundary copies the
`capture` reference: as much as is mechanical lives in the binary, the agent is
reached only for genuine model work.

Composes the tracker GithubBackend's `gh` seam — `issue_list`/`issue_view` and
the claim reads for present, `claim_assign`/`claim_release`, `issue_label`,
`issue_comment`, and `issue_close` for the acts — taken as a parameter so the
queue read and every transition are unit-tested against a canned runner without
the network.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Mapping, Sequence, TextIO

from adapter import cli, identity as identity_mod
from adapter.tracker import GithubBackend, _resolve_repo

# The five maintainer-owned state labels triage moves an issue between
# (skills/GITHUB.md). `in-progress` is pickup's, never triage's, so it is not in
# this set — a transition never strips or applies it.
STATE_LABELS = (
    "needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix",
)

# The two terminal ready states a promotion lands an issue in.
READY_LABELS = ("ready-for-agent", "ready-for-human")

# The two category labels; at most one rides a triaged issue.
CATEGORY_LABELS = ("bug", "enhancement")

# The two priority labels; at most one, set only on the maintainer's call.
PRIORITY_LABELS = ("priority:high", "priority:low")


def _states_on(issue: Mapping[str, Any]) -> list[str]:
    """The maintainer-owned state labels currently on an issue."""
    labels = set(issue.get("labels") or [])
    return [s for s in STATE_LABELS if s in labels]


def _summary(issue: Mapping[str, Any]) -> dict[str, Any]:
    """One queue row: the opaque id, title, and current labels."""
    return {
        "id": issue["id"],
        "title": issue.get("title"),
        "labels": issue.get("labels") or [],
    }


def gather(be: GithubBackend) -> dict[str, Any]:
    """The actionable triage queue, bucketed, with claimed work held aside.

    Three actionable buckets — never-triaged (unlabeled by any state), open
    `needs-triage`, and open `needs-info` — and a separate `claimed_elsewhere`
    bucket for any issue another session holds. A claimed issue is held aside
    even when it otherwise qualifies: honouring the claim is what stops two
    sessions triaging the same issue to divergent decisions (CONCURRENCY.md). The
    agent decides actionability over these buckets; this only reads and
    partitions. A holder reading is reported raw — whether one of the holders is
    *this* session is the agent's call from the presented logins, not the
    binary's (it never resolves "me").

    `needs-info` re-evaluation gating (reporter activity since the last notes) is
    a judgment the agent makes from the candidate's comments via present --id, so
    every open `needs-info` issue is surfaced here, not pre-filtered.
    """
    issues = be.issue_list(state="open")
    unlabeled: list[dict[str, Any]] = []
    needs_triage: list[dict[str, Any]] = []
    needs_info: list[dict[str, Any]] = []
    claimed: list[dict[str, Any]] = []
    for issue in issues:
        number = issue["id"]
        holders = be.claim_holder(number)["info"]["holders"]
        if holders:
            since = be.claim_since(number)["info"]["since"]
            row = _summary(issue)
            row["holders"] = holders
            row["since"] = since
            claimed.append(row)
            continue
        states = _states_on(issue)
        if not states:
            unlabeled.append(_summary(issue))
        elif "needs-triage" in states:
            needs_triage.append(_summary(issue))
        elif "needs-info" in states:
            needs_info.append(_summary(issue))
    return {
        "unlabeled": unlabeled,
        "needs_triage": needs_triage,
        "needs_info": needs_info,
        "claimed_elsewhere": claimed,
        "counts": {
            "unlabeled": len(unlabeled),
            "needs_triage": len(needs_triage),
            "needs_info": len(needs_info),
            "claimed_elsewhere": len(claimed),
        },
    }


def candidate(be: GithubBackend, id: str) -> dict[str, Any]:
    """One issue's full triage context: the issue (body, comments, labels) plus
    its current claim holder and since-when, so the agent evaluates and the
    human sees who holds it before a claim is taken."""
    issue = be.issue_view(id)
    holder = be.claim_holder(id)
    since = be.claim_since(id)
    issue["claim"] = {
        "holders": holder["info"]["holders"],
        "since": since["info"]["since"],
    }
    issue["current_states"] = _states_on(issue)
    return issue


def present(be: GithubBackend, id: str | None,
            stream: TextIO | None = None) -> int:
    """Present the queue, or a single candidate's full context with --id. Read-
    only: the agent evaluates from this, the human decides, and an act applies
    exactly the chosen transition."""
    if id:
        return cli.present_json(candidate(be, id), stream=stream)
    return cli.present_json(gather(be), stream=stream)


# --- claim (advisory) -------------------------------------------------------

def claim(be: GithubBackend, id: str, force: bool = False,
          stream: TextIO | None = None) -> int:
    """Take the advisory assignee claim, refusing a held issue unless forced.

    Re-reads the holders immediately before taking it: a held issue is surfaced
    as a halt (who holds it, since when) rather than grabbed, so the maintainer
    decides — proceed anyway, reap the stale claim, or pick other work
    (CONCURRENCY.md). The binary never resolves "me", so it cannot tell the
    session's own claim from a foreign one; `--force` is the agent's channel for
    every proceed-anyway case the maintainer authorised (their own existing
    claim, or a deliberate take-over). With `--force` the claim is taken
    regardless — `--add-assignee @me` is idempotent, so re-claiming an issue the
    session already holds is a safe no-op.
    """
    holders = be.claim_holder(id)["info"]["holders"]
    if holders and not force:
        since = be.claim_since(id)["info"]["since"]
        return cli.halt("issue is already claimed",
                        details={"id": id, "holders": holders, "since": since},
                        stream=stream)
    be.claim_assign(id)
    return cli.acted({"id": id, "claimed": True, "holders": holders},
                     stream=stream)


def release(be: GithubBackend, id: str,
            stream: TextIO | None = None) -> int:
    """Drop the advisory claim on a clean exit, so the issue stops reading as
    held — covers a claim taken over by reaping as much as one opened with."""
    be.claim_release(id)
    return cli.acted({"id": id, "released": True}, stream=stream)


# --- state-machine transitions ----------------------------------------------

def _set_state(be: GithubBackend, id: str, issue: Mapping[str, Any],
               new_state: str, category: str | None,
               priority: str | None) -> dict[str, Any]:
    """Apply one state transition: strip the maintainer-owned state labels the
    issue carries, add the new one, and reconcile the optional category and
    priority. `in-progress` is pickup's and never touched. Returns the label
    diff so the act can report exactly what changed."""
    labels = set(issue.get("labels") or [])
    add: list[str] = []
    remove: list[str] = []
    for state in STATE_LABELS:
        if state == new_state:
            if state not in labels:
                add.append(state)
        elif state in labels:
            remove.append(state)
    if category:
        for cat in CATEGORY_LABELS:
            if cat == category and cat not in labels:
                add.append(cat)
            elif cat != category and cat in labels:
                remove.append(cat)
    if priority:
        for prio in PRIORITY_LABELS:
            if prio == priority and prio not in labels:
                add.append(prio)
            elif prio != priority and prio in labels:
                remove.append(prio)
    if add or remove:
        be.issue_label(id, add=add or None, remove=remove or None)
    return {"added": add, "removed": remove}


def transition(be: GithubBackend, id: str, state: str,
               category: str | None = None, priority: str | None = None,
               body: str | None = None,
               stream: TextIO | None = None) -> int:
    """Apply a non-terminal state transition the agent decided, plus its body.

    The state must be one of the maintainer-owned states other than `wontfix`
    (rejection closes the issue — that is `reject`). A `ready-for-*` promotion's
    body is the agent brief, a `needs-info` transition's body is the triage
    notes; both ride stdin (out-of-band). The body is posted as a comment after
    the labels land, so a triaged issue carries its brief or notes alongside its
    new state. The brief/notes are the agent's synthesis — this only files them.
    """
    if state not in STATE_LABELS or state == "wontfix":
        return cli.halt(f"not a transition state: {state}",
                        details={"id": id, "state": state}, stream=stream)
    if priority and priority not in PRIORITY_LABELS:
        return cli.halt(f"unknown priority label: {priority}",
                        details={"id": id, "priority": priority}, stream=stream)
    if category and category not in CATEGORY_LABELS:
        return cli.halt(f"unknown category label: {category}",
                        details={"id": id, "category": category}, stream=stream)
    issue = be.issue_view(id)
    diff = _set_state(be, id, issue, state, category, priority)
    commented = False
    if body and body.strip():
        be.issue_comment(id, body)
        commented = True
    return cli.acted({"id": id, "state": state, "category": category,
                      "priority": priority, "commented": commented,
                      "added": diff["added"], "removed": diff["removed"]},
                     stream=stream)


def reject(be: GithubBackend, id: str, category: str | None = None,
           body: str | None = None,
           stream: TextIO | None = None) -> int:
    """Reject an issue: apply `wontfix` and close with the reason.

    The `wontfix` label plus the reason on the closed issue *is* the rejection
    record — a later triage finds it by querying closed `wontfix` issues, so the
    label rides both a bug and an enhancement rejection. The reason rides stdin
    (out-of-band) and becomes the close comment. Closing is a clean exit; the
    caller releases the claim with it.
    """
    if category and category not in CATEGORY_LABELS:
        return cli.halt(f"unknown category label: {category}",
                        details={"id": id, "category": category}, stream=stream)
    issue = be.issue_view(id)
    diff = _set_state(be, id, issue, "wontfix", category, priority=None)
    reason = body if (body and body.strip()) else None
    be.issue_close(id, comment=reason)
    return cli.acted({"id": id, "state": "wontfix", "category": category,
                      "closed": True, "commented": reason is not None,
                      "added": diff["added"], "removed": diff["removed"]},
                     stream=stream)


# --- dispatch ---------------------------------------------------------------

_COMMANDS = ("present", "claim", "release", "transition", "reject")

# Commands whose body (brief / notes / reason) rides stdin (SECURITY.md).
_STDIN_COMMANDS = {"transition", "reject"}


def run(argv: Sequence[str], env: Mapping[str, str] | None = None,
        runner: Any = None, repo: str | None = None,
        stream: TextIO | None = None, stdin_body: str | None = None) -> int:
    """Dispatch a triage command.

    Resolves the backend exactly as capture/reap/land do — `$ISSUE_TRACKER`,
    then the bot identity (halting on the half-configured state) — and routes to
    present (the queue/candidate) or one of the acts (claim/release, the state
    transition, the rejection). `runner` and `repo` are injectable for testing.
    """
    env = env if env is not None else os.environ
    stream = stream or sys.stdout

    tracker_kind = env.get("ISSUE_TRACKER", "github")
    if tracker_kind != "github":
        return cli.halt(f"unsupported tracker backend: {tracker_kind}",
                        details={"backend": tracker_kind}, stream=stream)

    try:
        ident = identity_mod.resolve(env)
    except identity_mod.HalfConfigured as exc:
        return cli.halt(str(exc), stream=stream)

    if argv and argv[0] not in _COMMANDS:
        return cli.halt(f"unknown command: {argv[0]}", stream=stream)

    repo = repo or _resolve_repo(runner)
    be = GithubBackend(identity=ident, repo=repo, runner=runner)

    args = _build_parser().parse_args(argv)

    if args.command == "present":
        return present(be, args.id, stream=stream)
    if args.command == "claim":
        return claim(be, args.id, force=args.force, stream=stream)
    if args.command == "release":
        return release(be, args.id, stream=stream)
    if args.command == "transition":
        return transition(be, args.id, args.state, category=args.category,
                          priority=args.priority, body=stdin_body, stream=stream)
    if args.command == "reject":
        return reject(be, args.id, category=args.category, body=stdin_body,
                      stream=stream)
    return cli.halt(f"unknown command: {args.command}", stream=stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="triage",
        description="Drive issues through the triage state machine "
                    "(present / claim / release / transition / reject).",
    )
    sub = parser.add_subparsers(dest="command")

    p_present = sub.add_parser(
        "present", help="present the queue, or a candidate's context with --id")
    p_present.add_argument("--id", help="surface one candidate's full context")

    p_claim = sub.add_parser("claim", help="take the advisory assignee claim")
    p_claim.add_argument("--id", required=True)
    p_claim.add_argument("--force", action="store_true",
                         help="take the claim even if held (proceed-anyway)")

    p_release = sub.add_parser("release", help="drop the advisory claim")
    p_release.add_argument("--id", required=True)

    p_trans = sub.add_parser(
        "transition", help="apply a state transition with an optional comment")
    p_trans.add_argument("--id", required=True)
    p_trans.add_argument("--state", required=True,
                         choices=("needs-triage", "needs-info",
                                  "ready-for-agent", "ready-for-human"))
    p_trans.add_argument("--category", choices=CATEGORY_LABELS)
    p_trans.add_argument("--priority", choices=PRIORITY_LABELS)

    p_reject = sub.add_parser("reject", help="apply wontfix and close")
    p_reject.add_argument("--id", required=True)
    p_reject.add_argument("--category", choices=CATEGORY_LABELS)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare invocation is the present shape: `triage` == `triage present` (ADR
    # 0008's side-effect-free default, safe to fire blind).
    if not argv:
        argv = ["present"]
    stdin_body = None
    if argv and argv[0] in _STDIN_COMMANDS and not sys.stdin.isatty():
        stdin_body = sys.stdin.read()
    return run(argv, stdin_body=stdin_body)


if __name__ == "__main__":
    sys.exit(main())
