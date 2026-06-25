"""The `capture` command group — file findings as needs-triage issues.

capture is a **command-launches-agent** (ADR 0008), and this binary is its
deterministic surface: *present* dedupes the findings against open issues and
orders them for the cull; *act* renders each finding's issue body and files it as
`needs-triage`. Neither makes a model's judgment.

The synthesis capture needs — shaping raw observations into findings, and the
clustering judgment — sits *before* present, reached by the host agent in-session
or a spawned subagent under `auto`, and is **skipped entirely** when findings
arrive pre-shaped from an audit. So the binary consumes findings as JSON on
stdin and never synthesises. The issue body is a fixed template over the six
finding fields (contracts/finding.md), so rendering it is deterministic and
belongs here, not behind the agent. That present→synthesis boundary is the
reference the `triage`/`pickup` flips copy: as much as is mechanical lives in the
binary, the agent is reached only for genuine model work.

Composes a neutral tracker-axis backend (ADR 0009) resolved from `$ISSUE_TRACKER`
through the shared `resolve_backend`, reaching only its `issue_list` for the
dedupe read and `issue_create` for the act — taken as a parameter so the dedupe
and the filing are unit-tested against a canned runner without the network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Mapping, Sequence, TextIO

from adapter import cli
from adapter.ghcmd import GhError
from adapter.tracker import IssueTrackerBackend, resolve_backend

# Severity/confidence order the cull (finding.md): a high/high finding leads. An
# unrecognised level sorts last rather than crashing the present of a sibling.
_RANK = {"high": 2, "medium": 1, "low": 0}

# A finding whose title overlaps an open issue's at or above this Jaccard ratio is
# flagged a near-match for the human to judge; an exact normalised-title match is
# a duplicate, dropped from the offer. Title is the only signal in the issue-list
# summary — `Where` lives in the body, which a dedupe read does not fetch.
_NEAR_THRESHOLD = 0.6


def _rank(level: str | None) -> int:
    return _RANK.get((level or "").lower(), -1)


def parse_findings(text: str) -> list[dict[str, Any]]:
    """Parse the findings JSON from stdin: `{"findings": [...]}` or a bare list.

    Every finding needs a title — it becomes the issue title — so a missing one
    is a contract violation the caller surfaces as a halt rather than filing a
    titleless issue. Raises on malformed JSON or a missing title.
    """
    data = json.loads(text)
    findings = data["findings"] if isinstance(data, dict) else data
    if not isinstance(findings, list):
        raise ValueError('findings must be a list or {"findings": [...]}')
    for finding in findings:
        if not isinstance(finding, dict) or not finding.get("title"):
            raise ValueError("every finding needs a title")
    return findings


def render_body(finding: Mapping[str, Any]) -> str:
    """Render a finding's issue body from the contracts/finding.md template.

    A fixed arrangement of the six fields, plus the `Instances` block only on a
    clustered finding and a `Source` defaulting to `ad-hoc`. Deterministic — no
    field is synthesised here; the agent shaped them upstream.
    """
    lines = [
        "## Finding",
        "",
        f"**Dimension:** {finding.get('dimension', '')}",
        f"**Suggested category:** {finding.get('category', '')}",
        f"**Severity:** {finding.get('severity', '')}",
        f"**Confidence:** {finding.get('confidence', '')}",
        "",
        f"**Where:** {finding.get('where', '')}",
        "",
        "**Evidence:**",
        (finding.get("evidence") or "").strip(),
    ]
    instances = finding.get("instances") or []
    if instances:
        lines.append("")
        lines.append("**Instances:**")
        lines.extend(f"- {item}" for item in instances)
    lines.append("")
    lines.append(f"**Source:** {finding.get('source') or 'ad-hoc'}")
    return "\n".join(lines) + "\n"


def _title_tokens(title: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (title or "").lower()))


def _ref(issue: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": issue.get("id"), "title": issue.get("title")}


def match(finding: Mapping[str, Any],
          open_issues: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify a finding against the open issues by title overlap.

    Same normalised word set → `duplicate`; token overlap at or above the
    threshold → `near`; otherwise `new`. Both flags are surfaced in present for
    the human to judge — `duplicate` is a strong signal already-tracked, not a
    silent drop. Title-only — the dedupe read fetches no bodies, so `Where` cannot
    factor in here; the near-match flag is where the human applies it.
    """
    ftok = _title_tokens(finding.get("title"))
    if not ftok:
        return {"status": "new", "issues": []}
    exact: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    for issue in open_issues:
        itok = _title_tokens(issue.get("title"))
        if not itok:
            continue
        if itok == ftok:
            exact.append(_ref(issue))
            continue
        if len(ftok & itok) / len(ftok | itok) >= _NEAR_THRESHOLD:
            near.append(_ref(issue))
    if exact:
        return {"status": "duplicate", "issues": exact}
    if near:
        return {"status": "near", "issues": near}
    return {"status": "new", "issues": []}


