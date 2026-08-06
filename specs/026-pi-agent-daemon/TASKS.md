# TASKS — Pi agent daemon command execution (DMI-66)

Specs: `specs/026-pi-agent-daemon/TRUTH.md`, `ARCHITECTURE.md`, `INTEGRATION.md`.

Agent assignment by layer:

| Task | Layers | Step 2 | Step 3 |
|------|--------|--------|--------|
| 1, 2, 4, 5, 6 | `hardware-agent/` | `test-engineer` | `code-reviewer` |
| 3 | `contracts/` + `backend/` + `frontend/` | `test-engineer` (backend) | `code-reviewer` (backend) **and** `frontend-code-reviewer` (frontend gate) |

Gates: `hardware-agent/` and `backend/` → `uv run pytest` + `uv run ruff check src tests`
(backend needs `./database.sh` first; a non-zero skip count is not green).
`frontend/` → `npm run lint && npm run typecheck && npm test && npm run build`.
Never run a repo-wide formatter.

## Dependency graph

```text
1 (signing) ─┐
2 (subnets) ─┼─> 4 (command channel) ─> 5 (daemon) ─> 6 (CLI dispatch)
3 (contract)─┘
```

Tasks 1, 2 and 3 are independent of each other and are executed in listed order.

---

## Task 1: Shared Ed25519 device signing helper
- **Description**: Extract the Ed25519 envelope construction currently inline in
  `transport/ingest.py` into `transport/signing.py` as `build_device_signature_headers(method,
  path, body, device_id, private_key_bytes)` returning the five `X-Device-*` headers. It must
  create a fresh timestamp, nonce, body SHA-256 and signature on every call, hash an empty body
  as SHA-256 of zero bytes, and never log, store, or interpolate the private key. Rewire
  `ScanIngestClient` to delegate to it with `POST` / `/api/v1/scans` / serialized payload bytes,
  leaving `submit()`'s public behavior untouched. Export the transport names the daemon and tests
  need from `transport/__init__.py`.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/transport/signing.py`,
  `hardware-agent/src/agent/transport/ingest.py`,
  `hardware-agent/src/agent/transport/__init__.py`,
  `hardware-agent/tests/unit/test_transport_signing.py`,
  `hardware-agent/tests/unit/test_ingest_client.py`]
- **Success Criteria**:
  - Canonical string for `GET` is exactly
    `GET\n/api/v1/agents/{device_id}/commands\n{device_id}\n{timestamp}\n{nonce}\n{body_sha256}`;
    the `POST` form matches the string `ScanIngestClient` signed before this task.
  - A test independently verifies both signatures with the public key.
  - Empty body hashes to the SHA-256 of zero bytes.
  - Two calls with identical arguments produce different nonces, timestamps and signatures.
  - No test can find the private key in any raised exception text or emitted diagnostic.
  - `ScanIngestClient.submit` request shape, headers and outcome mapping are unchanged; existing
    ingest tests pass with only signer injection/import assertions updated.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Available subnet enumeration with default-route marking
- **Description**: Add `detect_available_subnets()` to `agent/utils/network.py`. It enumerates up
  interfaces and their IPv4 addresses via `psutil`, rejects loopback, link-local, missing-netmask,
  invalid and duplicate interface/CIDR entries, and returns one entry per usable interface/CIDR
  carrying the interface name, canonical network CIDR and `is_default_route`. Reuse the module's
  existing default-route detection to map the outbound IPv4 address back to its interface and flag
  only that entry. If detection fails, return the usable list with every flag false — never raise,
  never guess. Do not touch the TUI's private `_detect_interfaces()`.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/utils/network.py`,
  `hardware-agent/tests/test_network_detection.py`]
- **Success Criteria**:
  - Dual-homed fixture returns both subnets with exactly one `is_default_route: true`.
  - Single-homed fixture returns one entry and selects no scan target.
  - Loopback, link-local, down interfaces, IPv6, and entries with a missing/invalid netmask are
    excluded.
  - Duplicate interface/CIDR pairs are deduplicated.
  - Addresses are converted to the canonical network CIDR (e.g. `10.0.0.7/24` → `10.0.0.0/24`).
  - Default-route detection failure yields the full usable list with every flag false and no
    exception.
  - Existing `test_network_detection.py` cases keep passing unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Required `is_default_route` on the shared AvailableSubnet contract
