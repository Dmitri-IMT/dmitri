# Tasks — Auth + invite contract edges (`023-auth-invite-contract-edges`)

5 tasks. **Unblocked now: #1, #2, #4**

> **Governing spec**: this feature has no `TRUTH.md` / `ARCHITECTURE.md` — [`PLAN.md`](PLAN.md)
> is the approved spec, and every `Target Files` path below was verified against the working
> tree rather than a naming table. Closes contract asks **C13**, **C15**, **C18** (DMI-77).
>
> **Agents**: blast radius is `backend/` + `contracts/`, so spawn **`test-engineer`** and
> **`code-reviewer`**. Gate is **`./database.sh --test`** with **0 skipped** — a bare
> `uv run pytest` skips every DB-backed test and proves nothing here. Baseline measured at the
> start of Task 2: **646 passed, 0 skipped, 1 failed**, the failure being the pre-existing
> `tests/test_migrations.py::test_runtime_role_allows_engine_work_and_rejects_privilege_expansion`,
> which fails identically on a clean tree and is **not** grounds for `[REJECT]`. (PLAN.md §Gates
> still quotes an older 619 — stale, ignore it.) Plus
> `uv run ruff check src tests`. **Never `ruff format`** — backend is hand-formatted. Task 5
> additionally runs the frontend typecheck/build over the regenerated types.

---

## Task 1: Reset-password — split token and policy failures (410 vs 400)
- **Description**: Per PLAN.md §Work item 1 and decisions Q1/Q3. In
  `routers/auth.py:110-116`, split the combined
  `except (InvalidResetTokenError, PasswordPolicyError)` into
  `InvalidResetTokenError` → `ApiError(410, code="invalid_reset_token")` and
  `PasswordPolicyError` → `ApiError(400, code="password_policy_violation")`. In the contract, add
  `ResetPasswordRejected` (400, pinned enum `password_policy_violation`) and `ResetTokenGone`
  (410, pinned enum `invalid_reset_token`) mirroring the `PasswordChangeRejected` pattern at
  `openapi.yaml:1299` (`allOf` + pinned `enum` + examples), point
  `/api/v1/auth/reset-password` at them, and delete the "not resolved here" C15 marker at
  `openapi.yaml:775-777`. `services/auth.py:111-124` already checks the token before the policy,
  so precedence needs no service change — only a test that pins it.
- **Absorbed**: the C13 remainder — retitling change-password's `401` so its description pins it
  to session/`Authorization` failures only (PLAN.md decision A). One line of contract wording
  with no router change and no test of its own; it lands with the neighbouring auth-contract edit.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/routers/auth.py`,
  `contracts/openapi/openapi.yaml`, `backend/tests/test_auth_routes.py`]
- **Tests**: `backend/tests/test_auth_routes.py` — a dead/consumed/expired reset token returns
  `410` with `error.code == "invalid_reset_token"`; a valid token with a policy-violating password
  returns `400` with `error.code == "password_policy_violation"`; and the precedence case (dead
  token **and** weak password) returns the **410 token** code, not the policy code.
- **Success Criteria**:
  - No `HTTPException` remains in `reset_password_route`; both paths raise `ApiError` with the
    codes above.
  - `openapi.yaml` defines `ResetPasswordRejected` and `ResetTokenGone` with pinned `enum`s and
    examples; `/api/v1/auth/reset-password` declares `400` **and** `410` referencing them; the
    C15 "Not resolved here" text is gone.
  - Change-password's `401` description names the `Authorization` header / session as its only
    cause; its `400` still references `PasswordChangeRejected`.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Accept-invite — pin all four error codes
- **Description**: Per PLAN.md §Work item 2 and §Code vocabulary. In
  `routers/invites.py:62-69`, split the 3-way `except` into
  `InviteEmailMismatchError` → `ApiError(400, code="invite_email_mismatch")`,
  `DuplicateUserError` → `ApiError(400, code="email_already_registered")`,
  `PasswordPolicyError` → `ApiError(400, code="password_policy_violation")`, and pin the existing
  `410` (`InviteTokenError`) to `code="invalid_invite_token"`. In the contract, add
  `AcceptInviteRejected` (400, pinned enum of the three codes) and `AcceptInviteTokenGone` (410,
  pinned enum `invalid_invite_token`) in the `PasswordChangeRejected` shape and point
  `/api/v1/invites/{token}/accept` at them, keeping the existing 410 prose about single-use.
  `email_already_registered` stays **global** (`services/invites.py:81-85`) — do not narrow it to
  the org; the name difference from `email_already_member` is deliberate.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/routers/invites.py`,
  `contracts/openapi/openapi.yaml`, `backend/tests/test_invite_routes.py`]
