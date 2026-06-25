"""Tests for the capture command group: the dedupe, the body render, the order,
and the present/act dispatch.

The pure core — `render_body`, `match`, `annotate`, `parse_findings` — is tested
directly. present and act drive the tracker GithubBackend through the same canned
`gh` runner the other adapter tests use, so the dedupe read and the issue filing
are covered against canned JSON, never the network.
"""

from __future__ import annotations

import io
import json
import unittest
from typing import Any, Sequence

from adapter import capture, cli, ghcmd
from adapter.ghcmd import GhError
from adapter.identity import Identity
from adapter.tracker import GithubBackend


class ProgrammedRunner:
    """A run_gh stand-in routing each call to a canned reply keyed by an argv
    substring, popping successive replies for a repeated key and recording every
    call. Mirrors test_reap.py's runner."""

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


def _finding(**over: Any) -> dict[str, Any]:
    base = {
        "title": "Discount branch of OrderTotals.calculate is untested",
        "dimension": "test-gap",
        "category": "enhancement",
        "severity": "medium",
        "confidence": "high",
        "where": "OrderTotals.calculate (path as of audit: src/orders/totals.py)",
        "evidence": "The discount branch is never exercised — rounding unverified.",
        "source": "audit-coverage",
    }
    base.update(over)
    return base


