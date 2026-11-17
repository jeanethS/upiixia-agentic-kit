#!/usr/bin/env python3
"""UAK-093: reviewers name the safety fact, its proof level and what could break."""
import argparse
import subprocess
import sys
import unittest
from pathlib import Path


LADDER = "said, pointed at file:line, walked, ran a script, reproduced in the app"


def flat(path):
    return " ".join(path.read_text(encoding="utf-8").split())


class ReviewerBlastRadiusTests(unittest.TestCase):
    package = Path(__file__).resolve().parents[2]

    def test_reviewer_asks_for_the_safety_fact_and_its_level(self):
        text = flat(self.package / ".claude/agents/uak-reviewer.md")
        self.assertIn("one fact the change is safe because of", text)
        self.assertIn(LADDER, text)
        self.assertRegex(text, r'below ["`]ran a script["`][^.]*reported as ["`]?unproven\b')
        self.assertRegex(
            text,
            r"`uak map users`.*?`uak map impact`.*?starting point for what the change could break",
        )

    def test_generated_reviewers_match_the_source(self):
        gen = self.package.parent / "scripts/gen_harness.py"
        with self.subTest(check="gen_harness.py --check"):
            if not gen.is_file():
                self.skipTest("installed project: scripts/gen_harness.py is absent")
            out = subprocess.run(
                [sys.executable, str(gen), "--check"],
                capture_output=True, text=True, errors="replace", timeout=120,
            )
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        for rel in (
            ".codex/agents/uak-reviewer.toml",
            ".cursor/agents/uak-reviewer.md",
            ".gemini/agents/uak-reviewer.md",
        ):
            with self.subTest(path=rel):
                self.assertIn(LADDER, flat(self.package / rel))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    args, remaining = parser.parse_known_args()
    ReviewerBlastRadiusTests.package = args.package.resolve()
    unittest.main(argv=[sys.argv[0]] + remaining)


if __name__ == "__main__":
    main()
