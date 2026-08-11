# Tasks — Users and invites admin API (`030-users-invites-admin-api`)

7 tasks. **Unblocked now: #1.**

Backend tasks use `test-engineer` and `code-reviewer`; the reviewer gate is `./database.sh --test`, then `cd backend && uv run ruff check src tests && uv run pytest` with zero database-test skips. Frontend Task 7 uses `frontend-test-engineer` and `frontend-code-reviewer`; the reviewer gate is `cd frontend && npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build`.

---

## Task 1: Persist member activity and revoke permission
- **Description**: Add the nullable activity columns and runtime invite-delete grant per `ARCHITECTURE.md` §§1–2 and its naming table.
- **Absorbed**: The `User` model fields and runtime-grant expectation are part of the migration artifact and cannot carry independent end-to-end tests.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/identity.py`, `backend/alembic/versions/20260810_16_user_activity_and_invite_revoke.py`, `backend/tests/test_user_activity_migration.py`, `backend/tests/test_migrations.py`]
- **Tests**: `backend/tests/test_user_activity_migration.py` proves revision order, upgrade/downgrade shape, live `timestamptz` nullability, and absence of activity indexes; `backend/tests/test_migrations.py` proves model/migration agreement and the runtime `DELETE` grant.
- **Success Criteria**: The migration chains from `20260808_15`; upgrade adds nullable, unindexed `last_login_at` and `last_seen_at` and grants invite deletion; downgrade revokes the grant and drops both columns; the model uses `UTC_TIMESTAMP` without indexes; migration and grant tests pass against live Postgres.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Stamp login and session activity
- **Description**: Record login and last-seen facts at the complete session-issuance and refresh call paths per `ARCHITECTURE.md` §6.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/auth.py`, `backend/tests/test_auth_service.py`, `backend/tests/test_invite_service.py`]
- **Tests**: `backend/tests/test_auth_service.py` proves login and refresh timestamps, failure ordering, commit visibility, and narrow SQL updates; `backend/tests/test_invite_service.py` proves invite acceptance stamps both facts.
- **Success Criteria**: Password login and invite acceptance stamp both columns; refresh advances only `last_seen_at`; failed login, failed token reuse, logout, and password reset do not stamp; emitted activity updates name only intended columns; fresh sessions observe committed stamps.
- **Status**: COMPLETED
- **Review Rejections**: 2

