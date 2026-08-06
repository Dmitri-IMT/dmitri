# INTEGRATION — Pi agent daemon command execution

## Boundary ownership

| Concern | Owner |
|---------|-------|
| Command creation, delivery, lifecycle persistence, stale sweep | Existing backend command channel |
| Signed outbound connection, frame validation, reconnect | DMI-66 command-channel client |
| One-active-command state and scan/upload orchestration | DMI-66 daemon |
| Scan execution and local persistence | Existing hardware-agent headless path |
| Signed result upload and HTTP retry/response mapping | Existing `ScanIngestClient` |
| Result validation and persistence under the delivered scan | Existing backend ingest route |
| Interface discovery, default-route marking, hello construction | DMI-66 hardware-agent scope, including the absorbed DMI-73 requirements |
| Hello schema and in-memory replacement cache | Shared OpenAPI contract and existing backend command channel |

## End-to-end sequence

```text
backend             command client          daemon          headless         ingest client
   | signed WS upgrade    |                    |                 |                  |
   |<---------------------|                    |                 |                  |
   | 101                  |                    |                 |                  |
   |--------------------->|                    |                 |                  |
   | hello: version + current flagged subnets   |                 |                  |
   |<---------------------|                    |                 |                  |
   | command frame        |                    |                 |                  |
   |--------------------->| validate + dispatch|                 |                  |
   |                      |------------------->|                 |                  |
   | status: running      |<-------------------|                 |                  |
   |<---------------------|                    | to_thread scan  |                  |
   |                      |                    |---------------->|                  |
   |                      |                    | payload + path  |                  |
   | status: uploading    |<-------------------|<----------------|                  |
   |<---------------------|                    | to_thread submit(payload, scan_id)  |
   |                      |                    |------------------------------------>|
   | POST /api/v1/scans   |                    |                 |<-----------------|
   | accepted 202         |                    |                 |----------------->|
   |                      |                    | valid accepted result               |
   |                      |                    |<------------------------------------|
   | status: done         |<-------------------|                 |                  |
   |<---------------------|                    |                 |                  |
```

Any fatal scan or non-accepted ingest result replaces the remaining success steps with one
`failed` status carrying a stable error code.

## WebSocket upgrade contract

| Item | Value |
|------|-------|
| HTTP origin source | Existing `BACKEND_URL` |
| Production URL | `wss://{api}/api/v1/agents/{device_id}/commands` |
| Local URL | `ws://{api}/api/v1/agents/{device_id}/commands` |
| Method/path signed | `GET` and `/api/v1/agents/{device_id}/commands` exactly |
| Body hash | SHA-256 of zero bytes |
| Identity equality | Path UUID and `X-Device-Id` are byte-for-byte equal canonical UUID text |
| Proof headers | `X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Body-SHA256`, `X-Signature` |

The canonical string is:

```text
GET
/api/v1/agents/{device_id}/commands
{X-Device-Id}
{X-Timestamp}
{X-Nonce}
{X-Body-SHA256}
```

Every reconnect creates a new proof. No signature header from an earlier attempt is reused.

### Reconnect classification

| Result | Client action |
|--------|---------------|
| Network failure, normal close, or backend restart | Retry after `1, 2, 5, 10, 30` seconds, then remain capped at 30 seconds |
| Upgrade `401` | Retry on the same schedule with a completely fresh proof; a clock that synchronizes during backoff can recover |
| Upgrade `403` | Park with a secret-safe diagnostic; do not redial; operator intervention is required |
| Close classified by OpenAPI as permanent revocation | Park until externally terminated; do not dial or accept commands; DMI-97 owns the concrete close code and backend enforcement |
| Close `4000` with reason `replaced` | Park until externally terminated; do not dial, accept commands, or send WS status; an existing scan may finish HTTP ingest pending DMI-101 fencing |
| Invalid local configuration | Fail before dialing |

