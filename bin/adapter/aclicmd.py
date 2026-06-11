"""Thin `acli` subprocess substrate for the Jira tracker backend, per ADR 0008.

The `gh` half lives in `ghcmd.py`; this is the `acli` (official Atlassian CLI)
half — the symmetric substrate the Jira backend composes over. `run_acli` is the
single shell-out point; the higher-level helpers (`acli_json`, `acli_text`) build
on it, and the backend takes the runner as an injectable seam so unit tests
assert on the argv built and the JSON parsed without touching the network.

The security boundary (SECURITY.md) holds the same shape as the `gh` half:

  - bodies and untrusted fields pass on stdin or a file, never spliced into argv
    — `run_acli` exposes `input` for this;
  - the operator's api_token materialises only in a single child env, never in
    argv, a body, or a logged value.

`acli` owns its own stored auth (the startup check verifies it via `acli jira
auth status`), but it offers no supported way to hand that stored credential to
a urllib call. `acli jira workitem transition` takes only `--status <name>` and
exposes no transition-listing verb, so resolving a target status by category at
call time needs the REST `GET /rest/api/3/issue/{key}/transitions` endpoint
directly. `fetch_transitions` is that one mandatory urllib call — it takes an
injectable opener seam so the resolution is tested against a canned response
with no network, and authenticates with HTTP Basic `email:api_token` against the
same site (the operator's api_token is the shared source for both code paths,
which is why the adapter pins api_token auth — under OAuth there is no static
token to share).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.request
from typing import Any, Callable, Mapping, Sequence

# The `acli` runner seam: any callable with run_acli's signature, returning an
# AcliResult. The Jira backend takes one so tests can substitute a recording fake.
Runner = Callable[..., "AcliResult"]

# The urllib opener seam for the /transitions fallback: a callable taking a
# urllib.request.Request and returning an object whose .read() yields the body
# bytes (a urlopen stand-in). Injectable so the REST call is tested offline.
Opener = Callable[..., Any]


class AcliError(RuntimeError):
    """An `acli` subprocess exited non-zero. Carries argv, code, and stderr."""

    def __init__(self, args: Sequence[str], returncode: int, stderr: str) -> None:
        self.args = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"acli {' '.join(args)} exited {returncode}: {stderr.strip()}")


class AcliResult:
    """The outcome of an `acli` call: argv, exit code, captured streams."""

    def __init__(self, args: Sequence[str], returncode: int, stdout: str,
                 stderr: str) -> None:
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_acli(args: Sequence[str], env: dict[str, str] | None = None,
             input: str | None = None, check: bool = True) -> AcliResult:
    """Run `acli <args>`, capturing stdout/stderr as text.

    `env`, when given, is merged onto the parent environment for this call only.
    `input`, when given, is fed on stdin (the out-of-band body channel). Returns
    an AcliResult; the caller decides whether to raise via the helpers below.
    """
    child_env = None
    if env is not None:
        child_env = {**os.environ, **env}
    result = subprocess.run(
        ["acli", *args],
        env=child_env,
        input=input,
        text=True,
        capture_output=True,
    )
    return AcliResult(args=list(args), returncode=result.returncode,
                      stdout=result.stdout, stderr=result.stderr)


def _checked(result: AcliResult) -> AcliResult:
    if result.returncode != 0:
        raise AcliError(result.args, result.returncode, result.stderr)
    return result


def acli_text(args: Sequence[str], runner: Runner | None = None,
              env: dict[str, str] | None = None, input: str | None = None,
              check: bool = True) -> str:
    """Run `acli` and return its stdout text (stripped)."""
    runner = runner or run_acli
    result = runner(args, env=env, input=input, check=check)
    if check:
        _checked(result)
    return result.stdout.strip()


def acli_json(args: Sequence[str], runner: Runner | None = None,
              env: dict[str, str] | None = None, input: str | None = None,
              default: Any = None, check: bool = True) -> Any:
    """Run `acli` and parse its stdout as JSON.

    Empty stdout yields `default` (e.g. an absent optional record), so a command
    can distinguish "no data" from a parse it must branch on.
    """
    runner = runner or run_acli
    result = runner(args, env=env, input=input, check=check)
    if check:
        _checked(result)
    text = result.stdout.strip()
    if not text:
        return default
    return json.loads(text)


# --- credential -------------------------------------------------------------

# The three env vars that configure the single Jira credential. The api_token is
# named indirectly (a command that prints it) so it never persists in the
# environment, mirroring GITHUB_BOT_TOKEN_CMD.
_SITE_VAR = "JIRA_SITE"
_EMAIL_VAR = "JIRA_EMAIL"
_TOKEN_CMD_VAR = "JIRA_API_TOKEN_CMD"


class CredentialIncomplete(RuntimeError):
    """The Jira credential env is incomplete; the adapter refuses to act.

    Carries a message naming each var's state so the operator can see which is
    missing, mirroring the GitHub identity's half-configured refusal.
    """


class JiraCredential:
    """The resolved Jira credential: the single source `(site, email, token)`.

    `site` is the Atlassian base URL; `email` and the api_token (evaluated from
    `token_cmd`) form the HTTP Basic pair the urllib `/transitions` call uses.
    `acli` carries its own stored auth — this credential exists for the one REST
    call acli cannot make, and pins api_token auth (under OAuth there is no
    static token to share between the two code paths).
    """

    def __init__(self, site: str, email: str, token_cmd: str) -> None:
        self.site = site
        self.email = email
        self.token_cmd = token_cmd


def _state(present: bool, nonempty: bool) -> str:
    if not present:
        return "unset"
    if not nonempty:
        return "set but empty"
    return "set"


def resolve_credential(env: Mapping[str, str] | None = None) -> JiraCredential:
    """Resolve the Jira credential from the environment (or an explicit mapping).

    All three vars must be set and non-empty. Unlike the GitHub identity — where
    "all unset" is a valid solo-dev mode — the Jira backend has no unconfigured
    state: the api_token is the shared source for both acli's REST site and the
    urllib `/transitions` fallback, so a missing one is always a refusal.
    """
    if env is None:
        env = os.environ
    parts = {}
    states = {}
    for var in (_SITE_VAR, _EMAIL_VAR, _TOKEN_CMD_VAR):
        present = var in env
        value = env.get(var, "")
        parts[var] = value
        states[var] = _state(present, bool(value))
    if all(parts.values()):
        return JiraCredential(site=parts[_SITE_VAR], email=parts[_EMAIL_VAR],
                              token_cmd=parts[_TOKEN_CMD_VAR])
    raise CredentialIncomplete(
        "Jira credential is incomplete. All three env vars must be set and "
        "non-empty (api_token auth, not OAuth).\n"
        f"  - {_SITE_VAR}: {states[_SITE_VAR]}\n"
        f"  - {_EMAIL_VAR}: {states[_EMAIL_VAR]}\n"
        f"  - {_TOKEN_CMD_VAR}: {states[_TOKEN_CMD_VAR]}"
    )


def eval_token(token_cmd: str) -> str:
    """Evaluate the api_token command in a shell and return its stdout, stripped.

    Mirrors ghcmd.eval_token: the command is the operator's own configured
    indirection, run once, its output never logged. A failing command withholds
    its stderr to avoid leaking secret fragments.
    """
    result = subprocess.run(token_cmd, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        raise AcliError(
            ["<jira-api-token-command>"], result.returncode,
            "token command failed; stderr withheld to avoid leaking secrets")
    return result.stdout.strip()


# --- startup auth check -----------------------------------------------------

def is_authenticated(runner: Runner | None = None) -> bool:
    """Whether `acli` is itself authenticated to Jira.

    The startup check, mirroring the GitHub identity check's shape. `acli jira
    auth status` has no machine-readable mode — `--json` is rejected as an
    unknown flag in acli 1.x — so this parses its plain-text report: a clean
    exit carrying the authenticated marker means logged in. A non-zero exit
    (acli not logged in at all) reads as not-authenticated rather than crashing,
    so the startup check can turn it into one clear halt. The negative marker is
    matched explicitly so a "not authenticated" line that still exits zero is
    not mistaken for the positive one.
    """
    runner = runner or run_acli
    result = runner(["jira", "auth", "status"], check=False)
    if result.returncode != 0:
        return False
    text = result.stdout.lower()
    return "authenticated" in text and "not authenticated" not in text


# --- the mandatory urllib /transitions fallback -----------------------------

def fetch_transitions(credential: JiraCredential, key: str,
                      opener: Opener | None = None,
                      token_evaluator: Callable[[str], str] | None = None,
                      ) -> list[dict[str, str]]:
    """The reachable transitions for an issue, each with its target status's
    name and platform-stable category key.

    This is the one urllib REST call the adapter is forced to make: `acli`
    transitions only by status name and cannot enumerate transitions, so
    resolving a target category (`indeterminate`/`done`) to a concrete reachable
    status name *at call time* — the binding that survives a project workflow
    rename — has no acli path. It calls `GET {site}/rest/api/3/issue/{key}/
    transitions`, which returns each `transitions[].to.name` alongside its
    `transitions[].to.statusCategory.key`.

    Auth is HTTP Basic `email:api_token` against the same site; the api_token is
    evaluated from the credential's command (the operator's indirection) so it
    materialises only on this one request and never persists. `opener` and
    `token_evaluator` are injectable seams so the call is tested offline.
    """
    opener = opener or urllib.request.urlopen
    token_evaluator = token_evaluator or eval_token

    token = token_evaluator(credential.token_cmd)
    basic = base64.b64encode(
        f"{credential.email}:{token}".encode("utf-8")).decode("ascii")
    url = f"{credential.site}/rest/api/3/issue/{key}/transitions"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
    })
    with opener(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    out = []
    for tr in payload.get("transitions") or []:
        to = tr.get("to") or {}
        out.append({
            "name": to.get("name"),
            "category": (to.get("statusCategory") or {}).get("key"),
        })
    return out
