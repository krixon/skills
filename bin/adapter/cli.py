"""Present/act output substrate for adapter commands.

ADR 0008 gives every command one of two stdin-free shapes: *present* (emit
JSON/text, exit) or *act* (perform one mutation, then report, exit). A pure
command also *halts at synthesis* — on reaching a state only a human or model
can resolve, it presents the blocker and exits non-zero rather than degrading
into resolving it. These helpers emit the JSON envelope for each shape and
return the process exit code, so command functions stay free of sys.exit and
remain directly testable.
"""

import json
import sys

HALT_EXIT = 2


def present_json(payload, stream=None):
    """Emit a present-shape JSON payload and return exit code 0."""
    _emit(payload, stream or sys.stdout)
    return 0


def acted(payload, stream=None):
    """Emit an act-shape result payload and return exit code 0."""
    _emit(payload, stream or sys.stdout)
    return 0


def halt(reason, details=None, stream=None):
    """Present a synthesis blocker and return a non-zero exit code.

    The command stops here: it surfaces what blocked it and never attempts the
    resolution that only a human or model can make.
    """
    payload = {"status": "halted", "reason": reason}
    if details:
        payload.update(details)
    _emit(payload, stream or sys.stderr)
    return HALT_EXIT


def _emit(payload, stream):
    json.dump(payload, stream, indent=2)
    stream.write("\n")
