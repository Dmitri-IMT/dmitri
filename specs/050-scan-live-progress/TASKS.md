# Tasks — Live scan progress (`050-scan-live-progress`)

6 tasks. The user approved implementation; all six tasks are IN_PROGRESS while implementation and review gates run.

This is a self-contained task spec because this feature has no approved `TRUTH.md`, `ARCHITECTURE.md`, or `DESIGN.md`. It follows the `create-tasks` task shape and records the scope, decisions, file map, and acceptance criteria here for approval.

## Scope and decisions

- The web scan-detail page shows live counts for **machines, open ports, filtered ports, industrial services, and vulnerabilities**, matching the current `ScanUnfinishedNotice` on `main`. The earlier screenshot had a single services card; the current screen has two port cards.
- Counts are nullable until their source stage has produced evidence. Display `—` for unknown and `0` only for a confirmed zero. Discovery confirms machines; the port stage confirms open and filtered ports; OT inspection confirms industrial services in NSPi mode; normalization confirms vulnerability findings. A final payload may correct earlier counts, including ports added by deep inspection.
- The existing `ScanEvent` stream and `ProgressMapper` supply stage and percentage. The daemon sends compact snapshots through the existing authenticated Pi → backend WebSocket. It does not repeatedly serialize or write the full result JSON. The complete payload continues to use `POST /api/v1/scans`.
- A new `progress` frame carries `command_id`, `scan_id`, a monotonically increasing `sequence`, and one complete snapshot: stage (`discovery`, `ports`, `deep_inspection`, `ot_inspection`, `targeted_assessment`, `normalization`, or `uploading`), percent (0–99 while unfinished), and the five nullable counters. The backend stores the latest accepted snapshot on the scan stub in separate progress fields, including a server receipt timestamp. `metadata_json` remains final-result metadata.
- Accept progress only for the authenticated agent's matching active command and scan. Ignore duplicate, older, or terminal-state frames. Validate bounds and stage names. Keep the newest snapshot in Pi memory across a temporary socket loss and replay only that snapshot after reconnect; an unavailable progress channel must not stop the scan.
- The scan-detail API exposes optional `progress` only while the scan is unfinished. Completed results use persisted hosts and findings as the authority; failed and cancelled scans without results do not show stale progress. Old agents return `progress: null`.
- The frontend keeps its existing 2-second scan-detail polling. It uses the reported percentage and stage, with an indeterminate display before the first report. The UI does not infer progress from `pending` / `accepted` / `processing` status. The existing terminal and partial-result views remain authoritative.
- Coalesce in-stage reports to at most one every 2 seconds per scan; send stage boundaries and the pre-upload snapshot promptly. A thread-safe handoff keeps WebSocket I/O off the scan worker thread. Bound memory to the latest pending snapshot.

## Acceptance matrix

| Scenario | Expected observable result | Task |
|---|---|---|
| No report yet or old Pi | Stage and counts are unknown; no invented percentage or zero | #3, #6 |
| Discovery completes with N hosts, including N = 0 | Machines becomes N while scan is running | #4–#6 |
| Port stage completes | Open and filtered ports show separate confirmed counts | #4–#6 |
| NSPi OT stage completes | Industrial services shows its confirmed count; other modes show a confirmed zero | #4–#6 |
| Normalization finishes before upload | Findings count is available; percentage remains below 100 | #4–#6 |
| Duplicate, delayed, foreign, or post-terminal frame | Saved progress and final results remain unchanged | #1–#3, #5 |
| Connection drops and returns | Scan continues; at most the newest snapshot is replayed | #5 |
| Final ingest or accepted partial ingest | Final hosts, ports, industrial services, and findings take precedence | #3, #6 |
| Failed or cancelled scan without results | The existing terminal notice appears without stale live counts | #3, #6 |

## File map

