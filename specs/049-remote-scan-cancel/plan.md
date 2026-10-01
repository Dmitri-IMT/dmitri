# 049 — Remote scan cancel (DMI-145)

Linear: [DMI-145](https://linear.app/dmitri-imt/issue/DMI-145) · Branch: `feat/dmi-145` ·
Approved by @guilhermeronca on 2026-09-27.

## Scope

One issue, one PR across Pi, backend, contract and frontend — including the AI partial-coverage
fix (decision 15), which also covers timeout partials. Operator choice, 2026-09-27.

## Goal

An admin stops a running scan from the device screen. The Pi stops the scan, uploads what it
found so far, and the command becomes terminal as `cancelled`. The device accepts a new scan.
No SSH.

## What already exists (do not rebuild)

| Piece | Where | Built by |
|--|--|--|
| `ScanRunner.request_cancel()` kills nmap, targeted and Modbus work | `hardware-agent/src/agent/scanner/runner.py:93` | — |
| Runner builds a partial payload on cancel (`partial_result=True`, `terminated_by="user_cancel"`) | `runner.py:431` | — |
| `_ScanStop` binds the runner's cancel from the event loop | `hardware-agent/src/agent/daemon.py:38-58` | DMI-178 |
| `headless` binds `scan_runner.request_cancel` | `hardware-agent/src/agent/headless.py:131` | DMI-178 |
| Partial scans are stored as `completed` and shown with the partial-evidence copy | `backend/src/api/services/persistence.py`, `frontend/src/pages/ScanDetail.tsx:116` | — |
| Per-mode duration timeout sweep (backstop) | `backend/src/api/services/commands.py` `sweep_stale_commands` | DMI-144 |
| TUI cancel | `tui/screens/scan_progress.py:695` | — |

## Decisions

1. **New terminal command status `cancelled`.** Not `failed` + error code: a cancelled scan must
   be told apart from one that failed on its own.
2. **Partial results are kept.** An operator may stop a scan because it is misbehaving and still
   need what it found. The Pi uploads the partial payload the runner already builds.
3. **The scan row follows its data, the command row follows the operator.**
   - Results uploaded → scan status `completed` (partial, like a timeout partial today), command
     `cancelled`. Hosts reach inventory, reports and AI analysis, which all read `completed` only.
   - No results (stopped before any upload) → scan status `cancelled`.
4. **Backend does not wait for the Pi.** Connected Pi → send the cancel frame, return 202. The Pi
   uploads, then confirms `cancelled`. Offline Pi → mark `cancelled` at once, return 200.
   Accepted race (2026-10-01): after an offline cancel the device reads as free before the Pi
   hears the cancel. A scan started while the reconnected Pi is still stopping ends `failed` /
   `device_busy`; the operator starts it again. Rare for one Pi, so the backend does not wait
   for the Pi's confirmation.
5. **A late upload for a `cancelled` command is accepted** (today any terminal command gets
   400 `ScanClosedError`). This keeps the partial results from an offline cancel.
6. **Offline catch-up runs on connect.** `replay_pending()` re-sends only undelivered statuses,
   so a Pi that sent `running` before it dropped never sends it again. On the Pi's hello, the
   backend sends a cancel frame for each of that agent's commands that is `cancelled`, has no
   results (scan status `cancelled`), and is still inside its mode's max duration (DMI-144
   setting). The Pi ignores frames for unknown or finished commands (decision 8).
7. **`uploading` is not cancellable** → 409 `command_not_cancellable`. The results are already on
   their way.
8. **Idempotent** — cancel on a terminal command returns 200 with the current state, no frame.
9. **Activity feed** gets a `scan_cancelled` kind (migration on `ck_activity_kind`). It replaces
   `scan_finished` / `scan_failed` for a cancelled scan.
10. **Old Pi software** drops the unknown frame (`_parse_command`); the DMI-144 timeout frees the
    device. No version gate and no hello capability flag: one Pi is in service and it is
    updated with the backend (operator decision, 2026-09-27). An old Pi would show
    "Stopping…" until the mode's time limit.
11. **Stop bound**: the scan stops within 15 s of the frame reaching the Pi, proven with a fake
    runner. The upload that follows is not in the bound. No on-device figure is claimed.
