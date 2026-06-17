"""Tests for the land command group: classification and apply orchestration.

Classification (plan) and the apply sequence drive the tracker GithubBackend
through the same scripted `gh` runner seam test_tracker.py uses, plus fake
worktree teardown / sync-main functions and a fake git runner for worktree
discovery — so every bucket and every apply branch is covered against canned
JSON, never the network or a real checkout.
"""

from __future__ import annotations

import io
import json
import unittest
from typing import Any, Sequence

from adapter import ghcmd, land
from adapter.identity import Identity
from adapter.tracker import GithubBackend


class ProgrammedRunner:
    """A run_gh stand-in routing each call to a canned reply keyed by argv.

    land issues many heterogeneous gh calls per PR (merge-state, approval,
    closing-refs, merge, label, parent, sub-issues, …), so a positional script
    is brittle. This matches on a substring of the joined argv and pops the
    next queued reply for that key, recording every call for assertions.
    """

    def __init__(self, routes: dict[str, Sequence[Any]]) -> None:
        # routes: argv-substring -> list of (stdout, rc, stderr) | stdout
        self._routes = {k: [self._norm(v) for v in vs]
                        for k, vs in routes.items()}
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
                 input: str | None = None, check: bool = True) -> ghcmd.GhResult:
        self.calls.append({"args": list(args), "env": env, "input": input})
        joined = " ".join(str(a) for a in args)
        for key, replies in self._routes.items():
            if key in joined:
                stdout, rc, stderr = replies.pop(0) if len(replies) > 1 else replies[0]
                return ghcmd.GhResult(args=list(args), returncode=rc,
                                      stdout=stdout, stderr=stderr)
        raise AssertionError(f"no canned route for gh call: {joined}")

    def argvs(self, substring: str) -> list[list[str]]:
        return [c["args"] for c in self.calls
                if substring in " ".join(str(a) for a in c["args"])]


def _backend(runner: Any) -> GithubBackend:
    return GithubBackend(identity=Identity(), repo="krixon/skills", runner=runner)


def _merge_state(mergeable: str, status: str) -> str:
    return json.dumps({"mergeable": mergeable, "mergeStateStatus": status})


def _approval(head: str, oid: str, state: str = "APPROVED") -> str:
    return json.dumps({"data": {"repository": {"pullRequest": {
        "headRefOid": head,
        "latestReviews": {"nodes": [
            {"state": state, "author": {"login": "human"}, "commit": {"oid": oid}}]},
    }}}})


def _rules(methods: list[str]) -> str:
    return json.dumps([{"type": "pull_request",
                        "parameters": {"allowed_merge_methods": methods}}])


def _closing(numbers: list[int]) -> str:
    return json.dumps({"closingIssuesReferences": [{"number": n} for n in numbers]})


# --- classification (plan) buckets ------------------------------------------

class TestClassify(unittest.TestCase):
    def test_landable_clean_covered_with_method_and_closes(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash", "rebase"])],
            "closingIssuesReferences": [_closing([42])],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 5, "title": "t", "baseRefName": "main",
                                  "body": "Closes #42"}], sleep=lambda _s: None)
        self.assertEqual(len(out["landable"]), 1)
        lp = out["landable"][0]
        self.assertEqual(lp["method"], "squash")
        self.assertEqual(lp["closes"], [42])
        self.assertEqual(lp["flags"], [])

    def test_rework_behind(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "BEHIND")],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 6, "title": "t"}], sleep=lambda _s: None)
        self.assertEqual(out["rework"], [{"number": 6, "reason": "behind"}])

    def test_rework_conflicting(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("CONFLICTING", "DIRTY")],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 7, "title": "t"}], sleep=lambda _s: None)
        self.assertEqual(out["rework"], [{"number": 7, "reason": "conflicting"}])

    def test_skip_stale_approval(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("newhead", "oldcommit")],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 8, "title": "t"}], sleep=lambda _s: None)
        self.assertEqual(out["skip"], [{"number": 8, "reason": "stale-approval"}])

    def test_skip_not_ready(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "BLOCKED")],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 9, "title": "t"}], sleep=lambda _s: None)
        self.assertEqual(out["skip"], [{"number": 9, "reason": "not-ready: BLOCKED"}])

    def test_merged_bucket(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "MERGED",
                                                  "mergedAt": "2026-06-01T00:00:00Z"})],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 10, "title": "t"}], sleep=lambda _s: None)
        self.assertEqual(out["merged"], [{"number": 10}])

    def test_skip_no_allowed_method(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["merge"])],  # only a merge commit allowed
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 11, "title": "t", "baseRefName": "main"}],
                            sleep=lambda _s: None)
        self.assertEqual(out["skip"], [{"number": 11, "reason": "no-allowed-merge-method"}])

    def test_no_issue_flag_when_no_closing_ref_and_no_marker(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([])],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 12, "title": "t", "baseRefName": "main",
                                  "body": "no marker here"}], sleep=lambda _s: None)
        self.assertIn("no-issue", out["landable"][0]["flags"])
        self.assertIn("no-issue", out["unusual"])

    def test_no_issue_marker_is_not_flagged(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([])],
        })
        be = _backend(runner)
        out = land.classify(be, [{"number": 13, "title": "t", "baseRefName": "main",
                                  "body": "No-issue: a tiny doc fix"}],
                            sleep=lambda _s: None)
        self.assertEqual(out["landable"][0]["flags"], [])
        self.assertNotIn("no-issue", out["unusual"])

    def test_multi_pr_flag(self) -> None:
        runner = ProgrammedRunner({
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([1])],
        })
        be = _backend(runner)
        out = land.classify(be, [
            {"number": 1, "title": "a", "baseRefName": "main", "body": "Closes #1"},
            {"number": 2, "title": "b", "baseRefName": "main", "body": "Closes #1"},
        ], sleep=lambda _s: None)
        self.assertIn("multi-pr", out["unusual"])