| Area | Planned files |
|---|---|
| Contract and backend model | `contracts/openapi/openapi.yaml`; `backend/src/api/schemas/agent_frames.py`; `backend/src/api/schemas/scan_progress.py` (new); `backend/src/api/schemas/read.py`; `backend/src/api/models/persistence.py`; `backend/alembic/versions/20261002_39_scan_live_progress.py` (new) |
| Backend behavior | `backend/src/api/services/scan_progress.py` (new); `backend/src/api/services/agent_ws.py`; `backend/src/api/services/read.py` |
| Pi behavior | `hardware-agent/src/agent/scanner/progress.py`; `hardware-agent/src/agent/scanner/stages.py`; `hardware-agent/src/agent/scanner/live_progress.py` (new); `hardware-agent/src/agent/transport/command_channel.py`; `hardware-agent/src/agent/daemon.py` |
| Web UI | `frontend/src/types/openapi.d.ts` (generated); `frontend/src/pages/scans/ScanDetailHeader.tsx`; `frontend/src/pages/scans/ScanUnfinishedNotice.tsx`; `frontend/src/i18n/messages/catalog.types.ts`; `frontend/src/i18n/messages/en.ts`; `frontend/src/i18n/messages/pt-BR.ts`; `frontend/src/i18n/messages/ru.ts` |
| Tests | `backend/tests/test_scan_progress_schema.py` (new); `backend/tests/test_scan_progress_migration.py` (new); `backend/tests/test_scan_progress_service.py` (new); `backend/tests/test_agent_ws.py`; `backend/tests/test_agent_ws_channel.py`; `backend/tests/test_read_scans.py`; `backend/tests/test_scan_read.py`; `backend/tests/test_ingest_scan.py`; `hardware-agent/tests/unit/test_live_progress.py` (new); `hardware-agent/tests/unit/test_scan_runner_events.py`; `hardware-agent/tests/unit/test_command_channel.py`; `hardware-agent/tests/unit/test_daemon.py`; `frontend/src/pages/ScanDetail.test.tsx` |
| Protocol and code-map docs | `docs/adr/ADR-011-pi-command-channel.md`; `.claude/docs/hardware-agent/scanner/progress.md`; `.claude/docs/hardware-agent/transport.md`; `.claude/docs/backend/schemas.md`; `.claude/docs/backend/services.md`; `.claude/docs/frontend/screens.md` |

Do not add a new `ScanRunner` constructor parameter. Pass a reporter through the existing `run_headless_scan(reporter=...)` argument. Audit all call sites if implementation changes that boundary; the TUI has its own runner path.

Review gates during implementation: hardware agent `uv run pytest` plus its scoped Ruff/Black hooks; backend `./database.sh --test` before `uv run ruff check src tests` and `uv run pytest`; frontend `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, and `npm run build`. Never run a repo-wide formatter or backend `ruff format`. Regenerate frontend types with `npm run gen:types` and run the repository's `openapi-contract-sync` / `docs-sync` workflows when the contract and behavior are ready.

---

## Task 1: Define the progress contract and durable snapshot
- **Description**: Define the typed Pi `progress` frame and public scan progress object in OpenAPI and backend schemas. Add nullable progress data, sequence, and server receipt time to `ScanRecord` through a reversible migration. Amend ADR-011 with the new frame and its small-message semantics.
- **Absorbed**: Contract text and ADR updates belong to the schema task because they have no independent runtime behavior; schema and migration tests gate them.
- **Dependencies**: —
- **Target Files**: [`contracts/openapi/openapi.yaml`, `backend/src/api/schemas/agent_frames.py`, `backend/src/api/schemas/scan_progress.py`, `backend/src/api/schemas/read.py`, `backend/src/api/models/persistence.py`, `backend/alembic/versions/20261002_39_scan_live_progress.py`, `backend/tests/test_scan_progress_schema.py`, `backend/tests/test_scan_progress_migration.py`, `docs/adr/ADR-011-pi-command-channel.md`]
- **Tests**: New schema tests reject unknown stages, invalid percentages, negative counts, malformed identifiers, and extra fields; migration tests prove upgrade and downgrade against the current head.
- **Success Criteria**:
  - One named snapshot shape covers stage, percent, nullable counts, and server receipt time in the public response; the wire frame also carries `command_id`, `scan_id`, and positive `sequence`.
  - `progress_json` is separate from final-result metadata, `progress_seq` starts at 0, and `progress_updated_at` is nullable; the migration preserves existing scans and reverses cleanly.
  - OpenAPI, Python schemas, and ADR-011 agree on fields, bounds, and transport direction.
- **Status**: IN_PROGRESS
- **Review Rejections**: 0

## Task 2: Accept and guard progress frames on the backend
- **Description**: Parse Pi `progress` frames in the existing WebSocket handler and apply each snapshot atomically to its matching scan stub. Check agent ownership, command/scan pairing, active command state, sequence, and terminal races in one database transaction; keep the current malformed-frame and revoked-agent behavior.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/scan_progress.py`, `backend/src/api/services/agent_ws.py`, `backend/tests/test_scan_progress_service.py`, `backend/tests/test_agent_ws.py`, `backend/tests/test_agent_ws_channel.py`]
- **Tests**: Service and channel tests cover a valid update, stale/duplicate sequence, foreign agent, mismatched IDs, malformed frame, revoked agent, progress arriving after final ingest, and progress arriving after failure or cancellation.
- **Success Criteria**:
  - Only the authenticated agent's active `running` or `uploading` command can update its linked scan; each accepted frame changes one scan row and records server time.
  - Duplicate, older, and terminal-state frames are idempotent no-ops; unknown or malformed frames follow the established WebSocket error policy.
  - Progress handling does not transition command status, create hosts/findings, or interfere with `hello`, `status`, and `cancel` frames.
