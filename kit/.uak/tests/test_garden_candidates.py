#!/usr/bin/env python3
"""UAK-095: repeated judgment rules become check candidates; garden stays read-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest


PACKAGE = Path(__file__).resolve().parents[2]
TESTS = ("a_repeated_judgment_rule_is_listed", "a_rule_with_a_check_is_not_listed",
         "garden_writes_nothing")
CORRECTION = "no, do not invent DOIs"
RULE = "Never invent DOIs"
CHECKED_RULE = "Never delete regression tests"
CHECKED_CORRECTION = "no, do not delete regression tests"


class GardenCandidates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="uak-garden-candidates-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / "project"
        self.repo.mkdir()
        self.home = self.base / "claude"
        self.env = {**os.environ, "UAK_AGENT": "sol-095",
                    "CLAUDE_CONFIG_DIR": str(self.home),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        subprocess.run(["git", "init", "-q", str(self.repo)], env=self.env,
                       check=True, capture_output=True, text=True)
        self.git_dir = self.repo / ".git"
        self.write(".uak/PROJECT.md", "Mode: marathon\n")
        self.write("AGENTS.md", "# Rules\n\nSee .uak/docs/WHY.md.\n")
        self.write(".uak/docs/WHY.md",
                   "# Why\n\n| Rule | Incident / reason | Enforced by |\n|---|---|---|\n"
                   "| " + RULE + " | " + CORRECTION + " | judgment |\n"
                   "| " + CHECKED_RULE + " | " + CHECKED_CORRECTION + " | `test_regressions.py` |\n"
                   "| Reserve separate ports | no, do not reuse ports | judgment |\n")

    def write(self, relative, text):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def seed_evidence(self, source):
        corrections = [CORRECTION, CHECKED_CORRECTION] * 2
        if source == "transcripts":
            main = str(self.git_dir.parent)
            win = subprocess.run(["bash", "-c", 'cygpath -m "$1" 2>/dev/null', "_", main],
                                 env=self.env, capture_output=True, text=True).stdout.strip()
            folder = self.home / "projects" / re.sub(r"[^A-Za-z0-9]", "-", win or main)
            folder.mkdir(parents=True, exist_ok=True)
            lines = [json.dumps({"type": "user", "message": {"role": "user", "content": text},
                                 "uuid": "u"}, separators=(",", ":")) for text in corrections]
            (folder / "s.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            now = int(time.time())
            lines = ["- %d | 5.10 | test | marathon | agent | friction | done | %s | fix: add a check"
                     % (now - len(corrections) + i, text) for i, text in enumerate(corrections)]
            self.write(".git/uak-blackbox.pending", "\n".join(lines) + "\n")

    def garden(self):
        result = subprocess.run(["bash", str(PACKAGE / ".uak/bin/garden")], cwd=self.repo,
                                env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def candidates(self, output):
        lines = output.splitlines()
        self.assertIn("RULES WITHOUT A CHECK", lines,
                      "missing exact RULES WITHOUT A CHECK section:\n" + output)
        section = []
        for line in lines[lines.index("RULES WITHOUT A CHECK") + 1:]:
            if line.startswith("GARDEN:") or re.match(r"^[A-Z][A-Z ]+(?:$| \()", line):
                break
            section.append(line)
        return "\n".join(section)

    def a_repeated_judgment_rule_is_listed(self):
        for source in ("transcripts", "blackbox"):
            with self.subTest(source=source):
                self.seed_evidence(source)
                section = self.candidates(self.garden())
                self.assertIn(RULE, section)
                self.assertRegex(section, r"\b(architecture|type|lint|test|doc)\b")
                self.assertIn(CORRECTION, section, "candidate needs the past failing instance")
                self.assertNotIn("Reserve separate ports", section)
            if source == "transcripts":
                for transcript in self.home.rglob("*.jsonl"):
                    transcript.unlink()

    def a_rule_with_a_check_is_not_listed(self):
        self.seed_evidence("transcripts")
        self.seed_evidence("blackbox")
        section = self.candidates(self.garden())
        self.assertIn(RULE, section)
        self.assertNotIn(CHECKED_RULE, section)
        self.assertNotIn(CHECKED_CORRECTION, section)

    def snapshot(self):
        project = {}
        git_uak = {}
        for path in self.repo.rglob("*"):
            relative = path.relative_to(self.repo)
            if relative.parts[0] == ".git":
                if len(relative.parts) < 2 or not relative.parts[1].startswith("uak"):
                    continue
                target = git_uak
            else:
                target = project
            if path.is_symlink():
                value = ("symlink", os.readlink(path))
            elif path.is_dir():
                value = ("directory", None)
            else:
                value = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
            target[relative.as_posix()] = value
        return project, git_uak

    def garden_writes_nothing(self):
        self.seed_evidence("transcripts")
        self.seed_evidence("blackbox")
        self.write("notes/nested/untracked.txt", "Keep this untracked file.\n")
        self.write(".git/uak-clock", "1000000\n")
        self.write(".git/uak-cache/entry", "Preserve cached state.\n")
        before = self.snapshot()
        self.garden()
        self.assertEqual(self.snapshot(), before, "garden changed project or git-dir uak paths/content")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PACKAGE)
    args = parser.parse_args()
    PACKAGE = args.package.resolve()
    suite = unittest.TestSuite(GardenCandidates(name) for name in TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
