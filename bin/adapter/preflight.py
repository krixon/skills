"""Startup substrate check for the adapter entry points.

ADR 0008 makes the adapter a Python (stdlib-only) entry point orchestrating
`git` and `gh` as subprocesses, distributed with no install hook to verify the
substrate is present. This check runs first in every entry point so a missing
prerequisite surfaces as one clear, named blocker — naming the tool or version
floor and that it is required — rather than a cryptic exec failure deep in a
subprocess call.

Each entry point declares the tools it actually shells out to (ADR 0008 wires
the preflight into each one): `worktree` is pure git and passes `("git",)`; a
tracker group that drives `gh` passes `("git", "gh")`. So the check never
rejects an environment over a tool the invoked command never uses.

`check_substrate` is pure (it reports what is missing); `preflight` wires that
report to the `cli.halt` envelope — the same shape every other adapter blocker
emits — so a missing substrate reads identically to any other halt.
"""

import shutil
import sys

from adapter import cli

# The full adapter substrate. Entry points pass the subset they use; this is
# the default for a caller that wants the whole set. Python is checked
# separately, by version.
REQUIRED_TOOLS = ("git", "gh")

# Minimum Python the adapter is written against. 3.8 is the floor: it is the
# oldest interpreter still shipped on the supported macOS/Linux targets, and
# nothing here reaches past its stdlib.
PYTHON_FLOOR = (3, 8)
PYTHON_FLOOR_STR = ".".join(str(n) for n in PYTHON_FLOOR)


def check_substrate(required=REQUIRED_TOOLS, python_version=None):
    """Report the missing runtime prerequisites, in declaration order.

    `required` is the set of tools the calling entry point shells out to.
    Returns a list of human-readable lines, one per missing requirement; an
    empty list means the substrate is fully present. `python_version` defaults
    to the running interpreter and is injectable for testing.
    """
    version = python_version or sys.version_info
    missing = []
    for tool in required:
        if shutil.which(tool) is None:
            missing.append(
                f"{tool} is a required prerequisite and was not found on PATH")
    if tuple(version[:2]) < PYTHON_FLOOR:
        running = ".".join(str(n) for n in version[:2])
        missing.append(
            f"Python {PYTHON_FLOOR_STR} is a required prerequisite; "
            f"found {running}")
    return missing


def preflight(required=REQUIRED_TOOLS, python_version=None, stream=None):
    """Run the substrate check; on a miss, halt with a named blocker.

    Returns 0 when the substrate is present and silent. On a miss, emits the
    `cli.halt` envelope naming every missing prerequisite and returns its
    non-zero exit code, so the entry point stops before the cryptic failure.
    """
    missing = check_substrate(required=required, python_version=python_version)
    if not missing:
        return 0
    return cli.halt(
        "adapter substrate check failed", {"missing": missing}, stream=stream)
