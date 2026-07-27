# ARCHITECTURE — `GET /users/me` + global error envelope (DMI-72)

Implements `TRUTH.md`. This is a **backend** feature (`backend/src/api/…`, FastAPI + SQLModel).
It touches no hardware-agent code, no `scanner/`, no `tui/` — the `.claude/CLAUDE.md`
ScanRunner/ScanProgressScreen thread-through rule is **N/A here**. It does cross a real layer
boundary (backend → `contracts/openapi/openapi.yaml` → generated frontend types), so this spec
ships with an `INTEGRATION.md`.

## System context

Two independent, small changes landing in one spec because they share a seam (every raise site
in the app) and because C13's acceptance criteria require the envelope to exist before the
wrong-password code can be observed as anything other than `{"detail": ...}`.

```
HTTP request ──routing──► require_user (existing, unchanged) ──► CallerIdentity(sub, org_id, role)
                                │
                                ▼
                     routers/users.py (new) ──► session.get(User, caller.sub) ──► UserProfileResponse

Any raise site (20 existing HTTPException(...) call sites + this feature's new ones)
                                │
                                ▼
                     app.exception_handler(HTTPException) (new, main.py)
                                │
                                ▼
                     {"error": {"code", "message", "details"}}  (JSONResponse)
```

Middleware ordering is unchanged and unaffected: `NoContentCorsMiddleware` then
`RequestIdMiddleware` wrap every response including error responses, same as today — a FastAPI
exception handler runs *inside* the ASGI app FastAPI wraps, so both middlewares still see and
decorate the final response (CORS headers, `X-Request-Id`). No middleware ordering change is
part of this feature.

`GET /api/v1/health` (`backend/src/api/main.py:51-66`) does **not** raise `HTTPException` — its
503 path returns a hand-built `JSONResponse` directly, bypassing routing exception handling
entirely. The new global handler only fires for raised `HTTPException` instances, so the health
route's existing envelope is untouched by construction, not by a special-case in the handler.
Verified by reading the route: it has no `try/except` that raises, only a `try/except
SQLAlchemyError: return JSONResponse(...)`.

## Data model / contracts

### `GET /api/v1/users/me` (new)

Reuses `require_user` (`backend/src/api/dependencies/auth.py`) — no token re-decoding. Looks up
the `User` row (`backend/src/api/models/identity.py`) by `caller.sub` for `email`; `role` is
read from the same row, **not** from the JWT claims, so it satisfies "the role is authoritative
from the profile resource" (TRUTH business rules) even though today `User.role` and the JWT's
`role` claim always agree (`services/auth.py::issue_session` mints both from the same row at
login time — divergence would only appear if a role changed and the caller hadn't re-logged-in,
which is out of scope here).

Response schema `UserProfileResponse` (`backend/src/api/schemas/users.py`, new):

| Field | Type | Source |
|-------|------|--------|
| `user_id` | UUID | `User.id` |
| `email` | str | `User.email` |
| `role` | `Literal["admin", "viewer"]` | `User.role` |

`model_config = ConfigDict(extra="forbid")`, matching every other schema in `schemas/auth.py` /
`schemas/invites.py`. No `password_expires_at`, no `display_name` — neither field exists on
`User` and ADR-016 forbids adding the former (TRUTH "No expiry field").

If `session.get(User, caller.sub)` returns `None` (the account was deleted after the token was
issued), the route raises `HTTPException(status_code=401, detail="Not authenticated")` — the
exact pattern already used at `routers/auth.py:85-87` in `change_password_route`. This is not a
new failure mode; it is the existing "token valid, subject gone" case reused.

**No `OPTIONS` preflight twin.** The derived-preflight loops at the bottom of `routers/auth.py`
and `routers/invites.py` filter on `if "POST" in _route.methods`, so they produce nothing for a
GET route; and the GET-only routers (`hosts.py`, `scans.py`, `findings.py`) have no preflight loop
at all, with `/api/v1/hosts` carrying only `get:` in the contract. Real browser preflights are
answered by `NoContentCorsMiddleware` before routing — as the comment on the auth loop states, the
router-level handlers exist only to serve *bare* `OPTIONS` requests. `/users/me` follows the GET
house style: no `OPTIONS` route, no `options:` entry in `openapi.yaml`.

### C16 — JWT-claims documentation decision

**Decision: declare the claims explicitly not-a-contract**, rather than documenting their shape
in `openapi.yaml`. `FrontendBearerAuth`'s `description`
(`contracts/openapi/openapi.yaml:882-887`) gains one sentence:

