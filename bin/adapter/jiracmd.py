"""Thin `curl` REST substrate for the Jira tracker backend, per ADR 0008.

The `gh` half of the substrate lives in `ghcmd.py`; this is the Jira REST half.
It exists because Jira has no first-party CLI that both speaks the full REST
surface and trusts the OS/corporate trust store. Python's `urllib` does not use
the system trust store, so behind an enterprise TLS-intercepting proxy it fails
with `CERTIFICATE_VERIFY_FAILED`; `curl` (like `acli` and `gh`) honours the OS
trust store, so every Jira REST call shells out through `curl` instead.

`run_curl` is the single shell-out point — the backend composes the higher-level
helpers (`request`, `request_json`) over it, and takes the runner as an injectable
seam so unit tests assert on the request built (method, URL, payload) and the JSON
parsed without touching the network.

The security boundary (SECURITY.md): the Basic-auth credential (the Jira email and
api_token) never rides argv. It is written into a `curl` config file fed on stdin
(`curl -K -`), so the token is invisible to `ps`, the same out-of-band discipline
`gh_as_author` keeps for `GH_TOKEN`.
"""

from __future__ import annotations

import base64
import json
import subprocess
from typing import Any, Callable, Mapping, Sequence

# The `curl` runner seam: any callable with run_curl's signature, returning a
# CurlResult. The backend logic takes one so tests substitute a recording fake.
Runner = Callable[..., "CurlResult"]


class JiraError(RuntimeError):
    """A Jira REST call failed (curl error or a non-2xx HTTP status).

    Carries the method, URL, the HTTP status (or None on a transport error),
    and the response body so the failure is contextful, never a bare exit code.
    """

    def __init__(self, method: str, url: str, status: int | None,
                 body: str) -> None:
        self.method = method
        self.url = url
        self.status = status
        self.body = body
        detail = f"HTTP {status}" if status is not None else "curl transport error"
        super().__init__(f"jira {method} {url} failed ({detail}): {body.strip()}")


class CurlResult:
    """The outcome of a `curl` call: the request, exit code, body, HTTP status.

    `status` is the HTTP status code parsed from curl's response (None when curl
    itself failed before a response, e.g. a TLS or DNS error).
    """

    def __init__(self, method: str, url: str, returncode: int, body: str,
                 status: int | None) -> None:
        self.method = method
        self.url = url
        self.returncode = returncode
        self.body = body
        self.status = status


# The sentinel curl writes after the body so the HTTP status can be split off
# the response without a second request. `-w` appends it; the body is everything
# before it.
_STATUS_MARKER = "\n__HTTP_STATUS__:"


def run_curl(method: str, url: str, config: str,
             payload: str | None = None) -> CurlResult:
    """Run one `curl` REST request, capturing the body and HTTP status.

    `config` is a curl config file (the `-K -` channel) carrying the credential
    and headers — it is fed on stdin so the api_token never appears in argv.
    `payload`, when given, is the JSON request body; it rides the same config
    (as a quoted `data = "…"` directive appended below) rather than a second
    stdin stream, since curl reads `-` once. So both the credential and the body
    travel the one out-of-band channel, and argv stays free of either.

    Returns a CurlResult; the helpers below decide whether to raise.
    """
    args = [
        "curl", "--silent", "--show-error",
        "--request", method,
        "--config", "-",
        "--write-out", _STATUS_MARKER + "%{http_code}",
        url,
    ]
    stdin = config if payload is None else config + "\n" + _data_lines(payload)
    result = subprocess.run(
        args, input=stdin, text=True, capture_output=True,
    )
    body, status = _split_status(result.stdout)
    return CurlResult(method=method, url=url, returncode=result.returncode,
                      body=body, status=status)


def _data_lines(payload: str) -> str:
    """A curl config `data` directive carrying the JSON request body.

    The body is quoted as a single config-file value; embedded quotes and
    backslashes are escaped so the JSON survives curl's config parser intact.
    """
    escaped = payload.replace("\\", "\\\\").replace('"', '\\"')
    return f'data = "{escaped}"'


def _split_status(stdout: str) -> tuple[str, int | None]:
    """Split curl's stdout into the response body and the trailing HTTP status."""
    marker_idx = stdout.rfind(_STATUS_MARKER)
    if marker_idx < 0:
        return stdout, None
    body = stdout[:marker_idx]
    tail = stdout[marker_idx + len(_STATUS_MARKER):].strip()
    return body, int(tail) if tail.isdigit() else None


def auth_config(email: str, api_token: str,
                headers: Mapping[str, str] | None = None) -> str:
    """Build the `curl -K -` config carrying Basic auth and JSON headers.

    The email and api_token form the Basic credential; it is base64-encoded into
    an explicit `Authorization` header rather than passed via `--user` so the
    secret never lands on a command line even inside the config-file channel's
    own argv. Returns the config text fed to `run_curl` on stdin.
    """
    raw = f"{email}:{api_token}".encode()
    token = base64.b64encode(raw).decode()
    lines = [
        f'header = "Authorization: Basic {token}"',
        'header = "Content-Type: application/json"',
        'header = "Accept: application/json"',
    ]
    for name, value in (headers or {}).items():
        lines.append(f'header = "{name}: {value}"')
    return "\n".join(lines)


def request(method: str, url: str, config: str, payload: Any = None,
            runner: Runner | None = None) -> CurlResult:
    """Run a Jira REST request, raising JiraError on a transport or HTTP failure.

    `payload`, when given, is serialised to JSON for the request body. Returns
    the CurlResult on a 2xx; a curl error or a non-2xx status raises JiraError
    carrying the status and body.
    """
    runner = runner or run_curl
    body = json.dumps(payload) if payload is not None else None
    result = runner(method, url, config, body)
    if result.returncode != 0:
        raise JiraError(method, url, result.status, result.body)
    if result.status is None or not 200 <= result.status < 300:
        raise JiraError(method, url, result.status, result.body)
    return result


def request_json(method: str, url: str, config: str, payload: Any = None,
                 runner: Runner | None = None, default: Any = None) -> Any:
    """Run a Jira REST request and parse the response body as JSON.

    Empty body yields `default` (a 204 No Content on a successful transition has
    no body), so a caller distinguishes "no data" from a parse it branches on.
    """
    result = request(method, url, config, payload=payload, runner=runner)
    text = result.body.strip()
    if not text:
        return default
    return json.loads(text)
