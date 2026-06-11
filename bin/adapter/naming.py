"""Pure branch-name and slug derivation, per ISOLATION.md.

These functions carry the unit-test weight of the worktree group: they are
side-effect-free so the git-mutating commands can stay thin wrappers over them.
"""

from __future__ import annotations

import re

# Branch kinds, per ISOLATION.md. The kind is chosen from the artifact.
KINDS = ("feat", "fix", "chore", "docs", "refactor")

# Slug length cap. A branch slug stays short enough to read in `git branch`
# output and on a PR; the cap falls on a word boundary where one exists.
_MAX_SLUG = 50


class InvalidKind(ValueError):
    """Raised when a branch kind is not one of KINDS."""


def slugify(title: str) -> str:
    """Derive a branch slug from a title: kebab-case, lowercased, punctuation
    stripped, length-capped at a word boundary.

    Raises ValueError if nothing survives normalisation.
    """
    # Dashes of every width (hyphen, en, em, minus) act as word separators, so
    # an em-dashed issue title splits rather than fusing across the dash.
    text = re.sub(r"[‐-―−]", " ", title)
    text = text.lower()
    # Anything that isn't an ASCII alphanumeric becomes a separator.
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        raise ValueError(f"title yields an empty slug: {title!r}")
    return _cap(text)


def _cap(slug: str) -> str:
    if len(slug) <= _MAX_SLUG:
        return slug
    head = slug[:_MAX_SLUG]
    # Prefer the last word boundary inside the cap; fall back to a hard cut for
    # a single over-long word.
    cut = head.rfind("-")
    if cut > 0:
        return head[:cut]
    return head


def branch_name(kind: str, title: str, issue: int | str | None = None) -> str:
    """Build a branch name: `<kind>/<issue>-<slug>` with a tracker issue,
    `<kind>/<slug>` without one.
    """
    if kind not in KINDS:
        raise InvalidKind(f"unknown kind {kind!r}; expected one of {', '.join(KINDS)}")
    slug = slugify(title)
    if issue is None:
        return f"{kind}/{slug}"
    return f"{kind}/{issue}-{slug}"
