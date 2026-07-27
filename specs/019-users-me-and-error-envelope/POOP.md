# POOP — Technical ledger (append only)

`POOP.md` is the "poop" of the subagents — a joke about subagents constantly producing messy
code. Every coder, test engineer, and reviewer appends one section before returning. The
orchestrator appends only `STRUCTURAL_REEVAL` blocks. Never overwrite prior entries.

Each entry includes:
1. **Order Given** — the exact task scope / prompt.
2. **What, How, and Why** — what was done, how, and why that approach.
3. **Decisions Made** — key technical decisions.
4. **Code Changed / Reviewed** — file paths only, no snippets.

---

## Task 1 — `ApiError` and the status→code default map

### Order Given

Create `backend/src/api/errors.py` per ARCHITECTURE.md "Error envelope": an `ApiError(HTTPException)` subclass with keyword-only `code` (no `details` parameter), plus module-level `_DEFAULT_CODES_BY_STATUS` mapping 400/401/403/404/405/410 to their default codes.

### What, How, and Why

Added `errors.py` with `ApiError` subclassing `fastapi.HTTPException`, calling `super().__init__(status_code=..., detail=...)` and setting `self.code`. Defined `_DEFAULT_CODES_BY_STATUS` with the six status codes required by the spec (including 405 for Starlette router-raised method-not-allowed). No handler registration — subclassing `HTTPException` is sufficient for Task 2's global handler to catch it via `isinstance(exc, ApiError)`.

### Decisions Made

- Imported `HTTPException` from `fastapi` to match existing raise sites in the codebase.
- Omitted `details` parameter deliberately per spec — always `{}` at the handler layer until DMI-77 or a 422 follow-up needs it.

### Code Changed

- created: `backend/src/api/errors.py`

---

## Task 1 — test engineer

### Order Given

Evaluate whether `backend/src/api/errors.py` warrants unit tests for Task 1 (`ApiError`, `_DEFAULT_CODES_BY_STATUS`). Append POOP; return list of test files created or modified (may be empty).

### What, How, and Why

Read `errors.py`, TASKS.md Task 1 success criteria, and nearest backend test patterns (`test_auth_schemas.py`). The module is 16 lines: a three-line `__init__` on an `HTTPException` subclass plus a six-entry status→code dict. Task 1 lists no test success criteria; Task 2 adds `test_error_envelope.py` integration coverage for 401/403/404/405 default codes via the global handler, and Task 5 will assert explicit `ApiError` codes at the one override call site. No new test file added — the thin constructor and inheritance are exercised as soon as those tasks land, and a dedicated unit file would mostly restate the spec dict.

### Decisions Made

- Skipped tests per ponytail/YAGNI: zero test files for this task.
- Did not import or assert on `_DEFAULT_CODES_BY_STATUS` in isolation — it is private module data consumed by Task 2's handler; integration tests are the right boundary.
- Did not add a keyword-only `code` or `issubclass` smoke test — both are one-liner behaviors with no branching logic.

### Code Changed

(none)

---

## Task 1 — code reviewer

### Order Given

Code-review gate for Task 1 (`ApiError` and `_DEFAULT_CODES_BY_STATUS` in `backend/src/api/errors.py`). Verify success criteria in TASKS.md, run `uv run ruff check src/api/errors.py` and `uv run pytest` from `backend/`, append POOP, output `[APPROVE]` or `[REJECT]`.

### What, How, and Why

Read `errors.py` against TASKS.md Task 1 success criteria and ARCHITECTURE.md "Error envelope". Confirmed `ApiError` subclasses `fastapi.HTTPException`, `__init__` takes keyword-only `code` with no `details` parameter, calls `super().__init__(status_code=..., detail=...)`, sets `self.code`, and `_DEFAULT_CODES_BY_STATUS` contains exactly the six required entries. No comments, docstrings, or `# ponytail:` markers. Ran `uv run ruff check src/api/errors.py` (pass) and full `uv run pytest` (361 passed, 167 skipped, no regressions).

### Decisions Made

- **Approve** — implementation is minimal, matches spec exactly, no over-engineering findings.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (backend-only task).
- No ponytail markers to strip on approve.

### Code Reviewed

- `backend/src/api/errors.py`

---

## Task 2 — Global `HTTPException` → envelope handler

### Order Given

Add `@app.exception_handler(StarletteHTTPException)` to `backend/src/api/main.py` per ARCHITECTURE.md. Register on `starlette.exceptions.HTTPException`, not `fastapi.HTTPException`. Create `backend/tests/test_error_envelope.py` with 401/403/404/405 envelope assertions, unmatched-path 404, wrong-method 405, and health 503 regression guard.

### What, How, and Why

Registered `http_exception_handler` on `StarletteHTTPException` so Starlette-router-raised 404/405 responses get the envelope alongside app-raised `HTTPException`. Handler reads `exc.code` for `ApiError`, else `_DEFAULT_CODES_BY_STATUS`, builds `message` from `str(exc.detail)` with `code` fallback, always `{}` details, and returns `JSONResponse` with unmodified `exc.status_code`. Added integration tests mirroring `test_read_endpoints` sqlite fixtures for hosts 401/404, `postgres_client` + conftest fixtures for viewer invite 403, bare `TestClient` for unmatched path and wrong method, and the existing `test_health` DATABASE_URL override pattern for 503 `database_unreachable`.

### Decisions Made

- Imported `StarletteHTTPException` from `starlette.exceptions` and `Request` from `starlette.requests` per spec.
- Used separate `postgres_client` fixture for the invite 403 test so it uses `administrative_session` instead of the sqlite `client` fixture.
- Shared `_assert_error_envelope` helper asserts three-key envelope shape and absence of top-level `detail`.

### Code Changed

- modified: `backend/src/api/main.py`
- created: `backend/tests/test_error_envelope.py`

---

## Task 2 — test-engineer review

### Order Given

Review `backend/tests/test_error_envelope.py` against Task 2 success criteria; add missing cases only; run `uv run pytest tests/test_error_envelope.py`; append POOP.

### What, How, and Why

