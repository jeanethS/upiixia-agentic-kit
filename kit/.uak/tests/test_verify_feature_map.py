#!/usr/bin/env python3
"""UAK-096: lint checks feature maps named by a task's Verify."""
import argparse
import tempfile
import time
from pathlib import Path

from test_hack import Runner, resolve_binary


def uak(r, c, *args):
    return r.run([r.bash, ".uak/bin/uak", *args], cwd=c,
                 env={"UAK_AGENT": "sol-096", "UAK_REMOTE": "origin"}, allowed=None)


def project(r, name):
    f = r.fixture(name, paths={"HACK-001": "src/"}, count=1)
    c = f.clones[0]
    tasks = c / ".uak/TASKS.md"
    text = tasks.read_text(encoding="utf-8").replace(
        "- **Verify:** .uak/bin/smoke --package-only",
        "- **Verify:** `bash .claude/skills/verify-app/run.sh features/checkout.md`")
    tasks.write_text(text, encoding="utf-8")
    return c


def a_missing_feature_file_fails_lint(r):
    c = project(r, "feature-missing")
    out = uak(r, c, "lint")
    text = out.stdout + out.stderr
    assert out.returncode != 0, "a missing feature map must fail lint: " + text
    assert any("HACK-001" in line and "features/checkout.md" in line for line in text.splitlines()), (
        "the failure line must name HACK-001 and features/checkout.md: " + text)
    return "missing feature map rejected with its task ID"


def an_existing_feature_file_passes(r):
    c = project(r, "feature-existing")
    missing = uak(r, c, "lint")
    feature = c / ".claude/skills/verify-app/features/checkout.md"
    feature.parent.mkdir(parents=True)
    feature.write_text("# Checkout\n", encoding="utf-8")
    out = uak(r, c, "lint")
    text = out.stdout + out.stderr
    assert not any("features/checkout.md" in line for line in text.splitlines()), (
        "an existing feature map has no feature diagnostic: " + text)
    before = missing.stdout + missing.stderr
    assert any("HACK-001" in line and "features/checkout.md" in line for line in before.splitlines()), (
        "creating the feature map must remove its missing-file diagnostic: " + before)
    return "creating the feature map clears its diagnostic"


TESTS = [a_missing_feature_file_fails_lint, an_existing_feature_file_passes]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    fails = 0
    with tempfile.TemporaryDirectory(prefix="uak-verify-feature-map-") as tmp:
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
    print("VERIFY_FEATURE_MAP_RESULT %s failed=%d" % ("PASS" if not fails else "FAIL", fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
