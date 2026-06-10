"""Tests for the tracker command group's GitHub backend.

Every test drives the backend through a scripted runner seam — a stand-in for
run_gh that pops a canned GhResult per call and records the argv — so the unit
covers the command built and the logic applied, never the network. The three
named acceptance criteria (stale-mergeable re-query, merge-method discovery,
approval-covers-HEAD) get dedicated cases, alongside the relations typing, the
branch-ref CAS lost-claim signal, the identity dispatch, and the present/act
output shapes.
"""

import io
import json
import unittest

from adapter import ghcmd, tracker
from adapter.identity import Identity


class ScriptedRunner:
    """A run_gh stand-in: returns queued results in order, records each call.

    Each queued entry is (stdout, returncode, stderr). Calls beyond the script
    reuse the last entry, so a fixed re-query that settles can over-poll
    harmlessly in a test.
    """

    def __init__(self, script):
        # script: list of (stdout, returncode, stderr)
        self._script = [self._norm(s) for s in script]
        self.calls = []

    @staticmethod
    def _norm(entry):
        if isinstance(entry, tuple):
            stdout = entry[0]
            rc = entry[1] if len(entry) > 1 else 0
            stderr = entry[2] if len(entry) > 2 else ""
            return (stdout, rc, stderr)
        return (entry, 0, "")

    def __call__(self, args, env=None, input=None, check=True):
        self.calls.append({"args": list(args), "env": env, "input": input})
        idx = min(len(self.calls) - 1, len(self._script) - 1)
        stdout, rc, stderr = self._script[idx]
        return ghcmd.GhResult(args=list(args), returncode=rc, stdout=stdout,
                              stderr=stderr)

    def argv(self, i=0):
        return self.calls[i]["args"]


def _backend(runner, identity=None):
    return tracker.GithubBackend(
        identity=identity or Identity(),
        repo="krixon/skills",
        runner=runner,
    )


# --- stale-mergeable re-query (named criterion) -----------------------------

