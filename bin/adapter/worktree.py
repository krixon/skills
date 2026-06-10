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

import argparse
import os
import sys

from adapter import cli, gitcmd
from adapter.naming import branch_name, slugify

WORKTREE_DIR = os.path.join(".claude", "worktrees")
BASE = "main"


def _worktree_path(repo_root, slug):
    return os.path.join(repo_root, WORKTREE_DIR, slug)


def cmd_create(repo_root, kind, title, issue=None, stream=None):
    """Create a worktree on its own branch, or check out an existing one.

    New branch: `git worktree add <path> -b <branch> main`. When the branch
    already exists locally or only on the remote, drop `-b` and check it out,
    fetching first so a remote-only ref resolves.
    """
    branch = branch_name(kind, title, issue=issue)
    slug = slugify(title)
    path = _worktree_path(repo_root, slug)

    if gitcmd.branch_exists(repo_root, branch):
        gitcmd.run_git(["worktree", "add", path, branch], cwd=repo_root)
        mode = "checkout-local"
    else:
        gitcmd.run_git(["fetch", "origin"], cwd=repo_root)
        if gitcmd.branch_exists(repo_root, branch) or _remote_branch_exists(repo_root, branch):
            gitcmd.run_git(["worktree", "add", path, "--track", "-b", branch,
                            f"origin/{branch}"], cwd=repo_root)
            mode = "checkout-remote"
        else:
            gitcmd.run_git(["worktree", "add", path, "-b", branch, BASE], cwd=repo_root)
            mode = "created"

    return cli.acted({"branch": branch, "path": path, "mode": mode}, stream=stream)


def cmd_rebase(worktree_path, stream=None):
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


def cmd_teardown(repo_root, path, branch, stream=None):
    """Remove the worktree and delete its branch."""
    gitcmd.run_git(["worktree", "remove", path], cwd=repo_root)
    gitcmd.run_git(["branch", "-D", branch], cwd=repo_root)
    return cli.acted({"status": "torn-down", "path": path, "branch": branch},
                     stream=stream)


def cmd_sync_main(repo_root, stream=None):
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

    gitcmd.run_git(["merge", "--ff-only", f"origin/{BASE}"], cwd=repo_root)
    return cli.present_json({"status": "fast-forwarded"}, stream=stream)


def _remote_branch_exists(repo_root, branch):
    result = gitcmd.run_git(
        ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        cwd=repo_root, check=False,
    )
    return result.returncode == 0


def _conflicting_paths(worktree_path):
    result = gitcmd.run_git(["diff", "--name-only", "--diff-filter=U"],
                            cwd=worktree_path, check=False)
    return [line for line in result.stdout.splitlines() if line]


def _build_parser():
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

    p_rebase = sub.add_parser("rebase", help="rebase a worktree branch onto main")
    p_rebase.add_argument("--path", required=True, help="the worktree path")

    p_teardown = sub.add_parser("teardown", help="remove a worktree and its branch")
    p_teardown.add_argument("--path", required=True)
    p_teardown.add_argument("--branch", required=True)

    sub.add_parser("sync-main", help="fast-forward local main when clean and behind")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.command == "create":
        return cmd_create(args.repo_root, kind=args.kind, title=args.title,
                          issue=args.issue)
    if args.command == "rebase":
        return cmd_rebase(args.path)
    if args.command == "teardown":
        return cmd_teardown(args.repo_root, path=args.path, branch=args.branch)
    if args.command == "sync-main":
        return cmd_sync_main(args.repo_root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
