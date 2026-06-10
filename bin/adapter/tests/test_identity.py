"""Tests for the internal bot-identity resolution and startup check.

This ports the gh-identity.sh contract into the adapter: the env is read once
at startup, the half-configured state is refused, and the two valid states
(both unset, both set non-empty) resolve to a small value object the writes
consult. The matrix here is the same one the retired hook tested.
"""

import unittest

from adapter import identity


def _resolve(acct=None, token=None):
    """Resolve identity from an explicit env mapping, omitting absent vars."""
    env = {}
    if acct is not None:
        env["GITHUB_BOT_ACCOUNT"] = acct
    if token is not None:
        env["GITHUB_BOT_TOKEN_CMD"] = token
    return identity.resolve(env)


class TestValidStates(unittest.TestCase):
    def test_both_unset_is_unconfigured(self):
        ident = _resolve()
        self.assertFalse(ident.configured)
        self.assertIsNone(ident.account)
        self.assertIsNone(ident.token_cmd)

    def test_both_set_is_configured(self):
        ident = _resolve(acct="krixon-bot", token="gh auth token")
        self.assertTrue(ident.configured)
        self.assertEqual(ident.account, "krixon-bot")
        self.assertEqual(ident.token_cmd, "gh auth token")


class TestHalfConfiguredRefused(unittest.TestCase):
    def test_account_without_token(self):
        with self.assertRaises(identity.HalfConfigured):
            _resolve(acct="krixon-bot")

    def test_token_without_account(self):
        with self.assertRaises(identity.HalfConfigured):
            _resolve(token="gh auth token")

    def test_account_set_but_empty(self):
        with self.assertRaises(identity.HalfConfigured):
            _resolve(acct="", token="gh auth token")

    def test_token_set_but_empty(self):
        with self.assertRaises(identity.HalfConfigured):
            _resolve(acct="krixon-bot", token="")

    def test_both_set_but_empty(self):
        with self.assertRaises(identity.HalfConfigured):
            _resolve(acct="", token="")

    def test_error_names_each_var_state(self):
        # The refusal must name which var is wrong, like the hook did.
        with self.assertRaises(identity.HalfConfigured) as ctx:
            _resolve(acct="krixon-bot")
        msg = str(ctx.exception)
        self.assertIn("GITHUB_BOT_ACCOUNT", msg)
        self.assertIn("GITHUB_BOT_TOKEN_CMD", msg)


class TestAuthorFilter(unittest.TestCase):
    def test_configured_filters_on_bot_account(self):
        ident = _resolve(acct="krixon-bot", token="gh auth token")
        self.assertEqual(ident.author_filter(), "krixon-bot")

    def test_unconfigured_has_no_author_filter(self):
        ident = _resolve()
        self.assertIsNone(ident.author_filter())


if __name__ == "__main__":
    unittest.main()
