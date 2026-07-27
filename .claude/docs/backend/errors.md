---
type: Module
title: Backend API error envelope
description: ApiError(HTTPException) with per-site code overrides and the global handlers that wrap every HTTPException and unhandled Exception into the contract ErrorResponse shape.
resource: backend/src/api/errors.py
tags: [backend, errors, fastapi, contract, envelope]
timestamp: 2026-07-27T21:00:00Z
---

# Backend API error envelope

## Purpose

`errors.py` is the single place the backend defines how API failures are shaped on the wire.
`ApiError` subclasses `HTTPException` and carries an explicit `code` string for the few routes
that need a machine-readable discriminator beyond the HTTP status (today: change-password only).
Everything else keeps raising bare `HTTPException` and gets a status-derived default code from
`DEFAULT_CODES_BY_STATUS`. The global handlers in [`main.py`](/backend/api.md) turn both into
`{"error": {"code", "message", "details": {}}}` — matching `contracts/openapi/openapi.yaml`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ApiError` | `HTTPException` subclass; `__init__(status_code, detail, *, code)` sets `self.code`. No `details` parameter — nothing raises with one. | `backend/src/api/errors.py:21` |
| `DEFAULT_CODES_BY_STATUS` | Maps 400/401/403/404/405/410 → `bad_request`/`unauthorized`/`forbidden`/`not_found`/`method_not_allowed`/`gone`; unknown statuses fall back to `"error"`. | `backend/src/api/errors.py:7` |
| `error_envelope` | Builds the three-key body. Single source of the shape for all four handlers. | `backend/src/api/errors.py:27` |
| `field_path` | `("body", "hosts", 0, "ip")` → `"hosts[0].ip"` for 422 `details.field`; drops the leading location segment. | `backend/src/api/errors.py:33` |
| `http_exception_handler` | Registered on `starlette.exceptions.HTTPException` (not FastAPI's subclass) so Starlette-router 404/405 are enveloped too. Uses `exc.code` for `ApiError`, else the default map. Passes `exc.headers` through. | `backend/src/api/main.py:46` |
| `validation_exception_handler` | `@app.exception_handler(RequestValidationError)` → `422` / `validation_error` with `details.field` from the first error. Fixed message; never echoes `input`/`ctx`. | `backend/src/api/main.py:71` |
| `unhandled_exception_handler` | `@app.exception_handler(Exception)` → fixed `500` / `internal_server_error` body; never leaks `str(exc)`. | `backend/src/api/main.py:87` |
| `ws_validation_denial` | Pre-accept WS path validation → HTTP 403 denial with the same envelope (malformed `{agent_id}`), fixed message. | `backend/src/api/main.py:103` |

## How it connects

- **Upstream** — every router and dependency that raises `HTTPException` or `ApiError` flows
  through `http_exception_handler`; WebSocket upgrade auth denials from
  [`require_agent_ws`](/backend/device-auth.md) use the same handler.
- **Downstream** — the SPA and contract consumers read `error.code`; C13 change-password uses
  `wrong_current_password` / `password_policy_violation` at **400** (never 401) — see
  [auth](/backend/auth.md).
- **Explicit override call site** — `change_password_route` in `routers/auth.py` only; reset/accept
  invite codes are deferred to DMI-77.

## Notes / gotchas

- Register on **Starlette's** `HTTPException` base class — registering on `fastapi.HTTPException`
  alone would leave router-raised 404/405 as bare `{"detail": ...}`.
- `GET /api/v1/health` builds its own `503 database_unreachable` `JSONResponse` and never raises —
  the global handler does not double-wrap it.
- **`http_exception_handler` must pass `exc.headers` through.** Starlette's router raises `405`
  with an `Allow` header (RFC 9110 requires it) and FastAPI's default handler propagated it;
  building a bare `JSONResponse` silently drops it. Pinned by
  `test_wrong_method_returns_method_not_allowed_envelope`.
- **The 422 body is fixed and must stay that way.** Pydantic's `errors()` carries `input` — the
  rejected value verbatim — so echoing it leaks the submitted password on the `min_length`
  rejection for change-password / reset-password. For the same reason the raw errors are **not
  logged**: the log file is not a safer home for a plaintext password than the response body.
  Pinned by `test_validation_failure_does_not_echo_submitted_password`.
- `details` is `{}` everywhere except `422`, which carries `{"field": ...}` for the first error
  only. DMI-77 may add more.

# Citations

[1] [specs/019-users-me-and-error-envelope](../../../specs/019-users-me-and-error-envelope/TRUTH.md)
[2] [contracts/openapi/openapi.yaml](../../../contracts/openapi/openapi.yaml)
