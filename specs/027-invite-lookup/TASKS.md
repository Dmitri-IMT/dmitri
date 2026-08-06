# TASKS — Read an invite before accepting, and stop asking for the address

Spec: `specs/027-invite-lookup/` (`TRUTH.md`, `ARCHITECTURE.md`, `decisions/DR-0001…`, `decisions/DR-0002…`).
No `DESIGN.md` — this feature changes no screen.

Layer: `backend/` (plus one regenerated `frontend/src/types/openapi.d.ts`).
Agents: `agent-developer` → `test-engineer` → `code-reviewer`.
Gate: `./database.sh` first, then `uv run ruff check src tests` and `uv run pytest` from `backend/`.
**Never `ruff format`.** A non-zero DB-skip count means the run does not count.

## Dependency graph

```
1 (schemas D1) ─▶ 2 (service read_invite) ─▶ 3 (route) ─▶ 4 (contract D1 + fidelity)
                                                              │
5 (service accept re-source) ─▶ 6 (schema + router D2) ─▶ 7 (contract D2 + regen types)
```

Tasks 1–4 are deliverable D1; tasks 5–7 are deliverable D2. D2 depends on D1 only in
reasoning; it is sequenced after it here because D1 is smaller and self-contained.

---

## Task 1: Lookup request/response schemas
- **Description**: Add `InviteLookupRequest` (`token: str`) and `InviteLookupResponse` (`email: str`, `role: Literal["admin","viewer"]`, `org_name: str`) to the invites schema module, both with `ConfigDict(extra="forbid")`, matching the module's existing style (`CreateInviteRequest`'s `Literal` role).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/schemas/invites.py`, `backend/tests/test_invite_schemas.py`]
- **Success Criteria**:
  - `InviteLookupRequest` accepts `{"token": "..."}`, rejects a missing `token`, rejects any extra field (mirrors `test_accept_invite_request_requires_token`).
  - `InviteLookupResponse` accepts a valid three-field payload, rejects extra fields, and constrains `role` to `admin`/`viewer`.
  - No comments, no docstrings. No other model in the file is touched.
  - `uv run ruff check src tests` clean; the schema tests pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: `read_invite` service function
- **Description**: Append `read_invite(session: Session, *, token: str) -> tuple[str, str, str]` after `accept_invite` in the invites service. Look the invite up by `hash_token(token)`; collapse unknown / consumed / expired into a **single predicate and single raise** of the existing `InviteTokenError("invalid or expired invite token")`; return `(email, role, org_name)` with the org name from `session.get(Org, invite.org_id)`. Add `Org` to the `api.models.identity` import.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/invites.py`, `backend/tests/test_invite_service.py`]
- **Success Criteria**:
  - Returns the 3-tuple `(invite.email, invite.role, org.name)` for a pending, unexpired invite.
  - Unknown, expired and consumed tokens all raise `InviteTokenError` with the **identical** message string; no new error type is introduced.
  - **Non-mutating**: no `session.add/commit/flush/refresh`, no `consumed_at` or timestamp write, no `issue_session`/`hash_password`/`validate_policy`, no advisory lock. A test asserts `consumed_at` is still `None`, `expires_at` unchanged, and no `User` row exists after a read.
  - Two consecutive calls return equal tuples.
  - No comments or docstrings; existing comments in the module are untouched.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: `POST /api/v1/invites/lookup` route
- **Description**: Add the public lookup route to the existing invites router: `@router.post("/api/v1/invites/lookup", response_model=InviteLookupResponse, status_code=200)`, session via `Depends(get_session)`, **no auth dependency of any kind**. Catch only `InviteTokenError` and raise `ApiError(410, str(exc), code="invalid_invite_token")` with the status and code written literally. The bare-OPTIONS preflight loop needs no change.
- **Dependencies**: 1, 2
- **Target Files**: [`backend/src/api/routers/invites.py`, `backend/tests/test_invite_routes.py`, `backend/tests/test_health.py`]
  - `test_health.py` was not in ARCHITECTURE's file table; it pins the exact route surface and fails by design on any new route, so two rows (`POST` + `OPTIONS`) were folded into this task.
- **Success Criteria**: one test per `TRUTH.md` criterion, mirroring `test_accept_expired_invite_returns_410` and reusing the `client` / `seeded_org` fixtures and `_seed_invite`:
  - live invite → `200` and `response.json() == {"email": …, "role": …, "org_name": …}` (whole-body equality — no `org_id`, `invite_id`, `user_id`, `expires_at`, `created_at`, `token`, `token_hash`).
  - sent with no `Authorization` header and no cookie → `200`, never `401`/`403`.
  - looked up twice → both `200`, identical bodies, `consumed_at` still `None` in the DB.
  - lookup ×N then `POST /api/v1/invites/accept` → still `201` with a `LoginResponse` and refresh cookie.
  - accepted / expired / unknown token → `410` with `error.code == "invalid_invite_token"`.
  - expired vs fabricated token → equal `status_code` **and** equal whole `response.json()`.
  - the lookup's `410` body equals the accept route's `410` body for a dead token.
  - `{"token": …, "role": "admin"}` → `422`, not `200`.
  - No auth dependency appears anywhere on the route.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Publish the lookup in the OpenAPI contract
