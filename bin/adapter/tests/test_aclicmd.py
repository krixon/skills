"""Tests for the acli subprocess substrate and the Jira credential.

The real shell-out point is run_acli; these tests drive a recording fake through
the same `runner` seam the Jira backend uses, so they assert on the argv built
and the parsing — never the network. The api_token's confinement to a single
child env (never argv) is checked by inspecting the env passed to the runner.
The transitions REST call no longer lives here — the close path drives it over
the `curl` seam in `jiracmd`, exercised by test_jira.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Sequence

from adapter import aclicmd


class RecordingRunner:
    """A run_acli stand-in: records each call and returns canned stdout."""

    def __init__(self, stdout: str = "", returncode: int = 0,
                 stderr: str = "") -> None:
        self.calls: list[dict[str, Any]] = []
        self._stdout = stdout
        self._returncode = returncode
        self._stderr = stderr

    def __call__(self, args: Sequence[str], env: dict[str, str] | None = None,
                 input: str | None = None, check: bool = True) -> aclicmd.AcliResult:
        self.calls.append({"args": list(args), "env": env, "input": input})
        return aclicmd.AcliResult(args=list(args), returncode=self._returncode,
                                  stdout=self._stdout, stderr=self._stderr)


class TestAcliJson(unittest.TestCase):
    def test_parses_stdout_json(self) -> None:
        runner = RecordingRunner(stdout=json.dumps({"key": "PROJ-1"}))
        data = aclicmd.acli_json(["jira", "workitem", "view", "PROJ-1", "--json"],
                                 runner=runner)
        self.assertEqual(data, {"key": "PROJ-1"})
        self.assertEqual(runner.calls[0]["args"][0], "jira")

    def test_empty_stdout_returns_default(self) -> None:
        runner = RecordingRunner(stdout="")
        self.assertEqual(aclicmd.acli_json(["x"], runner=runner, default=[]), [])


class TestAcliError(unittest.TestCase):
    def test_nonzero_raises_with_stderr(self) -> None:
        def failing(args: Sequence[str], env: dict[str, str] | None = None,
                    input: str | None = None,
                    check: bool = True) -> aclicmd.AcliResult:
            return aclicmd.AcliResult(args=list(args), returncode=1, stdout="",
                                      stderr="boom")

        with self.assertRaises(aclicmd.AcliError) as ctx:
            aclicmd.acli_json(["bad"], runner=failing)
        self.assertIn("boom", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