# --- apply orchestration ----------------------------------------------------

class FakeWorktree:
    """Records teardown / sync-main calls so apply's cleanup is asserted without
    a real git checkout."""

    def __init__(self) -> None:
        self.teardowns: list[dict[str, Any]] = []
        self.syncs = 0

    def teardown(self, repo_root: str, path: str, branch: str, stream: Any) -> int:
        self.teardowns.append({"repo_root": repo_root, "path": path, "branch": branch})
        return 0

    def sync_main(self, repo_root: str, stream: Any) -> int:
        self.syncs += 1
        return 0


def _git_worktree_list(branch: str, path: str) -> Any:
    """A fake git runner returning one worktree on `branch` at `path`."""
    out = f"worktree {path}\nHEAD deadbeef\nbranch refs/heads/{branch}\n"

    class _Result:
        returncode = 0
        stdout = out

    def runner(args: Sequence[str], cwd: str | None = None,
               check: bool = True) -> Any:
        return _Result()

    return runner


def _git_no_worktree() -> Any:
    class _Result:
        returncode = 0
        stdout = "worktree /repo\nHEAD deadbeef\nbranch refs/heads/main\n"

    def runner(args: Sequence[str], cwd: str | None = None,
               check: bool = True) -> Any:
        return _Result()

    return runner


def _pr_row(number: int, head: str, body: str, base: str = "main") -> str:
    """The per-number row land.apply sources via pr_fields — the fields it needs
    to merge and clean up one confirmed PR. apply binds to the selection, so it
    reads each PR by number rather than sweeping the approved set."""
    return json.dumps({"number": number, "headRefName": head,
                       "baseRefName": base, "body": body})


