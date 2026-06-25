"""The `tracker` command group — issue and PR mechanics, per ADR 0008.

The single namer of the issue tracker. It dispatches on `$ISSUE_TRACKER` to a
backend (`github` is the only backend in this slice; the dispatch is shaped so a
`jira` backend can be added later as a sibling) and exposes the tracker concepts
defined in skills/GITHUB.md: issues, native relations, advisory + CAS claims, PR
and review-thread mechanics, the selection queries, and release publish.

Identity is internal (ADR 0008): the backend resolves the bot identity itself
and performs the `GH_TOKEN` dance on the writes that must appear as the PR
author. The agent never passes or chooses a token.

The backend methods take the `gh` runner as an injectable seam so the logic —
the stale-`mergeable` re-query, merge-method discovery, approval-covers-HEAD —
is unit-tested against canned `gh` JSON without the network. Bodies and untrusted
fields ride stdin (`--body-file -`, `-F field=@-`), never argv (SECURITY.md).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Callable, Mapping, Sequence, TextIO

from adapter import (aclicmd, cli, enums, ghcmd, identity as identity_mod,
                     jira as jira_mod, jiracmd)
from adapter.preflight import preflight

# How long to wait between stale-`mergeable` re-polls, and the poll cap. The
# value settles in a few seconds after a base move; the cap stops an UNKNOWN
# that never settles from spinning forever.
_REQUERY_SLEEP = 2.0
_REQUERY_MAX_POLLS = 10


class GithubBackend:
    """The `gh`-backed implementation of the tracker concepts.

    `repo` is `owner/name`; `runner` is the gh subprocess seam (defaults to the
    real one). `identity` carries the resolved bot identity — its presence
    decides whether author filters and the `GH_TOKEN` dance apply.
    """

    def __init__(self, identity: identity_mod.Identity, repo: str,
                 runner: ghcmd.Runner | None = None) -> None:
        self.identity = identity
        self.repo = repo
        self.runner = runner or ghcmd.run_gh

    # -- internal helpers ----------------------------------------------------

    def _json(self, args: Sequence[str], **kw: Any) -> Any:
        return ghcmd.gh_json(args, runner=self.runner, **kw)

    def _text(self, args: Sequence[str], **kw: Any) -> str:
        return ghcmd.gh_text(args, runner=self.runner, **kw)

    def _api(self, path: str) -> str:
        return f"repos/{self.repo}/{path}"

    def _issue_id(self, number: str) -> str:
        """Resolve an issue's internal id from its opaque id (relations key on id).

        The opaque id stays a string until this gh boundary; GitHub's ids are
        numeric, so the path coerces `int(number)` here, where the value reaches
        the `gh` call — not at the neutral dispatch layer (ADR 0009)."""
        return self._text(
            ["api", self._api(f"issues/{int(number)}"), "--jq", ".id"])

    @staticmethod
    def _neutral_comment(native: Mapping[str, Any]) -> dict[str, Any]:
        """Project a gh comment into the neutral two-zone shape: the author
        login, body text, and creation time at the top level; the native id and
        url ride in the `info` sidecar."""
        author = native.get("author") or {}
        return {
            "author": author.get("login"),
            "body": native.get("body"),
            "created_at": native.get("createdAt"),
            "info": {"id": native.get("id"), "url": native.get("url")},
        }

    @staticmethod
    def _neutral_issue(native: Mapping[str, Any]) -> dict[str, Any]:
        """Project gh's native issue JSON into the neutral two-zone envelope.

        Neutral `id`/`state`/`title`/`labels` sit at the top level — the opaque
        id is the number as a string, the state goes through the closed-vocab
        mapper (raising on an unmapped native value), and labels carry across as
        plain neutral strings. `body` and `comments` are neutral issue content
        (an agent brief lives in one or the other), so they surface at the top
        level whenever the caller fetched them — `issue view` does; `issue list`
        omits both from its field set to stay a lean summary. The native number
        rides in the `info` sidecar, with the url alongside it when fetched.
        """
        number = native["number"]
        info: dict[str, Any] = {}
        if "url" in native:
            info["url"] = native["url"]
        info["number"] = number
        neutral: dict[str, Any] = {
            "id": str(number),
            "state": enums.issue_state(native["state"]),
            "title": native.get("title"),
            "labels": [lbl["name"] for lbl in native.get("labels", [])],
            "info": info,
        }
        if "body" in native:
            neutral["body"] = native["body"]
        if "comments" in native:
            neutral["comments"] = [
                GithubBackend._neutral_comment(c) for c in native["comments"]
            ]
        return neutral

    @staticmethod
    def _number_from_url(url: str) -> int:
        """The trailing issue/PR number in a gh-returned URL.

        gh returns the created issue's html_url (`.../issues/42`) and a comment's
        URL (`.../issues/7#issuecomment-…`); the number is the last path segment,
        before any fragment.

        A URL whose tail is not a number (a malformed or empty gh response) is a
        clear, contextful failure — raise it as one rather than letting a bare
        `int()` ValueError escape with no clue what was being parsed.
        """
        tail = url.split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        if not tail.isdigit():
            raise ValueError(f"no trailing number in gh url: {url!r}")
        return int(tail)

    # -- issues --------------------------------------------------------------

    def issue_create(self, title: str, body: str) -> dict[str, Any]:
        """Create an issue; body on stdin. Returns the contract envelope: the new
        issue's opaque id at top level, its url and number in `info`."""
        url = self._text(
            ["issue", "create", "--repo", self.repo, "--title", title,
             "--body-file", "-"],
            input=body,
        )
        number = self._number_from_url(url)
        return {"outcome": cli.OK, "id": str(number),
                "info": {"url": url, "number": number}}

    def issue_view(self, id: str) -> dict[str, Any]:
        native = self._json(
            ["issue", "view", str(id), "--repo", self.repo,
             "--json", "number,url,title,body,state,labels,assignees,comments"],
        )
        return self._neutral_issue(native)

    def issue_list(self, label: str | None = None,
                   state: str = "open") -> list[dict[str, Any]]:
        args = ["issue", "list", "--repo", self.repo, "--state", state,
                "--json", "number,title,state,labels"]
        if label:
            args += ["--label", label]
        return [self._neutral_issue(i) for i in self._json(args, default=[])]

    def issue_comment(self, id: str, body: str) -> dict[str, Any]:
        url = self._text(
            ["issue", "comment", str(id), "--repo", self.repo, "--body-file", "-"],
            input=body,
        )
        return {"outcome": cli.OK, "id": str(id), "info": {"url": url}}

    def issue_label(self, id: str, add: list[str] | None = None,
                    remove: list[str] | None = None) -> dict[str, Any]:
        args = ["issue", "edit", str(id), "--repo", self.repo]
        for lbl in add or []:
            args += ["--add-label", lbl]
        for lbl in remove or []:
            args += ["--remove-label", lbl]
        self._text(args)
        return {"outcome": cli.OK, "id": str(id),
                "info": {"added": add or [], "removed": remove or []}}

    def issue_close(self, id: str,
                    comment: str | None = None) -> dict[str, Any]:
        args = ["issue", "close", str(id), "--repo", self.repo]
        if comment is not None:
            args += ["--comment", comment]
        self._text(args)
        return {"outcome": cli.OK, "id": str(id), "state": "closed"}

    # -- relations -----------------------------------------------------------

    @staticmethod
    def _neutral_relation(native: Mapping[str, Any]) -> dict[str, Any]:
        """Project a gh relation row (`{number, state}`) into the neutral
        two-zone shape: an opaque string `id` and the closed-vocabulary state.

        Reused across every relation list (sub-issues, blockers, blocking) and
        copied by the sibling slices (#231/#232). The native number becomes the
        opaque id; the state goes through the raise-on-miss mapper.
        """
        return {
            "id": str(native["number"]),
            "state": enums.issue_state(native["state"]),
        }

    def add_sub_issue(self, parent: str, child: str) -> dict[str, Any]:
        """Add `child` as a sub-issue of `parent`.

        Both ids are opaque strings (ADR 0009), coerced to GitHub's native
        number only here at the gh boundary. `sub_issue_id` is the child's
        resolved internal id, typed as an integer with `-F`; a string (`-f`)
        returns HTTP 422. Returns the contract act envelope: a coded `outcome`
        with the native parent/child numbers under `info`.
        """
        child_id = self._issue_id(child)
        self._text(
            ["api", self._api(f"issues/{int(parent)}/sub_issues"),
             "-F", f"sub_issue_id={child_id}"],
        )
        return {"outcome": cli.OK, "info": {"parent": parent, "child": child}}

    def list_sub_issues(self, parent: str) -> list[dict[str, Any]]:
        rows = self._json(
            ["api", self._api(f"issues/{int(parent)}/sub_issues"),
             "--jq", "[.[] | {number, state}]"],
            default=[],
        )
        return [self._neutral_relation(r) for r in rows]

    def remove_sub_issue(self, parent: str, child: str) -> dict[str, Any]:
        child_id = self._issue_id(child)
        self._text(
            ["api", "-X", "DELETE", self._api(f"issues/{int(parent)}/sub_issue"),
             "-F", f"sub_issue_id={child_id}"],
        )
        return {"outcome": cli.OK, "info": {"parent": parent, "child": child}}

    def parent_of(self, number: str) -> int | None:
        """The issue's parent number, or None when it has no parent.

        Takes an opaque string id (ADR 0009), coerced at the gh boundary. The
        `/parent` endpoint 404s (non-zero exit) for an issue with no parent;
        that reads as no parent, not an error. The raw helper internal callers
        (land's epic-close path) use; `parent` wraps it in the neutral contract.
        """
        result = self.runner(
            ["api", self._api(f"issues/{int(number)}/parent"), "--jq", ".number"],
            check=False,
        )
        if result.returncode != 0:
            return None
        text = result.stdout.strip()
        return int(text) if text else None

    def parent(self, child: str) -> dict[str, Any]:
        """The child's parent in the neutral contract shape.

        An issue with a parent reads `{id, outcome: ok}` — the opaque parent id.
        An issue with none reads a coded `noop` (the absence is a result, not an
        error), so a caller branches on the outcome, never on a null `id`.
        """
        number = self.parent_of(child)
        if number is None:
            return {"outcome": cli.NOOP, "message": "issue has no parent"}
        return {"outcome": cli.OK, "id": str(number)}

    def add_blocked_by(self, number: str, blocker: str) -> dict[str, Any]:
        """Record that `number` is blocked by `blocker` (typed `issue_id`).

        Both ids are opaque strings (ADR 0009), coerced to GitHub's native
        number only here at the gh boundary. Returns the contract act envelope:
        a coded `outcome` with the native issue/blocker numbers under `info`.
        """
        blocker_id = self._issue_id(blocker)
        self._text(
            ["api", self._api(f"issues/{int(number)}/dependencies/blocked_by"),
             "-F", f"issue_id={blocker_id}"],
        )
        return {"outcome": cli.OK, "info": {"number": number, "blocker": blocker}}

    def list_blocked_by(self, number: str) -> list[dict[str, Any]]:
        rows = self._json(
            ["api", self._api(f"issues/{int(number)}/dependencies/blocked_by"),
             "--jq", "[.[] | {number, state}]"],
            default=[],
        )
        return [self._neutral_relation(r) for r in rows]

    def list_blocking(self, number: str) -> list[dict[str, Any]]:
        rows = self._json(
            ["api", self._api(f"issues/{int(number)}/dependencies/blocking"),
             "--jq", "[.[] | {number, state}]"],
            default=[],
        )
        return [self._neutral_relation(r) for r in rows]

    # -- claims --------------------------------------------------------------

    def claim_assign(self, number: str) -> dict[str, Any]:
        """Take the advisory assignee claim. Takes an opaque string id (ADR
        0009). Returns the contract act envelope: a coded `outcome` and the
        opaque issue id."""
        self._text(["issue", "edit", str(number), "--repo", self.repo,
                    "--add-assignee", "@me"])
        return {"outcome": cli.OK, "id": str(number)}

    def claim_release(self, number: str) -> dict[str, Any]:
        """Drop the advisory assignee claim. Contract act envelope."""
        self._text(["issue", "edit", str(number), "--repo", self.repo,
                    "--remove-assignee", "@me"])
        return {"outcome": cli.OK, "id": str(number)}

    def claim_holder(self, number: str) -> dict[str, Any]:
        """Who holds the claim. Neutral `id`-keyed result: a held issue reads
        `ok`, an unheld one `noop`; the holder logins ride under `info`."""
        logins = self._text(
            ["issue", "view", str(number), "--repo", self.repo,
             "--json", "assignees", "--jq", ".assignees[].login"],
        )
        holders = logins.splitlines() if logins else []
        return {"outcome": cli.OK if holders else cli.NOOP,
                "id": str(number), "info": {"holders": holders}}

    def claim_since(self, number: str) -> dict[str, Any]:
        """When the claim was taken. Takes an opaque string id (ADR 0009),
        coerced at the gh boundary. Neutral `id`-keyed result: an assigned
        issue reads `ok`, a never-assigned one `noop`; the timestamp (or None)
        rides under `info`."""
        ts = self._text(
            ["api", self._api(f"issues/{int(number)}/timeline"),
             "--jq", '[.[] | select(.event == "assigned")][-1].created_at'],
        )
        since = ts or None
        return {"outcome": cli.OK if since else cli.NOOP,
                "id": str(number), "info": {"since": since}}

    def create_branch_ref(self, branch: str, sha: str) -> dict[str, Any]:
        """Create a branch ref as a compare-and-swap at a commit site.

        The POST returns 422 when the ref already exists — another session
        created it first. That rejection *is* the lost-claim signal, delivered
        by the write itself; it surfaces as a result, not an exception. Any
        other failure still raises.
        """
        result = self.runner(
            ["api", "-X", "POST", self._api("git/refs"),
             "-f", f"ref=refs/heads/{branch}", "-f", f"sha={sha}"],
            check=False,
        )
        if result.returncode == 0:
            return {"outcome": cli.OK, "info": {"branch": branch}}
        # The lost-claim signal is precisely "Reference already exists"; other
        # 422s (a malformed ref, a ref-creation rule) are real failures, not a
        # lost claim, so they raise rather than read as one. The rejection rides
        # the contract `claim_lost` outcome (ADR 0009) — the same closed code the
        # CAS claim methods speak — not a free-text `reason`.
        if "already exists" in result.stderr:
            return {"outcome": cli.CLAIM_LOST, "info": {"branch": branch}}
        raise ghcmd.GhError(result.args, result.returncode, result.stderr)

    # -- PR mechanics --------------------------------------------------------

    def pr_create(self, title: str, body: str) -> dict[str, Any]:
        """Open a PR as the bot (or normal identity when unconfigured).

        The body — carrying the closing reference — rides stdin; the token, when
        configured, rides the child env. Returns the contract act envelope (like
        issue_create): the new PR's opaque id at the top level, its url in the
        `info` sidecar. The id is the number parsed from the returned html_url.
        """
        result = ghcmd.gh_as_author(
            ["pr", "create", "--repo", self.repo, "--title", title,
             "--body-file", "-"],
            self.identity, runner=self.runner, input=body,
        )
        url = result.stdout.strip()
        number = self._number_from_url(url)
        return {"outcome": cli.OK, "id": str(number), "info": {"url": url}}

    def _author_args(self) -> list[str]:
        """The `--author <bot>` filter, or [] when unconfigured (matches any PR)."""
        af = self.identity.author_filter()
        return ["--author", af] if af else []

    @staticmethod
    def _neutral_select_row(native: Mapping[str, Any]) -> dict[str, Any]:
        """Project a gh PR list row into the neutral select shape: an opaque
        string `id` and the `title` at the top level, every native specific
        (headRefName, baseRefName, reviewDecision, createdAt, …) under `info`.

        The shared shape behind the `select` reads (ADR 0009): a consumer takes
        the first `id`, never a native `number`. `reviewDecision`, where carried,
        rides `info` mapped through the closed review-decision vocabulary."""
        info = {k: v for k, v in native.items()
                if k not in ("number", "title")}
        if "reviewDecision" in info:
            info["reviewDecision"] = enums.review_decision(info["reviewDecision"])
        return {"id": str(native["number"]), "title": native.get("title"),
                "info": info}

    def find_rework(self) -> list[dict[str, Any]]:
        """Bot-owned open PRs the maintainer sent back with changes requested.

        Returns neutral id-keyed select rows (ADR 0009); the native headRefName
        and the mapped reviewDecision ride each row's `info` sidecar."""
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "open",
             *self._author_args(),
             "--json", "number,title,reviewDecision,headRefName,body"],
            default=[],
        )
        return [self._neutral_select_row(p) for p in prs
                if p.get("reviewDecision") == "CHANGES_REQUESTED"]

    def merge_state(self, id: str, max_polls: int = _REQUERY_MAX_POLLS,
                    sleep: Callable[[float], None] | None = None) -> dict[str, Any]:
        """Read a PR's mergeability, re-querying past UNKNOWN, in the contract shape.

        `mergeable` is computed asynchronously: after a push, or when the base
        moves under the PR (a sibling landing), a read returns the value against
        the *old* base — often a stale clean — or UNKNOWN until the recompute
        finishes. The loop re-polls the raw `mergeable`/`mergeStateStatus` until
        `mergeStateStatus` leaves UNKNOWN before deciding; the poll cap stops a
        never-settling UNKNOWN from spinning forever.

        Returns the neutral two-zone envelope (ADR 0009): the neutral `state`
        maps the `mergeable` field through the closed merge-state vocabulary —
        and is `"unknown"` when the read never settles (an empty/None mergeable);
        the raw `mergeable` and `mergeStateStatus` ride the `info` sidecar.
        `mergeStateStatus` (CLEAN/BEHIND/BLOCKED/DIRTY/DRAFT — the merge-button
        readiness) has no neutral 3-token equivalent, so it lives in `info` for
        adapter-internal code (land) to route on; no skill reads it.
        """
        sleep = sleep or time.sleep
        raw: dict[str, Any] = {}
        for attempt in range(max_polls):
            raw = self._json(
                ["pr", "view", str(int(id)), "--repo", self.repo,
                 "--json", "mergeable,mergeStateStatus"],
                default={},
            )
            # Settled only when both fields are present and neither is UNKNOWN:
            # `mergeable` is the async-computed value, but `mergeStateStatus` can
            # settle while it is still UNKNOWN, and an empty read leaves both
            # None. Treating any of those as settled would let find_conflicting
            # decide off a value that has not resolved.
            if (raw.get("mergeStateStatus") not in (None, "UNKNOWN")
                    and raw.get("mergeable") not in (None, "UNKNOWN")):
                break
            if attempt < max_polls - 1:
                sleep(_REQUERY_SLEEP)
        mergeable = raw.get("mergeable")
        # An unsettled/empty read carries no neutral state — report `unknown`
        # rather than mapping a None (which UNKNOWN already covers in the table).
        state = enums.merge_state(mergeable) if mergeable else "unknown"
        return {"state": state,
                "info": {"mergeable": mergeable,
                         "merge_state_status": raw.get("mergeStateStatus")}}

    def find_conflicting(
            self, sleep: Callable[[float], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Bot-owned open PRs that no longer merge cleanly onto the base.

        The list read can report a now-conflicting PR as clean (stale), so each
        candidate is re-queried through merge_state — settling past UNKNOWN —
        before it is classified. The output is neutral id-keyed select rows
        (ADR 0009); the settled mergeable/mergeStateStatus ride each row's info.
        """
        # The list's own mergeable/mergeStateStatus are deliberately not fetched:
        # they are the stale values this method exists to defeat. merge_state
        # re-queries each candidate and supplies the settled pair below.
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "open",
             *self._author_args(),
             "--json", "number,title,headRefName,baseRefName"],
            default=[],
        )
        conflicting = []
        for pr in prs:
            st = self.merge_state(pr["number"], sleep=sleep)
            # Classify on the neutral state, or the DIRTY merge-button status
            # (which means a conflict the `mergeable` field can lag behind).
            if (st["state"] == "conflicting"
                    or st["info"]["merge_state_status"] == "DIRTY"):
                row = self._neutral_select_row(pr)
                row["info"].update(st["info"])
                conflicting.append(row)
        return conflicting

    @staticmethod
    def _neutral_review(native: Mapping[str, Any]) -> dict[str, Any]:
        """Project a gh review into the neutral two-zone shape: the author login,
        body, the review state (lowercased native, e.g. `approved`/`commented`/
        `changes_requested`), and submit time at the top level; the native id in
        `info`.

        The per-review `state` is NOT the aggregate review *decision* — a single
        review can be `COMMENTED`, which carries no decision — so it stays a
        plain lowercased string and is never routed through review_decision
        (that maps the PR's aggregate `reviewDecision`, surfaced separately)."""
        author = native.get("author") or {}
        state = native.get("state")
        return {
            "author": author.get("login"),
            "body": native.get("body"),
            "state": state.lower() if isinstance(state, str) else state,
            "submitted_at": native.get("submittedAt"),
            "info": {"id": native.get("id")},
        }

    def read_review(self, id: str) -> dict[str, Any]:
        """Read a PR's review state in the neutral contract shape.

        The aggregate `decision` — the AC's neutral `{approved,
        changes_requested, review_required}` token — sits at the top level,
        mapped from gh's `reviewDecision` (None reads as review_required). The
        review and comment *content* (what the rework brief `pickup` reads) also
        stays neutral at the top level: `comments` through `_neutral_comment`,
        `reviews` through `_neutral_review`.
        """
        native = self._json(
            ["pr", "view", str(int(id)), "--repo", self.repo,
             "--json", "reviewDecision,reviews,comments"],
        )
        return {
            "decision": enums.review_decision(native.get("reviewDecision")),
            "reviews": [self._neutral_review(r)
                        for r in native.get("reviews", [])],
            "comments": [self._neutral_comment(c)
                         for c in native.get("comments", [])],
        }

    def approval_covers_head(self, id: str) -> bool:
        """True when the latest approving review covers the PR's HEAD.

        A force-push after approval leaves the approval standing against the
        commit the reviewer saw, not the one that would merge. The approval is
        current only when a latestReviews node is APPROVED and its commit.oid
        equals headRefOid.
        """
        owner, name = self.repo.split("/", 1)
        query = (
            "query($owner:String!,$repo:String!,$pr:Int!)"
            "{repository(owner:$owner,name:$repo){pullRequest(number:$pr)"
            "{headRefOid latestReviews(first:20){nodes{state author{login} commit{oid}}}}}}"
        )
        data = self._json(
            ["api", "graphql", "-f", f"query={query}",
             "-F", f"owner={owner}", "-F", f"repo={name}", "-F", f"pr={int(id)}"],
        )
        pr = data["data"]["repository"]["pullRequest"]
        head = pr["headRefOid"]
        for node in pr["latestReviews"]["nodes"]:
            if node.get("state") == "APPROVED" and node["commit"]["oid"] == head:
                return True
        return False

    def find_approved(self) -> list[dict[str, Any]]:
        """Bot-owned open PRs a human has approved (a first cut; the caller
        applies approval_covers_head per PR to reject a stale approval, and
        re-reads readiness via merge_state — so `mergeable` is deliberately not
        carried here, where the list read would only ever supply a stale one).

        Returns neutral id-keyed select rows (ADR 0009): `id`/`title` at the top
        level, headRefName/baseRefName and the mapped reviewDecision in `info`.
        land iterates on `pr["id"]` and re-reads readiness per PR."""
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "open",
             *self._author_args(),
             "--json", "number,title,reviewDecision,headRefName,baseRefName,body"],
            default=[],
        )
        return [self._neutral_select_row(p) for p in prs
                if p.get("reviewDecision") == "APPROVED"]

    def sweep_rework(self) -> list[dict[str, Any]]:
        """Compact per-PR rework state across all open bot PRs in one query.

        `auto`'s per-iteration scan: rather than a query per PR, one GraphQL
        search returns each open (bot-owned) PR's open-thread count, its most
        recent review across reviewers (state + time), and its head-commit time.
        The caller decides actionability — an unresolved thread, or a changes-
        requested review postdating HEAD — from these without further reads.
        The author scope rides the search query string passed out-of-band as the
        `q` variable, never spliced into the GraphQL source.
        """
        qstr = f"repo:{self.repo} is:pr is:open"
        af = self.identity.author_filter()
        if af:
            qstr += f" author:{af}"
        query = (
            "query($q:String!){search(query:$q,type:ISSUE,first:100){nodes"
            "{...on PullRequest{number commits(last:1){nodes{commit{committedDate}}} "
            "reviewThreads(first:100){nodes{isResolved}} "
            "latestReviews(first:20){nodes{state submittedAt}}}}}}"
        )
        data = self._json(
            ["api", "graphql", "-f", f"query={query}", "-F", f"q={qstr}"],
            default={},
        )
        nodes = ((data.get("data") or {}).get("search") or {}).get("nodes") or []
        out = []
        for node in nodes:
            if not node:
                continue
            threads = (node.get("reviewThreads") or {}).get("nodes") or []
            unresolved = sum(1 for t in threads if not t.get("isResolved"))
            reviews = (node.get("latestReviews") or {}).get("nodes") or []
            latest = max(reviews, key=lambda r: r.get("submittedAt") or "",
                         default=None)
            commits = (node.get("commits") or {}).get("nodes") or []
            head_at = commits[0]["commit"]["committedDate"] if commits else None
            # The row's signal fields (unresolvedCount/lastReviewState/…) ARE
            # the neutral data `auto` branches on, so they stay at the top level;
            # only the identifier changes from a native `number` to the opaque
            # string `id` (ADR 0009).
            out.append({
                "id": str(node["number"]),
                "unresolvedCount": unresolved,
                "lastReviewState": latest["state"] if latest else None,
                "lastReviewAt": latest["submittedAt"] if latest else None,
                "headAt": head_at,
            })
        return out

    def find_next(self, label: str,
                  state: str = "open") -> list[dict[str, Any]]:
        """Ready candidates for a readiness label: open, carrying the label, and
        not yet claimed (`in-progress`), oldest first.

        The raw candidate pool — a present-shape mechanic. The selection
        *policy* (rework before new work, the label precedence, skipping a
        blocked issue) stays with the caller; this returns the pool it draws on.
        """
        issues = self._json(
            ["issue", "list", "--repo", self.repo, "--state", state,
             "--label", label, "--json", "number,title,labels,createdAt"],
            default=[],
        )
        ready = [
            {"id": str(i["number"]), "title": i["title"],
             "info": {"created_at": i["createdAt"]}}
            for i in issues
            if not any(l["name"] == "in-progress" for l in i.get("labels", []))
        ]
        # Already sorted oldest-first (info.created_at); the caller takes the
        # first `id`. createdAt is a native specific, so it rides info.
        ready.sort(key=lambda i: i["info"]["created_at"])
        return ready

    def is_merged(self, id: str) -> dict[str, Any]:
        """Whether a PR is merged, in the contract result shape: a coded
        `outcome`, the opaque `id`, the neutral `merged` bool at the top level
        (land reads it), and the native merge timestamp under `info`."""
        state = self._json(
            ["pr", "view", str(int(id)), "--repo", self.repo,
             "--json", "state,mergedAt"],
        )
        return {"outcome": cli.OK, "id": str(id),
                "merged": state.get("state") == "MERGED",
                "info": {"merged_at": state.get("mergedAt")}}

    def pr_fields(self, number: int) -> dict[str, Any] | None:
        """The branch refs and body of one PR by number — the row `land apply`
        needs to merge and clean up a single confirmed PR. None when no PR with
        that number exists.

        apply binds to the human-confirmed selection (ADR 0008): it sources each
        selected PR's row through this per-number read rather than re-sweeping
        approved PRs, so a PR approved after the plan can never enter the batch.
        `check=False` makes an absent number return None (reported, not raised)
        rather than aborting the whole selection on one bad number.
        """
        return self._json(
            ["pr", "view", str(number), "--repo", self.repo,
             "--json", "number,headRefName,baseRefName,body"],
            default=None, check=False,
        )

    def merge_method(self, base: str) -> str | None:
        """Discover the allowed merge method for the base branch.

        A branch ruleset can restrict beyond the repo settings, and a disallowed
        method fails only at merge time. Read the base's effective rules: when a
        `pull_request` rule is present, its `allowed_merge_methods` is the
        allowed set; otherwise the repo flags govern. Pick squash if allowed,
        else rebase; never fall through to a merge commit — return None so the
        caller skips the PR instead.
        """
        rules = self._json(
            ["api", self._api(f"rules/branches/{base}")],
            default=[],
        )
        allowed = None
        for rule in rules:
            if rule.get("type") == "pull_request":
                allowed = rule.get("parameters", {}).get("allowed_merge_methods")
                break
        if allowed is None:
            flags = self._json(["api", f"repos/{self.repo}",
                                "--jq", "{allow_squash_merge,allow_merge_commit,allow_rebase_merge}"])
            allowed = []
            if flags.get("allow_squash_merge"):
                allowed.append("squash")
            if flags.get("allow_rebase_merge"):
                allowed.append("rebase")
            if flags.get("allow_merge_commit"):
                allowed.append("merge")
        if "squash" in allowed:
            return "squash"
        if "rebase" in allowed:
            return "rebase"
        return None

    def merge(self, id: str, method: str,
              delete_branch: bool = True) -> dict[str, Any]:
        """Merge a PR with the discovered method. Contract act envelope: a coded
        `outcome`, the opaque `id`, the neutral `merged` bool (land reads it),
        and the merge method under `info`."""
        args = ["pr", "merge", str(int(id)), "--repo", self.repo, f"--{method}"]
        if delete_branch:
            args.append("--delete-branch")
        self._text(args)
        return {"outcome": cli.OK, "id": str(id), "merged": True,
                "info": {"method": method}}

    def closing_refs(self, id: str) -> dict[str, Any]:
        """The issues a PR closes on merge, in the contract result shape: the
        neutral `closes` list (the issue numbers) at the top level, the raw
        `closingIssuesReferences` nodes under `info`. land's apply reads
        `closes` to drive the in-progress strip."""
        native = self._json(
            ["pr", "view", str(int(id)), "--repo", self.repo,
             "--json", "closingIssuesReferences"],
        )
        nodes = native.get("closingIssuesReferences") or []
        return {"outcome": cli.OK, "id": str(id),
                "closes": [n["number"] for n in nodes if "number" in n],
                "info": {"closingIssuesReferences": nodes}}

    # -- review threads ------------------------------------------------------

    def unresolved_threads(self, id: str) -> list[dict[str, Any]]:
        """A PR's unresolved review threads, in the neutral contract shape.

        Each row projects to `{id, comment_id, body, path, author}`: `id` is the
        thread node id — the opaque thread handle `pickup` hands to reply-resolve
        — and `comment_id` is the first comment's databaseId (the reply target).
        `body`/`path`/`author` are neutral review-thread content `pickup` reads
        to drive `field` and the reply. The raw isResolved/nested gh shape is
        dropped; only the unresolved threads come back."""
        owner, name = self.repo.split("/", 1)
        query = (
            "query($owner:String!,$repo:String!,$pr:Int!)"
            "{repository(owner:$owner,name:$repo){pullRequest(number:$pr)"
            "{reviewThreads(first:100){nodes{id isResolved "
            "comments(first:1){nodes{databaseId body path author{login}}}}}}}}"
        )
        data = self._json(
            ["api", "graphql", "-f", f"query={query}",
             "-F", f"owner={owner}", "-F", f"repo={name}", "-F", f"pr={int(id)}"],
        )
        nodes = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
        out = []
        for node in nodes:
            if node["isResolved"]:
                continue
            comments = (node.get("comments") or {}).get("nodes") or []
            first = comments[0] if comments else {}
            author = first.get("author") or {}
            out.append({
                "id": node["id"],
                "comment_id": first.get("databaseId"),
                "body": first.get("body"),
                "path": first.get("path"),
                "author": author.get("login"),
            })
        return out

    def _thread_is_resolved(self, id: str, thread_id: str) -> bool:
        for node in self.unresolved_threads(id):
            if node["id"] == thread_id:
                return False
        return True

    def reply_and_resolve(self, pr: str, comment_id: int, thread_id: str,
                          body: str) -> dict[str, Any]:
        """Post the converged answer to a review thread, then resolve it.

        Sequence per skills/GITHUB.md: reply (body out-of-band on stdin, as the
        bot) → confirm the reply's id → re-read the thread's isResolved → resolve
        only while it is still false. A failed reply raises (no resolve fires);
        an already-resolved thread is skipped, never re-resolved.

        `pr` is the opaque PR id (coerced at the gh boundary); `comment_id` and
        `thread_id` are gh-native handles, kept as-is. Returns the contract act
        envelope: a coded `outcome`, the reply/resolve/skip flags under `info`.
        """
        reply = ghcmd.gh_as_author(
            ["api", self._api(f"pulls/{int(pr)}/comments/{comment_id}/replies"),
             "-F", "body=@-", "--jq", ".id"],
            self.identity, runner=self.runner, input=body,
        )
        reply_id = reply.stdout.strip()
        if not reply_id:
            raise ghcmd.GhError(reply.args, 1, "reply posted no id")

        if self._thread_is_resolved(pr, thread_id):
            return {"outcome": cli.OK,
                    "info": {"replied": True, "reply_id": reply_id,
                             "resolved": False, "skipped": True}}

        mutation = ("mutation($id:ID!){resolveReviewThread(input:{threadId:$id})"
                    "{thread{isResolved}}}")
        ghcmd.gh_as_author(
            ["api", "graphql", "-f", f"query={mutation}", "-F", f"id={thread_id}"],
            self.identity, runner=self.runner,
        )
        return {"outcome": cli.OK,
                "info": {"replied": True, "reply_id": reply_id,
                         "resolved": True, "skipped": False}}

    # -- staleness selection (reap) ------------------------------------------

    def open_pr_for_issue(self, number: int) -> bool:
        """True when an open PR cross-references this issue.

        An issue with an open PR is in review, not abandoned (reap step 1): read
        the issue's timeline for a cross-reference from an open pull request. The
        link is the same signal `closingIssuesReferences` reports on a merge,
        read here from the issue's side while the PR is still open.
        """
        count = self._json(
            ["api", self._api(f"issues/{number}/timeline"),
             "--jq", '[.[] | select(.event == "cross-referenced") '
             '| .source.issue | select(.pull_request != null) '
             '| select(.state == "open")] | length'],
            default=0,
        )
        return int(count or 0) > 0

    def issue_updated_at(self, number: int) -> str | None:
        """The issue's last-update timestamp (ISO 8601), for the quiet check."""
        ts = self._text(
            ["issue", "view", str(number), "--repo", self.repo,
             "--json", "updatedAt", "--jq", ".updatedAt"],
        )
        return ts or None

    def pr_for_branch(self, branch: str) -> dict[str, Any] | None:
        """The PR opened from `branch` and its state, or None when none exists.

        reap matches an orphaned worktree to its PR by the head branch `pickup`
        derived. A branch with no PR reads as None; the caller then decides on
        the remote-existence signal instead. State is lower-snake (`open`,
        `merged`, `closed`).
        """
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "all",
             "--head", branch, "--json", "number,state"],
            default=[],
        )
        if not prs:
            return None
        # A head branch carries at most one open PR; with several historical
        # ones, the open one (if any) decides, else the first listed.
        for pr in prs:
            if pr.get("state") == "OPEN":
                return {"number": pr["number"], "state": "open"}
        pr = prs[0]
        return {"number": pr["number"], "state": pr.get("state", "").lower()}

    def find_stale_claims(self, before: str) -> list[dict[str, Any]]:
        """Claimed issues abandoned by a crashed run, oldest claim first.

        A candidate carries `in-progress`, has no open PR referencing it, and
        was claimed before `before` (an ISO 8601 cutoff the caller derives from
        the threshold). An issue with an open PR is in review — never a
        candidate. Skips ones with no claim timestamp: the label without an
        assignment is a different anomaly, not an abandoned claim.
        """
        issues = self.issue_list(label="in-progress", state="open")
        out: list[dict[str, Any]] = []
        for issue in issues:
            number = issue["info"]["number"]
            since = self.claim_since(str(number))["info"]["since"]
            if since is None or since >= before:
                continue
            if self.open_pr_for_issue(number):
                continue
            holders = self.claim_holder(str(number))["info"]["holders"]
            out.append({"number": number, "title": issue.get("title"),
                        "since": since, "holders": holders})
        out.sort(key=lambda i: i["since"])
        return out

    def find_quiet_needs_info(self, before: str) -> list[dict[str, Any]]:
        """Open needs-info issues whose last activity predates `before`."""
        issues = self.issue_list(label="needs-info", state="open")
        out: list[dict[str, Any]] = []
        for issue in issues:
            number = issue["info"]["number"]
            updated = self.issue_updated_at(number)
            if updated is None or updated >= before:
                continue
            out.append({"number": number, "title": issue.get("title"),
                        "updatedAt": updated})
        out.sort(key=lambda i: i["updatedAt"])
        return out

    def find_stale_epics(self) -> list[dict[str, Any]]:
        """Open epics every one of whose sub-issues is now closed.

        An epic with no children, or any open child, is not a candidate; the
        sub-issue list is carried so the caller can show the evidence.
        """
        epics = self.issue_list(label="epic", state="open")
        out: list[dict[str, Any]] = []
        for epic in epics:
            number = epic["info"]["number"]
            subs = self.list_sub_issues(str(number))
            if subs and all(s.get("state") == "closed" for s in subs):
                out.append({"number": number, "title": epic.get("title"),
                            "subIssues": subs})
        return out

    # -- release -------------------------------------------------------------

    def release_publish(self, tag: str, notes: str) -> dict[str, str]:
        """Publish a GitHub release for an existing tag; notes on stdin, as the
        bot. The tag already exists on main, so gh attaches to it."""
        result = ghcmd.gh_as_author(
            ["release", "create", tag, "--repo", self.repo, "--title", tag,
             "--notes-file", "-"],
            self.identity, runner=self.runner, input=notes,
        )
        return {"url": result.stdout.strip(), "tag": tag}


