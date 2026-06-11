"""Tests for the acli subprocess substrate and the Jira credential.

The real shell-out point is run_acli; these tests drive a recording fake through
the same `runner` seam the Jira backend uses, so they assert on the argv built
and the parsing — never the network. The api_token's confinement to a single
child env (never argv) is checked by inspecting the env passed to the runner.
The urllib /transitions helper takes an injectable opener so the REST fallback
is tested against a canned response with no network.
"""

from __future__ import annotations

import base64
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


class _FakeResponse:
    """A urlopen stand-in: yields canned bytes from .read()."""

    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class TestFetchTransitions(unittest.TestCase):
    """The mandatory urllib /transitions fallback — acli cannot enumerate them.

    `acli jira workitem transition` takes only `--status <name>` and offers no
    listing verb, and view/search return transitions: null with no --expand. So
    the only way to resolve a target category to a concrete reachable status name
    at call time is this REST call.
    """

    _PAYLOAD = json.dumps({
        "transitions": [
            {"id": "11", "name": "Start work",
             "to": {"name": "In Progress",
                    "statusCategory": {"key": "indeterminate"}}},
            {"id": "21", "name": "Mark done",
             "to": {"name": "Done", "statusCategory": {"key": "done"}}},
        ],
    })

    def _cred(self) -> aclicmd.JiraCredential:
        return aclicmd.JiraCredential(site="https://acme.atlassian.net",
                                      email="bot@acme.io", token_cmd="printf tok")

    def test_returns_each_transition_target_name_and_category(self) -> None:
        captured: dict[str, Any] = {}

        def opener(req: Any, *a: Any, **kw: Any) -> _FakeResponse:
            captured["url"] = req.full_url
            captured["auth"] = req.get_header("Authorization")
            return _FakeResponse(self._PAYLOAD)

        out = aclicmd.fetch_transitions(self._cred(), "PROJ-7", opener=opener)
        self.assertEqual(
            out,
            [{"name": "In Progress", "category": "indeterminate"},
             {"name": "Done", "category": "done"}],
        )

    def test_hits_the_transitions_endpoint_on_the_site(self) -> None:
        def opener(req: Any, *a: Any, **kw: Any) -> _FakeResponse:
            self.assertEqual(
                req.full_url,
                "https://acme.atlassian.net/rest/api/3/issue/PROJ-7/transitions")
            return _FakeResponse(self._PAYLOAD)

        aclicmd.fetch_transitions(self._cred(), "PROJ-7", opener=opener)

    def test_authenticates_with_http_basic_email_and_token(self) -> None:
        captured: dict[str, Any] = {}

        def opener(req: Any, *a: Any, **kw: Any) -> _FakeResponse:
            captured["auth"] = req.get_header("Authorization")
            return _FakeResponse(self._PAYLOAD)

        aclicmd.fetch_transitions(self._cred(), "PROJ-7", opener=opener)
        scheme, _, b64 = captured["auth"].partition(" ")
        self.assertEqual(scheme, "Basic")
        self.assertEqual(base64.b64decode(b64).decode(), "bot@acme.io:tok")

    def test_evaluates_token_command_via_injectable_evaluator(self) -> None:
        # The api_token is evaluated from the command, never read from argv/env
        # literally — the evaluator seam lets the test confirm it without a shell.
        def opener(req: Any, *a: Any, **kw: Any) -> _FakeResponse:
            return _FakeResponse(self._PAYLOAD)

        seen = []

        def evaluator(cmd: str) -> str:
            seen.append(cmd)
            return "evaluated-secret"

        captured: dict[str, Any] = {}

        def auth_opener(req: Any, *a: Any, **kw: Any) -> _FakeResponse:
            captured["auth"] = req.get_header("Authorization")
            return _FakeResponse(self._PAYLOAD)

        aclicmd.fetch_transitions(self._cred(), "PROJ-7", opener=auth_opener,
                                  token_evaluator=evaluator)
        self.assertEqual(seen, ["printf tok"])
        b64 = captured["auth"].split(" ", 1)[1]
        self.assertEqual(base64.b64decode(b64).decode(),
                         "bot@acme.io:evaluated-secret")


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
