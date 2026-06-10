import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

# bin/version has no .py extension, so name an explicit source loader rather
# than relying on extension-based loader discovery (which yields no loader).
_BIN = Path(__file__).resolve().parent.parent / "bin" / "version"
_spec = importlib.util.spec_from_loader(
    "version_adapter", SourceFileLoader("version_adapter", str(_BIN))
)
version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(version)


class ParseSubjectTest(unittest.TestCase):
    def test_parses_type_and_scope(self):
        commit = version.parse_commit("feat(pickup): carry framing into the body")
        self.assertEqual(commit.type, "feat")
        self.assertEqual(commit.scope, "pickup")
        self.assertFalse(commit.breaking)

    def test_parses_type_without_scope(self):
        commit = version.parse_commit("fix: guard nil cart")
        self.assertEqual(commit.type, "fix")
        self.assertEqual(commit.scope, "")

    def test_breaking_via_bang(self):
        commit = version.parse_commit("refactor(land)!: drop the merge fallthrough")
        self.assertEqual(commit.type, "refactor")
        self.assertEqual(commit.scope, "land")
        self.assertTrue(commit.breaking)

    def test_breaking_via_footer(self):
        commit = version.parse_commit(
            "feat: rework the claim protocol",
            body="Adds CAS.\n\nBREAKING CHANGE: assignee claims are gone.",
        )
        self.assertTrue(commit.breaking)

    def test_unrecognised_subject_yields_empty_type(self):
        commit = version.parse_commit("Merge pull request #12 from x")
        self.assertEqual(commit.type, "")
        self.assertFalse(commit.breaking)


class MaterialityTest(unittest.TestCase):
    def test_feat_fix_refactor_perf_are_material(self):
        for type_ in ("feat", "fix", "refactor", "perf"):
            self.assertTrue(
                version.is_material(version.parse_commit(f"{type_}: x")), type_
            )

    def test_docs_and_chore_are_non_material(self):
        for type_ in ("docs", "chore"):
            self.assertFalse(
                version.is_material(version.parse_commit(f"{type_}: x")), type_
            )

    def test_unrecognised_type_is_non_material(self):
        self.assertFalse(version.is_material(version.parse_commit("Merge branch x")))

    def test_breaking_is_material_even_when_type_is_non_material(self):
        commit = version.parse_commit("chore!: drop python 3.8")
        self.assertTrue(version.is_material(commit))


def _commits(*subjects):
    return [version.parse_commit(s) for s in subjects]


class DerivePost1Test(unittest.TestCase):
    """Current major >= 1: breaking->major, feat->minor, fix/refactor/perf->patch."""

    def test_breaking_bumps_major(self):
        result = version.derive("1.4.2", _commits("feat: a", "refactor!: b"))
        self.assertEqual(result.increment, "major")
        self.assertEqual(result.new_version, "2.0.0")

    def test_feat_bumps_minor(self):
        result = version.derive("1.4.2", _commits("fix: a", "feat: b"))
        self.assertEqual(result.increment, "minor")
        self.assertEqual(result.new_version, "1.5.0")

    def test_fix_only_bumps_patch(self):
        result = version.derive("1.4.2", _commits("fix: a", "refactor: b"))
        self.assertEqual(result.increment, "patch")
        self.assertEqual(result.new_version, "1.4.3")

    def test_perf_only_bumps_patch(self):
        result = version.derive("1.4.2", _commits("perf: a"))
        self.assertEqual(result.increment, "patch")
        self.assertEqual(result.new_version, "1.4.3")


class DerivePre1Test(unittest.TestCase):
    """Current major == 0: breaking->minor, feat->minor, fix/refactor/perf->patch."""

    def test_breaking_bumps_minor(self):
        result = version.derive("0.2.0", _commits("feat!: a"))
        self.assertEqual(result.increment, "minor")
        self.assertEqual(result.new_version, "0.3.0")

    def test_feat_bumps_minor(self):
        result = version.derive("0.2.0", _commits("feat: a", "fix: b"))
        self.assertEqual(result.increment, "minor")
        self.assertEqual(result.new_version, "0.3.0")

    def test_fix_only_bumps_patch(self):
        result = version.derive("0.2.0", _commits("fix: a"))
        self.assertEqual(result.increment, "patch")
        self.assertEqual(result.new_version, "0.2.1")


class DeriveNoOpTest(unittest.TestCase):
    def test_chore_and_docs_only_is_a_no_op(self):
        result = version.derive("0.2.0", _commits("docs: a", "chore: b"))
        self.assertTrue(result.no_op)
        self.assertIsNone(result.increment)
        self.assertIsNone(result.new_version)

    def test_empty_range_is_a_no_op(self):
        result = version.derive("1.4.2", [])
        self.assertTrue(result.no_op)

    def test_material_range_is_not_a_no_op(self):
        result = version.derive("0.2.0", _commits("fix: a"))
        self.assertFalse(result.no_op)


