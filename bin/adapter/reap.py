"""The `reap` command group — sweep stale workflow state and clean it up.

reap is a pure command (ADR 0008 buckets 1/2): it detects staleness by
thresholds and state changes, and it never makes a model's judgment. The lone
human decision — "reap this item" — rides the present/act split: `plan` presents
every stale candidate across the four classes read-only; the per-class act
commands each perform one mutation a human authorised. Nothing mutates without a
per-item confirmation, and every act re-reads the deciding signal immediately
before mutating, so the sweep going stale while the human decided cannot reap a
claim taken since or a PR reopened since (the trade in CONCURRENCY.md — never
yank work from under a live session).

The orchestration composes the existing seams in-process, exactly as land does:
the `tracker` GithubBackend's `gh` runner seam for the issue and PR reads and the
claim/label/close/comment writes, and the `worktree` command functions over the
git seam for orphaned-worktree discovery and teardown. Every operation takes
those seams as parameters, so the sweep and each act are unit-tested against a
canned `gh` runner and fake git/worktree functions without the network or a real
checkout.

The four staleness classes:

  - **abandoned claim** — `in-progress`, no open PR, claim older than the `claim`
    threshold → release the claim and strip `in-progress`;
  - **quiet needs-info** — open `needs-info`, last activity past the `needs-info`
    threshold → re-ping with a comment, or close;
  - **orphaned worktree/branch** — a local worktree whose PR merged or closed, or
    whose branch has no PR and no longer exists on the remote → tear it down;
  - **stale epic** — an open epic every sub-issue of which is now closed → close
    the epic.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence, TextIO

from adapter import cli, gitcmd, identity as identity_mod, worktree
from adapter.tracker import GithubBackend, _resolve_repo

# Defaults age a claim and a quiet needs-info out on a clock (CONCURRENCY.md
# records that nothing reaps them automatically — reap is the human's hand). The
# worktree and epic classes carry no clock: they age on a state change.
_DEFAULT_CLAIM_HOURS = 24
_DEFAULT_NEEDS_INFO_DAYS = 14

_DURATION_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[hdw])$")
_UNIT_HOURS = {"h": 1, "d": 24, "w": 24 * 7}


def parse_duration(text: str) -> timedelta | None:
    """Parse a `<n><unit>` threshold (`48h`, `7d`, `2w`) into a timedelta.

    Pure: an unrecognised form returns None so the caller keeps the default
    rather than erroring on a typo, matching the skill's "an unrecognised key
    leaves the default" rule.
    """
    match = _DURATION_RE.match(text.strip())
    if not match:
        return None
    return timedelta(hours=int(match.group("value")) * _UNIT_HOURS[match.group("unit")])


def cutoff(now: datetime, age: timedelta) -> str:
    """The ISO 8601 instant `age` before `now`, the selection queries compare
    against (a claim/activity timestamp older than this is past the threshold)."""
    return (now - age).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- the sweep (plan) -------------------------------------------------------

def sweep(be: GithubBackend, repo_root: str,
          claim_age: timedelta, needs_info_age: timedelta,
          now: datetime | None = None,
          worktree_runner: gitcmd.Runner | None = None) -> dict[str, Any]:
    """Gather every stale candidate across the four classes — read-only.

    Returns one bucket per class, each entry naming the proposed action's inputs
    so the wrapper can present it and the matching act command receive them. The
    whole picture is gathered in one pass so the human sees it together.
    """
    now = now or datetime.now(timezone.utc)
    return {
        "abandoned_claims": be.find_stale_claims(cutoff(now, claim_age)),
        "quiet_needs_info": be.find_quiet_needs_info(cutoff(now, needs_info_age)),
        "orphaned_worktrees": find_orphaned_worktrees(
            be, repo_root, runner=worktree_runner),
        "stale_epics": be.find_stale_epics(),
    }


def list_worktrees(repo_root: str,
                   runner: gitcmd.Runner | None = None) -> list[dict[str, str]]:
    """Every local worktree and its branch, parsed from the porcelain listing.

    Each worktree is a `worktree <path>` line optionally followed by a
    `branch refs/heads/<name>` line (absent for a detached HEAD, which carries no
    branch to match a PR on). The repo-root worktree itself is dropped — reap
    never tears down the live checkout.
    """
    run = runner or gitcmd.run_git
    result = run(["worktree", "list", "--porcelain"], cwd=repo_root, check=False)
    if result.returncode != 0:
        return []
    out: list[dict[str, str]] = []
    path: str | None = None
    branch: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
            branch = None
        elif line.startswith("branch "):
            branch = line[len("branch "):]
        elif line == "":
            _maybe_add(out, repo_root, path, branch)
            path, branch = None, None
    _maybe_add(out, repo_root, path, branch)
    return out


def _maybe_add(out: list[dict[str, str]], repo_root: str,
               path: str | None, branch: str | None) -> None:
    if path is None or branch is None:
        return
    if os.path.realpath(path) == os.path.realpath(repo_root):
        return  # never the live repo-root checkout
    name = branch[len("refs/heads/"):] if branch.startswith("refs/heads/") else branch
    out.append({"path": path, "branch": name})


def _remote_branch_exists(repo_root: str, branch: str,
                          runner: gitcmd.Runner | None = None) -> bool:
    run = runner or gitcmd.run_git
    result = run(["ls-remote", "--exit-code", "--heads", "origin", branch],
                 cwd=repo_root, check=False)
    return result.returncode == 0


def find_orphaned_worktrees(be: GithubBackend, repo_root: str,
                            runner: gitcmd.Runner | None = None,
                            ) -> list[dict[str, Any]]:
    """Local worktrees safe to tear down: the PR merged/closed, or no PR and the
    branch is gone from the remote.

    A worktree whose PR is still open is live work — never a candidate. A branch
    with a PR is decided by the PR's state; a branch with no PR falls back to the
    remote-existence signal (gone remotely → orphaned by a failed run).
    """
    out: list[dict[str, Any]] = []
    for wt in list_worktrees(repo_root, runner=runner):
        branch = wt["branch"]
        pr = be.pr_for_branch(branch)
        if pr is not None:
            if pr["state"] == "open":
                continue  # live work
            out.append({"path": wt["path"], "branch": branch,
                        "reason": f"pr-{pr['state']}", "pr": pr["number"]})
        elif not _remote_branch_exists(repo_root, branch, runner=runner):
            out.append({"path": wt["path"], "branch": branch,
                        "reason": "no-pr-no-remote", "pr": None})
    return out


def plan(be: GithubBackend, repo_root: str,
         claim_age: timedelta, needs_info_age: timedelta,
         now: datetime | None = None,
         worktree_runner: gitcmd.Runner | None = None,
         stream: TextIO | None = None) -> int:
    """Present every stale candidate across the four classes. Read-only."""
    return cli.present_json(
        sweep(be, repo_root, claim_age, needs_info_age, now=now,
              worktree_runner=worktree_runner),
        stream=stream)


# --- per-item acts (each human-confirmed, re-reading its deciding signal) ----

def reap_claim(be: GithubBackend, number: int, before: str,
               stream: TextIO | None = None) -> int:
    """Release an abandoned claim and strip `in-progress`, re-checking first.

    Re-reads the claim timestamp and the open-PR signal immediately before
    mutating: a claim re-taken, refreshed, or a PR opened since the sweep must
    not be reaped. Halts with the reason rather than yanking live work.
    """
    since = be.claim_since(str(number))["info"]["since"]
    if since is None or since >= before:
        return cli.halt("claim is no longer past the threshold",
                        details={"number": number, "since": since},
                        stream=stream)
    if be.open_pr_for_issue(number):
        return cli.halt("issue now has an open PR — in review, not abandoned",
                        details={"number": number}, stream=stream)
    be.claim_release(str(number))
    be.issue_label(number, remove=["in-progress"])
    return cli.acted({"number": number, "reaped": "claim",
                      "released": True, "labelStripped": "in-progress"},
                     stream=stream)


def reap_needs_info(be: GithubBackend, number: int, action: str,
                    body: str | None = None,
                    stream: TextIO | None = None) -> int:
    """Re-ping a quiet needs-info issue (a comment) or close it.

    `action` is `re-ping` (the default the wrapper offers) or `close`. The
    re-ping body rides stdin (the out-of-band channel). reap does not re-check
    the quiet window here: a comment or close is reversible and the human chose
    it per item.
    """
    if action == "re-ping":
        result = be.issue_comment(number, body or "")
        return cli.acted({"number": number, "reaped": "needs-info",
                          "action": "re-ping", "url": result.get("url")},
                         stream=stream)
    if action == "close":
        be.issue_close(number)
        return cli.acted({"number": number, "reaped": "needs-info",
                          "action": "close"}, stream=stream)
    return cli.halt(f"unknown needs-info action: {action}",
                    details={"number": number}, stream=stream)


def reap_worktree(repo_root: str, path: str, branch: str,
                  teardown: Callable[..., int] | None = None,
                  stream: TextIO | None = None) -> int:
    """Tear down an orphaned worktree and its branch, per ISOLATION.md."""
    teardown = teardown or worktree.cmd_teardown
    sink: TextIO = io.StringIO()
    teardown(repo_root, path=path, branch=branch, stream=sink)
    return cli.acted({"reaped": "worktree", "path": path, "branch": branch,
                      "tornDown": True}, stream=stream)


def reap_epic(be: GithubBackend, number: int,
              stream: TextIO | None = None) -> int:
    """Close a stale epic, re-verifying every child is still closed first.

    Guards the race land's close-epic guards: a child reopened between the sweep
    and the confirmation halts the close rather than closing an epic with live
    children.
    """
    subs = be.list_sub_issues(str(number))
    open_children = [s["id"] for s in subs if s.get("state") != "closed"]
    if not subs:
        return cli.halt("epic has no sub-issues to evidence closure",
                        details={"number": number}, stream=stream)
    if open_children:
        return cli.halt("epic has children that are no longer closed",
                        details={"number": number, "openChildren": open_children},
                        stream=stream)
    be.issue_close(number)
    return cli.acted({"number": number, "reaped": "epic", "closed": True},
                     stream=stream)


# --- dispatch ---------------------------------------------------------------

_COMMANDS = ("plan", "reap-claim", "reap-needs-info", "reap-worktree", "reap-epic")

# Commands whose body rides stdin (the out-of-band channel, SECURITY.md).
_STDIN_COMMANDS = {"reap-needs-info"}


def _resolve_thresholds(args: argparse.Namespace) -> tuple[timedelta, timedelta]:
    """The claim and needs-info ages from the args, each falling back to its
    default when absent or unparseable (the skill's threshold-override rule)."""
    claim_age = timedelta(hours=_DEFAULT_CLAIM_HOURS)
    needs_info_age = timedelta(days=_DEFAULT_NEEDS_INFO_DAYS)
    if getattr(args, "claim", None):
        claim_age = parse_duration(args.claim) or claim_age
    if getattr(args, "needs_info", None):
        needs_info_age = parse_duration(args.needs_info) or needs_info_age
    return claim_age, needs_info_age


def run(argv: Sequence[str], env: Mapping[str, str] | None = None,
        runner: Any = None, repo: str | None = None,
        repo_root: str | None = None, stream: TextIO | None = None,
        stdin_body: str | None = None) -> int:
    """Dispatch a reap command.

    Resolves the backend exactly as land.run does — `$ISSUE_TRACKER`, then the
    bot identity (halting on the half-configured state) — and routes to a present
    (`plan`) or act (the per-class `reap-*`) operation. `runner`, `repo`, and
    `repo_root` are injectable for testing.
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
    repo_root = repo_root or os.getcwd()
    be = GithubBackend(identity=ident, repo=repo, runner=runner)

    args = _build_parser().parse_args(argv)

    if args.command == "plan":
        claim_age, needs_info_age = _resolve_thresholds(args)
        return plan(be, repo_root, claim_age, needs_info_age, stream=stream)
    if args.command == "reap-claim":
        claim_age, _ = _resolve_thresholds(args)
        before = cutoff(datetime.now(timezone.utc), claim_age)
        return reap_claim(be, args.number, before, stream=stream)
    if args.command == "reap-needs-info":
        return reap_needs_info(be, args.number, args.action,
                               body=stdin_body, stream=stream)
    if args.command == "reap-worktree":
        return reap_worktree(repo_root, args.path, args.branch, stream=stream)
    if args.command == "reap-epic":
        return reap_epic(be, args.number, stream=stream)
    return cli.halt(f"unknown command: {args.command}", stream=stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reap",
        description="Sweep stale workflow state and clean it up (plan / reap-*).",
    )
    sub = parser.add_subparsers(dest="command")

    p_plan = sub.add_parser("plan", help="present every stale candidate")
    p_plan.add_argument("--claim", help="abandoned-claim threshold, e.g. 48h")
    p_plan.add_argument("--needs-info", dest="needs_info",
                        help="quiet needs-info threshold, e.g. 7d")

    p_claim = sub.add_parser("reap-claim", help="release an abandoned claim")
    p_claim.add_argument("--number", type=int, required=True)
    p_claim.add_argument("--claim", help="threshold the re-check applies, e.g. 48h")

    p_ni = sub.add_parser("reap-needs-info", help="re-ping or close a quiet issue")
    p_ni.add_argument("--number", type=int, required=True)
    p_ni.add_argument("--action", choices=("re-ping", "close"), default="re-ping")

    p_wt = sub.add_parser("reap-worktree", help="tear down an orphaned worktree")
    p_wt.add_argument("--path", required=True)
    p_wt.add_argument("--branch", required=True)

    p_epic = sub.add_parser("reap-epic", help="close a stale epic")
    p_epic.add_argument("--number", type=int, required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare invocation is the present shape: `reap` == `reap plan` (ADR 0008's
    # side-effect-free default, safe to fire blind).
    if not argv:
        argv = ["plan"]
    stdin_body = None
    if argv and argv[0] in _STDIN_COMMANDS:
        stdin_body = sys.stdin.read()
    return run(argv, stdin_body=stdin_body)


if __name__ == "__main__":
    sys.exit(main())
