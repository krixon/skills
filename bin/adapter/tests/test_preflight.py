"""Tests for the substrate preflight: required tools and Python floor."""

import io
import json
import unittest
from unittest import mock

from adapter import preflight


class TestCheckSubstrate(unittest.TestCase):
    """check_substrate is pure: it reports what's missing, it doesn't exit."""

    def test_all_present_reports_nothing(self):
        with mock.patch("adapter.preflight.shutil.which", return_value="/usr/bin/x"):
            missing = preflight.check_substrate(python_version=(3, 11))
        self.assertEqual(missing, [])

    def test_missing_git_is_named(self):
        def which(tool):
            return None if tool == "git" else "/usr/bin/" + tool
        with mock.patch("adapter.preflight.shutil.which", side_effect=which):
            missing = preflight.check_substrate(python_version=(3, 11))
        self.assertEqual(len(missing), 1)
        self.assertIn("git", missing[0])

    def test_missing_gh_is_named(self):
        def which(tool):
            return None if tool == "gh" else "/usr/bin/" + tool
        with mock.patch("adapter.preflight.shutil.which", side_effect=which):
            missing = preflight.check_substrate(python_version=(3, 11))
        self.assertEqual(len(missing), 1)
        self.assertIn("gh", missing[0])

    def test_python_below_floor_is_named(self):
        with mock.patch("adapter.preflight.shutil.which", return_value="/usr/bin/x"):
            missing = preflight.check_substrate(python_version=(3, 6))
        self.assertEqual(len(missing), 1)
        self.assertIn("Python", missing[0])
        self.assertIn(preflight.PYTHON_FLOOR_STR, missing[0])

    def test_all_missing_each_named(self):
        with mock.patch("adapter.preflight.shutil.which", return_value=None):
            missing = preflight.check_substrate(python_version=(3, 6))
        joined = " ".join(missing)
        self.assertIn("git", joined)
        self.assertIn("gh", joined)
        self.assertIn("Python", joined)
        self.assertEqual(len(missing), 3)

    def test_subset_required_ignores_unlisted_tool(self):
        # A pure-git entry point (e.g. worktree) requires only git, so a missing
        # gh is not a missing prerequisite for it — the check never rejects an
        # environment over a tool the invoked command never uses.
        def which(tool):
            return None if tool == "gh" else "/usr/bin/" + tool
        with mock.patch("adapter.preflight.shutil.which", side_effect=which):
            missing = preflight.check_substrate(
                required=("git",), python_version=(3, 11))
        self.assertEqual(missing, [])


class TestPreflight(unittest.TestCase):
    """preflight wires the check to the cli.halt envelope and its exit code."""

    def test_all_present_returns_zero_and_is_silent(self):
        err = io.StringIO()
        with mock.patch("adapter.preflight.shutil.which", return_value="/usr/bin/x"):
            rc = preflight.preflight(python_version=(3, 11), stream=err)
        self.assertEqual(rc, 0)
        self.assertEqual(err.getvalue(), "")

    def test_missing_tool_returns_nonzero(self):
        err = io.StringIO()
        with mock.patch("adapter.preflight.shutil.which", return_value=None):
            rc = preflight.preflight(python_version=(3, 11), stream=err)
        self.assertNotEqual(rc, 0)

    def test_missing_tool_emits_named_halt_envelope(self):
        err = io.StringIO()

        def which(tool):
            return None if tool == "gh" else "/usr/bin/" + tool
        with mock.patch("adapter.preflight.shutil.which", side_effect=which):
            preflight.preflight(python_version=(3, 11), stream=err)
        # Same halt shape as every other adapter blocker: a JSON envelope with
        # status "halted", a reason, and the named missing prerequisites.
        payload = json.loads(err.getvalue())
        self.assertEqual(payload["status"], "halted")
        self.assertIn("substrate", payload["reason"].lower())
        self.assertTrue(any("gh" in m for m in payload["missing"]))


if __name__ == "__main__":
    unittest.main()
