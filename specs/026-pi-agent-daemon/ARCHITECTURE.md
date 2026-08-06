# ARCHITECTURE — Pi agent daemon command execution

## System context

DMI-66 adds the long-lived device-side coordinator between the backend command channel and the
existing hardware-agent scan and ingest paths:

```text
backend WS command
  → daemon command state
  → existing headless scan
  → existing ScanRunner and scan stages
  → existing local result persistence
  → existing ScanIngestClient with backend scan_id override
  → backend ingest
```

The daemon is a new front door. It does not add a scan pipeline, change normalization, or route
remote work through the TUI. The current one-shot `dmitri agent <mode> <subnet>` command remains
available; bare `dmitri agent` starts the daemon.

Bare daemon startup reuses the existing `agent.cli._check_nmap()` presence check before loading the
async command loop. Failure prints the existing safe installation guidance and exits with ADR-012's
fatal code `20` before opening the WebSocket. There is no version probe or background health check.
If nmap disappears later, `run_headless_scan` returns `fatal` and the active command maps to
`failed/scan_failed`.

## Component responsibilities

### Shared device signing

Extract the existing Ed25519 envelope construction from `transport/ingest.py` into a small shared
helper. It accepts method, exact path, body bytes, device id, and private-key bytes and returns the
five device headers. The ingest client uses it with `POST`, `/api/v1/scans`, and the serialized
payload. The command client uses it with `GET`, the agent-specific command path, and an empty body.

The helper creates a fresh timestamp, nonce, body hash, and signature for every HTTP attempt or WS
upgrade. It never stores, logs, or interpolates the private key into an error.

### Command-channel client

`CommandChannelClient` owns URL conversion, the signed WebSocket upgrade, hello and status writes,
JSON frame validation, and reconnect timing. `http://` maps to `ws://`; `https://` maps to
`wss://`. The path is exactly `/api/v1/agents/{device_id}/commands`, and the path UUID is the same
canonical value sent in `X-Device-Id`.

Inbound commands are strict typed models: unknown fields, invalid UUIDs, unsupported scan modes,
and invalid IPv4 CIDRs are rejected before dispatch. Unsupported, malformed, and backend `error`
frames do not start scans. A send lock prevents lifecycle frames from being interleaved when the
receive loop and scan task report concurrently.

### Available subnet reporting

Extend `agent.utils.network` with daemon-facing enumeration. It reads up interfaces and their IPv4
addresses from `psutil`, rejects loopback, link-local, missing-netmask, invalid, and duplicate
interface/CIDR entries, and returns the canonical network CIDR for each usable entry. The TUI's
private interface enumerator remains unchanged and outside this feature.

The existing default-route detection identifies the outbound IPv4 address and maps it back to its
interface. Each reported entry includes `is_default_route`; the entry belonging to that interface is
true and every other entry is false. A detection failure does not make the signed WS connection
fail: the daemon sends the usable entries with every route flag false, allowing the backend to show
what is known without guessing.

Immediately after every successful upgrade, before replaying any pending status or reading a
command, the client sends `AgentHelloFrame` containing the installed package version and the freshly
enumerated list. The backend's existing `set_hello` assignment replaces its in-memory prior list.
The Pi does not store `target_subnet` and never selects an entry.

### Daemon coordinator

`AgentDaemon` owns one active execution task and a process-lifetime command ledger keyed by
`command_id`. The ledger records the latest lifecycle status, optional stable error code, and
whether that status still needs to be sent after a disconnect.

The WebSocket receive loop never runs nmap or HTTP ingest directly. It records an accepted command,
sends `running`, and starts an async task. The task calls both blocking operations with
`asyncio.to_thread`: first `run_headless_scan`, then `ScanIngestClient.submit`. This keeps the
receive loop responsive to duplicate and defensive busy cases while scan subprocesses or ingest
retries are in progress.

The scan task is owned and observed by the daemon; exceptions are converted to `failed` rather than
left as unobserved background-task failures. The ingest client is closed on daemon shutdown.

### Shutdown boundary

An idle controlled shutdown closes the current socket and owned ingest client. DMI-66 does not add
a cancellation parameter to `run_headless_scan` or `ScanRunner`, wait for a bounded cancellation,
persist active command state, or attempt a final status after process termination has begun. The
later service-manager unit owns process-group termination. If the process disappears without a
terminal frame, the backend's existing disconnect grace and stale sweep make the command failed.

## Command state machine

```text
valid idle command
  → running
  → fatal scan or missing persisted result → failed
  → uploading
  → accepted ingest → done
  → any non-accepted ingest outcome → failed
```

- `completed` and `partial` headless outcomes are uploadable. `fatal` is not. Accepted ingest marks
  either upload `done`; a partial result stays distinguishable through its persisted scan metadata.
