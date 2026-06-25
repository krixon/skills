"""Tests for the tracker command group's Jira backend.

Symmetric with test_tracker.py: every test drives the backend through a scripted
acli runner seam — a run_acli stand-in that pops a canned AcliResult per call and
records argv — so the unit covers the command built and the logic applied, never
the network. The named acceptance criteria get dedicated cases: statusCategory.key
resolution (the already-done no-op), the all-REST close path through the curl
seam (transitions GET, done-category pick, resolution-only-when-required POST),
the two-zone issue_view envelope, and the concept→primitive map. The close path
drives an injected curl runner (a run_curl stand-in recording method/URL/payload)
so its REST requests are asserted offline, with the api_token never in argv.
"""

from __future__ import annotations

import base64
import io
import json
import unittest
from typing import Any, Sequence

from adapter import aclicmd, cli, jira, jiracmd, tracker
from adapter.jiracmd import CurlResult


class ScriptedRunner:
    """A run_acli stand-in: returns queued results in order, records each call.

    Each queued entry is (stdout, returncode, stderr). Calls beyond the script
    reuse the last entry.
    """

    def __init__(self, script: Sequence[Any]) -> None:
        self._script = [self._norm(s) for s in script]
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _norm(entry: Any) -> tuple[str, int, str]:
        if isinstance(entry, tuple):
            stdout = entry[0]
            rc = entry[1] if len(entry) > 1 else 0
            stderr = entry[2] if len(entry) > 2 else ""
            return (stdout, rc, stderr)
        return (entry, 0, "")

    def __call__(self, args: Sequence[str], env: dict[str, str] | None = None,
                 input: str | None = None, check: bool = True) -> aclicmd.AcliResult:
        self.calls.append({"args": list(args), "env": env, "input": input})
        idx = min(len(self.calls) - 1, len(self._script) - 1)
        stdout, rc, stderr = self._script[idx]
        return aclicmd.AcliResult(args=list(args), returncode=rc, stdout=stdout,
                                  stderr=stderr)

    def argv(self, i: int = 0) -> list[str]:
        return self.calls[i]["args"]