- **Tests**: `backend/tests/test_invite_routes.py` — one assertion per code: mismatched email →
  `400 invite_email_mismatch`; already-registered address → `400 email_already_registered`; weak
  password → `400 password_policy_violation`; expired/consumed/unknown token →
  `410 invalid_invite_token`. Plus precedence: a dead token with a weak password returns the
  **410 token** code.
- **Success Criteria**:
  - No `HTTPException` remains in `accept_invite_route`; all four causes raise `ApiError` with
    exactly the codes above.
  - The three bad-token causes (never issued, consumed, expired) all emit the **same** code —
    they must stay indistinguishable to a token guesser (PLAN.md §Code vocabulary).
  - Contract declares both responses with pinned enums and examples.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Move the invite token out of the URL path into the request body
- **Description**: Per PLAN.md §"Added by user decision 2026-08-03". `routers/invites.py:51`
  takes a live single-use credential as a **path parameter**, so uvicorn's default access logger
  (this repo configures none) and any edge proxy write it to a log line, against OWASP logging
  guidance. Move it: the route becomes `POST /api/v1/invites/accept`, `AcceptInviteRequest` gains
  a `token` field alongside `email` and `password`, and the router reads `body.token`. The
  `OPTIONS` preflight follows automatically from the loop at `routers/invites.py:77-81` but its
  contract entry does not — update the contract path key, drop the `InviteToken` parameter from
  both operations (and the now-unused `components/parameters/InviteToken` if nothing else
  references it), and add `token` to the `AcceptInviteRequest` schema at `openapi.yaml:2292`.
  `mailer.py:44-46` moves its link target to the query form (`{base}/invite?token=…`) to match
  `reset_link`. Nothing in `frontend/src/` consumes the old shape yet — only the generated
  `openapi.d.ts` mentions it — which is why this is near-free now and expensive after DMI-87.
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/routers/invites.py`,
  `backend/src/api/schemas/invites.py`, `backend/src/api/services/mailer.py`,
  `contracts/openapi/openapi.yaml`, `backend/tests/test_invite_routes.py`,
  `backend/tests/test_invite_schemas.py`, `backend/tests/test_mailer.py`]
- **Tests**: `test_invite_routes.py` (acceptance succeeds against the new body-carried token at
  the new path, and Task 2's four error codes still hold there), `test_invite_schemas.py`
  (`AcceptInviteRequest` requires `token`; `extra="forbid"` still rejects unknown fields),
  `test_mailer.py` (the invite link carries the token in the query string).
- **Success Criteria**:
  - `POST /api/v1/invites/accept` accepts `{token, email, password}`; no route in the app takes an
    invite token in its path, and the old `/api/v1/invites/{token}/accept` path is gone from both
    the router and the contract.
  - `OPTIONS /api/v1/invites/accept` still answers `204`.
  - Contract and code agree on the request schema; no dangling `$ref` to `InviteToken`.
  - Every Task 2 error-code test passes unchanged against the new shape.
  - Gate green. **Flag in the completion report that DMI-87 and DMI-90 must be told this route
    changed** (PLAN.md).
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Create-invite — live-invite check under an advisory lock, 409
- **Description**: Per PLAN.md §Work item 3 and decisions B/Q2/Q4. In `services/invites.py`, take
  `pg_advisory_xact_lock(<namespace>, hashtext(org_id::text || lower(email)))` as the first
  statement of `create_invite`, then the existing member check, then a new `PendingInviteError`
  when an unconsumed, unexpired `Invite` exists for `org_id` + `lower(email)`. The namespace
  constant lives next to the call and the two-argument form is deliberate — nothing else in the
  repo uses advisory locks yet. The lock releases on commit or rollback: no unlock, no cleanup
  path. Router maps `AlreadyMemberError` → `ApiError(400, code="email_already_member")` and
  `PendingInviteError` → `ApiError(409, code="invite_already_pending")`, with the member check
  first so `email_already_member` wins (Q4). Contract: add `InviteCreateRejected` (400, pinned
  enum `email_already_member`) and `InviteAlreadyPending` (409, pinned enum
  `invite_already_pending`) in the `PasswordChangeRejected` shape, keeping the existing 400 prose
  about cross-org probing. **No index and no migration** — PLAN.md §"Why not an index" rules both
  out (`now()` is STABLE so the predicate will not compile; `consumed_at IS NULL` would
  permanently block re-inviting a lapsed address).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/invites.py`,
  `backend/src/api/routers/invites.py`, `contracts/openapi/openapi.yaml`,
  `backend/tests/test_invite_service.py`, `backend/tests/test_invite_routes.py`]
