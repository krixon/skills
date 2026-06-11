"""Internal bot identity for the GitHub backend, per ADR 0008.

Identity is the adapter's, not the caller's: the agent never chooses an account
because it never issues the `gh` call. This module resolves the two env vars
that configure a bot identity and refuses the half-configured state at startup —
the behaviour the retired `gh-identity.sh` PreToolUse hook held in prose.

Two states are valid (skills/GITHUB.md → PR identity):

  - both unset            → unconfigured: no bot dance, `gh` runs as the
                            authenticated user, and author filters drop;
  - both set and non-empty → configured: writes that must appear as the PR
                            author carry a `GH_TOKEN` evaluated from the token
                            command, and rework/land queries filter on the bot.

Every other combination — one var without the other, or either set-but-empty —
is the silent-fallback gap (a PR opened as the maintainer instead of the bot).
`resolve` refuses it rather than guessing.
"""

from __future__ import annotations

import os
from typing import Mapping


class HalfConfigured(RuntimeError):
    """The bot-identity env is half-configured; the adapter refuses to act.

    Carries a message naming each var's state so the operator can see which
    half is wrong, mirroring the hook's report.
    """


class Identity:
    """Resolved bot identity: configured (bot) or not (default `gh`)."""

    def __init__(self, account: str | None = None,
                 token_cmd: str | None = None) -> None:
        self.account = account
        self.token_cmd = token_cmd

    @property
    def configured(self) -> bool:
        return self.account is not None

    def author_filter(self) -> str | None:
        """The `--author` value for rework/land queries, or None when
        unconfigured — where the filter drops to match any open PR."""
        return self.account


def _state(present: bool, nonempty: bool) -> str:
    if not present:
        return "unset"
    if not nonempty:
        return "set but empty"
    return "set"


def resolve(env: Mapping[str, str] | None = None) -> Identity:
    """Resolve identity from the environment (or an explicit mapping).

    Returns an Identity. Raises HalfConfigured on any half-configured state.
    """
    if env is None:
        env = os.environ

    acct_present = "GITHUB_BOT_ACCOUNT" in env
    tok_present = "GITHUB_BOT_TOKEN_CMD" in env
    acct = env.get("GITHUB_BOT_ACCOUNT", "")
    tok = env.get("GITHUB_BOT_TOKEN_CMD", "")
    acct_ok = bool(acct)
    tok_ok = bool(tok)

    # Both entirely unset → no bot configured → default authed gh.
    if not acct_present and not tok_present:
        return Identity()
    # Both set and non-empty → bot fully configured.
    if acct_ok and tok_ok:
        return Identity(account=acct, token_cmd=tok)

    # Anything else is half-configured; name each var's state precisely.
    raise HalfConfigured(
        "GitHub bot identity is half-configured. The two env vars must be set "
        "together and non-empty, or both left unset.\n"
        f"  - GITHUB_BOT_ACCOUNT: {_state(acct_present, acct_ok)}\n"
        f"  - GITHUB_BOT_TOKEN_CMD: {_state(tok_present, tok_ok)}"
    )
