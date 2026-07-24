# Tasks — Sessions + auth routes (`016-sessions-auth-routes`)

12 tasks. **Unblocked now: #1, #2, #5, #6**

Split scope finely: config/deps → models+migration → services → middleware/deps → router+wiring → tests.

---

## Task 1: Config env vars + auth dependencies
- **Description**: Add the auth `Settings` fields to `core/config.py` and the two runtime libs to `pyproject.toml`, per the ARCHITECTURE.md "Env vars" table and deps row. Reuse the existing pydantic-settings pattern; `JWT_SIGNING_SECRET` is a required `SecretStr`. Because `Settings()` is instantiated at import time and `backend/tests/conftest.py` only sets `DATABASE_URL` before importing `main`/`Settings`, making `JWT_SIGNING_SECRET` required without also updating `conftest.py` will break the entire existing test suite — this task must also set `JWT_SIGNING_SECRET` in `conftest.py`, add it to `backend/.env.example`, and reconcile `backend/tests/test_settings.py`'s "defaults when env unset" test (which currently `delenv`s a fixed list of optional vars and instantiates `Settings()`).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/core/config.py`, `backend/pyproject.toml`, `backend/tests/conftest.py`, `backend/.env.example`, `backend/tests/test_settings.py`]
- **Success Criteria**: `Settings` exposes `JWT_SIGNING_SECRET` (SecretStr, required), `ACCESS_TOKEN_TTL_MINUTES=15`, `REFRESH_TOKEN_TTL_DAYS=7`, `REFRESH_COOKIE_SECURE=true`, `CORS_ALLOWED_ORIGINS` (comma list defaulting to the two ADR-005 origins), `RESET_TOKEN_TTL_MINUTES=60`, `HIBP_ENABLED=true`, `HIBP_TIMEOUT_SECONDS=2`; `pyjwt` and `argon2-cffi` added to `pyproject.toml`; `conftest.py` sets `JWT_SIGNING_SECRET` so the full existing suite still passes; `.env.example` documents the new vars; `uv run pytest` (full suite, not just new scope) and `uv run ruff check` both pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Session models + Alembic migration
- **Description**: Add `RefreshToken` and `PasswordResetToken` SQLModel tables and the migration creating them, per the ARCHITECTURE.md data-model tables. Mirror the DMI-58 identity table + migration style; `down_revision = "20260722_06"`. Includes the migration test mirroring `test_identity_migration.py`.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/session.py`, `backend/alembic/versions/20260722_07_auth_sessions.py`, `backend/tests/test_auth_migration.py`]
- **Success Criteria**: `refresh_tokens` (id, user_id FK→users, family_id indexed, token_hash unique+indexed, family_expires_at, rotated_at nullable, revoked_at nullable, created_at) and `password_reset_tokens` (id, user_id FK→users, token_hash unique+indexed, expires_at, consumed_at nullable, created_at) exist; Alembic upgrade→downgrade runs clean on the Postgres test DB; unique `token_hash` and FK constraints reject bad rows; test passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Password service + policy tests
- **Description**: Implement `services/passwords.py` with `hash_password`/`verify_password` (argon2-cffi) and `validate_policy(password, *, email, name, org_name)` enforcing every AUTH.md rule (minimum length **12**, matching the contract's `minLength`), including the HIBP k-anonymity range-API screen (gated by `HIBP_ENABLED`, graceful skip on timeout/failure). Birth-date rejection (AUTH.md) is explicitly out of scope — no DOB field exists to check against. Add the policy accept/reject test table incl. a known-breached input, per ARCHITECTURE.md. The HIBP call must be mocked/stubbed in tests, never a live call to `api.pwnedpasswords.com`.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/passwords.py`, `backend/tests/test_password_policy.py`]
- **Success Criteria**: valid passwords hash/verify round-trip; `validate_policy` raises a violation-listing error for too-short (<12), common/breached, repeated-char/keyboard-suffix/repeated-number patterns, and email/name/org substrings; HIBP screen matches the 35-char suffix locally (mocked in tests) and is skipped, not failed, when the call errors/times out (test proves this with a mocked timeout/exception); test table covers each rule incl. an HIBP-known password; no test makes a live network call; `uv run pytest`/`ruff` pass on scope.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Token service (JWT + refresh rotation/reuse/revoke)
- **Description**: Implement `services/tokens.py`: JWT encode/decode (PyJWT HS256, claims `sub`/`org_id`/`role`/`iat`/`exp`), and refresh-token issue/rotate/reuse-detect/revoke over `RefreshToken`. Raw token = `secrets.token_urlsafe(32)`, stored as `sha256(raw)` hex; `family_expires_at` fixed at login+7d and copied on rotation; reuse of a rotated/revoked hash revokes the whole family; per ARCHITECTURE.md.
- **Dependencies**: Task 1, Task 2
- **Target Files**: [`backend/src/api/services/tokens.py`]
- **Success Criteria**: access JWT encodes/decodes with the specified claims and ~15-min exp; issuing a refresh creates a family row; rotation retires the old row and copies the fixed `family_expires_at`; presenting a rotated/revoked hash revokes every row of that `family_id`; refresh past `family_expires_at` is rejected; revoke marks rows revoked; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Mailer seam
- **Description**: Add `services/mailer.py` with a `Mailer` protocol (`send_reset_link(email, token)`) and a `LogMailer` dev implementation that logs the link, per ARCHITECTURE.md. No real provider (DMI-71).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/mailer.py`]
- **Success Criteria**: `Mailer` protocol defines `send_reset_link`; `LogMailer` implements it by logging the link and nothing else; no network/provider code; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Auth Pydantic schemas
- **Description**: Add request/response models in `schemas/auth.py` matching the frozen `openapi.yaml` `auth` tag: `LoginRequest`, `LoginResponse`, `ChangePasswordRequest`, `ForgotPasswordRequest`, `ResetPasswordRequest`, per ARCHITECTURE.md.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/schemas/auth.py`]
- **Success Criteria**: all five schemas exist with fields matching `contracts/openapi/openapi.yaml` (`LoginResponse` = access_token/token_type="bearer"/expires_in); field names/types match the contract exactly; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 7: Auth service orchestration
- **Description**: Implement `services/auth.py` orchestrating login/logout/change-password/forgot-password/reset-password over the token, password, mailer services and the session/identity models, per TRUTH.md business rules and ARCHITECTURE.md. Reset consumes the single-use token, applies the full policy, and **revokes every refresh family for the user**; forgot always succeeds without enumeration; change-password leaves sessions untouched. Change-password and reset-password both distinguish a **wrong current password** and a **policy-violating new password** as caller errors (contract C13 — both are 400 at the route layer, never 401) from an unauthenticated caller; both also update `users.password_changed_at`.
- **Dependencies**: Task 2, Task 3, Task 4, Task 5
- **Target Files**: [`backend/src/api/services/auth.py`]
- **Success Criteria**: login verifies credentials and returns an access token + issues a refresh family (bad credentials → auth error, no tokens); logout revokes the current family; change-password checks current password and raises a distinguishable error for (a) wrong current password and (b) policy-violating new password (both must map to 400 in the router, not 401), succeeding only updates `password_hash`/`password_changed_at` without touching sessions; forgot-password produces a reset link only for a real account but signals success either way; reset-password consumes the token once, validates policy, updates `password_hash`/`password_changed_at`, and issues one `UPDATE` revoking all of the user's refresh rows; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: `require_user` dependency
- **Description**: Add the minimal `require_user` FastAPI dependency validating the `Authorization: Bearer` JWT and exposing the caller identity (sub/org_id/role), per ARCHITECTURE.md (general role middleware is DMI-61, out of scope).
- **Dependencies**: Task 4
- **Target Files**: [`backend/src/api/dependencies/auth.py`]
- **Success Criteria**: a valid Bearer resolves to the caller identity; missing/invalid/expired Bearer yields 401; no role-enforcement logic beyond identity resolution; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Request-id + CORS middleware
- **Description**: Add `middleware.py` with `RequestIdMiddleware` (read or generate `X-Request-Id`, set on every response) and a CORS middleware built from `CORS_ALLOWED_ORIGINS`/`x-cors`, per ARCHITECTURE.md. Stock `starlette.middleware.cors.CORSMiddleware` answers real preflights (requests with both `Origin` and `Access-Control-Request-Method`) with status 200 and intercepts them before any route runs — the contract requires 204. Subclass `CORSMiddleware` and override `preflight_response` to return 204 (same headers) instead of 200.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/middleware.py`]
- **Success Criteria**: `RequestIdMiddleware` echoes an inbound `X-Request-Id` or generates one and sets it on the response; CORS middleware yields no-wildcard origins, `allow_credentials=true`, methods GET/POST/OPTIONS, headers Authorization/Content-Type/X-Request-Id, expose X-Request-Id; a request carrying `Origin` + `Access-Control-Request-Method` gets a **204** preflight response (not the Starlette default 200) with the CORS headers attached; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 10: Auth router + app wiring
- **Description**: Add `routers/auth.py` (6 POST routes + OPTIONS preflights matching the frozen contract, setting/clearing the `dmitri_refresh` cookie with `HttpOnly`/`Path=/api/v1/auth`/`SameSite=Lax`/`Max-Age`=7d/`Secure` per `REFRESH_COOKIE_SECURE`) and wire it in `main.py` (include router, add both middleware, answer `OPTIONS /api/v1/health` 204), per ARCHITECTURE.md. `change-password` maps **both** a wrong current password and a policy-violating new password to 400 (contract C13) — only a missing/invalid/expired Bearer is 401 on this route.
- **Dependencies**: Task 6, Task 7, Task 8, Task 9
- **Target Files**: [`backend/src/api/routers/auth.py`, `backend/src/api/main.py`]
- **Success Criteria**: `/api/v1/auth` login/refresh/logout/change-password/forgot-password/reset-password paths, status codes, and cookie names match `openapi.yaml`; change-password wrong-current-password AND policy failure are both 400 (not 401); forgot-password always 204; the refresh cookie carries the pinned attributes; router + middleware registered in `main.py`; a real preflight (`Origin` + `Access-Control-Request-Method`) to `OPTIONS /api/v1/health` returns 204 via the CORS middleware; `ruff` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 11: Auth route flow tests
- **Description**: Add `test_auth_routes.py` asserting behaviour (not snapshots) across the TRUTH.md acceptance table: login issues tokens, refresh rotates and kills the old token, reuse revokes the family, logout revokes, the 7-day window is fixed, bad credentials 401, weak password 400, wrong current password on change-password 400 (not 401, contract C13), forgot-password always returns 204 for both a real and a nonexistent email (no enumeration), reset-password consumes its token once (second use with the same token is rejected), and a successful reset revokes all refresh families.
- **Dependencies**: Task 10
- **Target Files**: [`backend/tests/test_auth_routes.py`]
- **Success Criteria**: tests cover each of those scenarios and pass under `uv run pytest`; a rotated refresh is proven dead; reuse is proven to revoke the family; reset is proven to log the session out everywhere; change-password with a wrong current password is proven to return 400; forgot-password is proven to return 204 identically for a real and a fake email; a reset token is proven single-use (first call succeeds, replay with the same token is rejected).
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 12: CORS + request-id tests
- **Description**: Add `test_cors_headers.py` asserting a real preflight request (sending both `Origin` and `Access-Control-Request-Method` headers, as a browser does — a bare `OPTIONS` without these hits the route handler, not the CORS middleware, and is not an equivalent test) to `OPTIONS /api/v1/health` → 204 with `Access-Control-Allow-*` matching `openapi.yaml`, and that every response carries `X-Request-Id`, per ARCHITECTURE.md.
- **Dependencies**: Task 9, Task 10
- **Target Files**: [`backend/tests/test_cors_headers.py`]
- **Success Criteria**: a preflight sent with `Origin` + `Access-Control-Request-Method` returns 204 with allow-origin/credentials/methods/headers matching the contract; an inbound `X-Request-Id` is echoed and a missing one is generated; tests pass under `uv run pytest`.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ─┬─> #3 ─┐
    ├─> #4 ─┼─> #7 ─┐
    └─> #9  │       ├─> #10 ─┬─> #11
#2 ─────────┴─> #8 ─┘        └─> #12
#5 ─────────────> #7         (#9 ─> #12)
#6 ─────────────> #10
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Config env vars + auth dependencies | COMPLETED |
| 2 | Session models + Alembic migration | COMPLETED |
| 3 | Password service + policy tests | COMPLETED |
| 4 | Token service (JWT + refresh rotation/reuse/revoke) | COMPLETED |
| 5 | Mailer seam | COMPLETED |
| 6 | Auth Pydantic schemas | COMPLETED |
| 7 | Auth service orchestration | COMPLETED |
| 8 | `require_user` dependency | COMPLETED |
| 9 | Request-id + CORS middleware | COMPLETED |
| 10 | Auth router + app wiring | COMPLETED |
| 11 | Auth route flow tests | COMPLETED |
| 12 | CORS + request-id tests | COMPLETED |
