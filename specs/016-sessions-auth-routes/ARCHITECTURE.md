# ARCHITECTURE — Sessions + auth routes (DMI-60)

## System context

This is a **backend FastAPI** feature under `backend/src/api/`. It adds the first
browser-facing routes to the app that until now served only agent ingest and frontend reads.
It builds on the identity tables shipped in DMI-58 (`orgs`, `users`, `invites` in
`models/identity.py`) and slots into the existing shape:

```
main.py (app) ──includes──> routers/auth.py ──calls──> services/auth.py ──> services/tokens.py
                                                        services/passwords.py
                                                        services/mailer.py (seam)
       │
       ├── middleware: RequestIdMiddleware + CORSMiddleware (wraps every response)
       └── db/session.py (get_session)  models/identity.py + models/session.py (new tables)
```

Routes match the **frozen** `contracts/openapi/openapi.yaml` `auth` tag exactly (the contract
uses the `/api/v1/auth/*` prefix). No business route behaviour changes.

## Data model / contracts

### New tables (Alembic migration `20260722_07`, `down_revision = "20260722_06"`)

**`refresh_tokens`** — one row per issued refresh token; rotation chains within a `family_id`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK → `users.id` | |
| `family_id` | UUID, indexed | shared by every token descended from one login |
| `token_hash` | str, unique, indexed | SHA-256 of the opaque token; raw token never stored |
| `family_expires_at` | datetime | login time + 7 days; **fixed**, copied to each rotation |
| `rotated_at` | datetime \| null | set when this token is retired by a refresh |
| `revoked_at` | datetime \| null | set on logout or family invalidation |
| `created_at` | datetime | |

Reuse detection: a refresh presenting a `token_hash` whose row has `rotated_at` or `revoked_at`
set ⇒ mark **every** row with that `family_id` revoked, reject the request.

No grace window: the backend does not distinguish a benign concurrent double-refresh from real
reuse — both kill the family. The frontend interceptor (ADR-008) must single-flight refresh so
legitimate callers never present the same rotated token twice. Not solved here.

Reset-password side effect: a successful `reset-password` revokes **every** `refresh_tokens` row
for that `user_id` (one `UPDATE … SET revoked_at WHERE user_id = … AND revoked_at IS NULL`), so
the recovery path logs the user out everywhere. `change-password` does not touch sessions.

Both `change-password` and `reset-password` set `users.password_hash` to the new hash **and**
update `users.password_changed_at = utc_now()` (column already exists on `User`, from DMI-58).

**`password_reset_tokens`** — mirrors the `invites` single-use pattern.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK → `users.id` | |
| `token_hash` | str, unique, indexed | SHA-256 of the emailed token |
| `expires_at` | datetime | short TTL (e.g. 1h) |
| `consumed_at` | datetime \| null | single-use gate |
| `created_at` | datetime | |

### Pydantic schemas (`schemas/auth.py`) — must match `openapi.yaml`

- `LoginRequest` { email, password }
- `LoginResponse` { access_token, token_type="bearer", expires_in } — returned by login,
  refresh, and (later, DMI-61) invite-accept.
- `ChangePasswordRequest` { current_password, new_password }
- `ForgotPasswordRequest` { email }
- `ResetPasswordRequest` { token, new_password }

Cookie `dmitri_refresh` is set/cleared via `Set-Cookie` (contract headers
`Set-Cookie-Refresh` / `Set-Cookie-Cleared`), not a body field. Attributes (per ADR-005 §2):
`HttpOnly`, `Path=/api/v1/auth`, `SameSite=Lax`, `Max-Age` = the fixed 7-day window, and `Secure`
gated by `REFRESH_COOKIE_SECURE` (true in prod, false for local HTTP dev). `SameSite=Lax` is
correct **only** while the SPA and API share a registrable domain (eTLD+1) — `localhost:5173`↔
`localhost:8000` in dev, `app.*`↔`api.*` under one domain in prod are same-site, so the credentialed
refresh `fetch` still carries the cookie. Deploying the API on a genuinely different site would
break refresh and force `SameSite=None; Secure` + CSRF handling — **out of scope for v1** (see
`docs/research/http-cookies-samesite.md`).

### JWT access token

- Library: **PyJWT**. HS256, signed with `JWT_SIGNING_SECRET`.
- Claims: `sub` (user id), `org_id`, `role`, `iat`, `exp` (~15 min). No refresh data in the JWT.
- Business routes validate the Bearer via a `require_user` dependency (defined here, minimally —
  the general role-enforcement middleware is DMI-61).

### Password hashing + policy

