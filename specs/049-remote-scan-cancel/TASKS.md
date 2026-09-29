# Tasks — Remote scan cancel (`049-remote-scan-cancel`)

10 tasks. **Completed: #1–10 (all).** Assign one task at a time to a fresh implementation subagent.

`plan.md` is the approved source for this feature; this directory has no separate `TRUTH.md`, `ARCHITECTURE.md`, or `DESIGN.md`. The paths below come from its Steps, with existing test files named for each task. A task may be reviewed independently once its dependencies are complete. Avoid concurrent edits to shared files.

Review gates: `hardware-agent/`: `uv run pytest`; `backend/`: `./database.sh --test`, then `uv run ruff check src tests` and `uv run pytest`; `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. Never run a repo-wide formatter or `ruff format` on backend code. Use `test-engineer` / `code-reviewer` for Python tasks and `frontend-test-engineer` / `frontend-code-reviewer` for frontend tasks.

---

## Task 1: Parse and deliver Pi cancel frames
- **Description**: Extend the device command-channel protocol in `plan.md` so the Pi parses a `cancel` frame by `type`, invokes an `on_cancel` callback, and can send `cancelled` status. Preserve the existing behavior for unknown frames. Amend ADR-011 with the new frame and status.
- **Absorbed**: The ADR amendment and `AgentStatus` literal are covered by the protocol tests and do not warrant separate implementation cycles.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/transport/command_channel.py`, `hardware-agent/tests/unit/test_command_channel.py`, `docs/adr/ADR-011-pi-command-channel.md`]
- **Tests**: `test_command_channel.py` proves cancel dispatch, status serialization, and rejection of malformed frames without breaking command dispatch.
- **Success Criteria**:
  - A valid `{"type":"cancel","command_id":"<uuid>"}` reaches `on_cancel` with the correct ID through `run()` / `_serve_once`.
  - `AgentStatus` accepts `cancelled`; unknown frames remain ignored as specified in `plan.md`.
  - ADR-011 describes the new frame and terminal status.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Stop remote scans and report the honest outcome
- **Description**: Wire the cancel callback into the daemon per `plan.md` decisions 2, 8, 11–13. Distinguish remote cancel from park/revoke, stop only an active scan before upload, upload any partial payload, and release the command hold on terminal `cancelled`.
- **Dependencies**: Task 1
- **Target Files**: [`hardware-agent/src/agent/daemon.py`, `hardware-agent/src/agent/headless.py`, `hardware-agent/tests/unit/test_daemon.py`]
- **Tests**: `test_daemon.py` covers running/no-payload/uploading/finished/unknown commands, park silence, upload failure, a new command after cancellation, and the 15-second stop bound with a fake runner.
- **Success Criteria**:
  - A remote cancel during a running scan invokes the runner stop within 15 seconds of frame receipt; a partial result uploads before `cancelled` is sent.
  - No payload produces `cancelled` without upload; failed upload produces `failed` / `ingest_failed`.
  - Unknown, finished, or uploading command IDs cause no stop; a completed scan that wins the race ends `done`.
  - Park/revoke still sends neither upload nor status; the hold is released and a new scan can start after terminal cancel.
- **Status**: COMPLETED
- **Review Rejections**: 3

