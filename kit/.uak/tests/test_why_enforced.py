#!/usr/bin/env python3
"""UAK-090: rule enforcers exist and dated portability exceptions expire."""
import argparse
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("kit_lint_for_why", REPO / "scripts/kit_lint.py")
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)


class WhyEnforced(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="why-enforced-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.write("kit/.uak/bin/lib/.keep", "")
        self.write("kit/.uak/docs/WHY.md", "| Rule | Reason | Enforced by |\n|---|---|---|\n| Rule | Incident | judgment |\n")

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run_lint(self):
        out = io.StringIO()
        with patch.object(lint, "ROOT", self.root), patch.object(lint, "BIN", self.root / "kit/.uak/bin"), \
                patch.dict(os.environ, KIT_LINT_TODAY="2026-11-17"), patch.object(sys, "argv", ["kit_lint.py"]), \
                patch.object(lint, "check_structure"), patch.object(lint, "check_garden"), \
                patch.object(lint, "check_dogfood"), contextlib.redirect_stdout(out):
            # Only unrelated installer, registry and backlog checks are outside these small fixtures.
            rc = lint.main()
        return rc, out.getvalue()

    def test_a_row_without_enforcer_fails_lint(self):
        for table in ("| Rule | Reason |\n|---|---|\n| New rule | Incident |\n",
                      "| Rule | Reason | Enforced by |\n|---|---|---|\n| New rule | Incident | |\n"):
            with self.subTest(table=table):
                self.write("kit/.uak/docs/WHY.md", table)
                rc, out = self.run_lint()
                self.assertEqual(rc, 1, out)
                self.assertIn("kit/.uak/docs/WHY.md:", out)
                self.assertIn("Enforced by", out)

    def test_an_enforcer_that_does_not_exist_fails_lint(self):
        for enforcer in ("`test_missing.py`", "`kit/.uak/tests/test_missing.py`",
                         "`kit_lint: missing-rule`", "judgment; `test_missing.py`"):
            with self.subTest(enforcer=enforcer):
                self.write("kit/.uak/docs/WHY.md", "| Rule | Reason | Enforced by |\n|---|---|---|\n"
                           "| New rule | Incident | %s |\n" % enforcer)
                rc, out = self.run_lint()
                self.assertEqual(rc, 1, out)
                self.assertIn("kit/.uak/docs/WHY.md:3", out)
                self.assertIn("missing", out)

    def test_an_expired_exception_fails_lint(self):
        for script, line in (("declare -A x # kit-lint: ok (fixture) until 2026-11-16\n", 2),
                             ("# kit-lint: ok (fixture) until 2026-11-16\ndeclare -A x\n", 2),
                             ("echo fine # kit-lint: ok (fixture) until 2026-11-16\n", 2)):
            with self.subTest(script=script):
                self.write("kit/.uak/bin/fixture", "#!/bin/bash\n" + script)
                rc, out = self.run_lint()
                self.assertEqual(rc, 1, out)
                self.assertIn("kit/.uak/bin/fixture:%d" % line, out)
                self.assertIn("expired", out)

    def test_an_undated_exception_still_passes(self):
        for script in ("declare -A x # kit-lint: ok (fixture)\n",
                       "# kit-lint: ok (fixture)\ndeclare -A x\n"):
            with self.subTest(script=script):
                self.write("kit/.uak/bin/fixture", "#!/bin/bash\n" + script)
                rc, out = self.run_lint()
                self.assertEqual(rc, 0, out)

    def test_exception_includes_its_expiry_day(self):
        for date in ("2026-11-17", "2026-11-18"):
            for marker in ("declare -A x # kit-lint: ok (fixture) until %s\n",
                           "# kit-lint: ok (fixture) until %s\ndeclare -A x\n"):
                with self.subTest(date=date, marker=marker):
                    self.write("kit/.uak/bin/fixture", "#!/bin/bash\n" + marker % date)
                    rc, out = self.run_lint()
                    self.assertEqual(rc, 0, out)

    def test_malformed_expiry_fails_lint(self):
        self.write("kit/.uak/bin/fixture", "#!/bin/bash\ndeclare -A x # kit-lint: ok (fixture) until 2026-02-30\n")
        rc, out = self.run_lint()
        self.assertEqual(rc, 1, out)
        self.assertIn("kit/.uak/bin/fixture:2", out)

    def test_existing_enforcers_and_escaped_pipes_pass(self):
        self.write("kit/.uak/tests/test_present.py", "")
        self.write("kit/.uak/docs/WHY.md", "| Rule | Reason | Enforced by |\n|---|---|---|\n"
                   "| Pipe \\| rule | Incident | `test_present.py`; `kit_lint: bash4-assoc` |\n\n"
                   "| Rule | Enforced by | Reason |\n|---|---|---|\n"
                   "| Other | judgment | Incident |\n")
        rc, out = self.run_lint()
        self.assertEqual(rc, 0, out)

    def test_every_rule_table_is_checked(self):
        with (self.root / "kit/.uak/docs/WHY.md").open("a", encoding="utf-8") as f:
            f.write("\n| Rule | Reason | Enforced by |\n|---|---|---|\n| Another | Incident | |\n")
        rc, out = self.run_lint()
        self.assertEqual(rc, 1, out)
        self.assertIn("kit/.uak/docs/WHY.md:7", out)

    def test_unmarked_portability_violation_still_fails(self):
        self.write("kit/.uak/bin/fixture", "#!/bin/bash\ndeclare -A x\n")
        rc, out = self.run_lint()
        self.assertEqual(rc, 1, out)
        self.assertIn("bash4-assoc", out)

    def test_real_why_passes(self):
        findings = []
        lint.check_why_enforced(findings)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=REPO / "kit")
    _, remaining = parser.parse_known_args()
    unittest.main(argv=[sys.argv[0]] + remaining)