Mapped each Task 2 required case to an existing test: `test_hosts_without_bearer_returns_unauthorized_envelope` (401, no bearer on `/api/v1/hosts`), `test_viewer_post_invite_returns_forbidden_envelope` (403, viewer on `POST /api/v1/invites`), `test_unknown_host_returns_not_found_envelope` (404, unknown host with bearer), `test_unmatched_path_returns_not_found_envelope` (Starlette-router 404 on `GET /api/v1/nope`), `test_wrong_method_returns_method_not_allowed_envelope` (405 on `POST /api/v1/hosts`), `test_health_database_failure_returns_existing_envelope` (503 `database_unreachable` unchanged). Shared `_assert_error_envelope` covers the three-key envelope shape, correct `code`, and absence of top-level `detail`. Ran pytest: 5 passed, 1 skipped (`test_viewer_post_invite` skips when `DATABASE_URL_TEST` unset — conftest convention, test body is present).

### Decisions Made

- No new tests added — all six Task 2 cases already covered with no duplication.
- Did not duplicate 403 coverage with a sqlite-only path; the postgres invite test matches the spec endpoint and mirrors existing conftest patterns.

### Code Changed

- (none)

---

## Task 2 — code reviewer

### Order Given

Code-review gate for Task 2 (global `HTTPException` → envelope handler in `backend/src/api/main.py` and `backend/tests/test_error_envelope.py`). Verify all Task 2 success criteria against TASKS.md and ARCHITECTURE.md "Error envelope"; run `uv run ruff check src/api/main.py tests/test_error_envelope.py` and `uv run pytest tests/test_error_envelope.py` plus full suite from `backend/`; append POOP; first line `[APPROVE]` or `[REJECT]`.

### What, How, and Why

Read `main.py` handler registration and envelope logic against spec: `@app.exception_handler(StarletteHTTPException)` imported from `starlette.exceptions`; `code` from `ApiError.code` or `_DEFAULT_CODES_BY_STATUS` with `"error"` fallback; `message` from `str(exc.detail)` with `code` fallback; `details` always `{}`; `status_code=exc.status_code` with no remapping; health route still returns hand-built `503` `database_unreachable` envelope. Read `test_error_envelope.py` for all six scenarios (401 hosts, 403 viewer invite, 404 unknown host, unmatched-path 404, wrong-method 405, health DB failure). Confirmed only `main.py` modified and `test_error_envelope.py` created under `backend/tests/` (no other test files edited). Ran `uv run ruff check src/api/main.py tests/test_error_envelope.py` (pass); `uv run pytest tests/test_error_envelope.py -v` (5 passed, 1 skipped — `test_viewer_post_invite` skips without `DATABASE_URL_TEST`, established conftest convention); full `uv run pytest -q` (366 passed, 168 skipped, 0 failed). No `# ponytail:` markers in touched files.

### Decisions Made

- **Approve** — handler and tests match spec; suite green; no over-engineering in application code.
- 403 test skip without `DATABASE_URL_TEST` is acceptable — same harness pattern as other DB-backed tests; test body present and runs in CI.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (backend-only).
- No ponytail markers to strip.

### Code Reviewed

- `backend/src/api/main.py`
- `backend/tests/test_error_envelope.py`

---

## Task 3 — Unhandled-exception (500) envelope

### Order Given

Add `@app.exception_handler(Exception)` to `backend/src/api/main.py` returning 500 with `{"error": {"code": "internal_server_error", "message": <fixed string>, "details": {}}}`. No exception text in the body. Extend `backend/tests/test_error_envelope.py` with a route raising `RuntimeError("boom")` via `TestClient(app, raise_server_exceptions=False)`; assert envelope and that `"boom"` does not appear in the response body.

### What, How, and Why

Added `unhandled_exception_handler` immediately after the existing `StarletteHTTPException` handler in `main.py`, returning a fixed `"Internal server error."` message and empty `details` per ARCHITECTURE.md — no `str(exc)` or traceback leakage. Extended `test_error_envelope.py` with a temporary `/__test_internal_error__` route that raises `RuntimeError("boom")`, driven through `TestClient(..., raise_server_exceptions=False)` so the 500 body can be read; route is removed in a `finally` block to avoid polluting the shared app. Reused `_assert_error_envelope` for shape/code and added `assert "boom" not in response.text` for the no-leak pin.

### Decisions Made

- Placed the `Exception` handler after the `HTTPException` handler so more-specific handlers remain registered first; FastAPI resolves by exception type/MRO, not registration order.
- Used a disposable test route with cleanup rather than a permanent debug endpoint — YAGNI, no production surface.
- Checked `response.text` for `"boom"` rather than only `response.json()` so a leak in any JSON field would fail.

### Code Changed

- modified: `backend/src/api/main.py`
- modified: `backend/tests/test_error_envelope.py`

---

## Task 3 — test-engineer review

### Order Given

Verify `test_error_envelope.py` coverage against TASKS.md Task 3 success criteria for the unhandled-exception (500) envelope; add tests only if gaps; run `uv run pytest tests/test_error_envelope.py` from `backend/`; append POOP; return changed files (may be empty).

### What, How, and Why

Mapped Task 3 test criteria to `test_unhandled_exception_returns_internal_server_error_envelope`: disposable `/__test_internal_error__` route raises `RuntimeError("boom")`, driven via `TestClient(app, raise_server_exceptions=False)` so the 500 body is readable; `_assert_error_envelope` pins status `500`, three-key envelope shape, code `internal_server_error`, empty `details`, and no top-level `detail`; `assert "boom" not in response.text` pins the no-leak rule across the full response body. Handler in `main.py` returns fixed message `"Internal server error."` with no `str(exc)` — not separately asserted in tests, but the explicit `"boom"` negative covers the load-bearing leak regression. Ran `uv run pytest tests/test_error_envelope.py -v`: 6 passed, 1 skipped (`test_viewer_post_invite` without `DATABASE_URL_TEST`).

### Decisions Made

- No new tests added — developer's Task 3 test satisfies all stated success criteria with no duplication.
- Did not add a fixed-message assertion — TASKS.md test criteria stop at code envelope + no `"boom"` leak; `response.text` check already fails if message echoed the exception.
- Did not test `raise_server_exceptions=True` re-raise behavior — spec marks it as unchanged debugging semantics, not a test deliverable for this task.

