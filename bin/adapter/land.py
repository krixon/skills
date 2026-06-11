"""The `land` command group — merge approved PRs and clean up, per ADR 0008.

land is a pure command (ADR 0008 buckets 1/2): it merges what GitHub will merge
and clears the trail behind it, and it never makes a model's judgment. The lone
human decision — "land these now" — rides the present/act split: `plan` presents
the classified PRs read-only, `apply` performs the merges, `close-epic` closes a
parent epic a human chose to close. A blocker only a model could resolve halts
(`cli.halt`); land never spawns and never rebases — a conflicting or behind PR is
rework, owned by `pickup`, so land routes it there rather than touching it.

The orchestration composes the existing seams in-process: the `tracker`
GithubBackend's `gh` runner seam for PR/issue mechanics, and the `worktree`
command functions over the git seam for teardown and sync-main. Every operation
takes those seams as parameters, so classification and the apply sequence are
unit-tested against a canned `gh` runner and fake worktree functions without the
network or a real checkout.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from typing import Any, Callable, Mapping, Sequence, TextIO

from adapter import cli, ghcmd, gitcmd, identity as identity_mod, worktree
from adapter.tracker import GithubBackend, _resolve_repo

# The teardown seam: a worktree teardown function with cmd_teardown's signature.
# land discovers the worktree for a merged PR's branch, then drives this to
# remove it; injected so apply is tested without a real git checkout.
TeardownFn = Callable[..., int]
# The sync-main seam: cmd_sync_main's signature. land runs it once after the
# sweep so the next pickup branches from a fresh base.
SyncMainFn = Callable[..., int]


# --- worktree discovery -----------------------------------------------------

def find_worktree(repo_root: str, branch: str,
                  runner: gitcmd.Runner | None = None) -> str | None:
    """The local worktree path checked out on `branch`, or None when there is
    none.

    Parses `git worktree list --porcelain` through the git seam: each worktree
    is a `worktree <path>` line followed by a `branch refs/heads/<name>` line
    (absent for a detached HEAD). land tears a worktree down only when one
    exists for the merged PR's head branch — a PR merged from a clone with no
    local worktree leaves nothing to remove.
    """
    run = runner or gitcmd.run_git
    result = run(["worktree", "list", "--porcelain"], cwd=repo_root, check=False)
    if result.returncode != 0:
        return None
    current_path: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            if ref == f"refs/heads/{branch}" and current_path is not None:
                return current_path
    return None


# --- classification (plan) --------------------------------------------------

def _closing_numbers(refs: dict[str, Any]) -> list[int]:
    """The issue numbers a PR's body closes on merge, from closingIssuesReferences."""
    nodes = refs.get("closingIssuesReferences") or []
    return [n["number"] for n in nodes if "number" in n]


def _no_issue_declared(body: str | None) -> bool:
    """True when the PR body leads with a `No-issue:` marker — an issue-less
    patch by design, not an anomaly."""
    if not body:
        return False
    return body.lstrip().lower().startswith("no-issue:")


def classify(be: GithubBackend, prs: Sequence[dict[str, Any]],
             sleep: Callable[[float], None] | None = None) -> dict[str, Any]:
    """Bucket each approved PR into landable / rework / skip / merged.

    `prs` is the approved first cut (from `find_approved`, already bot-scoped).
    For each, the readiness re-query (merge_state, past UNKNOWN) and the
    approval-covers-HEAD check decide the bucket:

      - already merged                       → merged
      - approval no longer covers HEAD       → skip (stale-approval)
      - CLEAN and covered, a linear method   → landable (carries method, closes)
      - CLEAN and covered, no linear method  → skip (no-allowed-merge-method)
      - CONFLICTING or DIRTY                 → rework (conflicting)
      - BEHIND                               → rework (behind)
      - anything else (BLOCKED, DRAFT, …)    → skip (not-ready: <status>)

    rework routes to pickup; land never rebases (ADR 0008). The `unusual` flags
    surface the conditions land's wrapper confirms in chat before applying.
    """
    landable: list[dict[str, Any]] = []
    rework: list[dict[str, Any]] = []
    skip: list[dict[str, Any]] = []
    merged: list[dict[str, Any]] = []

    for pr in prs:
        number = pr["number"]
        if be.is_merged(number)["merged"]:
            merged.append({"number": number})
            continue

        if not be.approval_covers_head(number):
            skip.append({"number": number, "reason": "stale-approval"})
            continue

        state = be.merge_state(number, sleep=sleep)
        mergeable = state.get("mergeable")
        status = state.get("mergeStateStatus")

        if status == "CLEAN":
            base = pr.get("baseRefName", worktree.BASE)
            method = be.merge_method(base)
            if method is None:
                skip.append({"number": number,
                             "reason": "no-allowed-merge-method"})
                continue
            refs = be.closing_refs(number)
            closes = _closing_numbers(refs)
            flags: list[str] = []
            body = pr.get("body")
            if not closes and not _no_issue_declared(body):
                flags.append("no-issue")
            landable.append({
                "number": number, "title": pr.get("title"),
                "method": method, "closes": closes, "flags": flags,
            })
            continue

        if mergeable == "CONFLICTING" or status == "DIRTY":
            rework.append({"number": number, "reason": "conflicting"})
            continue
        if status == "BEHIND":
            rework.append({"number": number, "reason": "behind"})
            continue

        skip.append({"number": number, "reason": f"not-ready: {status}"})

    unusual: list[str] = []
    if len(landable) > 1:
        unusual.append("multi-pr")
    if any("no-issue" in lp["flags"] for lp in landable):
        unusual.append("no-issue")
    # `stale-against-moved-main` is omitted: the merge_state re-query settles a
    # PR's readiness but does not cheaply report that the *base* moved between
    # the sweep and now (it carries no before/after base oid), and apply's
    # per-PR re-check catches a PR that went un-ready against a moved main. Per
    # the spec, the flag is omitted rather than guessed.

    return {"landable": landable, "rework": rework, "skip": skip,
            "merged": merged, "unusual": unusual}


