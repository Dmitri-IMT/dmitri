---
type: Entry Point
title: Backend entry points & config
description: The FastAPI app (health, read, auth, user/invite admin, command-channel HTTP/WS, global errors), the worker entry, settings, and DB sessions.
resource: backend/src/api/main.py
tags: [backend, entrypoint, fastapi, config, database, websocket]
timestamp: 2026-09-13T16:40:00Z
---

# Backend entry points & config

## Purpose

The four files that boot and configure the backend: the FastAPI **API** process (`main.py`), the
**worker** process (`worker_main.py`), the pydantic-settings configuration (`core/config.py`), and
the SQLAlchemy engine/session factory (`db/session.py`). Together they define how each process
starts, how it is configured from the environment, and how it reaches Postgres.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `app` | The `FastAPI` instance with generated OpenAPI/Swagger/ReDoc disabled; the published hand-authored contract is authoritative. Mounts read, home, auth, users, invites, command, and ingest routers plus global errors and middleware. | `backend/src/api/main.py:46` |
| `app.add_middleware(NoContentCorsMiddleware / RequestIdMiddleware)` | Registers the 204-preflight CORS middleware (built from `CORS_ALLOWED_ORIGINS`) and the `X-Request-Id` middleware — see [auth](/backend/auth.md). | `backend/src/api/main.py:32` |
| `options_health()` | `OPTIONS /api/v1/health` → 204, so a real browser preflight is answered by the CORS middleware. | `backend/src/api/main.py:54` |
| `http_exception_handler()` | `@app.exception_handler(StarletteHTTPException)` — wraps every `HTTPException`/`ApiError` into `{"error": {code, message, details:{}}}`; forwards `exc.headers` so the router's `405` keeps its `Allow`. | `backend/src/api/main.py:46` |
| `validation_exception_handler()` | `@app.exception_handler(RequestValidationError)` — `422` / `validation_error` with `details.field`; fixed message, never echoes the rejected `input`. | `backend/src/api/main.py:71` |
| `unhandled_exception_handler()` | `@app.exception_handler(Exception)` — fixed `500` / `internal_server_error`; no exception text in the body. | `backend/src/api/main.py:87` |
| `app.include_router(auth.router)` | Wires the six auth POST routes and their preflights. | `backend/src/api/main.py:152` |
| `app.include_router(users.router)` | Wires self profile/removal plus admin member list, role change, and member removal. | `backend/src/api/main.py:153` |
| `app.include_router(invites.router)` | Wires admin invite create/list/revoke plus public accept/lookup. | `backend/src/api/main.py:157` |
| `get_settings()` (import-time call) | Called at module import so missing/invalid required configuration fails fast at startup. | `backend/src/api/main.py:34` |
| `read_health()` | `GET /api/v1/health`; runs `SELECT 1` and returns status/version or the fixed 503 envelope. | `backend/src/api/main.py:131` |
| `app.include_router(hosts.router / scans.router / findings.router)` | Wires host/scan/finding reads plus signed scan ingest. | `backend/src/api/main.py:154` |
| `app.include_router(agents.router / commands.router)` | Wires the agent list/detail/target-subnet routes and command enqueue/read plus the agent WebSocket channel. | `backend/src/api/main.py:150` |
| lifespan startup → `reconcile_all(session)` | Clears every `agents.connected_at` at boot, so a hard-crashed API (where the WS `finally` never ran) does not leave agents looking permanently connected to the worker's sweeper. See [services](/backend/services.md). | `backend/src/api/main.py:39` |
| `ws_validation_denial()` | `WebSocketRequestValidationError` handler — pre-accept HTTP **403** with the [error envelope](/backend/errors.md) for malformed `{agent_id}` (non-UUID path segment) via `send_denial_response`. | `backend/src/api/main.py:103` |
| `main()` | Worker process entry. Configures INFO logging; if `ai_is_available`, starts `run_ai_worker_loop` in a daemon thread; then `run_worker_loop()`. Run as `python -m api.worker_main` or `backend-worker`. | `backend/src/api/worker_main.py:12` |
| `Settings` | pydantic-settings `BaseSettings` (env + `.env`, `extra="ignore"`). Fields: `database_url` (`SecretStr`, validated to a Postgres URL), optional **AI** (`ai_enabled` default false, `ai_api_key`, `ai_model`, `ai_api_base_url`, `ai_max_findings`, `ai_timeout_seconds`, `ai_max_output_tokens`, `ai_reasoning_effort`, `ai_max_attempts`, `ai_retry_delay_seconds`, `ai_poll_interval_seconds`; no `AI_PROVIDER`), the KEV/EPSS/NVD base URLs + cache TTLs, optional `nvd_api_key`, `nvd_min_request_interval_seconds` (6), enrichment poll/batch/retry knobs, and the **auth knobs**: `jwt_signing_secret` (`SecretStr`, **required**), `access_token_ttl_minutes` (15), `refresh_token_ttl_days` (7), `refresh_cookie_secure` (true), `cors_allowed_origins` (**empty by default**, so browsers fail closed until a deployment supplies an allowlist), `reset_token_ttl_minutes` (60), `hibp_enabled` (true), `hibp_timeout_seconds` (2), plus the device/invite knobs `device_sig_max_skew_seconds` (300) and `invite_ttl_hours` (48), the command-channel knob `command_disconnect_grace_seconds` (900), and the mail/link knobs `resend_api_key`, `resend_api_base_url`, `mail_from`, `mail_reply_to`, `mail_timeout_seconds` (10.0) and `app_base_url`. | `backend/src/api/core/config.py:22` |
| `normalize_postgres_url()` | Rewrites any accepted Postgres scheme to `postgresql+psycopg://`; **rejects** unknown schemes (no SQLite). Used by both config validation and the engine. | `backend/src/api/core/config.py:16` |
| `get_settings()` | `lru_cache`d `Settings` accessor (singleton). | `backend/src/api/core/config.py:98` |
| `Severity` / `SEVERITY_ORDER` | The severity domain and its `low→1 … critical→4` ranking, derived from the literal's declaration order. Dependency-free on purpose: it sits in `core/` so [models](/backend/models.md) can spell the `findings.severity` check constraint without importing the schema layer above them. Read by `services/hosts.py` (host ranking), `services/read.py` (scan-list rank), `routers/findings.py` (the `severity` query param) and `schemas/read.py`. Moved here from `schemas/read.py` on 2026-07-31. | `backend/src/api/core/severity.py:5` |
| `ScanErrorCode` / `normalise_error_code` / `scan_error_code` | The closed eight-code failure vocabulary and the two pure read helpers. Same leaf reason as `Severity`: `schemas/read.py` and `schemas/commands.py` must not import each other. Full map in [error-codes](/backend/error-codes.md). | `backend/src/api/core/error_codes.py:5` |
| `MachineType` / `MACHINE_TYPES` / `classify_machine_type()` | Closed nine-value machine-type vocabulary (`router`…`unknown`) and a pure classifier: service signals first (fixed priority), then vendor signals; `vendor == "unknown"` matches nothing. No I/O. Read by [inventory](/backend/services.md) and re-exported on the read schemas. | `backend/src/api/core/machine_type.py:5` |
| `get_engine()` | `lru_cache`d engine from the normalized `DATABASE_URL`, with `pool_pre_ping=True` and `connect_args={"prepare_threshold": None, "connect_timeout": 10}` — required for the pgbouncer/Supabase pooler. | `backend/src/api/db/session.py:11` |
| `get_session()` | Generator yielding a `Session` in a context manager; the FastAPI dependency and the worker's session source. | `backend/src/api/db/session.py:22` |
| `reset_db_state()` | Test helper clearing the engine + settings caches. | `backend/src/api/db/session.py:27` |

