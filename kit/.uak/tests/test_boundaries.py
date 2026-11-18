#!/usr/bin/env python3
"""UAK-094: lint enforces import boundaries from the real code map.

Rules: FROM_GLOB !-> TO_GLOB  reason
Exceptions: allow FILE -> FILE since YYYY-MM-DD  reason
"""
import argparse
import tempfile
import time
from pathlib import Path

from test_hack import Runner, resolve_binary


RULE = "src/ui/* !-> src/db/*  UI must use the service layer\n"
EXCEPTION = "allow src/ui/x.py -> src/db/y.py since 2026-01-01  Legacy import awaiting migration\n"
IMPORTER = '"""UI entry point."""\n\nfrom src.db.y import load\n\ndef render():\n    return load()\n'


def uak(r, c, *args):
    return r.run([r.bash, ".uak/bin/uak", *args], cwd=c,
                 env={"UAK_AGENT": "sol-094", "UAK_REMOTE": "origin"}, allowed=None)


def build_map(r, c):
    out = uak(r, c, "map")
    assert out.returncode == 0, "map builds: " + out.stdout + out.stderr
    deps = uak(r, c, "map", "deps", "src/ui/x.py")
    assert deps.returncode == 0 and "src/db/y.py" in deps.stdout, (
        "map sees the real Python import: " + deps.stdout + deps.stderr)


def project(r, name):
    f = r.fixture(name, paths={"HACK-001": "src/"}, count=1)
    c = f.clones[0]
    (c / "src/ui").mkdir(parents=True)
    (c / "src/db").mkdir(parents=True)
    (c / "src/ui/x.py").write_text(IMPORTER, encoding="utf-8")
    (c / "src/db/y.py").write_text("def load():\n    return 1\n", encoding="utf-8")
    build_map(r, c)
    return c


def an_import_across_a_boundary_fails_lint(r):
    c = project(r, "boundary-fails")
    baseline = uak(r, c, "lint")
    assert baseline.returncode == 0, "fixture lint passes: " + baseline.stdout + baseline.stderr
    (c / ".uak/boundaries").write_text(RULE, encoding="utf-8")
    out = uak(r, c, "lint")
    assert out.returncode != 0, "a forbidden UI -> DB import must fail lint: " + out.stdout + out.stderr
    return "forbidden import rejected"


def no_boundaries_file_is_silent(r):
    c = project(r, "boundary-absent")
    assert not (c / ".uak/boundaries").exists(), "fixture has no boundaries file"
    out = uak(r, c, "lint")
    text = out.stdout + out.stderr
    assert out.returncode == 0, "no boundaries file leaves lint passing: " + text
    assert "boundar" not in text.lower(), "no boundary diagnostics without a boundaries file: " + text
    assert "src/ui/x.py" not in text and "src/db/y.py" not in text, "no import diagnostics: " + text
    return "silent"


def a_listed_exception_passes(r):
    c = project(r, "boundary-exception")
    (c / ".uak/boundaries").write_text(RULE + EXCEPTION, encoding="utf-8")
    out = uak(r, c, "lint")
    assert out.returncode == 0, "a dated exception permits the existing import: " + out.stdout + out.stderr
    (c / "src/ui/new.py").write_text(IMPORTER, encoding="utf-8")
    build_map(r, c)
    out = uak(r, c, "lint")
    text = out.stdout + out.stderr
    assert out.returncode != 0, "the dated exception must not permit a new importer: " + text
    assert any("src/ui/new.py:3" in line and "src/db/y.py" in line for line in text.splitlines()), (
        "only the unlisted import is rejected: " + text)
    assert "src/ui/x.py:3" not in text, "the listed import remains exempt: " + text
    return "dated exception permits only its file pair"


def the_failure_names_file_line_and_reason(r):
    c = project(r, "boundary-diagnostic")
    (c / ".uak/boundaries").write_text(RULE, encoding="utf-8")
    out = uak(r, c, "lint")
    text = out.stdout + out.stderr
    assert any("src/ui/x.py:3" in line and "src/db/y.py" in line
               and "UI must use the service layer" in line for line in text.splitlines()), (
        "the failure line must name src/ui/x.py:3, src/db/y.py and the rule reason: " + text)
    assert out.returncode != 0, "a boundary diagnostic fails lint: " + text
    return "importer line, imported file and reason reported together"


TESTS = [an_import_across_a_boundary_fails_lint, no_boundaries_file_is_silent,
         a_listed_exception_passes, the_failure_names_file_line_and_reason]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    fails = 0
    with tempfile.TemporaryDirectory(prefix="uak-boundaries-") as tmp:
        runner = Runner(args.package.resolve(), Path(tmp), resolve_binary("bash"), resolve_binary("git"))
        for test in TESTS:
            if args.case and test.__name__ not in args.case:
                continue
            started = time.monotonic()
            try:
                note = test(runner)
                print("PASS %s (%s, %.2fs)" % (test.__name__, note, time.monotonic() - started))
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print("FAIL %s (%s: %s)" % (test.__name__, type(exc).__name__, str(exc)[:2500]))
    print("BOUNDARIES_RESULT %s failed=%d" % ("PASS" if not fails else "FAIL", fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
