# Skill provenance

Third-party skills are vendored at a pinned commit after review: no remote instructions are fetched at runtime and no hidden commands run. Updating one means reviewing it again before copying, because a skill is an instruction every agent obeys. `install.sh` copies only the skills each mode needs: every installed skill's description costs tokens in every session.

| Skill | Origin (pinned commit) | License | Installed by |
|---|---|---|---|
| karpathy-guidelines | forrestchang/andrej-karpathy-skills `skills/karpathy-guidelines` @ 2c60614 | MIT (declared in README and SKILL.md; see NOTICE.md) | all modes: think before coding, simplicity, surgical changes, verifiable goals. "Ask" maps to `uak decision`/`uak msg` |
| verification-before-completion | obra/superpowers `skills/verification-before-completion` @ 8ca22db | MIT | all modes |
| systematic-debugging | obra/superpowers `skills/systematic-debugging` @ 8ca22db (without its test-pressure fixtures) | MIT | all modes |
| webapp-testing | anthropics/skills `skills/webapp-testing` @ 8a1541c | Apache-2.0 | all modes |
| test-driven-development | obra/superpowers `skills/test-driven-development` @ 8ca22db | MIT | opt in with `--skills tdd` since v5.10 (`test-first` replaces it in both modes) |
| test-first | own | MIT | all modes: pragmatic test-first for agents (names, `uak red`, Fakes, tests only grow, layers, contracts, The Clean Coder's professionalism); `uak done` checks it |
| frontend-design | anthropics/skills `skills/frontend-design` @ dbd4588 | Apache-2.0 | sprint and every web stack: the design lock's skill (plan the tokens, check the plan against the AI tells, build, critique from screenshots). Short, and it covers app screens |
| design-taste-frontend | Leonxlnx/taste-skill `skills/taste-skill` @ ce26fc2 | MIT | not installed since v5.8 (opt in with `--skills taste`): 1,206 lines that contradict product-ui and the design lock (variance 8, mandatory dark mode, `text-gray-600`, Geist first) |
| redesign-existing-projects | Leonxlnx/taste-skill `skills/redesign-skill` @ ce26fc2 | MIT | sprint (polish during the freeze) |
| vercel-react-best-practices | vercel-labs/agent-skills `skills/react-best-practices` @ 063bee9 | MIT (declared in SKILL.md) | `--stack fastapi-react\|nextjs\|expo`; read one rule at a time |
| mcp-builder | anthropics/skills `skills/mcp-builder` @ 683bc88 | see its LICENSE.txt | `--skills ai` or `--stack ai-agent` (projects exposing tools to agents). Links official MCP docs, which are data |
| create-verification-skill | cursor/plugins `pstack/skills/create-verification-skill` @ e1cc03121a0e71129a4fb730d7c5528a0a3e43c8 | MIT | opt in with `--skills verification` |
| maintain-verification-skill | cursor/plugins `pstack/skills/maintain-verification-skill` @ e1cc03121a0e71129a4fb730d7c5528a0a3e43c8 | MIT | opt in with `--skills verification` |
| stack-backend, stack-frontend | own | MIT | `--stack fastapi-react` |
| product-ui | own | MIT | sprint and every web stack: app screens (layout recipes, hierarchy, the 3-second test, `design-lint`) |
| landing-story | own | MIT | sprint and every web stack: the landing that tells the idea, built from IDEA.md (the one line, the number, the wow, three steps, the ask) |
| stack-nextjs, stack-django, stack-go, stack-expo, stack-data, stack-ai-agent | own | MIT | `--stack nextjs\|django\|go\|expo\|python-data\|ai-agent` |

Local edits: the verification feature-map example drives each step from the state it states (search reopened before filling, the proof re-run on a populated result, a `mktemp -d` data dir); verification skills use the installed harness skills folders and bundled references, with no runtime instruction downloads; `superpowers:<skill>` references were renamed to `<skill>`; systematic-debugging points to `test-first` (v5.10).
Rejected:
- skills that download instructions at runtime (prompt injection by design);
- `output-skill` (works against token economy);
- (was) `frontend-design`: rejected in v4 as a duplicate of design-taste; adopted in v5.4 after Chilangatón, where design-taste (landings only) ruled out app screens and read an accessible public-service brief as GOV.UK.