# --- dispatch ---------------------------------------------------------------

def _resolve_repo(runner: ghcmd.Runner | None) -> str:
    """Discover owner/name from the current clone's origin."""
    return ghcmd.gh_text(["repo", "view", "--json", "nameWithOwner",
                          "--jq", ".nameWithOwner"], runner=runner)


def required_tools(env: Mapping[str, str]) -> tuple[str, ...]:
    """The substrate the active backend shells out to, for the startup preflight.

    Each backend declares its own set so the check never rejects an environment
    over a tool the chosen backend never uses: the GitHub backend drives `gh`,
    the Jira backend drives `acli` for its reads and create/comment/label writes
    and `curl` for the all-REST close path; both need `git`.
    """
    if env.get("ISSUE_TRACKER", "github") == "jira":
        return ("git", "acli", "curl")
    return ("git", "gh")


def run(argv: Sequence[str], env: Mapping[str, str] | None = None,
        runner: ghcmd.Runner | None = None, repo: str | None = None,
        stream: TextIO | None = None, stdin_body: str | None = None,
        jira_curl_runner: jiracmd.Runner | None = None) -> int:
    """Dispatch a tracker command.

    Resolves the backend from `$ISSUE_TRACKER`, resolves the bot identity
    (halting on the half-configured state), and routes to a present or act
    command. `stdin_body` stands in for a piped body in tests; in the binary it
    is read from sys.stdin when a command needs it. `jira_curl_runner` is the
    Jira REST seam, injected so the close path's curl calls run offline in tests.
    """
    env = env if env is not None else os.environ
    stream = stream or sys.stdout

    tracker_kind = env.get("ISSUE_TRACKER", "github")
    if tracker_kind == "github":
        return _run_github(argv, env, runner, repo, stream, stdin_body)
    if tracker_kind == "jira":
        return _run_jira(argv, env, runner, stream, stdin_body, jira_curl_runner)
    return cli.halt(cli.UNSUPPORTED,
                    message=f"unsupported tracker backend: {tracker_kind}",
                    info={"backend": tracker_kind}, stream=stream)


