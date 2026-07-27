# Tasks — `GET /users/me` + global error envelope (`019-users-me-and-error-envelope`)

9 tasks. **Unblocked now: #1, #6**

Backend + contract feature (`backend/src/api/…`, `contracts/openapi/openapi.yaml`). No
`hardware-agent/`, `scanner/`, or `tui/` files are touched, so the CLAUDE.md `ScanRunner` /
`ScanProgressScreen` thread-through rule is **N/A** here (`ARCHITECTURE.md` opening section).

Two ordering facts that make this safe to land in one PR, both verified during spec refinement:

- **No backend test asserts on a `detail` body** (`grep '"detail"' backend/tests/` returns
  nothing), and no hand-written frontend code reads `detail` or `error.code`
  (`INTEGRATION.md`). Changing the error body shape app-wide regresses no existing consumer.
- **Tasks 2, 3, 4 and 7 all touch `backend/src/api/main.py`.** They are chained sequentially
  rather than run in parallel so the orchestrator never has two agents editing that file.

**Status codes must not change anywhere** (`ARCHITECTURE.md` Constraints). Every task inherits
that constraint; any task whose diff changes a status code is a reject.

Out of scope, do not build: 422 request-validation envelope, reset-password / accept-invite
error codes (DMI-77), profile editing, password expiry, user management, any frontend runtime
code (`TRUTH.md` "Out of scope (v1)", `INTEGRATION.md` "What does not ship").

---

## Task 1: `ApiError` and the status→code default map
- **Description**: Create `backend/src/api/errors.py` per the ARCHITECTURE.md "Error envelope" section: an `ApiError(HTTPException)` subclass carrying a `code`, plus the module-level `_DEFAULT_CODES_BY_STATUS` map. `ApiError` deliberately has **no `details` parameter** — nothing in this feature populates it (CLAUDE.md §2); DMI-77 or the 422 follow-up adds it when it has a value to put there. Because `ApiError` subclasses `HTTPException`, it needs no separate handler registration.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/errors.py`]
- **Success Criteria**:
  - `ApiError.__init__(self, status_code, detail, *, code)` — keyword-only `code`, **no `details` parameter**, calls `super().__init__(status_code=..., detail=...)` and sets `self.code`.
  - `ApiError` is a subclass of `fastapi.HTTPException` (and therefore of `starlette.exceptions.HTTPException`).
  - `_DEFAULT_CODES_BY_STATUS` maps exactly `400: bad_request`, `401: unauthorized`, `403: forbidden`, `404: not_found`, `405: method_not_allowed`, `410: gone` — 405 is included because Starlette's router raises it and the handler in Task 2 now catches it.
  - No comments or docstrings (project convention, ARCHITECTURE.md Constraints).
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Global `HTTPException` → envelope handler
- **Description**: Add the exception handler to `backend/src/api/main.py` per the ARCHITECTURE.md "Error envelope" section. Register it on **`starlette.exceptions.HTTPException`, not `fastapi.HTTPException`** — Starlette resolves handlers by walking the raised exception's MRO, so registering on the FastAPI subclass would miss the `404` and `405` that Starlette's own router raises, leaving them with a bare `{"detail": ...}` body. Registering on the Starlette base class replaces FastAPI's own default handler (same dict key), so no bare `detail` body can survive on this path.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/main.py`, `backend/tests/test_error_envelope.py`]
- **Success Criteria**:
  - Handler is registered via `@app.exception_handler(StarletteHTTPException)` where `StarletteHTTPException` is imported from `starlette.exceptions`.
  - Body is exactly `{"error": {"code", "message", "details"}}`; `code` is `exc.code` when the exception is an `ApiError`, else `_DEFAULT_CODES_BY_STATUS.get(exc.status_code, "error")`; `message` is `str(exc.detail)` falling back to `code` when `detail` is falsy; `details` is always `{}`.
  - `status_code` is read off the exception unmodified — no status is remapped.
  - `GET /api/v1/health` is untouched: it returns a hand-built `JSONResponse` and never raises `HTTPException`, so it must not be double-wrapped.
  - Tests (`test_error_envelope.py`, new): a `401` (no bearer on `/api/v1/hosts`), a `403` (viewer bearer on `POST /api/v1/invites`) and a `404` (unknown host id with a valid bearer) each return the three-key envelope with codes `unauthorized` / `forbidden` / `not_found` and **no top-level `detail` key**; an unmatched path (`GET /api/v1/nope`) returns the `404` envelope with code `not_found` and a wrong method on a real route returns the `405` envelope — these two are the regression test for registering on the wrong exception class; `GET /api/v1/health` under a forced `SQLAlchemyError` still returns its existing `503` `database_unreachable` envelope unchanged.
  - The full existing suite passes unmodified — no test file other than the new one is edited by this task.