class TestStaleMergeableRequery(unittest.TestCase):
    def test_repolls_until_mergestatestatus_leaves_unknown(self):
        # Two UNKNOWN reads, then it settles to CONFLICTING/DIRTY.
        runner = ScriptedRunner([
            (json.dumps({"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"}),),
            (json.dumps({"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"}),),
            (json.dumps({"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}),),
        ])
        be = _backend(runner)
        state = be.merge_state(7, sleep=lambda _s: None)
        self.assertEqual(state["mergeStateStatus"], "DIRTY")
        self.assertEqual(state["mergeable"], "CONFLICTING")
        # It polled three times — it did not decide on the first UNKNOWN read.
        self.assertEqual(len(runner.calls), 3)

    def test_settled_read_does_not_repoll(self):
        runner = ScriptedRunner([
            (json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}),),
        ])
        be = _backend(runner)
        state = be.merge_state(7, sleep=lambda _s: None)
        self.assertEqual(state["mergeStateStatus"], "CLEAN")
        self.assertEqual(len(runner.calls), 1)

    def test_gives_up_after_max_polls_returning_last(self):
        runner = ScriptedRunner([
            (json.dumps({"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"}),),
        ])
        be = _backend(runner)
        state = be.merge_state(7, max_polls=4, sleep=lambda _s: None)
        # It stopped at the cap rather than spinning forever.
        self.assertEqual(len(runner.calls), 4)
        self.assertEqual(state["mergeStateStatus"], "UNKNOWN")

    def test_find_conflicting_requeries_each_candidate(self):
        # The list read reports one PR clean (stale); the per-PR re-query
        # settles it to CONFLICTING, so it is reported as conflicting.
        list_payload = json.dumps([
            {"number": 12, "title": "x", "mergeable": "MERGEABLE",
             "mergeStateStatus": "CLEAN", "headRefName": "feat/12-x",
             "baseRefName": "main"},
        ])
        runner = ScriptedRunner([
            (list_payload,),  # the pr list
            (json.dumps({"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}),),
        ])
        be = _backend(runner)
        out = be.find_conflicting(sleep=lambda _s: None)
        self.assertEqual([p["number"] for p in out], [12])


# --- merge-method discovery (named criterion) -------------------------------

class TestMergeMethodDiscovery(unittest.TestCase):
    def test_branch_rule_allowed_methods_win(self):
        # A pull_request rule on the base restricts to rebase only.
        rules = json.dumps([
            {"type": "creation"},
            {"type": "pull_request",
             "parameters": {"allowed_merge_methods": ["rebase"]}},
        ])
        runner = ScriptedRunner([(rules,)])
        be = _backend(runner)
        self.assertEqual(be.merge_method("main"), "rebase")

    def test_prefers_squash_when_allowed(self):
        rules = json.dumps([
            {"type": "pull_request",
             "parameters": {"allowed_merge_methods": ["merge", "squash", "rebase"]}},
        ])
        runner = ScriptedRunner([(rules,)])
        be = _backend(runner)
        self.assertEqual(be.merge_method("main"), "squash")

    def test_falls_back_to_repo_flags_without_pr_rule(self):
        rules = json.dumps([{"type": "creation"}])
        repo_flags = json.dumps({
            "allow_squash_merge": False,
            "allow_merge_commit": True,
            "allow_rebase_merge": True,
        })
        runner = ScriptedRunner([(rules,), (repo_flags,)])
        be = _backend(runner)
        # Squash disallowed → rebase, never the merge commit.
        self.assertEqual(be.merge_method("main"), "rebase")

    def test_returns_none_when_only_merge_commit_allowed(self):
        rules = json.dumps([{"type": "creation"}])
        repo_flags = json.dumps({
            "allow_squash_merge": False,
            "allow_merge_commit": True,
            "allow_rebase_merge": False,
        })
        runner = ScriptedRunner([(rules,), (repo_flags,)])
        be = _backend(runner)
        # Neither squash nor rebase → no linear method → skip, never --merge.
        self.assertIsNone(be.merge_method("main"))


# --- approval-covers-HEAD (named criterion) ---------------------------------

class TestApprovalCoversHead(unittest.TestCase):
    def _payload(self, head, reviews):
        return json.dumps({"data": {"repository": {"pullRequest": {
            "headRefOid": head,
            "latestReviews": {"nodes": reviews},
        }}}})

    def test_current_when_approval_oid_equals_head(self):
        runner = ScriptedRunner([(self._payload("abc123", [
            {"state": "APPROVED", "author": {"login": "human"},
             "commit": {"oid": "abc123"}},
        ]),)])
        be = _backend(runner)
        self.assertTrue(be.approval_covers_head(5))

    def test_stale_when_approval_oid_behind_head(self):
        runner = ScriptedRunner([(self._payload("newhead", [
            {"state": "APPROVED", "author": {"login": "human"},
             "commit": {"oid": "oldcommit"}},
        ]),)])
        be = _backend(runner)
        self.assertFalse(be.approval_covers_head(5))

    def test_changes_requested_at_head_does_not_count(self):
        runner = ScriptedRunner([(self._payload("abc123", [
            {"state": "CHANGES_REQUESTED", "author": {"login": "human"},
             "commit": {"oid": "abc123"}},
        ]),)])
        be = _backend(runner)
        self.assertFalse(be.approval_covers_head(5))

    def test_no_reviews_is_not_covered(self):
        runner = ScriptedRunner([(self._payload("abc123", []),)])
        be = _backend(runner)
        self.assertFalse(be.approval_covers_head(5))


# --- relations: typed sub_issue_id (-F, integer) ----------------------------

class TestRelations(unittest.TestCase):
    def test_add_sub_issue_resolves_child_id_and_types_with_F(self):
        # First call resolves the child's internal id; second adds the relation.
        runner = ScriptedRunner([
            ("9876",),  # child id
            ("{}",),    # the sub_issues POST
        ])
        be = _backend(runner)
        be.add_sub_issue(parent=10, child=42)
        add_argv = runner.argv(1)
        # Typed integer field: -F sub_issue_id=<id>, never -f (string → 422).
        self.assertIn("-F", add_argv)
        self.assertIn("sub_issue_id=9876", add_argv)
        self.assertNotIn("-f", add_argv)
        self.assertIn("repos/krixon/skills/issues/10/sub_issues", add_argv)

    def test_add_blocker_types_issue_id_with_F(self):
        runner = ScriptedRunner([
            ("5555",),  # blocker id
            ("{}",),
        ])
        be = _backend(runner)
        be.add_blocked_by(number=10, blocker=7)
        add_argv = runner.argv(1)
        self.assertIn("-F", add_argv)
        self.assertIn("issue_id=5555", add_argv)
        self.assertIn("repos/krixon/skills/issues/10/dependencies/blocked_by", add_argv)

    def test_read_parent_absent_reads_as_no_parent(self):
        # The /parent endpoint 404s (non-zero) when there is no parent.
        runner = ScriptedRunner([("", 1, "gh: Not Found (HTTP 404)")])
        be = _backend(runner)
        self.assertIsNone(be.parent_of(42))


# --- branch-ref create as CAS ----------------------------------------------

class TestBranchRefCas(unittest.TestCase):
    def test_create_succeeds(self):
        runner = ScriptedRunner([(json.dumps({"ref": "refs/heads/feat/1-x"}),)])
        be = _backend(runner)
        result = be.create_branch_ref("feat/1-x", "deadbeef")
        self.assertTrue(result["created"])
        post_argv = runner.argv(0)
        self.assertIn("POST", post_argv)
        self.assertIn("repos/krixon/skills/git/refs", post_argv)
        self.assertIn("ref=refs/heads/feat/1-x", post_argv)

    def test_422_already_exists_is_lost_claim_not_error(self):
        runner = ScriptedRunner([
            ("", 1, "gh: Reference already exists (HTTP 422)"),
        ])
        be = _backend(runner)
        result = be.create_branch_ref("feat/1-x", "deadbeef")
        # The lost-claim signal is the write's own rejection — not an exception.
        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "claim-lost")

    def test_other_failure_still_raises(self):
        runner = ScriptedRunner([("", 1, "gh: Server Error (HTTP 500)")])
        be = _backend(runner)
        with self.assertRaises(ghcmd.GhError):
            be.create_branch_ref("feat/1-x", "deadbeef")


# --- selection: find-rework / find-approved drop author when unconfigured ---

class TestSelectionAuthorFilter(unittest.TestCase):
    def test_configured_filters_on_bot_author(self):
        runner = ScriptedRunner([("[]",)])
        be = _backend(runner, identity=Identity(account="krixon-bot",
                                                token_cmd="printf t"))
        be.find_rework()
        argv = runner.argv(0)
        self.assertIn("--author", argv)
        self.assertIn("krixon-bot", argv)

    def test_unconfigured_drops_author_filter(self):
        runner = ScriptedRunner([("[]",)])
        be = _backend(runner)  # unconfigured
        be.find_rework()
        argv = runner.argv(0)
        self.assertNotIn("--author", argv)

    def test_find_rework_keeps_only_changes_requested(self):
        payload = json.dumps([
            {"number": 1, "reviewDecision": "CHANGES_REQUESTED"},
            {"number": 2, "reviewDecision": "APPROVED"},
            {"number": 3, "reviewDecision": None},
        ])
        runner = ScriptedRunner([(payload,)])
        be = _backend(runner)
        out = be.find_rework()
        self.assertEqual([p["number"] for p in out], [1])

    def test_find_approved_keeps_only_approved(self):
        payload = json.dumps([
            {"number": 1, "reviewDecision": "APPROVED"},
            {"number": 2, "reviewDecision": "CHANGES_REQUESTED"},
        ])
        runner = ScriptedRunner([(payload,)])
        be = _backend(runner)
        out = be.find_approved()
        self.assertEqual([p["number"] for p in out], [1])


# --- PR create uses bot identity (token in env, not argv) -------------------

class TestPrCreate(unittest.TestCase):
    def test_passes_body_on_stdin_and_token_in_env(self):
        runner = ScriptedRunner([("https://github.com/krixon/skills/pull/9",)])
        be = _backend(runner, identity=Identity(account="krixon-bot",
                                                token_cmd="printf tok"))
        be.pr_create(title="feat: x", body="Closes #1")
        call = runner.calls[0]
        self.assertIn("--body-file", call["args"])
        self.assertIn("-", call["args"])
        self.assertEqual(call["input"], "Closes #1")
        self.assertEqual(call["env"]["GH_TOKEN"], "tok")
        # Token never in argv.
        self.assertNotIn("tok", " ".join(call["args"]))

    def test_unconfigured_pr_create_has_no_token(self):
        runner = ScriptedRunner([("https://github.com/krixon/skills/pull/9",)])
        be = _backend(runner)
        be.pr_create(title="feat: x", body="Closes #1")
        env = runner.calls[0]["env"]
        self.assertTrue(env is None or "GH_TOKEN" not in env)


# --- review thread reply-then-resolve ---------------------------------------

class TestReviewThread(unittest.TestCase):
    def test_reply_then_resolve_gated_on_reply_id(self):
        runner = ScriptedRunner([
            (json.dumps({"id": 555}),),  # reply posts, returns id
            (json.dumps({"data": {"repository": {"pullRequest": {
                "reviewThreads": {"nodes": [{"id": "THREAD", "isResolved": False}]}}}}}),),  # re-read
            (json.dumps({"data": {"resolveReviewThread": {"thread": {"isResolved": True}}}}),),  # resolve
        ])
        be = _backend(runner, identity=Identity(account="krixon-bot",
                                                token_cmd="printf t"))
        result = be.reply_and_resolve(pr=3, comment_id=99, thread_id="THREAD",
                                      body="answer")
        self.assertTrue(result["resolved"])
        # The reply body went out-of-band on stdin.
        self.assertEqual(runner.calls[0]["input"], "answer")

    def test_reply_failure_skips_resolve(self):
        # The reply returns no id (failed); resolve must not fire.
        runner = ScriptedRunner([("", 1, "gh: error")])
        be = _backend(runner, identity=Identity(account="krixon-bot",
                                                token_cmd="printf t"))
        with self.assertRaises(ghcmd.GhError):
            be.reply_and_resolve(pr=3, comment_id=99, thread_id="THREAD",
                                 body="answer")
        # Only the reply was attempted — never the resolve mutation.
        self.assertEqual(len(runner.calls), 1)

    def test_already_resolved_thread_skips_mutation(self):
        runner = ScriptedRunner([
            (json.dumps({"id": 555}),),  # reply
            (json.dumps({"data": {"repository": {"pullRequest": {
                "reviewThreads": {"nodes": [{"id": "THREAD", "isResolved": True}]}}}}}),),  # re-read: already resolved
        ])
        be = _backend(runner, identity=Identity(account="krixon-bot",
                                                token_cmd="printf t"))
        result = be.reply_and_resolve(pr=3, comment_id=99, thread_id="THREAD",
                                      body="answer")
        self.assertTrue(result["skipped"])
        # Reply + re-read only; no resolve mutation issued.
        self.assertEqual(len(runner.calls), 2)


# --- present/act output shapes via the dispatcher ---------------------------

class TestDispatchAndShapes(unittest.TestCase):
    def test_present_issue_view_emits_json(self):
        payload = json.dumps({"number": 7, "title": "t", "body": "b"})
        runner = ScriptedRunner([(payload,)])
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--number", "7"],
            env={"ISSUE_TRACKER": "github"},
            runner=runner, repo="krixon/skills", stream=out,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["number"], 7)

    def test_act_issue_comment_reports_acted(self):
        runner = ScriptedRunner([("https://github.com/krixon/skills/issues/7#x",)])
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "comment", "--number", "7"],
            env={"ISSUE_TRACKER": "github"},
            runner=runner, repo="krixon/skills", stream=out,
            stdin_body="a comment body",
        )
        self.assertEqual(rc, 0)
        # The body reached gh on stdin, not in argv.
        self.assertEqual(runner.calls[0]["input"], "a comment body")

    def test_unknown_tracker_halts(self):
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--number", "7"],
            env={"ISSUE_TRACKER": "jira"},
            runner=ScriptedRunner([("{}",)]), repo="x", stream=out,
        )
        # jira is not built in this slice; the dispatcher halts, not crashes.
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")

    def test_half_configured_identity_halts_at_startup(self):
        out = io.StringIO()
        rc = tracker.run(
            ["issue", "view", "--number", "7"],
            env={"ISSUE_TRACKER": "github", "GITHUB_BOT_ACCOUNT": "krixon-bot"},
            runner=ScriptedRunner([("{}",)]), repo="x", stream=out,
        )
        self.assertNotEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "halted")
        self.assertIn("half-configured", payload["reason"])


if __name__ == "__main__":
    unittest.main()