The schedule resets after the upgrade succeeds and the hello frame is sent. Tests inject sleep and
connection outcomes; they do not use wall-clock delays.

## Frame contract

The normative schemas remain `AgentCommandFrame` and `AgentStatusFrame` in
`contracts/openapi/openapi.yaml`.

### Device to backend on every connection

```json
{
  "type": "hello",
  "agent_version": "0.1.4",
  "available_subnets": [
    {
      "interface": "eth0",
      "cidr": "10.0.0.0/24",
      "is_default_route": false
    },
    {
      "interface": "wlan0",
      "cidr": "192.168.1.0/24",
      "is_default_route": true
    }
  ]
}
```

Hello is the first application frame after every successful upgrade. The list is freshly detected
on reconnect and replaces the backend registry's prior list. It is reported state, not a device-side
target selection. `is_default_route` is required in OpenAPI, the generated frontend type, and the
backend Pydantic model; older senders that omit it are rejected as invalid hello frames.

### Backend to device

```json
{
  "type": "command",
  "command_id": "uuid",
  "scan_id": "uuid",
  "scan_mode": "nspi",
  "subnet": "10.0.0.0/24"
}
```

### Device to backend

```json
{
  "type": "status",
  "command_id": "uuid",
  "status": "running|uploading|done|failed",
  "error_code": null
}
```

`error_code` is null for non-failure states and a stable local code for `failed`. Result payloads
never travel on this socket.

### Duplicate and busy delivery

- A duplicate `command_id` receives the ledger's latest status frame. The scan task and upload task
  counts remain unchanged.
- A different delivered command while work is active receives `failed/device_busy`. This uses the
  existing status schema and backend handler; no new ack or busy frame is invented.
- Backend status updates are monotonic. Replayed equal or older status is a safe no-op.

### Early running frame

The daemon sends `running` once before scan execution. Backend delivery commits the stub scan only
after sending the command frame, so that first status can overtake the commit and be discarded by
the existing `scan_id IS NOT NULL` guard. The daemon does not sleep, retry, or wait for an ack.
Subsequent `uploading`, ingest-driven `done`, or `failed` can legally advance from `delivered`, so
integration acceptance requires the correct terminal state rather than every intermediate state in
database history.

## Scan and ingest handoff

The daemon calls the existing one-shot headless function with only the command mode and subnet. It
does not introduce a `ScanRunner` parameter or alter TUI construction. After the scan:

1. `fatal`, missing payload, or missing result path reports `failed` and does not call ingest.
2. `completed` or `partial` with both payload and path reports `uploading`.
3. The daemon calls `ScanIngestClient.submit(payload, scan_id=command.scan_id)`.
4. The ingest client creates a temporary payload copy carrying the backend id. The original payload
   and persisted artifact remain unchanged.
5. Only `SubmissionResult.outcome == "accepted"` reports `done`.
6. `SubmissionResult.outcome == "forbidden"` records `failed/ingest_failed`, permits one
   best-effort failed status on the current socket, then closes the socket and parks without
   accepting commands or reconnecting. Every other non-accepted outcome fails the command but does
   not change the command-channel reconnect policy.

## Reconnect and stale-command interaction

Connection loss does not cancel an already running local scan. The daemon records lifecycle changes
while disconnected and replays the latest pending state after reconnect. The backend remains
authoritative:

- If reconnect occurs within its grace window, a replay advances or confirms the command.
- If the stale sweep has already made the command terminal, replay cannot revive it.
- A later ingest `400/rejected` is final. The daemon reports/records `failed/ingest_failed`, does
  not retry outside the ingest client's policy, and does not queue the artifact.

No new command is accepted locally while the prior scan or upload task is active, even if the socket
has reconnected.

Process termination is not a command-channel transition. DMI-66 does not cancel/resume a blocking
scan or promise a final frame during shutdown. The later service manager terminates the process
group; the existing backend disconnect grace and stale sweep own the eventual `failed` transition.