- `uploading` is sent only when both the in-memory payload and persisted result path exist.
- `done` is sent only after a valid ingest `202` acknowledgement.
- Every terminal failure carries a stable local `error_code`; response bodies and exception text
  are not placed on the wire.
- A duplicate known `command_id` replays its recorded status and never creates another task or
  upload.
- A different command received while the active command is `running` or `uploading` receives
  `failed` with `error_code: device_busy`. This is defensive: normal backend enqueue logic should
  prevent such delivery.
- The ledger is process-lifetime state, not a durable local queue. A process crash ends active work;
  backend stale-command handling remains authoritative. Terminal backend commands are not revived.

### Early running race

The backend sends a command frame before committing its stub scan and `delivered` transition. A
prompt `running` frame can therefore arrive while the command still has no committed `scan_id`; the
existing backend intentionally drops that frame. The daemon still emits `running` exactly once
before scan execution, but does not delay work, repeat the frame, or invent an acknowledgement.
Later `uploading`, ingest-driven `done`, or `failed` advances monotonically and remains authoritative.

## Reconnect behavior

Network errors, normal closure, backend restart, and a `401` upgrade rejection enter the fixed
backoff schedule `1, 2, 5, 10, 30` seconds, capped at 30 seconds. Every attempt rebuilds the full
signature envelope with a fresh timestamp and nonce; this lets an initially unsynchronized Pi clock
self-recover. The backoff resets only after a successful upgrade and hello send. Sleep is injectable
so tests do not wait.

A `403` upgrade rejection is permanent and parks with a secret-safe diagnostic. A
WebSocket close that OpenAPI classifies as permanent revocation also parks without another dial;
DMI-97 owns adding the concrete live-revocation close code and backend enforcement. WebSocket close
`4000` with reason `replaced` stops reconnecting because another daemon instance owns the device
slot. The replaced daemon remains parked until externally terminated; it accepts no commands and
sends no further WS statuses. An already-running scan may finish and use the existing HTTP ingest
path. Active cancellation, fencing, and replacement work belong to DMI-101. Invalid local
configuration exits before any connection attempt. These rules follow the close-code table in
OpenAPI rather than treating every disconnect alike.

An ingest outcome of `forbidden` is the HTTP permanent-revocation signal in the existing backend.
The daemon records the active command as `failed/ingest_failed`, makes at most one best-effort status
send on the current socket, closes the socket, and parks. It does not accept another command or
redial. Other non-accepted ingest outcomes fail only the command and retain the normal connection
policy.

An active scan continues if the socket drops. Status changes are recorded as pending. After a new
connection is established, pending/current status is replayed before newly received work is acted
on. If the backend has already closed the command, its monotonic status update is a no-op and ingest
returns a final rejection; the daemon does not requeue or retry that result.

## Data model and contracts

No scan payload, scanner model, database, or backend service change is required. The shared OpenAPI
and backend frame model gain the default-route boolean required by the combined subnet-reporting
scope. The daemon consumes `AgentCommandFrame` and emits `AgentHelloFrame` and `AgentStatusFrame`
from `contracts/openapi/openapi.yaml`.

| Contract | Existing/new type | Rule |
|----------|-------------------|------|
| Device configuration | Existing `IngestConfig` / `load_ingest_config` | Reuse `BACKEND_URL`, `DEVICE_ID`, and `DEVICE_PRIVATE_KEY`; do not add a second parser |
| Available subnet | Extended shared `AvailableSubnet` contract | Interface name, canonical IPv4 CIDR, required `is_default_route` boolean |
| Hello | New hardware-agent `AgentHello` | `type=hello`, installed agent version, current available-subnet list, no extra fields |
| Command | New `AgentCommand` | `type=command`, UUID command and scan ids, existing scan mode, valid IPv4 CIDR, no extra fields |
| Status | New `AgentStatus` | `type=status`, command UUID, one of running/uploading/done/failed, nullable stable error code |
| Scan result | Existing `HeadlessScanResult` | Payload and persisted result path are both required before upload |
| Ingest | Existing `ScanIngestClient.submit(payload, scan_id=…)` | Pass the backend-provided scan id; do not mutate the local payload or artifact |

### Stable daemon error codes

| Failure | Status error code |
|---------|-------------------|
| Different command while active | `device_busy` |
| Invalid scan input that passed frame validation | `invalid_command` |
| Fatal scan outcome or unexpected scan exception | `scan_failed` |
| Payload exists but no persisted result exists | `result_unavailable` |
| Any non-accepted ingest outcome | `ingest_failed` |

The daemon may write the ingest client's existing fixed, secret-safe outcome message to stderr for
diagnosis, but the WS contract does not expose transport-specific failure categories.

