---
type: Module
title: Backend auth — sessions, tokens, passwords, routes
description: The wired auth subsystem — login/refresh/logout + password change/reset, JWT access tokens, rotating refresh-token families, the argon2 password policy, and the request-id/CORS middleware.
resource: backend/src/api/services/auth.py
tags: [backend, auth, jwt, sessions, passwords, middleware, cors]
timestamp: 2026-07-24T00:00:00Z
---

# Backend auth — sessions, tokens, passwords, routes

## Purpose

The auth subsystem (spec 016 / DMI-60) is the second route group wired over HTTP after the
[read path](/backend/routers.md). It authenticates users against the dormant-no-longer
[`users` identity table](/backend/models.md), issues short-lived **JWT access tokens** plus a
rotating **refresh-token family** stored in [`refresh_tokens`](/backend/models.md), and handles the
password lifecycle (change, forgot, reset) with an argon2 hash + policy screen. It spans a
router, four services, one FastAPI dependency, and the app-wide middleware. The agent→backend
ingest link is still unwired, but auth itself now runs in `main.py`.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `login()` | Verifies email + argon2 password, returns `(access_token, refresh_token, expires_in)`; issues a refresh family. Bad creds → `InvalidCredentialsError`, no tokens. | `backend/src/api/services/auth.py:42` |
| `refresh_session()` | Rotates the presented refresh token and mints a fresh access token (composes `rotate_refresh_token` + `create_access_token`). | `backend/src/api/services/auth.py:56` |
| `logout()` | Revokes the current refresh family; silently idempotent on an unknown/stale cookie. | `backend/src/api/services/auth.py:76` |
| `change_password()` | `WrongCurrentPasswordError` on bad current pw, `PasswordPolicyError` on weak new pw (both → 400, never 401); on success updates `password_hash`/`password_changed_at` without touching sessions. | `backend/src/api/services/auth.py:80` |
| `forgot_password()` | Sends a reset link **only** for a real account (via the `Mailer`) but never raises — no account enumeration. | `backend/src/api/services/auth.py:96` |
| `reset_password()` | Consumes the single-use token once (`InvalidResetTokenError` on missing/consumed/expired), validates policy, updates the password, and `revoke_all_refresh_tokens` to log out everywhere. | `backend/src/api/services/auth.py:115` |
| `create_access_token()` / `decode_access_token()` | PyJWT HS256; claims `sub`/`org_id`/`role`/`iat`/`exp`, exp from `ACCESS_TOKEN_TTL_MINUTES` (15), signed with `JWT_SIGNING_SECRET`. | `backend/src/api/services/tokens.py:20` |
| `issue_refresh_token()` | Raw = `secrets.token_urlsafe(32)`, stored as `sha256` hex; new `family_id`, `family_expires_at` = now + `REFRESH_TOKEN_TTL_DAYS` (7d). | `backend/src/api/services/tokens.py:42` |
| `rotate_refresh_token()` | Sets `rotated_at` on the old row and mints a new row in the same family with the **copied** `family_expires_at`; reuse of a rotated/revoked hash calls `_revoke_family` and raises `RefreshTokenError`; refresh past `family_expires_at` rejected. | `backend/src/api/services/tokens.py:73` |
| `revoke_refresh_token()` / `revoke_all_refresh_tokens()` | Revoke the current family / every one of a user's refresh rows (one UPDATE). | `backend/src/api/services/tokens.py:104` |
| `hash_password()` / `verify_password()` | argon2-cffi hash + verify. | `backend/src/api/services/passwords.py:36` |
| `validate_policy()` | Enforces the AUTH.md rules — min length 12, common/breached, repeated-char / keyboard-suffix / repeated-number, email/name/org substrings — raising a violation-listing `PasswordPolicyError`; includes the HIBP k-anonymity screen. | `backend/src/api/services/passwords.py:76` |
| `_check_hibp()` | SHA-1 range-API screen (first 5 chars sent, 35-char suffix matched locally), gated by `HIBP_ENABLED`; skipped (not failed) on timeout/HTTP error. | `backend/src/api/services/passwords.py:57` |
| `Mailer` / `LogMailer` | Protocol `send_reset_link(email, token)` + a dev impl that only logs the link (real provider is DMI-71). | `backend/src/api/services/mailer.py:10` |
| `require_user()` / `CallerIdentity` | FastAPI dependency validating the `Authorization: Bearer` JWT → caller identity (sub/org_id/role); missing/invalid/expired → 401. No role enforcement (DMI-61). | `backend/src/api/dependencies/auth.py:21` |
| auth routes | 6 POST routes (`login`/`refresh`/`logout`/`change-password`/`forgot-password`/`reset-password`) + OPTIONS preflights; set/clear the `dmitri_refresh` cookie. | `backend/src/api/routers/auth.py:62` |
| `_set_refresh_cookie()` / `_clear_refresh_cookie()` | `dmitri_refresh` cookie: `HttpOnly`, `Path=/api/v1/auth`, `SameSite=Lax`, `Max-Age`=7d, `Secure` per `REFRESH_COOKIE_SECURE`. | `backend/src/api/routers/auth.py:38` |
| `RequestIdMiddleware` | Reads inbound `X-Request-Id` or generates a uuid4, sets it on **every** response. | `backend/src/api/middleware.py:15` |
| `NoContentCorsMiddleware` | Subclasses Starlette `CORSMiddleware`, overriding `preflight_response` to return **204** (contract requires it) instead of the default 200. | `backend/src/api/middleware.py:38` |
| `build_cors_middleware_kwargs()` | Builds CORS kwargs from `CORS_ALLOWED_ORIGINS` — no-wildcard origins, `allow_credentials=true`, methods GET/POST/OPTIONS, headers Authorization/Content-Type/X-Request-Id, expose X-Request-Id. | `backend/src/api/middleware.py:45` |