## Task 3: Define cancelled state and migrate activity
- **Description**: Add the command/scan `cancelled` status and `scan_cancelled` activity kind per `plan.md` decisions 1, 3, and 9. Update lifecycle rank, terminal and Pi-owned sets, schemas, activity wording, and the migration for `ck_activity_kind` and `uq_activity_org_kind_subject` with downgrade support.
- **Absorbed**: Literal and enum additions have no independent behavior; the lifecycle and migration tests cover them.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/command_lifecycle.py`, `backend/src/api/schemas/commands.py`, `backend/src/api/schemas/read.py`, `backend/src/api/schemas/agent_frames.py`, `backend/src/api/models/activity.py`, `backend/src/api/services/activity.py`, `backend/alembic/versions/20260927_37_scan_cancelled_activity.py`, `backend/tests/test_command_lifecycle.py`, `backend/tests/test_command_models.py`, `backend/tests/test_activity_service.py`, `backend/tests/test_scan_cancelled_activity_migration.py`, `contracts/openapi/openapi.yaml`]
- **Tests**: Lifecycle and model tests check accepted states; activity tests check text and uniqueness; migration tests check upgrade and downgrade.
- **Success Criteria**:
  - `cancelled` is terminal, Pi-owned, rank 4, and maps to scan `cancelled`; the frame and public schemas accept it.
  - `scan_cancelled` says “was stopped”; migration adds its check/index membership and fully reverses on downgrade.
  - OpenAPI publishes the new statuses and activity kind.
- **Status**: COMPLETED
- **Review Rejections**: 2

## Task 4: Implement the admin cancel endpoint and service
- **Description**: Implement `POST /api/v1/commands/{command_id}/cancel` per `plan.md` decisions 4, 7, and 8. Send the frame to an online Pi and return 202; retire an offline command and scan at once with 200; keep terminal requests idempotent. Add the OpenAPI path and error response.
- **Absorbed**: The OpenAPI endpoint entry is verified through route tests and contract sync, so it belongs to the route task.
- **Dependencies**: Task 3
- **Target Files**: [`backend/src/api/services/commands.py`, `backend/src/api/routers/commands.py`, `backend/src/api/schemas/agent_frames.py`, `backend/tests/test_commands_service.py`, `backend/tests/test_enqueue_command.py`, `backend/tests/test_activity_service.py`, `contracts/openapi/openapi.yaml`]
- **Tests**: Service and route tests cover admin authorization, 202 online, 200 offline/terminal, 404, 409, frame count, activity, and device availability.
- **Success Criteria**:
  - Only an admin can cancel an org-owned command; missing or other-org commands return 404.
  - Online cancellable command sends one `AgentCancelFrame` and returns 202; offline command becomes terminal `cancelled`, mirrors scan status, and returns 200.
  - `uploading` returns 409 `command_not_cancellable`; any terminal command returns 200 with current state and sends no frame.
  - Retiring a cancelled command records `scan_cancelled` activity and frees the device for a new scan.
- **Status**: COMPLETED
- **Review Rejections**: 2

## Task 5: Preserve partial results through cancellation
- **Description**: Update status application and ingest per `plan.md` decisions 2, 3, and 5. A cancelled command can still upload late results; a completed scan with results stays completed, while the command ends cancelled and activity records the stop.
- **Dependencies**: Task 3, Task 4
- **Target Files**: [`backend/src/api/services/commands.py`, `backend/src/api/services/persistence.py`, `backend/tests/test_commands_service.py`, `backend/tests/test_ingest_scan.py`, `backend/tests/test_scan_ingest_route.py`]
- **Tests**: Ingest and status tests prove normal and late partial upload, retained completed scan, no-result cancellation, and rejection of uploads for other terminal states.
- **Success Criteria**:
  - `apply_status(cancelled)` mirrors scan status only when that scan is not already `completed` and emits `scan_cancelled` rather than `scan_failed`.
  - A user-cancel partial upload, including one after offline cancellation, is accepted; scan status is `completed`, command status is `cancelled`, and activity is `scan_cancelled` instead of `scan_finished`.
  - Upload for `done`, `failed`, or `expired` remains a 400 `ScanClosedError`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Send missed cancels when a Pi reconnects
- **Description**: On accepted hello, query and send cancel frames for this agent's cancelled, no-results scans still within the mode duration limit, per `plan.md` decision 6. Keep normal pending-status replay behavior.
- **Dependencies**: Task 4, Task 5
- **Target Files**: [`backend/src/api/services/commands.py`, `backend/src/api/services/agent_ws.py`, `backend/tests/test_agent_ws.py`, `backend/tests/test_agent_ws_channel.py`, `backend/tests/test_command_delivery.py`]
- **Tests**: WebSocket and delivery tests cover same-agent catch-up, duration expiry, results already present, and no duplicate replay of a delivered `running` status.
- **Success Criteria**:
  - Hello sends one cancel frame for each eligible command belonging to that Pi and none for other agents, completed scans, or expired duration windows.
  - Reconnect does not resend a delivered `running` status; a late upload remains accepted after catch-up.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 7: Explain partial coverage to scan AI
- **Description**: Add `partial_result` and mapped `stopped_by` to `ScanAIContext`, increment context version to 3, and make the Groq prompt lead with the coverage limit for every partial scan, per `plan.md` decision 15. Amend ADR-020.
- **Absorbed**: The ADR note and context version are validated by the AI context and prompt tests.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/ai/context.py`, `backend/src/api/services/ai/groq.py`, `backend/src/api/services/ai/analyzer.py`, `backend/tests/test_ai_context.py`, `backend/tests/test_ai_groq.py`, `backend/tests/test_ai_analyzer.py`, `docs/adr/ADR-020-ai-scan-analysis.md`]
- **Tests**: Context and prompt tests cover operator, timeout, error, and complete scans, including the rule against treating absent findings as clean evidence.
- **Success Criteria**:
  - `terminated_by` maps to `operator`, `timeout`, `error`, or null as specified; `partial_result` is present and `AI_CONTEXT_VERSION` is `"3"`.
  - The prompt opens with the coverage limit for all partial scans and does not infer a clean result from missing findings.
  - Split child contexts preserve the partial fields, so bounded and repair prompts retain the coverage limit.
  - ADR-020 records the partial-coverage input change.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 8: Add the device-screen stop control
