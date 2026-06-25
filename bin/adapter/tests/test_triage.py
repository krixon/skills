"""Tests for the triage command group: the queue partition, the candidate
context read, the claim guard, and the state-machine transitions.

The pure partition (`gather`, `_states_on`, `_set_state`) is covered through the
present/act functions, which drive the tracker GithubBackend over the same canned
`gh` runner the other adapter tests use — so the queue read, the claim reads, and
every transition's label diff and comment/close are covered against canned JSON,
never the network.
"""

from __future__ import annotations

import io
import json
import unittest
from typing import Any, Sequence

from adapter import cli, ghcmd, triage
from adapter.identity import Identity
from adapter.tracker import GithubBackend


class ProgrammedRunner:
    """A run_gh stand-in routing each call to a canned reply keyed by an argv
    substring, popping successive replies for a repeated key and recording every
    call. Mirrors test_capture.py / test_reap.py's runner."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self._routes = {k: [self._norm(v) for v in self._as_list(vs)]
                        for k, vs in routes.items()}
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _as_list(vs: Any) -> list[Any]:
        return vs if isinstance(vs, list) else [vs]

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


def _issue(number: int, title: str, labels: list[str]) -> dict[str, Any]:
    return {"number": number, "title": title, "state": "open",
            "labels": [{"name": n} for n in labels]}


def _view(number: int, title: str, labels: list[str],
          body: str = "", comments: list[dict[str, Any]] | None = None,
          assignees: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {"number": number, "url": f"https://x/{number}", "title": title,
            "body": body, "state": "open",
            "labels": [{"name": n} for n in labels],
            "assignees": assignees or [],
            "comments": comments or []}


class Gather(unittest.TestCase):
    def test_partitions_into_actionable_buckets(self) -> None:
        listing = json.dumps([
            _issue(1, "never triaged", []),
            _issue(2, "in triage", ["needs-triage", "bug"]),
            _issue(3, "awaiting reporter", ["needs-info"]),
            _issue(4, "already ready", ["ready-for-agent"]),
        ])
        # No issue carries assignees → no claim holders, nothing held aside.
        runner = ProgrammedRunner({
            "issue list": (listing,),
            "assignees": ("",),
            "timeline": ("",),
        })
        out = io.StringIO()
        rc = triage.present(_backend(runner), None, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual([r["id"] for r in payload["unlabeled"]], ["1"])
        self.assertEqual([r["id"] for r in payload["needs_triage"]], ["2"])
        self.assertEqual([r["id"] for r in payload["needs_info"]], ["3"])
        # A ready issue is past triage and in no actionable bucket.
        self.assertEqual(payload["counts"]["claimed_elsewhere"], 0)

    def test_claimed_issue_held_aside_not_actionable(self) -> None:
        listing = json.dumps([_issue(7, "held", ["needs-triage"])])
        runner = ProgrammedRunner({
            "issue list": (listing,),
            # claim_holder reads assignees via issue view --json assignees
            "--json assignees": ("someone\n",),
            "timeline": ("2026-06-01T00:00:00Z\n",),
        })
        out = io.StringIO()
        triage.present(_backend(runner), None, stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["counts"]["needs_triage"], 0)
        self.assertEqual(payload["counts"]["claimed_elsewhere"], 1)
        held = payload["claimed_elsewhere"][0]
        self.assertEqual(held["id"], "7")
        self.assertEqual(held["holders"], ["someone"])
        self.assertEqual(held["since"], "2026-06-01T00:00:00Z")


class Candidate(unittest.TestCase):
    def test_present_id_surfaces_full_context_and_claim(self) -> None:
        view = json.dumps(_view(42, "a bug", ["needs-triage", "bug"],
                                body="repro steps",
                                comments=[{"author": {"login": "r"},
                                           "body": "more", "createdAt": "t",
                                           "id": "c1", "url": "u"}]))
        runner = ProgrammedRunner({
            "issue view 42 --repo krixon/skills --json number": (view,),
            "--json assignees": ("",),
            "timeline": ("",),
        })
        out = io.StringIO()
        rc = triage.present(_backend(runner), "42", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["id"], "42")
        self.assertEqual(payload["body"], "repro steps")
        self.assertEqual(payload["current_states"], ["needs-triage"])
        self.assertEqual(payload["claim"]["holders"], [])


class Claim(unittest.TestCase):
    def test_claims_unheld_issue(self) -> None:
        runner = ProgrammedRunner({
            "--json assignees": ("",),
            "issue edit 5 --repo krixon/skills --add-assignee": ("",),
        })
        out = io.StringIO()
        rc = triage.claim(_backend(runner), "5", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["claimed"])
        self.assertIn("--add-assignee", runner.argvs("issue edit 5")[0])

    def test_held_issue_halts_without_force(self) -> None:
        runner = ProgrammedRunner({
            "--json assignees": ("holder\n",),
            "timeline": ("2026-06-01T00:00:00Z\n",),
        })
        out = io.StringIO()
        rc = triage.claim(_backend(runner), "5", stream=out)
        self.assertEqual(rc, cli.HALT_EXIT)
        # No assign write was attempted.
        self.assertEqual(runner.argvs("--add-assignee"), [])

    def test_force_takes_a_held_issue(self) -> None:
        runner = ProgrammedRunner({
            "--json assignees": ("holder\n",),
            "issue edit 5 --repo krixon/skills --add-assignee": ("",),
        })
        out = io.StringIO()
        rc = triage.claim(_backend(runner), "5", force=True, stream=out)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out.getvalue())["claimed"])
        self.assertEqual(len(runner.argvs("--add-assignee")), 1)

    def test_release_drops_the_claim(self) -> None:
        runner = ProgrammedRunner({
            "issue edit 5 --repo krixon/skills --remove-assignee": ("",),
        })
        out = io.StringIO()
        rc = triage.release(_backend(runner), "5", stream=out)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out.getvalue())["released"])
        self.assertIn("--remove-assignee", runner.argvs("issue edit 5")[0])


class Transition(unittest.TestCase):
    def test_promote_swaps_state_and_posts_brief(self) -> None:
        view = json.dumps(_view(9, "feat", ["needs-triage", "enhancement"]))
        runner = ProgrammedRunner({
            "issue view 9 --repo krixon/skills --json number": (view,),
            "issue edit 9 --repo krixon/skills": ("",),
            "issue comment 9": ("https://x/9#c",),
        })
        out = io.StringIO()
        rc = triage.transition(_backend(runner), "9", "ready-for-agent",
                               category="enhancement",
                               body="## Agent Brief\n...", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["state"], "ready-for-agent")
        self.assertTrue(payload["commented"])
        self.assertIn("ready-for-agent", payload["added"])
        self.assertIn("needs-triage", payload["removed"])
        # The brief rode stdin on the comment, not argv.
        comment = next(c for c in runner.calls
                       if "issue comment 9" in " ".join(map(str, c["args"])))
        self.assertIn("Agent Brief", comment["input"])

    def test_promote_applies_priority_label(self) -> None:
        view = json.dumps(_view(9, "feat", ["needs-triage"]))
        runner = ProgrammedRunner({
            "issue view 9 --repo krixon/skills --json number": (view,),
            "issue edit 9 --repo krixon/skills": ("",),
            "issue comment 9": ("https://x/9#c",),
        })
        out = io.StringIO()
        triage.transition(_backend(runner), "9", "ready-for-agent",
                          priority="priority:high", body="brief", stream=out)
        edit = runner.argvs("issue edit 9")[0]
        self.assertIn("priority:high", edit)
        self.assertIn("--add-label", edit)

    def test_needs_info_transition_without_priority(self) -> None:
        view = json.dumps(_view(3, "bug", ["needs-triage", "bug"]))
        runner = ProgrammedRunner({
            "issue view 3 --repo krixon/skills --json number": (view,),
            "issue edit 3 --repo krixon/skills": ("",),
            "issue comment 3": ("https://x/3#c",),
        })
        out = io.StringIO()
        rc = triage.transition(_backend(runner), "3", "needs-info",
                               body="## Triage Notes\n...", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["state"], "needs-info")
        self.assertIn("needs-info", payload["added"])
        self.assertIn("needs-triage", payload["removed"])

    def test_wontfix_state_is_rejected_by_transition(self) -> None:
        # wontfix closes the issue — that is `reject`, not `transition`.
        out = io.StringIO()
        rc = triage.transition(_backend(ProgrammedRunner({})), "1", "wontfix",
                               stream=out)
        self.assertEqual(rc, cli.HALT_EXIT)

    def test_transition_without_body_skips_comment(self) -> None:
        view = json.dumps(_view(9, "feat", ["needs-triage"]))
        runner = ProgrammedRunner({
            "issue view 9 --repo krixon/skills --json number": (view,),
            "issue edit 9 --repo krixon/skills": ("",),
        })
        out = io.StringIO()
        triage.transition(_backend(runner), "9", "ready-for-human", stream=out)
        self.assertFalse(json.loads(out.getvalue())["commented"])
        self.assertEqual(runner.argvs("issue comment"), [])


class Reject(unittest.TestCase):
    def test_applies_wontfix_and_closes_with_reason(self) -> None:
        view = json.dumps(_view(8, "spam", ["needs-triage", "enhancement"]))
        runner = ProgrammedRunner({
            "issue view 8 --repo krixon/skills --json number": (view,),
            "issue edit 8 --repo krixon/skills": ("",),
            "issue close 8": ("",),
        })
        out = io.StringIO()
        rc = triage.reject(_backend(runner), "8", category="enhancement",
                           body="out of scope", stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["state"], "wontfix")
        self.assertTrue(payload["closed"])
        self.assertTrue(payload["commented"])
        self.assertIn("wontfix", payload["added"])
        self.assertIn("needs-triage", payload["removed"])
        close = runner.argvs("issue close 8")[0]
        self.assertIn("--comment", close)
        self.assertIn("out of scope", close)

    def test_reject_without_reason_closes_uncommented(self) -> None:
        view = json.dumps(_view(8, "spam", ["needs-triage"]))
        runner = ProgrammedRunner({
            "issue view 8 --repo krixon/skills --json number": (view,),
            "issue edit 8 --repo krixon/skills": ("",),
            "issue close 8": ("",),
        })
        out = io.StringIO()
        triage.reject(_backend(runner), "8", stream=out)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["commented"])
        self.assertNotIn("--comment", runner.argvs("issue close 8")[0])


class RunDispatch(unittest.TestCase):
    def test_bare_present_lists_the_queue(self) -> None:
        listing = json.dumps([_issue(1, "x", [])])
        runner = ProgrammedRunner({
            "issue list": (listing,),
            "assignees": ("",),
        })
        out = io.StringIO()
        rc = triage.run(["present"], env={"ISSUE_TRACKER": "github"},
                        runner=runner, repo="krixon/skills", stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["counts"]["unlabeled"], 1)

    def test_transition_reads_body_from_stdin(self) -> None:
        view = json.dumps(_view(9, "feat", ["needs-triage"]))
        runner = ProgrammedRunner({
            "issue view 9 --repo krixon/skills --json number": (view,),
            "issue edit 9 --repo krixon/skills": ("",),
            "issue comment 9": ("https://x/9#c",),
        })
        out = io.StringIO()
        rc = triage.run(["transition", "--id", "9", "--state", "ready-for-agent"],
                        env={"ISSUE_TRACKER": "github"}, runner=runner,
                        repo="krixon/skills", stdin_body="## Agent Brief\nbody",
                        stream=out)
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out.getvalue())["commented"])

    def test_unknown_command_halts(self) -> None:
        out = io.StringIO()
        rc = triage.run(["frobnicate"], env={"ISSUE_TRACKER": "github"},
                        repo="krixon/skills", stream=out)
        self.assertEqual(rc, cli.HALT_EXIT)

    def test_non_github_tracker_halts(self) -> None:
        out = io.StringIO()
        rc = triage.run(["present"], env={"ISSUE_TRACKER": "jira"},
                        repo="krixon/skills", stream=out)
        self.assertEqual(rc, cli.HALT_EXIT)


if __name__ == "__main__":
    unittest.main()
