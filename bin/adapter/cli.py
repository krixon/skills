"""Present/act output substrate for adapter commands.

ADR 0008 gives every command one of two stdin-free shapes: *present* (emit
JSON/text, exit) or *act* (perform one mutation, then report, exit). A pure
command also *halts at synthesis* — on reaching a state only a human or model
can resolve, it presents the blocker and exits non-zero rather than degrading
into resolving it.

ADR 0009 fixes the *shape* of what the tracker commands emit. Every result is a
two-zone envelope: neutral contract fields at the top level, all adapter-specific
data under one reserved `info` key that nothing branches on. Act and halt
results carry a closed `outcome` code, with any human-readable explanation
confined to a non-branched `message`.

The emitters are dual-shape during the contract migration (ADR 0009 lands one
slice at a time). A caller on the contract passes an `outcome` token from the
closed vocabulary as the first argument; a not-yet-migrated caller passes a
plain payload (`acted`) or a free-text reason (`halt`) and gets the legacy
shape. The discriminator is membership in the `OUTCOMES` vocabulary, so the two
forms never collide. These helpers return the process exit code, so command
functions stay free of sys.exit and remain directly testable.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

HALT_EXIT = 2

# The closed outcome vocabulary (ADR 0009). Every act or halt result a skill
# branches on carries one of these codes; free text never leaks into the code.
OK = "ok"
NOOP = "noop"
CLAIM_LOST = "claim_lost"
CONFLICT = "conflict"
UNSUPPORTED = "unsupported"
NOT_FOUND = "not_found"
UNCONFIGURED = "unconfigured"
NEEDS_DECISION = "needs_decision"

OUTCOMES = frozenset({
    OK, NOOP, CLAIM_LOST, CONFLICT, UNSUPPORTED, NOT_FOUND, UNCONFIGURED,
    NEEDS_DECISION,
})


def present_json(payload: Any, stream: TextIO | None = None) -> int:
    """Emit a present-shape payload and return exit code 0.

    A read result is already shaped by the backend (a contract issue envelope, a
    list of them, or a legacy present payload), so present passes it through.
    """
    _emit(payload, stream or sys.stdout)
    return 0


def acted(outcome_or_payload: Any, fields: dict[str, Any] | None = None,
          info: dict[str, Any] | None = None, message: str | None = None,
          stream: TextIO | None = None) -> int:
    """Emit an act-shape result and return exit code 0.

    Contract form: `acted(outcome, fields=, info=, message=)` — an outcome token
    from the closed vocabulary, neutral `fields` lifted to the top level, the
    adapter-specific `info` sidecar, and free text in `message`. Legacy form:
    `acted(payload_dict)` emits the dict verbatim (a not-yet-migrated caller).
    """
    if isinstance(outcome_or_payload, str):
        payload = _envelope(outcome_or_payload, fields, info, message)
    else:
        payload = outcome_or_payload
    _emit(payload, stream or sys.stdout)
    return 0


def halt(outcome_or_reason: str, details: dict[str, Any] | None = None,
         info: dict[str, Any] | None = None, message: str | None = None,
         stream: TextIO | None = None) -> int:
    """Present a synthesis blocker and return a non-zero exit code.

    The command stops here: it surfaces what blocked it and never attempts the
    resolution that only a human or model can make.

    Contract form: `halt(outcome, info=, message=)` — a coded outcome from the
    closed vocabulary with a human-readable `message` and an `info` sidecar,
    making the halt machine-parseable (ADR 0009). Legacy form:
    `halt(reason, details)` emits `{status:"halted", reason, **details}`.
    """
    # Dual-shape discriminator: membership in OUTCOMES routes to the contract
    # branch, else the arg is a legacy free-text reason. A legacy reason must
    # never be a bare outcome token (e.g. "conflict") — it would take the
    # contract branch and silently drop its `details`. All legacy reasons today
    # are full sentences, so none collide; this invariant must hold until the
    # legacy branch is dropped. (`acted` is unaffected: its legacy form passes a
    # dict, so a str first-arg is unambiguously the contract form.)
    if outcome_or_reason in OUTCOMES:
        payload = _envelope(outcome_or_reason, None, info, message)
    else:
        payload = {"status": "halted", "reason": outcome_or_reason}
        if details:
            payload.update(details)
    _emit(payload, stream or sys.stderr)
    return HALT_EXIT


def _envelope(outcome: str, fields: dict[str, Any] | None,
              info: dict[str, Any] | None, message: str | None) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError(
            f"unknown outcome {outcome!r}; expected one of {sorted(OUTCOMES)}"
        )
    payload: dict[str, Any] = {}
    if fields:
        payload.update(fields)
    payload["outcome"] = outcome
    if message is not None:
        payload["message"] = message
    if info is not None:
        payload["info"] = info
    return payload


def _emit(payload: Any, stream: TextIO) -> None:
    json.dump(payload, stream, indent=2)
    stream.write("\n")
