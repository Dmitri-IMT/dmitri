# Codex harness preparation

Prepared on branch `feature/scan-adjusts-improve` for future work. This changes the repository
harness only. `.claude/docs/` remains the canonical code-map; no second code-map was created.

## Installed skills

Repo skills are in `.agents/skills/` and Codex discovers them at session startup. The installed
set is the requested Delivery A workflow: `consult-docs`, `feature-planning`, `create-tasks`,
`feature-orchestrator`, `tdd`, `frontend-conventions`, `frontend-design-system`,
`openapi-contract-sync`, and `docs-sync`. The TDD references and the feature-planning/task
references are included. The task skill has a local copy of the canonical task template.

The frontend skills refer to existing `docs/` guidance and each other through skill names.
`docs-sync` links to the canonical `.claude/docs/MAINTAINING.md` with a corrected relative path.
It reports unhandled ADR and roadmap work when the optional `architecture-adr-sync` or
`roadmap-sync` skills are not installed. Claude-only tool calls were removed or described in
Codex terms. OpenAPI contract conflicts remain a human decision.

## Agents and model selection

Project agents are in `.codex/agents/*.toml`; `.codex/config.toml` enables agents and caps
concurrency at one. The harness defines 11 profiles; sequential orchestration closes or releases
each completed worker using the client's supported lifecycle action, or uses separate sequential
sessions when no close action is exposed, before opening the next role.

| Work | Agent profile | Model and effort |
|---|---|---|
| Orchestration | `feature-orchestrator` | GPT-6.1 Sol, medium |
| Architecture | `architecture-agent` | GPT-6.1 Sol, high |
| UI design | `frontend-design-agent` | GPT-6 Luna, medium |
| Coding/testing | `agent-developer`, `test-engineer`, `frontend-test-engineer` | GPT-6 Luna, medium |
| Standard review | `code-reviewer`, `frontend-code-reviewer` | GPT-6.1 Sol, medium |
| Evidence-sensitive review | `code-reviewer-high`, `frontend-code-reviewer-high` | GPT-6.1 Sol, high |
| Documentation closeout | `docs-sync-agent` | GPT-6 Luna, medium |

Choose the matching reviewer profile at the actual spawn step. A prompt that merely names a
model does not change the running model. If a profile is unavailable in a client, start a
separate Codex session with that model and effort selected in the real CLI/UI settings; do not
silently substitute a model. In the CLI, the session-level selection is `-m` and
`-c model_reasoning_effort=...`; custom agent profiles remain the preferred per-role selector.

The orchestrator skill preserves the sequential coder → tester → reviewer gate, a new coder
after rejection, architecture reconsideration when the same cause recurs twice, structural
re-evaluation and human approval at rejection four, reviewer-owned gates, and one docs-sync at
feature closeout. No permission or approval setting was changed. The configured orchestrator
profile is selectable in a client; it does not change the model running the parent session.

## Verification and limits

- Confirmed the active branch is `feature/scan-adjusts-improve`; existing untracked research
  files were present and left untouched.
- Confirmed Codex CLI version `0.162.0-alpha.17.2` and checked its help output.
- Consulted current official Codex skills and subagent docs for `.agents/skills`,
  `.codex/agents/*.toml`, custom-agent fields, and model/reasoning settings.
- Checked skill resources and relative Markdown links, parsed TOML, and validated skill
  frontmatter and names locally without starting a model session.
- `codex debug prompt-input` listed the nine repository skills and their metadata without
  starting a model inference. It confirmed skill discovery in this checkout.
- Custom agent TOML matches the documented schema and parsed locally. This preparation did not
  execute the native TOML profiles; confirm them in the next Codex client session. Model workers
  used for preparation were selected explicitly through this session's delegation tool. Project
  settings apply to new sessions, not this active session or other agent tools.

Official references: [Codex skills](https://learn.chatgpt.com/docs/build-skills) and
[Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).