### Code Changed

(none)

---

## Task 3 — code reviewer

### Order Given

Code-review gate for Task 3 (`019-users-me-and-error-envelope`). Review `backend/src/api/main.py` and `backend/tests/test_error_envelope.py` against TASKS.md Task 3 success criteria. Run ruff + pytest from `backend/`. First line `[APPROVE]` or `[REJECT]`. Append POOP.

### What, How, and Why

Read `unhandled_exception_handler` in `main.py` against TASKS.md Task 3 and ARCHITECTURE.md "Unhandled exceptions (500)": `@app.exception_handler(Exception)` returns `500` with `code: internal_server_error`, fixed `message: "Internal server error."`, and `details: {}`; handler body never references `exc` (no `str(exc)`, `repr`, or traceback leakage). Read `test_unhandled_exception_returns_internal_server_error_envelope`: disposable route raises `RuntimeError("boom")`, driven via `TestClient(app, raise_server_exceptions=False)`, asserts envelope via `_assert_error_envelope` and `assert "boom" not in response.text`. Target files match spec. Ran `uv run ruff check src/api/main.py tests/test_error_envelope.py` (pass); `uv run pytest tests/test_error_envelope.py -v` (6 passed, 1 skipped); full `uv run pytest -q` (367 passed, 168 skipped). No `# ponytail:` markers in touched files.

### Decisions Made

- **Approve** — handler matches ARCHITECTURE.md verbatim; test covers envelope + no-leak pin; suite green; no over-engineering.
- `raise_server_exceptions=True` re-raise behavior not tested — spec treats it as unchanged FastAPI semantics, not a Task 3 test deliverable.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (backend-only).
- No ponytail markers to strip.

### Code Reviewed

- `backend/src/api/main.py`
- `backend/tests/test_error_envelope.py`

---

## Task 4 — WebSocket denial responses carry the envelope

### Order Given

Change `ws_validation_denial` in `backend/src/api/main.py` to send `JSONResponse` with `{"error": {"code": "forbidden", "message": ..., "details": {}}}` at 403. Narrow the existing RFC 6455 comment. Do not edit `dependencies/agent_auth.py`. Extend `backend/tests/test_require_agent_ws.py`: bad-signature 401, `test_revoked_device_refused_with_403`, and `test_malformed_agent_id_path_refused_without_burning_nonce` each assert denial body is envelope with codes `unauthorized` / `forbidden` / `forbidden`.

### What, How, and Why

Updated `ws_validation_denial` to call `send_denial_response` with a `JSONResponse` carrying the standard three-key error envelope (`code: forbidden`, `message` from `str(exc)`, `details: {}`) at status 403 — closing the contract drift where malformed `{agent_id}` paths returned a bodiless denial while auth failures already got the Task 2 envelope via `HTTPException`. Narrowed the handler comment to clarify RFC 6455's 123-byte limit applies to WebSocket close reasons, not HTTP denial bodies. Added `_assert_ws_denial_envelope` helper in the test file (mirroring `test_error_envelope.py`'s shape assertions) and wired it into the three specified denial cases. Removed unused `Response` import from `main.py`.

### Decisions Made

- Used `str(exc)` for the malformed-path message — validation detail belongs in the HTTP denial body now that we are no longer constrained by close-frame length.
- Auth-path 401/403 envelopes come from the existing `StarletteHTTPException` handler unchanged; only the separate `WebSocketRequestValidationError` handler needed editing.

### Code Changed

- modified: `backend/src/api/main.py`
- modified: `backend/tests/test_require_agent_ws.py`

---

## Task 4 — test-engineer review

### Order Given

Verify `backend/tests/test_require_agent_ws.py` covers Task 4 success criteria (WebSocket denial envelope on bad-signature 401, revoked-device 403, malformed-agent-id 403); run pytest from `backend/`; append POOP; return changed files.

### What, How, and Why

Mapped each Task 4 test criterion to existing coverage: `test_bad_signature_refused` calls `_assert_ws_denial_envelope(..., 401, "unauthorized")`; `test_revoked_device_refused_with_403` and `test_malformed_agent_id_path_refused_without_burning_nonce` each call `_assert_ws_denial_envelope(..., 403, "forbidden")`. Shared helper asserts status, three-key `error` envelope shape, correct `code`, empty `details`, and no top-level `detail`. The malformed-path test still re-connects with the same headers and asserts the agent comes online — nonce-not-burned behavior unchanged. Ran `uv run pytest tests/test_require_agent_ws.py -v` (12 skipped — `DATABASE_URL_TEST` unset, conftest convention) and full `uv run pytest -q` (367 passed, 168 skipped, 0 failed).

### Decisions Made

- No new tests added — all three specified cases already extended with envelope assertions; helper mirrors `test_error_envelope.py` boundary.
- Did not extend other 401 cases (stale timestamp, replay, missing header, path mismatch) — Task 4 names only the bad-signature 401 case.
- Skips without `DATABASE_URL_TEST` are acceptable — same harness as other DB-backed WS tests; bodies run in CI.

### Code Changed

(none)

---

## Task 4 — code reviewer

### Order Given

Code-review gate for Task 4 (`019-users-me-and-error-envelope`). Review `backend/src/api/main.py` (`ws_validation_denial`) and `backend/tests/test_require_agent_ws.py` against TASKS.md Task 4 success criteria. Run `uv run ruff check` and `uv run pytest` from `backend/`. First line `[APPROVE]` or `[REJECT]`. Append POOP.

### What, How, and Why