class RenderNotesTest(unittest.TestCase):
    def test_groups_in_fixed_order_breaking_feat_fix_docs_rest(self):
        commits = _commits(
            "docs: write the guide",
            "fix(land): guard merge method",
            "feat(slice): carry framing",
            "refactor!: drop the shim",
            "chore: bump deps",
        )
        notes = version.render_notes(commits)
        lines = [ln for ln in notes.splitlines() if ln.strip()]
        self.assertEqual(
            lines,
            [
                "refactor!: drop the shim",
                "feat(slice): carry framing",
                "fix(land): guard merge method",
                "docs: write the guide",
                "chore: bump deps",
            ],
        )

    def test_scope_is_preserved(self):
        notes = version.render_notes(_commits("fix(pickup): x"))
        self.assertIn("fix(pickup): x", notes)

    def test_breaking_feat_groups_before_plain_feat(self):
        commits = _commits("feat: plain", "feat!: breaking")
        lines = [ln for ln in version.render_notes(commits).splitlines() if ln.strip()]
        self.assertEqual(lines, ["feat!: breaking", "feat: plain"])


def _git(cwd, *args, **kw):
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True, **kw
    )


def _commit(cwd, subject, body=""):
    msg = subject if not body else f"{subject}\n\n{body}"
    _git(cwd, "commit", "--allow-empty", "-m", msg)


class GitRangeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        _git(self.repo, "init", "-q", "-b", "main")
        self.addCleanup(self._tmp.cleanup)

    def test_no_tag_reads_all_history(self):
        _commit(self.repo, "feat: one")
        _commit(self.repo, "fix: two")
        subjects = [c.subject for c in version.read_range(self.repo)]
        self.assertEqual(subjects, ["fix: two", "feat: one"])

    def test_range_starts_after_last_v_tag(self):
        _commit(self.repo, "feat: before")
        _git(self.repo, "tag", "-a", "v0.1.0", "-m", "v0.1.0")
        _commit(self.repo, "fix: after")
        subjects = [c.subject for c in version.read_range(self.repo)]
        self.assertEqual(subjects, ["fix: after"])

    def test_reads_breaking_footer_from_body(self):
        _commit(self.repo, "feat: x", body="BREAKING CHANGE: gone")
        commits = version.read_range(self.repo)
        self.assertTrue(commits[0].breaking)

    def test_current_version_reads_plugin_json(self):
        manifest = Path(self.repo) / ".claude-plugin"
        manifest.mkdir()
        (manifest / "plugin.json").write_text(json.dumps({"version": "3.1.4"}))
        self.assertEqual(version.current_version(self.repo), "3.1.4")


class _ApplyArgs:
    def __init__(self, repo):
        self.repo = repo


class ApplyTest(unittest.TestCase):
    """Drive `version apply` against throwaway repos only — never the real one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        # A bare repo standing in for origin, and a clone that plays the role of
        # the local checkout apply operates from.
        self.origin = str(root / "origin.git")
        _git(str(root), "init", "-q", "--bare", "-b", "main", self.origin)
        self.repo = str(root / "clone")
        _git(str(root), "clone", "-q", self.origin, self.repo)

        manifest = Path(self.repo) / ".claude-plugin"
        manifest.mkdir()
        (manifest / "plugin.json").write_text(
            json.dumps({"version": "0.2.0"}, indent=2) + "\n"
        )
        _git(self.repo, "add", ".")
        _commit(self.repo, "chore: scaffold")
        _git(self.repo, "push", "-q", "origin", "main")
        _commit(self.repo, "feat: a shippable change")
        _git(self.repo, "push", "-q", "origin", "main")

    def test_apply_bumps_tags_and_pushes(self):
        rc = version.cmd_apply(_ApplyArgs(self.repo))
        self.assertEqual(rc, 0)

        # The bump landed on origin's main.
        shown = _git(self.origin, "show", "main:.claude-plugin/plugin.json").stdout
        self.assertEqual(json.loads(shown)["version"], "0.3.0")

        # The annotated tag exists on origin and carries the grouped notes.
        tags = _git(self.origin, "tag", "--list").stdout.split()
        self.assertIn("v0.3.0", tags)

        # The throwaway worktree and branch were torn down.
        worktrees = _git(self.repo, "worktree", "list").stdout
        self.assertNotIn("release-v0.3.0", worktrees)
        branches = _git(self.repo, "branch", "--list").stdout
        self.assertNotIn("chore/release-v0.3.0", branches)

    def test_apply_no_op_when_nothing_material(self):
        # Land only a chore on top, then a fresh clone whose range is chore-only.
        _commit(self.repo, "docs: tidy")
        _git(self.repo, "push", "-q", "origin", "main")
        # Tag the current tip so the range from tag..HEAD is empty of material.
        _git(self.repo, "tag", "-a", "v0.2.0", "-m", "v0.2.0")
        _commit(self.repo, "chore: noise")
        rc = version.cmd_apply(_ApplyArgs(self.repo))
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
