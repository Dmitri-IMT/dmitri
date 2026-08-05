# INTEGRATION — Pi ingest client and Ed25519 signing

## Boundary ownership

This document freezes the process boundary between the hardware agent and the already-implemented
backend ingest route.

| Concern | Owner |
|---|---|
| Scan execution, normalization, and local JSON persistence | Hardware-agent scan pipeline |
| Request serialization, Ed25519 signing, HTTP retry, and response mapping | DMI-65 ingest client |
| Device lookup, freshness/replay checks, signature verification, authorization, and persistence | Existing backend ingest implementation |
| Calling the client after a remote command and reporting command status | DMI-66 daemon, out of scope here |

## Sequence

```text
future daemon        local workspace       ingest client             backend
     |                      |                    |                       |
     | run scan             |                    |                       |
     |--------------------->|                    |                       |
     | payload + path       |                    |                       |
     |<---------------------|                    |                       |
     | assert path exists                        |                       |
     | submit(payload, assigned scan_id?)        |                       |
     |------------------------------------------>|                       |
     |                      |       serialize body once                  |
     |                      |       build fresh signed envelope          |
     |                      |                    | POST /api/v1/scans    |
     |                      |                    |---------------------->|
     |                      |                    | 202 / 4xx / 5xx       |
     |                      |                    |<----------------------|
     |                      |       retry only transport/5xx             |
     |                      |       with a new envelope                  |
     | typed SubmissionResult                    |                       |
     |<------------------------------------------|                       |
     | local artifact remains unchanged          |                       |
```

The client never scans, writes artifacts, changes command state, or sends WebSocket frames.

## Configuration contract

The process environment contains:

```text
BACKEND_URL=https://api.example.invalid
DEVICE_ID=<agent UUID>
DEVICE_PRIVATE_KEY=<64 hex characters / 32-byte Ed25519 private seed>
```

For local development, `BACKEND_URL=http://127.0.0.1:8000` is valid. The future systemd unit may
use `EnvironmentFile=/etc/dmitri/agent.env`; DMI-65 receives already-populated environment values
and does not read that file itself.

Only the public key derived from `DEVICE_PRIVATE_KEY` is registered with the backend. The private
value never appears in a URL, body, header, result, exception, or log.

## HTTP contract

| Item | Value |
|---|---|
| Method | `POST` |
| URL | `{BACKEND_URL}/api/v1/scans` |
| Signed path | `/api/v1/scans` exactly; scheme, authority, and query are not signed |
| Body | UTF-8 bytes from compact `ScanPayload.model_dump_json()` |
| Content type | `application/json` |
| Success | HTTP `202` with a valid accepted acknowledgement |
| Redirects | Not followed; returned as `protocol_error` |

### Body identity

The submitted body is the existing normalized scan payload. If the caller supplies a
backend-assigned `scan_id`, only a temporary model copy carries that id. The original model and
artifact remain unchanged. The body is serialized once so retries submit identical bytes.

### Required headers

| Header | Value |
|---|---|
| `X-Device-Id` | Canonical UUID text from `DEVICE_ID` |
| `X-Timestamp` | Current UTC ISO-8601 timestamp with offset, regenerated per attempt |
| `X-Nonce` | `secrets.token_hex(16)`, regenerated per attempt |
| `X-Body-SHA256` | Lowercase SHA-256 hex of the exact body bytes |
| `X-Signature` | Lowercase 128-character Ed25519 signature hex |

The signature input is the UTF-8 form of:

```text
POST
/api/v1/scans
{X-Device-Id}
{X-Timestamp}
{X-Nonce}
{X-Body-SHA256}
```

No trailing newline is appended.

## Retry sequence

The body is stable across attempts; the envelope is not.

1. Serialize the effective payload and compute its body hash.
2. Generate timestamp and nonce, construct the canonical string, and sign it.
3. Send with the fixed per-attempt timeouts (connect 10 s, write 60 s, read 120 s, pool 10 s).
4. On a transport failure or `5xx`, wait for the next fixed delay and return to step 2.
5. Stop after three total attempts.

