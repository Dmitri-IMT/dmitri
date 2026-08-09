# ARCHITECTURE — Account removal API (DMI-102, backend only)

Implements [`TRUTH.md`](TRUTH.md). Decision of record: [`ADR-017`](../../docs/adr/ADR-017-account-removal.md),
summarised in [`AUTH.md`](../../docs/roadmap/AUTH.md) § Account removal. Nothing here re-decides
either document; where the ADR is silent, the choice is named as such below.

**Scope:** `backend/` only. No `hardware-agent/` work, no `frontend/` work, no cross-layer
contract — hence no `INTEGRATION.md` and no `DESIGN.md`.

**CLAUDE.md ScanRunner rule — not applicable.** This feature touches no part of the scan
pipeline; `ScanRunner` and `ScanProgressScreen` live in `hardware-agent/` and neither they nor
`ScanOrchestrator` are read, called, or parameterised by anything in this spec.

---

## System context

Two new destructive routes on the existing FastAPI surface, inside the auth/identity slice of
the backend. The pipeline they sit in is the browser request path, not the scan path:

```
SPA  →  Bearer access token
        →  api/main.py (RequestIdMiddleware, CORSMiddleware, error-envelope handlers)
          →  api/routers/users.py
            →  api/dependencies/auth.py   require_user_row  |  require_admin
              →  api/services/users.py    admin count + hard DELETE
                →  Postgres: DELETE FROM users … ON DELETE CASCADE
                   → refresh_tokens   (this IS the session teardown)
                   → password_reset_tokens
```

Existing pieces reused unchanged:

| Piece | Where | Role here |
|---|---|---|
| `require_user_row` | `backend/src/api/dependencies/auth.py:42` | Loads the caller's `User` row; already 401s when the row is gone — which is exactly the post-deletion behaviour TRUTH's "unauthenticated-proof" row demands |
| `require_admin` | `backend/src/api/dependencies/auth.py:54` | Gates the remove-someone-else route using the existing JWT role claim. Its known post-removal authorization window is DMI-104 |
| `ApiError` + global handler | `backend/src/api/errors.py:21`, `backend/src/api/main.py:62` | Shapes the 409 into the pinned `ErrorResponse` envelope |
| Org-scoping → 404 | The `get_host_detail` pattern: the query filters `org_id` in SQL and the router raises `404` on `None` — `backend/src/api/services/read.py:74` + `backend/src/api/routers/hosts.py:31` | The foreign-org target must use the **same shape**: scope the lookup by `caller.org_id`, 404 on miss. Never a role/ownership branch producing 403 |

Nothing in the auth service (`issue_session`, `revoke_*`) is called. Per ADR-017 § 1 the FK
cascade *is* the session teardown; per ADR-017 § 6 neither route touches the refresh cookie
(no `Set-Cookie`, no `response.delete_cookie`).

---

## Data model / contracts

### 1. The cascade does **not** exist today — a migration is in scope

Verified in the code, not assumed:

- `backend/src/api/models/session.py:15` and `:27` declare `user_id: UUID = Field(foreign_key="users.id")`
  with **no `ondelete`**.
- `backend/alembic/versions/20260722_07_auth_sessions.py:46,64` create both FKs as bare
  `sa.ForeignKeyConstraint(["user_id"], ["users.id"])` — Postgres default `NO ACTION`.
- There are **no `Relationship()` declarations anywhere** in `backend/src/api/models/` (grep
  confirms), so there is no ORM-level cascade either.

Consequence: `DELETE FROM users` today raises `ForeignKeyViolation` for any user with a live
session. Both constraints must be recreated with `ON DELETE CASCADE`.

| Table | Constraint (Postgres default name for an unnamed FK) | Change |
|---|---|---|
| `refresh_tokens` | `refresh_tokens_user_id_fkey` | drop, recreate `ON DELETE CASCADE` |
| `password_reset_tokens` | `password_reset_tokens_user_id_fkey` | drop, recreate `ON DELETE CASCADE` |

