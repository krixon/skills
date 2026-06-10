"""Tests for the substrate preflight: required tools and Python floor."""

import io
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


class TestPreflight(unittest.TestCase):
    """preflight wires the check to a clear, named stderr error and exit code."""

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

    def test_missing_tool_writes_named_single_line_error(self):
        err = io.StringIO()

        def which(tool):
            return None if tool == "gh" else "/usr/bin/" + tool
        with mock.patch("adapter.preflight.shutil.which", side_effect=which):
            preflight.preflight(python_version=(3, 11), stream=err)
        out = err.getvalue()
        self.assertIn("gh", out)
        self.assertIn("prerequisite", out.lower())
        # One line: the message is a single newline-terminated line, not a
        # multi-line JSON blob.
        self.assertEqual(out.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
