"""File-mode regression: adapter entry points ship executable, modules don't.

A marketplace install is a git clone, which reproduces the committed tree mode,
so the executable bit is an invariant of what is committed — not of an install
hook (ADR 0008's distribution edge). These tests read `git ls-files -s` so they
assert the committed mode, the thing an install actually reproduces, rather than
the working-tree mode a local `chmod` could mask.
"""

from __future__ import annotations

import os
import subprocess
import unittest

# bin/ — the adapter root, two levels up from this test file.
_BIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO_ROOT = os.path.dirname(_BIN)

_EXEC_MODE = "100755"
_FILE_MODE = "100644"


def _ls_files() -> dict[str, str]:
    """Map every tracked path under bin/ to its committed mode string."""
    result = subprocess.run(
        ["git", "ls-files", "-s", "bin/"],
        cwd=_REPO_ROOT, text=True, capture_output=True, check=True,
    )
    modes = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        meta, path = line.split("\t", 1)
        mode = meta.split()[0]
        modes[path] = mode
    return modes


def _is_entry_point(path: str) -> bool:
    """An adapter entry point: a file directly under bin/ with no extension.

    The importable package lives under bin/adapter/; the executables sit at the
    top of bin/ and are invoked by absolute path, extensionless. Keying off shape
    rather than a hard-coded name makes the test self-maintaining: a new entry
    point shipped non-executable fails it without anyone editing the list.
    """
    head, tail = os.path.split(path)
    return head == "bin" and "." not in tail


class TestEntryPointModes(unittest.TestCase):
    def setUp(self) -> None:
        self.modes = _ls_files()

    def test_at_least_one_entry_point_tracked(self) -> None:
        # Guards against the shape predicate silently matching nothing, which
        # would make the executable-mode assertion vacuously pass.
        entry_points = [p for p in self.modes if _is_entry_point(p)]
        self.assertIn("bin/worktree", entry_points)

    def test_entry_points_are_executable(self) -> None:
        for path, mode in self.modes.items():
            if _is_entry_point(path):
                self.assertEqual(
                    mode, _EXEC_MODE,
                    f"entry point {path} is committed {mode}, expected {_EXEC_MODE}")

    def test_adapter_modules_are_not_executable(self) -> None:
        for path, mode in self.modes.items():
            if path.startswith("bin/adapter/") and path.endswith(".py"):
                self.assertEqual(
                    mode, _FILE_MODE,
                    f"module {path} is committed {mode}, expected {_FILE_MODE}")


if __name__ == "__main__":
    unittest.main()