> The token's internal claims are an implementation detail of the session machinery and are not
> part of this contract — do not decode it client-side. Call `GET /api/v1/users/me` for the
> caller's identity and role.

Rationale: `backend/src/api/services/tokens.py` mints `sub`/`org_id`/`role`/`iat`/`exp` today,
but OpenAPI's `http`/`bearer` security scheme has no standard vehicle for documenting a JWT's
claim shape — it would have to live in a `description` freeform block or an `x-` extension
either way, and doing that commits the contract to never changing the claim set without a
version bump. `/users/me` is the one real per-request source of truth the frontend needs
(TRUTH: "the role is authoritative from the profile resource"); documenting claims as a second,
parallel contract for the same fact is the drift C16 exists to close, not a fix for it. This is
a documentation-only edit — no code reads or writes claims differently.

### Error envelope

**Central design decision: status-derived default codes, with an explicit per-site override.**

Two options were on the table. Explicit per-site codes (editing all ~20 raise sites, agreeing a
full taxonomy now) is more precise but is exactly the "big-bang rename" TRUTH's `Open question`
section and the C15/DMI-77 fence both warn against — DMI-77 needs to add wrong-token and
weak-password codes to `reset-password`/`accept-invite` later without this feature having
already renamed everything under it. Status-derived defaults touch **zero** of the 20 existing
sites (they already do the right thing: right status, string `detail`) and give every route the
correct envelope shape for free. The one place TRUTH requires precision **today** — C13's
wrong-current-password code — gets it through the override, added at exactly one call site.

**Mechanism — concrete, so the implementer does not have to invent it:**

`backend/src/api/errors.py` (new):

```python
class ApiError(HTTPException):
    def __init__(self, status_code, detail, *, code):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
```

