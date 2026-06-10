"""Startup substrate check for the adapter entry points.

ADR 0008 makes the adapter a Python (stdlib-only) entry point orchestrating
`git` and `gh` as subprocesses, distributed with no install hook to verify the
substrate is present. This check runs first in every entry point so a missing
prerequisite surfaces as one clear, named line on stderr — naming the tool or
version floor and that it is required — rather than a cryptic exec failure deep
in a subprocess call.

`check_substrate` is pure (it reports what is missing); `preflight` wires that
report to a stderr line and a non-zero exit, mirroring the present/act split in
`cli.py` that keeps the logic directly testable.
"""

import shutil
import sys

# The tools the adapter shells out to. Python is checked separately by version.
REQUIRED_TOOLS = ("git", "gh")

# Minimum Python the adapter is written against. 3.8 is the floor: it is the
# oldest interpreter still shipped on the supported macOS/Linux targets, and
# nothing here reaches past its stdlib.
PYTHON_FLOOR = (3, 8)
PYTHON_FLOOR_STR = ".".join(str(n) for n in PYTHON_FLOOR)

EXIT_MISSING_SUBSTRATE = 3


def check_substrate(python_version=None):
    """Report the missing runtime prerequisites, in declaration order.

    Returns a list of human-readable lines, one per missing requirement; an
    empty list means the substrate is fully present. `python_version` defaults
    to the running interpreter and is injectable for testing.
    """
    version = python_version or sys.version_info
    missing = []
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            missing.append(
                f"{tool} is a required prerequisite and was not found on PATH")
    if tuple(version[:2]) < PYTHON_FLOOR:
        running = ".".join(str(n) for n in version[:2])
        missing.append(
            f"Python {PYTHON_FLOOR_STR} is a required prerequisite; "
            f"found {running}")
    return missing


def preflight(python_version=None, stream=None):
    """Run the substrate check; on a miss, emit a named error and exit non-zero.

    Returns 0 when the substrate is present and silent. On a miss, writes a
    single clear line naming every missing prerequisite to stderr and returns a
    non-zero code, so the entry point can stop before the cryptic failure.
    """
    missing = check_substrate(python_version=python_version)
    if not missing:
        return 0
    stream = stream or sys.stderr
    stream.write("adapter substrate check failed: " + "; ".join(missing) + "\n")
    return EXIT_MISSING_SUBSTRATE