## Error mapping

| Boundary failure | Device behavior | Backend-observable result |
|------------------|-----------------|---------------------------|
| Invalid local environment, private key, or missing startup nmap | Exit daemon before connection; secret-safe stderr and fatal code `20` | Device remains offline |
| Nmap disappears after connection | Existing headless path returns fatal | `failed/scan_failed`; no upload |
| Default-route lookup unavailable | Send current usable subnets with every route flag false | Device remains online; no target is guessed |
| Daemon process terminates during work | No local resume, queue, or final-frame guarantee | Existing disconnect grace and stale sweep eventually mark the command failed |
| WS `401` authentication rejection | Fresh proof after capped backoff | Recovers after clock synchronization; otherwise remains offline between attempts |
| WS `403` authorization rejection | Park without reconnecting; emit only a secret-safe diagnostic | Device remains offline pending operator action |
| WS permanent-revocation close defined by OpenAPI | Park; do not reconnect or accept commands | Device remains offline pending operator action; DMI-97 owns the concrete close code and backend enforcement |
| WS `4000/replaced` close | Park; do not reconnect or accept commands; active work may finish HTTP ingest | Replacement remains the sole live command connection; DMI-101 owns future cancellation/fencing |
| Network drop or transient handshake/server failure | Capped reconnect; retain active state | Offline until reconnect; pending status replayed |
| Malformed/unsupported inbound frame | Ignore with safe diagnostic; keep socket when usable | No scan or lifecycle mutation |
| Headless `fatal` or unexpected exception | Do not upload | `failed/scan_failed` |
| Result was not persisted | Do not upload | `failed/result_unavailable` |
| Ingest `forbidden` | Record `failed/ingest_failed`, make at most one best-effort failed status send, close the socket, and park | Device remains offline pending operator action; no later command is accepted |
| Any other non-accepted ingest outcome | Respect the ingest client's existing retry/finality decision; never add daemon retries or a queue | `failed/ingest_failed` unless backend is already terminal; daemon remains available for later commands |

The ingest client's typed outcome and fixed secret-safe message remain available to local stderr and
tests. They are not expanded into separate command-channel error codes.

## Network-report contract

- Enumerate up, non-loopback, non-link-local IPv4 interfaces with valid netmasks.
- Convert each address/netmask pair to its canonical network CIDR and remove duplicate
  interface/CIDR entries.
- Mark only entries on the interface selected by the system's outbound IPv4 route. If that route
  cannot be determined, report the usable list with every flag false rather than guessing or
  failing the WS connection.
- Recompute on every reconnect; do not cache the list on disk.
- The backend replaces the in-memory prior list atomically through its existing hello handler.
- No scan starts until a backend command explicitly supplies a subnet.

## Verification boundary

Automated hardware-agent tests use injected WebSocket connections, reconnect sleep, headless runner,
and ingest client. They verify exact frames, calls, threading, and state without a database or Pi.

The existing local backend provides the integration check:

1. Provision a local test device and start the backend WS and ingest routes.
2. Run bare `dmitri agent` with the three existing environment values.
3. Deliver one command with backend-owned command and scan UUIDs.
4. Assert the first application frame reports all current subnets with the correct default-route
   flag and that a reconnect after an interface change replaces the registry list.
5. Assert the daemon emits `running → uploading → done`, the backend reaches `done`, and results are
   persisted under that scan UUID; allow stored history to omit an early `running` frame.
6. Deliver the same command twice and assert exactly one headless invocation and upload.
7. Inject a different command while the first scan is held and assert `failed/device_busy` without
   disturbing the first command.
8. Drop the socket mid-scan, restore it within grace, and assert fresh signed reconnect, fresh hello,
   plus status
   replay without a second scan.

Real Pi, service-manager, reboot, and clock-synchronization validation are
`HUMAN_INFRA_REQUIRED` and remain outside this issue.