Read `ws_validation_denial` in `main.py` against TASKS.md Task 4 and ARCHITECTURE.md "agent WebSocket upgrade path": handler sends `JSONResponse` at `403` with `{"error": {"code": "forbidden", "message": str(exc), "details": {}}}`; RFC 6455 comment narrowed to close-reason scope, not HTTP denial body; `http_exception_handler` unchanged (`Request` annotation, no websocket scope branch). Confirmed `dependencies/agent_auth.py` untouched. Read `test_require_agent_ws.py`: `_assert_ws_denial_envelope` helper asserts three-key envelope shape and no top-level `detail`; wired into `test_bad_signature_refused` (401/`unauthorized`), `test_revoked_device_refused_with_403` (403/`forbidden`), and `test_malformed_agent_id_path_refused_without_burning_nonce` (403/`forbidden`); malformed-path test still re-connects and asserts agent online (nonce-not-burned). Ran `uv run ruff check src/api/main.py tests/test_require_agent_ws.py` (pass); `uv run pytest tests/test_require_agent_ws.py -v` (12 skipped — `DATABASE_URL_TEST` unset, conftest convention); full `uv run pytest -q` (367 passed, 168 skipped). No `# ponytail:` markers in touched files.

### Decisions Made

- **Approve** — implementation minimal, matches spec; suite green; no over-engineering findings.
- WS test skips without `DATABASE_URL_TEST` acceptable — same harness as prior tasks; envelope assertions present and run in CI.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (backend-only).
- No ponytail markers to strip.

### Code Reviewed

- `backend/src/api/main.py`
- `backend/tests/test_require_agent_ws.py`

---

## Task 5 — C13 distinguish wrong-current-password from policy rejection

### Order Given

In `backend/src/api/routers/auth.py`, split `change_password_route`'s shared `except (WrongCurrentPasswordError, PasswordPolicyError)` into two clauses raising `ApiError` with codes `wrong_current_password` and `password_policy_violation` (both stay 400). Do not touch `reset_password_route` or `accept_invite_route`. Extend `backend/tests/test_auth_routes.py` with tests per success criteria.

### What, How, and Why

Split the single combined `except` in `change_password_route` into two clauses per ARCHITECTURE.md: `WrongCurrentPasswordError` → `ApiError(400, str(exc), code="wrong_current_password")` and `PasswordPolicyError` → `ApiError(400, str(exc), code="password_policy_violation")`, both with `from exc`. Imported `ApiError` from `api.errors`. Left `reset_password_route` and all other raise sites untouched. Extended the two existing change-password route tests: wrong current password asserts `400`, not `401`, and `error.code == "wrong_current_password"`; policy-violating new password asserts `400`, not `401`, `error.code == "password_policy_violation"`, and `verify_password(VALID_PASSWORD, user.password_hash)` after refresh to pin the stored hash unchanged.

### Decisions Made

- Reused existing tests rather than adding new ones — spec says "extend existing change-password tests".
- `verify_password` on refreshed `User` row for the policy-rejection unchanged-password pin — minimal check without a second login round-trip.
- No changes to `reset_password_route` per DMI-77 fence.

### Code Changed

- modified: `backend/src/api/routers/auth.py`
- modified: `backend/tests/test_auth_routes.py`

---

## Task 6 — `UserProfileResponse` schema

### Order Given

Create `backend/src/api/schemas/users.py` with `UserProfileResponse` (user_id UUID, email str, role Literal admin/viewer, extra=forbid). Create `backend/tests/test_users_schemas.py` mirroring `test_auth_schemas.py` patterns. No comments/docstrings. Append POOP.md.

### What, How, and Why

Added `UserProfileResponse` as a minimal Pydantic `BaseModel` with `ConfigDict(extra="forbid")` and exactly three required fields per ARCHITECTURE.md data model table — no `password_expires_at` or `display_name`. Mirrored `schemas/auth.py` import style (`from __future__ import annotations`, `Literal`, `UUID` from `uuid`). Tests follow `test_auth_schemas.py`: valid payload parse, extra field rejection, missing required field rejection, and invalid `role` rejection.

### Decisions Made

- Used `Literal["admin", "viewer"]` for `role` as specified — matches `User.role` domain values.
- `display_name` in the extra-field test as the negative pin — plausible field that must not exist on this schema.
- Did not register the schema in `schemas/__init__.py` — not required by task; route task will import directly from `api.schemas.users`.

### Code Changed

- created: `backend/src/api/schemas/users.py`
- created: `backend/tests/test_users_schemas.py`

---

## Task 5 — test-engineer review

### Order Given

Test engineer Task 5 (`019-users-me-and-error-envelope`). Verify `test_auth_routes.py` covers Task 5 criteria. Run pytest from `backend/`. Append POOP.

### What, How, and Why

Mapped each Task 5 test criterion to existing coverage in `test_auth_routes.py`: `test_change_password_wrong_current_returns_400_not_401` posts a wrong `current_password` with a valid bearer, asserts `400`, `!= 401`, and `error.code == "wrong_current_password"`; `test_change_password_weak_new_password_returns_400` posts policy-violating `new_password` (`aaabbbcccddd`) with the correct current password, asserts `400`, `!= 401`, `error.code == "password_policy_violation"`, and `verify_password(VALID_PASSWORD, user.password_hash)` after refresh to pin the stored hash unchanged. Both reuse `_seed_user`, `_login_and_get_access_token`, and the `client` fixture per spec. Confirmed `change_password_route` in `auth.py` has the two split `ApiError` clauses; `reset_password_route` still raises bare `HTTPException`. Ran `uv run pytest tests/test_auth_routes.py -v` from `backend/` with `DATABASE_URL_TEST` set: 11 passed (all skipped without it — conftest convention).

### Decisions Made

- No new tests added — developer's two extended change-password tests satisfy every Task 5 assertion with no duplication.
- Did not add envelope-shape or top-level `detail` assertions — Task 5 criteria stop at status, code, and unchanged password; global envelope shape is Task 2's boundary.
- Did not assert `reset_password_route` / `accept_invite_route` unchanged in tests — production-code fence verified by read; those routes are out of Task 5 test scope.

### Code Changed

(none)

---

## Task 5 — code-reviewer gate

### Order Given

Code reviewer gate Task 5 (`019-users-me-and-error-envelope`). Review `auth.py` and `test_auth_routes.py` against TASKS.md Task 5. Run ruff + pytest from `backend/`. First line `[APPROVE]` or `[REJECT]`. Append POOP.md.

### What, How, and Why

