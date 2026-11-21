#!/usr/bin/env python3
"""UAK-097: done checks evidence pointers against the published task tip. Real Git, local bare remote."""
import argparse
import concurrent.futures
import json
import tempfile
import time
from pathlib import Path

from test_hack import Runner, expect, resolve_binary


def ready(r, name):
    f = r.fixture(name, paths={"HACK-001": "src/app.py"}, count=1)
    f.claim(0, "HACK-001")
    w = f.worktrees[0]
    (w / ".uak-env").write_bytes(b"UAK_TASK=HACK-001\nUAK_AGENT=agent-1\n")
    (w / "src").mkdir(exist_ok=True)
    (w / "src/app.py").write_text("print('hello')\n", encoding="utf-8")
    r.g(w, "add", "src/app.py")
    r.g(w, "commit", "-q", "-m", "HACK-001: a change")
    r.g(w, "push", "-q", "origin", f.branches[0])
    return f


def done(f, evidence):
    return f.hack(0, "--json", "done", "HACK-001", "--pr", "https://example.invalid/pull/1",
                  "--evidence", evidence, "--no-red", "fixture", now=1000010, allowed=None)


def a_missing_sha_is_refused(r):
    f = ready(r, "done-evidence-sha")
    out = done(f, "verified deadbee1.")
    data = json.loads(out.stdout)
    expect(out.returncode == 3 and data["exit"] == 3 and data["result"] == "CONFLICT", out.stdout + out.stderr)
    expect(data["code"] == "evidence-missing", out.stdout)
    expect("deadbee1" in data["message"], out.stdout)


def a_file_line_past_the_end_is_refused(r):
    f = ready(r, "done-evidence-line")
    out = done(f, "checked src/app.py:999)")
    data = json.loads(out.stdout)
    expect(out.returncode == 3 and data["exit"] == 3 and data["result"] == "CONFLICT", out.stdout + out.stderr)
    expect(data["code"] == "evidence-missing", out.stdout)
    expect("src/app.py:999" in data["message"], out.stdout)


def prose_evidence_still_passes(r):
    f = ready(r, "done-evidence-prose")
    out = done(f, "ran the suite, all green")
    data = json.loads(out.stdout)
    expect(out.returncode == 0 and data["ok"] is True and data["state"] == "REVIEW", out.stdout + out.stderr)
    expect("State: REVIEW\n" in f.show("tasks/HACK-001.md"), "done must persist REVIEW")


TESTS = [a_missing_sha_is_refused, a_file_line_past_the_end_is_refused, prose_evidence_still_passes]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="uak-done-evidence-") as tmp:
        runner = Runner(args.package.resolve(), Path(tmp), resolve_binary("bash"), resolve_binary("git"))

        def one(test):
            started = time.monotonic()
            try:
                test(runner)
                return test.__name__, True, "%.2fs" % (time.monotonic() - started)
            except Exception as exc:  # noqa: BLE001
                return test.__name__, False, str(exc)[:2500]

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(one, TESTS))
    for name, ok, info in results:
        print(("PASS " if ok else "FAIL ") + name + " (" + info + ")")
    passed = sum(1 for _, ok, _ in results if ok)
    print("DONE_EVIDENCE_RESULT %s passed=%d failed=%d" % ("PASS" if passed == len(results) else "FAIL", passed, len(results) - passed))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
