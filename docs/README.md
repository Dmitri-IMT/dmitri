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
| [`adr/ADR-011-pi-command-channel.md`](adr/ADR-011-pi-command-channel.md) | Touch the Pi ↔ backend command channel (WebSocket, Ed25519-signed upgrade, command lifecycle) |
| [`adr/ADR-012-headless-exit-code-contract.md`](adr/ADR-012-headless-exit-code-contract.md) | Change how a headless/CLI scan reports outcome (exit codes, `dmitri agent`) |
| [`adr/ADR-018-nspi-active-modbus-safety.md`](adr/ADR-018-nspi-active-modbus-safety.md) | Active Modbus safety bounds and submodes |
| [`adr/ADR-019-v2-active-scanning-and-agent-hardening.md`](adr/ADR-019-v2-active-scanning-and-agent-hardening.md) | Agent hardening, keyed digest, industrial persistence |
| [`adr/ADR-020-ai-scan-analysis.md`](adr/ADR-020-ai-scan-analysis.md) | Groq scan overview, Explain this scan, data boundary |
| [`adr/ADR-021-pi-agent-updates.md`](adr/ADR-021-pi-agent-updates.md) | How a provisioned Pi upgrades `hardware-agent` |

### Product roadmap (`roadmap/`)

| File | Read it when you need to… |
|------|---------------------------|
| [`roadmap/README.md`](roadmap/README.md) | Plan the path to the final product (Pi remote-command, backend/auth, frontend, LLM) — the index + cross-layer sequencing |
| [`roadmap/PI.md`](roadmap/PI.md) / [`BACKEND.md`](roadmap/BACKEND.md) / [`AUTH.md`](roadmap/AUTH.md) / [`FRONTEND.md`](roadmap/FRONTEND.md) / [`AI.md`](roadmap/AI.md) / [`SECURITY.md`](roadmap/SECURITY.md) | Layer direction / open decisions |
| [`cloud/README.md`](cloud/README.md) | Hosted stack (Supabase + Railway), env contract, NSPi ops |
| [`epics/EPICS.md`](epics/EPICS.md) | Cloud/hosting issue epics |

> Roadmap docs are forward-looking and link back to ADRs/ARCHITECTURE. They are kept in sync by
> the **`roadmap-sync`** skill — edit one, run it to find the siblings to re-check.

### Scan & vulnerability pipeline (`implementation/`)

| File | Read it when you need to… |
|------|---------------------------|
| [`implementation/NSE-VULNERABILITY-PIPELINE.md`](implementation/NSE-VULNERABILITY-PIPELINE.md) | Add/modify NSE scripts or the vulnerability pipeline |
| [`implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`](implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md) | Work on the AI/assessment roadmap |
| [`implementation/SCAN-EVIDENCE-CORRECTIONS-2026-09-24.md`](implementation/SCAN-EVIDENCE-CORRECTIONS-2026-09-24.md) | Understand scan coverage, partial-scan reconciliation, CVE confidence and evidence display corrections |

### UI & setup (`ui/`, root)

| File | Read it when you need to… |
|------|---------------------------|
| [`ui/FOUNDATIONS.md`](ui/FOUNDATIONS.md) | Look up any token, colour, type size, spacing step or component pattern for the web UI |
| [`ui/FOUNDATIONS-DECISIONS.md`](ui/FOUNDATIONS-DECISIONS.md) | Understand why a UI value was chosen or retired |
| [`ui/REFERENCE.md`](ui/REFERENCE.md) | Apply the 37signals design principles to any web UI work |
| [`ui/FLOWS.md`](ui/FLOWS.md) | Add or change a web SPA user flow (breadboards) |
| [`ui/SCREENS.md`](ui/SCREENS.md) | Spec a web screen (epicenter, three states, copy, layout) |
| [`ui/IDEAS.md`](ui/IDEAS.md) | Park an unvalidated UI idea |
| [`ui/DESIGN-SYSTEM-RESEARCH.md`](ui/DESIGN-SYSTEM-RESEARCH.md) | Read the DMI-131 research record behind Foundations v2 |
| [`ui/mockups/`](ui/mockups/) | See the approved screen mockups; v4 is the exemplar |
| [`DEV-SETUP.md`](DEV-SETUP.md) | Set up the dev environment / run the agent, database, backend or frontend locally |
| [`PI-INSTALLER.md`](PI-INSTALLER.md) | Deploy, provision and register a Raspberry Pi appliance on-site (vendor playbook) |
| [`PI-RECOVERY.md`](PI-RECOVERY.md) | Diagnose parked, refused, offline, or damaged Raspberry Pi appliances |
| [`tests/nspi-modbus-inventory.md`](tests/nspi-modbus-inventory.md) | Laboratory checklist for NSPi inventory |
| [`tests/nspi-modbus-read-only-mapping.md`](tests/nspi-modbus-read-only-mapping.md) | Laboratory checklist for read-only mapping |
| [`examples/ot-policy.example.json`](examples/ot-policy.example.json) | Sample OT mapping policy |

## Global conventions (apply everywhere)

- **Stack:** Python 3.11+, Textual TUI, pydantic v2. Agent source under
  `hardware-agent/src/agent/`.
- **Tests:** `uv run pytest` (inside `hardware-agent/`); lint with `uv run ruff check`.
- **Style:** no comments or docstrings in new code, including tests.
- **Integration rule:** `ScanRunner` (`scanner/runner.py`) bypasses `ScanOrchestrator.run()` —
  thread any new orchestrator/runner parameter through `ScanRunner` and `ScanProgressScreen`
  too (see `.claude/CLAUDE.md`).
- **Specs:** new features are planned with `/feature-planning` (flat docs under
  `specs/NNN-feature-slug/`); see `.claude/docs/pipeline.md`.
- Keep docs short — code-first, no filler.
