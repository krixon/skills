"""Thin git subprocess substrate shared by the adapter command groups.

ADR 0008 makes the adapter a Python (stdlib-only) entry point that orchestrates
`git` (and, in later slices, `gh`) as subprocesses. This module is the git half:
`run_git` is the single shell-out point, and the query helpers compose it into
the predicates the commands branch on. Keeping git access here lets the command
modules stay thin over the pure logic in `naming.py`.
"""

from __future__ import annotations

import subprocess
from typing import Callable, Sequence

# The git subprocess seam: run_git's call signature, injected for testing. The
# result is a subprocess.CompletedProcess of captured text; kept a forward-ref
# string so the 3.8 floor never evaluates the generic subscript at import. The
# tracker half (ghcmd) defines the matching Runner over its own result type.
Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class GitError(RuntimeError):
    """A git subprocess exited non-zero on a checked call.

    Carries the argv, exit code, and captured stderr so a command can present a
    blocker rather than swallow the failure.
    """

    def __init__(self, args: Sequence[str], returncode: int, stderr: str) -> None:
        self.args = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"git {' '.join(args)} exited {returncode}: {stderr.strip()}")


def run_git(
    args: Sequence[str],
    cwd: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
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


def is_clean(cwd: str) -> bool:
    """True when the working tree has no staged, unstaged, or untracked changes."""
    result = run_git(["status", "--porcelain"], cwd=cwd)
    return result.stdout.strip() == ""


def branch_exists(cwd: str, branch: str) -> bool:
    """True when a local branch ref of this name exists."""
    result = run_git(
        ["show-ref", "--verify", "--quiet", "--", f"refs/heads/{branch}"],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0


def current_branch(cwd: str) -> str:
    """The name of the currently checked-out branch."""
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip()


def is_ancestor(cwd: str, maybe_ancestor: str, descendant: str) -> bool:
    """True when maybe_ancestor is an ancestor of descendant."""
    result = run_git(
        ["merge-base", "--is-ancestor", "--", maybe_ancestor, descendant],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0
