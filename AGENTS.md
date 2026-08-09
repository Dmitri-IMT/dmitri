## Integration rules

When wiring a new module into the codebase, trace ALL call paths that reach
the affected code — not just the primary pipeline. In this project the TUI has
its own scan runner (`ScanRunner` in `scanner.py`) that bypasses
`ScanOrchestrator.run()` and calls discovery functions directly. Any new
parameter added to the orchestrator (e.g. `workspace_root`) MUST also be
threaded through `ScanRunner` and `ScanProgressScreen` so TUI-initiated scans
receive it. Before marking an integration task complete, grep for every
constructor/call site of the changed class and verify each one passes the new
parameter.

## No temporary code

Do not build temporary implementations, stopgap abstractions, or partial replacements that a
known follow-up will immediately remove. Build each feature in its intended complete shape. If
that is not possible within the requested scope or current constraints, state the limitation and
ask the user to decide how to proceed rather than silently shipping temporary code.

## Formatting and lint gates

**Never run a repo-wide formatter.** Not `ruff format`, not `black .`, not `./lint.sh`
from the root. Automated formatting is scoped to `hardware-agent/` (see
`.pre-commit-config.yaml`); `backend/` has never been formatted by either tool, so
`uv run ruff format` rewrites ~32 unrelated files and buries your diff. Decided
2026-07-30: **`ruff check` is the backend's only Python gate** — backend code is
formatted by hand to match its neighbours.

Per-layer gates:

| Layer | Gate |
|-------|------|
| `hardware-agent/` | `uv run pytest`; black + ruff run from the pre-push hooks |
| `backend/` | `uv run ruff check src tests` and `uv run pytest` — never `ruff format` |
| `frontend/` | `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` |

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