- Hashing: **argon2-cffi** (`argon2.PasswordHasher`) — modern default, no bcrypt 72-byte trap.
- `services/passwords.py`: `hash_password`, `verify_password`, and `validate_policy(password,
  *, email, name, org_name)` raising a policy error listing violations. Rules per AUTH.md:
  **minimum length 12** (matches `openapi.yaml`'s `minLength: 12` on `new_password` — the schema
  and the policy service must agree, so validate against the same constant rather than a
  separate number); reject a bundled common/breached list; reject patterns (repeated chars,
  keyboard/number suffixes, repeated number sequences); reject email/name/org substrings; screen
  against the HIBP Pwned-Passwords range API (k-anonymity: SHA-1 the candidate password, send the
  first 5 hex chars as a keyless `GET` to `api.pwnedpasswords.com/range/{prefix}` via the existing
  `httpx` dep, match the remaining 35 hex chars against the response locally). Gated by
  `HIBP_ENABLED` (default true) with a short timeout; if the call fails or times out, degrade
  gracefully and skip the breach check rather than blocking the request. **Birth-date rejection
  (listed in AUTH.md) is out of scope for v1**: there is no date-of-birth field anywhere in the
  identity model to check a password against, so `validate_policy` has no signal to test it with.
  Not a gap — nothing to wire it to.

### Env vars (add to `core/config.py` `Settings`)

`Settings()` is instantiated at import time in `main.py`, and `backend/tests/conftest.py` only
sets `DATABASE_URL` before the app/settings modules import — it does not set any auth vars.
Making `JWT_SIGNING_SECRET` required (no default) will break every existing test that imports
`main` or `Settings` unless `conftest.py` also sets it. Task 1 must therefore also: set
`JWT_SIGNING_SECRET` (and any other var without a default) in `conftest.py` alongside
`DATABASE_URL`; add `JWT_SIGNING_SECRET=` to `backend/.env.example`; and check
`backend/tests/test_settings.py`'s existing "defaults when env unset" test — it deletes a fixed
list of optional vars and instantiates `Settings()`, so it must either delete `JWT_SIGNING_SECRET`
too (and assert the resulting `ValidationError`) or the auth vars must be excluded from that
delete-loop. Do not let the required field regress the pre-existing suite.

| Var | Purpose | Default |
|-----|---------|---------|
| `JWT_SIGNING_SECRET` | HS256 signing key (SecretStr, required) | — |
| `ACCESS_TOKEN_TTL_MINUTES` | access JWT lifetime | 15 |
| `REFRESH_TOKEN_TTL_DAYS` | fixed refresh window | 7 |
| `REFRESH_COOKIE_SECURE` | `Secure` flag (false for local HTTP dev per ADR-005) | true |
| `CORS_ALLOWED_ORIGINS` | comma list; defaults to the two ADR-005 origins | localhost:5173 + prod |
| `RESET_TOKEN_TTL_MINUTES` | reset-link lifetime | 60 |
| `HIBP_ENABLED` | enable HIBP breach screening on password set/change | true |
| `HIBP_TIMEOUT_SECONDS` | timeout for the HIBP range API call | 2 |

### Middleware (DMI-56 deferral lands here)

- `RequestIdMiddleware` (`middleware.py`): read or generate `X-Request-Id`, set it on every
  response.
- Starlette `CORSMiddleware` configured from `x-cors`: allowed origins (no wildcard),
  `allow_credentials=true`, allow methods GET/POST/OPTIONS, allow headers Authorization/
  Content-Type/X-Request-Id, expose X-Request-Id.
- **Preflight status code**: stock `starlette.middleware.cors.CORSMiddleware` answers a real
  preflight (request carrying `Origin` + `Access-Control-Request-Method`) with **200**, and
  intercepts it before it reaches any route — the explicit `OPTIONS` handlers below never run
  for a real browser preflight. The contract requires **204**
  (`CorsPreflightNoContent`). `middleware.py` must subclass `CORSMiddleware` and override
  `preflight_response` to return 204 instead of 200 (same headers), so `OPTIONS /api/v1/health`
  and every `OPTIONS /api/v1/auth/*` route both return 204 with the CORS headers attached. The
  explicit `OPTIONS` route handlers in `routers/auth.py` and `main.py` exist only for requests
  that reach them without an `Origin` header (same-origin tooling, curl); they are not what a
  browser preflight hits.

### Email seam

`services/mailer.py`: a `Mailer` protocol with `send_reset_link(email, token)`; a `LogMailer`
dev implementation that logs the link. The real provider/domain is **DMI-71** — do not add one.

## New files and naming (mandatory)