12. **Park/revoke stop stays silent** (DMI-178): no upload, no status. Only a remote cancel uploads.
13. **A cancel that loses the race ends honestly.** If the Pi already finished scanning when the
    frame lands, it ignores the frame and the command ends `done`. The UI shows **Done** + **View
    scan** and a toast "The scan finished before it could stop." The backend stores nothing about
    the request (no `cancel_requested_at` column).
14. **Two labels, two views.** Scan `cancelled` (no results) → label **Stopped**, a notice "This
    scan was stopped before the Pi sent any results.", no AI panel, no findings, counts hidden.
    Scan `completed` + `terminated_by == "user_cancel"` → label **Stopped early**, normal results
    view plus the "stopped early" line.
15. **The AI is told about partial coverage — for every partial scan**, not only operator stops.
    `ScanAIContext` gains `partial_result` and `stopped_by` (`operator` | `timeout` | `error` |
    null, mapped from `terminated_by`). The prompt must open with the coverage limit and must not
    read missing findings as a clean result. A `cancelled` scan with no results gets no AI
    analysis. ADR-020 gets an amendment note, not a new ADR.

No change to `ck_commands_scan_id_or_expired`: `queued` lasts only inside the POST request, so
every cancellable command already has a `scan_id`. The partial unique index lists non-terminal
states by name, so a new terminal state needs no index change.

## Protocol (ADR-011 amendment)

```jsonc
// server → Pi
{ "type": "cancel", "command_id": "<uuid>" }
// Pi → server (existing status frame, new value)
{ "type": "status", "command_id": "<uuid>", "status": "cancelled", "error_code": null }
```

Sequence, connected Pi: `running` → cancel frame → runner stops → `uploading` → ingest (partial,
`terminated_by="user_cancel"`) → `cancelled`.

## Steps

### 1. Pi — `hardware-agent/`

- `transport/command_channel.py`
  - Add `AgentCancel` (`type: Literal["cancel"]`, `command_id`).
  - `AgentStatus.status` gains `"cancelled"`.
  - `_parse_command` parses either frame (discriminated on `type`); `run()` / `_serve_once`
    take an `on_cancel` callback next to `on_command`.
- `daemon.py`
  - `CommandStatus` gains `"cancelled"`; `_send` releases the hold on it like `done`/`failed`.
  - `_ScanStop.request()` takes a reason: `"cancel"` (remote) or `"park"` (DMI-178 path).
  - New `handle_cancel(command_id)`: active and not uploading → `self._stop.request("cancel")`.
    In ledger → re-send the record. Unknown → no-op. Uploading → no-op.
  - `_run_command`: after the scan, reason `"park"` → return silently (as now). Reason
    `"cancel"` → upload the partial payload as usual, then report `cancelled` on accept.
    No payload → report `cancelled` at once. Upload failure → `failed` / `ingest_failed`
    (results lost; honest).
- **Verify**: `cd hardware-agent && uv run pytest` — cancel while running (stops in bound,
  partial payload uploaded, `cancelled` sent, lock released, new command accepted); cancel with
  no payload; cancel for done/unknown command; cancel while uploading; park still silent.

### 2. Backend — `backend/`

- `services/command_lifecycle.py`: `RANK["cancelled"] = 4`, add to `TERMINAL` and `PI_OWNED`,
  `_SCAN_STATUS_BY_COMMAND_STATUS["cancelled"] = "cancelled"`.
- `schemas/commands.py` `CommandStatus`, `schemas/read.py` `ScanStatus`,
  `schemas/agent_frames.py` (`AgentStatus` value + new `AgentCancelFrame`).
- `services/commands.py`
  - `apply_status`: on `cancelled`, mirror the scan status only where the scan is not
    `completed` (keeps uploaded results visible); append `scan_cancelled` activity, not
    `scan_failed`.
  - New `cancel_command(session, org_id, command_id, now)`: terminal → as is; `uploading` →
    `CommandNotCancellableError`; Pi socket present → send `AgentCancelFrame`; no socket →
    `_retire_commands(... status="cancelled")` + mirror.
  - `_mirror_retired_commands`: activity kind by status.
- `services/persistence.py` `ingest_scan` / `persist_scan`
  - Accept an upload when the command is `cancelled` (other terminal states still 400).
  - Final command status: `cancelled` when the command is already `cancelled` or
    `metadata.terminated_by == "user_cancel"`, else `done`. Activity `scan_cancelled` in place
    of `scan_finished` for those.
