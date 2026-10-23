# Tasks — R6 scan and machine redesign (`052-ai-assistant-upgrade`)

Six implementation and verification tasks. Phases A and B are committed in `0e96c75` and `37d4e7f`.
The owner authorized phases C–E in the pasted R6 plan. Tasks 1–5 are complete. Verification ran; the full backend gate has unrelated failures (see PROGRESS.md).

## Task 1: Build structured scan and machine explanations
- **Description**: Complete phase C, including the existing uncommitted model/schema/migration work. Keep provider context anonymous, validate counts, share the chat daily limit, and cache by scope, context, language and prompt version. Refresh host caches when their latest scan changes. Absorbed: prompt files and usage metadata, verified through provider and route tests.
- **Dependencies**: Phase B
- **Target Files**: `backend/src/api/models/persistence.py`, `backend/alembic/versions/20261024_47_ai_explanations.py`, `backend/src/api/schemas/ai.py`, `backend/src/api/routers/ai.py`, `backend/src/api/services/ai/explanations.py`, `backend/src/api/services/ai/openai_responses.py`, `backend/src/api/services/ai/writing.py`, `backend/src/api/services/ai/instructions/explain-scan.md`, `backend/src/api/services/ai/instructions/explain-machine.md`, `backend/src/api/services/deletion.py`
- **Tests**: `backend/tests/test_ai_explanations.py`: cache, tenancy, host refresh, shared daily limit, count checks and anonymous provider inputs. Python review role: code-reviewer-high.
- **Success Criteria**: POST `/api/v1/ai/explain` returns validated structured text; cached reads make no provider call; errors retain usage; scan/machine deletion clears explanations.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Publish the explanation contract and panel
- **Description**: Generate OpenAPI and TypeScript types; connect the structured explanation to a focus-managed right side panel with waiting, Cancel, retry, task pointer and assistant entry.
- **Dependencies**: Task 1
- **Target Files**: `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`, `frontend/src/api/ai.ts`, `frontend/src/api/queryKeys.ts`, `frontend/src/components/SidePanel.tsx`, `frontend/src/components/ExplainPanel.tsx`
- **Tests**: `frontend/src/components/ExplainPanel.test.tsx`: ready, waiting, cancel, retry and focus behavior. Frontend review role: frontend-code-reviewer.
- **Success Criteria**: Both scopes render their structured fields; pointer data comes from tasks; request errors use toasts; regeneration is reproducible.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Build hints and the shared vulnerability view
- **Description**: Implement DESIGN §§6–7 and 17 with one open hint, backend risk parts, AI fix/task fields, scanner fallback, fixed and waiting states, and collapsed technical details. Replace both finding panels and remove inline finding chats.
- **Dependencies**: Phase B
- **Target Files**: `frontend/src/components/TermHint.tsx`, `frontend/src/components/RiskBreakdownHint.tsx`, `frontend/src/components/VulnerabilityView.tsx`, `frontend/src/pages/scans/FindingPanel.tsx`, `frontend/src/pages/hosts/HostFindings.tsx`, `frontend/src/index.css`, `frontend/src/i18n/messages/en.ts`, `frontend/src/i18n/messages/pt-BR.ts`, `frontend/src/i18n/messages/ru.ts`
- **Tests**: `frontend/src/components/TermHint.test.tsx`, `frontend/src/components/VulnerabilityView.test.tsx`: keyboard hints and view states. Frontend review role: frontend-code-reviewer-high.
- **Success Criteria**: All prescribed selectors and scores exist; no duplicated formula; facts and references remain accessible; advice has exactly one active source.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Compose the scan page
- **Description**: Implement DESIGN §§4–5 and 14–16: story, to-do, meaning, risk-sorted expandable problems, and counted IT sections. Preserve running/failed/stopped states, evidence filtering and deep links.
- **Dependencies**: Tasks 2, 3
- **Target Files**: `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/scans/ScanDetailHeader.tsx`, `frontend/src/pages/scans/StoryStrip.tsx`, `frontend/src/pages/scans/MeaningTable.tsx`, `frontend/src/components/ProblemsTable.tsx`, `frontend/src/components/ItSections.tsx`, `frontend/src/pages/scans/TodoList.tsx`, `frontend/src/pages/scans/ScanReports.tsx`
- **Tests**: `frontend/src/pages/ScanDetail.test.tsx`, `frontend/src/components/ProblemsTable.test.tsx`: order, coverage, evidence filter, five-row limit, deep links. Frontend review role: frontend-code-reviewer-high.
- **Success Criteria**: Page follows approved order, old summary strip is removed, and exposure links open the correct finding or IT section.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Compose the machine page and assistant entry
- **Description**: Implement 053 §1.2 and 052 §19: about, best task by number of this machine's latest-scan findings, shared problems, IT sections and explanation. Move the assistant trigger into the top bar and restyle messages.
- **Dependencies**: Tasks 2, 3, 4
- **Target Files**: `frontend/src/pages/HostDetail.tsx`, `frontend/src/pages/hosts/MachineAbout.tsx`, `frontend/src/pages/hosts/MachineBestFix.tsx`, `frontend/src/components/TopBar.tsx`, `frontend/src/components/GlobalAssistant.tsx`, `frontend/src/components/ContextChat.tsx`, `frontend/src/components/AppShell.tsx`
- **Tests**: `frontend/src/pages/HostDetail.test.tsx`, `frontend/src/components/TopBar.test.tsx`, `frontend/src/components/ContextChat.test.tsx`: latest-scan task selection, fallback, assistant context and cancellation. Frontend review role: frontend-code-reviewer-high.
- **Success Criteria**: Machine advice uses its findings from its latest scan; global assistant has one top-bar entry and works from explanation panels.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Verify the complete redesign
- **Description**: Run required backend/frontend gates, update factual code-map/spec progress, and inspect scan/machine pages in the browser. Attempt one real analysis and explanation with available local credentials/data; report any external limitation precisely.
- **Dependencies**: Tasks 1–5
- **Target Files**: `specs/052-ai-assistant-upgrade/TASKS.md`, `specs/052-ai-assistant-upgrade/PRD.md`, `.claude/docs/backend/ai.md`, `.claude/docs/frontend/screens.md`, `.claude/docs/frontend/scan-ai.md`, `.claude/docs/frontend/host-detail.md`, `.claude/docs/log.md`
- **Tests**: `./database.sh --test`; backend `uv run ruff check src tests`; frontend lint, format:check, typecheck, test, build; clean type regeneration; live browser checks.
- **Success Criteria**: Gates pass with live `dmitri_test`; phase commits contain scoped changes; documentation describes final behavior; live checks or exact blockers recorded.
- **Status**: VERIFIED WITH LIMITATIONS
- **Review Rejections**: 0

## Dependency graph

`B → #1 → #2 → #4 → #5 → #6`; `B → #3 → #4`.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Structured explanations | COMPLETED |
| 2 | Contract and panel | COMPLETED |
| 3 | Hints and vulnerability view | COMPLETED |
| 4 | Scan page | COMPLETED |
| 5 | Machine page and assistant | COMPLETED |
| 6 | Verification | VERIFIED WITH LIMITATIONS |
