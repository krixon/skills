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
