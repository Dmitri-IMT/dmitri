# ARCHITECTURE — Pi ingest client and Ed25519 signing

## System context

DMI-51 already exposes the scan pipeline programmatically and writes normalized results to disk.
DMI-63 already exposes `POST /api/v1/scans`, verifies the ADR-005 Ed25519 envelope, consumes the
nonce before route work, and persists both standalone and command-assigned scans. Both Linear
blockers are Done.

This feature fills only the device-side boundary between those completed pieces. It adds a
synchronous, reusable ingest client under `hardware-agent/src/agent/transport/`. The future DMI-66
daemon will call it after `run_headless_scan()` returns a payload and a durable result path. This
feature does not call it automatically from the CLI or TUI.

The resulting flow is:

```text
ScanRunner → ScanPayload → write_scan_result → durable local JSON
                                  ↓
                         ScanIngestClient.submit
                                  ↓
                 signed POST /api/v1/scans → backend
```

No `ScanRunner` argument, scan stage, TUI screen, CLI exit code, or result-writer behavior changes.

## Architecture decisions

### One transport module

Create `agent.transport.ingest` containing the configuration parser, Ed25519 request builder,
HTTP client, response validator, and typed result. These pieces have one consumer boundary and do
not justify separate signer/retry/config packages.

Use the same direct dependencies as the backend:

- `httpx>=0.27.0` for a synchronous client and `MockTransport` tests.
- `cryptography>=42.0` for `Ed25519PrivateKey.from_private_bytes()` and signing.

`cryptography` is unavoidable: the standard library has no Ed25519. `httpx` is a deliberate choice
over `urllib.request` despite its transitive dependencies, and this is settled — do not re-open it
during implementation. It does not follow redirects by default, which makes the signed-path
guarantee a default rather than a custom redirect handler; it separates connect and read timeouts;
and `MockTransport` exposes the exact transmitted bytes, which every signature and retry test below
depends on.

The public names exported from `agent.transport` are:

```python
IngestConfig
IngestConfigError
SubmissionOutcome
SubmissionResult
ScanIngestClient
load_ingest_config
```

`SubmissionOutcome` is a `Literal` with these values:

```text
accepted | unauthorized | forbidden | invalid | rejected | unavailable | protocol_error
```

`SubmissionResult` is an immutable slotted dataclass carrying `outcome`, effective `scan_id`,
`attempts`, `status_code`, and a secret-safe `message`. Expected HTTP and network failures return a
result; they do not call `sys.exit`, print, or expose raw response bodies. Invalid local
configuration raises `IngestConfigError` before an HTTP request is attempted.

`ScanIngestClient` owns one synchronous `httpx.Client` unless a client is injected for tests. It
implements `close()` and the context-manager protocol. Redirect following is disabled because a
redirect changes the signed path. Its constructor is fixed as:

```python
ScanIngestClient(config: IngestConfig, *, client: httpx.Client | None = None)
```

An injected client is used as given and is not closed by `close()`; an owned client is. This is the
only injection seam, and the mandated tests use it with `httpx.MockTransport`.

### Configuration boundary

`load_ingest_config(environ: Mapping[str, str] | None = None)` reads the process environment. A
later systemd unit may populate that environment from `/etc/dmitri/agent.env`; this feature does not
open or parse that file.

| Variable | Accepted form | Validation |
|---|---|---|
| `BACKEND_URL` | API origin, with an optional trailing slash | `http` or `https`; no credentials, query, fragment, or non-root path |
| `DEVICE_ID` | UUID string | Parsed once as `UUID` |
| `DEVICE_PRIVATE_KEY` | 64 hexadecimal characters | Decodes to the 32-byte Ed25519 private seed emitted by the existing local provisioning command |

`IngestConfig` stores decoded key bytes with `repr=False`. Configuration errors name only the
variable and expected shape, never its value. HTTP remains allowed for local development; deployed
environments are responsible for supplying an HTTPS origin per ADR-005.

Retry policy is intentionally fixed rather than exposed as more device configuration:

- three total attempts;
- per-attempt timeouts of connect 10 s, write 60 s, read 120 s, pool 10 s;
- delays of 0.25 seconds and 1 second before attempts two and three;
- retry only `httpx.TransportError` and HTTP `5xx`.

The read timeout is deliberately generous rather than a flat 30 seconds. Backend ingest costs one
database round trip per host, per port, and per finding, so a large result can legitimately hold the
connection open for a long time. A read timeout is a `TransportError` and is therefore retried,
which means a premature one can put attempt two on the wire while attempt one is still inside its
transaction — before the backend's completed-scan idempotency can absorb it. Sizing the read
timeout so that it fires only when the service is genuinely wedged keeps that window closed without
adding a special case to the retry rules.