- **Description**: Implement the cancel API call, command hook, terminal label, and the confirmation dialog in the existing scan-control slot per `plan.md` frontend step. Regenerate OpenAPI types with `npm run gen:types`. Cover the finish-before-stop race and 409 response.
- **Absorbed**: The thin API wrapper, generated types, and simple status label are exercised through the hook and device-screen tests.
- **Dependencies**: Task 2, Task 4, Task 5
- **Target Files**: [`frontend/src/api/commands.ts`, `frontend/src/types/openapi.d.ts`, `frontend/src/lib/commandStatus.ts`, `frontend/src/lib/commandStatus.test.ts`, `frontend/src/hooks/useScanCommand.ts`, `frontend/src/pages/DeviceDetail.tsx`, `frontend/src/pages/agents/ScanControl.tsx`, `frontend/src/pages/agents/CommandStatus.tsx`, `frontend/src/pages/DeviceDetail.command.test.tsx`, `frontend/src/pages/DeviceDetail.invalidation.test.tsx`]
- **Tests**: Device-screen tests cover admin-only control, dialog/focus/copy, stopping state, retry/view actions, race and 409 toasts, and query invalidation; status tests cover terminal `cancelled`.
- **Success Criteria**:
  - Delivered/running admin scan shows **Stop scan** next to the left-aligned status; confirmation uses the copy in `plan.md`, and focus returns to the status region.
  - Confirming shows **Stopping…** until terminal; 409 says “The scan is already uploading its results.”
  - A scan that finishes before stop shows **Done**, **View scan**, and “The scan finished before it could stop.”
  - Cancelled results show **View scan** and **Retry** with the saved-results hint; no-results cancellation shows **Retry** only. Relevant command, scan, host, finding, and agent queries refresh.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Render stopped scans accurately