## Task 3: Unhandled-exception (500) envelope
- **Description**: Add `@app.exception_handler(Exception)` to `backend/src/api/main.py` per the ARCHITECTURE.md "Unhandled exceptions (500) — in scope" section. The contract `$ref`s `InternalServerError` on every route while the runtime emits Starlette's plain-text body, making this the widest envelope gap in the API. This handler's input is untrusted: the message is a fixed string and `details` is always `{}` — `str(exc)` must not appear anywhere in the body (`TRUTH.md` "reveal nothing about the internal failure").
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/main.py`, `backend/tests/test_error_envelope.py`]
- **Success Criteria**:
  - Returns `500` with `{"error": {"code": "internal_server_error", "message": <fixed string>, "details": {}}}`.
  - No `str(exc)`, `repr(exc)`, traceback, or exception attribute reaches the response body.
  - Debugging behavior is unchanged: FastAPI installs this as `ServerErrorMiddleware`'s handler, which re-raises after sending, so tracebacks still surface and `TestClient`'s default `raise_server_exceptions=True` still re-raises.
  - Tests (`test_error_envelope.py`, extend): a route raising a bare `RuntimeError("boom")` driven through `TestClient(app, raise_server_exceptions=False)` returns the envelope with code `internal_server_error`, **and the string `"boom"` appears nowhere in the response body** — the explicit no-leak assertion.

## Task 4: WebSocket denial responses carry the envelope
- **Description**: `require_agent_ws` raises `HTTPException(401/403)` in **websocket** scope; Starlette runs the same handler there and sends its return value as the HTTP denial response, so Task 2 already changes that body. `openapi.yaml:475-478` already documents those responses as `Unauthorized`/`Forbidden`, both `$ref`ing `ErrorResponse` — so this closes pre-existing contract drift. Left alone, `main.py`'s separate `ws_validation_denial` handler (malformed `{agent_id}`) would still send a bodiless `Response(403)`, giving one route two shapes for one documented response. Change it to send the envelope per the ARCHITECTURE.md "agent WebSocket upgrade path" section.
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/main.py`, `backend/tests/test_require_agent_ws.py`]
- **Success Criteria**:
  - `ws_validation_denial` sends a `JSONResponse` denial with `{"error": {"code": "forbidden", "message": ..., "details": {}}}` at status `403` — status unchanged from today.
  - The existing comment on that handler is kept but narrowed: RFC 6455's 123-byte limit governs the WebSocket **close reason**, not an HTTP denial body, so it no longer justifies dropping the body.
  - `dependencies/agent_auth.py` is **not** edited — its raises are already covered by the Task 2 handler.
  - No scope branch is added to the Task 2 handler; its first parameter stays annotated `Request` even though websocket scope passes a `WebSocket`, since the body reads only `exc`.
  - Tests (`test_require_agent_ws.py`, extend three existing cases that today assert `status_code` only): a bad-signature `401`, `test_revoked_device_refused_with_403`, and `test_malformed_agent_id_path_refused_without_burning_nonce` each additionally assert the denial body is the envelope with codes `unauthorized` / `forbidden` / `forbidden`.
  - All other assertions in that file — including the nonce-not-burned check — still pass unchanged.

