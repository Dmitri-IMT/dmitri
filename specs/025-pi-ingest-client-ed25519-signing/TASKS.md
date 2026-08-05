# TASKS — Pi ingest client and Ed25519 signing (DMI-65)

Layer: `hardware-agent/` only. Agents: `agent-developer` → `test-engineer` → `code-reviewer`.
Gate: from `hardware-agent/`, `uv run pytest` and `uv run ruff check src tests`.
Never run a repo-wide formatter.

Specs: `specs/025-pi-ingest-client-ed25519-signing/TRUTH.md`, `ARCHITECTURE.md`, `INTEGRATION.md`.

## Dependency graph

```text
Task 1 ──> Task 2 ──> Task 3
```

## Task 1: Transport package, dependencies, and configuration boundary
- **Description**: Add `httpx>=0.27.0` and `cryptography>=42.0` as direct hardware-agent runtime
  dependencies and regenerate `uv.lock` for the hardware-agent graph only. Create the
  `agent.transport` package exporting the six public names from ARCHITECTURE.md "One transport
  module". Implement `IngestConfig` (immutable, `repr=False` on decoded key bytes),
  `IngestConfigError`, and `load_ingest_config(environ: Mapping[str, str] | None = None)` per the
  configuration table: `BACKEND_URL` (http/https origin, optional trailing slash, no credentials,
  query, fragment or non-root path), `DEVICE_ID` (UUID), `DEVICE_PRIVATE_KEY` (64 hex chars →
  32-byte Ed25519 seed). Errors name only the variable and expected shape. `SubmissionOutcome`,
  `SubmissionResult`, and a not-yet-wired `ScanIngestClient` skeleton with the fixed constructor
  signature may be stubbed here only to satisfy the exports; behavior lands in Tasks 2–3.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/pyproject.toml`, `hardware-agent/uv.lock`,
  `hardware-agent/src/agent/transport/__init__.py`,
  `hardware-agent/src/agent/transport/ingest.py`]
- **Success Criteria**:
  - `from agent.transport import IngestConfig, IngestConfigError, SubmissionOutcome, SubmissionResult, ScanIngestClient, load_ingest_config` succeeds.
  - `load_ingest_config` reads a supplied mapping or the process environment; every missing or
    malformed variable raises `IngestConfigError` before any I/O.
  - Invalid `BACKEND_URL` forms rejected: non-http(s) scheme, embedded credentials, query,
    fragment, non-root path. `http://127.0.0.1:8000` and a trailing slash are accepted.
  - `DEVICE_PRIVATE_KEY` accepts exactly 64 hex characters and decodes to 32 bytes; anything else
    raises `IngestConfigError`.
  - No error message, `repr`, or `str` of `IngestConfig`/`IngestConfigError` contains the private
    key hex, decoded key bytes, or any supplied value.
  - `SubmissionOutcome` is the `Literal` with exactly: `accepted`, `unauthorized`, `forbidden`,
    `invalid`, `rejected`, `unavailable`, `protocol_error`.
  - `SubmissionResult` is an immutable slotted dataclass with `outcome`, `scan_id`, `attempts`,
    `status_code`, `message`.
  - Tests in `hardware-agent/tests/unit/test_ingest_config.py`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Signed request construction and accepted-response validation
