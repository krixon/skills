"""Tests for the Jira tracker backend and its curl REST seam (#232).

Every test drives the backend through a scripted curl runner — a stand-in for
run_curl that returns a canned CurlResult per call and records the request
(method, URL, config, payload) — so the unit covers the REST request built and
the contract envelope returned, never the network. The two acceptance criteria
(issue view two-zone envelope; all-REST close that sets `resolution` only when
the transition requires it) get dedicated cases, alongside the credential-out-of-
argv discipline and the Jira-side preflight requiring curl.
"""

from __future__ import annotations

import base64
import io
import json
import unittest
from typing import Any, Sequence

from adapter import enums, jiracmd, tracker
from adapter.jiracmd import CurlResult


class ScriptedCurl:
    """A run_curl stand-in: returns queued results in order, records each call.

    Each queued entry is (body, status, returncode); a bare string is a 200 with
    that body. Calls beyond the script reuse the last entry.
    """

    def __init__(self, script: Sequence[Any]) -> None:
        self._script = [self._norm(s) for s in script]
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _norm(entry: Any) -> tuple[str, int | None, int]:
        if isinstance(entry, tuple):
            body = entry[0]
            status = entry[1] if len(entry) > 1 else 200
            rc = entry[2] if len(entry) > 2 else 0
            return (body, status, rc)
        return (entry, 200, 0)

    def __call__(self, method: str, url: str, config: str,
                 payload: str | None = None) -> CurlResult:
        self.calls.append({"method": method, "url": url, "config": config,
                           "payload": payload})
        idx = min(len(self.calls) - 1, len(self._script) - 1)
        body, status, rc = self._script[idx]
        return CurlResult(method=method, url=url, returncode=rc, body=body,
                          status=status)


def _backend(runner: Any, env: dict[str, str] | None = None) -> tracker.JiraBackend:
    base = {
        "JIRA_BASE_URL": "https://acme.atlassian.net",
        "JIRA_EMAIL": "agent@acme.io",
        "JIRA_API_TOKEN": "s3cr3t-token",
    }
    if env:
        base.update(env)
    return tracker.JiraBackend(config=base, runner=runner)


# --- AC1: issue view returns the two-zone envelope --------------------------

class TestJiraIssueView(unittest.TestCase):
    def test_view_projects_into_two_zone_contract_envelope(self) -> None:
        native = json.dumps({
            "key": "ORPL-123",
            "self": "https://acme.atlassian.net/rest/api/3/issue/10042",
            "fields": {
                "summary": "The thing is broken",
                "status": {"name": "In Progress",
                           "statusCategory": {"key": "indeterminate"}},
                "labels": ["bug", "p1"],
            },
        })
        be = _backend(ScriptedCurl([native]))
        result = be.issue_view("ORPL-123")
        # Neutral fields at the top level — the opaque key is the id, state goes
        # through the statusCategory mapper, title is the summary.
        self.assertEqual(result["id"], "ORPL-123")
        self.assertEqual(result["state"], "open")
        self.assertEqual(result["title"], "The thing is broken")
        self.assertEqual(result["labels"], ["bug", "p1"])
        # AC#1: the Jira key and the issue url ride the info sidecar. The url is
        # Jira's REST `self` link (keyed on the internal id, not the key).
        self.assertEqual(result["info"]["key"], "ORPL-123")
        self.assertEqual(result["info"]["url"],
                         "https://acme.atlassian.net/rest/api/3/issue/10042")
        self.assertNotIn("key", result)
        self.assertNotIn("url", result)

    def test_view_done_category_maps_to_closed(self) -> None:
        native = json.dumps({
            "key": "ORPL-9", "self": "https://acme.atlassian.net/x",
            "fields": {"summary": "s", "labels": [],
                       "status": {"statusCategory": {"key": "done"}}},
        })
        be = _backend(ScriptedCurl([native]))
        self.assertEqual(be.issue_view("ORPL-9")["state"], "closed")

    def test_view_unknown_status_category_raises(self) -> None:
        native = json.dumps({
            "key": "ORPL-9", "self": "x",
            "fields": {"summary": "s", "labels": [],
                       "status": {"statusCategory": {"key": "weird"}}},
        })
        be = _backend(ScriptedCurl([native]))
        with self.assertRaises(enums.UnmappedValue):
            be.issue_view("ORPL-9")

    def test_view_issues_a_get_to_the_issue_endpoint(self) -> None:
        native = json.dumps({
            "key": "ORPL-1", "self": "x",
            "fields": {"summary": "s", "labels": [],
                       "status": {"statusCategory": {"key": "new"}}},
        })
        runner = ScriptedCurl([native])
        _backend(runner).issue_view("ORPL-1")
        call = runner.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertIn("/rest/api/3/issue/ORPL-1", call["url"])