## Task 5: C13 — distinguish wrong-current-password from a policy rejection
- **Description**: In `backend/src/api/routers/auth.py`, split `change_password_route`'s shared `except (WrongCurrentPasswordError, PasswordPolicyError)` into two clauses raising `ApiError` with distinct codes, per the ARCHITECTURE.md "The one call site this feature edits to use the override". **Both stay `400`** — a `401` would trip the SPA's refresh interceptor and bounce the user to login over a mistyped field, which is the entire point of C13. This is the only raise site this feature converts; every other site keeps its bare `HTTPException` and gets the envelope via the default-code path.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/routers/auth.py`, `backend/tests/test_auth_routes.py`]
- **Success Criteria**:
  - Two `except` clauses: `WrongCurrentPasswordError` → `ApiError(400, str(exc), code="wrong_current_password")`; `PasswordPolicyError` → `ApiError(400, str(exc), code="password_policy_violation")`. Both use `from exc`.
  - `reset_password_route` and `accept_invite_route` are **not** touched — their codes belong to DMI-77 (ARCHITECTURE.md Constraints).
  - No other raise site in the file is converted to `ApiError`.
  - Tests (`test_auth_routes.py`, extend existing change-password tests, reusing their fixtures): a wrong `current_password` → `400` with `error.code == "wrong_current_password"`; a policy-violating `new_password` with the correct current password → `400` with `error.code == "password_policy_violation"`; both explicitly assert the status is **not** `401`; the policy-rejection case asserts the stored password is unchanged.

## Task 6: `UserProfileResponse` schema
- **Description**: Create `backend/src/api/schemas/users.py` with the `UserProfileResponse` model from the ARCHITECTURE.md "Data model / contracts" field table. No `password_expires_at` and no `display_name` — neither field exists on `User`, and ADR-016 removed forced rotation entirely, so there is no expiry to report (`TRUTH.md` "No password expiry exists").
- **Dependencies**: —
- **Target Files**: [`backend/src/api/schemas/users.py`, `backend/tests/test_users_schemas.py`]
- **Success Criteria**:
  - `UserProfileResponse` has exactly `user_id: UUID`, `email: str`, `role: Literal["admin", "viewer"]` — all required.
  - `model_config = ConfigDict(extra="forbid")`, matching `schemas/auth.py` / `schemas/invites.py`.
  - No comments or docstrings.
  - Tests (`test_users_schemas.py`, mirroring `test_auth_schemas.py`): a valid payload parses; an unknown extra key raises `ValidationError`; a missing required field raises `ValidationError`; a `role` outside `admin`/`viewer` raises `ValidationError`.

## Task 7: `GET /api/v1/users/me` route
- **Description**: Create `backend/src/api/routers/users.py` and register it in `main.py`, per the ARCHITECTURE.md naming table. Reuse the existing `require_user` dependency — no token re-decoding. Read `role` from the `User` **row**, not from the JWT claims, so the role is authoritative from the profile resource (`TRUTH.md` business rules); that is the whole point of C16. Mirror the shape of `routers/hosts.py`: full path in the decorator, `Depends(get_session)` + `Depends(require_user)`, `response_model=`. **No `OPTIONS` preflight handler** — the derived-preflight loops in `auth.py`/`invites.py` filter on POST, and the GET-only routers (`hosts`, `scans`, `findings`) have none; real browser preflights are answered by `NoContentCorsMiddleware` before routing.
- **Dependencies**: Task 6
- **Target Files**: [`backend/src/api/routers/users.py`, `backend/src/api/main.py`, `backend/tests/test_users_routes.py`]
- **Success Criteria**:
  - `GET /api/v1/users/me` returns `UserProfileResponse` built from `session.get(User, caller.sub)`; `role` comes from the row, not from `caller.role`.
  - Route is read-only: no `PATCH`/`PUT`, no request body, no write path, and **no path parameter** — there is structurally no way to address another user's record.
  - No `OPTIONS` route is added to this router.
  - A missing `User` row (token valid, account deleted) raises `HTTPException(401, "Not authenticated")`, reusing the existing pattern at `routers/auth.py:85-87`.
  - `main.py` adds `users` to the `from api.routers import ...` line and `app.include_router(users.router)`.
  - Tests (`test_users_routes.py`, mirroring `test_read_endpoints.py`'s bearer-gate pattern): no bearer → `401` envelope; a malformed/garbage bearer → `401` envelope; a valid admin token → `200` with `role == "admin"` and the seeded id and email; a valid viewer token → `200` with `role == "viewer"`; the `200` body has **no `password_expires_at` key** (explicit negative assertion pinning ADR-016).

## Task 8: Contract edits in `openapi.yaml`
- **Description**: Apply all five edits from the ARCHITECTURE.md "`openapi.yaml` additions" section. The load-bearing one is `PasswordChangeRejected`: Task 5's codes are values the SPA must branch on, and shipping them without publishing them would recreate C16's exact defect inside the feature that exists to close it. Follow the established `DeviceBusyError` / `DeviceOfflineError` house style at `openapi.yaml:1213-1240`.
- **Dependencies**: Task 5, Task 7
- **Target Files**: [`contracts/openapi/openapi.yaml`]
- **Success Criteria**:
  - New `users` tag (`Read-only self profile.`) and path `/api/v1/users/me` with `get:` only — **no `options:` entry** — `security: [FrontendBearerAuth: []]`, `200` → new `UserProfileResponse` schema, `401` → `$ref: '#/components/responses/Unauthorized'`.
  - `UserProfileResponse` schema: `user_id` (`format: uuid`), `email` (`format: email`), `role` (`enum: [admin, viewer]`); all three `required`; `additionalProperties: false`.
  - New `PasswordChangeRejected` response component: `allOf` over `ErrorResponse` narrowing `error.code` to `enum: [wrong_current_password, password_policy_violation]`, a description stating **"The `code` is pinned"** and folding in the existing must-be-400-not-401 C13 sentence, and one example per code. `/api/v1/auth/change-password`'s `400` points at it instead of `BadRequest`, and the C13 sentence is not left duplicated at the old site.
  - `FrontendBearerAuth.description` gains the C16 not-a-contract sentence: the token's claims are an implementation detail, do not decode client-side, call `GET /api/v1/users/me` for identity and role.
  - `/api/v1/invites/{token}/accept`'s `410` gains `content: application/json: schema: $ref: '#/components/schemas/ErrorResponse'` — body shape only, **no `examples` block and no pinned `code`** (that value is DMI-77's to choose).
  - No other path, schema, or response component is modified.
  - The file still parses as valid OpenAPI 3.1.

## Task 9: Regenerate `openapi.d.ts`
- **Description**: Run `npm run gen:types` from `frontend/` and commit the regenerated `frontend/src/types/openapi.d.ts`, per `INTEGRATION.md`. This file is generated and **never hand-edited** (ADR-008); deferring regeneration would leave the contract and its generated type disagreeing in the repo, which is exactly the drift ADR-008 keeps the file versioned to catch. No frontend runtime code is written — consuming these types is DMI-81's work.
- **Dependencies**: Task 8
- **Target Files**: [`frontend/src/types/openapi.d.ts`]
- **Success Criteria**:
  - Produced solely by `cd frontend && npm run gen:types` — zero manual edits to the file.
  - `git diff frontend/src/types/openapi.d.ts` shows only: the new `/api/v1/users/me` path, the `UserProfileResponse` type, the `PasswordChangeRejected` union on change-password's `400`, the `FrontendBearerAuth` description text, and the `410` response's new content type. An unrelated diff means the Task 8 edit touched something it should not have — re-check `openapi.yaml` rather than committing it.
  - `role` surfaces as a `"admin" | "viewer"` union, and the change-password `400` code as a `"wrong_current_password" | "password_policy_violation"` union — not bare `string`. If either lands as `string`, the Task 8 `enum` is wrong.
  - No other file under `frontend/` changes.

---

## Dependency graph

```
#1 (errors.py) ──┬──→ #2 (HTTPException handler) ──┬──→ #3 (500 handler)
                 │                                 └──→ #4 (WS denial envelope)
                 └──→ #5 (C13 codes) ──────────────────┐
                                                       ├──→ #8 (openapi.yaml) ──→ #9 (gen:types)
#6 (schema) ─────────→ #7 (/users/me route) ───────────┘
```

Two independent entry points: **#1** opens the error-envelope track, **#6** opens the
`/users/me` track. They converge at **#8**. Tasks #2, #3, #4 and #7 all edit
`backend/src/api/main.py` — the graph chains them so no two run against that file at once.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | `ApiError` and the status→code default map | COMPLETED |
| 2 | Global `HTTPException` → envelope handler | COMPLETED |
| 3 | Unhandled-exception (500) envelope | COMPLETED |
| 4 | WebSocket denial responses carry the envelope | COMPLETED |
| 5 | C13 — distinguish wrong-current-password from a policy rejection | COMPLETED |
| 6 | `UserProfileResponse` schema | COMPLETED |
| 7 | `GET /api/v1/users/me` route | COMPLETED |
| 8 | Contract edits in `openapi.yaml` | COMPLETED |
| 9 | Regenerate `openapi.d.ts` | COMPLETED |