## Task 3: Serialize and enforce role changes
- **Description**: Add the shared organization-admin advisory lock and safe role-change service per `ARCHITECTURE.md` §§5 and 7.
- **Absorbed**: The lock helper is merged with its first observable consumer because a standalone helper has no product behavior without an admin-reducing write.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/org_lock.py`, `backend/src/api/services/users.py`, `backend/tests/test_org_lock.py`, `backend/tests/test_users_service.py`]
- **Tests**: `backend/tests/test_org_lock.py` proves organization scope, transaction scope, namespace separation, blocking, promotions, and concurrent mutual-demotion safety; `backend/tests/test_users_service.py` proves role-change success, misses, org isolation, and last-admin refusal.
- **Success Criteria**: `lock_org_admins` uses namespace `8818` and a transaction-scoped organization key; `change_member_role` locks before reads, preserves existing admin counting, and never partially adopts the lock in removal services; concurrent mutual demotion leaves exactly one admin and one `LastAdminError`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 4: Publish member administration routes
- **Description**: Implement member listing and role-change HTTP behavior, schemas, and browser PATCH support per `ARCHITECTURE.md` §§3, 5, 8, and 10.
- **Absorbed**: CORS configuration is merged into the PATCH route task because only a real browser preflight can verify it; user schemas and list service are merged with their only public consumers.
- **Dependencies**: Tasks 2, 3
- **Target Files**: [`backend/src/api/services/users.py`, `backend/src/api/schemas/users.py`, `backend/src/api/routers/users.py`, `backend/src/api/middleware.py`, `backend/tests/test_users_admin_routes.py`, `backend/tests/test_users_service.py`, `backend/tests/test_users_schemas.py`, `backend/tests/test_cors_headers.py`, `backend/tests/test_health.py`]
- **Tests**: Route tests prove admin-only access, exact response shape, ordering, isolation, self-target and last-admin envelopes, profile role effects, and PATCH preflight; service and schema tests prove SQL scoping, validation, and `extra="forbid"`; CORS tests prove PATCH is allowed; the exact route-surface gate includes both new member operations.
- **Success Criteria**: `GET /api/v1/users` returns only the caller organization in recent-first, NULL-last stable order with exactly `user_id`, `email`, `role`, and `last_seen_at`; `PATCH /api/v1/users/{user_id}` returns the updated member, rejects self-target and last-admin changes with pinned 409 codes, maps misses to 404, rejects invalid bodies, and is reachable through CORS; `/me` route precedence remains correct.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: Publish pending-invite administration routes
- **Description**: Implement pending-invitation listing and hard revocation per `ARCHITECTURE.md` §§3–4 and 8.
- **Absorbed**: Invite schemas and the shared pending predicate are merged with the routes that make them observable.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/invites.py`, `backend/src/api/schemas/invites.py`, `backend/src/api/routers/invites.py`, `backend/tests/test_invite_admin_routes.py`, `backend/tests/test_invite_service.py`, `backend/tests/test_invite_schemas.py`, `backend/tests/test_health.py`]
- **Tests**: Route tests prove pending filtering, ordering, isolation, token secrecy, runtime-role revocation, token invalidation, and re-invitation; service and schema tests prove shared predicate behavior, hard deletion, miss semantics, validation, and exact response shapes; the exact route-surface gate includes both new invite operations without OPTIONS twins.
- **Success Criteria**: `GET /api/v1/invites` returns only live unconsumed invitations for the caller organization, ordered by expiry then id and without token material; `DELETE /api/v1/invites/{invite_id}` hard-deletes only a pending same-org invite, returns 204, makes lookup and acceptance fail, permits re-invitation, and maps consumed, expired, foreign, and unknown ids to 404; both routes require admin and precede the OPTIONS loop.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Publish and verify the API contract
- **Description**: Update the OpenAPI contract and route wiring fidelity for all four operations per `ARCHITECTURE.md` §9 and testing area 8.
- **Dependencies**: Tasks 4, 5
- **Target Files**: [`contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`, `backend/tests/test_contract_fidelity.py`, `backend/tests/test_auth_wiring.py`]
- **Tests**: `backend/tests/test_contract_fidelity.py` proves live-schema fingerprints, role-conflict codes, operation ids, security, exact response sets, and CORS example fidelity; `backend/tests/test_auth_wiring.py` proves exact methods, paths, registration, and `require_admin` dependencies.
- **Success Criteria**: The contract publishes `listOrgUsers`, `updateUserRole`, `listPendingInvites`, and `revokeInvite`; five strict schemas and `RoleChangeConflict` match FastAPI; member rows omit status and login history; all operations publish exact auth/refusal responses and use frontend bearer security; CORS method examples include PATCH; wiring tests prove all four unconditional admin gates; `npm run gen:types` is re-run and `frontend/src/types/openapi.d.ts` committed, so a fresh generation leaves no diff.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Disclose recorded activity in Settings
- **Description**: Add the role-independent activity disclosure to Settings exactly as specified by `DESIGN.md` §§2–10 and `ARCHITECTURE.md` §11.
- **Dependencies**: Task 2
- **Target Files**: [`frontend/src/pages/Settings.tsx`, `frontend/src/pages/Settings.test.tsx`]
- **Tests**: `frontend/src/pages/Settings.test.tsx` proves both roles see the label, the button toggles exact copy by mouse and keyboard, focus and ARIA relationships remain correct, the note stays mounted but hidden when collapsed, and no setting control or timestamp exists.
- **Success Criteria**: A sibling section after the password form renders `Activity` and a stable `What's recorded?` button for both roles; activation reveals and hides the exact American-spelling copy with `aria-expanded` and `aria-controls`, without moving focus; the note is always mounted, uses the specified layout, and no API read, toggle, timestamp, persistence, icon, modal, or new shared component is added; the complete frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

---

## Dependency graph

```text
#1 → #2 ───────────────→ #4 ─→ #6
 │    └────────────────────────→ #7
 ├→ #3 ────────────────→ #4
 └─────────────────────→ #5 ─→ #6
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Persist member activity and revoke permission | COMPLETED |
| 2 | Stamp login and session activity | COMPLETED |
| 3 | Serialize and enforce role changes | COMPLETED |
| 4 | Publish member administration routes | COMPLETED |
| 5 | Publish pending-invite administration routes | COMPLETED |
| 6 | Publish and verify the API contract | COMPLETED |
| 7 | Disclose recorded activity in Settings | COMPLETED |