def plan(be: GithubBackend, pr_number: int | None = None,
         sleep: Callable[[float], None] | None = None,
         stream: TextIO | None = None) -> int:
    """Present the classified landable / rework / skip / merged buckets.

    With `pr_number`, classify that one PR (still subject to the approved +
    bot-owned gate `find_approved` applies); otherwise sweep every approved PR.
    Read-only — the *present* shape.
    """
    approved = be.find_approved()
    if pr_number is not None:
        approved = [p for p in approved if p["number"] == pr_number]
    return cli.present_json(classify(be, approved, sleep=sleep), stream=stream)


# --- orchestration (apply) --------------------------------------------------

def _strip_in_progress(be: GithubBackend, issues: Sequence[int]) -> None:
    for issue in issues:
        be.issue_label(issue, remove=["in-progress"])


def _epic_close_candidate(be: GithubBackend,
                          closed_issue: int) -> dict[str, Any] | None:
    """The parent epic to offer for closing, when this child was its last open
    one — else None.

    After a child closes, read its parent; offer the epic only when it exists,
    is still open, and every sub-issue now reads closed. land never closes the
    epic here — the offer faces a human in the wrapper.
    """
    parent = be.parent_of(closed_issue)
    if parent is None:
        return None
    epic = be.issue_view(parent)
    if epic.get("state") != "OPEN":
        return None
    subs = be.list_sub_issues(parent)
    if subs and all(s.get("state") == "closed" for s in subs):
        return {"number": parent, "title": epic.get("title"),
                "subIssues": subs}
    return None


def apply(be: GithubBackend, repo_root: str,
          pr_number: int | None = None,
          teardown: TeardownFn | None = None,
          sync_main: SyncMainFn | None = None,
          worktree_runner: gitcmd.Runner | None = None,
          sleep: Callable[[float], None] | None = None,
          stream: TextIO | None = None) -> int:
    """Merge each landable PR in turn, then clean up after the sweep.

    Per PR: re-check merged-in-UI, then re-check readiness (CLEAN + covers HEAD)
    — the swept list goes stale when main moves — merge with the discovered
    linear method, confirm the closing refs, strip `in-progress` on each closed
    issue, tear down the local worktree when one exists, and collect a parent
    epic to offer for closing when this child was its last. After all PRs, run
    sync-main once. A PR with no closing ref and no `No-issue:` marker has its
    issue left untouched and is reported.

    teardown / sync_main default to the real worktree command functions; they
    are injected as seams for testing. Their JSON envelopes are swallowed (land
    emits its own roll-up), but their exit codes are not consulted — a teardown
    that fails surfaces by raising from the git seam, the same as any mutation.
    """
    teardown = teardown or worktree.cmd_teardown
    sync_main = sync_main or worktree.cmd_sync_main
    sink: TextIO = io.StringIO()

    plan_payload = plan_buckets(be, pr_number=pr_number, sleep=sleep)
    landable = plan_payload["landable"]

    results: list[dict[str, Any]] = []
    epic_candidates: list[dict[str, Any]] = []
    seen_epics: set[int] = set()

    for lp in landable:
        number = lp["number"]
        head = lp.get("headRefName")
        result: dict[str, Any] = {"number": number}

        already = be.is_merged(number)["merged"]
        if not already:
            # Re-check readiness at merge time: the swept list goes stale the
            # moment main moves, so a CLEAN+covered PR at plan time may no
            # longer be either. Skip with the reason rather than force-merge.
            if not be.approval_covers_head(number):
                result.update(merged=False, skipped=True, reason="stale-approval")
                results.append(result)
                continue
            state = be.merge_state(number, sleep=sleep)
            if state.get("mergeStateStatus") != "CLEAN":
                result.update(merged=False, skipped=True,
                              reason=f"not-ready: {state.get('mergeStateStatus')}")
                results.append(result)
                continue
            method = lp.get("method")
            if method is None:
                result.update(merged=False, skipped=True,
                              reason="no-allowed-merge-method")
                results.append(result)
                continue
            be.merge(number, method)
            result.update(merged=True, method=method)
        else:
            result.update(merged=False, alreadyMerged=True)

        # Confirm the closing refs resolved, then act on the closed issues.
        closes = _closing_numbers(be.closing_refs(number))
        body = lp.get("body")
        if not closes and not _no_issue_declared(body):
            result.update(closedIssues=[], noLinkedIssue=True)
        else:
            _strip_in_progress(be, closes)
            result.update(closedIssues=closes)
            for issue in closes:
                candidate = _epic_close_candidate(be, issue)
                if candidate and candidate["number"] not in seen_epics:
                    seen_epics.add(candidate["number"])
                    epic_candidates.append(candidate)

        # Tear down the local worktree only when one exists for the head branch.
        if head:
            path = find_worktree(repo_root, head, runner=worktree_runner)
            if path is not None:
                teardown(repo_root, path=path, branch=head, stream=sink)
                result.update(tornDown=True, worktreePath=path)
            else:
                result.update(tornDown=False)

        results.append(result)

    sync_main(repo_root, stream=sink)

    return cli.acted({"results": results,
                      "epic_close_candidates": epic_candidates}, stream=stream)


