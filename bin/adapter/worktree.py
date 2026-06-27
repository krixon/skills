"""The `worktree` command group — git isolation, per ISOLATION.md.

Pure git, tracker-agnostic. Each command is one of ADR 0008's two shapes:
create and teardown and a clean rebase *act* (one mutation, then report);
sync-main *presents* its outcome (fast-forward only on a clean, behind tree).
rebase is the rework path's single owner — it replays onto main and force-pushes,
but on conflict it aborts cleanly and *halts* with the conflicting paths rather
than attempting a resolution only a model can make.

Command functions take the repo paths explicitly and write their JSON envelope
to a stream, so they stay thin over naming.py and gitcmd.py and test directly.
The argparse dispatcher and the bin/worktree executable wire them to argv.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence, TextIO

from adapter import cli, gitcmd
from adapter.naming import branch_name

WORKTREE_DIR = os.path.join(".claude", "worktrees")
BASE = "main"

# Isolation stances (ADR 0010). strict worktree is the default; branch-in-primary
# trades the read-only-root invariant for warm working-directory state and is
# single-session only.
WORKTREE = "worktree"
BRANCH = "branch"
ISOLATIONS = (WORKTREE, BRANCH)
ISOLATION_ENV = "ISOLATION_MODE"


def _resolve_isolation(isolation: str | None) -> str | None:
    """Resolve the stance: explicit flag, else $ISOLATION_MODE, else worktree.

    Returns None for an unrecognised value so the caller halts rather than
    silently picking a stance.
    """
    mode = isolation or os.environ.get(ISOLATION_ENV) or WORKTREE
    return mode if mode in ISOLATIONS else None


def _worktree_path(repo_root: str, branch: str) -> str:
    """Path for a worktree, keyed off the unique branch so two same-title
    issues never collide on one directory.

    `branch` carries kind and issue (e.g. `feat/87-csv-export`); flattening its
    `/` to `-` yields a directory name as unique as the branch itself. The
    realpath stays under the worktrees root — a defence against a branch slug
    that somehow encodes `..`.
    """
    root = os.path.realpath(os.path.join(repo_root, WORKTREE_DIR))
    path = os.path.realpath(os.path.join(root, branch.replace("/", "-")))
    if os.path.commonpath([root, path]) != root:
        raise ValueError(f"worktree path escapes the worktrees root: {path}")
    return path


def cmd_create(
    repo_root: str,
    kind: str,
    title: str,
    issue: int | str | None = None,
    isolation: str | None = None,
    stream: TextIO | None = None,
) -> int:
    """Place the branch under isolation, per the resolved stance (ADR 0010).

    strict worktree: the branch lives in its own worktree, leaving the primary
    checkout untouched. branch-in-primary: the branch is checked out in the
    primary checkout itself. Either way `path` is where the branch is live —
    the worktree directory, or `repo_root` — so the caller stays stance-blind.
    """
    if issue is not None and not str(issue).isdigit():
        return cli.halt("issue must be digits-only",
                        details={"issue": str(issue)}, stream=stream)

    mode = _resolve_isolation(isolation)
    if mode is None:
        return cli.halt("unknown isolation mode",
                        details={"isolation": isolation or os.environ.get(ISOLATION_ENV)},
                        stream=stream)

    # Derive the branch once; the worktree path keys off it, so the slug has a
    # single source feeding both.
    branch = branch_name(kind, title, issue=issue)
    if mode == BRANCH:
        return _create_in_primary(repo_root, branch, stream)
    return _create_worktree(repo_root, branch, stream)


def _create_worktree(repo_root: str, branch: str,
                     stream: TextIO | None) -> int:
    """strict worktree: `git worktree add <path> -b <branch> main`, or check out
    an existing local/remote branch into its own worktree."""
    path = _worktree_path(repo_root, branch)

    if gitcmd.branch_exists(repo_root, branch):
        gitcmd.run_git(["worktree", "add", "--", path, branch], cwd=repo_root)
        mode = "checkout-local"
    else:
        # Fetch immediately before the remote-existence check, so the tracking
        # ref it reads is fresh; a plain fetch creates no local refs/heads, so
        # only the remote check can newly pass here.
        gitcmd.run_git(["fetch", "origin"], cwd=repo_root)
        if _remote_branch_exists(repo_root, branch):
            gitcmd.run_git(["worktree", "add", "--track", "-b", branch,
                            "--", path, f"origin/{branch}"], cwd=repo_root)
            mode = "checkout-remote"
        else:
            gitcmd.run_git(["worktree", "add", "-b", branch, "--", path, BASE],
                           cwd=repo_root)
            mode = "created"

    return cli.acted({"branch": branch, "path": path, "mode": mode,
                      "isolation": WORKTREE}, stream=stream)


def _create_in_primary(repo_root: str, branch: str,
                       stream: TextIO | None) -> int:
    """branch-in-primary: check the branch out in the primary checkout itself.

    With no separate worktree to make collisions structurally impossible, a
    clean-and-on-BASE precondition stands in for it (ADR 0010): it is the
    compare-and-swap that stops two branch-mode creates sharing the one checkout
    — the second sees the first's branch and halts — and it refuses to switch a
    tree carrying uncommitted work.
    """
    if not gitcmd.is_clean(repo_root):
        return cli.halt(cli.CONFLICT,
                        message="primary checkout is dirty; branch mode needs a clean tree",
                        stream=stream)
    current = gitcmd.current_branch(repo_root)
    if current != BASE:
        return cli.halt(
            cli.CONFLICT,
            message=f"primary checkout is on {current}, not {BASE}; "
                    f"another branch-mode task may hold it",
            info={"branch": current}, stream=stream)

    if gitcmd.branch_exists(repo_root, branch):
        gitcmd.run_git(["checkout", branch], cwd=repo_root)
        mode = "checkout-local"
    else:
        gitcmd.run_git(["fetch", "origin"], cwd=repo_root)
        if _remote_branch_exists(repo_root, branch):
            gitcmd.run_git(["checkout", "--track", "-b", branch,
                            f"origin/{branch}"], cwd=repo_root)
            mode = "checkout-remote"
        else:
            gitcmd.run_git(["checkout", "-b", branch, BASE], cwd=repo_root)
            mode = "created"

    return cli.acted({"branch": branch, "path": repo_root, "mode": mode,
                      "isolation": BRANCH}, stream=stream)


def cmd_rebase(worktree_path: str, stream: TextIO | None = None) -> int:
    """Rebase the worktree's branch onto main without squashing, then force-push.

    On conflict, abort the rebase and halt with the conflicting paths — the
    rework path resolves it, this command does not.
    """
    result = gitcmd.run_git(["rebase", BASE], cwd=worktree_path, check=False)
    if result.returncode != 0:
        paths = _conflicting_paths(worktree_path)
        gitcmd.run_git(["rebase", "--abort"], cwd=worktree_path, check=False)
        return cli.halt("rebase onto main hit a conflict",
                        details={"paths": paths}, stream=stream)

    # Push explicitly to origin/<branch>: a branch created via cmd_create's
    # `-b <branch> main` path has no configured upstream, so a bare push would
    # error with "no upstream" rather than push.
    branch = gitcmd.current_branch(worktree_path)
    gitcmd.run_git(["push", f"--force-with-lease={branch}", "origin", branch],
                   cwd=worktree_path)
    return cli.acted({"status": "rebased", "base": BASE}, stream=stream)


def cmd_teardown(
    repo_root: str,
    path: str,
    branch: str,
    isolation: str | None = None,
    stream: TextIO | None = None,
) -> int:
    """Tear the isolation down for the resolved stance (ADR 0010).

    strict worktree: remove the worktree and delete the branch. branch-in-primary:
    switch the primary checkout off the branch and delete it.
    """
    mode = _resolve_isolation(isolation)
    if mode is None:
        return cli.halt("unknown isolation mode",
                        details={"isolation": isolation or os.environ.get(ISOLATION_ENV)},
                        stream=stream)
    if mode == BRANCH:
        return _teardown_primary(repo_root, branch, stream)

    gitcmd.run_git(["worktree", "remove", "--", path], cwd=repo_root)
    gitcmd.run_git(["branch", "-D", "--", branch], cwd=repo_root)
    return cli.acted({"status": "torn-down", "path": path, "branch": branch,
                      "isolation": WORKTREE}, stream=stream)


def _teardown_primary(repo_root: str, branch: str,
                      stream: TextIO | None) -> int:
    """branch-in-primary teardown: return the primary checkout to BASE, delete
    the branch. A dirty tree halts — switching off the branch would strand the
    uncommitted work the checkout still holds."""
    if not gitcmd.is_clean(repo_root):
        return cli.halt(cli.CONFLICT,
                        message="primary checkout is dirty; commit or discard before teardown",
                        stream=stream)
    gitcmd.run_git(["checkout", BASE], cwd=repo_root)
    gitcmd.run_git(["branch", "-D", "--", branch], cwd=repo_root)
    return cli.acted({"status": "torn-down", "path": repo_root, "branch": branch,
                      "isolation": BRANCH}, stream=stream)


def cmd_sync_main(repo_root: str, stream: TextIO | None = None) -> int:
    """Bring local main current: fast-forward only on a clean, behind tree.

    Fetch, then fast-forward only when the tree is clean and main is an ancestor
    of origin/main. A dirty or diverged tree is skipped with its reason. Never
    forces, never creates a merge commit.
    """
    gitcmd.run_git(["fetch", "origin"], cwd=repo_root)

    if not gitcmd.is_clean(repo_root):
        return cli.present_json({"status": "skipped", "reason": "dirty tree"},
                                stream=stream)

    if not gitcmd.is_ancestor(repo_root, BASE, f"origin/{BASE}"):
        return cli.present_json({"status": "skipped", "reason": "diverged"},
                                stream=stream)

    if gitcmd.is_ancestor(repo_root, f"origin/{BASE}", BASE):
        return cli.present_json({"status": "up-to-date"}, stream=stream)

    try:
        gitcmd.run_git(["merge", "--ff-only", f"origin/{BASE}"], cwd=repo_root)
    except gitcmd.GitError:
        # origin/main can move between the ancestry guard above and this merge
        # (a raced push, a sibling land), so a guard that just passed can still
        # see --ff-only fail. This is a best-effort sync, so degrade to a
        # skip-with-reason like the dirty and diverged cases rather than raising
        # and aborting a caller's tail (land's apply emits its roll-up after).
        return cli.present_json(
            {"status": "skipped", "reason": "could not fast-forward"},
            stream=stream)
    return cli.present_json({"status": "fast-forwarded"}, stream=stream)


def _remote_branch_exists(repo_root: str, branch: str) -> bool:
    result = gitcmd.run_git(
        ["show-ref", "--verify", "--quiet", "--",
         f"refs/remotes/origin/{branch}"],
        cwd=repo_root, check=False,
    )
    return result.returncode == 0


def _conflicting_paths(worktree_path: str) -> list[str]:
    result = gitcmd.run_git(["diff", "--name-only", "--diff-filter=U"],
                            cwd=worktree_path, check=False)
    return [line for line in result.stdout.splitlines() if line]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="worktree",
        description="Git isolation command group (create, rebase, teardown, sync-main).",
    )
    parser.add_argument("--repo-root", default=os.getcwd(),
                        help="repo-root checkout (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="create or check out a worktree branch")
    p_create.add_argument("--kind", required=True)
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--issue", default=None)
    p_create.add_argument("--isolation", choices=ISOLATIONS, default=None,
                          help="isolation stance (default: $ISOLATION_MODE or worktree)")

    p_rebase = sub.add_parser("rebase", help="rebase a worktree branch onto main")
    p_rebase.add_argument("--path", required=True, help="the worktree path")

    p_teardown = sub.add_parser("teardown", help="remove a worktree and its branch")
    p_teardown.add_argument("--path", required=True)
    p_teardown.add_argument("--branch", required=True)
    p_teardown.add_argument("--isolation", choices=ISOLATIONS, default=None,
                            help="isolation stance (default: $ISOLATION_MODE or worktree)")

    sub.add_parser("sync-main", help="fast-forward local main when clean and behind")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "create":
        return cmd_create(args.repo_root, kind=args.kind, title=args.title,
                          issue=args.issue, isolation=args.isolation)
    if args.command == "rebase":
        return cmd_rebase(args.path)
    if args.command == "teardown":
        return cmd_teardown(args.repo_root, path=args.path, branch=args.branch,
                            isolation=args.isolation)
    if args.command == "sync-main":
        return cmd_sync_main(args.repo_root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