- **Description**: Add a `/api/v1/invites/lookup` node to `contracts/openapi/openapi.yaml` with `post` + `options`, `security: []`, `tags: [auth]`, `operationId`s `lookupInvite` / `optionsInviteLookup`, request body → new `components.schemas.InviteLookupRequest`, `200` → new `components.schemas.InviteLookupResponse`, `410` → `$ref: '#/components/responses/AcceptInviteTokenGone'` (**reused, not duplicated**). Add `"InviteLookupRequest"` and `"InviteLookupResponse"` to `SCHEMA_NAMES` in the fidelity test.
- **Dependencies**: 3
- **Target Files**: [`contracts/openapi/openapi.yaml`, `backend/tests/test_contract_fidelity.py`]
- **Success Criteria**:
  - `test_schema_matches_contract` covers both new schemas and passes.
  - **No** `ERROR_RESPONSE_ROUTES` entry is added — a second entry keyed `"AcceptInviteTokenGone"` would overwrite the accept-route entry and silently drop coverage.
  - No new `410` response component is minted.
  - The published path matches how the sibling invite paths are published.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: `accept_invite` drops `email` and re-sources it from the invite
- **Description**: Change the signature to `accept_invite(session, *, token: str, password: str)`. Delete the mismatch check (`services/invites.py:108-109`) and `InviteEmailMismatchError`. **Re-source, do not delete** the other two uses: the duplicate-user `select` operand becomes `invite.email.lower()`, and `validate_policy(password, email=invite.email)`. Everything after those lines (`User(...)` from `invite.*`, `consumed_at`, the `IntegrityError` rollback, `issue_session`) is untouched.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/invites.py`, `backend/tests/test_invite_service.py`]
- **Success Criteria**:
  - Existing `accept_invite` call sites in the test file drop the `email=` keyword and still pass.
  - `test_accept_invite_email_mismatch_raises_and_leaves_invite_unconsumed` (`:346`) is deleted.
  - **New regression guard**: accepting with a password the policy rejects *on the basis of the invited address* raises `PasswordPolicyError` — proving `validate_policy` still receives the address.
  - Duplicate detection still raises already-registered for an address that already has an account.
  - The created `User` carries `invite.email`, `invite.role`, `invite.org_id`.
  - `InviteEmailMismatchError` has no remaining definition or raise site.
- **Status**: COMPLETED
- **Note**: Tasks 5–7 were reviewed as one gate — deleting `InviteEmailMismatchError` broke suite *collection* until Task 6, and contract fidelity stayed red until Task 7. `backend/tests/test_bootstrap_org.py` also calls `accept_invite` and was not in ARCHITECTURE's file table; its `email=` was dropped here.
- **Review Rejections**: 0

## Task 6: `AcceptInviteRequest` loses `email`; router stops passing it
- **Description**: Remove `email` from `AcceptInviteRequest` (`schemas/invites.py:29`) so it is `token` + `password` with `extra="forbid"` already present. In the router, drop the `InviteEmailMismatchError` import (`:18`) and its `except` block (`:67-68`, with `ApiError(400, …, code="invite_email_mismatch")`), and stop passing `email` to `accept_invite`.
- **Dependencies**: 5
- **Target Files**: [`backend/src/api/schemas/invites.py`, `backend/src/api/routers/invites.py`, `backend/tests/test_invite_schemas.py`, `backend/tests/test_invite_routes.py`]
- **Success Criteria**:
  - A body of exactly `{"token": …, "password": …}` still returns `201` with a `LoginResponse` and the refresh cookie.
  - Posting `{"token", "password", "email"}` returns `422` — rejected, not silently ignored (new test).
  - `test_accept_mismatched_email_returns_400_invite_email_mismatch` (`test_invite_routes.py:369`) is deleted.
  - The existing already-registered test, edited to drop `email`, still returns `400 email_already_registered`.
  - `AcceptInviteRequest` schema tests updated: `email` is no longer required and supplying it is an extra-field rejection.
  - Method, path, `201` shape and single-use semantics are otherwise unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Contract + generated types follow acceptance
- **Description**: In `contracts/openapi/openapi.yaml`, remove `email` from the `AcceptInviteRequest` schema and from its `required` list, and remove `invite_email_mismatch` from the `AcceptInviteRejected` enum (`:1407`) and its example (`:1414`). Regenerate `frontend/src/types/openapi.d.ts` from the contract — **do not hand-edit it**.
- **Dependencies**: 6
- **Target Files**: [`contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`]
- **Success Criteria**:
  - `test_contract_fidelity` passes: the `AcceptInviteRejected` `400` enum equals the set of codes `accept_invite_route` literally raises (`invalid_invite_token`, `email_already_registered`, `password_policy_violation`).
  - `invite_email_mismatch` appears nowhere in the contract or the generated types.
  - The regenerated `openapi.d.ts` is a clean generator output whose accept-request type has no `email` and whose error-code union has dropped the mismatch code.
  - No other `frontend/` file is touched (no other file references these routes).
- **Status**: COMPLETED
- **Note**: the stale "the address does not match the one invited" clause in the `AcceptInviteRejected` **description** was also removed — TRUTH.md requires the failure gone "in the code or in the published contract", and `openapi-typescript` emits descriptions as JSDoc, so the drift spanned the contract and the generated types.
- **Review Rejections**: 0

---

## Status table

| # | Task | Deliverable | Depends on | Status | Rejections |
|---|---|---|---|---|---|
| 1 | Lookup schemas | D1 | — | COMPLETED | 0 |
| 2 | `read_invite` service | D1 | — | COMPLETED | 0 |
| 3 | Lookup route | D1 | 1, 2 | COMPLETED | 0 |
| 4 | Contract: publish lookup | D1 | 3 | COMPLETED | 0 |
| 5 | `accept_invite` re-sourcing | D2 | — | COMPLETED | 0 |
| 6 | Accept schema + router | D2 | 5 | COMPLETED | 0 |
| 7 | Contract + generated types | D2 | 6 | COMPLETED | 0 |

All 7 tasks COMPLETED. Backend gate: 771 passed, 0 skipped, ruff clean.
Frontend `npm test` is UNVERIFIED (vitest worker-pool failure in this environment), not green —
the only frontend file touched is the regenerated, type-only `openapi.d.ts`.
