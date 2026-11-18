#!/usr/bin/env python3
"""UAK-092: docs/tla/Claims.tla models the claims protocol (one TLA+ step = one push to the claims branch) and
scripts/tla_check.sh runs TLC on it. The check must mean something: the same model with the push's tip check removed
has to yield a counterexample. TLC needs Java, which neither the engine nor the kit payload depends on, so the two
model runs happen only with UAK_TLA=1 (the tla workflow sets it); the jar pin is checked everywhere."""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "tla_check.sh"
TLA = REPO / "docs" / "tla"


def source_repo():
    return SCRIPT.is_file() and (TLA / "Claims.tla").is_file()


def run(*args, env=None):
    return subprocess.run(["bash", str(SCRIPT)] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, env=dict(os.environ, **(env or {})), timeout=900)


class TlaCheck(unittest.TestCase):
    def setUp(self):
        if not (REPO / "scripts").is_dir():
            self.skipTest("no kit source repository here: the model lives in its docs/tla")
        self.assertTrue(source_repo(), "scripts/tla_check.sh and docs/tla/Claims.tla must exist")

    def model_run(self, cfg):
        if os.environ.get("UAK_TLA") != "1":
            self.skipTest("TLC needs Java and the pinned jar: the tla workflow runs it (UAK_TLA=1)")
        return run(str(TLA / cfg))

    def test_the_model_passes(self):
        out = self.model_run("Claims.cfg")
        self.assertEqual(out.returncode, 0, out.stdout[-3000:])
        self.assertIn("No error has been found", out.stdout)

    def test_the_broken_variant_fails_with_a_counterexample(self):
        out = self.model_run("ClaimsBroken.cfg")
        self.assertNotEqual(out.returncode, 0, out.stdout[-3000:])
        self.assertRegex(out.stdout, r"Invariant \w+ is violated")
        self.assertIn("State 1:", out.stdout, "TLC prints the counterexample trace")

    def test_the_per_agent_variant_is_checked(self):
        """UAK-098: the ADR on per-agent claim files records the outcome TLC actually gives for that variant."""
        adr = REPO / "docs" / "adr" / "0001-claims-per-agent-files.md"
        self.assertTrue((TLA / "ClaimsPerAgent.tla").is_file() and adr.is_file(),
                        "docs/tla/ClaimsPerAgent.tla and docs/adr/0001-claims-per-agent-files.md must exist")
        recorded = re.search(r"^TLC result: (no error|(\w+) is violated)$", adr.read_text(encoding="utf-8"), re.M)
        self.assertTrue(recorded, "the ADR states 'TLC result: no error' or 'TLC result: NAME is violated'")
        out = self.model_run("ClaimsPerAgent.cfg")
        if recorded.group(1) == "no error":
            self.assertEqual(out.returncode, 0, out.stdout[-3000:])
            self.assertIn("No error has been found", out.stdout)
        else:
            self.assertNotEqual(out.returncode, 0, out.stdout[-3000:])
            self.assertIn("Invariant %s is violated" % recorded.group(2), out.stdout)

    def test_the_jar_is_pinned_by_hash(self):
        text = SCRIPT.read_text(encoding="utf-8")
        version = re.search(r'^TLA_VERSION=([0-9][0-9.]*)$', text, re.M)
        sha = re.search(r'^TLA_SHA256=([0-9a-f]{64})$', text, re.M)
        self.assertTrue(version and sha, "tla_check.sh pins TLA_VERSION and TLA_SHA256")
        self.assertIn("releases/download/v$TLA_VERSION/tla2tools.jar", text)
        with tempfile.TemporaryDirectory() as cache:
            jar = Path(cache) / ("tla2tools-%s.jar" % version.group(1))
            jar.write_bytes(b"not the pinned jar")
            out = run(str(TLA / "Claims.cfg"), env={"UAK_TLA_CACHE": cache, "JAVA": "false"})
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("SHA-256 mismatch", out.stdout)
            self.assertFalse(jar.exists(), "a jar with the wrong hash is deleted, never run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package")
    _, remaining = parser.parse_known_args()
    unittest.main(argv=[sys.argv[0]] + remaining, verbosity=2)