## How it connects

- **Upstream** — the router and both middleware are registered in [`main.py`](/backend/api.md);
  `main.py` also answers `OPTIONS /api/v1/health` with 204 through the CORS middleware.
- **Config** — every knob (`JWT_SIGNING_SECRET`, the TTLs, `REFRESH_COOKIE_SECURE`,
  `CORS_ALLOWED_ORIGINS`, `RESET_TOKEN_TTL_MINUTES`, `HIBP_*`) is a `Settings` field — see
  [config](/backend/api.md).
- **Data** — refresh/reset rows live in [`models/session.py`](/backend/models.md)
  (`refresh_tokens`, `password_reset_tokens`), created by
  [migration `20260722_07`](/backend/migrations.md); users come from `identity.py`.
- `routers/auth.py` maps the service exception types to HTTP status: `InvalidCredentialsError` →
  401; `WrongCurrentPasswordError` + `PasswordPolicyError` → **400** (contract C13);
  `InvalidResetTokenError` per contract.

## Notes / gotchas

- **Refresh-token reuse revokes the whole family.** Presenting a rotated or revoked hash is treated
  as theft and kills every row sharing that `family_id`; `family_expires_at` is fixed at login and
  copied verbatim on each rotation, so the 7-day window never slides.
- **Both password errors are 400, not 401.** A wrong *current* password and a policy-violating
  *new* password are caller errors (contract C13); only a missing/invalid/expired Bearer is 401.
- **No enumeration.** `forgot_password` always yields 204 whether or not the email exists.
- **HIBP fails open.** A timeout or HTTP error on the pwnedpasswords range call skips the screen
  rather than blocking a password change; tests mock it and never hit the network.
- **DB-backed tests skip without local Postgres** — `test_auth_routes.py`, `test_auth_service.py`,
  `test_tokens.py`, `test_auth_migration.py` follow the project's Postgres-fixture skip pattern.

# Citations

[1] [specs/016-sessions-auth-routes](../../../specs/016-sessions-auth-routes/TRUTH.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [docs/adr/ADR-015-password-policy.md](../../../docs/adr/ADR-015-password-policy.md)
[4] [docs/roadmap/AUTH.md](../../../docs/roadmap/AUTH.md)
[5] [contracts/openapi/openapi.yaml](../../../contracts/openapi/openapi.yaml)