`downgrade()` recreates both without `ondelete`. The implementer must confirm the live
constraint names against `dmitri_test` before writing the migration rather than trusting the
default-naming rule (there is no `naming_convention` on the metadata).

The models must be updated to match, or Alembic autogenerate drifts:
`Field(foreign_key="users.id", ondelete="CASCADE")` (SQLModel ≥ 0.0.21 is pinned in
`backend/pyproject.toml:18`, so the `ondelete=` kwarg is available).

### 2. The runtime role has no `DELETE` on `users` — also in scope

`backend/alembic/versions/20260716_02_identity_schema.py:88` grants only
`SELECT, INSERT, UPDATE` on the identity tables to `dmitri_runtime`, and the role is `BYPASSRLS`
but not superuser. The same migration must therefore:

```
GRANT DELETE ON TABLE public.users TO dmitri_runtime
```

`refresh_tokens` / `password_reset_tokens` need **no** `DELETE` grant: Postgres performs
`ON DELETE CASCADE` through the referential-integrity trigger, which is not subject to the
caller's privileges on the referencing table. `downgrade()` revokes it.

This grant is asserted by `RUNTIME_GRANTS_BY_TABLE` in `backend/tests/test_migrations.py:38`,
which currently expects the default `{SELECT, INSERT, UPDATE}` for every table but
`agent_nonces` — that map must gain `"users": {"SELECT", "INSERT", "UPDATE", "DELETE"}` or
`test_live_migration_round_trip_and_security` fails.

### 3. Deletion goes through the ORM session, not raw SQL

`session.delete(user); session.commit()` on the `User` instance already loaded by
`require_user_row` (self route) or by the org-scoped lookup (admin route). Because there are no
`Relationship()`s, SQLAlchemy emits a single `DELETE FROM users WHERE id = …` and does **not**
attempt to null out or pre-delete dependents — the database does the cascade. No
`session.exec(delete(...))` and no `text()` is needed; this matches how every other write in
`services/` mutates rows.

### 4. Routes and status codes