- **Description**: Implement `ScanIngestClient(config, *, client: httpx.Client | None = None)` with
  `close()` and the context-manager protocol (an injected client is used as given and not closed;
  an owned client is), redirects disabled, and the fixed per-attempt timeouts (connect 10 s,
  write 60 s, read 120 s, pool 10 s). Implement `submit(payload: ScanPayload, *, scan_id: UUID |
  None = None)` for the single-attempt success path: compute the effective payload
  (`model_copy(update=...)` for an override, never mutating the caller's model), serialize once
  with `model_dump_json()` UTF-8-encoded, send with `content=body` (never `json=`), and build the
  envelope exactly as ARCHITECTURE.md "Exact body and signature construction" specifies. Validate a
  `202` against `ScanIngestAcceptedResponse` shape: `status == "accepted"`, `scan_id` equals the
  effective submitted id, `hosts_received` equals the submitted host count; a malformed or
  contradictory `202` is `protocol_error`.
- **Dependencies**: Task 1
- **Target Files**: [`hardware-agent/src/agent/transport/ingest.py`,
  `hardware-agent/src/agent/transport/__init__.py`]
- **Success Criteria**:
  - Request is `POST {BACKEND_URL}/api/v1/scans` with `Content-Type: application/json` and headers
    `X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Body-SHA256`, `X-Signature`.
  - Capturing the raw transmitted bytes via `httpx.MockTransport`: SHA-256 of those exact bytes
    equals `X-Body-SHA256` (lowercase hex); the canonical string
    `POST\n/api/v1/scans\n{device_id}\n{timestamp}\n{nonce}\n{body_sha256}` with no trailing newline
    verifies against `X-Signature` (lowercase hex) using the matching Ed25519 public key.
  - `X-Timestamp` is UTC ISO-8601 with an offset; `X-Nonce` is 32 hex characters.
  - No override → body carries the payload's existing `scan_id`. With an override → body carries the
    assigned id while the caller's in-memory `ScanPayload` is unchanged and no file is written or
    read by the client.
  - Valid `202` returns `SubmissionResult(outcome="accepted", ...)` with the effective `scan_id`,
    `attempts == 1`, `status_code == 202`.
  - A `202` whose `status`, `scan_id`, or `hosts_received` does not match returns `protocol_error`
    with exactly one request made.
  - Redirects are not followed; a redirect response returns `protocol_error`.
  - Injected client is not closed by `close()`; an owned client is.
  - Tests in `hardware-agent/tests/unit/test_ingest_client.py`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Error mapping, bounded retry, and secret-safe diagnostics
- **Description**: Implement the full response/error mapping table and the fixed retry policy:
  three total attempts, delays of 0.25 s and 1 s before attempts two and three, retrying only
  `httpx.TransportError` and HTTP `5xx`, rebuilding timestamp, nonce, canonical string, and
  signature for every attempt while reusing the identical body bytes. Map `401` →
  `unauthorized`, `403` → `forbidden`, `413`/`422` → `invalid`, `400` and other `4xx` →
  `rejected`, exhausted transient failures → `unavailable`, unexpected `2xx`/redirect/malformed
  `202` → `protocol_error`. Build `SubmissionResult.message` from a fixed outcome-to-text mapping
  plus the numeric status code, with nothing interpolated from the response, configuration, or
  exception. No client-side payload revalidation, no pre-flight schema check.
- **Dependencies**: Task 2
- **Target Files**: [`hardware-agent/src/agent/transport/ingest.py`]
- **Success Criteria**:
  - `401`, `403`, `400`, `413`, `422`, and an unexpected `4xx` each make exactly one request and map
    to `unauthorized`, `forbidden`, `rejected`, `invalid`, `invalid`, `rejected` respectively.
  - A transport failure or `5xx` followed by a valid `202` returns `accepted` with `attempts == 2`;
    captured headers prove `X-Timestamp`, `X-Nonce`, and `X-Signature` differ between attempts while
    the body bytes are byte-identical.
  - Three consecutive transient failures return `unavailable` with exactly three requests and no
    fourth.
  - Submitting the same payload twice builds fresh envelopes and returns `accepted` for both, with
    no client-side mutation of the payload.
  - No `SubmissionResult.message` contains any response body text, the configuration values, the
    private-key hex, or a signature; messages vary only by outcome and status code.
  - Expected HTTP and network failures return a `SubmissionResult` and never call `sys.exit`, print,
    or log secrets.
  - Reviewer re-runs `rg -n "ScanRunner\(|run_headless_scan\(|ScanProgressScreen\("` and confirms no
    call site needs a new argument, and that no backend, contract, frontend, TUI, scanner,
    normalization, result-writer, CLI, or documentation file was changed.
  - Tests in `hardware-agent/tests/unit/test_ingest_client.py`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Status table

| Task | Name | Status | Rejections |
|---|---|---|---|
| 1 | Transport package, dependencies, and configuration boundary | COMPLETED | 0 |
| 2 | Signed request construction and accepted-response validation | COMPLETED | 0 |
| 3 | Error mapping, bounded retry, and secret-safe diagnostics | COMPLETED | 0 |