class ParseFindings(unittest.TestCase):
    def test_accepts_envelope(self) -> None:
        out = capture.parse_findings(json.dumps({"findings": [_finding()]}))
        self.assertEqual(len(out), 1)

    def test_accepts_bare_list(self) -> None:
        out = capture.parse_findings(json.dumps([_finding(), _finding()]))
        self.assertEqual(len(out), 2)

    def test_missing_title_raises(self) -> None:
        with self.assertRaises(ValueError):
            capture.parse_findings(json.dumps([{"dimension": "test-gap"}]))

    def test_malformed_json_raises(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            capture.parse_findings("not json")


class RenderBody(unittest.TestCase):
    def test_renders_six_fields(self) -> None:
        body = capture.render_body(_finding())
        self.assertIn("**Dimension:** test-gap", body)
        self.assertIn("**Suggested category:** enhancement", body)
        self.assertIn("**Severity:** medium", body)
        self.assertIn("**Confidence:** high", body)
        self.assertIn("**Where:** OrderTotals.calculate", body)
        self.assertIn("The discount branch is never exercised", body)
        self.assertIn("**Source:** audit-coverage", body)

    def test_omits_instances_when_unclustered(self) -> None:
        self.assertNotIn("**Instances:**", capture.render_body(_finding()))

    def test_includes_instances_when_clustered(self) -> None:
        body = capture.render_body(_finding(
            instances=["order_totals.calculate — discount untested",
                       "order_totals.apply_tax — zero-rate untested"]))
        self.assertIn("**Instances:**", body)
        self.assertIn("- order_totals.calculate — discount untested", body)
        self.assertIn("- order_totals.apply_tax — zero-rate untested", body)

    def test_source_defaults_to_ad_hoc(self) -> None:
        body = capture.render_body(_finding(source=None))
        self.assertIn("**Source:** ad-hoc", body)


class Match(unittest.TestCase):
    def _issues(self, *titles: str) -> list[dict[str, Any]]:
        return [{"id": str(i), "title": t} for i, t in enumerate(titles, 1)]

    def test_new_when_no_overlap(self) -> None:
        out = capture.match(_finding(title="Cache stampede on token refresh"),
                            self._issues("Discount branch untested"))
        self.assertEqual(out["status"], "new")

    def test_duplicate_on_exact_normalised_title(self) -> None:
        out = capture.match(
            _finding(title="Discount branch untested"),
            self._issues("discount   branch untested!"))
        self.assertEqual(out["status"], "duplicate")
        self.assertEqual(out["issues"][0]["id"], "1")

    def test_near_on_token_overlap(self) -> None:
        out = capture.match(
            _finding(title="Discount branch of OrderTotals is untested"),
            self._issues("Discount branch of OrderTotals untested now"))
        self.assertEqual(out["status"], "near")

    def test_duplicate_wins_over_near(self) -> None:
        out = capture.match(
            _finding(title="Discount branch untested"),
            self._issues("Discount branch untested partially",
                         "discount branch untested"))
        self.assertEqual(out["status"], "duplicate")


class Annotate(unittest.TestCase):
    def test_orders_by_severity_then_confidence(self) -> None:
        findings = [
            _finding(title="low one", severity="low", confidence="high"),
            _finding(title="high high", severity="high", confidence="high"),
            _finding(title="high low", severity="high", confidence="low"),
            _finding(title="medium one", severity="medium", confidence="high"),
        ]
        rows = capture.annotate(findings, [])
        self.assertEqual([r["title"] for r in rows],
                         ["high high", "high low", "medium one", "low one"])
        self.assertEqual([r["index"] for r in rows], [1, 2, 3, 4])

    def test_flags_clustered(self) -> None:
        rows = capture.annotate([_finding(instances=["a", "b"])], [])
        self.assertTrue(rows[0]["clustered"])

    def test_evidence_is_one_line(self) -> None:
        rows = capture.annotate(
            [_finding(evidence="\n\nfirst line\nsecond line\n")], [])
        self.assertEqual(rows[0]["evidence"], "first line")


class Present(unittest.TestCase):
    def test_dedupes_against_open_issues_and_emits_rows(self) -> None:
        open_issues = json.dumps([
            {"number": 7, "title": "Discount branch of OrderTotals.calculate is untested",
             "state": "open", "labels": []},
        ])
        runner = ProgrammedRunner({"issue list": (open_issues,)})
        out = io.StringIO()
        rc = capture.present(_backend(runner), [_finding()], stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["findings"][0]["match"]["status"], "duplicate")


class Act(unittest.TestCase):
    def test_files_each_with_two_labels(self) -> None:
        url = "https://github.com/krixon/skills/issues/99"
        runner = ProgrammedRunner({"issue create": (url,)})
        out = io.StringIO()
        rc = capture.act(_backend(runner), [_finding()], stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["filed"][0]["id"], "99")
        self.assertEqual(payload["filed"][0]["labels"], ["needs-triage", "enhancement"])
        # The create carried both labels and the body on stdin.
        create = runner.argvs("issue create")[0]
        self.assertIn("--label", create)
        self.assertIn("needs-triage", create)
        self.assertIn("enhancement", create)
        body = runner.calls[-1]["input"]
        self.assertIn("## Finding", body)

    def test_one_failure_does_not_abort_the_batch(self) -> None:
        # The first finding's create raises (e.g. a category that isn't a real
        # label); the second must still file, and both outcomes are reported.
        ok_url = "https://github.com/krixon/skills/issues/12"
        runner = ProgrammedRunner({
            "--label bogus": ("", 1, "label not found"),
            "issue create": (ok_url,),
        })
        out = io.StringIO()
        rc = capture.act(_backend(runner),
                         [_finding(title="bad one", category="bogus"),
                          _finding(title="good one", category="enhancement")],
                         stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["filed"][0]["title"], "good one")
        self.assertEqual(payload["failed"][0]["title"], "bad one")

    def test_drops_category_label_when_absent(self) -> None:
        url = "https://github.com/krixon/skills/issues/100"
        runner = ProgrammedRunner({"issue create": (url,)})
        out = io.StringIO()
        capture.act(_backend(runner), [_finding(category=None)], stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["filed"][0]["labels"], ["needs-triage"])


class RunDispatch(unittest.TestCase):
    def test_bare_present_reads_stdin_findings(self) -> None:
        open_issues = json.dumps([])
        runner = ProgrammedRunner({"issue list": (open_issues,)})
        out = io.StringIO()
        rc = capture.run(["present"], env={"ISSUE_TRACKER": "github"},
                         runner=runner, repo="krixon/skills",
                         stdin_body=json.dumps([_finding()]), stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["count"], 1)

    def test_act_files_and_reports(self) -> None:
        url = "https://github.com/krixon/skills/issues/5"
        runner = ProgrammedRunner({"issue create": (url,)})
        out = io.StringIO()
        rc = capture.run(["act"], env={"ISSUE_TRACKER": "github"},
                         runner=runner, repo="krixon/skills",
                         stdin_body=json.dumps([_finding()]), stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["filed"][0]["id"], "5")

    def test_unparseable_findings_halt(self) -> None:
        out = io.StringIO()
        rc = capture.run(["present"], env={"ISSUE_TRACKER": "github"},
                         repo="krixon/skills", stdin_body="garbage", stream=out)
        self.assertEqual(rc, cli.HALT_EXIT)

    def test_non_github_tracker_halts(self) -> None:
        out = io.StringIO()
        rc = capture.run(["present"], env={"ISSUE_TRACKER": "jira"},
                         repo="krixon/skills", stdin_body="[]", stream=out)
        self.assertEqual(rc, cli.HALT_EXIT)


if __name__ == "__main__":
    unittest.main()
