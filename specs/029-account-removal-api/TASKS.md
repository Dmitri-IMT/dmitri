# TASKS — Account removal API (DMI-102, backend only)

Specs: [`TRUTH.md`](TRUTH.md), [`ARCHITECTURE.md`](ARCHITECTURE.md). No `DESIGN.md` (no screens).

**Agents:** every task is `backend/` or `contracts/` → step 1 `agent-developer`, step 2
`test-engineer`, step 3 `code-reviewer`. Gate: `./database.sh --test` first, then
`uv run ruff check src tests` + `uv run pytest` with **zero skips**. Never `ruff format`.

**CLAUDE.md ScanRunner rule:** not applicable — this feature touches no scan-pipeline code
(ARCHITECTURE.md § System context).

## Dependency graph

```
Task 1 (cascade migration + grant)
   └─> Task 3 (routers + CORS)  <──  Task 2 (service layer)
                 └─> Task 4 (OpenAPI contract + fidelity)
```

---

## Task 1: FK cascade migration, model `ondelete`, and the `DELETE` grant
- **Description**: Add `ondelete="CASCADE"` to `RefreshToken.user_id` and
  `PasswordResetToken.user_id`; write the new Alembic revision `20260808_15` that drops and
  recreates both FK constraints with `ON DELETE CASCADE` and issues
  `GRANT DELETE ON public.users TO dmitri_runtime`, with `downgrade()` reversing both. Confirm
  the live constraint names against `dmitri_test` before writing the migration rather than
  trusting Postgres default naming (ARCHITECTURE.md § 1–2). Extend
  `RUNTIME_GRANTS_BY_TABLE` with the new `users` grant set. Do not rename constraints, add a
  metadata `naming_convention`, or touch other unnamed FKs.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/session.py`,
  `backend/alembic/versions/20260808_15_user_delete_cascade.py`,
  `backend/tests/test_migrations.py`,
  `backend/tests/test_user_delete_cascade_migration.py`]
- **Success Criteria**:
  - `revision == "20260808_15"`, `down_revision == "20260804_14"`.
  - Both FKs are `ON DELETE CASCADE` at head, asserted live against `postgres_engine`
    (`pg_constraint.confdeltype = 'c'` or `information_schema.referential_constraints`).
  - `upgrade()`/`downgrade()` unit-tested with a monkeypatched `op`, mirroring
    `backend/tests/test_users_email_unique_migration.py`.
  - `test_live_migration_round_trip_and_security` passes with
    `"users": {"SELECT", "INSERT", "UPDATE", "DELETE"}`.
  - A `runtime_session` test (`SET ROLE dmitri_runtime`) deletes a seeded user with a
    `RefreshToken` and the token row is gone — proving both the grant and that the RI trigger
    is not blocked by the caller's privileges.
  - Gate green with zero skipped tests.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: `services/users.py` — admin count and the two deletions
- **Description**: New service module mirroring `backend/src/api/services/invites.py`:
  `LastAdminError(ValueError)`; `count_org_admins(session, *, org_id) -> int`;
  `delete_self(session, *, user)`; `delete_member(session, *, user_id, org_id) -> bool`
  (org-scoped lookup, `False` on miss). Deletion goes through the ORM
  (`session.delete(user); session.commit()`) — no raw SQL, no `text()`. Role is read from the
  DB row, not the JWT. Ordinary count under READ COMMITTED: no locks, no retries, no isolation
  changes (ARCHITECTURE.md § 3, § 5a).
- **Dependencies**: 1
- **Target Files**: [`backend/src/api/services/users.py`,
  `backend/tests/test_users_service.py`]
- **Success Criteria**:
  - `count_org_admins` counts only `role == "admin"` and only within the given org (a second
    org's admin is not counted).
  - `delete_self` raises `LastAdminError` for a sole admin; succeeds for a viewer in an org
    with one admin; succeeds for an admin once a second admin exists.
  - `delete_member` removes a peer admin in a two-admin org, leaving one admin.
  - The sole member of a one-member org cannot remove themselves (`LastAdminError`) — the
    documented v1 lockout, pinned.
  - `delete_member` returns `False` for an unknown id and for a foreign-org id, leaving the
    foreign row intact.
  - Gate green with zero skipped tests.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Both `DELETE` routes and the CORS method
- **Description**: Add `delete_current_user_route` (`DELETE /api/v1/users/me`,
  `status_code=204`, `require_user_row`) and `delete_user_route`
  (`DELETE /api/v1/users/{user_id}`, `status_code=204`, `require_admin`) to
  `routers/users.py`, both declared **above** the parameterised path (§ 4a trap). Each route's
  authorization is a single unconditional dependency — no branching inside the handler.
  `/{user_id}` compares `user_id == caller.sub` **before** the lookup and raises
  `ApiError(409, "Remove your account from Settings instead.", code="self_target")`; the
  org-scoped miss raises `404 not_found`. `/me` maps `LastAdminError` to
  `ApiError(409, "Add another admin before removing your account.", code="last_admin")`. All
  three raised literally inside the handlers (the fidelity gate AST-scans route bodies). Add
  `"DELETE"` to `allow_methods` in `build_cors_middleware_kwargs`. No `Set-Cookie` on either
  response; no touching `services/auth.py`, `schemas/users.py`, or `dependencies/auth.py`.
- **Dependencies**: 1, 2
- **Target Files**: [`backend/src/api/routers/users.py`,
  `backend/src/api/middleware.py`,
  `backend/tests/test_user_delete_routes.py`,
  `backend/tests/test_cors_headers.py`,
  `backend/tests/test_auth_wiring.py`]
- **Success Criteria**: every row of ARCHITECTURE.md § Testing expectations for
  `test_user_delete_routes.py` is covered — Postgres-backed via `administrative_session` /
  `seeded_org`, with tokens minted via `create_access_token(user_id=<seeded id>, …)` because the
  `bearer_headers` fixture's `uuid4()` subject 401s under `require_user_row`. Specifically:
  - admin removes a member → `204`, row gone; viewer removes themselves → `204`; admin removes
    themselves with a second admin → `204`.
  - sole admin self-removal → `409` / `last_admin` / exact message / row present; succeeds once
    a second admin exists.
  - viewer removing another → `403`, target untouched.
  - admin self-targeting `/{user_id}` → `409` / `self_target` / exact message, asserted **not**
    `404`, caller row present.
  - foreign-org target → `404`, asserted **not** `403`, target row untouched; unknown uuid and
    retry-after-removal → `404`; retry after self-removal → `401`.
  - either route without a bearer → `401` with the envelope shape (reuse the
    `_assert_error_envelope` helper shape from `test_users_routes.py:19`).
  - cascade: seeded `RefreshToken` **and** `PasswordResetToken` both gone after deletion.
  - session teardown: refresh fails and the row-backed identity route `401`s afterwards;
    login with the removed address and former password returns the ordinary
    invalid-credentials response.
  - neither `204` carries a `Set-Cookie` header.
  - org data survives (agent + scan/host/finding via `read_factories.py`); the removed address
    is invitable again with no `AlreadyMemberError` and no `ix_users_email` violation.
  - `test_auth_wiring.py` asserts both routes are registered with their dependencies;
    `test_cors_headers.py` asserts `"DELETE" in allow_methods`.
  - `test_users_routes.py` left unchanged. No regression test that treats the DMI-104 bug as
    expected behaviour.
  - Gate green with zero skipped tests.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: OpenAPI contract and fidelity map
- **Description**: Per ARCHITECTURE.md § 6, add `delete` to the existing `/api/v1/users/me`
  path (`operationId: deleteCurrentUser`, `FrontendBearerAuth`, `204` with the four standard
  headers used by the sibling `get`, `401 → Unauthorized`, `409 → LastAdminConflict`); add the
  new `/api/v1/users/{user_id}` path (`operationId: deleteUser`, uuid path param, `204`,
  `401`, `403 → Forbidden`, `404 → NotFound`, `409 → SelfTargetConflict`); add
  `components/responses/LastAdminConflict` and `SelfTargetConflict` modelled byte-for-byte on
  `InviteAlreadyPending`, each with the exact user-facing message and a description stating
  that the caller holds every permission and it is current state that refuses (RFC 9110
  § 15.5.10) — the `SelfTargetConflict` description points at Settings and contains no API
  paths. Update the `Access-Control-Allow-Methods` example to `GET, POST, DELETE, OPTIONS`. No
  `options` twin for either route. Extend `ERROR_RESPONSE_ROUTES` with both entries.
- **Dependencies**: 3
- **Target Files**: [`contracts/openapi/openapi.yaml`,
  `backend/tests/test_contract_fidelity.py`]
- **Success Criteria**:
  - `test_error_code_fidelity[LastAdminConflict]` and `[SelfTargetConflict]` pass, comparing
    each router's literal `code=` against the contract enum.
  - Both removals appear in the published contract with their success and failure shapes.
  - The CORS methods example includes `DELETE`.
  - Gate green with zero skipped tests.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Status table

| Task | Name | Deps | Status | Rejections |
|---|---|---|---|---|
| 1 | Cascade migration + `DELETE` grant | — | COMPLETED | 0 |
| 2 | `services/users.py` | 1 | COMPLETED | 0 |
| 3 | Both `DELETE` routes + CORS | 1, 2 | COMPLETED | 0 |
| 4 | OpenAPI contract + fidelity | 3 | COMPLETED | 0 |