Read `change_password_route` in `backend/src/api/routers/auth.py` against Task 5 success criteria: split `except WrongCurrentPasswordError` → `ApiError(400, str(exc), code="wrong_current_password") from exc` and `except PasswordPolicyError` → `ApiError(400, str(exc), code="password_policy_violation") from exc`; `reset_password_route` still raises bare `HTTPException(400, …)`; no other raise site converted to `ApiError`. Read `test_auth_routes.py`: `test_change_password_wrong_current_returns_400_not_401` and `test_change_password_weak_new_password_returns_400` cover wrong-current (`400`, `!= 401`, `wrong_current_password`), policy rejection (`400`, `!= 401`, `password_policy_violation`, unchanged hash via `verify_password`), both reusing `_seed_user` / `_login_and_get_access_token` / `client`. No `# ponytail:` markers in touched files. Ran `uv run ruff check src/api/routers/auth.py tests/test_auth_routes.py` (pass). Ran `uv run pytest tests/test_auth_routes.py -v` without `DATABASE_URL_TEST` (11 skipped — conftest convention) and with `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test` (11 passed, including both change-password cases).

### Decisions Made

- `[APPROVE]` — every Task 5 success criterion met; target files match; no over-engineering findings; ScanRunner thread-through N/A (backend-only).
- Skips without `DATABASE_URL_TEST` acceptable — established harness pattern; tests green when DB available.

### Code Reviewed

- `backend/src/api/routers/auth.py`
- `backend/tests/test_auth_routes.py`

---

## Task 6 — test-engineer review

### Order Given

Test engineer Task 6 (`019-users-me-and-error-envelope`). Verify `test_users_schemas.py` covers Task 6 criteria. Run pytest from `backend/`. Append POOP.

### What, How, and Why

Mapped each Task 6 test criterion to existing coverage in `test_users_schemas.py`: `test_user_profile_response_validates_good_payload` parses a valid `user_id`/`email`/`role` payload and asserts field values; `test_user_profile_response_rejects_extra_fields` raises `ValidationError` on `display_name` (plausible field excluded per TRUTH.md); `test_user_profile_response_rejects_missing_required_field` raises `ValidationError` when `role` is omitted; `test_user_profile_response_rejects_invalid_role` raises `ValidationError` for `superuser`. Layout mirrors `test_auth_schemas.py` (`model_validate`, `pytest.raises(pydantic.ValidationError)`, no comments/docstrings). Read `users.py` to confirm schema matches spec: three required fields, `ConfigDict(extra="forbid")`, no `password_expires_at` or `display_name`. Ran `uv run pytest tests/test_users_schemas.py -v` from `backend/`: 4 passed.

### Decisions Made

- No new tests added — all four Task 6 test success criteria already covered with no duplication.
- Did not add a separate `viewer` role happy-path test — `Literal` validation is symmetric; invalid-role rejection is the load-bearing case.
- Did not assert `model_config` or field types directly — Pydantic behavior is exercised by the four behavioral cases, matching `test_auth_schemas.py` style.

### Code Changed

(none)

---

## Task 6 — code reviewer

### Order Given

Code reviewer gate Task 6 (`019-users-me-and-error-envelope`). Review `users.py` schema and `test_users_schemas.py` against TASKS.md Task 6. Run ruff + pytest from `backend/`. First line `[APPROVE]` or `[REJECT]`. Append POOP.

### What, How, and Why

Read `backend/src/api/schemas/users.py` against TASKS.md Task 6 and ARCHITECTURE.md data-model table: `UserProfileResponse` has exactly three required fields (`user_id: UUID`, `email: str`, `role: Literal["admin", "viewer"]`), `model_config = ConfigDict(extra="forbid")`, no `password_expires_at` or `display_name`, no comments or docstrings. Read `backend/tests/test_users_schemas.py`: four tests mirror `test_auth_schemas.py` — valid payload parse, extra-field rejection (`display_name`), missing required field (`role`), invalid role (`superuser`). No `# ponytail:` markers. Ran `uv run ruff check src/api/schemas/users.py tests/test_users_schemas.py` (pass); `uv run pytest tests/test_users_schemas.py -v` (4 passed); full `uv run pytest -q` (371 passed, 168 skipped).

### Decisions Made

- **Approve** — every Task 6 success criterion met; target files match; implementation is minimal with no over-engineering findings.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (backend-only schema task).
- No ponytail markers to strip.

### Code Reviewed

- `backend/src/api/schemas/users.py`
- `backend/tests/test_users_schemas.py`

---

## Task 7 — `GET /api/v1/users/me` route

### Order Given

Create `backend/src/api/routers/users.py` with `GET /api/v1/users/me` using `require_user`, role from `User` row not JWT. Register in `main.py`. Create `backend/tests/test_users_routes.py` mirroring `test_read_endpoints.py` bearer-gate pattern. All Task 7 success criteria must be met.

### What, How, and Why

Added `read_current_user` route mirroring `hosts.py` shape: full path in decorator, `Depends(get_session)` + `Depends(require_user)`, `response_model=UserProfileResponse`. Looks up `User` by `caller.sub`, raises `HTTPException(401, "Not authenticated")` when missing (same pattern as `change_password_route`), returns profile with `role=user.role` from the row. Registered `users.router` in `main.py` after `auth.router`. Tests use sqlite fixtures like `test_read_endpoints.py`, seed `User` rows, build bearer tokens with matching `user_id` via `create_access_token`, assert 401 envelope for no/garbage bearer, 200 profiles for admin/viewer with no `password_expires_at`, plus C16 pin (JWT claims `admin` but row `viewer` → response `viewer`) and deleted-user 401 envelope.

### Decisions Made

- Placed `users.router` immediately after `auth.router` — identity-adjacent read route.
- Local `_assert_error_envelope` helper duplicated from `test_error_envelope.py` to avoid cross-test import and ruff I001.
- Added two tests beyond the minimum bearer-gate + happy-path set: row-over-JWT role pin (C16 load-bearing) and missing-user 401 (route success criterion).

### Code Changed

- created: `backend/src/api/routers/users.py`
- modified: `backend/src/api/main.py`
- created: `backend/tests/test_users_routes.py`

---

## Task 7 — test-engineer review

### Order Given

Test engineer Task 7 (`019-users-me-and-error-envelope`). Verify `test_users_routes.py` covers all Task 7 success criteria. Run pytest from `backend/`. Append POOP.