## Call-path audit

No `ScanRunner`, `ScanProgressScreen`, or `run_headless_scan` parameter changes are introduced.
The backend scan id is applied only at the existing ingest override boundary.

| Constructor/call path | Disposition |
|-----------------------|-------------|
| `agent.cli.main()` → `_run_agent(args)` | Modify dispatch: zero args runs the existing nmap presence check then starts daemon; two args retain one-shot scan; all other arities show updated usage |
| One-shot `_run_agent` → `run_headless_scan(...)` | Preserve current arguments and exit-code/JSON behavior |
| New `run_daemon()` → `AgentDaemon(...)` | Load the existing transport config once and construct command and ingest clients |
| `AgentDaemon` → `run_headless_scan(mode, subnet, …)` | New call site; invoke in a worker thread with no new runner parameter |
| `run_headless_scan` → `ScanRunner(...)` | Unchanged constructor and callback path |
| `ScanProgressScreen` → `ScanRunner(...)` | Unchanged; remote commands never enter the TUI |
| `HomeScreen` → `ScanProgressScreen(...)` | Unchanged |
| Direct `ScanRunner(...)` test call sites | Unchanged because its constructor is untouched |
| `AgentDaemon` → `ScanIngestClient.submit(payload, scan_id=command.scan_id)` | New caller of the existing override |
| Existing ingest client tests/callers | Update only signer injection/import assertions; submit API remains unchanged |
| `CommandChannelClient` → `detect_available_subnets()` | New caller; performs reporting only and does not feed or alter `ScanRunner` |
| `NetworkScreen` → private `_detect_interfaces()` | Unchanged; remote reporting does not enter or refactor the TUI |
| Backend `handle_agent_frame()` → `AgentHelloFrame` → `agent_connections.set_hello()` | Existing call path; schema gains the required route flag and replacement behavior stays unchanged |

Implementation review must repeat:

```text
rg -n "ScanRunner\(|run_headless_scan\(|ScanProgressScreen\(|ScanIngestClient\(" hardware-agent/src hardware-agent/tests
```

and verify every result matches this table before completion.

## New files and naming (mandatory)

| Action | Layer | Path | Exact responsibility |
|--------|-------|------|----------------------|
| Create | Transport auth | `hardware-agent/src/agent/transport/signing.py` | `build_device_signature_headers` for fresh Ed25519 GET/POST envelopes |
| Modify | Ingest transport | `hardware-agent/src/agent/transport/ingest.py` | Delegate header construction to the shared signer; keep public submit behavior unchanged |
| Modify | Transport exports | `hardware-agent/src/agent/transport/__init__.py` | Export only transport names needed by daemon/tests |
| Create | WS transport | `hardware-agent/src/agent/transport/command_channel.py` | `AvailableSubnet`, `AgentHello`, `AgentCommand`, `AgentStatus`, `CommandChannelClient`, hello-first ordering, URL/path building, strict frames, signed connect, send lock, fixed reconnect classification/backoff |
| Create | Daemon | `hardware-agent/src/agent/daemon.py` | `CommandRecord`, `AgentDaemon`, `run_daemon`; ledger, one-active-task rule, scan/upload orchestration, status/error mapping |
| Modify | CLI | `hardware-agent/src/agent/cli.py` | Bare-agent daemon dispatch while preserving the two-argument one-shot path |
| Modify | Network utility | `hardware-agent/src/agent/utils/network.py` | `detect_available_subnets`; canonical usable IPv4 enumeration and default-route interface marking |
| Modify | Dependencies | `hardware-agent/pyproject.toml` | Add the direct `websockets` runtime dependency |
| Regenerate | Lockfile | `hardware-agent/uv.lock` | Lock only the hardware-agent dependency graph |
| Create | Unit tests | `hardware-agent/tests/unit/test_transport_signing.py` | Exact GET/POST canonical strings, empty-body hash, fresh proof, and secret safety |
| Create | Unit tests | `hardware-agent/tests/unit/test_command_channel.py` | URL conversion, signed upgrade, strict frame parsing, serialized sends, reconnect classification/backoff |
| Create | Unit tests | `hardware-agent/tests/unit/test_daemon.py` | Lifecycle, thread boundary, duplicate, busy, reconnect replay, result-path gate, ingest mapping, cleanup |
| Modify | Network tests | `hardware-agent/tests/test_network_detection.py` | Dual/single-homed enumeration, filters, deduplication, canonical CIDRs, default route, detection fallback |
| Modify | CLI tests | `hardware-agent/tests/unit/test_cli_agent.py` | Bare daemon dispatch, preserved one-shot dispatch, usage and fatal startup behavior |
| Modify | Ingest tests | `hardware-agent/tests/unit/test_ingest_client.py` | Preserve existing request/signature coverage through the shared signer |
| Modify | Shared contract | `contracts/openapi/openapi.yaml` | Require `AvailableSubnet.is_default_route` and retain hello-before-status semantics |
| Regenerate | Frontend contract types | `frontend/src/types/openapi.d.ts` | Regenerate from OpenAPI; no hand-written frontend behavior |
| Modify | Backend frame schema | `backend/src/api/schemas/agent_frames.py` | Add required `is_default_route: bool` to `AvailableSubnet` |
| Modify | Backend frame tests | `backend/tests/test_agent_frames.py` | Validate the required boolean and strict rejection when absent or mistyped |
| Modify | Backend WS tests | `backend/tests/test_agent_ws.py` | Update hello fixtures and assert route flag reaches the registry |
| Modify | Backend channel tests | `backend/tests/test_agent_ws_channel.py` | Update hello fixtures and verify reconnect replaces the full flagged list |
| Modify | Backend registry tests | `backend/tests/test_agent_connections.py` | Store and replace flagged subnet models without persistence |

