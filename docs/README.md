# Knowledge Base — Dmitri

> **Location:** `docs/` (canonical). Use the **`consult-docs`** skill for selective loading.

> **For the AI agent:** this is a routing index. **Do not load every file.** Read this table,
> then open **only** the document(s) relevant to the current task (max two).

## How to use this knowledge base

1. Identify the task domain (architecture? scan methodology? security? NSE/vuln pipeline? UI?
   deployment? database?).
2. Open the matching file from the tables below.
3. Load a second file only if the task genuinely spans two domains (max two).

## Index

### Architecture (`architecture/`, `diagrams/`)

| File | Read it when you need to… |
|------|---------------------------|
| [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) | Understand the overall system and where a feature fits |
| [`diagrams/ComponentDiagram.mmd`](diagrams/ComponentDiagram.mmd) | See the component relationships |

### Decisions (`adr/`)

| File | Read it when you need to… |
|------|---------------------------|
| [`adr/ADR-001-hardware-selection.md`](adr/ADR-001-hardware-selection.md) | Know the target hardware (Raspberry Pi) constraints |
| [`adr/ADR-002-scanning-tools-selection.md`](adr/ADR-002-scanning-tools-selection.md) | Know which scanning tools (nmap, NSE) are sanctioned |
| [`adr/ADR-003-backend-stack.md`](adr/ADR-003-backend-stack.md) | Touch the backend stack |
| [`adr/ADR-004-scan-methodology.md`](adr/ADR-004-scan-methodology.md) | Add or change a scan mode / methodology |
| [`adr/ADR-005-security-model.md`](adr/ADR-005-security-model.md) | Touch auth, permissions, or data handling |
| [`adr/ADR-006-additional-tools.md`](adr/ADR-006-additional-tools.md) | Consider adding an external tool |
| [`adr/ADR-007-deployment-architecture.md`](adr/ADR-007-deployment-architecture.md) | Touch deployment / packaging |
| [`adr/ADR-008-frontend-stack.md`](adr/ADR-008-frontend-stack.md) | Touch the frontend stack |
| [`adr/ADR-009-database-stack.md`](adr/ADR-009-database-stack.md) | Touch persistence / database |
| [`adr/ADR-010-scan-contingency-policy.md`](adr/ADR-010-scan-contingency-policy.md) | Decide when a scan stops vs. continues on errors (timeouts, partial results, taxonomy) |

### Scan & vulnerability pipeline (`implementation/`)

| File | Read it when you need to… |
|------|---------------------------|
| [`implementation/NSE-VULNERABILITY-PIPELINE.md`](implementation/NSE-VULNERABILITY-PIPELINE.md) | Add/modify NSE scripts or the vulnerability pipeline |
| [`implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`](implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md) | Work on the AI/assessment roadmap |

### UI & setup (`ui/`, root)

| File | Read it when you need to… |
|------|---------------------------|
| [`ui/wireframes.md`](ui/wireframes.md) | Design or change a TUI screen |
| [`DEV-SETUP.md`](DEV-SETUP.md) | Set up the dev environment / run the agent |

## Global conventions (apply everywhere)

- **Stack:** Python 3.11+, Textual TUI, pydantic v2. Agent source under
  `hardware-agent/src/agent/`.
- **Tests:** `uv run pytest` (inside `hardware-agent/`); lint with `uv run ruff check`.
- **Style:** no comments or docstrings in new code, including tests.
- **Integration rule:** the TUI's `ScanRunner` bypasses `ScanOrchestrator.run()` — thread any
  new orchestrator/runner parameter through `ScanRunner` and `ScanProgressScreen` too (see
  `.claude/CLAUDE.md`).
- **Specs:** new features are planned with `/feature-planning` (flat docs under
  `specs/NNN-feature-slug/`); see `.claude/docs/pipeline.md`.
- Keep docs short — code-first, no filler.