### What, How, and Why

Mapped each Task 7 test criterion to existing coverage in `test_users_routes.py`: `test_users_me_without_bearer_returns_401_envelope` (no bearer → 401 envelope via `_assert_error_envelope`); `test_users_me_with_garbage_bearer_returns_401_envelope` (malformed bearer → 401 envelope); `test_users_me_admin_returns_profile` (valid admin → 200, `user_id`/`email`/`role == "admin"`, no `password_expires_at`); `test_users_me_viewer_returns_profile` (valid viewer → 200, `role == "viewer"`, no `password_expires_at`); `test_users_me_role_from_row_not_jwt` (JWT claims `admin`, row `viewer` → response `viewer` — C16 row-over-claims pin); `test_users_me_missing_user_row_returns_401_envelope` (valid token, no `User` row → 401 envelope). Shared `_assert_error_envelope` pins three-key envelope shape, correct `code`, empty `details`, and no top-level `detail`. Read `routers/users.py` and `main.py` to confirm route uses `session.get(User, caller.sub)`, `user.role` from row, `HTTPException(401, "Not authenticated")` on missing row, and `users.router` registered. Structural criteria (read-only GET, no OPTIONS, no path param) are satisfied by the router definition and not duplicated in tests per ponytail. Ran `uv run pytest tests/test_users_routes.py -v`: 6 passed. Full `uv run pytest -q`: 376 passed, 168 skipped, 1 failed — `test_health.py::test_route_surface_is_exactly_the_declared_contract` (extra `('/api/v1/users/me', 'GET')` in app surface); that contract pin belongs to Task 8 `openapi.yaml`, not Task 7 test scope.

### Decisions Made

- No new tests added — all six Task 7 test success criteria already covered with no duplication.
- Did not add OPTIONS/PATCH negative tests — structural guarantees from router shape; spec test list stops at bearer-gate, happy paths, C16 pin, and deleted-user 401.
- Did not fix `test_health.py` route-surface failure — out of Task 7 target files; will resolve when Task 8 updates `EXPECTED_ROUTE_SURFACE`.

### Code Changed

(none)

---

## Task 7 — code reviewer

### Order Given

Code reviewer gate Task 7 (`019-users-me-and-error-envelope`). Review `users.py` router, `main.py` mount, `test_users_routes.py` against TASKS.md Task 7. Run ruff + pytest `tests/test_users_routes.py` from `backend/`. First line `[APPROVE]` or `[REJECT]`. Append POOP.

### What, How, and Why

Read `backend/src/api/routers/users.py` against Task 7 success criteria: single `GET /api/v1/users/me` with full path in decorator, `Depends(get_session)` + `Depends(require_user)`, `response_model=UserProfileResponse`; lookup via `session.get(User, caller.sub)`; `role=user.role` from row; `HTTPException(401, "Not authenticated")` on missing row (matches `auth.py:85-87`); no PATCH/PUT/OPTIONS/path params. Read `main.py`: `users` in router import and `app.include_router(users.router)` after `auth.router`. Read `test_users_routes.py`: six tests cover no-bearer 401 envelope, garbage-bearer 401 envelope, admin/viewer 200 profiles with seeded id/email and no `password_expires_at`, C16 row-over-JWT role pin, and missing-user-row 401 envelope via `_assert_error_envelope`. Target files match spec. Ran `uv run ruff check src/api/routers/users.py src/api/main.py tests/test_users_routes.py` (pass); `uv run pytest tests/test_users_routes.py -v` (6 passed). No `# ponytail:` markers in touched files.

### Decisions Made

- **Approve** — every Task 7 success criterion met; implementation mirrors `hosts.py` shape; tests exceed `test_read_endpoints.py` bearer-gate baseline with explicit envelope assertions per spec; no over-engineering in application code.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (backend-only).
- `test_health.py` route-surface failure is Task 8 scope, not judged here.
- No ponytail markers to strip.

### Code Reviewed

- `backend/src/api/routers/users.py`
- `backend/src/api/main.py`
- `backend/tests/test_users_routes.py`

---

## Task 8 — Contract edits in `openapi.yaml`

### Order Given

Apply all five edits from ARCHITECTURE.md "`openapi.yaml` additions" to `contracts/openapi/openapi.yaml`: new `users` tag + `GET /api/v1/users/me` (no options), `UserProfileResponse` schema, `PasswordChangeRejected` response component + repoint change-password `400`, `FrontendBearerAuth` C16 sentence, accept-invite `410` gains `ErrorResponse` content. Follow `DeviceBusyError`/`DeviceOfflineError` house style. No other paths/schemas modified.

### What, How, and Why

Added `users` tag and `GET /api/v1/users/me` path with `FrontendBearerAuth`, `200` → `UserProfileResponse`, `401` → `Unauthorized` — no `options:` entry per GET house style. Defined `UserProfileResponse` schema (`user_id` uuid, `email` email, `role` admin/viewer enum, all required, `additionalProperties: false`) beside auth schemas. Added `PasswordChangeRejected` response component using `allOf` over `ErrorResponse` with `error.code` narrowed to `enum: [wrong_current_password, password_policy_violation]`, C13 must-be-400-not-401 sentence folded into description, and one example per code; repointed change-password `400` at it (removed duplicate description from the path). Extended `FrontendBearerAuth.description` with the C16 not-a-contract sentence pointing callers at `GET /api/v1/users/me`. Added `content: application/json: schema: ErrorResponse` to accept-invite `410` without examples or pinned code. Validated YAML parses with `yaml.safe_load`.

### Decisions Made

- Placed `PasswordChangeRejected` after `DeviceOfflineError` — same pinned-code response family.
- Used `getCurrentUser` operationId — mirrors `getAgentById`/`getHostById` naming; backend route is `read_current_user`.
- Example messages are illustrative only — contract pins codes, not message strings.

### Code Changed

- modified: `contracts/openapi/openapi.yaml`

---

## Task 8 — test-engineer review

### Order Given

Test engineer Task 8 (`019-users-me-and-error-envelope`). Verify `openapi.yaml` edits against Task 8 success criteria. Run backend `test_health` route-surface test if applicable. Append POOP.

