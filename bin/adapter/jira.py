"""The `acli`-backed Jira implementation of the tracker concepts, per ADR 0008.

Sibling of the `GithubBackend` in `tracker.py` and symmetric with it: the same
tracker-neutral concept surface, mapped to Jira primitives rather than GitHub
ones. It shells out to `acli jira` for the reads and the create/comment/label
writes acli handles, and drives the close path entirely over REST through the
`curl` seam (`jiracmd`) — the one thing acli cannot do without falling over
enterprise TLS interception: enumerate an issue's reachable transitions and POST
the one carrying the done category, attaching a resolution only when the
transition requires it.

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
status *transition* resolves the target category to a concrete reachable
transition at call time via the REST `GET /transitions`, then POSTs that
transition's id — so a workflow rename, which leaves the category and the
transition id intact, can never break the binding to a hard-coded name.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import urllib.parse
from typing import Any, Callable, Iterator, Mapping, Sequence

from adapter import aclicmd, cli, enums, jiracmd

# The default resolution attached when a done transition requires one. Jira
# rejects a transition with a mandatory Resolution field unset; the operator
# overrides the name via JIRA_DONE_RESOLUTION when the project renames it.
_DONE_RESOLUTION_VAR = "JIRA_DONE_RESOLUTION"
_DEFAULT_DONE_RESOLUTION = "Done"

# The operator config for backend-mandated non-neutral create fields (#233).
# JIRA_REQUIRED_FIELDS names, per issue type, the field identities a deployment
# mandates (a JSON `{"Epic": ["customfield_10100"]}` map); JIRA_FIELD_VALUES
# carries the deployment-wide fixed value for a field (a JSON
# `{"customfield_10100": "Run"}` map). A mandated field with a fixed value is
# set from config; one without is decided per case and halts for a value.
_REQUIRED_FIELDS_VAR = "JIRA_REQUIRED_FIELDS"
_FIELD_VALUES_VAR = "JIRA_FIELD_VALUES"

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


@contextlib.contextmanager
def _body_file(body: str) -> Iterator[str]:
    """Write an untrusted body to a private temp file and yield its path.

    acli reads a body from a file path (`--description-file` / `--body-file`),
    not from stdin — it has no `-` stdin convention. So the out-of-band channel
    here is a 0600 temp file (mkstemp's default mode) whose *path* rides argv
    while the body itself never does (SECURITY.md). The file is removed on exit
    whether or not the acli call succeeds.
    """
    fd, path = tempfile.mkstemp(prefix="tracker-body-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body or "")
        yield path
    finally:
        os.unlink(path)


def _find_field(meta: Any, field_id: str) -> dict[str, Any]:
    """Locate one field's create-screen metadata in a createmeta response.

    Tolerates the shapes Jira's createmeta returns across versions: a flat
    `{"fields": [{"fieldId": …}]}` list, a `{"fields": {field_id: {…}}}` dict
    keyed by id, and the nested `projects[].issuetypes[].fields` form. Returns
    the field's metadata dict, or an empty dict when the field is absent (a
    free-text required field the human still supplies, with no enumerated
    choices).
    """
    for fields in _iter_field_blocks(meta):
        if isinstance(fields, dict):
            if field_id in fields:
                return fields[field_id]
            for fid, spec in fields.items():
                if isinstance(spec, dict) and spec.get("fieldId") == field_id:
                    return spec
        elif isinstance(fields, list):
            for spec in fields:
                if isinstance(spec, dict) and (
                        spec.get("fieldId") == field_id
                        or spec.get("key") == field_id):
                    return spec
    return {}


def _iter_field_blocks(meta: Any) -> Iterator[Any]:
    """Yield each candidate `fields` block from a createmeta response shape."""
    if not isinstance(meta, dict):
        return
    if "fields" in meta:
        yield meta["fields"]
    for project in meta.get("projects") or []:
        for issuetype in (project.get("issuetypes") or []):
            if "fields" in issuetype:
                yield issuetype["fields"]


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
    `(site, email, api_token)` source the REST close path authenticates with;
    `runner` is the acli subprocess seam (defaults to the real one).
    `curl_runner` is the REST seam (defaults to `jiracmd.run_curl`) and
    `token_evaluator` the api_token-command seam, both injected so the close
    path's transitions GET and POST are unit-tested offline with no network and
    no token spawn. `done_resolution` is the resolution name attached when a
    done transition requires one (default `Done`, overridable per project).
    """

    @classmethod
    def done_resolution_from(cls, env: Any) -> str:
        """The done resolution name from the environment, defaulting to `Done`.

        The operator names their project's terminal resolution via
        `JIRA_DONE_RESOLUTION` (e.g. `Fixed`); absent or empty falls back to the
        Jira default `Done`. The single read point so dispatch and the backend
        agree on the var name.
        """
        return env.get(_DONE_RESOLUTION_VAR) or _DEFAULT_DONE_RESOLUTION

    @classmethod
    def required_fields_from(cls, env: Mapping[str, str]) -> dict[str, list[str]]:
        """The per-issue-type mandated field identities from the environment.

        Parses `JIRA_REQUIRED_FIELDS` — a JSON `{issue_type: [field_id, …]}`
        map naming which custom fields a deployment mandates on which type.
        Absent or empty yields no mandated fields, so the common create path is
        untouched. The single read point so dispatch and the backend agree on
        the var name and shape.
        """
        raw = env.get(_REQUIRED_FIELDS_VAR)
        return json.loads(raw) if raw else {}

    @classmethod
    def field_values_from(cls, env: Mapping[str, str]) -> dict[str, str]:
        """The deployment-wide fixed field values from the environment.

        Parses `JIRA_FIELD_VALUES` — a JSON `{field_id: value}` map carrying the
        same-everywhere value for a mandated field. A mandated field absent from
        this map is decided per case (it halts for a value); one present is set
        from config. Absent or empty yields no fixed values.
        """
        raw = env.get(_FIELD_VALUES_VAR)
        return json.loads(raw) if raw else {}

    def __init__(self, credential: aclicmd.JiraCredential, project: str,
                 runner: aclicmd.Runner | None = None,
                 curl_runner: jiracmd.Runner | None = None,
                 token_evaluator: Callable[[str], str] | None = None,
                 done_resolution: str = _DEFAULT_DONE_RESOLUTION,
                 required_fields: dict[str, list[str]] | None = None,
                 field_values: dict[str, str] | None = None) -> None:
        self.credential = credential
        self.project = project
        self.runner = runner or aclicmd.run_acli
        self._curl_runner = curl_runner or jiracmd.run_curl
        self._token_evaluator = token_evaluator or aclicmd.eval_token
        self.done_resolution = done_resolution
        # Mandated non-neutral create fields (#233): the per-type field
        # identities and the deployment-wide fixed values, both from config.
        self.required_fields = required_fields or {}
        self.field_values = field_values or {}

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

    # -- the all-REST curl close path ----------------------------------------

    def _config(self) -> str:
        """The `curl -K -` config carrying the Basic credential for this site.

        Evaluates the api_token from the credential's command once and base64-
        encodes it into the config's Authorization header, so the token rides
        the stdin config channel and never argv (SECURITY.md).
        """
        return jiracmd.config_for(self.credential,
                                  token_evaluator=self._token_evaluator)

    def _transitions_url(self, key: str) -> str:
        return f"{self.credential.site}/rest/api/3/issue/{key}/transitions"

    def transition_to_category(self, key: str,
                               target_category: str) -> dict[str, Any]:
        """Transition the issue to a status carrying `target_category`, all-REST.

        The category invariant's write half, over the `curl` REST seam. The
        target is resolved *at call time*: `GET /transitions` enumerates the
        reachable transitions, the one whose `to.statusCategory.key` carries
        `target_category` is picked by its id, and `POST /transitions` performs
        it — attaching a `resolution` field (name from `done_resolution`) only
        when that transition's `fields.resolution.required` is set. Nothing is
        keyed on a status name, so a project renaming its workflow cannot break
        the binding, and the REST path honours the OS trust store where the old
        urllib GET fell over enterprise TLS interception.

        Short-circuits as a no-op when the issue is already in the target
        category (the already-done check, still an acli read). Raises
        NoSuchTransition when no reachable transition carries the category — a
        real blocker, not a guess.
        """
        if self.status_category(key) == target_category:
            return {"key": key, "category": target_category, "noop": True}

        config = self._config()
        url = self._transitions_url(key)
        payload = jiracmd.request_json("GET", url, config,
                                       runner=self._curl_runner, default={})
        transitions = payload.get("transitions") or []
        match = next(
            (t for t in transitions
             if ((t.get("to") or {}).get("statusCategory") or {}).get("key")
             == target_category),
            None)
        if match is None:
            raise NoSuchTransition(
                f"no reachable transition to a {target_category!r} status for "
                f"{key} (reachable: "
                f"{[(t.get('to') or {}).get('name') for t in transitions]})")

        body: dict[str, Any] = {"transition": {"id": match["id"]}}
        # Attach a resolution only when this transition's screen requires the
        # field — an unrequired resolution is rejected, a required one omitted is
        # rejected; #233 owns the broader needs-a-field decision, this case is
        # the mandatory-Resolution one the close path must handle itself.
        if self._requires_resolution(match):
            body["fields"] = {"resolution": {"name": self.done_resolution}}
        # The POST returns 204 No Content on success (no body to parse).
        jiracmd.request("POST", url, config,
                        payload=body, runner=self._curl_runner)
        return {"key": key, "category": target_category,
                "transition_id": match["id"], "noop": False}

    @staticmethod
    def _requires_resolution(transition: dict[str, Any]) -> bool:
        """Whether a transition's screen marks the `resolution` field required.

        The transition's `fields.resolution.required` flag, read defensively: a
        transition with no fields block (the common case) requires nothing.
        """
        resolution = (transition.get("fields") or {}).get("resolution") or {}
        return bool(resolution.get("required"))

    # -- issues --------------------------------------------------------------

    @staticmethod
    def _neutral_issue(native: Mapping[str, Any],
                       key: str | None = None) -> dict[str, Any]:
        """Project one acli workitem into the neutral two-zone envelope (ADR 0009).

        The shared mapping behind both the detail read (`issue_view`) and the
        summary read (`issue_list`): the opaque Jira key is the neutral `id`, the
        neutral `state` resolves from `statusCategory.key` (`done`→`closed`, else
        `open`), and `title`/`labels` carry across at the top level. The Jira key
        and the issue url ride the `info` sidecar — the adapter-specific data
        nothing branches on. `key` is the fallback id for a detail read that
        requested a key the payload may omit; a list row carries its own.
        """
        resolved_key = native.get("key", key)
        fields = native.get("fields") or {}
        category = ((fields.get("status") or {}).get("statusCategory") or {}
                    ).get("key")
        info: dict[str, Any] = {"key": resolved_key}
        if "url" in native:
            info["url"] = native["url"]
        return {
            "id": resolved_key,
            "state": enums.jira_issue_state(category),
            "title": fields.get("summary"),
            "labels": fields.get("labels") or [],
            "info": info,
        }

    def issue_view(self, key: str) -> dict[str, Any]:
        """Read an issue and project it into the neutral two-zone envelope.

        Reads the same `--fields '*all'` view status_category reads, then shapes
        it through `_neutral_issue` (ADR 0009): the opaque Jira key is the neutral
        `id`, the neutral `state` resolves from `statusCategory.key`
        (`done`→`closed`, else `open`), and `title`/`labels` carry across at the
        top level, with the key and url on the `info` sidecar.
        """
        native = self._json(
            ["jira", "workitem", "view", key, "--json", "--fields", "*all"],
            default={},
        )
        return self._neutral_issue(native, key=key)

    @staticmethod
    def _jql_quote(value: str) -> str:
        """Quote a value as a JQL string literal, escaping what would break out.

        Backslash and double-quote are the two characters JQL treats specially
        inside a double-quoted string, so both are escaped before the value is
        wrapped. Today's callers pass controlled workflow labels and the
        configured project, but escaping at the boundary keeps the clause
        injection-proof if a fetched value is ever wired in.
        """
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @classmethod
    def _list_jql(cls, project: str, label: str | None, state: str) -> str:
        """The JQL for a summary list read, scoped to the project.

        Filters by neutral state through the platform-stable `statusCategory`
        (never a renameable status name): `open` is everything not yet `Done`,
        `closed` is `Done`. A label, when given, narrows further. Values are
        quoted through `_jql_quote` so a multi-word value still parses and an
        embedded quote can't break out of the clause.
        """
        clauses = [f"project = {cls._jql_quote(project)}"]
        if state == "open":
            clauses.append("statusCategory != Done")
        elif state == "closed":
            clauses.append("statusCategory = Done")
        if label:
            clauses.append(f"labels = {cls._jql_quote(label)}")
        return " AND ".join(clauses)

    def issue_list(self, label: str | None = None,
                   state: str = "open") -> list[dict[str, Any]]:
        """List issues as lean neutral summary rows (ADR 0009).

        The summary counterpart to `issue_view`: an `acli jira workitem search`
        JQL read scoped to the project, filtered by neutral `state` and an
        optional `label`, projecting each hit through the same `_neutral_issue`
        mapping the view uses. The field set is the summary minimum
        (`summary,status,labels`) the neutral row needs. acli's search payload is
        a bare list of workitems, tolerantly unwrapped from an envelope shape too.
        """
        jql = self._list_jql(self.project, label, state)
        payload = self._json(
            ["jira", "workitem", "search", "--jql", jql, "--json",
             "--fields", "summary,status,labels"],
            default=[],
        )
        if isinstance(payload, dict):
            payload = (payload.get("issues") or payload.get("workItems")
                       or payload.get("results") or [])
        return [self._neutral_issue(row) for row in payload]

    def issue_create(self, title: str, body: str, category: str,
                     set_fields: Mapping[str, str] | None = None
                     ) -> dict[str, Any]:
        """Create an issue in the project, honouring backend-mandated fields.

        The category label resolves to a Jira issue type (the concept→primitive
        map). When the deployment mandates no extra field on that type, the
        create takes the unchanged acli path — the untrusted body rides a temp
        file path (`--description-file`), never argv (SECURITY.md).

        When config mandates fields on the type (#233), the create runs all-REST
        over the curl seam — the same path the close path took when acli could
        not attach a required field. Each mandated field's value is resolved in
        order: an explicit `--set` value (verbatim) wins, else the configured
        fixed value, else the field is *decided per case*. A decided field with
        no value HALTS the create — `outcome: needs_decision` carrying the field,
        the allowed values discovered over REST, and a human prompt — rather than
        inventing one. The body rides the REST JSON payload (the stdin config
        channel), never argv.
        """
        issue_type = issue_type_for(category) or category
        mandated = self.required_fields.get(issue_type) or []
        if not mandated:
            return self._acli_create(title, body, issue_type)

        set_fields = dict(set_fields or {})
        fields: dict[str, Any] = {}
        for field_id in mandated:
            if field_id in set_fields:
                fields[field_id] = set_fields[field_id]
            elif field_id in self.field_values:
                fields[field_id] = self.field_values[field_id]
            else:
                # A decided field with no chosen value: halt rather than guess.
                return self._needs_decision(issue_type, field_id)
        return self._rest_create(title, body, issue_type, fields)

    def _acli_create(self, title: str, body: str,
                     issue_type: str) -> dict[str, Any]:
        """The unchanged acli create for a type with no mandated fields."""
        with _body_file(body) as path:
            out = self._json(
                ["jira", "workitem", "create", "--project", self.project,
                 "--type", issue_type, "--summary", title,
                 "--description-file", path, "--json"],
                default={},
            )
        return {"outcome": cli.OK, "key": out.get("key")}

    def _create_url(self) -> str:
        return f"{self.credential.site}/rest/api/3/issue"

    def _createmeta_url(self, issue_type: str) -> str:
        # The create-screen field metadata for one type. projectKeys/issuetypeNames
        # scope the response to the fields (and their allowedValues) on this type's
        # create screen — the discovery source for a decided field's choices. The
        # project key and issue type name are percent-encoded into the query so a
        # multi-word type ("User Story") or one carrying a URL metacharacter still
        # produces a well-formed URL on curl's argv (urllib.parse.quote is pure
        # string encoding — it makes no network call, so the no-urllib-network
        # discipline that drove the curl seam does not bar it).
        query = urllib.parse.urlencode({
            "projectKeys": self.project,
            "issuetypeNames": issue_type,
            "expand": "projects.issuetypes.fields",
        })
        return f"{self.credential.site}/rest/api/3/issue/createmeta?{query}"

    def _rest_create(self, title: str, body: str, issue_type: str,
                     fields: Mapping[str, Any]) -> dict[str, Any]:
        """POST a create over REST with the neutral fields plus the mandated ones.

        The neutral summary/description/issuetype/project ride the same `fields`
        block as the mandated custom fields, so the body travels the REST payload
        (the stdin config channel) and never argv (SECURITY.md). Returns the
        contract act envelope with the new key.
        """
        payload = {"fields": {
            "project": {"key": self.project},
            "issuetype": {"name": issue_type},
            "summary": title,
            "description": body,
            **fields,
        }}
        out = jiracmd.request_json("POST", self._create_url(), self._config(),
                                   payload=payload, runner=self._curl_runner,
                                   default={})
        return {"outcome": cli.OK, "key": (out or {}).get("key")}

    def _needs_decision(self, issue_type: str,
                        field_id: str) -> dict[str, Any]:
        """Halt the create on a decided field, carrying its discovered choices.

        Reads the create-screen metadata over REST, finds the mandated field's
        `allowedValues`, and shapes the `needs_decision` result: the field id,
        its human name, the allowed values, and a prompt — the payload the
        caller couriers a chosen value back through `--set`. It never picks a
        value itself; the choice is the human's.
        """
        name, allowed = self._discover_allowed_values(issue_type, field_id)
        return {
            "outcome": cli.NEEDS_DECISION,
            "field": field_id,
            "info": {"field": field_id, "field_name": name,
                     "allowed_values": allowed, "issue_type": issue_type},
            "message": (
                f"{issue_type} requires a value for {name or field_id!r}. "
                f"Choose one of {allowed} and retry with "
                f"--set {field_id}=<value>."),
        }

    def _discover_allowed_values(self, issue_type: str,
                                 field_id: str) -> tuple[str | None, list[Any]]:
        """The (name, allowed values) for a mandated field on a type's create
        screen, read over REST. Empty list when the field declares no enumerated
        values (a free-text required field the human still supplies)."""
        meta = jiracmd.request_json("GET", self._createmeta_url(issue_type),
                                    self._config(), runner=self._curl_runner,
                                    default={})
        field = _find_field(meta, field_id)
        name = field.get("name")
        allowed = [v.get("value", v) if isinstance(v, dict) else v
                   for v in (field.get("allowedValues") or [])]
        return name, allowed

    def issue_comment(self, key: str, body: str) -> dict[str, Any]:
        """Comment on an issue.

        `comment` is an acli command *group*; the leaf is `comment create`. The
        work item is named by `--key`, and the untrusted body reaches acli via a
        temp file path (`--body-file <path>`), never argv (SECURITY.md).
        """
        with _body_file(body) as path:
            self._text(
                ["jira", "workitem", "comment", "create", "--key", key,
                 "--body-file", path],
            )
        return {"key": key}

    def issue_label(self, key: str, add: list[str] | None = None,
                    remove: list[str] | None = None) -> dict[str, Any]:
        """Add/remove workflow-state labels on an issue.

        The state labels are the workflow's own state machine; they carry across
        as Jira labels verbatim (the identity mapping in `label_for`). acli's
        `edit` names the work item by `--key`, takes comma-separated label lists
        on `--labels` (add) / `--remove-labels` (remove), and prompts unless
        `--yes` is given — the binary has no TTY.
        """
        args = ["jira", "workitem", "edit", "--key", key, "--yes"]
        if add:
            args += ["--labels", ",".join(label_for(lbl) for lbl in add)]
        if remove:
            args += ["--remove-labels", ",".join(label_for(lbl) for lbl in remove)]
        self._text(args)
        return {"key": key, "added": add or [], "removed": remove or []}

    def issue_close(self, key: str) -> dict[str, Any]:
        """Close an issue by transitioning it to the done category, all-REST.

        Closure is a status move resolved by category, not a status name —
        delegates to transition_to_category (the curl GET/POST), which short-
        circuits when the issue is already done. Returns the contract act
        envelope: a coded `outcome`, the opaque `id`, and the neutral `closed`
        state; the transition id (or the noop flag) rides the `info` sidecar.
        """
        result = self.transition_to_category(key, CATEGORY_DONE)
        info = {k: v for k, v in result.items()
                if k not in ("key", "category")}
        return {"outcome": cli.OK, "id": key, "state": "closed", "info": info}
