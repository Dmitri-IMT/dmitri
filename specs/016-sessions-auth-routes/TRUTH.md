# TRUTH — Sessions + auth routes (DMI-60)

## Narrative

Dmitri's backend now has identity tables (`orgs`, `users`, `invites` — shipped in DMI-58) but
no way to actually sign in. This feature adds the session machinery from AUTH.md Phase 1: an
operator logs in with email + password, receives a short-lived access token plus a
longer-lived refresh session, and stays signed in for up to 7 days without re-entering their
password. They can change their password, and — if locked out — reset it through an emailed
one-time link. It also lands the browser-facing HTTP hygiene (CORS + `X-Request-Id`) that was
deferred from the app-shell rebuild (DMI-56), because these are the first routes a browser will
ever call.

The security posture is decided, not open: access tokens are ~15 minutes, refresh lives in an
httpOnly cookie scoped to `/api/v1/auth/*` with a **fixed** 7-day lifetime (no sliding),
rotated on every refresh with reuse detection that kills the whole token family. Logout is a
real server-side revocation, not a client-side cookie wipe. Passwords must clear a strong
policy at every set point.

## Business rules

- **Access token**: JWT, ~15-minute lifetime, carried as `Authorization: Bearer` on business
  endpoints, returned in the login/refresh response body (client holds it in memory only).
- **Refresh session**: opaque token in an httpOnly cookie (`dmitri_refresh`), scoped to
  `/api/v1/auth`, **fixed 7-day lifetime measured from login** — never extended by refreshing.
  After 7 days the user must log in with a password again.
- **Refresh rotation + reuse detection**: every successful refresh issues a new refresh token
  and retires the old one. Presenting a retired token (reuse) invalidates the **entire token
  family** descended from that login. The backend stays strict — no grace window — so the
  **frontend MUST single-flight refresh** (one shared in-flight refresh, not one per 401);
  concurrent refreshes of the same cookie would otherwise look like reuse and log the user out.
  Owned by the ADR-008 interceptor, tracked in AUTH.md.
- **Logout**: server-side revocation of the current refresh token/family plus a cleared cookie.
  A revoked refresh token is rejected on any later use.
- **Password policy** (enforced at every set/change/reset point): minimum length; reject
  common/breached passwords (screened against known-breached corpora via HIBP); reject obvious
  patterns (repeated characters, simple keyboard/number suffixes, repeated number sequences);
  reject the user's own email/name and the org name. Per AUTH.md.
- **Forgot/reset**: `forgot-password` always responds success (never reveals whether an account
  exists) and, for a real account, sends a one-time reset link. `reset-password` consumes the
  link once and applies the full password policy. A successful reset **revokes every refresh
  token family** for that user (full log-out-everywhere) — the reset path is account recovery, so
  any session an attacker still holds dies with it. A voluntary `change-password` leaves existing
  sessions untouched (broader "log out other devices" is Phase 2).
- **HTTP hygiene**: every API response carries an `X-Request-Id`. Browser CORS is restricted to
  the two decided origins; `OPTIONS` preflights are answered and `Access-Control-Allow-*`
  headers appear on responses, matching the frozen `contracts/openapi/openapi.yaml`.

## User stories

1. As an operator, I want to log in with email + password and stay signed in for up to 7 days
   without re-entering it, so daily use is painless but bounded.
2. As an operator who forgot my password, I want to reset it via an emailed one-time link, so I
   can regain access without an admin.
3. As an operator, I want to voluntarily change my password, so I can rotate my credentials on
   my own schedule.
4. As the frontend, I want CORS preflights answered and a request id on every response, so the
   browser can call the API and requests are traceable.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Login issues tokens | a valid email + password | I `POST /auth/login` | I get a 200 with an access JWT in the body and an httpOnly refresh cookie set |
| Refresh rotates | a valid refresh cookie | I `POST /auth/refresh` | I get a new access JWT and a rotated refresh cookie; the previous refresh token no longer works |
| Reuse kills the family | a refresh token that was already rotated away | I present it again to `/auth/refresh` | it is rejected and every token in that login's family is invalidated |
| Logout revokes | a logged-in session | I `POST /auth/logout` then present the old refresh cookie | logout succeeds (204) and the old refresh is rejected |
| Fixed 7-day window | a session created 7+ days ago | I `POST /auth/refresh` | it is rejected regardless of how recently I last refreshed |
| Bad credentials | a wrong password | I `POST /auth/login` | I get 401 with no tokens |
| Voluntary change succeeds | an authenticated user | I `POST /auth/change-password` with correct current + policy-valid new password | it succeeds (204) |
| Weak password rejected | an authenticated user | I change to a password that violates the policy | I get 400 (not 401) and the password is unchanged |
| Breached password rejected | an authenticated user | I change to a password found in the HIBP breach corpus | I get 400 (not 401) and the password is unchanged |
| Forgot never enumerates | any email (account or not) | I `POST /auth/forgot-password` | I always get 204; a reset link is produced only for a real account |
| Reset consumes token | a valid reset link | I `POST /auth/reset-password` once, then again with the same token | the first succeeds; the second is rejected |
| Reset logs out everywhere | a user with a live refresh session | I complete `POST /auth/reset-password` | every refresh family for that user is revoked; the old refresh cookie no longer refreshes |
| Preflight matches contract | a browser preflight | I `OPTIONS /api/v1/health` | I get 204 with `Access-Control-Allow-*` headers matching `openapi.yaml` |
| Request id everywhere | any request | I call any API route | the response carries an `X-Request-Id` header |
| Suite green | the touched scope | I run `uv run pytest` and `uv run ruff check` | both pass |

## Out of scope (v1)

- **Invite creation and acceptance** endpoints (`/api/v1/invites*`) and business-route role
  enforcement middleware — owned by **DMI-61**.
- **Real transactional email delivery** (provider, sending domain, SPF/DKIM/DMARC) — owned by
  **DMI-71**. This feature builds the forgot/reset flow behind a mail-sending seam; dev may log
  the link. Do not treat console logging as a shippable email flow.
- **Reset-password error-code disambiguation** (dead token vs weak password, C15) — owned by
  **DMI-77**. Implement the behaviour these routes already promise, but do not invent the
  unspecified wire codes here.
- No MFA, logout-everywhere, idle timeout, or session cap (Phase 2).
- No frontend pages (Frontend MVP epic).

## Related specs

- Implementation: `ARCHITECTURE.md`
- Product decisions: `docs/roadmap/AUTH.md` (Phase 1), `docs/adr/ADR-005-security-model.md`
- Frozen contract: `contracts/openapi/openapi.yaml` (`auth` tag, `x-cors`)
- Execution ledger: `POOP.md` (written during orchestration)
