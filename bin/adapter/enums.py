"""Neutral enum vocabularies and the mapping helper, per ADR 0009.

Every enum a skill branches on is a closed, lower-snake, documented vocabulary;
each backend maps its native values *in*, and an unmapped native value is an
error, not a pass-through. `map_enum` is the generic helper — a native→neutral
table plus a raise-on-miss guard — that the per-enum mappers (`issue_state`
here, review decision and merge state in later slices) are built on.

The maps live here, beside the helper, so the neutral vocabulary is legible in
one place and a new backend adds a row rather than a branch.
"""

from __future__ import annotations

from typing import Mapping

# The closed neutral issue-state vocabulary. The workflow's real state machine
# (needs-triage, in-progress, …) lives in labels, not tracker status — so this
# is exactly two tokens (ADR 0009).
ISSUE_STATES = frozenset({"open", "closed"})

# GitHub's native `state` values → neutral tokens. gh's --json emits lower-case
# (`open`/`closed`); the REST/GraphQL surface emits upper-case — both map in.
_GITHUB_ISSUE_STATE: Mapping[str, str] = {
    "open": "open",
    "OPEN": "open",
    "closed": "closed",
    "CLOSED": "closed",
}

# The closed neutral review-decision vocabulary. A PR's aggregate review state
# is exactly these three tokens — approved, changes requested, or a required
# review still outstanding (which also covers "only comment-state reviews so
# far", per GITHUB.md's "no review" glossary entry).
REVIEW_DECISIONS = frozenset({"approved", "changes_requested", "review_required"})

# GitHub's native `reviewDecision` values → neutral tokens. `None` is handled
# separately (see review_decision) — it is not a key here.
_GITHUB_REVIEW_DECISION: Mapping[str, str] = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes_requested",
    "REVIEW_REQUIRED": "review_required",
}

# The closed neutral merge-state vocabulary. This maps GitHub's `mergeable`
# field (a 3-value enum: MERGEABLE/CONFLICTING/UNKNOWN), NOT `mergeStateStatus`
# (a 7-value merge-button readiness enum — CLEAN/BEHIND/BLOCKED/DIRTY/DRAFT/…
# — which has no neutral 3-token equivalent and rides `info` instead).
MERGE_STATES = frozenset({"mergeable", "conflicting", "unknown"})

_GITHUB_MERGE_STATE: Mapping[str, str] = {
    "MERGEABLE": "mergeable",
    "CONFLICTING": "conflicting",
    "UNKNOWN": "unknown",
}


class UnmappedValue(ValueError):
    """A backend produced a native enum value with no neutral mapping.

    Raised rather than passed through: the closed-vocabulary guarantee is that a
    skill only ever sees a documented token, so an unknown native value is a
    contract breach to surface, not data to relay.
    """

    def __init__(self, value: object, known: object) -> None:
        self.value = value
        super().__init__(
            f"unmapped native value {value!r}; known values: {sorted(known)}"
        )


def map_enum(mapping: Mapping[str, str], native: str) -> str:
    """Map a native enum value to its neutral token, raising on a miss.

    `mapping` is the backend's native→neutral table. A native value absent from
    it raises `UnmappedValue` — it is never returned verbatim.
    """
    try:
        return mapping[native]
    except KeyError:
        raise UnmappedValue(native, mapping.keys()) from None


def issue_state(native: str) -> str:
    """Map a GitHub native issue state to the neutral `{open, closed}` token."""
    return map_enum(_GITHUB_ISSUE_STATE, native)


def review_decision(native: str | None) -> str:
    """Map a GitHub `reviewDecision` to the neutral review-decision token.

    GitHub's `reviewDecision` is `None` when no required review exists, or when
    only comment-state reviews were left (a `COMMENT` review never produces a
    decision). The contract reads that absence as `review_required` — the
    "no review" state in GITHUB.md's glossary. `None` is mapped *before* the
    table lookup; every other native value goes through `map_enum`, which raises
    `UnmappedValue` on a miss rather than passing an unknown token through.
    """
    if native is None:
        return "review_required"
    return map_enum(_GITHUB_REVIEW_DECISION, native)


def merge_state(native: str) -> str:
    """Map a GitHub `mergeable` value to the neutral merge-state token.

    This maps the `mergeable` field (MERGEABLE/CONFLICTING/UNKNOWN), not
    `mergeStateStatus` — those merge-button readiness tokens (CLEAN/BEHIND/…)
    have no neutral 3-token equivalent and ride the `info` sidecar. An unmapped
    value raises `UnmappedValue`.
    """
    return map_enum(_GITHUB_MERGE_STATE, native)