### Exact body and signature construction

`submit(payload: ScanPayload, *, scan_id: UUID | None = None)` computes the effective payload once:

1. With no override, use `payload` unchanged.
2. With an override, use `payload.model_copy(update={"scan_id": scan_id})` only for serialization.
   Do not mutate the caller's model or rewrite its artifact.
3. Serialize once with `model_dump_json()` and UTF-8 encode it. The resulting byte string is reused
   for every attempt.
4. Send it with `content=body`, never `json=...`, so the digest and transmitted bytes cannot diverge.

Inside the retry loop, rebuild the complete authentication envelope for every attempt:

```text
method       = POST
path         = /api/v1/scans
device_id    = canonical UUID text
timestamp    = current UTC ISO-8601 text with an offset
nonce        = secrets.token_hex(16)
body_sha256  = lowercase SHA-256 hex of the serialized bytes
canonical    = POST\n/api/v1/scans\n{device_id}\n{timestamp}\n{nonce}\n{body_sha256}
signature    = lowercase hex Ed25519 signature of canonical UTF-8 bytes
```

The request sends `Content-Type: application/json` plus `X-Device-Id`, `X-Timestamp`, `X-Nonce`,
`X-Body-SHA256`, and `X-Signature`. The body may be reused, but timestamp, nonce, canonical string,
and signature must be regenerated after every failed attempt. This is required because the backend
durably burns a verified nonce before route persistence and may then return `5xx`.

### Response validation and error mapping

A successful request is exactly HTTP `202` with JSON matching the existing
`ScanIngestAcceptedResponse`: `status == "accepted"`, `scan_id` equals the effective submitted id,
and `hosts_received` equals the submitted host count. A malformed or contradictory `202` is
`protocol_error`, not success.

| Condition | Outcome | Retry |
|---|---|---|
| Valid `202` acknowledgement | `accepted` | No |
| `401` | `unauthorized` | No |
| `403` | `forbidden` | No |
| `413` or `422` | `invalid` | No |
| `400` or another `4xx` | `rejected` | No |
| `5xx` or `httpx.TransportError`, attempts remain | Continue | Yes, with a fresh envelope |
| `5xx` or transport failure on attempt three | `unavailable` | No |
| Redirect, unexpected `2xx`, malformed `202`, or invalid acknowledgement | `protocol_error` | No |

Response bodies are not copied into diagnostic messages. Status code and stable category text are
enough for the future daemon to report failure without leaking credentials or server internals.

`SubmissionResult.message` is built from a fixed outcome-to-text mapping plus the numeric status
code, with nothing interpolated from the response, the configuration, or the exception. That is what
makes "stable" and "secret-safe" reviewable: the message cannot vary with server content, so the
secret-safety tests do not have to enumerate every possible backend reply. Callers branch on
`outcome`, never on `message`.

### Artifact ownership

The transport client accepts an in-memory `ScanPayload`, not an artifact path, and performs no file
operations. Its caller must persist first. DMI-66 must therefore call the client only after a
headless result includes both `payload` and `result_path`. Success and failure leave the artifact
byte-for-byte untouched. A backend-assigned id changes only the submitted copy, so the same artifact
can be retried later by supplying the id again.

### CPE handoff discrepancy

`specs/024-scan-ingest-endpoint/ARCHITECTURE.md` assigns adding port CPEs to DMI-65, but the Linear
issue and this feature's `TRUTH.md` explicitly exclude normalization and output-format changes. The
backend's `cpes` field is optional with an empty default, so the ingest client is not blocked by the
current hardware payload.

This plan follows the approved DMI-65 boundary: do not touch `normalize/contracts.py`,
`scanner/models.py`, or `scanner/stages.py`. CPE propagation needs a separate issue/spec or an
explicit DMI-65 scope amendment before implementation.

### No client-side payload revalidation

The agent's `ScanPayload` and the backend's `ScanIngestRequest` were compared field by field and are
compatible by construction: identical field names, and every field the backend requires is always
emitted by `model_dump_json()` even where the agent model supplies a default. The backend's
`extra="forbid"` tolerates the agent's missing `cpes` because that field defaults to an empty list.

The client therefore does not re-validate the payload before sending, and must not grow a
pre-flight schema check. A `422` from the service means the two model sets have genuinely drifted
apart — a deploy-skew signal worth surfacing, not something the client should mask.

## Call-path audit

No runner parameter is introduced, so the repository integration rule requires verification but no
threading edits.