class ScriptedCurl:
    """A run_curl stand-in: returns queued results in order, records each call.

    Each queued entry is (body, status, returncode); a bare string is a 200 with
    that body. Calls beyond the script reuse the last entry. Records the request
    (method, URL, config, payload) so a test asserts the REST request built and
    the credential's place in the config — never argv — offline.
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


def _cred() -> aclicmd.JiraCredential:
    return aclicmd.JiraCredential(site="https://acme.atlassian.net",
                                  email="bot@acme.io", token_cmd="printf tok")


def _backend(runner: Any, project: str = "PROJ",
             curl_runner: Any = None,
             token_evaluator: Any = None) -> jira.JiraBackend:
    return jira.JiraBackend(credential=_cred(), project=project, runner=runner,
                            curl_runner=curl_runner,
                            token_evaluator=token_evaluator or (lambda cmd: "tok"))


# --- concept -> Jira primitive mapping (named criterion) --------------------

class TestConceptMapping(unittest.TestCase):
    def test_category_labels_map_to_issue_types(self) -> None:
        self.assertEqual(jira.issue_type_for("bug"), "Bug")
        self.assertEqual(jira.issue_type_for("enhancement"), "Story")

    def test_structure_label_epic_maps_to_epic_issue_type(self) -> None:
        self.assertEqual(jira.issue_type_for("epic"), "Epic")

    def test_triage_states_map_to_jira_labels(self) -> None:
        # Triage/workflow state labels carry across as Jira labels verbatim —
        # they are the workflow's own state machine, not Jira primitives.
        for label in ("needs-triage", "ready-for-agent", "in-progress",
                      "wontfix"):
            self.assertEqual(jira.label_for(label), label)

    def test_unknown_category_has_no_issue_type(self) -> None:
        self.assertIsNone(jira.issue_type_for("not-a-category"))


# --- status reads resolve by statusCategory.key (named criterion) -----------

class TestStatusCategoryRead(unittest.TestCase):
    @staticmethod
    def _view(category: str, name: str = "Whatever") -> str:
        return json.dumps({"fields": {"status": {
            "name": name, "statusCategory": {"key": category}}}})

    def test_reads_category_key_via_view_all_fields(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        be = _backend(runner)
        self.assertEqual(be.status_category("PROJ-7"), "indeterminate")
        argv = runner.argv(0)
        # It views the work item in JSON with all fields — the path to the
        # statusCategory.key lives under .fields.status.
        self.assertEqual(argv[:3], ["jira", "workitem", "view"])
        self.assertIn("PROJ-7", argv)
        self.assertIn("--json", argv)
        self.assertIn("--fields", argv)
        self.assertIn("*all", argv)

    def test_resolves_by_category_not_status_name(self) -> None:
        # A project may rename "In Progress" to anything; the read keys on the
        # platform-stable category, so an arbitrary name still reads correctly.
        runner = ScriptedRunner([(self._view("done", name="Shipped 🚢"),)])
        be = _backend(runner)
        self.assertEqual(be.status_category("PROJ-7"), "done")

    def test_already_done_noop_check_resolves_by_category(self) -> None:
        runner = ScriptedRunner([(self._view("done"),)])
        be = _backend(runner)
        self.assertTrue(be.is_done("PROJ-7"))

    def test_not_done_when_category_is_indeterminate(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        be = _backend(runner)
        self.assertFalse(be.is_done("PROJ-7"))


# --- AC2/AC3: the all-REST curl close path ----------------------------------

class TestRestClose(unittest.TestCase):
    """The close path is all-REST through the curl seam (AC2/AC3).

    The is_done short-circuit reads the status category through acli (the runner)
    as before; the transition itself is GET /transitions then POST /transitions
    through the injected curl runner — the urllib /transitions GET and the
    `acli ... transition --status` write are both gone.
    """

    @staticmethod
    def _view(category: str) -> str:
        return json.dumps({"fields": {"status": {
            "name": "x", "statusCategory": {"key": category}}}})

    @staticmethod
    def _transitions(*, require_resolution: bool,
                     done_id: str = "31") -> str:
        # The GET /transitions payload: an indeterminate transition and the
        # done-category one, keyed by the platform-stable to.statusCategory.key.
        fields: dict[str, Any] = {}
        if require_resolution:
            fields["resolution"] = {"required": True, "name": "Resolution"}
        return json.dumps({"transitions": [
            {"id": "11", "name": "Start",
             "to": {"statusCategory": {"key": "indeterminate"}}},
            {"id": done_id, "name": "Ship It",
             "to": {"statusCategory": {"key": "done"}}, "fields": fields},
        ]})

    def test_close_gets_then_posts_the_done_transition_all_rest(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])  # is_done check
        curl = ScriptedCurl([
            self._transitions(require_resolution=False),  # GET /transitions
            ("", 204),                                    # POST transition (204)
        ])
        be = _backend(runner, curl_runner=curl)
        result = be.issue_close("PROJ-7")
        self.assertEqual(result["outcome"], "ok")
        self.assertEqual(result["state"], "closed")
        # Exactly two REST calls: GET transitions, POST the done transition.
        self.assertEqual(len(curl.calls), 2)
        get, post = curl.calls
        self.assertEqual(get["method"], "GET")
        self.assertIn("/rest/api/3/issue/PROJ-7/transitions", get["url"])
        self.assertEqual(post["method"], "POST")
        self.assertIn("/rest/api/3/issue/PROJ-7/transitions", post["url"])
        payload = json.loads(post["payload"])
        # It picked the done-category transition by its id (31), not the
        # indeterminate one — resolved by category at call time, never hard-coded.
        self.assertEqual(payload["transition"]["id"], "31")
        # No resolution field when the transition does not require one.
        self.assertNotIn("fields", payload)

    def test_close_sets_resolution_only_when_transition_requires_it(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        curl = ScriptedCurl([
            self._transitions(require_resolution=True),
            ("", 204),
        ])
        be = _backend(runner, curl_runner=curl)
        be.issue_close("PROJ-7")
        payload = json.loads(curl.calls[1]["payload"])
        self.assertEqual(payload["transition"]["id"], "31")
        # The resolution field is attached, defaulting to "Done".
        self.assertEqual(payload["fields"]["resolution"]["name"], "Done")

    def test_close_uses_configured_done_resolution_name(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        curl = ScriptedCurl([
            self._transitions(require_resolution=True),
            ("", 204),
        ])
        be = jira.JiraBackend(credential=_cred(), project="PROJ", runner=runner,
                              curl_runner=curl,
                              token_evaluator=lambda cmd: "tok",
                              done_resolution="Fixed")
        be.issue_close("PROJ-7")
        payload = json.loads(curl.calls[1]["payload"])
        self.assertEqual(payload["fields"]["resolution"]["name"], "Fixed")

    def test_rename_does_not_break_the_binding(self) -> None:
        # The done transition resolves by category, so a renamed done status
        # (any id) is still found with no code change.
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        curl = ScriptedCurl([
            self._transitions(require_resolution=False, done_id="99"),
            ("", 204),
        ])
        be = _backend(runner, curl_runner=curl)
        be.issue_close("PROJ-7")
        self.assertEqual(json.loads(curl.calls[1]["payload"])["transition"]["id"],
                         "99")

    def test_already_done_is_a_noop_no_rest_call(self) -> None:
        runner = ScriptedRunner([(self._view("done"),)])
        curl = ScriptedCurl([self._transitions(require_resolution=False)])
        be = _backend(runner, curl_runner=curl)
        result = be.issue_close("PROJ-7")
        # An already-done issue is still reported closed; the noop flag rides info.
        self.assertEqual(result["state"], "closed")
        self.assertTrue(result["info"]["noop"])
        # Only the is_done read ran — no transitions GET or POST.
        self.assertEqual(len(curl.calls), 0)

    def test_no_done_transition_raises(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        no_done = json.dumps({"transitions": [
            {"id": "11", "name": "Reopen",
             "to": {"statusCategory": {"key": "new"}}}]})
        curl = ScriptedCurl([no_done])
        be = _backend(runner, curl_runner=curl)
        with self.assertRaises(jira.NoSuchTransition):
            be.issue_close("PROJ-7")
        # It GETs the transitions but never POSTs.
        self.assertEqual(len(curl.calls), 1)

    def test_token_rides_the_config_not_argv(self) -> None:
        # The api_token (evaluated from the credential command) rides the curl
        # config as a base64 Basic credential, never the URL (argv).
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        curl = ScriptedCurl([self._transitions(require_resolution=False),
                             ("", 204)])
        be = _backend(runner, curl_runner=curl,
                      token_evaluator=lambda cmd: "s3cr3t")
        be.issue_close("PROJ-7")
        for call in curl.calls:
            self.assertNotIn("s3cr3t", call["url"])
        expected = base64.b64encode(b"bot@acme.io:s3cr3t").decode()
        self.assertIn(expected, curl.calls[0]["config"])


# --- AC1/2/3: backend-mandated required fields on create (#233) -------------

class TestRequiredFieldsConfig(unittest.TestCase):
    """The operator config naming required-field identities per issue type and
    the deployment-wide fixed values, read from the environment."""

    def test_required_fields_parses_per_type_mapping(self) -> None:
        env = {"JIRA_REQUIRED_FIELDS":
               '{"Epic": ["customfield_10100"], "Bug": ["customfield_10200"]}'}
        rf = jira.JiraBackend.required_fields_from(env)
        self.assertEqual(rf["Epic"], ["customfield_10100"])
        self.assertEqual(rf["Bug"], ["customfield_10200"])

    def test_required_fields_absent_is_empty(self) -> None:
        self.assertEqual(jira.JiraBackend.required_fields_from({}), {})

    def test_field_values_parses_fixed_value_mapping(self) -> None:
        env = {"JIRA_FIELD_VALUES": '{"customfield_10100": "Run the Business"}'}
        fv = jira.JiraBackend.field_values_from(env)
        self.assertEqual(fv["customfield_10100"], "Run the Business")

    def test_field_values_absent_is_empty(self) -> None:
        self.assertEqual(jira.JiraBackend.field_values_from({}), {})


def _create_backend(runner: Any, *, curl: Any = None,
                    required_fields: Any = None,
                    field_values: Any = None) -> jira.JiraBackend:
    return jira.JiraBackend(
        credential=_cred(), project="PROJ", runner=runner, curl_runner=curl,
        token_evaluator=lambda cmd: "tok",
        required_fields=required_fields or {},
        field_values=field_values or {})


class TestRequiredFieldCreate(unittest.TestCase):
    """The three-class handling of backend-mandated non-neutral create fields.

    A type with no mandated field creates through the unchanged acli path; a
    type with one drives the REST create over the curl seam so the field rides
    the create. Fixed values come from config; a decided value with no `--set`
    halts with `needs_decision` (allowed values discovered over REST); a `--set`
    value is forwarded verbatim.
    """

    @staticmethod
    def _createmeta(field_id: str, *, allowed: list[str]) -> str:
        # GET createmeta payload: the mandated field with its allowedValues,
        # shaped as the Jira createmeta REST endpoint returns them.
        return json.dumps({"fields": [
            {"fieldId": field_id, "name": "Investment Category",
             "required": True,
             "allowedValues": [{"value": v} for v in allowed]}]})

    # AC1 -- a mandated fixed-value field is set from config on create.
    def test_fixed_value_field_set_from_config(self) -> None:
        curl = ScriptedCurl([(json.dumps({"key": "PROJ-9"}), 201)])  # POST create
        be = _create_backend(ScriptedRunner(["{}"]), curl=curl,
                             required_fields={"Epic": ["customfield_10100"]},
                             field_values={"customfield_10100": "Run"})
        out = be.issue_create(title="an epic", body="b", category="epic")
        self.assertEqual(out["outcome"], "ok")
        self.assertEqual(out["key"], "PROJ-9")
        # One REST POST to the create endpoint, carrying the fixed field value.
        self.assertEqual(len(curl.calls), 1)
        post = curl.calls[0]
        self.assertEqual(post["method"], "POST")
        self.assertIn("/rest/api/3/issue", post["url"])
        payload = json.loads(post["payload"])
        self.assertEqual(payload["fields"]["customfield_10100"], "Run")
        # The neutral fields ride the same REST payload — type, project, summary.
        self.assertEqual(payload["fields"]["issuetype"]["name"], "Epic")
        self.assertEqual(payload["fields"]["project"]["key"], "PROJ")
        self.assertEqual(payload["fields"]["summary"], "an epic")

    # AC2 -- a mandated decided-value field with no --set halts needs_decision.
    def test_decided_field_without_set_halts_needs_decision(self) -> None:
        # GET createmeta (discovery) only; no POST — the create never fires.
        curl = ScriptedCurl([
            self._createmeta("customfield_10100", allowed=["Run", "Grow"])])
        be = _create_backend(ScriptedRunner(["{}"]), curl=curl,
                             required_fields={"Epic": ["customfield_10100"]})
        out = be.issue_create(title="an epic", body="b", category="epic")
        self.assertEqual(out["outcome"], "needs_decision")
        # The field identity, discovered allowed values, and a prompt ride info.
        info = out["info"]
        self.assertEqual(info["field"], "customfield_10100")
        self.assertEqual(info["allowed_values"], ["Run", "Grow"])
        self.assertIn("message", out)
        # Discovery GET ran; the create POST never did.
        self.assertEqual(len(curl.calls), 1)
        self.assertEqual(curl.calls[0]["method"], "GET")

    def test_discovery_url_percent_encodes_a_multiword_issue_type(self) -> None:
        # A mandated decided field on a space-bearing type ("User Story") must
        # still build a well-formed createmeta URL — the space is encoded, never
        # left raw on curl's argv.
        curl = ScriptedCurl([
            self._createmeta("customfield_10100", allowed=["Run"])])
        be = _create_backend(ScriptedRunner(["{}"]), curl=curl,
                             required_fields={"User Story": ["customfield_10100"]})
        be.issue_create(title="t", body="b", category="User Story")
        url = curl.calls[0]["url"]
        self.assertNotIn("User Story", url)
        self.assertIn("issuetypeNames=User+Story", url)

    def test_needs_decision_never_invents_a_value(self) -> None:
        # No POST means no create with a guessed value — the halt is terminal.
        curl = ScriptedCurl([
            self._createmeta("customfield_10100", allowed=["Run", "Grow"])])
        be = _create_backend(ScriptedRunner(["{}"]), curl=curl,
                             required_fields={"Epic": ["customfield_10100"]})
        be.issue_create(title="t", body="b", category="epic")
        self.assertTrue(all(c["method"] != "POST" for c in curl.calls))

    # AC3 -- re-invoking with --set forwards the chosen value verbatim.
    def test_set_value_forwarded_verbatim_on_create(self) -> None:
        curl = ScriptedCurl([(json.dumps({"key": "PROJ-9"}), 201)])
        be = _create_backend(ScriptedRunner(["{}"]), curl=curl,
                             required_fields={"Epic": ["customfield_10100"]})
        out = be.issue_create(title="t", body="b", category="epic",
                              set_fields={"customfield_10100": "Grow"})
        self.assertEqual(out["outcome"], "ok")
        payload = json.loads(curl.calls[0]["payload"])
        # The supplied value rides the create verbatim — no discovery GET fired.
        self.assertEqual(payload["fields"]["customfield_10100"], "Grow")
        self.assertTrue(all(c["method"] != "GET" for c in curl.calls))

    def test_set_overrides_a_configured_fixed_value(self) -> None:
        curl = ScriptedCurl([(json.dumps({"key": "PROJ-9"}), 201)])
        be = _create_backend(ScriptedRunner(["{}"]), curl=curl,
                             required_fields={"Epic": ["customfield_10100"]},
                             field_values={"customfield_10100": "Run"})
        be.issue_create(title="t", body="b", category="epic",
                        set_fields={"customfield_10100": "Grow"})
        payload = json.loads(curl.calls[0]["payload"])
        self.assertEqual(payload["fields"]["customfield_10100"], "Grow")

    def test_no_mandated_field_uses_unchanged_acli_create(self) -> None:
        # A type with no configured required field takes the acli create path —
        # no REST POST, the body still rides a temp file path.
        runner = ScriptedRunner([(json.dumps({"key": "PROJ-9"}),)])
        curl = ScriptedCurl([("", 200)])
        be = _create_backend(runner, curl=curl)
        out = be.issue_create(title="t", body="b", category="enhancement")
        self.assertEqual(out["key"], "PROJ-9")
        self.assertEqual(len(curl.calls), 0)
        self.assertEqual(runner.argv(0)[:3], ["jira", "workitem", "create"])

    def test_rest_create_keeps_body_and_token_off_argv(self) -> None:
        # The description rides the REST JSON payload (the stdin config channel),
        # and the token rides the curl config — neither lands on argv.
        curl = ScriptedCurl([(json.dumps({"key": "PROJ-9"}), 201)])
        be = jira.JiraBackend(
            credential=_cred(), project="PROJ", runner=ScriptedRunner(["{}"]),
            curl_runner=curl, token_evaluator=lambda cmd: "s3cr3t",
            required_fields={"Epic": ["customfield_10100"]},
            field_values={"customfield_10100": "Run"})
        be.issue_create(title="t", body="secret body", category="epic")
        post = curl.calls[0]
        self.assertNotIn("s3cr3t", post["url"])
        expected = base64.b64encode(b"bot@acme.io:s3cr3t").decode()
        self.assertIn(expected, post["config"])
        # The body is in the payload, not the URL.
        self.assertNotIn("secret body", post["url"])
        self.assertEqual(json.loads(post["payload"])["fields"]["description"],
                         "secret body")


# --- issue concept methods (the dispatched surface) -------------------------

class TestIssueConcepts(unittest.TestCase):
    def test_issue_view_projects_two_zone_contract_envelope(self) -> None:
        # AC1: the neutral state resolves from statusCategory, the key/url ride
        # info, and the read still goes through acli's all-fields view.
        payload = json.dumps({"key": "PROJ-7", "url": "https://acme/browse/PROJ-7",
                              "fields": {
            "summary": "t", "labels": ["bug"],
            "status": {"name": "In Progress",
                       "statusCategory": {"key": "indeterminate"}}}})
        runner = ScriptedRunner([(payload,)])
        be = _backend(runner)
        out = be.issue_view("PROJ-7")
        # Neutral fields at the top level; the opaque key is the id.
        self.assertEqual(out["id"], "PROJ-7")
        self.assertEqual(out["state"], "open")
        self.assertEqual(out["title"], "t")
        self.assertEqual(out["labels"], ["bug"])
        # The Jira key and url ride the info sidecar, not the top level.
        self.assertEqual(out["info"]["key"], "PROJ-7")
        self.assertEqual(out["info"]["url"], "https://acme/browse/PROJ-7")
        self.assertNotIn("key", out)
        self.assertNotIn("url", out)
        argv = runner.argv(0)
        self.assertEqual(argv[:3], ["jira", "workitem", "view"])
        self.assertIn("--json", argv)

    def test_issue_view_done_category_maps_to_closed(self) -> None:
        payload = json.dumps({"key": "PROJ-9", "fields": {
            "summary": "s", "labels": [],
            "status": {"statusCategory": {"key": "done"}}}})
        be = _backend(ScriptedRunner([(payload,)]))
        self.assertEqual(be.issue_view("PROJ-9")["state"], "closed")

    def test_issue_list_searches_open_and_maps_neutral_rows(self) -> None:
        # The summary read: an acli JQL search scoped to the project and the
        # open (not-Done) category, each hit projected through the same neutral
        # mapping issue_view uses.
        rows = json.dumps([
            {"key": "PROJ-7", "fields": {
                "summary": "first", "labels": ["needs-triage"],
                "status": {"statusCategory": {"key": "new"}}}},
            {"key": "PROJ-9", "fields": {
                "summary": "second", "labels": [],
                "status": {"statusCategory": {"key": "indeterminate"}}}},
        ])
        runner = ScriptedRunner([(rows,)])
        be = _backend(runner)
        out = be.issue_list()
        self.assertEqual([r["id"] for r in out], ["PROJ-7", "PROJ-9"])
        self.assertEqual(out[0]["title"], "first")
        self.assertEqual(out[0]["state"], "open")
        self.assertEqual(out[0]["labels"], ["needs-triage"])
        self.assertEqual(out[0]["info"]["key"], "PROJ-7")
        # The lean summary stays neutral: no body/comments fetched.
        self.assertNotIn("body", out[0])
        # The argv is the search read, with the project- and state-scoped JQL.
        argv = runner.argv(0)
        self.assertEqual(argv[:3], ["jira", "workitem", "search"])
        jql = argv[argv.index("--jql") + 1]
        self.assertIn('project = "PROJ"', jql)
        self.assertIn("statusCategory != Done", jql)

    def test_issue_list_filters_by_label_and_closed_state(self) -> None:
        rows = json.dumps([
            {"key": "PROJ-3", "fields": {
                "summary": "done one", "labels": ["needs-triage"],
                "status": {"statusCategory": {"key": "done"}}}},
        ])
        runner = ScriptedRunner([(rows,)])
        be = _backend(runner)
        out = be.issue_list(label="needs-triage", state="closed")
        self.assertEqual(out[0]["state"], "closed")
        jql = runner.argv(0)[runner.argv(0).index("--jql") + 1]
        self.assertIn("statusCategory = Done", jql)
        self.assertIn('labels = "needs-triage"', jql)

    def test_issue_list_empty_search_yields_no_rows(self) -> None:
        # An empty stdout is the no-hits case (acli_json's default), not a crash.
        be = _backend(ScriptedRunner([("",)]))
        self.assertEqual(be.issue_list(), [])

    def test_issue_create_uses_issue_type_for_category_and_body_via_file(self) -> None:
        runner = ScriptedRunner([(json.dumps({"key": "PROJ-9"}),)])
        be = _backend(runner)
        out = be.issue_create(title="add widget", body="the body",
                              category="enhancement")
        self.assertEqual(out["key"], "PROJ-9")
        argv = runner.argv(0)
        self.assertEqual(argv[:3], ["jira", "workitem", "create"])
        # The category label resolved to the Jira issue type Story.
        self.assertIn("Story", argv)
        self.assertIn("PROJ", argv)
        # The untrusted body reached acli via a temp file path, never argv or
        # stdin (acli has no stdin `-` convention). Only the path rides argv.
        self.assertIn("--description-file", argv)
        self.assertIsNone(runner.calls[0]["input"])
        self.assertNotIn("the body", argv)

    def test_issue_create_writes_body_to_the_passed_file(self) -> None:
        # The out-of-band channel works end to end: the path acli is handed
        # holds the body while the call runs.
        seen = {}

        def reader(args, env=None, input=None, check=True):
            idx = args.index("--description-file")
            with open(args[idx + 1], encoding="utf-8") as fh:
                seen["body"] = fh.read()
            return aclicmd.AcliResult(args=list(args), returncode=0,
                                      stdout=json.dumps({"key": "PROJ-9"}),
                                      stderr="")

        be = _backend(reader)
        be.issue_create(title="t", body="line1\nline2", category="bug")
        self.assertEqual(seen["body"], "line1\nline2")

    def test_issue_comment_uses_create_subcommand_and_body_via_file(self) -> None:
        runner = ScriptedRunner([("{}",)])
        be = _backend(runner)
        be.issue_comment("PROJ-7", body="a comment")
        argv = runner.argv(0)
        # `comment` is a command group; the leaf is `comment create`, keyed by
        # --key. The body rides a temp file path, never argv or stdin.
        self.assertEqual(argv[:4], ["jira", "workitem", "comment", "create"])
        self.assertIn("--key", argv)
        self.assertIn("PROJ-7", argv)
        self.assertIn("--body-file", argv)
        self.assertIsNone(runner.calls[0]["input"])
        self.assertNotIn("a comment", argv)

    def test_issue_label_uses_key_labels_and_yes(self) -> None:
        runner = ScriptedRunner([("{}",)])
        be = _backend(runner)
        be.issue_label("PROJ-7", add=["in-progress", "ready-for-agent"],
                       remove=["needs-triage"])
        argv = runner.argv(0)
        self.assertEqual(argv[:3], ["jira", "workitem", "edit"])
        # acli edit: --key (not positional), comma-joined --labels /
        # --remove-labels, and --yes for the no-TTY non-interactive run.
        self.assertIn("--key", argv)
        self.assertIn("PROJ-7", argv)
        self.assertIn("--yes", argv)
        self.assertIn("--labels", argv)
        self.assertIn("in-progress,ready-for-agent", argv)
        self.assertIn("--remove-labels", argv)
        self.assertIn("needs-triage", argv)


# --- PR title embeds the key (the truth-of-record link) ---------------------

class TestPrTitle(unittest.TestCase):
    def test_key_embedded_in_conventional_commit_description(self) -> None:
        title = jira.pr_title("feat", "add the jira backend", "PROJ-7")
        # Key rides the Conventional-Commits description, branch is the link.
        self.assertTrue(title.startswith("feat: "))
        self.assertIn("PROJ-7", title)


# --- preflight required tools per backend -----------------------------------

class TestRequiredTools(unittest.TestCase):
    def test_github_requires_git_and_gh(self) -> None:
        self.assertEqual(tracker.required_tools({"ISSUE_TRACKER": "github"}),
                         ("git", "gh"))

    def test_jira_requires_git_acli_and_curl(self) -> None:
        # AC4: the all-REST close path shells out to curl, so the Jira preflight
        # names it alongside acli (still used for the reads) and git.
        tools = tracker.required_tools({"ISSUE_TRACKER": "jira"})
        self.assertEqual(set(tools), {"git", "acli", "curl"})

    def test_github_does_not_require_curl(self) -> None:
        self.assertNotIn("curl", tracker.required_tools({"ISSUE_TRACKER": "github"}))

    def test_default_is_github(self) -> None:
        self.assertEqual(tracker.required_tools({}), ("git", "gh"))


# --- dispatch: tracker run routes jira -> JiraBackend -----------------------

class TestJiraDispatch(unittest.TestCase):
    _ENV = {
        "ISSUE_TRACKER": "jira",
        "JIRA_SITE": "https://acme.atlassian.net",
        "JIRA_EMAIL": "bot@acme.io",
        "JIRA_API_TOKEN_CMD": "printf tok",
        "JIRA_PROJECT": "PROJ",
    }

    # acli's real auth-status report is plain text (no --json in acli 1.x).
    _AUTHED = "✓ Authenticated\n  Authentication Type: api_token\n"
    _NOT_AUTHED = "✗ Not authenticated\n"

    def test_jira_tracker_dispatches_to_jira_backend(self) -> None:
        # auth status (authenticated) then the issue view.
        view = json.dumps({"key": "PROJ-7", "fields": {
            "summary": "t", "status": {"statusCategory": {"key": "new"}}}})
        runner = ScriptedRunner([
            (self._AUTHED,),  # acli auth status
            (view,),          # workitem view
        ])
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--key", "PROJ-7"],
            env=self._ENV, runner=runner, stream=out,
        )
        self.assertEqual(rc, 0)
        # The two-zone envelope: the opaque key is the id, the key rides info.
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["id"], "PROJ-7")
        self.assertEqual(payload["info"]["key"], "PROJ-7")

    def test_create_halts_needs_decision_through_dispatch(self) -> None:
        # AC2/AC4: a mandated decided-value field with no --set halts at the
        # human gate — a non-zero exit carrying the needs_decision outcome and
        # the discovered allowed values, wired from JIRA_REQUIRED_FIELDS.
        meta = json.dumps({"fields": [
            {"fieldId": "customfield_10100", "name": "Investment Category",
             "required": True,
             "allowedValues": [{"value": "Run"}, {"value": "Grow"}]}]})
        runner = ScriptedRunner([(self._AUTHED,)])
        curl = ScriptedCurl([meta])
        env = dict(self._ENV,
                   JIRA_REQUIRED_FIELDS='{"Epic": ["customfield_10100"]}')
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "create", "--title", "an epic", "--category", "epic"],
            env=env, runner=runner, jira_curl_runner=curl, stream=out,
            stdin_body="the brief",
        )
        self.assertEqual(rc, cli.HALT_EXIT)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["outcome"], "needs_decision")
        self.assertEqual(payload["info"]["allowed_values"], ["Run", "Grow"])

    def test_create_with_set_forwards_value_through_dispatch(self) -> None:
        # AC3: --set on the create command couriers the chosen value to the REST
        # create verbatim, wired from JIRA_REQUIRED_FIELDS through dispatch.
        runner = ScriptedRunner([(self._AUTHED,)])
        curl = ScriptedCurl([(json.dumps({"key": "PROJ-9"}), 201)])
        env = dict(self._ENV,
                   JIRA_REQUIRED_FIELDS='{"Epic": ["customfield_10100"]}')
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "create", "--title", "t", "--category", "epic",
             "--set", "customfield_10100=Grow"],
            env=env, runner=runner, jira_curl_runner=curl, stream=out,
            stdin_body="the brief",
        )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["outcome"], "ok")
        payload = json.loads(curl.calls[-1]["payload"])
        self.assertEqual(payload["fields"]["customfield_10100"], "Grow")

    def test_create_sets_fixed_value_through_dispatch(self) -> None:
        # AC1: a fixed value from JIRA_FIELD_VALUES is set on the REST create
        # with no --set and no halt.
        runner = ScriptedRunner([(self._AUTHED,)])
        curl = ScriptedCurl([(json.dumps({"key": "PROJ-9"}), 201)])
        env = dict(self._ENV,
                   JIRA_REQUIRED_FIELDS='{"Epic": ["customfield_10100"]}',
                   JIRA_FIELD_VALUES='{"customfield_10100": "Run"}')
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "create", "--title", "t", "--category", "epic"],
            env=env, runner=runner, jira_curl_runner=curl, stream=out,
            stdin_body="the brief",
        )
        self.assertEqual(rc, 0)
        payload = json.loads(curl.calls[-1]["payload"])
        self.assertEqual(payload["fields"]["customfield_10100"], "Run")

    def test_issue_close_dispatches_through_the_curl_seam(self) -> None:
        view = json.dumps({"fields": {"status": {
            "name": "x", "statusCategory": {"key": "indeterminate"}}}})
        runner = ScriptedRunner([(self._AUTHED,), (view,)])
        transitions = json.dumps({"transitions": [
            {"id": "31", "to": {"statusCategory": {"key": "done"}},
             "fields": {}}]})
        curl = ScriptedCurl([transitions, ("", 204)])
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "close", "--key", "PROJ-7"],
            env=self._ENV, runner=runner, jira_curl_runner=curl, stream=out,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["outcome"], "ok")
        self.assertEqual(payload["state"], "closed")

    def test_close_honours_jira_done_resolution_env_var(self) -> None:
        # AC2: the resolution name comes from JIRA_DONE_RESOLUTION through
        # dispatch, not just the direct constructor — the env override is wired.
        view = json.dumps({"fields": {"status": {
            "name": "x", "statusCategory": {"key": "indeterminate"}}}})
        runner = ScriptedRunner([(self._AUTHED,), (view,)])
        transitions = json.dumps({"transitions": [
            {"id": "31", "to": {"statusCategory": {"key": "done"}},
             "fields": {"resolution": {"required": True}}}]})
        curl = ScriptedCurl([transitions, ("", 204)])
        env = dict(self._ENV, JIRA_DONE_RESOLUTION="Fixed")
        rc = tracker.run(
            ["issue", "close", "--key", "PROJ-7"],
            env=env, runner=runner, jira_curl_runner=curl, stream=io.StringIO(),
        )
        self.assertEqual(rc, 0)
        payload = json.loads(curl.calls[1]["payload"])
        self.assertEqual(payload["fields"]["resolution"]["name"], "Fixed")

    def test_unauthenticated_acli_halts_at_startup(self) -> None:
        runner = ScriptedRunner([(self._NOT_AUTHED,)])
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--key", "PROJ-7"],
            env=self._ENV, runner=runner, stream=out,
        )
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")

    def test_incomplete_credential_halts_at_startup(self) -> None:
        env = dict(self._ENV)
        del env["JIRA_EMAIL"]
        runner = ScriptedRunner([(json.dumps({"authenticated": True}),)])
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--key", "PROJ-7"],
            env=env, runner=runner, stream=out,
        )
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")


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

    def test_config_for_carries_basic_credential_off_argv(self) -> None:
        # The config the backend feeds curl carries the api_token as a base64
        # Basic header, evaluated once from the credential command.
        config = jiracmd.config_for(_cred(), token_evaluator=lambda cmd: "s3cr3t")
        expected = base64.b64encode(b"bot@acme.io:s3cr3t").decode()
        self.assertIn(f"Basic {expected}", config)
        self.assertNotIn("s3cr3t", config.replace(expected, ""))

    def test_run_curl_keeps_credential_off_argv(self) -> None:
        # run_curl builds argv with the URL and flags only — the config (carrying
        # the credential) is delivered via --config - on stdin, never as argv.
        captured: dict[str, Any] = {}

        class FakeCompleted:
            returncode = 0
            stdout = "{}" + jiracmd._STATUS_MARKER + "200"
            stderr = ""

        def fake_run(args, **kw):
            captured["args"] = args
            captured["input"] = kw.get("input")
            return FakeCompleted()

        orig = jiracmd.subprocess.run
        jiracmd.subprocess.run = fake_run
        try:
            jiracmd.run_curl("GET", "https://acme.atlassian.net/x",
                             'header = "Authorization: Basic ZZZ"')
        finally:
            jiracmd.subprocess.run = orig
        self.assertNotIn("ZZZ", " ".join(captured["args"]))
        self.assertIn("--config", captured["args"])
        self.assertIn("-", captured["args"])
        self.assertIn("ZZZ", captured["input"])

    def test_data_payload_rides_the_stdin_config_not_argv(self) -> None:
        # The POST body travels the same -K stdin channel as the credential, so
        # neither rides argv; embedded quotes survive the config escaping.
        captured: dict[str, Any] = {}

        class FakeCompleted:
            returncode = 0
            stdout = "" + jiracmd._STATUS_MARKER + "204"
            stderr = ""

        def fake_run(args, **kw):
            captured["args"] = args
            captured["input"] = kw.get("input")
            return FakeCompleted()

        orig = jiracmd.subprocess.run
        jiracmd.subprocess.run = fake_run
        try:
            jiracmd.run_curl("POST", "https://acme/x", "cfg",
                             payload='{"transition": {"id": "31"}}')
        finally:
            jiracmd.subprocess.run = orig
        joined = " ".join(captured["args"])
        self.assertNotIn("transition", joined)
        self.assertIn('data = "{\\"transition\\": {\\"id\\": \\"31\\"}}"',
                      captured["input"])


if __name__ == "__main__":
    unittest.main()