**No `details` parameter.** Nothing in this feature's scope populates `details` — the two C13
raises pass only `code=`, and the only in-repo examples of a populated `details` are the 422
shapes this feature explicitly excludes. Per `.claude/CLAUDE.md` §2 ("no configurability that
wasn't requested"), `details` is always `{}` and is not settable. DMI-77 or a 422 follow-up adds
the parameter when it has a value to put in it — a two-line change in a file it is already
editing.

`ApiError` **is** an `HTTPException` (subclass), so it is caught by the same global handler as
every bare `HTTPException` — no second handler, no `isinstance` branching needed at the routing
layer beyond the one check described below.

`_DEFAULT_CODES_BY_STATUS` (module-level dict in `errors.py`), covering every status code any
current raise site uses: `{400: "bad_request", 401: "unauthorized", 403: "forbidden", 404:
"not_found", 410: "gone"}`. A status not in the map falls back to `"error"` (defensive; nothing
in the current codebase raises an uncovered status via `HTTPException`).

**Register the handler on Starlette's `HTTPException`, not FastAPI's.** `fastapi.HTTPException`
is a *subclass* of `starlette.exceptions.HTTPException`, and Starlette's exception middleware
resolves handlers by walking the raised exception's MRO. Registering under the FastAPI class
therefore catches only exceptions the application raises — it would **miss** the ones Starlette's
router raises itself: the `404` for an unmatched path and the `405` for a wrong method. Those
would silently keep FastAPI's default `{"detail": "Not Found"}` body and quietly violate TRUTH's
"no bare `detail` key" acceptance row. Registering on the Starlette base class catches both, since
every `fastapi.HTTPException` is one:

```python
from starlette.exceptions import HTTPException as StarletteHTTPException
```

Add `405: "method_not_allowed"` to `_DEFAULT_CODES_BY_STATUS` alongside the statuses listed above
for the same reason — it is now reachable through the handler.

Global handler (`backend/src/api/main.py`, new):

```python
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = exc.code if isinstance(exc, ApiError) else _DEFAULT_CODES_BY_STATUS.get(exc.status_code, "error")
    message = str(exc.detail) if exc.detail else code
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "details": {}}},
    )
```

Registering on `StarletteHTTPException` **replaces** FastAPI's own default handler rather than
sitting beside it — FastAPI seeds `exception_handlers` with that exact key. So there is no handler
ordering to reason about and no path by which a bare `{"detail": ...}` body can still be emitted
on the `HTTPException` route.

`message` falls back to `code` only if `detail` is falsy — every existing raise site already
passes a non-empty `detail` string, so in practice `message` is always that string. This is a
defensive fallback, not a behavior change for any existing route.

**The one call site this feature edits to use the override** — `routers/auth.py`,
`change_password_route` (currently lines 88-96), which today catches
`(WrongCurrentPasswordError, PasswordPolicyError)` in one `except` and raises one undifferentiated
`HTTPException(400, ...)` (TRUTH: "the two exceptions currently collapse to the same
undifferentiated response"). It becomes two `except` clauses:

```python
except WrongCurrentPasswordError as exc:
    raise ApiError(400, str(exc), code="wrong_current_password") from exc
except PasswordPolicyError as exc:
    raise ApiError(400, str(exc), code="password_policy_violation") from exc
```

Both stay `400` — **no status code changes**, per the hard constraint. This is the acceptance
row "Wrong current password is a 400 ... distinguishable from a policy rejection" made real.

**The seam DMI-77 inherits:** `reset-password` and `accept-invite` keep their current bare
`HTTPException(400/410, detail=str(exc))` raises in this feature — this feature does **not**
touch `reset_password_route` or `accept_invite_route`. DMI-77 assigns its C15 codes by changing
those two routes' `except` blocks to raise `ApiError(status_code, str(exc), code="...")` instead
of `HTTPException`, exactly mirroring the `change_password_route` edit above. No new mechanism,
no rework — the override already exists and is proven at one call site.

**The agent WebSocket upgrade path — in scope, and this is a drift fix, not a freebie.**
`require_agent_ws` (`dependencies/agent_auth.py:144-146`) raises `HTTPException(401/403)` during a
**WebSocket** handshake. Starlette's `wrap_app_handling_exceptions` resolves the same handler in
websocket scope, calls it with a `WebSocket` (not a `Request`), and sends the returned response as
an HTTP denial response — which is why `tests/test_require_agent_ws.py` asserts against
`WebSocketDenialResponse`. So the new handler changes that denial body from `{"detail": ...}` to
the envelope. `openapi.yaml:475-478` already documents that route's `401`/`403` as
`Unauthorized`/`Forbidden`, both `$ref`ing `ErrorResponse`, so today's body is **pre-existing
contract drift and this feature closes it**. Two consequences the implementer must handle:

- The handler's first parameter is annotated `request: Request` but receives a `WebSocket` in this
  path. The body only reads `exc`, so this is sound — annotate it `Request` anyway to match
  Starlette's own `ExceptionHandler` convention, and do not add a scope branch.
- `main.py:41-46`'s separate `ws_validation_denial` handler (malformed `{agent_id}`) sends a
  bodiless `Response(status_code=403)`. Left alone, that route would return the envelope for a
  revoked device and an empty body for a malformed id — two shapes for one documented response.
  **Change it to send the envelope** (`JSONResponse`, `code="forbidden"`, `details={}`). The
  existing comment's RFC 6455 123-byte concern governs the WebSocket *close reason*, not an HTTP
  denial body, so a small JSON envelope is fine; keep the comment but narrow it to the close-frame
  case it actually describes.

No hardware-agent change is needed: a grep of `hardware-agent/src/agent/` finds no reader of
`detail` or of any denial-response body, so the shape change regresses no client.

**Unhandled exceptions (500) — in scope.** The contract `$ref`s
`#/components/responses/InternalServerError` (code `internal_server_error`) on **every route**,
but an unhandled exception never reaches the `HTTPException` handler: Starlette's
`ServerErrorMiddleware` emits a plain-text `Internal Server Error` body. Without this, the
contract's most widely-referenced error response would be the one response still not matching the
envelope. Second handler in `main.py`:

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "Internal server error.",
                "details": {},
            }
        },
    )