## How it connects

- `read_health` and each router route depend on `get_session`, which yields sessions bound to the
  `get_engine` engine built from `Settings` — all four files in this doc form the boot chain.
- The [routers](/backend/routers.md) call straight into [`services/read.py`](/backend/services.md);
  no other layer sits between `main.py` and the DB for the read path.
- The worker entry starts [AI](/backend/ai.md) in a thread when configured, then
  `run_worker_loop()` in [services](/backend/services.md).
- `command_disconnect_grace_seconds` is read by `sweep_stale_commands`. There is deliberately **no**
  duration-based timeout setting: D11/D12 replaced that design with connection-loss detection, and the
  vestigial `command_running_timeout_seconds` was deleted once it was found to have no consumer.
- `Settings` cache TTLs and the poll interval/batch size are consumed by the enrichment
  [services](/backend/services.md) (NVD/KEV/EPSS clients and the worker loop).
- `normalize_postgres_url` is reused by the Alembic env — see [migrations](/backend/migrations.md).

## Notes / gotchas

- **Read, auth, identity administration, command channel, and ingest are wired.** In addition to
  `/users/me` and invite create/accept/lookup, the users router now serves admin member list and
  role change, while the invites router serves pending-list and revoke. All are registered through
  the existing router includes in `main.py`.
- **Both device transports are mounted and both ends exist.** WS denials use the error envelope;
  `require_agent_ws` gates the socket and `require_agent` gates ingest. The remaining gap is
  physical/operational provisioning, so tests use fake sockets and signed requests.
- **`websockets>=13` is a direct dependency** (not `uvicorn[standard]`) so uvicorn can serve WS
  upgrades in production with the sans-io protocol implementation.
- **`JWT_SIGNING_SECRET` is required** — `Settings()` (instantiated at import) fails fast without it;
  `conftest.py` sets it for the test suite. The two DMI-61 additions
  (`DEVICE_SIG_MAX_SKEW_SECONDS`, `INVITE_TTL_HOURS`) are plain optional fields with defaults — no
  validator, no required secret, and deliberately **no** nonce-retention knob. `RESEND_API_KEY` is
  the same shape: unset is a supported production state, not a boot failure — the backend falls back
  to `NullMailer` and invites/resets keep working off their returned link (see
  [auth](/backend/auth.md)).
- **CORS fails closed when unset.** `cors_allowed_origins` defaults to the empty string, which
  `build_cors_middleware_kwargs()` turns into `allow_origins=[]`. Local development and every
  deployment must supply the exact browser origins it trusts; the old localhost and placeholder
  production defaults were removed.
- Disabling `openapi_url` means FastAPI serves **no** generated schema; the hand-authored
  `contracts/openapi/openapi.yaml` is authoritative.
- The worker uses `time.sleep`, not FastAPI — it never imports `app`.

# Citations

[1] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[2] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[3] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