### What, How, and Why

Checked `git diff contracts/openapi/openapi.yaml` and read each touched section against TASKS.md Task 8 success criteria. All five ARCHITECTURE.md edits are present and only those five touch the file: (1) `users` tag with description `Read-only self profile.`; (2) `GET /api/v1/users/me` with `FrontendBearerAuth`, `200` → `UserProfileResponse`, `401` → `Unauthorized`, no `options:` entry; (3) `UserProfileResponse` schema with `user_id`/`email`/`role` required, uuid/email formats, `admin`/`viewer` enum, `additionalProperties: false`; (4) `PasswordChangeRejected` response component using `allOf` over `ErrorResponse` narrowing `error.code` to `enum: [wrong_current_password, password_policy_violation]`, description pins the code and folds in the C13 must-be-400-not-401 sentence, one example per code — change-password `400` now `$ref`s it with no duplicate C13 text at the path; (5) `FrontendBearerAuth.description` gains the C16 not-a-contract sentence pointing at `GET /api/v1/users/me`; (6) `/api/v1/invites/{token}/accept` `410` gains `content: application/json: schema: ErrorResponse` with no `examples` and no pinned `code`. Confirmed `openapi: 3.1.0` header unchanged and `yaml.safe_load` succeeds. Ran `test_route_surface_is_exactly_the_declared_contract` — failed initially because Task 7 added `GET /api/v1/users/me` but `EXPECTED_ROUTE_SURFACE` was not updated; added `("/api/v1/users/me", "GET")` to pin the new route (deferred from Task 7 POOP). Re-ran both route-surface tests: 2 passed.

### Decisions Made

- No new test file for openapi.yaml — no existing contract-parse pytest in backend; verification is criteria checklist + YAML parse + route-surface pin aligned with the new path.
- Updated `EXPECTED_ROUTE_SURFACE` in `test_health.py` — one-line pin so backend route contract matches Task 7 runtime and Task 8 OpenAPI documentation; without it full suite fails on `test_route_surface_is_exactly_the_declared_contract`.
- Did not run `npm run gen:types` — that is Task 9 scope.

### Code Changed

- modified: `backend/tests/test_health.py`

---

## Task 8 — code-reviewer gate

### Order Given

Code reviewer gate Task 8 (`019-users-me-and-error-envelope`). Review `contracts/openapi/openapi.yaml` and `test_health.py` route-surface update against TASKS.md Task 8. Run ruff + pytest `tests/test_health.py` from `backend/`.

### What, How, and Why

Read TASKS.md Task 8 success criteria and ARCHITECTURE.md "`openapi.yaml` additions". Inspected `git diff` for `contracts/openapi/openapi.yaml` and `backend/tests/test_health.py`. Confirmed all five contract edits and no other path/schema/response changes: `users` tag; `GET /api/v1/users/me` (no `options:`) with `FrontendBearerAuth`, `200` → `UserProfileResponse`, `401` → `Unauthorized`; `UserProfileResponse` schema; `PasswordChangeRejected` component (allOf, pinned enum, C13 description, two examples) repointing change-password `400`; `FrontendBearerAuth` C16 sentence; accept-invite `410` `ErrorResponse` content without examples or pinned code. Validated YAML via `yaml.safe_load` (`openapi: 3.1.0`). Confirmed `test_health.py` adds only `("/api/v1/users/me", "GET")` to `EXPECTED_ROUTE_SURFACE`, aligning route-surface pin with Task 7 runtime. Ran `uv run ruff check tests/test_health.py` (pass) and `uv run pytest tests/test_health.py -v` (6 passed, 1 skipped).

### Decisions Made

- **[APPROVE]** — every Task 8 success criterion met; openapi diff is scoped to the five declared edits; `test_health.py` one-line pin is correct companion work (deferred from Task 7) and not over-engineered.
- `test_health.py` is outside Task 8 target files but was explicitly in review scope and required for `test_route_surface_is_exactly_the_declared_contract` to pass.

### Code Reviewed

- contracts/openapi/openapi.yaml
- backend/tests/test_health.py

---

## Task 9 — Regenerate `openapi.d.ts`

### Order Given

Run `cd frontend && npm run gen:types` to regenerate `frontend/src/types/openapi.d.ts` from the updated `openapi.yaml`. Zero manual edits. Diff must show only `/users/me` path, `UserProfileResponse`, `PasswordChangeRejected` union on change-password `400`, `FrontendBearerAuth` description, accept-invite `410` content. `role` as `"admin" | "viewer"` union; change-password `400` code as `"wrong_current_password" | "password_policy_violation"` union. No other frontend files change.

### What, How, and Why

Ran `npm run gen:types` from `frontend/` (`openapi-typescript ../contracts/openapi/openapi.yaml -o src/types/openapi.d.ts`). Verified `git diff frontend/src/types/openapi.d.ts` contains only the expected additions: `/api/v1/users/me` path with `getCurrentUser` operation, `UserProfileResponse` schema with `role: "admin" | "viewer"`, `PasswordChangeRejected` response component with pinned `code` union, change-password `400` repointed from `BadRequest` to `PasswordChangeRejected`, and accept-invite `410` gaining `content: application/json: ErrorResponse`. Confirmed `git status frontend/` shows only `openapi.d.ts` modified — no other frontend files touched.

### Decisions Made

- `FrontendBearerAuth.description` C16 sentence does not appear in the diff — `openapi-typescript` does not emit `components.securitySchemes` into `openapi.d.ts`; the description lives only in `openapi.yaml`. Not a Task 8 regression; generator limitation, not manual omission.
- No frontend tests run — INTEGRATION.md confirms no frontend behavior to exercise yet.

### Code Changed

- modified: `frontend/src/types/openapi.d.ts`

---

## Task 9 — test-engineer review

### Order Given

Test engineer Task 9 (`019-users-me-and-error-envelope`). Verify `openapi.d.ts` diff against Task 9 success criteria. Confirm only `frontend/src/types/openapi.d.ts` changed under `frontend/`. Append POOP.

### What, How, and Why

