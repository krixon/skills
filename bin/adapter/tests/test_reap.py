"""Tests for the reap command group: the four-class sweep and the per-item acts.

The sweep (plan) and each act drive the tracker GithubBackend through the same
scripted `gh` runner seam test_tracker.py / test_land.py use, plus a fake git
runner for worktree listing and a fake teardown function — so every staleness
class and every act branch is covered against canned JSON, never the network or
a real checkout. The duration parsing and cutoff arithmetic are pure and tested
directly.
"""

from __future__ import annotations

import io
import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from adapter import ghcmd, reap
from adapter.identity import Identity
from adapter.tracker import GithubBackend


class ProgrammedRunner:
    """A run_gh stand-in routing each call to a canned reply keyed by an argv
    substring, popping successive replies for a repeated key and recording every
    call. Mirrors test_land.py's runner."""

    def __init__(self, routes: dict[str, Any]) -> None:
        # A route value is either a single reply (a str, or a (stdout, rc, stderr)
        # tuple) or a list of replies popped in turn. A bare str/tuple is wrapped
        # so iterating it never walks the string's characters.
        self._routes = {k: [self._norm(v) for v in self._as_list(vs)]
                        for k, vs in routes.items()}
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _as_list(vs: Any) -> list[Any]:
        if isinstance(vs, list):
            return vs
        return [vs]

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


def _issue_list(rows: list[dict[str, Any]]) -> str:
    # issue_list always requests `state` from gh, and the neutral projection
    # (ADR 0009) maps it through the closed vocabulary, so every native row
    # carries one. Default it here; a row may override.
    return json.dumps([{"state": "open", **row} for row in rows])


# --- pure: duration parsing and cutoff --------------------------------------

class TestParseDuration(unittest.TestCase):
    def test_hours_days_weeks(self) -> None:
        self.assertEqual(reap.parse_duration("48h"), timedelta(hours=48))
        self.assertEqual(reap.parse_duration("7d"), timedelta(days=7))
        self.assertEqual(reap.parse_duration("2w"), timedelta(days=14))

    def test_unrecognised_returns_none(self) -> None:
        self.assertIsNone(reap.parse_duration("soon"))
        self.assertIsNone(reap.parse_duration("5"))
        self.assertIsNone(reap.parse_duration("5m"))

    def test_cutoff_subtracts(self) -> None:
        now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(reap.cutoff(now, timedelta(hours=24)),
                         "2026-06-16T12:00:00Z")


# --- abandoned claims -------------------------------------------------------

class TestStaleClaims(unittest.TestCase):
    def test_old_claim_no_pr_is_candidate(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 7, "title": "stale", "labels": []}]),
            "timeline": [
                # claim_since: the assigned event
                "2026-06-01T00:00:00Z",
                # open_pr_for_issue: no cross-referenced open PR
                "0",
            ],
            "assignees": "ghost",
        })
        be = _backend(runner)
        candidates = be.find_stale_claims("2026-06-10T00:00:00Z")
        self.assertEqual([c["number"] for c in candidates], [7])
        self.assertEqual(candidates[0]["holders"], ["ghost"])

    def test_recent_claim_skipped(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 7, "title": "fresh", "labels": []}]),
            "timeline": "2026-06-15T00:00:00Z",
        })
        be = _backend(runner)
        self.assertEqual(be.find_stale_claims("2026-06-10T00:00:00Z"), [])

    def test_open_pr_skipped_as_in_review(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 7, "title": "in-review", "labels": []}]),
            "timeline": ["2026-06-01T00:00:00Z", "1"],  # an open PR cross-ref
        })
        be = _backend(runner)
        self.assertEqual(be.find_stale_claims("2026-06-10T00:00:00Z"), [])

    def test_never_assigned_skipped(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 7, "title": "label-only", "labels": []}]),
            "timeline": "",  # claim_since reads empty -> None
        })
        be = _backend(runner)
        self.assertEqual(be.find_stale_claims("2026-06-10T00:00:00Z"), [])


# --- quiet needs-info -------------------------------------------------------

class TestQuietNeedsInfo(unittest.TestCase):
    def test_quiet_past_threshold_is_candidate(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 9, "title": "quiet", "labels": []}]),
            "updatedAt": "2026-05-01T00:00:00Z",
        })
        be = _backend(runner)
        out = be.find_quiet_needs_info("2026-06-01T00:00:00Z")
        self.assertEqual([i["number"] for i in out], [9])

    def test_recently_active_skipped(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 9, "title": "active", "labels": []}]),
            "updatedAt": "2026-06-15T00:00:00Z",
        })
        be = _backend(runner)
        self.assertEqual(be.find_quiet_needs_info("2026-06-01T00:00:00Z"), [])