- **Status**: IN_PROGRESS
- **Review Rejections**: 0

## Task 3: Expose live progress while preserving final-result authority
- **Description**: Project the stored snapshot into `GET /api/v1/scans/{scan_id}` for unfinished scans only. Keep the existing `hosts`, `findings`, `host_count`, and `finding_count` fields based on persisted results, while the new `progress` object supplies temporary display counts.
- **Dependencies**: Tasks 1, 2
- **Target Files**: [`backend/src/api/services/read.py`, `backend/tests/test_read_scans.py`, `backend/tests/test_scan_read.py`, `backend/tests/test_ingest_scan.py`]
- **Tests**: Read and ingest tests cover no report, each accepted snapshot, final ingest winning a progress race, accepted partial results, failed/cancelled no-result scans, and organization isolation.
- **Success Criteria**:
  - A running scan returns its latest validated progress with nullable counts; an old agent or unreported scan returns `progress: null`.
  - Once results are accepted, the response uses stored hosts/findings and does not expose the prior progress snapshot; terminal scans without results also hide it.
  - The existing polling endpoint, response fields, and result-ingest idempotency continue to work.
- **Status**: IN_PROGRESS
- **Review Rejections**: 0

## Task 4: Convert scanner events into accurate snapshots
- **Description**: Build a pure live-progress reporter around the existing `ScanEvent` stream and `ProgressMapper`. Add only the event counters needed to distinguish open/filtered ports and to report industrial services after OT inspection; derive the final vulnerability count from the completed `ScanPayload` before upload.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/progress.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/live_progress.py`, `hardware-agent/tests/unit/test_live_progress.py`, `hardware-agent/tests/unit/test_scan_runner_events.py`]
- **Tests**: Reporter and stage-event tests cover all scan modes, zero hosts, separate port states, NSPi industrial count, unknown-to-confirmed transitions, monotonic percentage, payload reconciliation, and a cap below 100 before ingest.
- **Success Criteria**:
  - The five counters match the current web cards and final payload semantics; vulnerability count stays unknown until payload normalization succeeds.
  - Stage boundaries and progress percentages come from the existing scanner events; neither the TUI reporter nor the final JSON writer changes behavior.
  - The reporter performs no WebSocket, disk, or database I/O and adds no `ScanRunner` constructor argument.
- **Status**: IN_PROGRESS
- **Review Rejections**: 0

## Task 5: Deliver bounded progress from the Pi daemon
- **Description**: Pass the new reporter into the existing headless scan call, hand snapshots from the scan thread to the asyncio loop, and send typed `progress` frames through the command-channel client's existing send lock. Coalesce in-stage updates, flush stage/final boundaries, and retain only the newest unsent snapshot across a temporary reconnect.
- **Dependencies**: Tasks 1, 4
- **Target Files**: [`hardware-agent/src/agent/transport/command_channel.py`, `hardware-agent/src/agent/daemon.py`, `hardware-agent/tests/unit/test_command_channel.py`, `hardware-agent/tests/unit/test_daemon.py`]
- **Tests**: Daemon and channel tests cover wire serialization, thread handoff, the 2-second bound, immediate stage boundaries, socket loss/reconnect, sequence replay, upload ordering, cancellation, parking, and no-result failure.
- **Success Criteria**:
  - Progress I/O never blocks the scan worker; memory is bounded to the latest snapshot and no progress frame contains hosts, ports, findings, or raw evidence arrays.
  - Reconnect replays only the latest nonterminal snapshot with a sequence the backend can safely deduplicate; terminal status prevents later progress sends.
  - Final JSON and HTTP ingest paths, status replay, cancel, park/revoke, and TUI scanning retain their current behavior.
- **Status**: IN_PROGRESS
- **Review Rejections**: 0

## Task 6: Render stage progress and verify the complete flow
- **Description**: Regenerate OpenAPI types and update the unfinished scan UI to render reported stage, percentage, and five nullable counters. Preserve the existing 2-second polling, Check again action, terminal views, and language catalogs; finish the cross-layer regression and code-map updates.
- **Absorbed**: Generated types, translations, contract sync, and documentation write-backs are verified through the screen and cross-layer tests, so they do not need separate implementation tasks.
- **Dependencies**: Tasks 2, 3, 5
- **Target Files**: [`frontend/src/types/openapi.d.ts`, `frontend/src/pages/scans/ScanDetailHeader.tsx`, `frontend/src/pages/scans/ScanUnfinishedNotice.tsx`, `frontend/src/i18n/messages/catalog.types.ts`, `frontend/src/i18n/messages/en.ts`, `frontend/src/i18n/messages/pt-BR.ts`, `frontend/src/i18n/messages/ru.ts`, `frontend/src/pages/ScanDetail.test.tsx`, `backend/tests/test_agent_ws_channel.py`, `.claude/docs/hardware-agent/scanner/progress.md`, `.claude/docs/hardware-agent/transport.md`, `.claude/docs/backend/schemas.md`, `.claude/docs/backend/services.md`, `.claude/docs/frontend/screens.md`]
- **Tests**: Scan-detail tests cover no-report fallback, each counter transition, stage/percentage rendering and accessibility, manual/automatic refresh, old agents, final/partial authority, failure, and cancellation; backend channel regression covers progress followed by ingest.
- **Success Criteria**:
  - The initial view uses an indeterminate progress indicator and `—` for unknown counts; a reported zero remains visibly `0`.
  - The current five cards update from the progress object during the scan, and the bar never shows 100% before completed results are accepted.
  - Completion replaces partial counts with persisted results; failed/cancelled no-result views show their existing notices without stale progress.
  - Generated types match OpenAPI, localized stage labels exist in all three catalogs, and the relevant code-map docs match the shipped flow.
- **Status**: IN_PROGRESS
- **Review Rejections**: 0

---

## Dependency graph

```text
#1 contract/storage ──→ #2 backend intake ──→ #3 read projection ──┐
        │                    │                                        ├──→ #6 web/integration
        └───────────────→ #5 Pi delivery ─────────────────────────────┘
                           ↑
#4 scanner snapshots ──────┘
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Define the progress contract and durable snapshot | IN_PROGRESS |
| 2 | Accept and guard progress frames on the backend | IN_PROGRESS |
| 3 | Expose live progress while preserving final-result authority | IN_PROGRESS |
| 4 | Convert scanner events into accurate snapshots | IN_PROGRESS |
| 5 | Deliver bounded progress from the Pi daemon | IN_PROGRESS |
| 6 | Render stage progress and verify the complete flow | IN_PROGRESS |
