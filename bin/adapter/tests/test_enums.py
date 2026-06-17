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


class TestReviewDecision(unittest.TestCase):
    def test_approved_maps_through(self) -> None:
        self.assertEqual(enums.review_decision("APPROVED"), "approved")

    def test_changes_requested_maps_through(self) -> None:
        self.assertEqual(enums.review_decision("CHANGES_REQUESTED"),
                         "changes_requested")

    def test_explicit_review_required_maps_through(self) -> None:
        self.assertEqual(enums.review_decision("REVIEW_REQUIRED"),
                         "review_required")

    def test_none_maps_to_review_required(self) -> None:
        # gh's reviewDecision is None when no required review exists or only
        # comment-state reviews were left — the contract reads that as
        # review_required (GITHUB.md glossary: "no review").
        self.assertEqual(enums.review_decision(None), "review_required")

    def test_unmapped_value_raises(self) -> None:
        # Any other native value is an error, never passed through.
        with self.assertRaises(enums.UnmappedValue):
            enums.review_decision("DISMISSED")


class TestMergeState(unittest.TestCase):
    def test_mergeable_maps_to_mergeable(self) -> None:
        self.assertEqual(enums.merge_state("MERGEABLE"), "mergeable")

    def test_conflicting_maps_to_conflicting(self) -> None:
        self.assertEqual(enums.merge_state("CONFLICTING"), "conflicting")

    def test_unknown_maps_to_unknown(self) -> None:
        self.assertEqual(enums.merge_state("UNKNOWN"), "unknown")

    def test_unmapped_value_raises(self) -> None:
        # mergeStateStatus tokens (CLEAN/BEHIND/…) are NOT mergeable values —
        # they have no neutral 3-token mapping here and must raise.
        with self.assertRaises(enums.UnmappedValue):
            enums.merge_state("CLEAN")


if __name__ == "__main__":
    unittest.main()
