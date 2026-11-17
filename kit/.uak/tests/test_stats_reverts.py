#!/usr/bin/env python3
"""UAK-089: count reverted task merges using real Git history."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[2]


class StatsReverts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="uak-stats-reverts-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull, "UAK_BASE": "main",
                    "UAK_REMOTE": "origin"}
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(self.repo / "no-hooks"))
        self.initial = self.commit("seed", "initial")
        self.claims = self.repo / "claims-data"
        self.claims.mkdir()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                              text=True, capture_output=True, check=True).stdout.strip()

    def commit(self, name, subject, body=None):
        (self.repo / name).write_text(name + "\n", encoding="utf-8")
        self.git("add", "--", name)
        args = ["commit", "-q", "-m", subject]
        if body:
            args += ["-m", body]
        self.git(*args)
        return self.git("rev-parse", "HEAD")

    def task_merge(self, task):
        self.git("checkout", "-q", "-b", "feature/" + task.lower())
        member = self.commit(task, "feat: " + task)
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "feature/" + task.lower(),
                 "-m", "Merge " + task + " reviewed by reviewer")
        return self.git("rev-parse", "HEAD"), member

    def stats(self):
        result = subprocess.run(["bash", str(PACKAGE / ".uak/bin/stats"),
                                 "--dir", str(self.claims)], cwd=self.repo,
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("REVERTS", result.stdout)
        return result.stdout.split("REVERTS", 1)[1].split("lease recoveries:", 1)[0]

    def test_counts_a_reverted_task_merge(self):
        merge, member = self.task_merge("UAK-101")
        self.task_merge("UAK-102")
        before = self.git("rev-parse", "HEAD")
        for target in (merge, member):
            for detection in ("trailer", "subject"):
                with self.subTest(target=target, detection=detection):
                    self.git("reset", "-q", "--hard", before)
                    if detection == "trailer":
                        args = ["revert", "--no-edit"]
                        if target == merge:
                            args += ["-m", "1"]
                        self.git(*(args + [target]))
                        self.git("commit", "-q", "--amend", "-m", "undo task",
                                 "-m", "This reverts commit " + target + ".")
                    else:
                        title = self.git("show", "-s", "--format=%s", target)
                        self.commit("undo", 'Revert "' + title + '"')
                    reverting = self.git("rev-parse", "--short", "HEAD")
                    self.commit("another-undo", "undo again", "This reverts commit " + member + ".")
                    output = self.stats()
                    self.assertIn("2 merges", output)
                    self.assertIn("1 reverted", output)
                    self.assertIn("50.0%", output)
                    self.assertIn("UAK-101 " + reverting, output)
                    self.assertEqual(output.count("UAK-101"), 1)
                    self.assertNotIn("UAK-102", output)

    def test_ignores_reverts_of_commits_outside_task_merges(self):
        direct = self.commit("direct", "direct change")
        self.task_merge("UAK-101")
        self.git("revert", "--no-edit", direct)
        self.commit("fake", 'Revert "initial"', "This reverts commit " + self.initial + ".")
        self.git("checkout", "-q", "-b", "unmerged")
        self.commit("unmerged-revert", 'Revert "feat: UAK-101"')
        self.git("checkout", "-q", "main")
        output = self.stats()
        self.assertIn("1 merges", output)
        self.assertIn("0 reverted", output)
        self.assertIn("0.0%", output)
        self.assertNotIn("UAK-101", output)

    def test_a_revert_trailer_wins_over_a_shared_title(self):
        self.task_merge("UAK-101")
        direct = self.commit("direct", "feat: UAK-101")
        self.commit("undo", 'Revert "feat: UAK-101"', "This reverts commit " + direct + ".")
        output = self.stats()
        self.assertIn("0 reverted", output)
        self.assertNotIn("UAK-101", output)

    def test_a_branch_name_is_not_a_task_id(self):
        self.task_merge("UAK-101")
        self.git("checkout", "-q", "-b", "me/utf-8-cleanup")
        self.commit("utf", "clean up encodings")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "me/utf-8-cleanup", "-m", "Merge pull request #7 from me/utf-8-cleanup")
        output = self.stats()
        self.assertIn("1 merges", output)

    def test_no_merges_prints_zero_not_an_error(self):
        direct = self.commit("direct", "direct change")
        self.git("revert", "--no-edit", direct)
        self.assertIn("0 merges", self.stats())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PACKAGE)
    args, remaining = parser.parse_known_args()
    PACKAGE = args.package.resolve()
    unittest.main(argv=[__file__, *remaining])