class TestApply(unittest.TestCase):
    def test_merge_then_close_strip_teardown_sync(self) -> None:
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [("", 1, "404")],  # no parent epic
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        rc = land.apply(be, "/repo", pr_numbers=[5],
                        teardown=fw.teardown, sync_main=fw.sync_main,
                        worktree_runner=_git_worktree_list("feat/5-x", "/repo/wt"),
                        sleep=lambda _s: None, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        res = payload["results"][0]
        self.assertTrue(res["merged"])
        self.assertEqual(res["method"], "squash")
        self.assertEqual(res["closedIssues"], [42])
        self.assertTrue(res["tornDown"])
        # in-progress was stripped on the closed issue.
        self.assertTrue(any("--remove-label" in a and "in-progress" in a
                            for a in runner.argvs("issue edit")))
        self.assertEqual(fw.teardowns[0]["branch"], "feat/5-x")
        self.assertEqual(fw.syncs, 1)

    def test_binds_to_selection_never_sweeps_for_unconfirmed(self) -> None:
        # The widening regression: apply must act only on the passed selection
        # and never re-derive the approved set. No "pr list" route is provided,
        # so any sweep would raise — proving apply sources PRs by number and a
        # PR approved after the plan can never enter the batch.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [("", 1, "404")],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        payload = json.loads(out.getvalue())
        # Only the confirmed PR is acted on.
        self.assertEqual([r["number"] for r in payload["results"]], [5])
        self.assertTrue(payload["results"][0]["merged"])
        # find_approved was never consulted — no PR list sweep was issued.
        self.assertEqual(runner.argvs("pr list"), [])

    def test_unknown_pr_number_reported_not_found(self) -> None:
        # A number with no matching PR (empty pr_fields read) is reported skipped,
        # not raised — one bad number must not abort the rest of the selection.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [""],  # empty -> pr_fields None
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[999],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["skipped"])
        self.assertEqual(res["reason"], "not-found")
        self.assertEqual(runner.argvs("pr merge"), [])

    def test_already_merged_in_ui_skips_merge_goes_to_cleanup(self) -> None:
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            # Merged in the UI before apply ran: the merged-in-UI re-check.
            "--json state,mergedAt": [json.dumps({"state": "MERGED"})],
            "closingIssuesReferences": [_closing([42])],
            "issue edit": ["ok"],
            "issues/42/parent": [("", 1, "404")],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_worktree_list("feat/5-x", "/repo/wt"),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["alreadyMerged"])
        self.assertFalse(res["merged"])
        # No merge call was issued — it was already merged in the UI.
        self.assertEqual(runner.argvs("pr merge"), [])
        # Cleanup still ran.
        self.assertEqual(res["closedIssues"], [42])
        self.assertTrue(res["tornDown"])

    def test_gone_stale_at_merge_time_skips_with_reason(self) -> None:
        # BEHIND when apply re-checks (main moved under the confirmed PR).
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "BEHIND")],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["skipped"])
        self.assertIn("not-ready", res["reason"])
        self.assertEqual(runner.argvs("pr merge"), [])
        # sync still runs once after the selection.
        self.assertEqual(fw.syncs, 1)

    def test_no_issue_no_declaration_leaves_issue_untouched(self) -> None:
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "no marker, no closes")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([])],
            "pr merge": ["merged"],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["merged"])
        self.assertTrue(res["noLinkedIssue"])
        self.assertEqual(res["closedIssues"], [])
        # No issue edit (label strip) was attempted.
        self.assertEqual(runner.argvs("issue edit"), [])

    def test_no_marker_body_from_per_number_row_is_honoured(self) -> None:
        # The no-issue check reads the body from the per-number row: a body that
        # leads with `No-issue:` is an intentional issue-less land, not flagged.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "No-issue: a tiny doc fix")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([])],
            "pr merge": ["merged"],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["merged"])
        # No-issue: declared, so the absence of a closing ref is intentional —
        # not flagged noLinkedIssue, and no label strip attempted.
        self.assertNotIn("noLinkedIssue", res)
        self.assertEqual(res["closedIssues"], [])
        self.assertEqual(runner.argvs("issue edit"), [])

    def test_no_worktree_skips_teardown_quietly(self) -> None:
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [("", 1, "404")],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertFalse(res["tornDown"])
        self.assertEqual(fw.teardowns, [])

    def test_epic_close_candidate_on_last_child(self) -> None:
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [json.dumps(100)],   # parent epic #100
            "issue view": [json.dumps({"number": 100, "title": "epic",
                                       "state": "OPEN"})],
            "issues/100/sub_issues": [json.dumps([
                {"number": 42, "state": "closed"},
                {"number": 43, "state": "closed"},
            ])],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        payload = json.loads(out.getvalue())
        cands = payload["epic_close_candidates"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["number"], 100)
        # land never closes the epic here — no issue close call to the epic.
        self.assertEqual(runner.argvs("issue close"), [])

    def test_epic_not_offered_when_a_child_still_open(self) -> None:
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [json.dumps(100)],
            "issue view": [json.dumps({"number": 100, "title": "epic",
                                       "state": "OPEN"})],
            "issues/100/sub_issues": [json.dumps([
                {"number": 42, "state": "closed"},
                {"number": 43, "state": "open"},
            ])],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        self.assertEqual(json.loads(out.getvalue())["epic_close_candidates"], [])

    def test_multi_pr_shared_epic_dedups_to_one_candidate(self) -> None:
        # Two confirmed PRs, #5 closing #42 and #6 closing #43, both children of
        # the same epic #100 which now has only those two closed sub-issues.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [
                _pr_row(5, "feat/5-x", "Closes #42"),
                _pr_row(6, "feat/6-y", "Closes #43"),
            ],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            # closing-refs is asked once per PR in selection order: #5 -> #42,
            # #6 -> #43. Keyed on the field list (not `pr view N`) so it can't
            # shadow the other per-PR reads by argv substring.
            "closingIssuesReferences": [_closing([42]), _closing([43])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            # both children parent to the same epic #100.
            "issues/42/parent": [json.dumps(100)],
            "issues/43/parent": [json.dumps(100)],
            "issue view": [json.dumps({"number": 100, "title": "epic",
                                       "state": "OPEN"})],
            # the epic's only sub-issues, both now closed.
            "issues/100/sub_issues": [json.dumps([
                {"number": 42, "state": "closed"},
                {"number": 43, "state": "closed"},
            ])],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5, 6],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        payload = json.loads(out.getvalue())
        # Both PRs merged.
        self.assertEqual(len(payload["results"]), 2)
        self.assertTrue(all(r["merged"] for r in payload["results"]))
        # The shared epic is offered exactly once (seen_epics dedup).
        cands = payload["epic_close_candidates"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["number"], 100)

    def test_first_pr_skip_does_not_abort_the_rest(self) -> None:
        # #5 is stale at merge time (approval no longer covers HEAD); #6 is still
        # CLEAN+covered. The first PR's skip must not stop the selection.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [
                _pr_row(5, "feat/5-x", "Closes #42"),
                _pr_row(6, "feat/6-y", "Closes #43"),
            ],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            # approval-covers-HEAD asked once per PR: #5 stale, #6 covered.
            "headRefOid": [
                _approval("new", "old"),   # #5 -> stale
                _approval("def", "def"),   # #6 -> covered
            ],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            # #5 skips before its closing-refs read; only #6 reaches it (#43).
            "closingIssuesReferences": [_closing([43])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/43/parent": [("", 1, "404")],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5, 6],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(len(payload["results"]), 2)
        first, second = payload["results"]
        # #5 skipped stale; #6 still processed and merged.
        self.assertEqual(first["number"], 5)
        self.assertTrue(first["skipped"])
        self.assertEqual(first["reason"], "stale-approval")
        self.assertEqual(second["number"], 6)
        self.assertTrue(second["merged"])

    def test_stale_approval_at_merge_time_skips_with_no_merge(self) -> None:
        # Approval no longer covers HEAD at merge time: skip stale-approval, no
        # merge issued.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("new", "old")],   # stale
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["skipped"])
        self.assertEqual(res["reason"], "stale-approval")
        self.assertEqual(runner.argvs("pr merge"), [])

    def test_no_allowed_merge_method_skips_with_reason(self) -> None:
        # CLEAN + covered, but the base allows only a merge commit: skip rather
        # than fall through to a non-linear merge.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["merge"])],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        res = json.loads(out.getvalue())["results"][0]
        self.assertTrue(res["skipped"])
        self.assertEqual(res["reason"], "no-allowed-merge-method")
        self.assertEqual(runner.argvs("pr merge"), [])

    def test_no_candidate_when_epic_already_closed(self) -> None:
        # Like the last-child case, but the parent epic reads closed.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [json.dumps(100)],
            "issue view": [json.dumps({"number": 100, "title": "epic",
                                       "state": "CLOSED"})],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        self.assertEqual(json.loads(out.getvalue())["epic_close_candidates"], [])

    def test_no_candidate_when_epic_has_no_sub_issues(self) -> None:
        # The parent epic exists and is OPEN, but its sub-issue list is empty:
        # the `if subs and all(...)` guard must not offer a candidate.
        runner = ProgrammedRunner({
            "number,headRefName,baseRefName,body": [_pr_row(5, "feat/5-x", "Closes #42")],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([42])],
            "pr merge": ["merged"],
            "issue edit": ["ok"],
            "issues/42/parent": [json.dumps(100)],
            "issue view": [json.dumps({"number": 100, "title": "epic",
                                       "state": "OPEN"})],
            "issues/100/sub_issues": [json.dumps([])],
        })
        be = _backend(runner)
        fw = FakeWorktree()
        out = io.StringIO()
        land.apply(be, "/repo", pr_numbers=[5],
                   teardown=fw.teardown, sync_main=fw.sync_main,
                   worktree_runner=_git_no_worktree(),
                   sleep=lambda _s: None, stream=out)
        self.assertEqual(json.loads(out.getvalue())["epic_close_candidates"], [])


