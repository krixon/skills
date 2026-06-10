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

import argparse
import os
import sys
import time

from adapter import cli, ghcmd, identity as identity_mod

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

    def __init__(self, identity, repo, runner=None):
        self.identity = identity
        self.repo = repo
        self.runner = runner or ghcmd.run_gh

    # -- internal helpers ----------------------------------------------------

    def _json(self, args, **kw):
        return ghcmd.gh_json(args, runner=self.runner, **kw)

    def _text(self, args, **kw):
        return ghcmd.gh_text(args, runner=self.runner, **kw)

    def _api(self, path):
        return f"repos/{self.repo}/{path}"

    def _issue_id(self, number):
        """Resolve an issue's internal id from its number (relations key on id)."""
        return self._text(["api", self._api(f"issues/{number}"), "--jq", ".id"])

    # -- issues --------------------------------------------------------------

    def issue_create(self, title, body):
        """Create an issue; body on stdin. Returns the new issue's URL."""
        url = self._text(
            ["issue", "create", "--repo", self.repo, "--title", title,
             "--body-file", "-"],
            input=body,
        )
        return {"url": url}

    def issue_view(self, number):
        return self._json(
            ["issue", "view", str(number), "--repo", self.repo,
             "--json", "number,title,body,state,labels,assignees,comments"],
        )

    def issue_list(self, label=None, state="open"):
        args = ["issue", "list", "--repo", self.repo, "--state", state,
                "--json", "number,title,body,labels"]
        if label:
            args += ["--label", label]
        return self._json(args, default=[])

    def issue_comment(self, number, body):
        url = self._text(
            ["issue", "comment", str(number), "--repo", self.repo,
             "--body-file", "-"],
            input=body,
        )
        return {"url": url}

    def issue_label(self, number, add=None, remove=None):
        args = ["issue", "edit", str(number), "--repo", self.repo]
        for lbl in add or []:
            args += ["--add-label", lbl]
        for lbl in remove or []:
            args += ["--remove-label", lbl]
        self._text(args)
        return {"number": number, "added": add or [], "removed": remove or []}

    def issue_close(self, number, comment=None):
        args = ["issue", "close", str(number), "--repo", self.repo]
        if comment is not None:
            args += ["--comment", comment]
        self._text(args)
        return {"number": number, "state": "closed"}

    # -- relations -----------------------------------------------------------

    def add_sub_issue(self, parent, child):
        """Add `child` as a sub-issue of `parent`.

        `sub_issue_id` is the child's resolved internal id, typed as an integer
        with `-F`; a string (`-f`) returns HTTP 422.
        """
        child_id = self._issue_id(child)
        self._text(
            ["api", self._api(f"issues/{parent}/sub_issues"),
             "-F", f"sub_issue_id={child_id}"],
        )
        return {"parent": parent, "child": child}

    def list_sub_issues(self, parent):
        return self._json(
            ["api", self._api(f"issues/{parent}/sub_issues"),
             "--jq", "[.[] | {number, state}]"],
            default=[],
        )

    def remove_sub_issue(self, parent, child):
        child_id = self._issue_id(child)
        self._text(
            ["api", "-X", "DELETE", self._api(f"issues/{parent}/sub_issue"),
             "-F", f"sub_issue_id={child_id}"],
        )
        return {"parent": parent, "child": child}

    def parent_of(self, number):
        """The issue's parent number, or None when it has no parent.

        The `/parent` endpoint 404s (non-zero exit) for an issue with no parent;
        that reads as no parent, not an error.
        """
        result = self.runner(
            ["api", self._api(f"issues/{number}/parent"), "--jq", ".number"],
            check=False,
        )
        if result.returncode != 0:
            return None
        text = result.stdout.strip()
        return int(text) if text else None

    def add_blocked_by(self, number, blocker):
        """Record that `number` is blocked by `blocker` (typed `issue_id`)."""
        blocker_id = self._issue_id(blocker)
        self._text(
            ["api", self._api(f"issues/{number}/dependencies/blocked_by"),
             "-F", f"issue_id={blocker_id}"],
        )
        return {"number": number, "blocker": blocker}

    def list_blocked_by(self, number):
        return self._json(
            ["api", self._api(f"issues/{number}/dependencies/blocked_by"),
             "--jq", "[.[] | {number, state}]"],
            default=[],
        )

    def list_blocking(self, number):
        return self._json(
            ["api", self._api(f"issues/{number}/dependencies/blocking"),
             "--jq", "[.[] | {number, state}]"],
            default=[],
        )

    # -- claims --------------------------------------------------------------

    def claim_assign(self, number):
        self._text(["issue", "edit", str(number), "--repo", self.repo,
                    "--add-assignee", "@me"])
        return {"number": number, "claimed": True}

    def claim_release(self, number):
        self._text(["issue", "edit", str(number), "--repo", self.repo,
                    "--remove-assignee", "@me"])
        return {"number": number, "claimed": False}

    def claim_holder(self, number):
        logins = self._text(
            ["issue", "view", str(number), "--repo", self.repo,
             "--json", "assignees", "--jq", ".assignees[].login"],
        )
        return {"number": number, "holders": logins.splitlines() if logins else []}

    def claim_since(self, number):
        ts = self._text(
            ["api", self._api(f"issues/{number}/timeline"),
             "--jq", '[.[] | select(.event == "assigned")][-1].created_at'],
        )
        return {"number": number, "since": ts or None}

    def create_branch_ref(self, branch, sha):
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
            return {"created": True, "branch": branch}
        if "already exists" in result.stderr or "HTTP 422" in result.stderr:
            return {"created": False, "branch": branch, "reason": "claim-lost"}
        raise ghcmd.GhError(result.args, result.returncode, result.stderr)

    # -- PR mechanics --------------------------------------------------------

    def pr_create(self, title, body):
        """Open a PR as the bot (or normal identity when unconfigured).

        The body — carrying the closing reference — rides stdin; the token, when
        configured, rides the child env. Returns the new PR's URL.
        """
        result = ghcmd.gh_as_author(
            ["pr", "create", "--repo", self.repo, "--title", title,
             "--body-file", "-"],
            self.identity, runner=self.runner, input=body,
        )
        return {"url": result.stdout.strip()}

    def _author_args(self):
        """The `--author <bot>` filter, or [] when unconfigured (matches any PR)."""
        af = self.identity.author_filter()
        return ["--author", af] if af else []

    def find_rework(self):
        """Bot-owned open PRs the maintainer sent back with changes requested."""
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "open",
             *self._author_args(),
             "--json", "number,title,reviewDecision,headRefName,body"],
            default=[],
        )
        return [p for p in prs if p.get("reviewDecision") == "CHANGES_REQUESTED"]

    def merge_state(self, number, max_polls=_REQUERY_MAX_POLLS, sleep=None):
        """Read a PR's `mergeable`/`mergeStateStatus`, re-querying past UNKNOWN.

        `mergeable` is computed asynchronously: after a push, or when the base
        moves under the PR (a sibling landing), a read returns the value against
        the *old* base — often a stale clean — or UNKNOWN until the recompute
        finishes. Re-poll until `mergeStateStatus` leaves UNKNOWN before
        deciding; cap the polls so a never-settling UNKNOWN can't spin forever,
        returning the last read.
        """
        sleep = sleep or time.sleep
        state = None
        for attempt in range(max_polls):
            state = self._json(
                ["pr", "view", str(number), "--repo", self.repo,
                 "--json", "mergeable,mergeStateStatus"],
            )
            if state.get("mergeStateStatus") != "UNKNOWN":
                return state
            if attempt < max_polls - 1:
                sleep(_REQUERY_SLEEP)
        return state

    def find_conflicting(self, sleep=None):
        """Bot-owned open PRs that no longer merge cleanly onto the base.

        The list read can report a now-conflicting PR as clean (stale), so each
        candidate is re-queried through merge_state — settling past UNKNOWN —
        before it is classified.
        """
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "open",
             *self._author_args(),
             "--json", "number,title,mergeable,mergeStateStatus,headRefName,baseRefName"],
            default=[],
        )
        conflicting = []
        for pr in prs:
            state = self.merge_state(pr["number"], sleep=sleep)
            if (state.get("mergeable") == "CONFLICTING"
                    or state.get("mergeStateStatus") == "DIRTY"):
                conflicting.append({**pr, **state})
        return conflicting

    def read_review(self, number):
        return self._json(
            ["pr", "view", str(number), "--repo", self.repo,
             "--json", "reviews,comments"],
        )

    def approval_covers_head(self, number):
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
             "-F", f"owner={owner}", "-F", f"repo={name}", "-F", f"pr={number}"],
        )
        pr = data["data"]["repository"]["pullRequest"]
        head = pr["headRefOid"]
        for node in pr["latestReviews"]["nodes"]:
            if node.get("state") == "APPROVED" and node["commit"]["oid"] == head:
                return True
        return False

    def find_approved(self):
        """Bot-owned open PRs a human has approved (a first cut; the caller
        applies approval_covers_head per PR to reject a stale approval)."""
        prs = self._json(
            ["pr", "list", "--repo", self.repo, "--state", "open",
             *self._author_args(),
             "--json", "number,title,reviewDecision,mergeable,headRefName"],
            default=[],
        )
        return [p for p in prs if p.get("reviewDecision") == "APPROVED"]

    def is_merged(self, number):
        state = self._json(
            ["pr", "view", str(number), "--repo", self.repo,
             "--json", "state,mergedAt"],
        )
        return {"merged": state.get("state") == "MERGED",
                "mergedAt": state.get("mergedAt")}

    def merge_method(self, base):
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

    def merge(self, number, method, delete_branch=True):
        args = ["pr", "merge", str(number), "--repo", self.repo, f"--{method}"]
        if delete_branch:
            args.append("--delete-branch")
        self._text(args)
        return {"number": number, "merged": True, "method": method}

    def closing_refs(self, number):
        return self._json(
            ["pr", "view", str(number), "--repo", self.repo,
             "--json", "closingIssuesReferences"],
        )

    # -- review threads ------------------------------------------------------

    def unresolved_threads(self, number):
        owner, name = self.repo.split("/", 1)
        query = (
            "query($owner:String!,$repo:String!,$pr:Int!)"
            "{repository(owner:$owner,name:$repo){pullRequest(number:$pr)"
            "{reviewThreads(first:100){nodes{id isResolved "
            "comments(first:1){nodes{databaseId body path author{login}}}}}}}}"
        )
        data = self._json(
            ["api", "graphql", "-f", f"query={query}",
             "-F", f"owner={owner}", "-F", f"repo={name}", "-F", f"pr={number}"],
        )
        nodes = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
        return [n for n in nodes if not n["isResolved"]]

    def _thread_is_resolved(self, number, thread_id):
        for node in self.unresolved_threads(number):
            if node["id"] == thread_id:
                return False
        return True

    def reply_and_resolve(self, pr, comment_id, thread_id, body):
        """Post the converged answer to a review thread, then resolve it.

        Sequence per skills/GITHUB.md: reply (body out-of-band on stdin, as the
        bot) → confirm the reply's id → re-read the thread's isResolved → resolve
        only while it is still false. A failed reply raises (no resolve fires);
        an already-resolved thread is skipped, never re-resolved.
        """
        reply = ghcmd.gh_as_author(
            ["api", self._api(f"pulls/{pr}/comments/{comment_id}/replies"),
             "-F", "body=@-", "--jq", ".id"],
            self.identity, runner=self.runner, input=body,
        )
        reply_id = reply.stdout.strip()
        if not reply_id:
            raise ghcmd.GhError(reply.args, 1, "reply posted no id")

        if self._thread_is_resolved(pr, thread_id):
            return {"replied": True, "reply_id": reply_id, "resolved": False,
                    "skipped": True}

        mutation = ("mutation($id:ID!){resolveReviewThread(input:{threadId:$id})"
                    "{thread{isResolved}}}")
        ghcmd.gh_as_author(
            ["api", "graphql", "-f", f"query={mutation}", "-F", f"id={thread_id}"],
            self.identity, runner=self.runner,
        )
        return {"replied": True, "reply_id": reply_id, "resolved": True,
                "skipped": False}

    # -- release -------------------------------------------------------------

    def release_publish(self, tag, notes):
        """Publish a GitHub release for an existing tag; notes on stdin, as the
        bot. The tag already exists on main, so gh attaches to it."""
        result = ghcmd.gh_as_author(
            ["release", "create", tag, "--repo", self.repo, "--title", tag,
             "--notes-file", "-"],
            self.identity, runner=self.runner, input=notes,
        )
        return {"url": result.stdout.strip(), "tag": tag}