# --- credential discipline: token never in argv -----------------------------

class TestCredentialOutOfArgv(unittest.TestCase):
    def test_token_rides_the_config_not_argv(self) -> None:
        native = json.dumps({
            "key": "ORPL-1", "self": "x",
            "fields": {"summary": "s", "labels": [],
                       "status": {"statusCategory": {"key": "new"}}},
        })
        runner = ScriptedCurl([native])
        _backend(runner).issue_view("ORPL-1")
        call = runner.calls[0]
        # The raw api_token never appears in the URL (argv); it rides the config
        # as a base64 Basic credential fed to curl on stdin.
        self.assertNotIn("s3cr3t-token", call["url"])
        expected = base64.b64encode(b"agent@acme.io:s3cr3t-token").decode()
        self.assertIn(expected, call["config"])

    def test_run_curl_keeps_credential_off_argv(self) -> None:
        # run_curl builds argv with the URL and flags only — the config (carrying
        # the credential) is delivered via -K - on stdin, never as an argument.
        captured: dict[str, Any] = {}

        import adapter.jiracmd as jc

        class FakeCompleted:
            returncode = 0
            stdout = "{}" + jc._STATUS_MARKER + "200"
            stderr = ""

        def fake_run(args, **kw):
            captured["args"] = args
            captured["input"] = kw.get("input")
            return FakeCompleted()

        orig = jc.subprocess.run
        jc.subprocess.run = fake_run
        try:
            jc.run_curl("GET", "https://acme.atlassian.net/x",
                        'header = "Authorization: Basic ZZZ"')
        finally:
            jc.subprocess.run = orig
        self.assertNotIn("ZZZ", " ".join(captured["args"]))
        # The config is delivered via the -K/--config stdin channel, never argv.
        self.assertIn("--config", captured["args"])
        self.assertIn("-", captured["args"])
        self.assertIn("ZZZ", captured["input"])


# --- AC2: all-REST close, resolution only when required ----------------------

class TestJiraClose(unittest.TestCase):
    @staticmethod
    def _transitions(*, require_resolution: bool) -> str:
        # The GET /transitions payload: one transition into the done category.
        fields: dict[str, Any] = {}
        if require_resolution:
            fields["resolution"] = {"required": True, "name": "Resolution"}
        return json.dumps({"transitions": [
            {"id": "11", "name": "Start", "to": {
                "statusCategory": {"key": "indeterminate"}}},
            {"id": "31", "name": "Done", "to": {
                "statusCategory": {"key": "done"}}, "fields": fields},
        ]})

    def test_close_posts_transition_without_resolution_when_not_required(self) -> None:
        runner = ScriptedCurl([
            self._transitions(require_resolution=False),  # GET /transitions
            ("", 204),                                    # POST transition (204)
        ])
        be = _backend(runner)
        result = be.issue_close("ORPL-123")
        # The contract act envelope: a coded ok, the neutral closed state.
        self.assertEqual(result["outcome"], "ok")
        self.assertEqual(result["id"], "ORPL-123")
        self.assertEqual(result["state"], "closed")
        # Two REST calls: GET transitions, then POST the done-category transition.
        self.assertEqual(len(runner.calls), 2)
        get, post = runner.calls
        self.assertEqual(get["method"], "GET")
        self.assertIn("/rest/api/3/issue/ORPL-123/transitions", get["url"])
        self.assertEqual(post["method"], "POST")
        self.assertIn("/rest/api/3/issue/ORPL-123/transitions", post["url"])
        payload = json.loads(post["payload"])
        # It picked the done-category transition (id 31), not the indeterminate one.
        self.assertEqual(payload["transition"]["id"], "31")
        # No resolution field when the transition does not require it.
        self.assertNotIn("fields", payload)

    def test_close_sets_resolution_only_when_transition_requires_it(self) -> None:
        runner = ScriptedCurl([
            self._transitions(require_resolution=True),
            ("", 204),
        ])
        be = _backend(runner)
        result = be.issue_close("ORPL-123")
        self.assertEqual(result["outcome"], "ok")
        post = runner.calls[1]
        payload = json.loads(post["payload"])
        self.assertEqual(payload["transition"]["id"], "31")
        # The resolution field is set, defaulting to "Done".
        self.assertEqual(payload["fields"]["resolution"]["name"], "Done")

    def test_close_uses_configured_done_resolution_name(self) -> None:
        runner = ScriptedCurl([
            self._transitions(require_resolution=True),
            ("", 204),
        ])
        be = _backend(runner, env={"JIRA_DONE_RESOLUTION": "Fixed"})
        be.issue_close("ORPL-123")
        payload = json.loads(runner.calls[1]["payload"])
        self.assertEqual(payload["fields"]["resolution"]["name"], "Fixed")

    def test_close_raises_when_no_done_category_transition(self) -> None:
        # No transition reaches the done category — the close cannot resolve a
        # target, so it surfaces a clear error rather than picking a wrong one.
        no_done = json.dumps({"transitions": [
            {"id": "11", "name": "Reopen",
             "to": {"statusCategory": {"key": "new"}}},
        ]})
        runner = ScriptedCurl([no_done])
        be = _backend(runner)
        with self.assertRaises(ValueError):
            be.issue_close("ORPL-123")
        # It never POSTed a transition.
        self.assertEqual(len(runner.calls), 1)