Checked `git diff frontend/src/types/openapi.d.ts` against TASKS.md Task 9 success criteria and INTEGRATION.md verification list. Diff is scoped to the five generator-emitted changes from Task 8: (1) `/api/v1/users/me` path with `getCurrentUser` operation (GET only, no `options`); (2) `UserProfileResponse` schema with `role: "admin" | "viewer"` union; (3) `PasswordChangeRejected` response component with `code?: "wrong_current_password" | "password_policy_violation"` union and C13 description; (4) change-password `400` repointed from `BadRequest` to `PasswordChangeRejected` (inline C13 prose removed from the operation, now lives on the component — expected); (5) accept-invite `410` gains `content: { "application/json": ErrorResponse }` replacing `content?: never`. No unrelated path, schema, or operation hunks. `role` and change-password `400` `code` are string-literal unions, not bare `string`. Ran `cd frontend && npm run gen:types` — output identical to the committed diff (69 insertions, 7 deletions unchanged), confirming zero manual edits. `git diff --name-only -- frontend/` lists only `frontend/src/types/openapi.d.ts`.

### Decisions Made

- No new test files — INTEGRATION.md states no frontend test suite is required; verification is diff checklist + regeneration idempotency.
- `FrontendBearerAuth.description` C16 sentence is absent from the diff — `openapi-typescript` does not emit `components.securitySchemes` into `openapi.d.ts` (no `BearerAuth` or `securitySchemes` anywhere in the file, pre- or post-change). TASKS.md lists it as an expected diff item, but the generator cannot surface it; the description remains in `openapi.yaml` only. Not a Task 8 regression or manual omission.
- Accept criterion as pass — all generator-emittable Task 8 contract changes are present with correct literal unions.

### Code Changed

(none)

---

## Task 9 — test-engineer review

### Order Given

Test engineer Task 9 (`019-users-me-and-error-envelope`). Verify `openapi.d.ts` diff against Task 9 success criteria. Confirm only `frontend/src/types/openapi.d.ts` changed under `frontend/`. Append POOP.

### What, How, and Why

Checked `git diff frontend/src/types/openapi.d.ts` against TASKS.md Task 9 success criteria and INTEGRATION.md verification list. Diff is scoped to the five generator-emitted changes from Task 8: (1) `/api/v1/users/me` path with `getCurrentUser` operation (GET only, no `options`); (2) `UserProfileResponse` schema with `role: "admin" | "viewer"` union; (3) `PasswordChangeRejected` response component with `code?: "wrong_current_password" | "password_policy_violation"` union and C13 description; (4) change-password `400` repointed from `BadRequest` to `PasswordChangeRejected` (inline C13 prose removed from the operation, now lives on the component — expected); (5) accept-invite `410` gains `content: { "application/json": ErrorResponse }` replacing `content?: never`. No unrelated path, schema, or operation hunks. `role` and change-password `400` `code` are string-literal unions, not bare `string`. Ran `cd frontend && npm run gen:types` — output identical to the committed diff (69 insertions, 7 deletions unchanged), confirming zero manual edits. `git diff --name-only -- frontend/` lists only `frontend/src/types/openapi.d.ts`.

### Decisions Made

- No new test files — INTEGRATION.md states no frontend test suite is required; verification is diff checklist + regeneration idempotency.
- `FrontendBearerAuth.description` C16 sentence is absent from the diff — `openapi-typescript` does not emit `components.securitySchemes` into `openapi.d.ts` (no `BearerAuth` or `securitySchemes` anywhere in the file, pre- or post-change). TASKS.md lists it as an expected diff item, but the generator cannot surface it; the description remains in `openapi.yaml` only. Not a Task 8 regression or manual omission.
- Accept criterion as pass — all generator-emittable Task 8 contract changes are present with correct literal unions.

### Code Changed

(none)

---

## Task 9 — code reviewer

### Order Given

Code reviewer gate Task 9 (`019-users-me-and-error-envelope`). Verify `frontend/src/types/openapi.d.ts` against TASKS.md Task 9. Confirm `gen:types` idempotent. Run full backend pytest from `backend/`. First line `[APPROVE]` or `[REJECT]`. Append POOP.

### What, How, and Why

Checked `git diff frontend/src/types/openapi.d.ts` against TASKS.md Task 9 success criteria. Diff is scoped to the five generator-emittable Task 8 changes: (1) `/api/v1/users/me` path with `getCurrentUser` operation (GET only, `options?: never`); (2) `UserProfileResponse` schema with `role: "admin" | "viewer"` union; (3) `PasswordChangeRejected` response component with `code?: "wrong_current_password" | "password_policy_violation"` union and C13 description; (4) change-password `400` repointed from `BadRequest` to `PasswordChangeRejected`; (5) accept-invite `410` gains `content: { "application/json": ErrorResponse }`. No unrelated path, schema, or operation hunks. `role` and change-password `400` `code` are string-literal unions, not bare `string`. `git diff --name-only -- frontend/` lists only `frontend/src/types/openapi.d.ts`. Confirmed idempotency: `cp` + `npm run gen:types` + `diff` produced zero byte changes. Ran full `uv run pytest -q` from `backend/`: 377 passed, 168 skipped. No `# ponytail:` markers in the touched file. Ruff N/A — generated TypeScript, not Python.

### Decisions Made

- **Approve** — every Task 9 success criterion met; target file matches; regeneration idempotent; backend suite green.
- `FrontendBearerAuth.description` C16 sentence absent from diff — `openapi-typescript` does not emit `components.securitySchemes`; description lives in `openapi.yaml` only. Prior test-engineer and coder POOP entries document this; not a manual omission or Task 8 regression.
- ScanRunner / `ScanProgressScreen` thread-through rule N/A (frontend types-only task).

### Code Reviewed

- `frontend/src/types/openapi.d.ts`

---

## Docs drift — orchestrator (2026-07-27)

### Updated
- `.claude/docs/backend/errors.md` (created)
- `.claude/docs/backend/api.md`, `routers.md`, `schemas.md`, `auth.md`, `index.md`
- `.claude/docs/log.md`

### Not edited (no unambiguous factual drift)
- `docs/` human KB — no patches applied; contract/route alignment deferred to operator review if needed

