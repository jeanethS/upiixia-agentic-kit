#!/usr/bin/env python3
"""UAK-091: opt-in, offline verification skills across the kit's harnesses."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_hack import Runner, resolve_binary
from test_skills_windows_clone import repo


ROOT = Path(__file__).resolve().parents[3]
SKILLS = ("create-verification-skill", "maintain-verification-skill")
PIN = "e1cc03121a0e71129a4fb730d7c5528a0a3e43c8"


class VerificationSkills(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="uak-verification-")
        self.addCleanup(scratch.cleanup)
        self.runner = Runner(ROOT / "kit", Path(scratch.name), resolve_binary("bash"), resolve_binary("git"))

    def install(self, name, *args):
        target = repo(self.runner, name)
        out = subprocess.run(
            [self.runner.bash, str(ROOT / "install.sh"), *args, "--no-mcp", str(target)],
            env=self.runner.env, capture_output=True, text=True, timeout=180,
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(out.returncode, 0, out.stdout[-1000:] + out.stderr[-1000:])
        return target

    def test_verification_skills_install_only_with_the_flag(self):
        for mode in ("sprint", "marathon"):
            target = self.install("default-" + mode, "--mode", mode)
            for base in (".claude/skills", ".agents/skills"):
                for skill in SKILLS:
                    self.assertFalse((target / base / skill).exists(), str(target / base / skill))
            target = self.install("enabled-" + mode, "--mode", mode, "--skills", "ai,verification,tdd")
            for base in (".claude/skills", ".agents/skills"):
                for skill in SKILLS:
                    source = ROOT / "kit/.uak/skills" / skill
                    self.assertTrue((target / base / skill / "SKILL.md").is_file(), base + "/" + skill)
                    for item in source.rglob("*"):
                        if item.is_file():
                            installed = target / base / skill / item.relative_to(source)
                            self.assertTrue(installed.is_file(), str(installed))
                            self.assertEqual(installed.read_bytes(), item.read_bytes())
        for harness in ("claude", "codex", "cursor", "gemini"):
            target = self.install(harness, "--mode", "sprint", "--harness", harness, "--skills", "verification")
            base = ".claude/skills" if harness == "claude" else ".agents/skills"
            for skill in SKILLS:
                self.assertTrue((target / base / skill / "SKILL.md").is_file(), harness + "/" + skill)
                self.assertFalse((target / ".cursor/skills" / skill).exists())
        target = self.install("similar-flag", "--mode", "sprint", "--skills", "verification-extra")
        for base in (".claude/skills", ".agents/skills"):
            for skill in SKILLS:
                self.assertFalse((target / base / skill).exists())

    def test_vendored_skills_are_pinned_and_licensed(self):
        sources = (ROOT / "kit/.uak/skills/SOURCES.md").read_text(encoding="utf-8")
        licenses = []
        for skill in SKILLS:
            rows = [row for row in sources.splitlines() if row.startswith("| " + skill + " |")]
            self.assertEqual(len(rows), 1, skill + " needs a provenance row")
            self.assertIn("cursor/plugins", rows[0])
            self.assertIn("pstack/skills/" + skill, rows[0])
            self.assertIn(PIN, rows[0])
            self.assertIn("MIT", rows[0])
            self.assertIn("--skills verification", rows[0])
            license_path = ROOT / "kit/.uak/skills" / skill / "LICENSE"
            self.assertTrue(license_path.is_file(), str(license_path))
            license_text = license_path.read_text(encoding="utf-8")
            self.assertIn("MIT License", license_text)
            self.assertIn("Copyright (c) 2026 Lauren Tan", license_text)
            self.assertIn("Permission is hereby granted, free of charge", license_text)
            self.assertIn("THE SOFTWARE IS PROVIDED", license_text)
            licenses.append(license_text)
        self.assertEqual(licenses[0], licenses[1])
        example = ROOT / "kit/.uak/skills/create-verification-skill/references/feature-map-example"
        for name in ("README.md", "create-note.md", "search.md"):
            self.assertTrue((example / name).is_file(), name + " example is shipped")

    def test_vendored_skills_fetch_nothing_at_runtime(self):
        forbidden = re.compile(
            r"poteto-mode|\bswarm\b|\barena\b|\bunslop\b|subagent_type|"
            r"/(?:why|how|architect)\b|\.cursor/skills/|"
            r"\b(?:curl|wget)\s|git\s+(?:clone|fetch|pull)\b|"
            r"https?://(?!127\.0\.0\.1(?=[:/\s`])|localhost(?=[:/\s`]))",
            re.IGNORECASE,
        )
        for skill in SKILLS:
            directory = ROOT / "kit/.uak/skills" / skill
            body_path = directory / "SKILL.md"
            self.assertTrue(body_path.is_file(), str(body_path))
            body = body_path.read_text(encoding="utf-8")
            self.assertTrue(body.startswith("---\nname: " + skill + "\n"), skill)
            self.assertIn(".agents/skills/verify-", body)
            self.assertIn(".claude/skills/verify-", body)
            for item in directory.rglob("*"):
                if item.is_file():
                    self.assertIsNone(forbidden.search(item.read_text(encoding="utf-8")), str(item))


if __name__ == "__main__":
    unittest.main(verbosity=2)
