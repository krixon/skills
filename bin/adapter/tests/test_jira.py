"""Tests for the tracker command group's Jira backend.

Symmetric with test_tracker.py: every test drives the backend through a scripted
acli runner seam — a run_acli stand-in that pops a canned AcliResult per call and
records argv — so the unit covers the command built and the logic applied, never
the network. The named acceptance criteria get dedicated cases: statusCategory.key
resolution (reads and the already-done no-op), the call-time category→status-name
mapping (via the injected /transitions fetcher), and the concept→primitive map.
"""

from __future__ import annotations

import io
import json
import unittest
from typing import Any, Sequence

from adapter import aclicmd, jira, tracker


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


def _cred() -> aclicmd.JiraCredential:
    return aclicmd.JiraCredential(site="https://acme.atlassian.net",
                                  email="bot@acme.io", token_cmd="printf tok")


def _backend(runner: Any, project: str = "PROJ",
             transitions_fetcher: Any = None) -> jira.JiraBackend:
    return jira.JiraBackend(credential=_cred(), project=project, runner=runner,
                            transitions_fetcher=transitions_fetcher)


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


# --- transitions resolve category -> status name at call time (named) -------

class TestTransitionResolution(unittest.TestCase):
    @staticmethod
    def _view(category: str) -> str:
        return json.dumps({"fields": {"status": {
            "name": "x", "statusCategory": {"key": category}}}})

    def _fetcher(self, transitions: list[dict[str, str]]) -> Any:
        calls = []

        def fetch(credential: Any, key: str, **kw: Any) -> list[dict[str, str]]:
            calls.append({"key": key})
            return transitions

        fetch.calls = calls  # type: ignore[attr-defined]
        return fetch

    def test_resolves_target_category_to_reachable_status_name(self) -> None:
        # view: currently indeterminate (not yet done, so the transition runs).
        runner = ScriptedRunner([
            (self._view("indeterminate"),),  # is_done check
            ("{}",),                          # the transition
        ])
        fetch = self._fetcher([
            {"name": "Back to Todo", "category": "new"},
            {"name": "Ship It", "category": "done"},
        ])
        be = _backend(runner, transitions_fetcher=fetch)
        be.transition_to_category("PROJ-7", jira.CATEGORY_DONE)
        # It transitioned by the status NAME carrying the target category — the
        # name was resolved at call time, never hard-coded.
        transition_argv = runner.argv(1)
        self.assertEqual(transition_argv[:3], ["jira", "workitem", "transition"])
        self.assertIn("--status", transition_argv)
        self.assertIn("Ship It", transition_argv)
        # The name "Done" is never assumed.
        self.assertNotIn("Done", transition_argv)

    def test_rename_does_not_break_the_binding(self) -> None:
        # The project renamed its done status to "Closed"; resolution still finds
        # it by category, with no code change.
        runner = ScriptedRunner([(self._view("indeterminate"),), ("{}",)])
        fetch = self._fetcher([{"name": "Closed", "category": "done"}])
        be = _backend(runner, transitions_fetcher=fetch)
        be.transition_to_category("PROJ-7", jira.CATEGORY_DONE)
        self.assertIn("Closed", runner.argv(1))

    def test_already_in_target_category_is_a_noop(self) -> None:
        # Already done → no transition issued (the already-done no-op check).
        runner = ScriptedRunner([(self._view("done"),)])
        fetch = self._fetcher([{"name": "Ship It", "category": "done"}])
        be = _backend(runner, transitions_fetcher=fetch)
        result = be.transition_to_category("PROJ-7", jira.CATEGORY_DONE)
        self.assertTrue(result.get("noop"))
        # Only the is_done read ran — no transition call.
        self.assertEqual(len(runner.calls), 1)

    def test_no_reachable_transition_for_category_raises(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),)])
        fetch = self._fetcher([{"name": "Back to Todo", "category": "new"}])
        be = _backend(runner, transitions_fetcher=fetch)
        with self.assertRaises(jira.NoSuchTransition):
            be.transition_to_category("PROJ-7", jira.CATEGORY_DONE)

    def test_fetcher_is_called_with_the_issue_key(self) -> None:
        runner = ScriptedRunner([(self._view("indeterminate"),), ("{}",)])
        fetch = self._fetcher([{"name": "Ship It", "category": "done"}])
        be = _backend(runner, transitions_fetcher=fetch)
        be.transition_to_category("PROJ-7", jira.CATEGORY_DONE)
        self.assertEqual(fetch.calls[0]["key"], "PROJ-7")


# --- issue concept methods (the dispatched surface) -------------------------

class TestIssueConcepts(unittest.TestCase):
    def test_issue_view_reads_workitem_all_fields(self) -> None:
        payload = json.dumps({"key": "PROJ-7", "fields": {
            "summary": "t", "status": {"statusCategory": {"key": "new"}}}})
        runner = ScriptedRunner([(payload,)])
        be = _backend(runner)
        out = be.issue_view("PROJ-7")
        self.assertEqual(out["key"], "PROJ-7")
        argv = runner.argv(0)
        self.assertEqual(argv[:3], ["jira", "workitem", "view"])
        self.assertIn("--json", argv)

    def test_issue_create_uses_issue_type_for_category_and_body_on_stdin(self) -> None:
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
        # The untrusted body rode stdin, never argv (SECURITY.md).
        self.assertEqual(runner.calls[0]["input"], "the body")
        self.assertNotIn("the body", argv)

    def test_issue_comment_body_rides_stdin(self) -> None:
        runner = ScriptedRunner([("{}",)])
        be = _backend(runner)
        be.issue_comment("PROJ-7", body="a comment")
        self.assertEqual(runner.calls[0]["input"], "a comment")
        self.assertNotIn("a comment", runner.argv(0))

    def test_issue_label_maps_state_labels_through(self) -> None:
        runner = ScriptedRunner([("{}",)])
        be = _backend(runner)
        be.issue_label("PROJ-7", add=["in-progress"])
        argv = runner.argv(0)
        self.assertIn("in-progress", argv)


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

    def test_jira_requires_git_and_acli(self) -> None:
        self.assertEqual(tracker.required_tools({"ISSUE_TRACKER": "jira"}),
                         ("git", "acli"))

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
        self.assertEqual(json.loads(out.getvalue())["key"], "PROJ-7")

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


if __name__ == "__main__":
    unittest.main()
