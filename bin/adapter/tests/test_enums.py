"""Tests for the neutral enum-mapping helper (ADR 0009).

Every enum a skill branches on is a closed, lower-snake vocabulary; each backend
maps its native values *in*, and an unmapped native value RAISES rather than
passing through. These cover the generic mapping helper later slices reuse for
review decision and merge state.
"""

from __future__ import annotations

import unittest

from adapter import enums


class TestMapEnum(unittest.TestCase):
    def test_maps_native_value_to_neutral_token(self) -> None:
        self.assertEqual(enums.map_enum({"OPEN": "open"}, "OPEN"), "open")

    def test_unmapped_native_value_raises(self) -> None:
        # The closed-vocabulary guarantee: an unknown native value is never
        # passed through silently — it is an error.
        with self.assertRaises(enums.UnmappedValue):
            enums.map_enum({"OPEN": "open"}, "DELETED")

    def test_raises_message_names_the_offending_value(self) -> None:
        with self.assertRaises(enums.UnmappedValue) as ctx:
            enums.map_enum({"open": "open"}, "weird")
        self.assertIn("weird", str(ctx.exception))


class TestIssueState(unittest.TestCase):
    def test_open_maps_to_open(self) -> None:
        self.assertEqual(enums.issue_state("OPEN"), "open")

    def test_closed_maps_to_closed(self) -> None:
        self.assertEqual(enums.issue_state("CLOSED"), "closed")

    def test_case_insensitive_on_github_native(self) -> None:
        # gh emits lower-case state in --json output; the mapper accepts either.
        self.assertEqual(enums.issue_state("open"), "open")

    def test_unmapped_state_raises(self) -> None:
        with self.assertRaises(enums.UnmappedValue):
            enums.issue_state("MERGED")


if __name__ == "__main__":
    unittest.main()