# --- close-epic (human-gated) -----------------------------------------------

class TestCloseEpic(unittest.TestCase):
    def test_closes_when_all_children_closed(self) -> None:
        runner = ProgrammedRunner({
            "issues/100/sub_issues": [json.dumps([
                {"number": 42, "state": "closed"},
                {"number": 43, "state": "closed"},
            ])],
            "issue close": ["ok"],
        })
        be = _backend(runner)
        out = io.StringIO()
        rc = land.close_epic(be, 100, stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["state"], "closed")

    def test_halts_when_a_child_reopened(self) -> None:
        runner = ProgrammedRunner({
            "issues/100/sub_issues": [json.dumps([
                {"number": 42, "state": "closed"},
                {"number": 43, "state": "open"},
            ])],
        })
        be = _backend(runner)
        out = io.StringIO()
        rc = land.close_epic(be, 100, stream=out)
        self.assertNotEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "halted")
        self.assertIn(43, payload["openChildren"])
        # The epic was not closed.
        self.assertEqual(runner.argvs("issue close"), [])


# --- dispatch ---------------------------------------------------------------

class TestDispatch(unittest.TestCase):
    def test_plan_present_emits_json(self) -> None:
        runner = ProgrammedRunner({
            "pr list": [json.dumps([{"number": 5, "title": "t",
                                     "reviewDecision": "APPROVED",
                                     "headRefName": "feat/5-x", "body": "Closes #1"}])],
            "--json state,mergedAt": [json.dumps({"state": "OPEN"})],
            "headRefOid": [_approval("abc", "abc")],
            "--json mergeable,mergeStateStatus": [_merge_state("MERGEABLE", "CLEAN")],
            "rules/branches": [_rules(["squash"])],
            "closingIssuesReferences": [_closing([1])],
        })
        out = io.StringIO()
        rc = land.run(["plan"], env={"ISSUE_TRACKER": "github"},
                      runner=runner, repo="krixon/skills", repo_root="/repo",
                      stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["landable"][0]["number"], 5)

    def test_apply_without_selection_halts(self) -> None:
        # A bare `apply` has no confirmed selection to act on, so it halts rather
        # than sweeping — the binary boundary that closes the widening even if a
        # caller forgets to thread the confirmed --pr numbers.
        out = io.StringIO()
        rc = land.run(["apply"], env={"ISSUE_TRACKER": "github"},
                      runner=ProgrammedRunner({}), repo="x", repo_root="/repo",
                      stream=out)
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")

    def test_unknown_command_halts(self) -> None:
        out = io.StringIO()
        rc = land.run(["bogus"], env={"ISSUE_TRACKER": "github"},
                      runner=ProgrammedRunner({}), repo="x", repo_root="/repo",
                      stream=out)
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")

    def test_unknown_tracker_halts(self) -> None:
        out = io.StringIO()
        rc = land.run(["plan"], env={"ISSUE_TRACKER": "jira"},
                      runner=ProgrammedRunner({}), repo="x", repo_root="/repo",
                      stream=out)
        self.assertNotEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")

    def test_half_configured_identity_halts(self) -> None:
        out = io.StringIO()
        rc = land.run(["plan"],
                      env={"ISSUE_TRACKER": "github",
                           "GITHUB_BOT_ACCOUNT": "krixon-bot"},
                      runner=ProgrammedRunner({}), repo="x", repo_root="/repo",
                      stream=out)
        self.assertNotEqual(rc, 0)
        self.assertIn("half-configured", json.loads(out.getvalue())["reason"])

    def test_bare_main_defaults_to_plan(self) -> None:
        # main() with no argv routes to plan; check the default substitution
        # without resolving a real repo by patching run.
        captured: dict[str, Any] = {}

        def fake_run(argv: Sequence[str], **kw: Any) -> int:
            captured["argv"] = list(argv)
            return 0

        orig = land.run
        land.run = fake_run  # type: ignore[assignment]
        try:
            land.main([])
        finally:
            land.run = orig  # type: ignore[assignment]
        self.assertEqual(captured["argv"], ["plan"])


# --- worktree discovery -----------------------------------------------------

class TestFindWorktree(unittest.TestCase):
    def test_finds_path_for_branch(self) -> None:
        path = land.find_worktree("/repo", "feat/5-x",
                                  runner=_git_worktree_list("feat/5-x", "/repo/wt"))
        self.assertEqual(path, "/repo/wt")

    def test_none_when_branch_absent(self) -> None:
        path = land.find_worktree("/repo", "feat/9-y",
                                  runner=_git_no_worktree())
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