def plan_buckets(be: GithubBackend, pr_number: int | None = None,
                 sleep: Callable[[float], None] | None = None) -> dict[str, Any]:
    """The classification apply consumes — the landable bucket, each entry
    carrying the head branch and body apply needs for teardown and the
    no-issue check (which `plan`'s present payload omits).

    `find_approved`'s rows carry `headRefName`; classify drops it from the
    present shape, so apply re-derives the bucket here over the same rows and
    re-attaches head/body per landable PR.
    """
    approved = be.find_approved()
    if pr_number is not None:
        approved = [p for p in approved if p["number"] == pr_number]
    by_number = {p["number"]: p for p in approved}
    buckets = classify(be, approved, sleep=sleep)
    for lp in buckets["landable"]:
        src = by_number.get(lp["number"], {})
        lp["headRefName"] = src.get("headRefName")
        lp["body"] = src.get("body")
    return buckets


# --- close-epic (human-gated act) -------------------------------------------

def close_epic(be: GithubBackend, number: int,
               stream: TextIO | None = None) -> int:
    """Close a parent epic a human chose to close, re-verifying every child is
    closed first.

    Guards against a race: a child may have reopened between the offer and the
    confirmation. When one is still open, halt with that reason rather than
    closing an epic with live children.
    """
    subs = be.list_sub_issues(number)
    open_children = [s["number"] for s in subs if s.get("state") != "closed"]
    if open_children:
        return cli.halt(
            "epic has children that are no longer closed",
            details={"number": number, "openChildren": open_children},
            stream=stream)
    return cli.acted(be.issue_close(number), stream=stream)


# --- dispatch ---------------------------------------------------------------

_COMMANDS = ("plan", "apply", "close-epic")


def run(argv: Sequence[str], env: Mapping[str, str] | None = None,
        runner: ghcmd.Runner | None = None, repo: str | None = None,
        repo_root: str | None = None, stream: TextIO | None = None) -> int:
    """Dispatch a land command.

    Resolves the backend exactly as tracker.run does — `$ISSUE_TRACKER`, then
    the bot identity (halting on the half-configured state) — and routes to a
    present (`plan`) or act (`apply`, `close-epic`) operation. `runner`,
    `repo`, and `repo_root` are injectable for testing.
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

    # Reject an unknown subcommand through the halt envelope rather than
    # argparse's bare SystemExit, so a misfire reads like every other blocker.
    if argv and argv[0] not in _COMMANDS:
        return cli.halt(f"unknown command: {argv[0]}", stream=stream)

    repo = repo or _resolve_repo(runner)
    repo_root = repo_root or os.getcwd()
    be = GithubBackend(identity=ident, repo=repo, runner=runner)

    args = _build_parser().parse_args(argv)
    if args.command == "plan":
        return plan(be, pr_number=args.pr, stream=stream)
    if args.command == "apply":
        return apply(be, repo_root, pr_number=args.pr, stream=stream)
    if args.command == "close-epic":
        return close_epic(be, args.number, stream=stream)
    return cli.halt(f"unknown command: {args.command}", stream=stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="land",
        description="Merge approved PRs and clean up (plan / apply / close-epic).",
    )
    sub = parser.add_subparsers(dest="command")

    p_plan = sub.add_parser("plan", help="present the classified approved PRs")
    p_plan.add_argument("--pr", type=int, default=None)

    p_apply = sub.add_parser("apply", help="merge the landable PRs and clean up")
    p_apply.add_argument("--pr", type=int, default=None)

    p_close = sub.add_parser("close-epic", help="close a parent epic (human-gated)")
    p_close.add_argument("--number", type=int, required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare invocation is the present shape: `land` == `land plan` (ADR 0008's
    # side-effect-free default, safe to fire blind).
    if not argv:
        argv = ["plan"]
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
