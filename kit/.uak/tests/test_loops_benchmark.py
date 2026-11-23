#!/usr/bin/env python3
"""UAK-100: LOOPS.md asks seven questions before a speedup is reported."""
import sys
from pathlib import Path

LOOPS = Path(__file__).resolve().parents[1] / "docs" / "LOOPS.md"
QUESTIONS = [
    "limiter",
    "tuned like production",
    "physical limit",
    "errors",
    "median and range",
    "end to end",
    "inside the timed region",
]


def section():
    text = LOOPS.read_text(encoding="utf-8")
    start = text.find("## Before reporting a speedup")
    if start < 0:
        return ""
    end = text.find("\n## ", start + 1)
    return text[start:end if end > 0 else len(text)].lower()


def loops_lists_the_seven_questions():
    body = section()
    missing = [q for q in QUESTIONS if q not in body]
    assert not missing, "LOOPS.md benchmark checklist misses: %s" % ", ".join(missing)
    numbered = [line for line in body.splitlines() if line[:3].rstrip(".").strip().isdigit()]
    assert len(numbered) == 7, "expected 7 numbered questions, got %d" % len(numbered)
    assert "inconclusive" in body, "the checklist must allow the verdict inconclusive"


TESTS = [loops_lists_the_seven_questions]

if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        try:
            test()
            print("PASS", test.__name__)
        except AssertionError as error:
            failed += 1
            print("FAIL", test.__name__, error)
    print("LOOPS_BENCHMARK_RESULT", "FAIL" if failed else "PASS", "passed=%d failed=%d" % (len(TESTS) - failed, failed))
    sys.exit(1 if failed else 0)