# --- stale epics ------------------------------------------------------------

class TestStaleEpics(unittest.TestCase):
    def test_all_children_closed_is_candidate(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 2, "title": "epic", "labels": []}]),
            "sub_issues": json.dumps([{"number": 3, "state": "closed"},
                                      {"number": 4, "state": "closed"}]),
        })
        be = _backend(runner)
        out = be.find_stale_epics()
        self.assertEqual([e["number"] for e in out], [2])
        self.assertEqual(len(out[0]["subIssues"]), 2)

    def test_open_child_not_candidate(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 2, "title": "epic", "labels": []}]),
            "sub_issues": json.dumps([{"number": 3, "state": "open"}]),
        })
        be = _backend(runner)
        self.assertEqual(be.find_stale_epics(), [])

    def test_childless_epic_not_candidate(self) -> None:
        runner = ProgrammedRunner({
            "issue list": _issue_list([{"number": 2, "title": "lonely", "labels": []}]),
            "sub_issues": json.dumps([]),
        })
        be = _backend(runner)
        self.assertEqual(be.find_stale_epics(), [])


# --- orphaned worktrees -----------------------------------------------------

class FakeGit:
    """A run_git stand-in: canned `worktree list --porcelain` and ls-remote."""

    def __init__(self, porcelain: str, remote_branches: set[str]) -> None:
        self.porcelain = porcelain
        self.remote_branches = remote_branches

    def __call__(self, args: Sequence[str], cwd: str | None = None,
                 check: bool = True) -> subprocess.CompletedProcess:
        joined = " ".join(args)
        if "worktree list" in joined:
            return subprocess.CompletedProcess(args, 0, self.porcelain, "")
        if "ls-remote" in joined:
            branch = args[-1]
            rc = 0 if branch in self.remote_branches else 2
            return subprocess.CompletedProcess(args, rc, "", "")
        raise AssertionError(f"no canned git route: {joined}")


_PORCELAIN = (
    "worktree /repo\nbranch refs/heads/main\n\n"
    "worktree /repo/.claude/worktrees/feat-9-x\nbranch refs/heads/feat/9-x\n\n"
)


class TestOrphanedWorktrees(unittest.TestCase):
    def test_merged_pr_is_orphaned(self) -> None:
        git = FakeGit(_PORCELAIN, remote_branches=set())
        runner = ProgrammedRunner({
            "pr list": json.dumps([{"number": 12, "state": "MERGED"}]),
        })
        be = _backend(runner)
        out = reap.find_orphaned_worktrees(be, "/repo", runner=git)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["branch"], "feat/9-x")
        self.assertEqual(out[0]["reason"], "pr-merged")

    def test_open_pr_is_live_work(self) -> None:
        git = FakeGit(_PORCELAIN, remote_branches={"feat/9-x"})
        runner = ProgrammedRunner({
            "pr list": json.dumps([{"number": 12, "state": "OPEN"}]),
        })
        be = _backend(runner)
        self.assertEqual(reap.find_orphaned_worktrees(be, "/repo", runner=git), [])

    def test_no_pr_gone_from_remote_is_orphaned(self) -> None:
        git = FakeGit(_PORCELAIN, remote_branches=set())
        runner = ProgrammedRunner({"pr list": json.dumps([])})
        be = _backend(runner)
        out = reap.find_orphaned_worktrees(be, "/repo", runner=git)
        self.assertEqual(out[0]["reason"], "no-pr-no-remote")

    def test_no_pr_still_on_remote_kept(self) -> None:
        git = FakeGit(_PORCELAIN, remote_branches={"feat/9-x"})
        runner = ProgrammedRunner({"pr list": json.dumps([])})
        be = _backend(runner)
        self.assertEqual(reap.find_orphaned_worktrees(be, "/repo", runner=git), [])

    def test_repo_root_never_listed(self) -> None:
        git = FakeGit(_PORCELAIN, remote_branches=set())
        wts = reap.list_worktrees("/repo", runner=git)
        self.assertEqual([w["branch"] for w in wts], ["feat/9-x"])


# --- per-item acts ----------------------------------------------------------