def _one_line(text: str | None) -> str:
    """The first non-empty line of the evidence, for the cull summary."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def annotate(findings: Sequence[Mapping[str, Any]],
             open_issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The cull rows: each finding deduped and summarised, ordered by severity
    then confidence (high leads), 1-indexed for the human to pick from."""
    rows = [
        {
            "title": f.get("title"),
            "dimension": f.get("dimension"),
            "where": f.get("where"),
            "severity": f.get("severity"),
            "confidence": f.get("confidence"),
            "evidence": _one_line(f.get("evidence")),
            "clustered": bool(f.get("instances")),
            "match": match(f, open_issues),
        }
        for f in findings
    ]
    rows.sort(key=lambda r: (_rank(r["severity"]), _rank(r["confidence"])),
              reverse=True)
    for index, row in enumerate(rows, start=1):
        row["index"] = index
    return rows


def present(be: IssueTrackerBackend, findings: Sequence[Mapping[str, Any]],
            stream: TextIO | None = None) -> int:
    """Dedupe the findings against open issues and present them for the cull.

    Read-only: the human (or, under `auto`, the confidence floor) decides which
    survive, and `act` files exactly that confirmed set.
    """
    rows = annotate(findings, be.issue_list())
    return cli.present_json({"findings": rows, "count": len(rows)}, stream=stream)


def act(be: IssueTrackerBackend, findings: Sequence[Mapping[str, Any]],
        stream: TextIO | None = None) -> int:
    """File each confirmed finding as a `needs-triage` issue.

    Selection-shaped (ADR 0008): `act` files exactly the findings the cull
    confirmed — the agent passes the survivors, never the full set. It does not
    re-dedupe: a `needs-triage` issue is a reversible entry to a review queue and
    `triage` is the real human gate, so a since-filed duplicate is caught there,
    not worth a second round of reads here. Each issue carries two labels —
    `needs-triage` and the suggested category — front-loading `triage`'s work.

    Each finding files independently: one `gh` failure — a category that isn't a
    real label, a transient API error — is recorded against that finding and the
    rest still file, so a single bad row never aborts the batch and strands the
    issues already created with no report of what got through.
    """
    filed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for finding in findings:
        labels = ["needs-triage"]
        category = (finding.get("category") or "").strip()
        if category:
            labels.append(category)
        try:
            result = be.issue_create(title=finding["title"],
                                     body=render_body(finding), labels=labels)
        except GhError as exc:
            failed.append({"title": finding["title"], "error": str(exc)})
            continue
        filed.append({"title": finding["title"], "id": result["id"],
                      "url": result["info"]["url"], "labels": labels})
    return cli.acted({"filed": filed, "failed": failed,
                      "count": len(filed)}, stream=stream)


# --- dispatch ---------------------------------------------------------------

_COMMANDS = ("present", "act")


def run(argv: Sequence[str], env: Mapping[str, str] | None = None,
        runner: Any = None, repo: str | None = None,
        stream: TextIO | None = None, stdin_body: str | None = None) -> int:
    """Dispatch a capture command.

    Resolves the backend through the shared `resolve_backend` (the single
    `$ISSUE_TRACKER` resolver, which owns the per-backend startup and
    unknown-backend halts), so capture runs under whichever tracker the
    environment selects. Routes to present or act; both read the findings JSON
    from stdin (the out-of-band channel, SECURITY.md), and a parse failure halts
    rather than filing garbage. `runner` and `repo` are injectable for testing.
    """
    env = env if env is not None else os.environ
    stream = stream or sys.stdout

    be, rc = resolve_backend(env, runner=runner, repo=repo, stream=stream)
    if be is None:
        return rc

    args = _build_parser().parse_args(argv)
    if args.command not in _COMMANDS:
        return cli.halt(f"unknown command: {args.command}", stream=stream)

    try:
        findings = parse_findings(stdin_body or "")
    except (ValueError, json.JSONDecodeError) as exc:
        return cli.halt(f"could not parse findings: {exc}", stream=stream)

    if args.command == "present":
        return present(be, findings, stream=stream)
    return act(be, findings, stream=stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capture",
        description="File findings as needs-triage issues (present / act).",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("present",
                   help="dedupe findings against open issues, present for cull")
    sub.add_parser("act", help="file the confirmed findings as needs-triage")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare invocation is the present shape (ADR 0008's side-effect-free default).
    if not argv:
        argv = ["present"]
    # Findings ride stdin on both verbs; guard the tty so a by-hand run without a
    # pipe doesn't block waiting on a terminal.
    stdin_body = "" if sys.stdin.isatty() else sys.stdin.read()
    return run(argv, stdin_body=stdin_body)


if __name__ == "__main__":
    sys.exit(main())
