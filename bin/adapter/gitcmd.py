"""Thin git subprocess substrate shared by the adapter command groups.

ADR 0008 makes the adapter a Python (stdlib-only) entry point that orchestrates
`git` (and, in later slices, `gh`) as subprocesses. This module is the git half:
`run_git` is the single shell-out point, and the query helpers compose it into
the predicates the commands branch on. Keeping git access here lets the command
modules stay thin over the pure logic in `naming.py`.
"""

import subprocess


class GitError(RuntimeError):
    """A git subprocess exited non-zero on a checked call.

    Carries the argv, exit code, and captured stderr so a command can present a
    blocker rather than swallow the failure.
    """

    def __init__(self, args, returncode, stderr):
        self.args = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"git {' '.join(args)} exited {returncode}: {stderr.strip()}")


def run_git(args, cwd=None, check=True):
    """Run `git <args>`, capturing stdout/stderr as text.

    Raises GitError on non-zero exit when check is True; otherwise returns the
    CompletedProcess for the caller to inspect.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise GitError(args, result.returncode, result.stderr)
    return result


def is_clean(cwd):
    """True when the working tree has no staged, unstaged, or untracked changes."""
    result = run_git(["status", "--porcelain"], cwd=cwd)
    return result.stdout.strip() == ""


def branch_exists(cwd, branch):
    """True when a local branch ref of this name exists."""
    result = run_git(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0


def is_ancestor(cwd, maybe_ancestor, descendant):
    """True when maybe_ancestor is an ancestor of descendant."""
    result = run_git(
        ["merge-base", "--is-ancestor", maybe_ancestor, descendant],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0