class TestReapClaim(unittest.TestCase):
    def test_release_and_strip_on_still_stale(self) -> None:
        runner = ProgrammedRunner({
            "timeline": ["2026-06-01T00:00:00Z", "0"],  # since, then no open PR
            "issue edit": ["", ""],  # remove-assignee, then remove-label
        })
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_claim(be, 7, "2026-06-10T00:00:00Z", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["released"])
        self.assertEqual(payload["labelStripped"], "in-progress")
        # both writes issued: unassign and label removal
        self.assertTrue(runner.argvs("--remove-assignee"))
        self.assertTrue(runner.argvs("--remove-label"))

    def test_halts_when_claim_refreshed(self) -> None:
        runner = ProgrammedRunner({"timeline": "2026-06-15T00:00:00Z"})
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_claim(be, 7, "2026-06-10T00:00:00Z", stream=out)
        self.assertEqual(rc, cli_halt_code())
        self.assertEqual(json.loads(out.getvalue())["status"], "halted")
        self.assertEqual(runner.argvs("--remove-assignee"), [])

    def test_halts_when_pr_opened_since(self) -> None:
        runner = ProgrammedRunner({
            "timeline": ["2026-06-01T00:00:00Z", "1"],  # old claim, but open PR now
        })
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_claim(be, 7, "2026-06-10T00:00:00Z", stream=out)
        self.assertEqual(rc, cli_halt_code())
        self.assertEqual(runner.argvs("--remove-assignee"), [])


class TestReapNeedsInfo(unittest.TestCase):
    def test_re_ping_comments(self) -> None:
        runner = ProgrammedRunner({"issue comment": "https://gh/c/1"})
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_needs_info(be, 9, "re-ping", body="still need this?", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["action"], "re-ping")
        # body rode stdin, not argv
        comment = runner.argvs("issue comment")[0]
        self.assertIn("--body-file", comment)
        self.assertEqual(runner.calls[0]["input"], "still need this?")

    def test_close(self) -> None:
        runner = ProgrammedRunner({"issue close": ""})
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_needs_info(be, 9, "close", stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["action"], "close")


class TestReapWorktree(unittest.TestCase):
    def test_tears_down_via_seam(self) -> None:
        recorded: dict[str, Any] = {}

        def fake_teardown(repo_root: str, path: str, branch: str, stream=None) -> int:
            recorded.update(repo_root=repo_root, path=path, branch=branch)
            return 0

        out = io.StringIO()
        rc = reap.reap_worktree("/repo", "/repo/.claude/worktrees/feat-9-x",
                                "feat/9-x", teardown=fake_teardown, stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(recorded["branch"], "feat/9-x")
        self.assertTrue(json.loads(out.getvalue())["tornDown"])


class TestReapEpic(unittest.TestCase):
    def test_closes_when_all_children_closed(self) -> None:
        runner = ProgrammedRunner({
            "sub_issues": json.dumps([{"number": 3, "state": "closed"}]),
            "issue close": "",
        })
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_epic(be, 2, stream=out)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out.getvalue())["closed"])

    def test_halts_when_child_reopened(self) -> None:
        runner = ProgrammedRunner({
            "sub_issues": json.dumps([{"number": 3, "state": "open"}]),
        })
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_epic(be, 2, stream=out)
        self.assertEqual(rc, cli_halt_code())
        self.assertEqual(runner.argvs("issue close"), [])

    def test_halts_when_no_children(self) -> None:
        runner = ProgrammedRunner({"sub_issues": json.dumps([])})
        be = _backend(runner)
        out = io.StringIO()
        rc = reap.reap_epic(be, 2, stream=out)
        self.assertEqual(rc, cli_halt_code())


# --- dispatch (plan present shape) ------------------------------------------

class TestPlanDispatch(unittest.TestCase):
    def test_plan_emits_four_buckets(self) -> None:
        now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        # No candidates in any class: each issue-list read is empty, no worktrees.
        runner = ProgrammedRunner({"issue list": json.dumps([])})
        git = FakeGit("worktree /repo\nbranch refs/heads/main\n\n", set())
        be = _backend(runner)
        out = io.StringIO()
        reap.plan(be, "/repo", timedelta(hours=24), timedelta(days=14),
                  now=now, worktree_runner=git, stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(set(payload), {"abandoned_claims", "quiet_needs_info",
                                        "orphaned_worktrees", "stale_epics"})

    def test_unknown_tracker_halts(self) -> None:
        out = io.StringIO()
        rc = reap.run(["plan"], env={"ISSUE_TRACKER": "gitlab"}, stream=out)
        self.assertEqual(rc, cli_halt_code())


def cli_halt_code() -> int:
    from adapter import cli
    return cli.HALT_EXIT


if __name__ == "__main__":
    unittest.main()