- **Description**: Add the required `is_default_route: boolean` to `AvailableSubnet` in
  `contracts/openapi/openapi.yaml` and mirror it as a required `bool` on the backend Pydantic
  `AvailableSubnet` in `backend/src/api/schemas/agent_frames.py`. Regenerate
  `frontend/src/types/openapi.d.ts` from the contract — no hand-written frontend behavior. Update
  the backend hello fixtures and assertions so the flag is carried through
  `handle_agent_frame()` → `set_hello()` into the in-memory registry, and so a hello frame that
  omits or mistypes the flag is rejected. Hello-before-status semantics and the registry's
  replace-on-reconnect behavior are unchanged.
- **Dependencies**: —
- **Target Files**: [`contracts/openapi/openapi.yaml`,
  `backend/src/api/schemas/agent_frames.py`, `frontend/src/types/openapi.d.ts`,
  `backend/tests/test_agent_frames.py`, `backend/tests/test_agent_ws.py`,
  `backend/tests/test_agent_ws_channel.py`, `backend/tests/test_agent_connections.py`]
- **Success Criteria**:
  - A hello frame omitting `is_default_route`, or sending a non-boolean, is rejected as invalid.
  - A valid hello's flag reaches `agent_connections` unchanged for every subnet in the list.
  - Reconnect replaces the whole flagged list rather than merging it.
  - `frontend/src/types/openapi.d.ts` is regenerated (not hand-edited) and the frontend gate is
    green.
  - Backend gate green with `./database.sh` up and a zero skip count.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Command-channel client — frames, signed upgrade, hello, reconnect
- **Description**: Create `transport/command_channel.py` with strict Pydantic models
  `AvailableSubnet`, `AgentHello`, `AgentCommand`, `AgentStatus` (all forbidding extra fields) and
  `CommandChannelClient`. The client converts `BACKEND_URL` `http://`→`ws://` and `https://`→
  `wss://`, dials exactly `/api/v1/agents/{device_id}/commands` with the path UUID byte-for-byte
  equal to `X-Device-Id`, and signs each upgrade with Task 1's helper (`GET`, empty body, fresh
  proof per attempt). Immediately after every successful upgrade — before any pending status replay
  or command read — it sends one `AgentHello` with the installed package version and a freshly
  enumerated subnet list from Task 2. Inbound frames are validated strictly; invalid JSON, unknown
  or wrong `type`, extra keys, invalid UUIDs, unsupported scan modes and invalid IPv4 CIDRs are
  rejected without dispatch, and backend `error` frames never start work. A send lock serializes
  lifecycle frames. Reconnect uses the fixed schedule `1, 2, 5, 10, 30` seconds capped at 30, with
  injectable sleep, resetting only after a successful upgrade *and* hello send. Classify per
  INTEGRATION.md: network failure / normal close / backend restart / upgrade `401` → retry with a
  fresh proof; upgrade `403`, an OpenAPI permanent-revocation close, and close `4000` reason
  `replaced` → park with a secret-safe diagnostic and never redial; invalid local configuration
  fails before dialing. Add the direct `websockets` runtime dependency and regenerate the
  hardware-agent lockfile only.
- **Dependencies**: 1, 2, 3
- **Target Files**: [`hardware-agent/src/agent/transport/command_channel.py`,
  `hardware-agent/src/agent/transport/__init__.py`, `hardware-agent/pyproject.toml`,
  `hardware-agent/uv.lock`, `hardware-agent/tests/unit/test_command_channel.py`]
- **Success Criteria**:
  - URL conversion covers both schemes and produces the exact documented path.
  - The upgrade carries all five proof headers; a second attempt reuses no header value.
  - Exactly one fresh hello is sent per successful upgrade, before anything else, on first connect
    and every reconnect.
  - Malformed JSON, wrong/unknown type, extra keys, bad UUID, bad mode and bad CIDR each produce no
    dispatched command, and the socket stays usable where safe.
  - Concurrent sends are serialized — no interleaved frames under a forced concurrent write test.
  - Backoff asserts the pinned sequence with injected sleep, the 30s cap, and reset only after
    upgrade + hello.
  - `403`, permanent-revocation close, and `4000/replaced` each park with no further dial; `401`
    retries with a completely fresh proof.
  - No diagnostic contains the private key, a signature, or a signed URL.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Daemon coordinator — ledger, lifecycle, scan and upload orchestration