| Constructor/call path | Disposition |
|---|---|
| `hardware-agent/src/agent/headless.py` → `ScanRunner(...)` | Unchanged; returns payload and durable result path for the future daemon |
| `hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`) → `ScanRunner(...)` | Unchanged; no TUI upload |
| Direct `ScanRunner(...)` construction in hardware-agent unit tests | Unchanged; constructor signature is untouched |
| `hardware-agent/src/agent/cli.py` → `run_headless_scan(...)` | Unchanged; no new CLI flags, output, or exit code |

Implementation review must repeat `rg -n "ScanRunner\\(|run_headless_scan\\(|ScanProgressScreen\\("`
before completion and confirm no call site needs a new argument.

## New files and naming (mandatory)

| Action | Path | Exact responsibility |
|---|---|---|
| Create | `hardware-agent/src/agent/transport/__init__.py` | Export the six public ingest names; no logic |
| Create | `hardware-agent/src/agent/transport/ingest.py` | `IngestConfig`, safe env parsing, request serialization/signing, `ScanIngestClient`, fixed retries, acknowledgement validation, and typed results |
| Modify | `hardware-agent/pyproject.toml` | Add direct `httpx>=0.27.0` and `cryptography>=42.0` runtime dependencies |
| Regenerate | `hardware-agent/uv.lock` | Lock only the hardware-agent dependency graph after the two direct additions |
| Create | `hardware-agent/tests/unit/test_ingest_config.py` | Environment parsing, URL/UUID/key validation, and secret-safe failures |
| Create | `hardware-agent/tests/unit/test_ingest_client.py` | Raw-byte signature, response mapping, retry, id override, idempotent resubmission, and artifact-retention tests with `httpx.MockTransport` |

No backend, contract, frontend, TUI, scanner, normalization, result-writer, CLI, or documentation
file is changed by implementation.

## Constraints

- No application-side key generation, provisioning, registration, or rotation.
- No daemon, WebSocket, command-state, service-manager, or background queue behavior.
- No automatic upload from `run_headless_scan`, `ScanRunner`, `ScanProgressScreen`, or the CLI.
- No payload-format or OpenAPI changes; `contracts/openapi/openapi.yaml` is consumed as frozen.
- No retry of authentication, authorization, validation, or other client errors.
- No redirect following and no signing a URL different from the transmitted path.
- No secret-bearing dataclass representation, exception text, result message, print, or log.
- No new infrastructure is required to implement or unit-test this feature. A real local-backend
  smoke test uses the existing backend/database setup.

## Testing expectations

| Area | File | Acceptance coverage |
|---|---|---|
| Configuration | `hardware-agent/tests/unit/test_ingest_config.py` | Missing/malformed variables fail before I/O; valid 32-byte hex seed loads; error text excludes supplied values and decoded key bytes |
| Signed request | `hardware-agent/tests/unit/test_ingest_client.py` | Capture the raw body, recompute its SHA-256, reconstruct the canonical string, and verify the hex signature with the matching public key |
| Accepted result | `hardware-agent/tests/unit/test_ingest_client.py` | Valid `202` returns `accepted`; acknowledgement id and host count are validated |
| Scan-id selection | `hardware-agent/tests/unit/test_ingest_client.py` | No override sends the payload id; an override sends the assigned id without changing the original model or artifact bytes |
| Non-retryable failures | `hardware-agent/tests/unit/test_ingest_client.py` | `401`, `403`, `400`, `413`, `422`, unexpected `4xx`, redirect, and malformed `202` each make one request and map to the specified outcome |
| Transient retries | `hardware-agent/tests/unit/test_ingest_client.py` | Transport failure and `5xx` retry at most three total attempts; captured headers prove a new nonce and signature per attempt; success after a transient failure returns `accepted` |
| Exhaustion | `hardware-agent/tests/unit/test_ingest_client.py` | Three transient failures return `unavailable`, with no fourth request |
| Safe resubmission | `hardware-agent/tests/unit/test_ingest_client.py` | Submitting the same payload twice builds fresh envelopes and accepts both acknowledgements without client-side mutation |
| Secret safety | Both test files | Neither result messages nor raised configuration errors contain the private-key text or signature |
| Local boundary smoke test | Manual, documented in `INTEGRATION.md` | Existing local backend accepts and persists a request from the client while the artifact checksum remains unchanged |

Run only the hardware-agent gates from `hardware-agent/`:

```text
uv run pytest
uv run ruff check src tests
```

Do not run a repository-wide formatter. Formatting remains the existing hardware-agent pre-push
hook responsibility.

Note that the root `pyproject.toml` sets `extend-exclude = ["hardware-agent/tests"]` for both ruff
and black, and hardware-agent has no ruff configuration of its own. `ruff check src tests` therefore
lints `src` only; the two new test files are not linted by that gate today. This is pre-existing
repository configuration and this feature does not change it — do not add a hardware-agent ruff
section to "fix" it. `uv run pytest` is the real gate for the test files.