- **Tests**: `test_invite_service.py` — a second invite to an address with a live invite raises
  `PendingInviteError` and **mints no second token** (invite row count unchanged, mailer not
  called); an invite whose token is consumed or expired can be reissued. `test_invite_routes.py` —
  `409 invite_already_pending`, `400 email_already_member`, and the precedence case (address is
  both a member and holds a pending invite) returns the **member** code.
- **Success Criteria**:
  - Re-inviting a live address never creates a second `Invite` row and never sends a second email.
  - The advisory lock is transaction-scoped (`pg_advisory_xact_lock`) and namespaced; no explicit
    unlock exists anywhere.
  - Expired or consumed invites do not block reissue.
  - No Alembic migration and no partial index were added.
  - Contract declares `400` and `409` with pinned enums and examples.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Contract-fidelity test over pinned error codes, and regenerate frontend types
- **Description**: Per PLAN.md §Work item 5 and decision Q3. `test_contract_fidelity.py`
  fingerprints read-path schemas and query params only and **never inspects error responses**, so
  a typo'd code literal ships green today. Extend it to walk the pinned response components
  (`PasswordChangeRejected`, `ResetPasswordRejected`, `ResetTokenGone`, `AcceptInviteRejected`,
  `AcceptInviteTokenGone`, `InviteCreateRejected`, `InviteAlreadyPending`), extract each pinned
  `enum`, and assert the corresponding route emits **exactly** that set of codes — no more, no
  fewer. Reuse the module's existing `_load_contract` / `_resolve_ref` helpers; follow its
  parametrized style.
- **Absorbed**: the frontend type regeneration and its gate (PLAN.md §Work item 7). It is a
  generated artifact plus two commands — no test can meaningfully assert it — so per the skill's
  merge rule it lands with the last implementation task. Run `cd frontend && npm run gen:types`,
  then `npm run typecheck && npm run build`. `frontend/src/` has no `/invite` or `/reset-password`
  route yet, so no hand-written frontend code should need to change; if any does, that is a
  finding to report, not to fix here.
- **Dependencies**: Task 1, Task 2, Task 3, Task 4
- **Target Files**: [`backend/tests/test_contract_fidelity.py`,
  `frontend/src/types/openapi.d.ts`]
- **Tests**: `backend/tests/test_contract_fidelity.py` — the new error-code fidelity test. Prove
  it bites: it must fail if a router code literal is changed to one absent from the contract enum,
  or if a contract enum gains a code no route emits.
- **Success Criteria**:
  - The test enumerates all seven pinned response components and asserts exact set equality
    against the codes the routers raise.
  - Temporarily mutating any one router code literal makes the new test fail (demonstrate in the
    completion report).
  - `frontend/src/types/openapi.d.ts` is regenerated from the edited contract and contains
    `/api/v1/invites/accept` with no `/api/v1/invites/{token}/accept`.
  - Backend gate green (`./database.sh --test`, 0 skipped; `uv run ruff check src tests`) **and**
    `npm run typecheck && npm run build` green.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ──────────────┐
#2 ── #3 ────────┼── #5
#4 ──────────────┘
```

Track A (auth): #1. Track B (invites): #2 → #3, and #4 independently. #5 closes.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Reset-password — split token and policy failures (410 vs 400) | COMPLETED |
| 2 | Accept-invite — pin all four error codes | COMPLETED |
| 3 | Move the invite token out of the URL path into the request body | COMPLETED |
| 4 | Create-invite — live-invite check under an advisory lock, 409 | COMPLETED |
| 5 | Contract-fidelity test over pinned error codes, and regenerate frontend types | COMPLETED |