# --- dispatch ---------------------------------------------------------------

def _resolve_repo(runner):
    """Discover owner/name from the current clone's origin."""
    return ghcmd.gh_text(["repo", "view", "--json", "nameWithOwner",
                          "--jq", ".nameWithOwner"], runner=runner)


def run(argv, env=None, runner=None, repo=None, stream=None, stdin_body=None):
    """Dispatch a tracker command.

    Resolves the backend from `$ISSUE_TRACKER` (only `github` is built here),
    resolves the bot identity (halting on the half-configured state), and routes
    to a present or act command. `stdin_body` stands in for a piped body in
    tests; in the binary it is read from sys.stdin when a command needs it.
    """
    env = env if env is not None else os.environ
    stream = stream or sys.stdout

    tracker_kind = env.get("ISSUE_TRACKER", "github")
    if tracker_kind != "github":
        return cli.halt(f"unsupported tracker backend: {tracker_kind}",
                        details={"backend": tracker_kind}, stream=stream)

    # The identity startup check runs before any gh call — a half-configured
    # state must refuse before the adapter shells out, not after.
    try:
        ident = identity_mod.resolve(env)
    except identity_mod.HalfConfigured as exc:
        return cli.halt(str(exc), stream=stream)

    repo = repo or _resolve_repo(runner)
    be = GithubBackend(identity=ident, repo=repo, runner=runner)

    args = _build_parser().parse_args(argv)
    return _route(be, args, stream=stream, stdin_body=stdin_body)


