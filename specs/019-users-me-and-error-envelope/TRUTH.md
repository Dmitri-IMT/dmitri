# TRUTH — User profile + API error envelope (DMI-72)

## Narrative

The SPA cannot tell an `admin` from a `viewer`. `LoginResponse` returns a bare access token
and there is **no user resource in the contract at all**, so after a successful login the
frontend knows the user is authenticated and nothing else about them. ADR-008 §Papéis assumes
the role "comes in the JWT claims", but the contract documents no claims — so the frontend
would have to decode an unspecified payload to decide what to render.

This blocks the product's core UI rule: role-gated affordances are **absent, not disabled**
(SCREENS.md consistency rule 3). The `Users` nav item, `[Scan now]`, the network chooser and
the invite form all key off the role. Until the role is a documented contract, every one of
them is unbuildable. This feature closes contract asks **C16** (the role is not in the
contract), **C3** (there is no user resource) and **C13** (a mistyped current password must
not look like an expired session).

C13 is the sharp edge. A wrong `current_password` already returns `400` and not `401`, which is
correct — but it returns it as `{"detail": "..."}`, while the frozen contract publishes every
error as `{"error": {"code", "message", "details"}}`. The SPA's refresh interceptor keys off
status codes and its error rendering keys off `error.code`, so a response the interceptor
handles correctly is still one the UI cannot explain to the user. That envelope drift is
**app-wide**, not specific to change-password: every error the API raises today is shaped
`{"detail": ...}` and none of them match the contract the frontend was built against. Closing
C13 honestly means closing it everywhere, so the envelope becomes a property of the API rather
than a special case bolted onto one route.

A note on what this feature deliberately does **not** carry: the original brief asked for
`password_expires_at` so the settings screen could warn about a 3-month rotation. ADR-016
(accepted after the brief was written) removed forced rotation entirely on NIST SP 800-63B
grounds. There is no expiry to report, and the user record has no expiry field. That ask is
withdrawn, not deferred.

## Business rules

- **A signed-in user can read their own profile.** It returns, at minimum, their identifier,
  email and role. It is **read-only** — this feature exposes the profile, it does not edit it.
- **The role is authoritative from the profile resource.** The role is what the UI gates on.
  The access token's claims are an implementation detail of the session machinery, not a
  frontend contract — either the claims are documented as a contract, or they are explicitly
  declared not-a-contract and the role is read from the profile. Silence is not acceptable;
  the whole point of C16 is that the frontend is currently guessing.
- **Only the caller's own profile is reachable.** There is no path to another user's record
  here; user *management* is a separate feature.
- **An unauthenticated caller cannot read a profile** — it is rejected as unauthenticated, the
  same as every other authenticated route.
- **Every error response the API returns carries a machine-readable code**, a human-readable
  message, and a details object — the shape the frozen contract already publishes. This holds
  for every error the API raises, not only the ones this feature touches.
- **An unexpected internal failure is still an error response.** It carries the same envelope,
  and its message and details reveal nothing about the internal failure — no exception text, no
  stack detail. The frontend learns only that the request failed unexpectedly.
- **A code the frontend must branch on is published in the contract.** Shipping a code the UI
  keys off without publishing it recreates exactly the guessing C16 exists to end. Codes that are
  merely descriptive need no such promise; codes that drive a branch do.
- **A wrong current password on a password change is a client error, not an auth failure.** It
  reports as a `400` carrying a code the UI can branch on. It must never report as `401`,
  because the SPA's refresh interceptor treats `401` as an expired session and would bounce
  the user to the login screen for a typo.
- **No password expiry exists.** Per ADR-016 there is no forced rotation, so the profile
  reports no expiry and the UI has no expiry to warn about.

## User stories

1. As a viewer, I want to never see actions I cannot perform, so the product doesn't tease me
   with buttons that will only fail.
2. As an admin, I want to see `[Scan now]` and the `Users` nav, so I can actually do my job.
3. As any signed-in user, I want to see my own email and role, so I know which account I am
   using and what it can do.
4. As a user changing my password, I want a mistyped current password to tell me so, rather
   than silently logging me out.
5. As the frontend, I want every API error to arrive in one predictable shape with a code, so
   I can render a specific message instead of a generic failure.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Admin sees own role | an admin's access token | I request my own profile | I get 200 and the role reads `admin` |
