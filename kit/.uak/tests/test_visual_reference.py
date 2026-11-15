#!/usr/bin/env python3
"""Optional visual concepts never replace browser evidence or require a service."""
import argparse
import tempfile
from pathlib import Path

from test_hack import Runner, expect, resolve_binary


def install(r, name, *options):
    d = r.scratch / name
    d.mkdir()
    r.g(d, "init", "-q", "-b", "main")
    r.run([r.bash, str(r.package.parent / "install.sh"), "--mode", "sprint", *options, str(d)], cwd=d)
    return d


def visual_reference_is_opt_in(r):
    default = install(r, "default", "--harness", "claude,codex")
    for base in (".claude/skills", ".agents/skills"):
        expect(not (default / base / "visual-reference").exists(), "default stays small")
    for harness in ("claude", "codex", "cursor", "gemini"):
        opted = install(r, harness, "--harness", harness, "--skills", "visual-reference")
        expect((opted / ".claude/skills/visual-reference/SKILL.md").is_file(), harness + " receives the skill")
        expect((opted / ".agents/skills/visual-reference/SKILL.md").is_file() == (harness != "claude"),
               "shared skills follow the selected harness")
    expect((default / ".mcp.json").read_bytes() == (r.scratch / "claude/.mcp.json").read_bytes(),
           "opt-in adds no MCP server")


def visual_reference_preserves_no_mcp(r):
    for name, extra in (("no-mcp-default", []), ("no-mcp-opted", ["--skills", "visual-reference"])):
        d = install(r, name, "--harness", "claude,codex,cursor,gemini", "--no-mcp", *extra)
        for base in (".claude/skills", ".agents/skills"):
            expect((d / base / "visual-reference/SKILL.md").is_file() == bool(extra), "no-mcp keeps skill selection")
        expect(not (d / ".mcp.json").exists() and not (d / ".cursor/mcp.json").exists(), "no MCP files")
        expect("[mcp_servers." not in (d / ".codex/config.toml").read_text(), "no Codex MCP")
        expect('"mcpServers"' not in (d / ".gemini/settings.json").read_text(), "no Gemini MCP")


def visual_reference_update_preserves_edits(r):
    d = install(r, "update", "--harness", "claude,codex", "--skills", "visual-reference", "--no-mcp")
    skill = d / ".claude/skills/visual-reference/SKILL.md"
    expect(skill.is_file(), "opt-in skill exists before editing")
    edited = skill.read_text() + "\nTeam-specific reference guidance.\n"
    skill.write_text(edited)
    r.run([r.bash, str(r.package.parent / "install.sh"), "--mode", "sprint", "--harness", "claude,codex",
           "--skills", "visual-reference", "--update", str(d)], cwd=d)
    proposed = (r.package / ".uak/skills/visual-reference/SKILL.md").read_text()
    for base in (".claude/skills", ".agents/skills"):
        dest = d / base / "visual-reference/SKILL.md"
        expect(dest.read_text() == edited, "team edit survives update in " + base)
        expect(Path(str(dest) + ".uak-new").read_text() == proposed, "proposed version is available in " + base)
    expect(not (d / ".mcp.json").exists(), "update keeps MCP off")


def visual_reference_keeps_evidence_separate(r):
    skill = r.package / ".uak/skills/visual-reference/SKILL.md"
    expect(skill.is_file(), "visual-reference skill exists")
    text = skill.read_text()
    for term in ("IDEA.md", "DESIGN.md", "Awwwards", "Mobbin", "untrusted", "source URL", "traits",
                 "three", "one desktop", "one mobile", ".uak-shots/visual-reference/", ".uak-shots/<task ID>/",
                 "concept references", "browser captures", "uak design round", "design shoot", "design pick",
                 "landing-story", "frontend-design", "webapp-testing", "marathon", "uak decision",
                 "human-supplied image", "no image tool", "no MCP", "manual"):
        expect(term in text, "evidence contract names " + term)


TESTS = [visual_reference_is_opt_in, visual_reference_preserves_no_mcp,
         visual_reference_update_preserves_edits, visual_reference_keeps_evidence_separate]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if not (args.package.parent / "install.sh").is_file():
        print("SKIP visual-reference install tests: install.sh is absent")
        return 0
    failed = 0
    with tempfile.TemporaryDirectory(prefix="uak-visual-reference-") as tmp:
        r = Runner(args.package.resolve(), Path(tmp), resolve_binary("bash"), resolve_binary("git"))
        for test in TESTS:
            try:
                test(r)
                print("PASS " + test.__name__)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL " + test.__name__ + ": " + str(exc)[:1500])
    print("VISUAL_REFERENCE_RESULT passed=%d failed=%d" % (len(TESTS) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