- **Description**: Create `agent/daemon.py` with `CommandRecord`, `AgentDaemon` and `run_daemon()`.
  `run_daemon()` loads the existing `load_ingest_config()` once and constructs the command and
  ingest clients. `AgentDaemon` keeps a process-lifetime ledger keyed by `command_id` holding the
  latest status, optional stable error code, and whether that status is still pending delivery after
  a disconnect. The receive loop never runs nmap or HTTP ingest: it records the accepted command,
  sends `running`, and starts one owned async task that calls `run_headless_scan(mode, subnet)` then
  `ScanIngestClient.submit(payload, scan_id=command.scan_id)` — both via `asyncio.to_thread`. Task
  exceptions are converted to `failed`, never left unobserved. Enforce the state machine: `fatal`
  outcome, missing payload, or missing persisted result path → `failed` without calling ingest;
  `completed`/`partial` with both payload and path → `uploading`; ingest `accepted` → `done`; any
  other outcome → `failed`. Error codes are exactly `device_busy`, `invalid_command`, `scan_failed`,
  `result_unavailable`, `ingest_failed`. A duplicate `command_id` replays its recorded status and
  starts no second scan or upload. A different command while one is `running`/`uploading` gets
  `failed/device_busy` and is not queued. Ingest `forbidden` records `failed/ingest_failed`, makes at
  most one best-effort status send, closes the socket and parks. A socket drop does not cancel an
  active scan; pending status is replayed after reconnect before new work is acted on. Idle
  controlled shutdown closes the socket and the owned ingest client; no cancellation parameter is
  added to `run_headless_scan` or `ScanRunner`.
- **Dependencies**: 4
- **Target Files**: [`hardware-agent/src/agent/daemon.py`,
  `hardware-agent/tests/unit/test_daemon.py`]
- **Success Criteria**:
  - Frame order asserted at the client boundary for: completed → `running, uploading, done`;
    partial → `running, uploading, done`; fatal → `running, failed/scan_failed`; missing persisted
    result → `running, failed/result_unavailable` with no upload attempt; every non-accepted ingest
    outcome → `running, uploading, failed/ingest_failed`; unexpected scan exception →
    `failed/scan_failed`.
  - A held blocking fake scan proves the receive loop still answers a duplicate and rejects a
    different command as `failed/device_busy`, with the active command unaffected.
  - The same `command_id` delivered during `running`, during `uploading`, and after each terminal
    outcome yields exactly one headless invocation and at most one upload.
  - `run_headless_scan` and `submit` are both invoked off the event loop.
  - Disconnect mid-scan preserves the work, and reconnect replays pending status before handling
    newly received commands, with no second execution.
  - Ingest `forbidden` parks the daemon: at most one best-effort failed status, socket closed, no
    redial, no further command accepted.
  - Idle shutdown closes the owned ingest client; no test asserts mid-scan cancellation, resumption,
    or a final frame after process termination.
  - `rg -n "ScanRunner\(|run_headless_scan\(|ScanProgressScreen\(|ScanIngestClient\(" hardware-agent/src hardware-agent/tests`
    matches ARCHITECTURE.md's call-path audit table with no unintended new or changed call site.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: CLI bare-agent daemon dispatch and startup nmap gate
- **Description**: Modify `_run_agent(args)` in `agent/cli.py` so zero arguments run the existing
  `_check_nmap()` presence check and then start `run_daemon()`, two arguments keep the current
  one-shot `run_headless_scan` path with unchanged output and exit codes, and any other arity is a
  usage error with updated text. A missing scanner at startup prints the existing safe installation
  guidance and exits with fatal code `20` before any WebSocket dial. No version probe, capability
  negotiation, or background health check.
- **Dependencies**: 5
- **Target Files**: [`hardware-agent/src/agent/cli.py`,
  `hardware-agent/tests/unit/test_cli_agent.py`]
- **Success Criteria**:
  - Bare `dmitri agent` calls `_check_nmap()` then `run_daemon()`.
  - Missing nmap exits `20` with the existing guidance and no connection attempt is made.
  - `dmitri agent <mode> <subnet>` produces byte-identical JSON output and exit codes to the current
    behavior; existing one-shot CLI tests pass unchanged.
  - One or three-plus arguments produce a usage error.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Status table

| Task | Name | Layer | Status | Rejections |
|------|------|-------|--------|-----------|
| 1 | Shared Ed25519 signing helper | hardware-agent | COMPLETED | 0 |
| 2 | Available subnet enumeration | hardware-agent | COMPLETED | 0 |
| 3 | `is_default_route` contract | contracts/backend/frontend | COMPLETED | 0 |
| 4 | Command-channel client | hardware-agent | COMPLETED | 0 |
| 5 | Daemon coordinator | hardware-agent | COMPLETED | 0 |
| 6 | CLI daemon dispatch | hardware-agent | COMPLETED | 0 |
