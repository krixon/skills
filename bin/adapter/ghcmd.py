"""Thin `gh` subprocess substrate for the GitHub tracker backend, per ADR 0008.

The git half lives in `gitcmd.py`; this is the `gh` half. `run_gh` is the single
shell-out point — every tracker command composes the higher-level helpers
(`gh_json`, `gh_text`, `gh_as_author`) over it, and the command logic takes the
runner as an injectable seam so unit tests assert on the argv built and the
JSON parsed without touching the network.

Two calling conventions enforce the security boundary (SECURITY.md):

  - bodies and untrusted fields pass on stdin (`--body-file -`, `-F field=@-`),
    never spliced into argv — `run_gh` exposes `input` for this;
  - the bot token materialises only as `GH_TOKEN` in a single child env, never
    in argv, a body, or a logged value — `gh_as_author` evaluates the token
    command inline per call and injects it for exactly that invocation.
"""

import json
import os
import subprocess


class GhError(RuntimeError):
    """A `gh` subprocess exited non-zero. Carries argv, code, and stderr."""

    def __init__(self, args, returncode, stderr):
        self.args = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"gh {' '.join(args)} exited {returncode}: {stderr.strip()}")


class GhResult:
    """The outcome of a `gh` call: argv, exit code, captured streams."""

    def __init__(self, args, returncode, stdout, stderr):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_gh(args, env=None, input=None, check=True):
    """Run `gh <args>`, capturing stdout/stderr as text.

    `env`, when given, is merged onto the parent environment for this call only
    (the channel `GH_TOKEN` rides). `input`, when given, is fed on stdin (the
    out-of-band body channel). Returns a GhResult; the caller decides whether to
    raise via the helpers below.
    """
    child_env = None
    if env is not None:
        child_env = {**os.environ, **env}
    result = subprocess.run(
        ["gh", *args],
        env=child_env,
        input=input,
        text=True,
        capture_output=True,
    )
    return GhResult(args=list(args), returncode=result.returncode,
                    stdout=result.stdout, stderr=result.stderr)


def _checked(result):
    if result.returncode != 0:
        raise GhError(result.args, result.returncode, result.stderr)
    return result


def gh_text(args, runner=None, env=None, input=None, check=True):
    """Run `gh` and return its stdout text (stripped)."""
    runner = runner or run_gh
    result = runner(args, env=env, input=input, check=check)
    if check:
        _checked(result)
    return result.stdout.strip()


def gh_json(args, runner=None, env=None, input=None, default=None, check=True):
    """Run `gh` and parse its stdout as JSON.

    Empty stdout yields `default` (e.g. an absent optional record), so a command
    can distinguish "no data" from a parse it must branch on.
    """
    runner = runner or run_gh
    result = runner(args, env=env, input=input, check=check)
    if check:
        _checked(result)
    text = result.stdout.strip()
    if not text:
        return default
    return json.loads(text)


def eval_token(token_cmd):
    """Evaluate the token command in a shell and return its stdout, stripped.

    Mirrors `GH_TOKEN=$(eval "$GITHUB_BOT_TOKEN_CMD")`: the command is the
    operator's own configured indirection, run once, its output never logged.
    """
    result = subprocess.run(token_cmd, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        raise GhError([token_cmd], result.returncode, result.stderr)
    return result.stdout.strip()


def gh_as_author(args, identity, runner=None, input=None, check=True):
    """Run a `gh` write that must appear as the PR author.

    When the identity is configured, evaluate its token command and inject the
    result as `GH_TOKEN` for this one call. When unconfigured, no token is added
    and `gh` runs as the authenticated user. Returns the GhResult.
    """
    runner = runner or run_gh
    env = None
    if identity.configured:
        env = {"GH_TOKEN": eval_token(identity.token_cmd)}
    result = runner(args, env=env, input=input, check=check)
    if check:
        _checked(result)
    return result
