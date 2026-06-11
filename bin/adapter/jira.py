"""The `acli`-backed Jira implementation of the tracker concepts, per ADR 0008.

Sibling of the `GithubBackend` in `tracker.py` and symmetric with it: the same
tracker-neutral concept surface, mapped to Jira primitives rather than GitHub
ones. It shells out to `acli jira` for everything acli can do, and makes exactly
one urllib REST call — `aclicmd.fetch_transitions` — for the one thing acli
cannot: enumerate an issue's reachable transitions.

The concept→primitive map (ADR 0008): category and structure labels become Jira
issue types, the workflow/triage state labels carry across as Jira labels, and
the execution/closure states resolve through the platform-stable status category
rather than a status name. The issue id is an opaque string (the Jira key); the
branch name is the truth-of-record link, and the key rides the PR title's
Conventional-Commits description — both owned by the skills that consume this
backend, not by the mechanics here.

The category invariant (ADR 0008): a status is *read* by its
`statusCategory.key` (`new` / `indeterminate` / `done`), never by name, because
the key is platform-stable while a project can rename "In Progress" freely. A
status *transition* resolves the target category to a concrete reachable status
name at call time via the /transitions fetch, then transitions by that name —
so a workflow rename can never break the binding to a hard-coded name.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from adapter import aclicmd

# Category/structure label → Jira issue type. The two category labels (bug,
# enhancement) and the one structure label (epic) name a kind of work; Jira
# expresses that kind as an issue type. enhancement maps to Story — the default
# deliverable type — rather than Task, matching the "feature work" sense the
# enhancement category carries in this workflow.
_ISSUE_TYPE = {
    "bug": "Bug",
    "enhancement": "Story",
    "epic": "Epic",
}

# The platform-stable status category keys. A status read resolves to one of
# these via `.fields.status.statusCategory.key`; a transition targets one of the
# two non-initial keys. Never a status name.
CATEGORY_NEW = "new"
CATEGORY_INDETERMINATE = "indeterminate"
CATEGORY_DONE = "done"


class NoSuchTransition(RuntimeError):
    """No reachable transition carries the requested target category.

    The project's workflow offers no path from the issue's current status to one
    in the target category — a real blocker the caller surfaces, not a default
    the mechanics invent.
    """


def issue_type_for(label: str) -> str | None:
    """The Jira issue type for a category or structure label, or None if the
    label names no kind of work (so the caller can fall back or refuse)."""
    return _ISSUE_TYPE.get(label)


def pr_title(kind: str, description: str, key: str) -> str:
    """A Conventional-Commits PR title with the Jira key in the description.

    The key rides the title's description — `<kind>: <description> (<KEY>)` — so
    the PR carries its issue link visibly, mirroring the GitHub backend's
    `Closes #n` placement. The branch name remains the truth-of-record link;
    this is the human-readable echo of it.
    """
    return f"{kind}: {description} ({key})"


def label_for(label: str) -> str:
    """The Jira label for a workflow/triage state label.

    The state labels (needs-triage, ready-for-agent, in-progress, …) are the
    workflow's own state machine, not Jira primitives, so they carry across as
    Jira labels verbatim — the identity mapping, named so callers route through
    one place rather than assuming it.
    """
    return label


class JiraBackend:
    """The `acli`-backed implementation of the tracker concepts.

    `project` is the Jira project key (e.g. `PROJ`); `credential` is the single
    `(site, email, api_token)` source the /transitions fetch authenticates with;
    `runner` is the acli subprocess seam (defaults to the real one).
    `transitions_fetcher` is the urllib /transitions seam, injected so the
    call-time category→status-name resolution is unit-tested offline.
    """

    def __init__(self, credential: aclicmd.JiraCredential, project: str,
                 runner: aclicmd.Runner | None = None,
                 transitions_fetcher: Callable[..., list[dict[str, str]]] | None
                 = None) -> None:
        self.credential = credential
        self.project = project
        self.runner = runner or aclicmd.run_acli
        self._fetch_transitions = transitions_fetcher or aclicmd.fetch_transitions

    # -- internal helpers ----------------------------------------------------

    def _json(self, args: Sequence[str], **kw: Any) -> Any:
        return aclicmd.acli_json(args, runner=self.runner, **kw)

    def _text(self, args: Sequence[str], **kw: Any) -> str:
        return aclicmd.acli_text(args, runner=self.runner, **kw)

    # -- status (resolved by category, never by name) ------------------------

    def status_category(self, key: str) -> str | None:
        """The issue's status category key, the platform-stable read.

        Resolves `.fields.status.statusCategory.key` from
        `acli jira workitem view <KEY> --json --fields '*all'`. This is the only
        status read the backend makes: the category (`new`/`indeterminate`/
        `done`) survives a project renaming its statuses, where a name read would
        silently break. Returns None when the field is absent.
        """
        data = self._json(
            ["jira", "workitem", "view", key, "--json", "--fields", "*all"],
            default={},
        )
        status = ((data.get("fields") or {}).get("status") or {})
        return (status.get("statusCategory") or {}).get("key")

    def is_done(self, key: str) -> bool:
        """Whether the issue is already in the done category — the no-op check.

        Resolves by `statusCategory.key == "done"`, never by a status name, so
        an already-closed issue is recognised regardless of what the project
        calls its terminal status.
        """
        return self.status_category(key) == CATEGORY_DONE

    def transition_to_category(self, key: str,
                               target_category: str) -> dict[str, Any]:
        """Transition the issue to a status carrying `target_category`.

        The category invariant's write half. `acli` transitions only by status
        name and cannot enumerate transitions, so the concrete target name is
        resolved *at call time*: fetch the reachable transitions, pick the one
        whose target status carries `target_category`, then
        `acli jira workitem transition <KEY> --status <that name>`. Nothing is
        hard-coded, so a project renaming its workflow statuses cannot break the
        binding.

        Short-circuits as a no-op when the issue is already in the target
        category (the already-done check). Raises NoSuchTransition when no
        reachable transition carries the category — a real blocker, not a guess.
        """
        if self.status_category(key) == target_category:
            return {"key": key, "category": target_category, "noop": True}

        transitions = self._fetch_transitions(self.credential, key)
        match = next(
            (t for t in transitions if t.get("category") == target_category),
            None)
        if match is None:
            raise NoSuchTransition(
                f"no reachable transition to a {target_category!r} status for "
                f"{key} (reachable: "
                f"{[t.get('name') for t in transitions]})")

        name = match["name"]
        self._text(["jira", "workitem", "transition", key, "--status", name])
        return {"key": key, "category": target_category, "status": name,
                "noop": False}

    # -- issues --------------------------------------------------------------

    def issue_view(self, key: str) -> dict[str, Any]:
        """Read an issue (work item) with all fields, in JSON.

        The same `--fields '*all'` view status_category reads, returned whole so
        the caller sees summary, status, labels, and the rest in one read.
        """
        return self._json(
            ["jira", "workitem", "view", key, "--json", "--fields", "*all"],
            default={},
        )

    def issue_create(self, title: str, body: str,
                     category: str) -> dict[str, Any]:
        """Create an issue in the project; body on stdin. Returns the new key.

        The category label resolves to a Jira issue type (the concept→primitive
        map); the untrusted body rides stdin (`--description-file -`), never
        argv (SECURITY.md).
        """
        issue_type = issue_type_for(category) or category
        out = self._json(
            ["jira", "workitem", "create", "--project", self.project,
             "--type", issue_type, "--summary", title,
             "--description-file", "-", "--json"],
            input=body,
            default={},
        )
        return {"key": out.get("key")}

    def issue_comment(self, key: str, body: str) -> dict[str, Any]:
        """Comment on an issue; body on stdin, never argv (SECURITY.md)."""
        self._text(
            ["jira", "workitem", "comment", key, "--body-file", "-"],
            input=body,
        )
        return {"key": key}

    def issue_label(self, key: str, add: list[str] | None = None,
                    remove: list[str] | None = None) -> dict[str, Any]:
        """Add/remove workflow-state labels on an issue.

        The state labels are the workflow's own state machine; they carry across
        as Jira labels verbatim (the identity mapping in `label_for`).
        """
        args = ["jira", "workitem", "edit", key]
        for lbl in add or []:
            args += ["--add-label", label_for(lbl)]
        for lbl in remove or []:
            args += ["--remove-label", label_for(lbl)]
        self._text(args)
        return {"key": key, "added": add or [], "removed": remove or []}

    def issue_close(self, key: str) -> dict[str, Any]:
        """Close an issue by transitioning it to the done category.

        Closure is a status move resolved by category, not a status name —
        delegates to transition_to_category, which short-circuits when the issue
        is already done.
        """
        return self.transition_to_category(key, CATEGORY_DONE)
