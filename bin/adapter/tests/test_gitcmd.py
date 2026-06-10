"""Tests for the git subprocess substrate, against a real temp git repo."""

import os
import subprocess
import tempfile
import unittest

from adapter import gitcmd


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class GitRepoFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")
        self._commit("initial")

    def tearDown(self):
        self._tmp.cleanup()

    def _commit(self, msg, name="file.txt", content=None):
        path = os.path.join(self.repo, name)
        with open(path, "w") as fh:
            fh.write(content if content is not None else msg)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", msg)


class TestRunGit(GitRepoFixture):
    def test_capture_stdout(self):
        result = gitcmd.run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo)
        self.assertEqual(result.stdout.strip(), "main")
        self.assertEqual(result.returncode, 0)

    def test_failure_raises_by_default(self):
        with self.assertRaises(gitcmd.GitError):
            gitcmd.run_git(["rev-parse", "--verify", "no-such-ref"], cwd=self.repo)

    def test_no_check_returns_nonzero(self):
        result = gitcmd.run_git(["rev-parse", "--verify", "nope"], cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)


class TestQueries(GitRepoFixture):
    def test_is_clean_true_on_clean_tree(self):
        self.assertTrue(gitcmd.is_clean(self.repo))

    def test_is_clean_false_on_dirty_tree(self):
        with open(os.path.join(self.repo, "dirty.txt"), "w") as fh:
            fh.write("y")
        self.assertFalse(gitcmd.is_clean(self.repo))

    def test_branch_exists(self):
        self.assertTrue(gitcmd.branch_exists(self.repo, "main"))
        self.assertFalse(gitcmd.branch_exists(self.repo, "feat/nope"))

    def test_is_ancestor(self):
        base = gitcmd.run_git(["rev-parse", "HEAD"], cwd=self.repo).stdout.strip()
        self._commit("second")
        head = gitcmd.run_git(["rev-parse", "HEAD"], cwd=self.repo).stdout.strip()
        self.assertTrue(gitcmd.is_ancestor(self.repo, base, head))
        self.assertFalse(gitcmd.is_ancestor(self.repo, head, base))


if __name__ == "__main__":
    unittest.main()
