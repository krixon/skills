"""Tests for the Jira credential resolution and the acli auth startup check.

The credential mirrors the GitHub identity contract: one source `(site, email,
api_token_cmd)`, read once at startup, the half-configured state refused, the
api_token evaluated from a command so it never persists. The startup check
verifies `acli` is itself authenticated by parsing `acli jira auth status` — a
clean authenticated/not state, never a status-name read.
"""

from __future__ import annotations

import unittest
from typing import Any, Sequence

from adapter import aclicmd


def _resolve(site: str | None = None, email: str | None = None,
             token_cmd: str | None = None) -> aclicmd.JiraCredential:
    env: dict[str, str] = {}
    if site is not None:
        env["JIRA_SITE"] = site
    if email is not None:
        env["JIRA_EMAIL"] = email
    if token_cmd is not None:
        env["JIRA_API_TOKEN_CMD"] = token_cmd
    return aclicmd.resolve_credential(env)


class TestCredentialResolution(unittest.TestCase):
    def test_all_set_is_configured(self) -> None:
        cred = _resolve(site="https://acme.atlassian.net",
                        email="bot@acme.io", token_cmd="printf tok")
        self.assertEqual(cred.site, "https://acme.atlassian.net")
        self.assertEqual(cred.email, "bot@acme.io")
        self.assertEqual(cred.token_cmd, "printf tok")

    def test_partial_is_refused_naming_each_var(self) -> None:
        with self.assertRaises(aclicmd.CredentialIncomplete) as ctx:
            _resolve(site="https://acme.atlassian.net")
        msg = str(ctx.exception)
        self.assertIn("JIRA_SITE", msg)
        self.assertIn("JIRA_EMAIL", msg)
        self.assertIn("JIRA_API_TOKEN_CMD", msg)

    def test_empty_var_is_refused(self) -> None:
        with self.assertRaises(aclicmd.CredentialIncomplete):
            _resolve(site="https://acme.atlassian.net", email="",
                     token_cmd="printf tok")

    def test_all_unset_is_refused(self) -> None:
        # Unlike the GitHub identity (where unconfigured is a valid solo-dev
        # state), the Jira backend has no unconfigured mode: the api_token is the
        # shared source for both acli and the urllib /transitions call.
        with self.assertRaises(aclicmd.CredentialIncomplete):
            _resolve()


class _AuthRunner:
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


class TestAuthStatus(unittest.TestCase):
    # The real `acli jira auth status` (acli 1.x) emits a plain-text report and
    # rejects `--json` as an unknown flag, so the check parses the text.
    _AUTHED = ("✓ Authenticated\n  Site: acme.atlassian.net\n"
               "  Email: bot@acme.io\n  Authentication Type: api_token\n")
    _NOT_AUTHED = "✗ Not authenticated\n"

    def test_authenticated_when_status_reports_authenticated(self) -> None:
        runner = _AuthRunner(stdout=self._AUTHED)
        self.assertTrue(aclicmd.is_authenticated(runner=runner))
        # It asks acli for its own auth state in plain text — never --json,
        # which acli 1.x rejects as an unknown flag.
        argv = runner.calls[0]["args"]
        self.assertEqual(argv, ["jira", "auth", "status"])
        self.assertNotIn("--json", argv)

    def test_not_authenticated_when_status_says_so_at_exit_zero(self) -> None:
        # The negative report must not be mistaken for the positive one even
        # when acli exits zero — "not authenticated" contains "authenticated".
        runner = _AuthRunner(stdout=self._NOT_AUTHED)
        self.assertFalse(aclicmd.is_authenticated(runner=runner))

    def test_not_authenticated_when_acli_exits_nonzero(self) -> None:
        # A non-zero exit (acli not logged in) reads as not-authenticated, not a
        # crash — the startup check turns it into a clear halt.
        runner = _AuthRunner(returncode=1, stderr="not logged in")
        self.assertFalse(aclicmd.is_authenticated(runner=runner))


if __name__ == "__main__":
    unittest.main()