| Route | Auth dependency | Success | Failures |
|---|---|---|---|
| `DELETE /api/v1/users/me` | `require_user_row` (any role) | `204`, empty body | `401 unauthorized` (no/blank/dead token — from the dependency), `409 last_admin` |
| `DELETE /api/v1/users/{user_id}` | `require_admin` | `204`, empty body | `401 unauthorized`, `403 forbidden` (viewer, from the dependency), `409 self_target` (the caller's own id), `404 not_found` (unknown id **or** foreign-org id) |

Each route's authorization is a single unconditional dependency — no branching inside one
handler (ADR-017 § 2). Self-targeting on `/{user_id}` is refused as **`409 self_target`**
(decided 2026-08-08 at the approval gate; ADR-017 says only "refused"). The caller can see their
own row on the Users screen, so `404` would deny the existence of something demonstrably visible
and force DMI-90 to word a lie; `409` matches how ADR-017 § 3 justifies `last_admin` — the
caller holds every permission, it is the request's shape against current state that refuses. A
single request therefore leaves its caller behind, so no admin count is taken there (ADR-017 § 3
rule 1). Per TRUTH's explicit v1 fence, this route does not serialize the improbable case of two
admins concurrently targeting each other. Ordering inside the handler: compare
`user_id == caller.sub` **before** the query, so the self-target answer never depends on a lookup.
The target lookup is scoped with `caller.org_id`.

The claims-only gate leaves the known DMI-104 authorization window after removal. This feature
uses the existing dependency rather than adding a temporary partial replacement; DMI-104 owns
the complete row-backed authorization change across all affected routes.

### 4a. Route declaration order (trap)

`DELETE /api/v1/users/me` **must be declared before** `DELETE /api/v1/users/{user_id}` in
`routers/users.py`. FastAPI matches in registration order; with `{user_id}` first, a request to
`/users/me` is matched against the uuid path param and fails validation with `422` instead of
deleting the caller's account. The existing `GET` on `/users/me` is already first in the file —
keep both `/me` operations above the parameterised path.

### 5. The `last_admin` and `self_target` error codes

Two new pinned codes, both `409` via `ApiError(409, …, code=…)`, raised **in the router
function** (the contract-fidelity gate AST-scans route bodies for literal `ApiError(...)` calls;
raising them in the service would not be seen). For `last_admin` the service raises a domain
exception and the router maps it — exactly the `create_invite` → `PendingInviteError` →
`ApiError(409, …, code="invite_already_pending")` pattern at
`backend/src/api/routers/invites.py:53`. `self_target` never reaches the service: it is a
router-level guard on the path parameter.

| Code | Route | Message |
|---|---|---|
| `last_admin` | `DELETE /users/me` | `Add another admin before removing your account.` |
| `self_target` | `DELETE /users/{user_id}` | `Remove your account from Settings instead.` |

### 5a. The ordinary last-admin check

For an admin removing themselves, count admins in the caller's organisation. If the count is
`1`, raise `LastAdminError`; otherwise delete the caller. A viewer skips the count because the
invariant concerns admins only. Role is read from the **DB row**, not the JWT —
`require_user_row` already returns the row, and `test_users_me_role_from_row_not_jwt` pins that
precedent.

Use an ordinary count under the existing **READ COMMITTED** transaction. Do not add row locks,
advisory locks, isolation changes, retries, or multi-connection coordination in this feature.
TRUTH records the resulting simultaneous self-removal and peer cross-removal races; DMI-105 owns
one complete concurrency solution across both routes.

**An admin may remove a peer admin** (TRUTH, decided 2026-08-08). `/{user_id}` needs no count
for an ordinary request: it refuses self-targeting, so that request leaves its caller as an admin.
Two admins → one ordinary request removes the other → survivor is sole admin, which is legal.
Concurrent self-removal and cross-removal are both deliberately outside v1 and receive no
partial locking here.

### 6. Contract changes — `contracts/openapi/openapi.yaml`

| Addition | Detail |
|---|---|
| `delete` on existing `/api/v1/users/me` (path exists at line 906) | `operationId: deleteCurrentUser`, `security: [FrontendBearerAuth: []]`, responses `204` (description + the four standard headers used by the sibling `get`), `401 → #/components/responses/Unauthorized`, `409 → #/components/responses/LastAdminConflict` |
| New path `/api/v1/users/{user_id}` | `delete`, `operationId: deleteUser`, `user_id` path param (`type: string, format: uuid`), responses `204`, `401 → Unauthorized`, `403 → Forbidden`, `404 → NotFound`, `409 → #/components/responses/SelfTargetConflict` |
| New `components/responses/LastAdminConflict` | Modelled byte-for-byte on `InviteAlreadyPending` (line 1519): `allOf: [ErrorResponse, {error.code enum: [last_admin]}]` plus the exact user-facing message from § 5. Description must state that the caller holds every permission and it is the org's state that refuses (RFC 9110 § 15.5.10) |
| New `components/responses/SelfTargetConflict` | Same shape: `allOf: [ErrorResponse, {error.code enum: [self_target]}]` plus the exact user-facing message from § 5. Description states that self-removal is available from Settings and contains no API-path instructions |
| `Access-Control-Allow-Methods` header example (line 1165) | Currently `GET, POST, OPTIONS` — must become `GET, POST, DELETE, OPTIONS` |

No `options` twin is added for either route. `/api/v1/users/me` has none today and the
CORSMiddleware answers its preflight; the explicit `options` operations in the contract exist
only for the cookie-credentialed `/auth/*` and `/invites/*` routes.

### 7. CORS — `DELETE` is not currently allowed (gap not covered by the ADR)

`backend/src/api/middleware.py:54` sets `"allow_methods": ["GET", "POST", "OPTIONS"]`. A
browser preflight for `DELETE /api/v1/users/me` would be rejected before the route is reached,
so the SPA work this unblocks (DMI-90, DMI-103) would fail in the browser while every backend
test passed. Add `"DELETE"` to that list. This is a one-line change with no security widening
beyond the two routes' own auth gates.

### 8. No schema additions

Both routes return `204` with an empty body and take no request body, so
`backend/src/api/schemas/users.py` needs **no** new model. `UserProfileResponse` is unchanged.

### 9. Claims-only authorization after removal — known bug DMI-104, out of scope

The business reads use claims-only `require_user`: `findings.py:25`, `scans.py:62,79`,
`commands.py:20`, `hosts.py:26,35`. Admin mutations also use claims-only `require_admin`, including
invite creation (`invites.py:39`) and scan-command creation (`agents.py:43`). These gates do not
re-check that the caller's row exists. A removed member's access token can therefore keep reading
organisation data for up to 15 minutes; a removed admin's token can also retain admin capabilities
for that period.

Removal cuts the authorization window from seven days to fifteen minutes; it does not close it.
TRUTH records this honestly rather than claiming all access ends immediately. Closing it means
making the shared user and admin gates row-backed, which also invalidates existing route tests
that mint tokens with `uuid4()` subjects and no user row. That is **DMI-104**, sequenced after
this issue. DMI-102 adds no temporary regression test that treats the known bug as expected
behavior.

## New files and naming (mandatory)

Every file an implementer creates or touches. Paths are exact and relative to the repo root.

| # | Kind | Path | Change |
|---|---|---|---|
| 1 | Model | `backend/src/api/models/session.py` | `RefreshToken.user_id` and `PasswordResetToken.user_id` gain `ondelete="CASCADE"` |
| 2 | Migration (**new**) | `backend/alembic/versions/20260808_15_user_delete_cascade.py` | `revision = "20260808_15"`, `down_revision = "20260804_14"` (current head — verified). Recreates both FKs with `ON DELETE CASCADE`; `GRANT DELETE ON public.users TO dmitri_runtime`; `downgrade()` reverses both |
| 3 | Service (**new**) | `backend/src/api/services/users.py` | `LastAdminError(ValueError)`; `count_org_admins(session, *, org_id) -> int` (ordinary count, § 5a); `delete_self(session, *, user)`; `delete_member(session, *, user_id, org_id) -> bool` (org-scoped lookup, `False` when not found). Mirrors `backend/src/api/services/invites.py` |
| 4 | Router | `backend/src/api/routers/users.py` | Adds `delete_current_user_route` (`DELETE /api/v1/users/me`, `status_code=204`, `require_user_row`) and `delete_user_route` (`DELETE /api/v1/users/{user_id}`, `status_code=204`, `require_admin`). Raises `ApiError(409, …, code="last_admin")`, `ApiError(409, …, code="self_target")` and the `404` literally inside the handlers |
| 5 | Middleware | `backend/src/api/middleware.py` | `build_cors_middleware_kwargs`: `allow_methods` gains `"DELETE"` |
| 6 | Contract | `contracts/openapi/openapi.yaml` | Per § 6 above: `deleteCurrentUser`, `deleteUser`, `LastAdminConflict`, `SelfTargetConflict`, CORS methods example |
| 7 | Test (**new**) | `backend/tests/test_user_delete_routes.py` | Route-level tests. **Postgres-backed** — uses the `administrative_session` / `seeded_org` fixtures, mirroring `backend/tests/test_invite_routes.py:34`. The cascade cannot be asserted on SQLite |
| 8 | Test (**new**) | `backend/tests/test_users_service.py` | Service-level tests, mirroring `backend/tests/test_invite_service.py` |
| 9 | Test (**new**) | `backend/tests/test_user_delete_cascade_migration.py` | Revision-chain + upgrade/downgrade tests, mirroring `backend/tests/test_users_email_unique_migration.py` |
| 10 | Test | `backend/tests/test_contract_fidelity.py` | `ERROR_RESPONSE_ROUTES` gains `"LastAdminConflict": ("users.py", "delete_current_user_route", 409)` and `"SelfTargetConflict": ("users.py", "delete_user_route", 409)` |
| 11 | Test | `backend/tests/test_migrations.py` | `RUNTIME_GRANTS_BY_TABLE` gains `"users": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})` |
| 12 | Test | `backend/tests/test_cors_headers.py` | `test_real_preflight_returns_204_with_cors_headers` asserts `"DELETE" in allow_methods` |
| 13 | Test | `backend/tests/test_auth_wiring.py` | Registration/dependency assertion for both new routes, alongside the existing `READ_ROUTES` dependency check at line 126 |

**Not touched, deliberately:** `backend/src/api/services/auth.py` (no explicit revocation — the
cascade is the teardown), `backend/src/api/schemas/users.py` (no bodies), `backend/src/api/main.py`
(the users router is already included at line 153), the claims-only routers `hosts.py`, `scans.py`,
`findings.py`, `commands.py`, `invites.py`, and `agents.py` (§ 9 — DMI-104 owns the known
post-removal authorization bug), `backend/src/api/dependencies/auth.py`, and any file under
`hardware-agent/` or `frontend/`.

---

## Constraints

- **No `ruff format`, ever.** Per `.claude/CLAUDE.md`, `backend/` has never been formatted;
  `uv run ruff check src tests` is the backend's only Python gate. Match neighbouring style by
  hand.
- **`./database.sh --test` before the suite.** Without a live `dmitri_test`, `conftest.py`
  *skips* every DB-backed test — which here would silently skip the entire cascade, 404 and
  migration surface. A run with a non-zero skip count is not a green run.
- **Alembic owns `dmitri_test`.** Never point `supabase db reset|push|migration` at it.
- **No new infrastructure.** No `HUMAN_INFRA_REQUIRED` — no hardware, daemon, external service,
  or new dependency. The only environmental prerequisite is the existing local Postgres.
- **Surgical diff.** The migration recreates exactly two constraints and adds exactly one grant.
  Do not rename constraints, do not add a `naming_convention` to the metadata, do not
  "fix" other unnamed FKs.
- **No rate limiting** (TRUTH out-of-scope) and **no audit record** (ADR-017 — deliberate; a
  mutable table would be worse than none).
- **No `Set-Cookie` on either route** (ADR-017 § 6). A test must pin this, not just prose.

---

## Testing expectations

Every row of TRUTH's acceptance table must map to at least one test. Mirror the named
neighbouring file for fixtures and style.

### `backend/tests/test_user_delete_routes.py` — mirror `test_invite_routes.py`

Postgres-backed (`administrative_session`), because the cascade and the FK are the point.

| Test | Asserts |
|---|---|
| Admin deletes a member | `204`; the `users` row is gone |
| Viewer deletes themselves | `204` — the self route is deliberately **not** admin-gated |
| Admin deletes themselves with a second admin present | `204` |
| Sole admin deletes themselves | `409`, envelope `error.code == "last_admin"`, exact message `Add another admin before removing your account.`, row still present |
| Second admin unblocks it | Same request now `204` |
| Viewer deletes another member | `403 forbidden`; target row untouched |
| Admin targets their own id on `/{user_id}` | `409`, envelope `error.code == "self_target"`, exact message `Remove your account from Settings instead.` — explicitly assert it is **not** `404`; caller's row still present |
| Foreign-org target | `404 not_found` — explicitly assert it is **not** `403`; target row untouched |
| Unknown uuid or retry after a completed admin removal | `404 not_found` |
| Retry after completed self-removal | `401 unauthorized` — the caller row is gone |
| Either route without a bearer | `401 unauthorized`, envelope shape |
| **Cascade** | Seed a `RefreshToken` **and** a `PasswordResetToken` for the target, delete, assert both rows gone |
| **Session teardown** | After deletion, refresh fails and a request with the removed user's still-valid access token gets `401` on the row-backed identity route |
| **Password no longer authenticates** | Login with the removed address and former password returns the ordinary invalid-credentials response |
| **Cookie untouched** | Neither `204` response carries a `Set-Cookie` header |
| **Org data survives** | Seed an `Agent` (and scan/host/finding rows via `read_factories.py`) in the org, delete a member, assert all still present |
| **Address reusable** | Delete a member, then `create_invite` for the same address succeeds (no `AlreadyMemberError`, no unique-index violation on `ix_users_email`) |

Reuse the `_assert_error_envelope` helper shape from `backend/tests/test_users_routes.py:19`
rather than reinventing it.

**The `bearer_headers` fixture will not work for the self-removal route.** `conftest.py:191` mints
tokens with `user_id=uuid4()` — a subject with no row, which 401s under `require_user_row`.
Build tokens with `create_access_token(user_id=<the seeded user's id>, …)` for row-backed cases,
as `test_invite_routes.py` does. The remove-someone-else route deliberately keeps the existing
claims-only `require_admin` until DMI-104.

**One test that route-level tests cannot cover, and why:**

| Test | Fixture | Why it cannot live in the ordinary route tests |
|---|---|---|
| Runtime role can delete + cascade | `runtime_session` (`conftest.py:167`, `SET ROLE dmitri_runtime`) | `administrative_session` connects as the **schema owner**, which can delete regardless of grants. The missing `GRANT DELETE ON users` would be invisible to every other test here and would 500 in production on the first real removal. Seed a user plus a `RefreshToken` as owner, delete via `runtime_session`, assert the commit succeeds and the token row is gone — proving the grant and that the cascade's RI trigger is not blocked by the caller's privileges |

### `backend/tests/test_users_service.py` — mirror `test_invite_service.py`

- `count_org_admins` counts only `role == "admin"` and only within the given org (seed a second
  org's admin and assert it is not counted).
- `delete_self` raises `LastAdminError` for a sole admin; succeeds for a viewer in an org with
  one admin; succeeds for an admin when a second admin exists.
- `delete_member` lets an admin remove a **peer admin** in a two-admin org, leaving one admin.
- The sole member of a one-member org cannot remove themselves (`LastAdminError`) — the
  documented v1 lockout, pinned so it is a known state rather than a surprise.
- `delete_member` returns `False` for a foreign-org id and for an unknown id, and leaves the
  row intact in the foreign case.

### `backend/tests/test_user_delete_cascade_migration.py` — mirror `test_users_email_unique_migration.py`

- `revision == "20260808_15"` and `down_revision == "20260804_14"`.
- `upgrade()` drops and recreates both FK constraints with `ondelete="CASCADE"` (monkeypatched
  `op`, as the neighbour does), and issues the `GRANT DELETE … ON public.users`.
- `downgrade()` restores both constraints without `ondelete` and revokes the grant.
- A live assertion against `postgres_engine`: query `information_schema.referential_constraints`
  (or `pg_constraint.confdeltype = 'c'`) for both constraints at head.

### Existing tests that must be extended, not replaced

- `test_contract_fidelity.py` — the two new `ERROR_RESPONSE_ROUTES` entries make
  `test_error_code_fidelity[LastAdminConflict]` and `[SelfTargetConflict]` compare each
  router's literal `code=` against the contract enum. This is the gate TRUTH's "Contract is
  published" row refers to.
- `test_migrations.py` — `RUNTIME_GRANTS_BY_TABLE`; without it the round-trip security test
  fails on the new grant.
- `test_cors_headers.py` — `DELETE` in the preflight's allowed methods.
- `test_auth_wiring.py` — both routes registered, with `/users/me` carrying `require_user_row`
  and `/users/{user_id}` carrying the existing `require_admin`.
- `test_users_routes.py` — **leave as is.** It is SQLite-backed and covers `GET /users/me`; the
  new routes do not belong in it.