# --- the curl REST seam helpers ---------------------------------------------

class TestCurlSeam(unittest.TestCase):
    def test_request_json_parses_2xx_body(self) -> None:
        runner = ScriptedCurl([(json.dumps({"ok": True}), 200)])
        out = jiracmd.request_json("GET", "https://x/y", "cfg", runner=runner)
        self.assertEqual(out, {"ok": True})

    def test_request_json_empty_204_yields_default(self) -> None:
        runner = ScriptedCurl([("", 204)])
        out = jiracmd.request_json("POST", "https://x/y", "cfg", payload={"a": 1},
                                   runner=runner, default=None)
        self.assertIsNone(out)
        # The payload was serialised to JSON for the body.
        self.assertEqual(json.loads(runner.calls[0]["payload"]), {"a": 1})

    def test_request_raises_on_non_2xx(self) -> None:
        runner = ScriptedCurl([("forbidden", 403)])
        with self.assertRaises(jiracmd.JiraError) as ctx:
            jiracmd.request("GET", "https://x/y", "cfg", runner=runner)
        self.assertEqual(ctx.exception.status, 403)

    def test_request_raises_on_curl_transport_error(self) -> None:
        # A non-zero curl exit (TLS/DNS) with no HTTP status still raises.
        runner = ScriptedCurl([("", None, 35)])
        with self.assertRaises(jiracmd.JiraError) as ctx:
            jiracmd.request("GET", "https://x/y", "cfg", runner=runner)
        self.assertIsNone(ctx.exception.status)


# --- dispatch + preflight ----------------------------------------------------

class TestJiraDispatch(unittest.TestCase):
    def _env(self) -> dict[str, str]:
        return {
            "ISSUE_TRACKER": "jira",
            "JIRA_BASE_URL": "https://acme.atlassian.net",
            "JIRA_EMAIL": "agent@acme.io",
            "JIRA_API_TOKEN": "tok",
        }

    def test_issue_view_dispatches_to_jira_backend(self) -> None:
        native = json.dumps({
            "key": "ORPL-7", "self": "https://acme.atlassian.net/x",
            "fields": {"summary": "s", "labels": [],
                       "status": {"statusCategory": {"key": "new"}}},
        })
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--id", "ORPL-7"],
            env=self._env(), jira_runner=ScriptedCurl([native]), stream=out,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["id"], "ORPL-7")
        self.assertEqual(payload["info"]["key"], "ORPL-7")

    def test_issue_close_dispatches_through_rest_seam(self) -> None:
        transitions = json.dumps({"transitions": [
            {"id": "31", "to": {"statusCategory": {"key": "done"}}, "fields": {}},
        ]})
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "close", "--id", "ORPL-7"],
            env=self._env(),
            jira_runner=ScriptedCurl([transitions, ("", 204)]), stream=out,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["outcome"], "ok")
        self.assertEqual(payload["state"], "closed")


class TestJiraPreflight(unittest.TestCase):
    def test_jira_tracker_requires_curl(self) -> None:
        # AC#4: the Jira backend's required-tools set names curl.
        self.assertIn("curl", tracker.required_tools("jira"))

    def test_github_tracker_does_not_require_curl(self) -> None:
        self.assertNotIn("curl", tracker.required_tools("github"))


if __name__ == "__main__":
    unittest.main()