def _run_github(argv: Sequence[str], env: Mapping[str, str],
                runner: ghcmd.Runner | None, repo: str | None,
                stream: TextIO, stdin_body: str | None) -> int:
    # The identity startup check runs before any gh call — a half-configured
    # state must refuse before the adapter shells out, not after.
    try:
        ident = identity_mod.resolve(env)
    except identity_mod.HalfConfigured as exc:
        return cli.halt(cli.UNCONFIGURED, message=str(exc), stream=stream)

    repo = repo or _resolve_repo(runner)
    be = GithubBackend(identity=ident, repo=repo, runner=runner)

    args = _build_parser().parse_args(argv)
    return _route(be, args, stream=stream, stdin_body=stdin_body)


def _run_jira(argv: Sequence[str], env: Mapping[str, str],
              runner: aclicmd.Runner | None, stream: TextIO,
              stdin_body: str | None,
              curl_runner: jiracmd.Runner | None = None) -> int:
    """Dispatch a tracker command to the Jira backend.

    The startup check mirrors the GitHub path's shape: resolve the single
    credential (refusing the incomplete state) and verify `acli` is itself
    authenticated, both before the adapter shells out for the command.
    """
    try:
        credential = aclicmd.resolve_credential(env)
    except aclicmd.CredentialIncomplete as exc:
        return cli.halt(str(exc), stream=stream)
    if not aclicmd.is_authenticated(runner=runner):
        return cli.halt(
            "acli is not authenticated to Jira; run `acli jira auth login`",
            stream=stream)

    project = env.get("JIRA_PROJECT")
    if not project:
        return cli.halt("JIRA_PROJECT is required for the Jira backend",
                        stream=stream)

    be = jira_mod.JiraBackend(
        credential=credential, project=project, runner=runner,
        curl_runner=curl_runner,
        done_resolution=jira_mod.JiraBackend.done_resolution_from(env))
    args = _build_jira_parser().parse_args(argv)
    return _route_jira(be, args, stream=stream, stdin_body=stdin_body)