- `services/agent_ws.py`: after the hello is accepted, send `AgentCancelFrame` for each
  catch-up command (decision 6); query lives in `services/commands.py`.
- `services/ai/context.py`: `ScanAIContext` gains `partial_result: bool` and `stopped_by`;
  bump `AI_CONTEXT_VERSION` to `"3"`. `services/ai/groq.py` prompt: the coverage rule (decision 15).
- `models/activity.py` + `services/activity.py`: `scan_cancelled` kind, phrase "was stopped".
- `routers/commands.py`: `POST /api/v1/commands/{command_id}/cancel`, `require_admin`,
  202 / 200 / 404 / 409.
- `alembic/versions/20260927_37_scan_cancelled_activity.py`: rebuild `ck_activity_kind` and the
  `uq_activity_org_kind_subject` partial index with the new kind (it joins `UNIQUE_KINDS`, like
  `scan_finished` / `scan_failed`); upgrade and downgrade.
- **Verify**: `./database.sh --test`, then `uv run ruff check src tests` and `uv run pytest`.
  Tests cover each endpoint branch, idempotency, ingest of a user-cancel payload (scan
  `completed`, command `cancelled`), late ingest after an offline cancel, ingest still 400 for
  `done`/`failed`/`expired`, reconnect catch-up, device free after cancel, migration round-trip.
  Never `ruff format`.

### 3. Contract

- `contracts/openapi/openapi.yaml`: new path, `cancelled` in `CommandStatus` and `ScanStatus`,
  409 `command_not_cancellable`, `scan_cancelled` activity kind.
- Regenerate `frontend/src/types/openapi.d.ts` with the repo script.
- **Verify**: `openapi-contract-sync` skill — routes match schema.

### 4. Frontend — `frontend/` (option A: confirm in a dialog)

The device screen (`pages/DeviceDetail.tsx`) is the only place a scan starts. `ScanControl`
swaps **Scan now** for `CommandStatus` after the click, so **Stop scan** sits in that same slot.

- `api/commands.ts`: `cancelCommand(commandId)`.
- `lib/commandStatus.ts`: `cancelled: 'Scan stopped'`; terminal set includes it.
- `lib/scanStatus.ts`: label for `cancelled` (the no-results case, in scan history).
- `hooks/useScanCommand.ts`: `cancel()` + `cancelling` state; a followed command that ends `done`
  after a cancel request → toast "The scan finished before it could stop." (decision 13); 409 → toast "The scan is already
  uploading its results."; refetch the command on success; on `cancelled`, invalidate scans,
  hosts, findings, agent (same sweep as `done`).
- `pages/agents/CommandStatus.tsx`
  - Left-align the status block (today `items-end text-right`) so the status and **Stop scan**
    sit in the slot **Scan now** occupied — the control does not jump across the screen.
  - `delivered`/`running`: **Stop scan** (outline, admin only) next to the status label.
  - Dialog on click, reusing `components/ui/dialog.tsx`: title "Stop the {mode} scan on
    {device}?", body "The Pi stops within a few seconds and saves what it found so far.",
    buttons **Keep scanning** / **Stop scan**. Focus returns to the status region.
  - After confirm: "Stopping…" until the status is terminal.
  - `cancelled` with a `scan_id` that has results: **View scan** + **Retry**, hint "You stopped
    this scan. Results found before the stop were saved." Without results: **Retry** only.
- `pages/ScanDetail.tsx`: explicit branch for scan status `cancelled` → a `ScanStoppedNotice`
  (decision 14), before the results branch; `lib/scanStatus.ts` hides counts for `cancelled`
  like `failed`; history label **Stopped**, and **Stopped early** for a completed user-cancel scan.
- `pages/ScanDetail.tsx`: when `metadata.terminated_by === "user_cancel"`, a line "This scan was
  stopped early. It shows what was found before the stop."
- Copy follows FOUNDATIONS §copy (verb + noun).
- **Verify**: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

### 5. Docs

- `docs/adr/ADR-011-pi-command-channel.md`: amendment for the cancel frame and status.
- `docs/adr/ADR-020-ai-scan-analysis.md`: amendment note — partial-coverage input.
- `docs-sync` skill at the end.

## Out of scope

Duration timeout (DMI-144), TUI cancel, upload cancel, park/revoke behaviour (DMI-178),
on-device timing claims.
