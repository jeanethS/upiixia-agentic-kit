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

from test_hack import resolve_binary

# Git Bash on Windows: a bare "bash" there is WSL's launcher, which has no distribution on the runners.
BASH = resolve_binary("bash")

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "tla_check.sh"
TLA = REPO / "docs" / "tla"


def source_repo():
    return SCRIPT.is_file() and (TLA / "Claims.tla").is_file()


def run(*args, env=None):
    return subprocess.run([BASH, str(SCRIPT)] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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

    def statechart(self):
        if os.environ.get("UAK_TLA") != "1":
            self.skipTest("TLC needs Java and the pinned jar: the tla workflow runs it (UAK_TLA=1)")
        with tempfile.TemporaryDirectory() as out:
            path = Path(out) / "statechart.md"
            gen = subprocess.run([sys.executable, str(REPO / "scripts" / "tla_statechart.py"), "--out", str(path)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                 timeout=900)
            self.assertEqual(gen.returncode, 0, gen.stdout[-3000:])
            text = path.read_text(encoding="utf-8")
        committed = TLA / "statechart.md"
        self.assertTrue(committed.is_file(), "docs/tla/statechart.md is committed")
        self.assertEqual(committed.read_text(encoding="utf-8"), text,
                         "docs/tla/statechart.md is stale: run python3 scripts/tla_statechart.py")
        return text

    def test_chart_has_every_reachable_task_state(self):
        """UAK-103: the chart is TLC's state graph projected on one task, so it shows every state the model
        reaches and nothing else."""
        text = self.statechart()
        chart = re.search(r"```mermaid\nstateDiagram-v2\n(.*?)```", text, re.S)
        self.assertTrue(chart, "a Mermaid stateDiagram-v2 block")
        states = set(re.findall(r"\b([A-Z]{4,})\b", chart.group(1)))
        self.assertEqual(states, {"AVAILABLE", "CLAIMED", "REVIEW", "INTEGRATED"})
        self.assertNotRegex(chart.group(1), r"\b(\w+) --> \1\b", "an arrow is a change of State")
        for edge in ("AVAILABLE --> CLAIMED", "CLAIMED --> REVIEW", "REVIEW --> INTEGRATED"):
            self.assertIn(edge, chart.group(1))
        self.assertNotIn("INTEGRATED --> ", chart.group(1).replace("INTEGRATED --> [*]", ""),
                         "INTEGRATED is final")

    def test_a_violation_is_drawn_as_its_shortest_path(self):
        """UAK-103: the broken variant's counterexample (TLC searches breadth-first, so it is a shortest one) is
        drawn step by step in task terms and ends on the invariant it breaks."""
        text = self.statechart()
        trace = run(str(TLA / "ClaimsBroken.cfg"), env={"UAK_TLC_WORKERS": "1"})
        steps = len(re.findall(r"^State \d+: ", trace.stdout, re.M))
        broken = re.search(r"Invariant (\w+) is violated", trace.stdout)
        self.assertTrue(steps > 1 and broken, trace.stdout[-3000:])
        path = re.search(r"```mermaid\nflowchart LR\n(.*?)```", text, re.S)
        self.assertTrue(path, "a Mermaid flowchart block for the counterexample")
        self.assertEqual(len(re.findall(r" -->\|", path.group(1))), steps - 1, "one arrow per TLC step")
        self.assertIn(broken.group(1), path.group(1))

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
