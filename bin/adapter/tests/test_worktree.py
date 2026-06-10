"""End-to-end tests for the worktree command group, against real temp repos.

create / teardown / sync-main / rebase each run real git in a tempdir with a
bare "remote" so the mutations and halt paths are exercised, not mocked.
"""

import io
import json
import os
import subprocess
import tempfile
import unittest

from adapter import gitcmd, worktree


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _write(path, content):
    with open(path, "w") as fh:
        fh.write(content)


class WorktreeFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        # A bare repo stands in for origin.
        self.remote = os.path.join(root, "remote.git")
        _git(root, "init", "-q", "--bare", "-b", "main", self.remote)
        # The local clone is the "repo-root checkout".
        self.repo = os.path.join(root, "clone")
        _git(root, "clone", "-q", self.remote, self.repo)
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")
        _write(os.path.join(self.repo, "README.md"), "base\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "initial")
        _git(self.repo, "push", "-q", "origin", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def _advance_remote_main(self, content="moved\n"):
        # Move origin/main forward via a throwaway clone so the local main is behind.
        other = os.path.join(self._tmp.name, "other")
        _git(self._tmp.name, "clone", "-q", self.remote, other)
        _git(other, "config", "user.email", "o@example.com")
        _git(other, "config", "user.name", "Other")
        _write(os.path.join(other, "upstream.txt"), content)
        _git(other, "add", "-A")
        _git(other, "commit", "-q", "-m", "upstream change")
        _git(other, "push", "-q", "origin", "main")


class TestCreate(WorktreeFixture):
    def test_creates_worktree_on_new_branch(self):
        out = io.StringIO()
        rc = worktree.cmd_create(self.repo, kind="feat", title="CSV Export",
                                 issue=87, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["branch"], "feat/87-csv-export")
        expected_path = os.path.join(self.repo, ".claude", "worktrees", "csv-export")
        self.assertEqual(payload["path"], expected_path)
        self.assertTrue(os.path.isdir(expected_path))
        self.assertTrue(gitcmd.branch_exists(self.repo, "feat/87-csv-export"))

    def test_no_issue_form(self):
        out = io.StringIO()
        worktree.cmd_create(self.repo, kind="chore", title="bump eslint",
                            issue=None, stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["branch"], "chore/bump-eslint")

    def test_checks_out_existing_local_branch(self):
        _git(self.repo, "branch", "feat/5-existing")
        out = io.StringIO()
        rc = worktree.cmd_create(self.repo, kind="feat", title="existing",
                                 issue=5, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["branch"], "feat/5-existing")
        self.assertTrue(os.path.isdir(payload["path"]))

    def test_checks_out_remote_only_branch(self):
        # Create the branch only on origin, then prune the local ref.
        other = os.path.join(self._tmp.name, "rbranch")
        _git(self._tmp.name, "clone", "-q", self.remote, other)
        _git(other, "config", "user.email", "o@example.com")
        _git(other, "config", "user.name", "Other")
        _git(other, "checkout", "-q", "-b", "feat/9-remote")
        _write(os.path.join(other, "r.txt"), "r")
        _git(other, "add", "-A")
        _git(other, "commit", "-q", "-m", "remote work")
        _git(other, "push", "-q", "origin", "feat/9-remote")

        out = io.StringIO()
        rc = worktree.cmd_create(self.repo, kind="feat", title="remote",
                                 issue=9, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["branch"], "feat/9-remote")
        self.assertTrue(os.path.isfile(os.path.join(payload["path"], "r.txt")))


class TestTeardown(WorktreeFixture):
    def test_removes_worktree_and_branch(self):
        worktree.cmd_create(self.repo, kind="feat", title="temp", issue=1,
                            stream=io.StringIO())
        path = os.path.join(self.repo, ".claude", "worktrees", "temp")
        self.assertTrue(os.path.isdir(path))

        out = io.StringIO()
        rc = worktree.cmd_teardown(self.repo, path=path, branch="feat/1-temp",
                                   stream=out)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.isdir(path))
        self.assertFalse(gitcmd.branch_exists(self.repo, "feat/1-temp"))


class TestSyncMain(WorktreeFixture):
    def test_fast_forwards_when_behind_and_clean(self):
        self._advance_remote_main()
        out = io.StringIO()
        rc = worktree.cmd_sync_main(self.repo, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "fast-forwarded")
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "upstream.txt")))

    def test_noop_when_already_current(self):
        out = io.StringIO()
        rc = worktree.cmd_sync_main(self.repo, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "up-to-date")

    def test_skips_dirty_tree(self):
        self._advance_remote_main()
        _write(os.path.join(self.repo, "README.md"), "dirty edit\n")
        out = io.StringIO()
        rc = worktree.cmd_sync_main(self.repo, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["reason"], "dirty tree")
        # Never fast-forwarded a dirty tree.
        self.assertFalse(os.path.isfile(os.path.join(self.repo, "upstream.txt")))

    def test_skips_when_diverged(self):
        self._advance_remote_main()
        # Local main commits independently, so it is no longer an ancestor.
        _write(os.path.join(self.repo, "local.txt"), "local\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "local divergent")
        out = io.StringIO()
        rc = worktree.cmd_sync_main(self.repo, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["reason"], "diverged")


class TestRebase(WorktreeFixture):
    def _branch_worktree(self, issue, fname, content):
        out = io.StringIO()
        worktree.cmd_create(self.repo, kind="feat", title=f"work {issue}",
                            issue=issue, stream=out)
        path = json.loads(out.getvalue())["path"]
        _write(os.path.join(path, fname), content)
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", f"branch work {issue}")
        # rebase force-pushes to the branch's upstream, so it must already track
        # one (a PR is open by the time rework rebases). Establish it.
        _git(path, "push", "-q", "-u", "origin", f"feat/{issue}-work-{issue}")
        return path

    def test_clean_rebase_pushes(self):
        path = self._branch_worktree(2, "feature.txt", "feature\n")
        # main advances with a non-conflicting change.
        _write(os.path.join(self.repo, "other.txt"), "other\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "main advances")

        out = io.StringIO()
        rc = worktree.cmd_rebase(path, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "rebased")
        # The branch now contains main's commit as an ancestor.
        merged = gitcmd.run_git(["log", "--oneline"], cwd=path).stdout
        self.assertIn("main advances", merged)

    def test_rebase_pushes_without_preset_upstream(self):
        # A branch created via cmd_create's `-b <branch> main` path has no
        # configured upstream. Rebase must push explicitly, not rely on one.
        out = io.StringIO()
        worktree.cmd_create(self.repo, kind="feat", title="no upstream",
                            issue=4, stream=out)
        path = json.loads(out.getvalue())["path"]
        _write(os.path.join(path, "feature.txt"), "feature\n")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", "branch work")
        # main advances with a non-conflicting change.
        _write(os.path.join(self.repo, "other.txt"), "other\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "main advances")

        rc = worktree.cmd_rebase(path, stream=io.StringIO())
        self.assertEqual(rc, 0)
        # The branch was pushed to origin without a pre-set upstream.
        remote_branches = subprocess.run(
            ["git", "ls-remote", "--heads", self.remote, "feat/4-no-upstream"],
            capture_output=True, text=True, check=True).stdout
        self.assertIn("feat/4-no-upstream", remote_branches)

    def test_conflict_halts_and_aborts(self):
        path = self._branch_worktree(3, "clash.txt", "branch side\n")
        # main edits the same file, so the replay conflicts.
        _write(os.path.join(self.repo, "clash.txt"), "main side\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "main clash")

        err = io.StringIO()
        rc = worktree.cmd_rebase(path, stream=err)
        self.assertNotEqual(rc, 0)
        payload = json.loads(err.getvalue())
        self.assertEqual(payload["status"], "halted")
        self.assertIn("clash.txt", payload["paths"])
        # The rebase was aborted, not left mid-replay.
        self.assertFalse(os.path.isdir(os.path.join(path, ".git", "rebase-merge")))
        rebase_apply = os.path.join(path, ".git", "rebase-apply")
        self.assertFalse(os.path.isdir(rebase_apply))


if __name__ == "__main__":
    unittest.main()
