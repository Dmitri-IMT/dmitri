# ARCHITECTURE — Read an invite before accepting, and stop asking for the address

Implements `TRUTH.md` (DMI-86, contract ask C14). Two deliverables:

- **D1 — the lookup.** A public, non-consuming read of an invitation. What C14 asked for.
- **D2 — acceptance drops the address field.** The direct consequence of D1, folded in by
  [`decisions/DR-0002-accept-drops-email.md`](decisions/DR-0002-accept-drops-email.md).

Backend, plus one regenerated type file. No `INTEGRATION.md` — there is no cross-layer
contract to negotiate; the consuming screen is DMI-87.

D2 depends on D1 only in reasoning, not in code — they can be built in either order, but D1
is the smaller and more self-contained of the two.

**OQ-1 (transport shape) is RESOLVED (2026-08-06): `POST /api/v1/invites/lookup`, token in
the request body.** Rationale in [`decisions/DR-0001-invite-lookup-transport.md`](decisions/DR-0001-invite-lookup-transport.md).
No open questions remain; this document is implementable as written.

---

## System context

The feature adds one **public, read-only** operation to the existing invite subsystem. It sits
beside, not inside, the acceptance path:

```
admin  ──POST /api/v1/invites──────────▶ create_invite()  ─▶ Invite row (token_hash) ─▶ mailer
                                                                     │
                                                                     │  {app_base_url}/invite?token=…
                                                                     ▼
invitee ──POST /api/v1/invites/lookup──▶ read_invite()   ─▶ SELECT Invite + Org   (no writes)
        ◀── {email, role, org_name} ────┘                          │
                                                                   ▼
invitee ──POST /api/v1/invites/accept──▶ accept_invite() ─▶ User + consumed_at + issue_session()
```

Placement in the existing stack (all pre-existing, unchanged):

- **Router layer** — `backend/src/api/routers/invites.py`, registered in
  `backend/src/api/main.py:157` via `app.include_router(invites.router)`. No new router module,
  no new `include_router` call.
- **Service layer** — `backend/src/api/services/invites.py`, which already owns
  `create_invite` / `accept_invite` and the error types.
- **Token comparison** — `hash_token()` from `api.services.tokens`; the raw token is never
  stored, only `Invite.token_hash`.
- **Error envelope** — `ApiError` → `api.main.http_exception_handler` →
  `error_envelope(code, message)`. Nothing new.
- **Auth** — none. Per `ADR-005` §2 the *frontend* routes use JWT Bearer; the invite-accept
  route is already `security: []` in the contract and this route joins it. Possession of the
  token is the only authorisation, as `TRUTH.md` states.
- **CORS / transport** — `ADR-005` §3 stands unchanged: closed origin list, HTTPS in
  production. `build_cors_middleware_kwargs` (`backend/src/api/middleware.py:53`) already
  allows `GET`, `POST`, `OPTIONS`, so **no CORS configuration change is required**. The
  router's bare-OPTIONS loop picks the new `POST` route up automatically (below).

Not touched: `create_invite`, `login_response`, `issue_session`, the mailer, the
`Invite`/`Org`/`User` tables, and every existing migration. **There is no migration in this
feature** — it reads columns that already exist.