```

`message` is a **fixed string** and `details` is always `{}` — `str(exc)` must never reach the
body (TRUTH: "reveal nothing about the internal failure"). This differs deliberately from the
`HTTPException` handler, where `detail` is author-written and safe to surface.

FastAPI installs an `Exception` handler as `ServerErrorMiddleware`'s handler, which **re-raises
after sending the response**. So tracebacks still surface in logs and `TestClient` still re-raises
under its default `raise_server_exceptions=True` — no debugging or existing-test behavior changes.
The consequence for testing: asserting this body requires
`TestClient(app, raise_server_exceptions=False)` (see Testing expectations).

`ServerErrorMiddleware` sits **outside** `NoContentCorsMiddleware`/`RequestIdMiddleware` — unlike
the `HTTPException` path, a 500 response is therefore **not** decorated with CORS headers or
`X-Request-Id`. That is today's behavior and this feature does not change it; it is noted so the
implementer does not mistake it for a regression introduced here.

**Amendment (human-approved 2026-07-27): 422 was pulled into scope during the pre-push audit.**
The out-of-scope call below was made without knowing that FastAPI's default validation body
echoes the rejected value back in `input` — and both `ChangePasswordRequest.new_password` and
`ResetPasswordRequest.new_password` are `constr(min_length=MIN_LENGTH)`, so a weak-password
attempt reflected the plaintext password to the client. That is a credential leak, not a
cosmetic contract gap, so the seam described below was built as specified:
`validation_exception_handler` in `main.py`, `code="validation_error"`, `details.field` from the
first error via `errors.field_path`, fixed message, `input`/`ctx` never read. `ApiError` still
gained **no** `details` parameter — the handler builds its envelope directly, so the reasoning
below about deferring that parameter still holds. The paragraph below is left intact as the
record of the original decision.

**422 request-validation bodies are explicitly out of scope.** FastAPI's default
`RequestValidationError` handler is untouched by this feature; a `422` response keeps its
current `{"detail": [...]}` shape. If a future follow-up picks this up, the seam is
`@app.exception_handler(RequestValidationError)` in `main.py`, mapped through the same
`{"error": {...}}` shape with `code="validation_error"` (already a pinned contract code — see
`contracts/openapi/openapi.yaml`'s `ValidationError` response component) and `details` built
from `exc.errors()` — which is also the change that would add a `details` parameter to `ApiError`.
Not built here; noted so the next implementer does not have to rediscover where it goes.

### `openapi.yaml` additions

- New path `/api/v1/users/me` under a new `users` tag (`Read-only self profile.`), `GET`,
  `security: [FrontendBearerAuth: []]`, `200` → new schema `UserProfileResponse`
  (`user_id` `format: uuid`, `email` `format: email`, `role`
  `enum: [admin, viewer]` — matching the pydantic `Literal` and the existing inline role enum at
  `openapi.yaml:2173`; all three `required`, `additionalProperties: false`), `401` →
  `$ref: '#/components/responses/Unauthorized'`. **No `options:` entry** — see the GET house-style
  note above.
- **New `PasswordChangeRejected` response component, pinning C13's two codes.** Today
  `/api/v1/auth/change-password`'s `400` (`contracts/openapi/openapi.yaml:713-718`) `$ref`s the
  generic `BadRequest`, whose only published code is `bad_request`. TRUTH requires the SPA to
  branch on `error.code`, so shipping the codes without publishing them would recreate C16's exact
  failure mode — a value the frontend must key off that the contract never promises. Add a
  component in the established house style of `DeviceBusyError` / `DeviceOfflineError`
  (`openapi.yaml:1213-1240`): `allOf` over `ErrorResponse` narrowing `error.code` to
  `enum: [wrong_current_password, password_policy_violation]`, a description saying **"The `code`
  is pinned: the SPA switches on it to choose which field to flag"**, and one example per code.
  Point change-password's `400` at it (replacing the `BadRequest` `$ref`) and fold the existing
  must-be-400-not-401 C13 sentence into the new component's description rather than duplicating it.
  `enum` is used, not `const`, because two values are legal here. This also gives the regenerated
  `openapi.d.ts` a real union type instead of a bare `string`.
- `FrontendBearerAuth.description` gains the not-a-contract sentence (C16, above).
- `/api/v1/invites/{token}/accept`'s `410` response (`contracts/openapi/openapi.yaml:858-860`)
  currently has **no `content`/schema at all** — undocumented body shape. This feature adds
  `content: application/json: schema: $ref: '#/components/schemas/ErrorResponse'`, matching
  every other error response's shape, without adding an `examples` block or pinning a `code`
  (that value is DMI-77's to choose). This is the one pre-existing contract gap this feature's
  "envelope is app-wide" acceptance criterion reaches, because the route already returns `410`
  today and will now actually return the envelope shape at runtime.
- No other path or schema changes. `BadRequest` / `Unauthorized` / `Forbidden` / `NotFound`
  response components already reference `ErrorResponse` — the contract already promised the
  envelope on every route that uses them; this feature makes the runtime match the promise it
  already made, it does not add new response refs to existing routes.

## New files and naming (mandatory)

| Path | Action | Notes |
|------|--------|-------|
| `backend/src/api/errors.py` | create | `ApiError(HTTPException)` (`code` only, **no `details`**), `_DEFAULT_CODES_BY_STATUS` dict |
| `backend/src/api/main.py` | touch | add `from api.errors import ApiError` (used only for the `isinstance` check), the `_DEFAULT_CODES_BY_STATUS` import, the `@app.exception_handler(StarletteHTTPException)` handler (**Starlette's base class, not FastAPI's** — see Data model / contracts) and the `@app.exception_handler(Exception)` 500 handler; change `ws_validation_denial`'s bodiless `Response(403)` to a `JSONResponse` carrying the envelope. Add `users` to `from api.routers import ...` and `app.include_router(users.router)` |
| `backend/src/api/routers/users.py` | create | `router = APIRouter()` + `read_current_user` (`GET /api/v1/users/me`), mirroring the shape of `routers/hosts.py` (full path in the decorator, `Depends(get_session)` + `Depends(require_user)`, `response_model=`). **No preflight handler** — GET house style, see Data model / contracts |
| `backend/src/api/schemas/users.py` | create | `UserProfileResponse` pydantic model |
| `backend/src/api/routers/auth.py` | touch | `change_password_route`: split the shared `except (WrongCurrentPasswordError, PasswordPolicyError)` into two `except` clauses raising `ApiError` with `code="wrong_current_password"` / `code="password_policy_violation"`; import `ApiError` from `api.errors` |
| `backend/src/api/routers/invites.py` | untouched by this feature | still raises bare `HTTPException` — envelope applies via the global handler's default-code path; no per-site edit needed or made here |
| `backend/src/api/routers/hosts.py` | untouched | same — default-code path covers its `404` |
| `backend/src/api/routers/scans.py` | untouched | same — default-code path covers its `404` |
| `backend/src/api/dependencies/auth.py` | untouched | `require_user` / `require_admin` keep raising bare `HTTPException(401/403, ...)` — default-code path covers both |
| `backend/src/api/dependencies/agent_auth.py` | untouched | its `401`/`403` raises are covered by the default-code path. Note `require_agent_ws` raises in **websocket** scope — the same handler runs there and its response becomes the WS denial body, closing pre-existing contract drift (see Data model / contracts) |
| `backend/tests/test_require_agent_ws.py` | touch | extend the existing denial assertions (currently status-only) to assert the envelope body on the `401`, the revoked-device `403`, and the malformed-`{agent_id}` `403` |
| `contracts/openapi/openapi.yaml` | touch | `users` tag, `/api/v1/users/me` GET (no `options:`), `UserProfileResponse` schema, new `PasswordChangeRejected` response component + repointing change-password's `400` at it, `FrontendBearerAuth` description edit, `/api/v1/invites/{token}/accept`'s `410` gains a `content` schema (see above) |
| `frontend/src/types/openapi.d.ts` | regenerate | `npm run gen:types` from `frontend/` — see `INTEGRATION.md` |
| `backend/tests/test_users_routes.py` | create | mirrors `backend/tests/test_read_endpoints.py`'s auth-gate shape (no bearer → 401; bad bearer → 401) plus its own 200 assertions |
| `backend/tests/test_users_schemas.py` | create | mirrors `backend/tests/test_auth_schemas.py` — `extra="forbid"`, field types |
| `backend/tests/test_error_envelope.py` | create | app-wide envelope assertions — see Testing expectations |
| `backend/tests/test_auth_routes.py` | touch | extend the existing `change_password_route` tests to assert `error.code` distinguishes wrong-password from policy-violation |

## Constraints

- **Status codes must not change anywhere.** The global handler reads `exc.status_code` off the
  exception exactly as raised today; it does not remap statuses. Every existing `pytest`
  assertion on a status code keeps passing unmodified.
- **Do not decide reset-password or accept-invite error codes.** Those two routes are not edited
  by this feature beyond the one `openapi.yaml` `content`-schema addition on `410` (a body-shape
  fix, not a code choice). DMI-77 assigns `code=` values there using the `ApiError` mechanism
  this feature ships.
- **422 request-validation is out of scope.** No `RequestValidationError` handler is added. See
  the seam note above.
- **The health route's hand-rolled envelope is not touched and must not double-wrap.** It does
  not raise `HTTPException`, so the new global handler never intercepts it — verified by reading
  `main.py:51-66`, not assumed.
- **The 500 handler must never leak internals.** Fixed `message`, empty `details`, no `str(exc)`
  anywhere in the body. This is the one handler whose input is untrusted.
- **`details` is always `{}`.** No raise site in this feature sets it and `ApiError` cannot.
- **No new infrastructure.** `errors.py` is a plain module; nothing here needs
  `HUMAN_INFRA_REQUIRED`.
- **Style** — no comments or docstrings in new code, including tests (project convention,
  `docs/README.md` global conventions). The `ApiError` code block shown above is illustrative for
  this document; the implementer writes it without comments.
- **`/users/me` is read-only.** No `PATCH`/`PUT` route, no request body, no write path — TRUTH is
  explicit this feature does not add profile editing.
- **`frontend/src/types/openapi.d.ts` is generated, never hand-edited** (ADR-008) — see
  `INTEGRATION.md`.

## Testing expectations

- **`/users/me` route** (`backend/tests/test_users_routes.py`, mirroring
  `backend/tests/test_read_endpoints.py`'s bearer-gate pattern): no bearer → `401` envelope; a
  malformed/garbage bearer → `401` envelope; a valid admin token → `200` with `role: "admin"`
  and the seeded email/id; a valid viewer token → `200` with `role: "viewer"`; response has no
  `password_expires_at` key (explicit negative assertion, pins ADR-016). Only the caller's own
  record is ever returned — there is no id-taking variant of this route to test for cross-user
  leakage, so this is structural (no path param), not a runtime check.
- **`UserProfileResponse` schema** (`backend/tests/test_users_schemas.py`, mirroring
  `backend/tests/test_auth_schemas.py`): `extra="forbid"` rejects an unknown field; required
  fields present.
- **Error envelope, app-wide** (`backend/tests/test_error_envelope.py`, new — no existing test
  file to mirror since, per the survey, zero current tests assert body shape): for each of a
  `401` (no bearer on `/api/v1/users/me` or `/api/v1/hosts`), a `403` (viewer bearer on
  `POST /api/v1/invites`), and a `404` (unknown host id with a valid bearer), assert the body is
  exactly `{"error": {"code": ..., "message": ..., "details": ...}}` with all three keys present
  and **no top-level `detail` key**. Assert the specific default codes: `unauthorized`,
  `forbidden`, `not_found`. **Also assert an unmatched path (e.g. `GET /api/v1/nope`) returns the
  `404` envelope with code `not_found`, and a wrong method on a real route returns the `405`
  envelope** — these are the Starlette-raised cases that a handler registered on the wrong
  exception class would miss, so they are the regression test for that specific mistake. **Assert
  the `500` envelope**: mount a throwaway route (or monkeypatch an existing dependency) that raises
  a bare `RuntimeError("boom")`, drive it through
  `TestClient(app, raise_server_exceptions=False)` — the default `True` re-raises before the body
  can be read — and assert the body is the envelope with code `internal_server_error`, plus the
  explicit negative that `"boom"` appears **nowhere** in the response body (pins the no-leak rule).
  Assert `GET /api/v1/health` under a forced `SQLAlchemyError` still
  returns its existing hand-built `503` `database_unreachable` envelope unchanged (regression
  guard against double-wrapping — mirrors the existing `test_health.py` DB-failure test, extended
  to also assert envelope shape explicitly rather than trusting it implicitly).
- **WebSocket denial envelope** (`backend/tests/test_require_agent_ws.py`, touch): the existing
  denial tests already capture `WebSocketDenialResponse` and assert `status_code` only. Extend
  three of them — a bad-signature `401`, `test_revoked_device_refused_with_403`, and
  `test_malformed_agent_id_path_refused_without_burning_nonce` — to also assert the response body
  is the envelope with codes `unauthorized` / `forbidden` / `forbidden`. These are the regression
  guard for the websocket-scope behavior described above; without them the WS denial shape is
  changed by this feature and asserted by nothing.
- **C13 differentiation** (`backend/tests/test_auth_routes.py`, touch): a wrong
  `current_password` → `400`, `error.code == "wrong_current_password"`; a policy-violating
  `new_password` (correct current password) → `400`, `error.code == "password_policy_violation"`;
  both assert **not** `401` (the acceptance row's explicit anti-regression check). Both keep
  using the existing test's fixtures/setup — only the assertions on the body grow.
- **Quality gates**: `uv run pytest` and `uv run ruff check` pass on the touched scope, run from
  `backend/`, per TRUTH's "Suite green" acceptance row.