The backend records a valid nonce before route persistence. Reusing headers after any verified
attempt can therefore turn a legitimate retry into replay `401`; the retry loop must regenerate all
per-attempt fields even when the body is unchanged.

## Response and error mapping

| Backend/network result | Client outcome | Attempts | Artifact |
|---|---|---|---|
| Valid `202`, matching scan id and host count | `accepted` | Current attempt | Untouched |
| `401` wrong key, unknown identity, stale proof (including an unsynchronised device clock), malformed proof, or replay | `unauthorized` | Stop immediately | Untouched |
| `403` revoked device, or a scan identity owned by a different device or organisation | `forbidden` | Stop immediately | Untouched |
| `413` or `422` | `invalid` | Stop immediately | Untouched |
| `400` closed scan (the command already reached a terminal state) or another `4xx` | `rejected` | Stop immediately | Untouched |
| Transport failure or `5xx`, attempts remain | Retry with fresh proof | Up to three | Untouched |
| Transport failure or `5xx`, attempts exhausted | `unavailable` | Three | Untouched |
| Redirect, unexpected success code, or malformed/contradictory `202` | `protocol_error` | Stop immediately | Untouched |

### A closed scan is a deliberate discard, not a race

`400` deserves special care from DMI-66, because it is easy to mistake for a bug worth working
around. Per ADR-011, a WS drop mid-scan or a stale post-delivery agent is swept to a terminal
`failed` command, and terminal status is exactly what releases the one-active-scan-per-agent lock.
By the time a late result arrives, the operator may already have started a replacement scan.

The service therefore discards the late result on purpose. `rejected` is the correct, final answer:
the daemon must not retry it, must not requeue it, and must not treat the retained local artifact as
pending upload. Recovery is a new scan. Anything that "rescues" the old result would write into a
released scan record underneath a live replacement command.

### Status-code authority

ADR-005 previously listed an unknown device under `403`. The shipped backend returns `401` for an
unknown device and reserves `403` for a registered-but-revoked device and for scan-ownership
failures. ADR-005 was corrected on 2026-08-05 to match; the mapping above follows the running code,
and the two now agree.

The client does not return the backend response body as its message. Stable local messages and the
numeric status code are the public diagnostics.

## Local-backend verification

This is a smoke test at the existing development boundary, not a new automated infrastructure
dependency:

1. Start the existing local backend/database using the repository setup instructions.
2. Provision a test agent with the existing backend management command and capture its device id
   and one-time private-key hex output. That command's `--generate` flag prints a private key from
   the backend side and labels itself local-testing-only; it is a development shortcut, not the
   provisioning model. ADR-005 requires each device to generate its own keypair so the private key
   never leaves the device, and real provisioning is out of scope here.
3. Persist a contract-valid scan artifact locally and record its checksum.
4. Load the three environment values, validate the artifact as a `ScanPayload`, and submit it with
   `ScanIngestClient`.
5. Assert the result is `accepted`, verify the scan exists in the local backend, and confirm the
   artifact checksum is unchanged.
6. Repeat with a different private key and assert `unauthorized` with the same artifact checksum.

A first acceptance and an idempotent re-acceptance are indistinguishable to the client: the service
answers both with the same `202` and the same acknowledgement fields, computed from the submitted
request rather than from stored state. `accepted` therefore means "the service holds this scan", not
"the service stored it just now". DMI-66 must not try to tell the two apart.

Automated hardware-agent tests use `httpx.MockTransport` to cover the same bytes, headers, retries,
and response mappings without importing backend code or requiring a database. Existing DMI-63
backend tests remain the authority for verification and persistence semantics.

## Explicitly deferred

- DMI-66 decides when the daemon invokes the client and how outcomes map to WebSocket command
  statuses.
- The daemon unit must not start the client before system time is synchronised (systemd
  `After=time-sync.target`). The device has no battery-backed clock, so a freshly booted Pi can sign
  a proof the service considers stale. DMI-65 has no clock-correction behaviour and treats the
  resulting `401` like any other rejected proof.
- Provisioning decides how the production private key is generated and placed in the environment.
- CPE propagation from scanner models into the normalized port payload requires a separate scope
  decision; the backend currently accepts its absence.