`accept_invite` and `AcceptInviteRequest` **are** touched, by the second deliverable — see
[§ Deliverable 2](#deliverable-2--acceptance-drops-the-address-field).

---

## Data model and contracts

### Storage (read-only; confirmed from `backend/src/api/models/identity.py`)

`Invite` (`backend/src/api/models/identity.py:40`) carries exactly what the lookup needs:

| Column | Type | Role in this feature |
|---|---|---|
| `token_hash` | `str`, unique, indexed | The lookup key: `WHERE token_hash = hash_token(raw)`. The raw token is never stored, so comparison is by hash, exactly as `accept_invite` does. |
| `email` | `str` | Disclosed field 1. |
| `role` | `str`, `CheckConstraint("role IN ('admin','viewer')")` | Disclosed field 2. |
| `org_id` | `UUID`, FK → `orgs.id` | **Never disclosed.** Used only to reach the org name. |
| `expires_at` | tz-aware `datetime` | Internal liveness test. Never disclosed. |
| `consumed_at` | tz-aware `datetime \| None` | Internal liveness test. Never disclosed. |

`Org.name` (`backend/src/api/models/identity.py:18`) is disclosed field 3, reached by
`session.get(Org, invite.org_id)`. `Org` is a new import in `services/invites.py` (the module
currently imports only `Invite, User`).

**Lifecycle states, and how they collapse.** The three "gone" conditions are three distinct
internal facts:

| State | Internal representation | External answer |
|---|---|---|
| Pending (readable) | row exists ∧ `consumed_at is None` ∧ `expires_at > utc_now()` | `200` with the three fields |
| Already accepted | row exists ∧ `consumed_at is not None` | gone |
| Expired | row exists ∧ `expires_at <= utc_now()` | gone |
| Unknown / forged | no row for `hash_token(token)` | gone |

The service collapses them with a **single predicate and a single raise**, mirroring
`accept_invite` (`backend/src/api/services/invites.py:105`) line for line:

```python
if invite is None or invite.consumed_at is not None or invite.expires_at <= now:
    raise InviteTokenError("invalid or expired invite token")
```

One error type, one message string, one branch. Do **not** introduce `InviteExpiredError` /
`InviteConsumedError` / `InviteNotFoundError`: three types would be three chances for the
response to differ, and `TRUTH.md`'s "No enumeration signal" criterion forbids any difference
in status, code, or body.

### Failure contract (pinned — read from the code, not assumed)

The gone answer reuses, byte for byte, what `accept_invite_route` already raises for a
spent/unknown token (`backend/src/api/routers/invites.py:66`):

| Element | Value | Source of truth |
|---|---|---|
| Service error | `InviteTokenError` (existing, `services/invites.py:20`) | reused, not subclassed |
| Message | `"invalid or expired invite token"` | `services/invites.py:106` |
| HTTP status | `410` | `routers/invites.py:66` |
| `error.code` | `invalid_invite_token` | `routers/invites.py:66` |
| Body shape | `{"error": {"code": …, "message": …, "details": {}}}` | `errors.error_envelope` |
| OpenAPI response | `$ref: '#/components/responses/AcceptInviteTokenGone'` | `contracts/openapi/openapi.yaml:1429` |

Reusing the **existing** `AcceptInviteTokenGone` component (rather than minting a parallel
`InviteLookupTokenGone`) is deliberate: a shared component makes "worded identically to the
one acceptance already gives" true by construction, and `test_contract_fidelity.py`'s
`ERROR_RESPONSE_ROUTES` is keyed by component name, so it cannot hold two routes for one
component. Route-level equality is asserted directly by a test instead (see Testing).

### Success response

New pydantic model in `backend/src/api/schemas/invites.py`, matching the module's existing
style (`ConfigDict(extra="forbid")`, `Literal` role as in `CreateInviteRequest`):

| Field | Type | Notes |
|---|---|---|
| `email` | `str` | The invited address, verbatim from `Invite.email` |
| `role` | `Literal["admin", "viewer"]` | Mirrors `CreateInviteRequest.role`; the DB check constraint guarantees the domain |
| `org_name` | `str` | `Org.name` |

Status `200`. **Nothing else may appear**: no `invite_id`, no `org_id`, no `user_id`, no
`expires_at`, no `created_at`, no token or token hash. `extra="forbid"` plus an explicit
whole-body equality assertion in the route test enforce this — `TRUTH.md` "Discloses nothing
extra".

### Service signature

In `backend/src/api/services/invites.py`, beside `accept_invite`:

```python
def read_invite(session: Session, *, token: str) -> tuple[str, str, str]:
```

Returns `(email, role, org_name)` — a plain tuple, matching the module's existing convention
(`create_invite` returns a 2-tuple, `accept_invite` a 3-tuple). No new dataclass.

**Non-mutating, mandatory.** The function performs `select(...)` reads only. It must not:
call `session.add()`, `session.commit()`, `session.flush()`, or `session.refresh()`; write
`consumed_at` or any timestamp; call `issue_session()`, `hash_password()`, or `validate_policy()`;
or take the advisory lock. The FastAPI `get_session` dependency is used unchanged; the request
leaves no trace in the database. A read must be repeatable an unbounded number of times with
an identical result, and must leave the invite acceptable.

`read_invite` is defined **after** `accept_invite` in the module so the diff is an append.

---

## Route

OQ-1 resolved 2026-08-06 in favour of a body `POST`
([`decisions/DR-0001-invite-lookup-transport.md`](decisions/DR-0001-invite-lookup-transport.md)).

| Aspect | Value |
|---|---|
| Decorator | `@router.post("/api/v1/invites/lookup", response_model=InviteLookupResponse)` |
| Status | `200` (explicitly — the router default for `post` is `200`, but the sibling routes set `status_code` deliberately, so state it) |
| Token arrives as | request body |
| Request model | `InviteLookupRequest` in `schemas/invites.py`: `token: str`, `ConfigDict(extra="forbid")` |
| Path collision | none — new path, distinct from `/api/v1/invites` and `/api/v1/invites/accept` |
| Missing or extra field | `422` `validation_error` from the global `RequestValidationError` handler. `extra="forbid"` means a caller who appends `"role": "admin"` is **rejected**, not silently ignored — the loud-failure property `TRUTH.md` names in its authority rule. |
| Preflight | Slots into the existing `routers/invites.py:80` loop **unchanged** — the loop walks `POST` routes, so an `OPTIONS` 204 route is registered automatically. The contract gains the matching `options` operation alongside the `post`, as the sibling invite paths already do. |
| Auth | none |
| Logging | The token stays out of the access log with no configuration — the reason this shape was chosen. |

### Handler shape

- No auth dependency of any kind. Not `require_admin`, not `require_user`, not
  `require_user_row`. `TRUTH.md`: "never rejected for being unauthenticated".
- Session via `session: Session = Depends(get_session)`, as the neighbouring routes do.
- Body of the handler:

```python
try:
    email, role, org_name = read_invite(session, token=body.token)
except InviteTokenError as exc:
    raise ApiError(410, str(exc), code="invalid_invite_token") from exc
return InviteLookupResponse(email=email, role=role, org_name=org_name)
```

  `InviteTokenError` is the **only** exception caught. The route raises `ApiError` and never
  `HTTPException` directly, matching the rest of the module.
- Write the `410` / `invalid_invite_token` pair **literally** in the handler, matching the
  sibling routes. Note this is a consistency convention here, not a gate:
  `test_contract_fidelity._route_error_codes_by_status` only AST-parses handlers listed in
  `ERROR_RESPONSE_ROUTES`, and this route is deliberately not listed (see below). The literal
  form matters only if a future change gives the lookup its own response component.

### OpenAPI shape

A new `/api/v1/invites/lookup` node in `contracts/openapi/openapi.yaml` carrying `post` +
`options`, matching how the sibling invite paths are published:

- `security: []` — public, as `POST /api/v1/invites/accept` already is
- request body → new `components.schemas.InviteLookupRequest`
- `200` → new `components.schemas.InviteLookupResponse`
- `410` → `$ref: '#/components/responses/AcceptInviteTokenGone'` (reused, not duplicated)
- `tags: [auth]`; suggested `operationId`s `lookupInvite` and `optionsInviteLookup`

---

## Deliverable 2 — acceptance drops the address field

Decided in [`decisions/DR-0002-accept-drops-email.md`](decisions/DR-0002-accept-drops-email.md).
`POST /api/v1/invites/accept` becomes `{token, password}`. Its method, path, `201` response,
and remaining failures are unchanged.

### The edit is a re-sourcing, not a deletion

`accept_invite(session, *, token, email, password)` loses its `email` parameter, but that
parameter is read in **three** places, and only one of them goes away:

| `services/invites.py` | Today | After |
|---|---|---|
| `:108-109` | `if invite.email.lower() != email.lower(): raise InviteEmailMismatchError(...)` | **deleted** — the whole check |
| `:111-113` | `select(User).where(func.lower(User.email) == email.lower())` | `== invite.email.lower()` |
| `:117` | `validate_policy(password, email=email)` | `validate_policy(password, email=invite.email)` |

⚠️ **Deleting rather than re-sourcing the last two is the failure mode to watch for.** Losing
the `validate_policy` argument silently stops the password policy from considering the
invited address — a quiet weakening that no existing test necessarily catches unless the
policy test is written against it. Losing the duplicate lookup's operand breaks the
already-registered path outright. New signature:

```python
def accept_invite(session: Session, *, token: str, password: str) -> tuple[str, str, int]:
```

Everything after those three lines — `User(...)` construction from `invite.*`, `consumed_at`,
the `IntegrityError` rollback, `issue_session` — is untouched.

### Removals

| Artifact | Action |
|---|---|
| `AcceptInviteRequest.email` (`schemas/invites.py:29`) | removed; model becomes `token` + `password`. `extra="forbid"` already present, so a caller still sending `email` gets `422` — the "rejected, not ignored" criterion |
| `InviteEmailMismatchError` (`services/invites.py:24`) | removed — no remaining raise site |
| its import and `except` block (`routers/invites.py:18`, `:67-68`) | removed, along with `ApiError(400, …, code="invite_email_mismatch")` |
| `invite_email_mismatch` in the contract enum (`contracts/openapi/openapi.yaml:1407`, example at `:1414`) | removed from `AcceptInviteRejected`; the remaining two codes stay |

These are orphans created **by this change**, so removing them is in scope under
`.claude/CLAUDE.md` §3. Nothing else in `services/invites.py` or `routers/invites.py` is
touched.

### This one is gated

`AcceptInviteRejected` **is** in `test_contract_fidelity.ERROR_RESPONSE_ROUTES`
(`("invites.py", "accept_invite_route", 400)`), so the fidelity test asserts the contract's
`400` enum equals the set of codes the handler literally raises. Dropping the code from the
handler but not the contract — or the reverse — fails the suite. Unlike the lookup's `410`
(which reuses a component and is verified by a route-to-route body test instead), this change
cannot silently drift.

---

## New files and naming (mandatory)

| Path | New / edit | What the implementer does |
|---|---|---|
| `backend/src/api/services/invites.py` | **edit** | **D1:** append `read_invite(session, *, token) -> tuple[str, str, str]`; add `Org` to the `api.models.identity` import; reads only, no writes. **D2:** drop `email` from `accept_invite`'s signature, delete the mismatch check, re-source the other two `email` uses from `invite.email`, delete `InviteEmailMismatchError`. |
| `backend/src/api/schemas/invites.py` | **edit** | **D1:** add `InviteLookupRequest` (`token: str`, `extra="forbid"`) and `InviteLookupResponse` (`email`, `role: Literal["admin","viewer"]`, `org_name`; `ConfigDict(extra="forbid")`). **D2:** remove `email` from `AcceptInviteRequest`. |
| `backend/src/api/routers/invites.py` | **edit** | **D1:** add `POST /api/v1/invites/lookup`, import `read_invite` and both new schemas, map `InviteTokenError` → `ApiError(410, …, code="invalid_invite_token")`; no auth dependency; the preflight loop needs **no change**. **D2:** drop the `InviteEmailMismatchError` import and `except` block, and stop passing `email` to `accept_invite`. |
| `contracts/openapi/openapi.yaml` | **edit** | **D1:** publish `/api/v1/invites/lookup` with `post` + `options` (see § OpenAPI shape). **D2:** remove `email` from the `AcceptInviteRequest` schema (and its `required`), and remove `invite_email_mismatch` from the `AcceptInviteRejected` enum and example. |
| `frontend/src/types/openapi.d.ts` | **regenerate** | Generated from the contract — do not hand-edit. Regenerate so the accept request type and the error-code union match. No other `frontend/` file references these routes (verified 2026-08-06). |
| `backend/tests/test_invite_service.py` | **edit** | **D1:** service tests for `read_invite`. **D2:** delete the mismatch test (`:346`), drop `email=` from every `accept_invite` call, add the password-policy regression guard. |
| `backend/tests/test_invite_routes.py` | **edit** | **D1:** route tests for the lookup (reuse the `client` fixture and `_seed_invite` at `:44`). **D2:** delete the mismatch test (`:369`), drop `email` from accept request bodies, add the `422`-on-`email` test. |
| `backend/tests/test_invite_schemas.py` | **edit** | **D1:** model tests for `InviteLookupRequest` / `InviteLookupResponse` — valid payload accepted, extra fields rejected, missing `token` rejected. **D2:** update `AcceptInviteRequest` tests — `email` no longer required, and supplying it is now an extra-field rejection. |
| `backend/tests/test_contract_fidelity.py` | **edit** | Add `"InviteLookupResponse"` (and `"InviteLookupRequest"`) to `SCHEMA_NAMES` so the published schemas are compared against the app's. Do **not** add an `ERROR_RESPONSE_ROUTES` entry: that dict is keyed by response-component name, and `"AcceptInviteTokenGone"` already maps to `accept_invite_route`. A second entry under the same key would not add coverage — it would **overwrite** the existing one and silently stop testing the accept route. Route-to-route body equality is asserted in `test_invite_routes.py` instead. |
| `.claude/docs/backend/auth.md` | **edit (docs-sync)** | Code-map row for the lookup route and `read_invite`, once the code lands. Handled by `/docs-sync`, not by the implementing task. |

**No new modules, no new files.** Nothing under `backend/migrations/`, nothing in
`backend/src/api/main.py` (the router is already registered), nothing in `middleware.py`,
nothing in `dependencies/`, nothing in `hardware-agent/`. The only `frontend/` touch is the
regenerated type file.

Historical specs `017-auth-middleware-invite-flow/` and `023-auth-invite-contract-edges/`
describe the old accept shape. They are **history — do not rewrite them.**

Any path not listed above is out of scope for this feature.

---

## Constraints

- **The read must not mutate.** No consumption, no timestamp write, no session issuance, no
  commit. Enforced by test, not just by review.
- **Acceptance changes in exactly one way:** it stops taking an address. Its method, path,
  `201` + `LoginResponse` success shape, single-use semantics, and its three remaining
  failures (`invalid_invite_token`, `email_already_registered`, `password_policy_violation`)
  are unchanged. Any other edit to `accept_invite` is out of scope.
- **Re-source, do not delete.** The duplicate-user lookup and `validate_policy` must keep
  receiving the invited address, now from `invite.email`. See § Deliverable 2.
- **One error type, not three.** Expired, accepted, and unknown must be indistinguishable in
  status, `error.code`, and body.
- **No new disclosed field.** Three fields, no more, ever — `extra="forbid"` plus an exact
  whole-body assertion.
- **Style:** no comments and no docstrings in new code, including tests (project convention).
  The existing explanatory comments in `services/invites.py` and `routers/invites.py` belong to
  other decisions — do not move, reword, or delete them.
- **Gate (from `.claude/CLAUDE.md`):** run `./database.sh` **first**, then
  `uv run ruff check src tests` and `uv run pytest` from `backend/`. **Never run
  `ruff format`** — backend code is hand-formatted and a repo-wide format buries the diff. A
  bare `uv run pytest` without a live `dmitri_test` **silently skips** every DB-backed test and
  prints a meaningless green; a non-zero skip count means the run does not count.
- Rate limiting, invite lifetime, token generation, and single-use semantics are unchanged
  (`TRUTH.md` out-of-scope).

---

## Testing expectations

Three existing files, no new test module. Mirror the local patterns: `_seed_invite` and the
`client` / `administrative_session` / `seeded_org` fixtures in `test_invite_routes.py`, and
the direct-session style of `test_invite_service.py`.

### `backend/tests/test_invite_service.py` — `read_invite`

Mirror `test_accept_invite_unknown_token_raises_invite_token_error`
(`backend/tests/test_invite_service.py:297`) and its expired/consumed siblings.

| Test | Asserts |
|---|---|
| pending invite returns email, role, org name | the 3-tuple matches the seeded invite and its org's `name` |
| unknown token raises `InviteTokenError` | exception type **and** message string |
| expired invite raises `InviteTokenError` | same type, same message as unknown |
| consumed invite raises `InviteTokenError` | same type, same message as unknown |
| read does not mutate the invite | after a read, `consumed_at` is still `None`, `expires_at` unchanged, and no `User` row exists |
| read is repeatable | two consecutive calls return equal tuples |

### `backend/tests/test_invite_routes.py` — the route

Mirror `test_accept_expired_invite_returns_410` (`backend/tests/test_invite_routes.py:323`).
Each row maps to a `TRUTH.md` acceptance criterion:

| `TRUTH.md` criterion | Test | Asserts |
|---|---|---|
| Reads a live invitation | `..._returns_200_with_email_role_and_org_name` | `200`; `response.json() == {"email": …, "role": …, "org_name": …}` |
| Needs no authentication | `..._without_credentials_succeeds` | request sent with **no** `Authorization` header and no cookie; status is `200`, never `401`/`403` |
| Read is non-consuming | `..._twice_returns_identical_bodies` | both `200`; bodies equal; `Invite.consumed_at` still `None` in the DB |
| Read leaves acceptance intact | `..._then_accept_still_returns_201` | lookup ×N, then `POST /api/v1/invites/accept` → `201` with a `LoginResponse` and the refresh cookie |
| Accepted invitation is gone | `..._accepted_invite_returns_410` | `410`, `error.code == "invalid_invite_token"` |
| Expired invitation is gone | `..._expired_invite_returns_410` | `410`, `error.code == "invalid_invite_token"` |
| Unknown token is gone | `..._unknown_token_returns_410` | `410`, `error.code == "invalid_invite_token"` |
| No enumeration signal | `..._expired_and_forged_tokens_are_byte_identical` | expired vs fabricated token: equal `status_code` **and** equal `response.json()` (whole body, not just the code) |
| Failure matches acceptance | `..._gone_body_matches_accept_route_gone_body` | the lookup's `410` body equals the accept route's `410` body for a dead token — this is what makes the shared `AcceptInviteTokenGone` component honest |
| Discloses nothing extra | covered by the exact-equality assertion in the first row | the body has exactly three keys; no `org_id`, `invite_id`, `user_id`, `expires_at`, `created_at`, `token`, or `token_hash` anywhere in the serialised response |
| Lookup is advisory, not authority | `..._rejects_unknown_body_fields` | posting `{"token": …, "role": "admin"}` returns `422`, not `200` — the tampering attempt fails loudly rather than being ignored |

### `backend/tests/test_invite_routes.py` — deliverable 2

| `TRUTH.md` criterion | Test | Asserts |
|---|---|---|
| Acceptance still issues a session | existing accept-success tests, **edited** to drop `email` from the posted body | still `201` with a `LoginResponse` and the refresh cookie |
| Acceptance takes token and password only | same tests | a body of exactly `{"token": …, "password": …}` succeeds |
| A supplied address is rejected | `..._accept_rejects_email_field` (new) | posting `{"token", "password", "email"}` returns `422` — not `201`, and not a silently-ignored field |
| The account still comes from the invitation | `..._accept_creates_user_from_invite` | the created `User` row carries `invite.email`, `invite.role`, `invite.org_id` |
| Duplicate detection still works | existing already-registered test, **edited** | still `400 email_already_registered` with no `email` in the request |
| Mismatched-address failure is gone | `test_accept_mismatched_email_returns_400_invite_email_mismatch` (`test_invite_routes.py:369`) | **deleted** — the behaviour it asserts no longer exists |

### `backend/tests/test_invite_service.py` — deliverable 2

| Test | Action |
|---|---|
| `test_accept_invite_email_mismatch_raises_and_leaves_invite_unconsumed` (`:346`) | **deleted** — `InviteEmailMismatchError` is gone |
| existing `accept_invite` call sites throughout the file | **edited** — drop the `email=` keyword argument |
| Password rules still see the address | **new** — accept with a password the policy rejects on the basis of the *invited* address; assert `PasswordPolicyError`. This is the regression guard for the `validate_policy(email=invite.email)` re-sourcing, and the reason that line cannot simply be deleted |

### `backend/tests/test_invite_schemas.py`

`InviteLookupResponse` accepts a valid payload and rejects extra fields. `InviteLookupRequest`
gets the same pair plus a missing-`token` rejection, mirroring
`test_accept_invite_request_requires_token`. The extra-field rejection is not decoration: it is
what makes `TRUTH.md`'s authority rule observable — a request carrying `"role": "admin"` fails
with `422` rather than being silently dropped.

### `backend/tests/test_contract_fidelity.py`

Adding `"InviteLookupResponse"` to `SCHEMA_NAMES` makes the existing parametrised
`test_schema_matches_contract` cover the new schema — this is the "Contract is published"
criterion. The `410` needs no fidelity entry because it reuses `AcceptInviteTokenGone`, whose
enum is already pinned to `invalid_invite_token` and already checked against
`accept_invite_route`.