def _route(be, args, stream, stdin_body):
    group, command = args.group, args.command

    if group == "issue":
        if command == "view":
            return cli.present_json(be.issue_view(args.number), stream=stream)
        if command == "list":
            return cli.present_json(
                be.issue_list(label=args.label, state=args.state), stream=stream)
        if command == "create":
            return cli.acted(be.issue_create(args.title, stdin_body), stream=stream)
        if command == "comment":
            return cli.acted(be.issue_comment(args.number, stdin_body), stream=stream)
        if command == "label":
            return cli.acted(
                be.issue_label(args.number, add=args.add_label,
                               remove=args.remove_label), stream=stream)
        if command == "close":
            return cli.acted(be.issue_close(args.number, comment=args.comment),
                             stream=stream)

    if group == "relation":
        if command == "add-sub":
            return cli.acted(be.add_sub_issue(args.parent, args.child), stream=stream)
        if command == "list-sub":
            return cli.present_json(be.list_sub_issues(args.parent), stream=stream)
        if command == "remove-sub":
            return cli.acted(be.remove_sub_issue(args.parent, args.child),
                             stream=stream)
        if command == "parent":
            return cli.present_json({"parent": be.parent_of(args.number)},
                                    stream=stream)
        if command == "add-blocker":
            return cli.acted(be.add_blocked_by(args.number, args.blocker),
                             stream=stream)
        if command == "list-blockers":
            return cli.present_json(be.list_blocked_by(args.number), stream=stream)
        if command == "list-blocking":
            return cli.present_json(be.list_blocking(args.number), stream=stream)

    if group == "claim":
        if command == "assign":
            return cli.acted(be.claim_assign(args.number), stream=stream)
        if command == "release":
            return cli.acted(be.claim_release(args.number), stream=stream)
        if command == "holder":
            return cli.present_json(be.claim_holder(args.number), stream=stream)
        if command == "since":
            return cli.present_json(be.claim_since(args.number), stream=stream)
        if command == "branch-ref":
            return cli.acted(be.create_branch_ref(args.branch, args.sha),
                             stream=stream)

    if group == "pr":
        if command == "create":
            return cli.acted(be.pr_create(args.title, stdin_body), stream=stream)
        if command == "review":
            return cli.present_json(be.read_review(args.number), stream=stream)
        if command == "merged":
            return cli.present_json(be.is_merged(args.number), stream=stream)
        if command == "closing-refs":
            return cli.present_json(be.closing_refs(args.number), stream=stream)
        if command == "merge-state":
            return cli.present_json(be.merge_state(args.number), stream=stream)
        if command == "approval-covers-head":
            return cli.present_json(
                {"covered": be.approval_covers_head(args.number)}, stream=stream)
        if command == "merge-method":
            return cli.present_json({"method": be.merge_method(args.base)},
                                    stream=stream)
        if command == "merge":
            return cli.acted(be.merge(args.number, args.method), stream=stream)
        if command == "reply-resolve":
            return cli.acted(
                be.reply_and_resolve(args.number, args.comment_id, args.thread_id,
                                     stdin_body), stream=stream)
        if command == "unresolved-threads":
            return cli.present_json(be.unresolved_threads(args.number), stream=stream)

    if group == "select":
        if command == "rework":
            return cli.present_json(be.find_rework(), stream=stream)
        if command == "conflicting":
            return cli.present_json(be.find_conflicting(), stream=stream)
        if command == "approved":
            return cli.present_json(be.find_approved(), stream=stream)

    if group == "release":
        if command == "publish":
            return cli.acted(be.release_publish(args.tag, stdin_body), stream=stream)

    return cli.halt(f"unknown command: {group} {command}", stream=stream)


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="tracker",
        description="Issue and PR mechanics (GitHub backend).",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    issue = groups.add_parser("issue").add_subparsers(dest="command", required=True)
    i_view = issue.add_parser("view"); i_view.add_argument("--number", type=int, required=True)
    i_list = issue.add_parser("list"); i_list.add_argument("--label"); i_list.add_argument("--state", default="open")
    i_create = issue.add_parser("create"); i_create.add_argument("--title", required=True)
    i_comment = issue.add_parser("comment"); i_comment.add_argument("--number", type=int, required=True)
    i_label = issue.add_parser("label"); i_label.add_argument("--number", type=int, required=True)
    i_label.add_argument("--add-label", action="append", default=[])
    i_label.add_argument("--remove-label", action="append", default=[])
    i_close = issue.add_parser("close"); i_close.add_argument("--number", type=int, required=True)
    i_close.add_argument("--comment")

    rel = groups.add_parser("relation").add_subparsers(dest="command", required=True)
    r_as = rel.add_parser("add-sub"); r_as.add_argument("--parent", type=int, required=True); r_as.add_argument("--child", type=int, required=True)
    r_ls = rel.add_parser("list-sub"); r_ls.add_argument("--parent", type=int, required=True)
    r_rs = rel.add_parser("remove-sub"); r_rs.add_argument("--parent", type=int, required=True); r_rs.add_argument("--child", type=int, required=True)
    r_p = rel.add_parser("parent"); r_p.add_argument("--number", type=int, required=True)
    r_ab = rel.add_parser("add-blocker"); r_ab.add_argument("--number", type=int, required=True); r_ab.add_argument("--blocker", type=int, required=True)
    r_lb = rel.add_parser("list-blockers"); r_lb.add_argument("--number", type=int, required=True)
    r_lg = rel.add_parser("list-blocking"); r_lg.add_argument("--number", type=int, required=True)

    claim = groups.add_parser("claim").add_subparsers(dest="command", required=True)
    c_a = claim.add_parser("assign"); c_a.add_argument("--number", type=int, required=True)
    c_r = claim.add_parser("release"); c_r.add_argument("--number", type=int, required=True)
    c_h = claim.add_parser("holder"); c_h.add_argument("--number", type=int, required=True)
    c_s = claim.add_parser("since"); c_s.add_argument("--number", type=int, required=True)
    c_b = claim.add_parser("branch-ref"); c_b.add_argument("--branch", required=True); c_b.add_argument("--sha", required=True)

    pr = groups.add_parser("pr").add_subparsers(dest="command", required=True)
    p_c = pr.add_parser("create"); p_c.add_argument("--title", required=True)
    p_rv = pr.add_parser("review"); p_rv.add_argument("--number", type=int, required=True)
    p_m = pr.add_parser("merged"); p_m.add_argument("--number", type=int, required=True)
    p_cr = pr.add_parser("closing-refs"); p_cr.add_argument("--number", type=int, required=True)
    p_ms = pr.add_parser("merge-state"); p_ms.add_argument("--number", type=int, required=True)
    p_ach = pr.add_parser("approval-covers-head"); p_ach.add_argument("--number", type=int, required=True)
    p_mm = pr.add_parser("merge-method"); p_mm.add_argument("--base", required=True)
    p_mg = pr.add_parser("merge"); p_mg.add_argument("--number", type=int, required=True); p_mg.add_argument("--method", required=True)
    p_rr = pr.add_parser("reply-resolve"); p_rr.add_argument("--number", type=int, required=True)
    p_rr.add_argument("--comment-id", type=int, required=True); p_rr.add_argument("--thread-id", required=True)
    p_ut = pr.add_parser("unresolved-threads"); p_ut.add_argument("--number", type=int, required=True)

    sel = groups.add_parser("select").add_subparsers(dest="command", required=True)
    sel.add_parser("rework"); sel.add_parser("conflicting"); sel.add_parser("approved")

    rel_pub = groups.add_parser("release").add_subparsers(dest="command", required=True)
    rp = rel_pub.add_parser("publish"); rp.add_argument("--tag", required=True)

    return parser


# Commands whose body/notes ride stdin (the out-of-band channel).
_STDIN_COMMANDS = {
    ("issue", "create"), ("issue", "comment"),
    ("pr", "create"), ("pr", "reply-resolve"),
    ("release", "publish"),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Peek the group/command to decide whether a stdin body is expected, so a
    # body-bearing command reads it before dispatch and the rest never block.
    stdin_body = None
    if len(argv) >= 2 and (argv[0], argv[1]) in _STDIN_COMMANDS:
        stdin_body = sys.stdin.read()
    return run(argv, stdin_body=stdin_body)


if __name__ == "__main__":
    sys.exit(main())