## Constraints

- No backend persistence/service change, hand-written frontend behavior, TUI code/design,
  scan-stage, normalization, or artifact-format change.
- No service-manager unit, installer, key provisioning, local command queue, HTTP polling fallback,
  external broker, or device-side target selection/storage.
- No new graceful mid-scan shutdown/cancellation contract; do not change `ScanRunner` or
  `run_headless_scan` for process termination.
- No scan preemption, command/daemon generation lease, late-work fencing, or force-restart path;
  DMI-101 owns those cross-process semantics.
- No second scan runner and no upload inside `ScanRunner` or `run_headless_scan`.
- No retry of a final ingest client outcome; its existing retry policy remains authoritative.
- No scanner version probe, capability negotiation, periodic health check, or new readiness system;
  startup reuses `_check_nmap()` exactly once.
- No application logs or errors may contain the private key, signature, signed URL query, scan
  payload, backend response body, or raw exception details.
- `HUMAN_INFRA_REQUIRED`: production daemon validation ultimately requires a provisioned Pi,
  synchronized system time, and later service-manager packaging. Those are not created or changed
  by DMI-66; automated implementation remains locally testable.

## Testing expectations

| Area | Verification |
|------|--------------|
| Shared signing | Independently verify Ed25519 signatures for the exact WS GET and ingest POST canonical strings; assert empty-body SHA-256 on upgrade and new nonce/signature per attempt |
| Interface enumeration | Report each distinct usable IPv4 interface/CIDR, filter unusable addresses, identify the default-route interface when detectable, and report all flags false without failing or guessing when it is not |
| Hello ordering | On initial connect and every reconnect, send exactly one fresh hello before pending status replay or command handling; backend registry holds the newest full list |
| Command validation | Reject malformed JSON, wrong/unknown type, extra keys, invalid UUID/mode/CIDR without starting work or disrupting an active command |
| Responsiveness | Hold a fake blocking scan in a worker thread and prove the receive loop still acknowledges a duplicate and rejects a different command as busy |
| Lifecycle | At the client boundary assert exact emitted frame order for completed, partial, fatal, missing-result, every ingest outcome, and unexpected exception paths; every non-accepted ingest outcome maps to `ingest_failed` |
| Idempotency | Deliver the same id during running, uploading, and after each terminal outcome; prove one scan and at most one upload |
| Reconnect | Verify the pinned backoff and reset; disconnect during scan/upload, preserve work, reconnect with fresh proof, replay pending status, and avoid duplicate execution |
| Permanent disconnects | Prove upgrade `403`, any OpenAPI permanent-revocation close, ingest `forbidden`, and close `4000/replaced` park without another dial or command acceptance; ingest `forbidden` permits only one best-effort failed status before socket close |
| Shutdown | Idle controlled shutdown closes owned clients; no test expects active scan cancellation, resumption, or a final frame after process termination |
| CLI regression | Bare agent enters daemon mode; two arguments preserve current one-shot output and exit codes; invalid arity is usage error |
| Scanner readiness | Missing nmap prevents the first dial and exits `20`; disappearance after connection produces `failed/scan_failed` through the existing headless outcome |
| Call-path regression | Existing headless, TUI, and direct `ScanRunner` tests pass unchanged |
| Boundary integration | Local backend sends a command and reaches done with ingest stored under its scan id; allow the documented delivery race to omit persisted running, while duplicate delivery runs once and defensive concurrent delivery reports busy |

Run from `hardware-agent/` only:

```text
uv run pytest
uv run ruff check src tests
```

Do not run a repository-wide formatter.

Also run the scoped backend and frontend gates because the shared hello contract changes:

```text
cd backend
uv run ruff check src tests
uv run pytest

cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```
