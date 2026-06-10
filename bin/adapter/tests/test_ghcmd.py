"""Tests for the gh subprocess substrate.

The real shell-out point is run_gh; these tests drive a recording fake through
the same `runner` seam the command logic uses, so they assert on the argv built
and the parsing — never the network. The one real-subprocess concern (the token
prefix landing only in the child env) is checked by inspecting the env passed to
the runner, not by evaluating a token command.
"""

import json
import unittest

from adapter import ghcmd
from adapter.identity import Identity


class RecordingRunner:
    """A run_gh stand-in: records each call and returns canned stdout."""

    def __init__(self, stdout="", returncode=0):
        self.calls = []
        self._stdout = stdout
        self._returncode = returncode

    def __call__(self, args, env=None, input=None, check=True):
        self.calls.append({"args": list(args), "env": env, "input": input})
        return ghcmd.GhResult(args=list(args), returncode=self._returncode,
                              stdout=self._stdout, stderr="")


class TestGhJson(unittest.TestCase):
    def test_parses_stdout_json(self):
        runner = RecordingRunner(stdout=json.dumps({"number": 7}))
        data = ghcmd.gh_json(["issue", "view", "7", "--json", "number"],
                             runner=runner)
        self.assertEqual(data, {"number": 7})
        self.assertEqual(runner.calls[0]["args"][0], "issue")

    def test_empty_stdout_returns_default(self):
        runner = RecordingRunner(stdout="")
        self.assertEqual(ghcmd.gh_json(["x"], runner=runner, default=[]), [])


class TestTokenEnv(unittest.TestCase):
    def test_configured_identity_sets_gh_token_in_child_env(self):
        # A write performed as the bot evaluates the token command and passes
        # GH_TOKEN in the child env only — never as an argv field.
        runner = RecordingRunner(stdout="{}")
        ident = Identity(account="krixon-bot", token_cmd="printf tok-123")
        ghcmd.gh_as_author(["pr", "create"], ident, runner=runner)
        env = runner.calls[0]["env"]
        self.assertEqual(env["GH_TOKEN"], "tok-123")
        # The token never appears in argv.
        self.assertNotIn("tok-123", " ".join(runner.calls[0]["args"]))

    def test_unconfigured_identity_passes_no_token(self):
        runner = RecordingRunner(stdout="{}")
        ident = Identity()
        ghcmd.gh_as_author(["pr", "create"], ident, runner=runner)
        env = runner.calls[0]["env"]
        # No GH_TOKEN injected; normal gh identity is used.
        self.assertTrue(env is None or "GH_TOKEN" not in env)


class TestGhError(unittest.TestCase):
    def test_nonzero_raises_with_stderr(self):
        runner = RecordingRunner(returncode=1)
        runner._stdout = ""

        def failing(args, env=None, input=None, check=True):
            return ghcmd.GhResult(args=list(args), returncode=1, stdout="",
                                  stderr="boom")

        with self.assertRaises(ghcmd.GhError) as ctx:
            ghcmd.gh_json(["bad"], runner=failing)
        self.assertIn("boom", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