def _route(be: GithubBackend, args: argparse.Namespace,
           stream: TextIO | None, stdin_body: str | None) -> int:
    group, command = args.group, args.command

    if group == "issue":
        # The issue methods return fully contract-shaped envelopes (the act ones
        # carry their own `outcome`); the dispatcher emits them verbatim.
        if command == "view":
            return cli.present_json(be.issue_view(args.id), stream=stream)
        if command == "list":
            return cli.present_json(
                be.issue_list(label=args.label, state=args.state), stream=stream)
        if command == "create":
            return cli.present_json(be.issue_create(args.title, stdin_body),
                                    stream=stream)
        if command == "comment":
            return cli.present_json(be.issue_comment(args.id, stdin_body),
                                    stream=stream)
        if command == "label":
            return cli.present_json(
                be.issue_label(args.id, add=args.add_label,
                               remove=args.remove_label), stream=stream)
        if command == "close":
            return cli.present_json(
                be.issue_close(args.id, comment=args.comment), stream=stream)

    if group == "relation":
        # The relation methods return fully contract-shaped results (the act ones
        # carry their own `outcome`); the dispatcher emits them verbatim.
        if command == "add-sub":
            return cli.present_json(be.add_sub_issue(args.id, args.child),
                                    stream=stream)
        if command == "list-sub":
            return cli.present_json(be.list_sub_issues(args.id), stream=stream)
        if command == "remove-sub":
            return cli.present_json(be.remove_sub_issue(args.id, args.child),
                                    stream=stream)
        if command == "parent":
            return cli.present_json(be.parent(args.id), stream=stream)
        if command == "add-blocker":
            return cli.present_json(be.add_blocked_by(args.id, args.blocker),
                                    stream=stream)
        if command == "list-blockers":
            return cli.present_json(be.list_blocked_by(args.id), stream=stream)
        if command == "list-blocking":
            return cli.present_json(be.list_blocking(args.id), stream=stream)

    if group == "claim":
        if command == "assign":
            return cli.present_json(be.claim_assign(args.id), stream=stream)
        if command == "release":
            return cli.present_json(be.claim_release(args.id), stream=stream)
        if command == "holder":
            return cli.present_json(be.claim_holder(args.id), stream=stream)
        if command == "since":
            return cli.present_json(be.claim_since(args.id), stream=stream)
        if command == "branch-ref":
            # The method carries its own outcome (ok / claim_lost), so the
            # dispatcher emits it verbatim — matching the CAS claim methods.
            return cli.present_json(be.create_branch_ref(args.branch, args.sha),
                                    stream=stream)

    if group == "pr":
        # The PR methods that self-code their outcome are emitted verbatim via
        # present_json; the two bool/str methods (approval-covers-head,
        # merge-method) are wrapped into a contract envelope here.
        if command == "create":
            return cli.present_json(be.pr_create(args.title, stdin_body),
                                    stream=stream)
        if command == "review":
            return cli.present_json(be.read_review(args.id), stream=stream)
        if command == "merged":
            return cli.present_json(be.is_merged(args.id), stream=stream)
        if command == "closing-refs":
            return cli.present_json(be.closing_refs(args.id), stream=stream)
        if command == "merge-state":
            return cli.present_json(be.merge_state(args.id), stream=stream)
        if command == "approval-covers-head":
            return cli.present_json(
                {"outcome": cli.OK, "id": str(args.id),
                 "covered": be.approval_covers_head(args.id)}, stream=stream)
        if command == "merge-method":
            return cli.present_json(
                {"outcome": cli.OK, "method": be.merge_method(args.base)},
                stream=stream)
        if command == "merge":
            return cli.present_json(be.merge(args.id, args.method), stream=stream)
        if command == "reply-resolve":
            return cli.present_json(
                be.reply_and_resolve(args.id, args.comment_id, args.thread_id,
                                     stdin_body), stream=stream)
        if command == "unresolved-threads":
            return cli.present_json(be.unresolved_threads(args.id), stream=stream)

    if group == "select":
        if command == "rework":
            return cli.present_json(be.find_rework(), stream=stream)
        if command == "conflicting":
            return cli.present_json(be.find_conflicting(), stream=stream)
        if command == "approved":
            return cli.present_json(be.find_approved(), stream=stream)
        if command == "sweep-stale":
            return cli.present_json(be.sweep_rework(), stream=stream)
        if command == "next":
            return cli.present_json(be.find_next(args.label), stream=stream)

    if group == "release":
        if command == "publish":
            return cli.acted(be.release_publish(args.tag, stdin_body), stream=stream)

    return cli.halt(cli.UNSUPPORTED,
                    message=f"unknown command: {group} {command}", stream=stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracker",
        description="Issue and PR mechanics (GitHub backend).",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    # Issues are identified by a single opaque string `--id` (ADR 0009); the
    # backend coerces it to the native number internally.
    issue = groups.add_parser("issue").add_subparsers(dest="command", required=True)
    i_view = issue.add_parser("view"); i_view.add_argument("--id", required=True)
    i_list = issue.add_parser("list"); i_list.add_argument("--label"); i_list.add_argument("--state", default="open")
    i_create = issue.add_parser("create"); i_create.add_argument("--title", required=True)
    i_comment = issue.add_parser("comment"); i_comment.add_argument("--id", required=True)
    i_label = issue.add_parser("label"); i_label.add_argument("--id", required=True)
    i_label.add_argument("--add-label", action="append", default=[])
    i_label.add_argument("--remove-label", action="append", default=[])
    i_close = issue.add_parser("close"); i_close.add_argument("--id", required=True)
    i_close.add_argument("--comment")

    # Relations key on opaque ids (ADR 0009): the subject is `--id`, the related
    # issue `--child`/`--blocker`; the backend coerces each to the native number.
    rel = groups.add_parser("relation").add_subparsers(dest="command", required=True)
    r_as = rel.add_parser("add-sub"); r_as.add_argument("--id", required=True); r_as.add_argument("--child", required=True)
    r_ls = rel.add_parser("list-sub"); r_ls.add_argument("--id", required=True)
    r_rs = rel.add_parser("remove-sub"); r_rs.add_argument("--id", required=True); r_rs.add_argument("--child", required=True)
    r_p = rel.add_parser("parent"); r_p.add_argument("--id", required=True)
    r_ab = rel.add_parser("add-blocker"); r_ab.add_argument("--id", required=True); r_ab.add_argument("--blocker", required=True)
    r_lb = rel.add_parser("list-blockers"); r_lb.add_argument("--id", required=True)
    r_lg = rel.add_parser("list-blocking"); r_lg.add_argument("--id", required=True)

    claim = groups.add_parser("claim").add_subparsers(dest="command", required=True)
    c_a = claim.add_parser("assign"); c_a.add_argument("--id", required=True)
    c_r = claim.add_parser("release"); c_r.add_argument("--id", required=True)
    c_h = claim.add_parser("holder"); c_h.add_argument("--id", required=True)
    c_s = claim.add_parser("since"); c_s.add_argument("--id", required=True)
    c_b = claim.add_parser("branch-ref"); c_b.add_argument("--branch", required=True); c_b.add_argument("--sha", required=True)

    # PRs are identified by a single opaque string `--id` (ADR 0009), like
    # issues; the backend coerces it to the native number at the gh boundary.
    # `--base` is a branch name (not an id); `--comment-id`/`--thread-id` are
    # gh-native review-thread handles, not the opaque PR id.
    pr = groups.add_parser("pr").add_subparsers(dest="command", required=True)
    p_c = pr.add_parser("create"); p_c.add_argument("--title", required=True)
    p_rv = pr.add_parser("review"); p_rv.add_argument("--id", required=True)
    p_m = pr.add_parser("merged"); p_m.add_argument("--id", required=True)
    p_cr = pr.add_parser("closing-refs"); p_cr.add_argument("--id", required=True)
    p_ms = pr.add_parser("merge-state"); p_ms.add_argument("--id", required=True)
    p_ach = pr.add_parser("approval-covers-head"); p_ach.add_argument("--id", required=True)
    p_mm = pr.add_parser("merge-method"); p_mm.add_argument("--base", required=True)
    p_mg = pr.add_parser("merge"); p_mg.add_argument("--id", required=True); p_mg.add_argument("--method", required=True)
    p_rr = pr.add_parser("reply-resolve"); p_rr.add_argument("--id", required=True)
    p_rr.add_argument("--comment-id", type=int, required=True); p_rr.add_argument("--thread-id", required=True)
    p_ut = pr.add_parser("unresolved-threads"); p_ut.add_argument("--id", required=True)

    sel = groups.add_parser("select").add_subparsers(dest="command", required=True)
    sel.add_parser("rework"); sel.add_parser("conflicting"); sel.add_parser("approved")
    sel.add_parser("sweep-stale")
    s_next = sel.add_parser("next"); s_next.add_argument("--label", required=True)

    rel_pub = groups.add_parser("release").add_subparsers(dest="command", required=True)
    rp = rel_pub.add_parser("publish"); rp.add_argument("--tag", required=True)

    return parser


def _route_jira(be: jira_mod.JiraBackend, args: argparse.Namespace,
                stream: TextIO | None, stdin_body: str | None) -> int:
    """Route a parsed command to the Jira backend.

    The symmetric counterpart to _route: the same concept surface, keyed on the
    opaque Jira issue key rather than an integer number.
    """
    group, command = args.group, args.command

    if group == "issue":
        if command == "view":
            return cli.present_json(be.issue_view(args.key), stream=stream)
        if command == "create":
            return cli.acted(
                be.issue_create(args.title, stdin_body, category=args.category),
                stream=stream)
        if command == "comment":
            return cli.acted(be.issue_comment(args.key, stdin_body), stream=stream)
        if command == "label":
            return cli.acted(
                be.issue_label(args.key, add=args.add_label,
                               remove=args.remove_label), stream=stream)
        if command == "close":
            return cli.acted(be.issue_close(args.key), stream=stream)
        if command == "done":
            return cli.present_json({"done": be.is_done(args.key)}, stream=stream)

    return cli.halt(f"unknown command: {group} {command}", stream=stream)


def _build_jira_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracker",
        description="Issue and PR mechanics (Jira backend).",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    issue = groups.add_parser("issue").add_subparsers(dest="command", required=True)
    i_view = issue.add_parser("view"); i_view.add_argument("--key", required=True)
    i_create = issue.add_parser("create"); i_create.add_argument("--title", required=True)
    i_create.add_argument("--category", required=True)
    i_comment = issue.add_parser("comment"); i_comment.add_argument("--key", required=True)
    i_label = issue.add_parser("label"); i_label.add_argument("--key", required=True)
    i_label.add_argument("--add-label", action="append", default=[])
    i_label.add_argument("--remove-label", action="append", default=[])
    i_close = issue.add_parser("close"); i_close.add_argument("--key", required=True)
    i_done = issue.add_parser("done"); i_done.add_argument("--key", required=True)

    return parser


# Commands whose body/notes ride stdin (the out-of-band channel).
_STDIN_COMMANDS: set[tuple[str, str]] = {
    ("issue", "create"), ("issue", "comment"),
    ("pr", "create"), ("pr", "reply-resolve"),
    ("release", "publish"),
}


def main(argv: Sequence[str] | None = None) -> int:
    # The substrate preflight runs first, with the set the active backend shells
    # out to (gh vs acli, both with git) — so a missing tool surfaces as one
    # named blocker before any subprocess, and the check never rejects over a
    # tool the chosen backend never uses.
    rc = preflight(required=required_tools(os.environ))
    if rc != 0:
        return rc

    argv = list(sys.argv[1:] if argv is None else argv)
    # Peek the group/command to decide whether a stdin body is expected, so a
    # body-bearing command reads it before dispatch and the rest never block.
    stdin_body = None
    if len(argv) >= 2 and (argv[0], argv[1]) in _STDIN_COMMANDS:
        stdin_body = sys.stdin.read()
    return run(argv, stdin_body=stdin_body)


if __name__ == "__main__":
    sys.exit(main())