| Viewer sees own role | a viewer's access token | I request my own profile | I get 200 and the role reads `viewer` |
| Profile carries identity | any valid access token | I request my own profile | the response carries my user identifier and my email, matching the account that signed in |
| Profile requires auth | no access token | I request my own profile | I get 401 |
| Profile rejects a bad token | a malformed or expired access token | I request my own profile | I get 401 |
| Profile is scoped to me | a valid access token | I request my own profile | the response describes the calling user only, with no route to any other user's record |
| No expiry field | any valid access token | I request my own profile | the response contains no password-expiry field (ADR-016) |
| Wrong current password is a 400 | an authenticated user | I submit a password change with an incorrect current password | I get 400, and the body carries an `error.code` identifying it as a wrong-current-password failure, distinguishable from a policy rejection |
| Wrong current password is never a 401 | an authenticated user | I submit a password change with an incorrect current password | the status is not 401, so the SPA's refresh interceptor does not fire |
| Weak new password still rejected | an authenticated user | I submit a policy-violating new password | I get 400 with a code meaning policy rejection, and my password is unchanged |
| Errors carry the envelope | any API route that fails | I trigger a failure (unauthenticated, forbidden, not found) | the body is `{"error": {"code", "message", "details"}}` with all three present, and no bare `detail` key |
| An unexpected failure carries the envelope | any API route | the route raises an unanticipated error | I get 500 and the envelope, carrying the code the contract already publishes for it, with no internal error text leaked into the message or details |
| Envelope is app-wide | the existing authenticated, admin-gated and lookup routes | I trigger their 401 / 403 / 404 responses | each returns the envelope shape, not `{"detail": ...}` |
| Status codes unchanged | every route that returned a given status before this change | I trigger the same conditions | the status codes are identical; only the body shape changes |
| Health failure keeps its code | the database is unreachable | I call the health route | it still returns 503 with code `database_unreachable`, unchanged |
| Agent channel rejections carry the envelope | an agent whose connection to the command channel is refused | the refusal is returned | it carries the envelope, matching what the contract already publishes for that refusal |
| Contract documents the resource | the frozen contract | I read it | the profile route, its response schema, and the token-claims position (documented or declared not-a-contract) are all present |
| Contract publishes the branchable codes | the frozen contract | I read the password-change failure response | both the wrong-current-password and the policy-rejection codes are published as pinned values, so the frontend branches on a promise rather than a guess |
| Suite green | the touched scope | I run `uv run pytest` and `uv run ruff check` | both pass |

## Out of scope (v1)

- **Password expiry / forced rotation** — withdrawn, not deferred. ADR-016 removed it; the
  original DMI-72 brief predates that ADR.
- **User management** — listing users, inviting, changing roles. Owned by the Users & invites
  admin API issue. This feature adds exactly one read-only self resource.
- **Profile editing** — no display-name or email updates. The user record has no display name
  today and this feature does not add one.
- **Reset-password and accept-invite error-code disambiguation (C15)** — owned by **DMI-77**.
  This feature builds the envelope *mechanism* and must leave a per-route override seam so
  DMI-77 can assign its semantic codes without rework. It does **not** decide those two routes'
  codes.
- **Request-validation (422) envelope conformance** — the contract publishes a
  `validation_error` response, but the framework's default validation body does not match it.
  This is **pre-existing drift, not introduced here**, and no frontend flow blocks on it.
  Reaffirmed out of scope during refinement; file a follow-up issue.
- **Role enforcement changes** — the admin gate already exists and is not modified. This
  feature exposes the role; it does not change who is allowed to do what.

## Resolved during refinement

Four decisions were taken while stress-testing these specs; all are now reflected inline above
and in `ARCHITECTURE.md`.

- **422 validation bodies stay out.** Reaffirmed: it is not one of C3/C13/C16 and it expands the
  blast radius from "errors we raise" to "errors the framework raises". File a follow-up issue.
- **500 responses are swept in.** The contract publishes `internal_server_error` on every route
  while the runtime emits plain text — the widest envelope gap in the API, and closing it is a
  handful of lines. New business rule and acceptance row above.
- **The agent command channel's refusals are swept in.** Its rejections already change shape as an
  unavoidable consequence of the envelope, and the contract already documents them as enveloped;
  the feature now states this and tests it rather than letting it happen silently.
- **The password-change codes are published in the contract.** Telling the SPA to branch on a value
  the contract never promises is the same defect as C16. New business rule and acceptance row above.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Product decisions: `docs/adr/ADR-008-frontend-stack.md` (§Papéis, §Auth Client),
  `docs/adr/ADR-016-password-policy.md` (no rotation), `docs/roadmap/AUTH.md` (role matrix)
- Contract asks: `docs/ui/FLOWS.md` §Contract asks (C3, C13, C16), `docs/ui/SCREENS.md` rule 3
- Frozen contract: `contracts/openapi/openapi.yaml` (`ErrorResponse`, `ErrorBody`)
- Adjacent, must not collide: `specs/016-sessions-auth-routes/` (DMI-60, shipped), DMI-77 (C15)
- Execution ledger: `POOP.md` (written during orchestration)