- **Description**: Extend scan status labels and scan detail per `plan.md` decision 14. A cancelled scan without results gets a stopped notice and no results/AI/counts; a completed user-cancel scan shows saved results and the stopped-early explanation.
- **Dependencies**: Task 3, Task 5, Task 8
- **Target Files**: [`frontend/src/lib/scanStatus.ts`, `frontend/src/lib/scanStatus.test.ts`, `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/ScanDetail.test.tsx`, `frontend/src/pages/scans/ScanStoppedNotice.tsx`, `frontend/src/pages/scans/ScanDetailHeader.tsx`, `backend/src/api/schemas/read.py`, `backend/src/api/services/read.py`, `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`, `frontend/src/pages/scans/scanListColumns.tsx`, `frontend/src/pages/agents/deviceScanHistoryColumns.tsx`, plus the matching backend read tests]
- **Tests**: Scan status and detail tests cover both stopped states, history labels, hidden counts, absent AI and findings for no-results scans, and visible partial results.
- **Success Criteria**:
  - Scan `cancelled` uses **Stopped**, hides counts, and shows “This scan was stopped before the Pi sent any results.” without AI or findings.
  - A `completed` scan with `terminated_by="user_cancel"` uses **Stopped early**, retains the normal results view, and shows “This scan was stopped early. It shows what was found before the stop.”
- **Status**: COMPLETED
- **Review Rejections**: 1
- **Scope amendment (human decision, 2026-09-28)**: add `terminated_by` to `ScanSummary` (OpenAPI + backend list + generated types) so history and list rows show **Stopped early**. Both layer review pairs apply.

## Task 10: Verify end-to-end contract and documentation
- **Description**: Add cross-layer regression coverage for the complete cancel flow in `plan.md`, run the `openapi-contract-sync` and `docs-sync` workflows, and fix only concrete contract or documentation drift they find. This is the final integration task after all behavior tasks.
- **Absorbed**: Contract sync and documentation write-backs have no standalone product behavior; the end-to-end regression makes this a testable final task.
- **Dependencies**: Tasks 1–9
- **Target Files**: [`backend/tests/test_agent_ws_channel.py`, `backend/tests/test_ingest_scan.py`, `frontend/src/pages/DeviceDetail.command.test.tsx`, `frontend/src/pages/ScanDetail.test.tsx`, `contracts/openapi/openapi.yaml`, `docs/adr/ADR-011-pi-command-channel.md`, `docs/adr/ADR-020-ai-scan-analysis.md`]
- **Tests**: Cross-layer regression checks the connected cancel → partial ingest → terminal command path and the offline cancel → reconnect → late ingest path; frontend regressions check both resulting views.
- **Success Criteria**:
  - Both end-to-end paths in `plan.md` are covered by tests; after cancellation the device accepts another scan.
  - Route, response enums, error codes, and generated types agree with OpenAPI; the ADR amendments and code-map match the shipped behavior.
  - All layer review gates listed above pass; no out-of-scope timeout, TUI, upload-cancel, or park/revoke feature is added.
- **Status**: COMPLETED
- **Review Rejections**: 1

---

## Dependency graph

```
#1 Pi protocol → #2 Pi behavior ───────────────────────┐
#3 backend state/migration → #4 cancel API → #5 ingest ├→ #8 device UI → #9 scan detail → #10 integration
                               └──────────→ #6 catch-up ┘                    ↑
#7 AI partial coverage ────────────────────────────────────────────────────────┘
#6 ───────────────────────────────────────────────────────────────────────────→ #10
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Parse and deliver Pi cancel frames | COMPLETED |
| 2 | Stop remote scans and report the honest outcome | COMPLETED |
| 3 | Define cancelled state and migrate activity | COMPLETED |
| 4 | Implement the admin cancel endpoint and service | COMPLETED |
| 5 | Preserve partial results through cancellation | COMPLETED |
| 6 | Send missed cancels when a Pi reconnects | COMPLETED |
| 7 | Explain partial coverage to scan AI | COMPLETED |
| 8 | Add the device-screen stop control | COMPLETED |
| 9 | Render stopped scans accurately | COMPLETED |
| 10 | Verify end-to-end contract and documentation | COMPLETED |
