"""Unit tests for the pure branch-naming and slug-derivation logic."""

from __future__ import annotations

import unittest

from adapter.naming import KINDS, InvalidKind, branch_name, slugify


class TestSlugify(unittest.TestCase):
    def test_lowercases(self) -> None:
        self.assertEqual(slugify("CSV Export"), "csv-export")

    def test_spaces_become_hyphens(self) -> None:
        self.assertEqual(slugify("null deref on empty cart"), "null-deref-on-empty-cart")

    def test_strips_punctuation(self) -> None:
        self.assertEqual(slugify("Fix: the thing!"), "fix-the-thing")

    def test_collapses_repeated_separators(self) -> None:
        self.assertEqual(slugify("a   b---c"), "a-b-c")

    def test_em_dash_becomes_separator(self) -> None:
        # Issue titles use em-dashes, e.g. "feat(slice) — carry framing".
        self.assertEqual(slugify("carry discover framing — into the body"),
                         "carry-discover-framing-into-the-body")

    def test_en_dash_becomes_separator(self) -> None:
        self.assertEqual(slugify("range – since last tag"), "range-since-last-tag")

    def test_trims_leading_trailing_separators(self) -> None:
        self.assertEqual(slugify("  --hello--  "), "hello")

    def test_underscores_become_hyphens(self) -> None:
        self.assertEqual(slugify("snake_case_name"), "snake-case-name")

    def test_keeps_digits(self) -> None:
        self.assertEqual(slugify("bump eslint 9"), "bump-eslint-9")

    def test_caps_length_at_word_boundary(self) -> None:
        title = "a very long title that keeps going well past the sensible cap for branches"
        slug = slugify(title)
        self.assertLessEqual(len(slug), 50)
        # Cap falls on a word boundary, never mid-word or on a trailing hyphen.
        self.assertFalse(slug.endswith("-"))
        self.assertTrue(all(part for part in slug.split("-")))

    def test_single_long_word_is_hard_truncated(self) -> None:
        slug = slugify("x" * 80)
        self.assertEqual(len(slug), 50)

    def test_empty_after_stripping_raises(self) -> None:
        with self.assertRaises(ValueError):
            slugify("!!! ---")


class TestBranchName(unittest.TestCase):
    def test_with_issue(self) -> None:
        self.assertEqual(
            branch_name("fix", "null deref on empty cart", issue=142),
            "fix/142-null-deref-on-empty-cart",
        )

    def test_without_issue(self) -> None:
        self.assertEqual(branch_name("chore", "bump eslint"), "chore/bump-eslint")

    def test_issue_none_is_no_issue_form(self) -> None:
        self.assertEqual(branch_name("feat", "csv export", issue=None), "feat/csv-export")

    def test_issue_accepts_string(self) -> None:
        self.assertEqual(branch_name("feat", "csv export", issue="87"), "feat/87-csv-export")

    def test_each_kind(self) -> None:
        for kind in KINDS:
            self.assertEqual(branch_name(kind, "x", issue=1), f"{kind}/1-x")

    def test_rejects_unknown_kind(self) -> None:
        with self.assertRaises(InvalidKind):
            branch_name("bugfix", "x", issue=1)

    def test_normalises_title_in_branch(self) -> None:
        self.assertEqual(
            branch_name("feat", "CSV Export — Phase 2", issue=87),
            "feat/87-csv-export-phase-2",
        )


if __name__ == "__main__":
    unittest.main()