| Layer | Path | Notes |
|-------|------|-------|
| Router | `backend/src/api/routers/auth.py` | 6 POST routes + OPTIONS preflights; `APIRouter()` |
| Router wiring | `backend/src/api/main.py` | `include_router(auth.router)`; add middleware; OPTIONS health |
| Schemas | `backend/src/api/schemas/auth.py` | request/response models matching `openapi.yaml` |
| Service | `backend/src/api/services/auth.py` | login/logout/change/forgot/reset orchestration |
| Service | `backend/src/api/services/tokens.py` | JWT encode/decode; refresh issue/rotate/reuse-detect/revoke |
| Service | `backend/src/api/services/passwords.py` | hash/verify + `validate_policy` |
| Service | `backend/src/api/services/mailer.py` | `Mailer` protocol + `LogMailer` seam (DMI-71 owns real one) |
| Deps (auth) | `backend/src/api/dependencies/auth.py` (or `routers/auth.py` local) | `require_user` |
| Middleware | `backend/src/api/middleware.py` | `RequestIdMiddleware`; CORS config helper |
| Models | `backend/src/api/models/session.py` | `RefreshToken`, `PasswordResetToken` SQLModel tables |
| Config | `backend/src/api/core/config.py` | new env vars above |
| Migration | `backend/alembic/versions/20260722_07_auth_sessions.py` | `down_revision = "20260722_06"` |
| Deps | `backend/pyproject.toml` | add `pyjwt`, `argon2-cffi` |
| Test | `backend/tests/test_auth_migration.py` | up/down + constraints (mirror `test_identity_migration.py`) |
| Test | `backend/tests/test_auth_routes.py` | login/refresh/logout/rotation/reuse flows |
| Test | `backend/tests/test_password_policy.py` | policy accept/reject cases, including HIBP-known password |
| Test | `backend/tests/test_cors_headers.py` | preflight + X-Request-Id per contract |

## Constraints

- **Match the frozen contract** — `contracts/openapi/openapi.yaml` is authoritative for paths,
  status codes, schemas, cookie names, and CORS. Contract ask **C13** covers *both* failure modes
  of `change-password`: a **wrong `current_password` and a policy-violating `new_password` are
  both 400, not 401**. A 401 here trips the SPA's silent-refresh interceptor and bounces the user
  to the login screen over a mistyped field — the whole point of C13. Only a missing/invalid/
  expired Bearer (the caller isn't authenticated at all) is 401 on this route. `forgot-password`
  always 204 (no account enumeration).
- **Scope fence** — do NOT build invite create/accept routes or general role middleware (DMI-61);
  no real email provider (DMI-71); do not invent the C15 wire codes (DMI-77).
- **No new infrastructure** — argon2 + PyJWT are libraries, not services. Refresh/reset state
  lives in Postgres. Flag `HUMAN_INFRA_REQUIRED` only if a real mail provider were in scope (it
  is not).
- **Style** — no comments/docstrings in new code, including tests. Reuse `get_session`,
  `utc_now`, and the existing SQLModel/pydantic-settings patterns; do not fork parallel ones.
- **The raw refresh/reset tokens are never stored** — only SHA-256 hashes; cookies carry the raw
  opaque value. Generate the raw value with `secrets.token_urlsafe(32)` (256-bit CSPRNG) for both
  token types; store `hashlib.sha256(raw).hexdigest()` in the uniquely-indexed `token_hash` column
  and look rows up by exact hash match. **SHA-256, not argon2** — these are high-entropy random
  tokens with no enumerable keyspace, so slow hashing (reserved for low-entropy passwords) would
  add per-request cost for zero gain. See `docs/research/opaque-token-generation-storage.md`.

## Testing expectations

- **Migration**: mirror `backend/tests/test_identity_migration.py` — Alembic upgrade→downgrade
  runs clean against the Postgres test DB; unique `token_hash`, FK, and single-use constraints
  reject bad rows. `conftest.py` already drives real Alembic.
- **Routes**: behaviour over snapshots — assert token issuance, that a rotated refresh is dead,
  that reuse revokes the family, that logout revokes, that the 7-day window is fixed, and that a
  weak password yields 400.
- **Policy**: table of accept/reject inputs covering each AUTH.md rule, including a test that a
  known-breached (HIBP) password is rejected. The HIBP range-API call must be **stubbed/mocked**
  in tests (e.g. monkeypatch the `httpx` call in `services/passwords.py`), never a live call to
  `api.pwnedpasswords.com` — a real network dependency in the suite is flaky and slow. Also add a
  case proving the *graceful-skip* path: the HIBP call raising/timing out does not block a
  policy-valid password.
- **CORS/headers**: a preflight request (with `Origin` **and**
  `Access-Control-Request-Method` headers set, matching what a real browser sends) to
  `OPTIONS /api/v1/health` and to at least one `/api/v1/auth/*` route → **204** with
  `Access-Control-Allow-*` matching `openapi.yaml`; every response carries `X-Request-Id`. See
  the "Preflight status code" note under Middleware above — a request without `Origin` +
  `Access-Control-Request-Method` will hit the explicit `OPTIONS` route handler instead of the
  CORS middleware and is not an equivalent test.
- `uv run pytest` and `uv run ruff check` pass on the touched scope.
