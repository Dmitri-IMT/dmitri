# PLAN — Auth + invite contract edges (DMI-77)

> Closes contract asks **C13**, **C15**, **C18**. Branch:
> `feature/dmi-77-auth-invite-contract-edges-reset-codes-change-password-400`.
> Blocker DMI-60 is **Done** (PR #98). Research backing the decisions below:
> [`docs/research/auth-error-disclosure-and-invite-state.md`](../../docs/research/auth-error-disclosure-and-invite-state.md)
> and `docs/research/emailed-token-link-placement.md` (in flight).

## Narrative

Four auth/invite responses cannot tell the SPA what to say. Every error the API raises
funnels through `main.py:66-79`, which stamps `code` from `DEFAULT_CODES_BY_STATUS` unless the
raiser used `ApiError`. Three of these four routes raise bare `HTTPException`, so
*"your reset link is dead"*, *"your password is too weak"*, *"that email is already taken"* and
*"that email doesn't match the invite"* all arrive as `code: "bad_request"`. The screens DMI-87
and DMI-90 are being built against cannot branch on that.

C13 is largely already closed — spec 019 (DMI-72) landed the envelope and pinned
change-password's two codes. What remains of C13 is one line of contract wording.

C18's premise has partly gone stale: the "already a member" case exists and is tested. The
genuinely missing behavior is that `create_invite` never looks for an existing live invite, so
re-inviting silently mints a second valid token.

## Current state

| Surface | Status |
|---|---|
| `POST /auth/change-password` | **Done.** `auth.py:93-96` raises pinned codes; contract `PasswordChangeRejected` (L1299) pins the enum; `test_auth_routes.py:192` asserts 400-not-401. |
| `POST /auth/reset-password` | Token + policy collapse to one bare `HTTPException(400)` (`auth.py:113-116`) → both emit `bad_request`. Contract L775-777 carries a "not resolved here" marker. |
| `POST /invites/{token}/accept` | **Three** causes collapse into one `bad_request` (`invites.py:64-69`). `410` for a dead token already correct and tested. |
| `POST /invites` | `AlreadyMemberError` → bare `HTTPException(400)`. Live-invite check **does not exist**. |
| Contract fidelity | `test_contract_fidelity.py` fingerprints read-path schemas and query params only. **It never inspects error responses** — the issue's "fidelity check passes" is currently a no-op for this work. |

## Decisions

| # | Decision | Rationale |
|---|---|---|
| A | Keep the `401` on change-password; retitle it to pin it to session failures only | The route is bearer-authed, so `401` is genuinely reachable. RFC 9110 §11.6.2 confirms `401` is about the `Authorization` header — a body field is not a credential, so a wrong `current_password` is `400`. Deleting the `401` would make the contract lie. |
| B | `409 Conflict` for "address already has a live invite" | Definitional match in RFC 9110 including the "user might resolve the conflict and resubmit" clause. Matches `DeviceBusyError` (`openapi.yaml:508`), the one existing `409`. |
| Q1 | Reset-password's dead token moves `400` → **`410`**, matching accept-invite | C15's complaint is that a dead link and a weak password *share a status*. Pinning a code papers over that; splitting the status resolves it. Also makes the two token screens one pattern for DMI-87. Research is explicit that RFC 9110 **does not settle** this — `400` would also be compliant, and parity is the deciding argument. |
| Q3 | Inline code literals **plus** a real fidelity test | Nothing today cross-checks router literals against contract enums; a typo ships green. The new test walks the pinned enums and asserts the routes emit exactly those codes. |
| Q4 | `email_already_member` beats `invite_already_pending`; existing chains unchanged | The two codes lead to different admin actions — "nothing to do" vs "wait or reissue". Precedence is now user-visible, so it gets tests. |
| Q5 | **No** `Cache-Control: no-store` | Research recommended it because `410` is heuristically cacheable, but our `410` answers a **POST**, and RFC 9110 §9.3.3 makes POST responses cacheable only with explicit freshness info, which we never send. Adding a cache header to two responses in an app that has none anywhere would read as significant and isn't. |
| Q2 | Close the live-invite race with a **transaction-scoped advisory lock** | Two concurrent `create_invite` calls both pass the pending check under READ COMMITTED and both insert. Usually harmless — but `Invite.role` is per-row and `invites.py:93` reads it back at acceptance, so two racing invites with *different roles* let the invitee pick their own privilege by choosing which email to click. The lock costs ~2 lines and no migration; the index alternative is not buildable as stated (below). |

### Why not an index

`WHERE expires_at > now()` is **not indexable** — Postgres requires index predicates to be
IMMUTABLE and `now()` is STABLE, so the statement errors outright. The indexable alternative,
`WHERE consumed_at IS NULL`, is semantically wrong: nothing removes expired invites today, so it
would permanently block re-inviting anyone whose invite lapsed. Making it correct needs a
`sweep_expired_invites` janitor (precedent: `sweep_stale_commands`, `worker.py:42`) plus a
migration plus `IntegrityError` handling — all to close a race an admin has to trigger by
double-clicking.

## Code vocabulary

`password_policy_violation` is **one code across three routes** — same cause, same user
instruction. All bad-token cases (never issued, consumed, expired) collapse into a **single**
code per surface; the research flags that distinguishing them is observable to a token guesser.

| Route | Status | `error.code` |
|---|---|---|
| `POST /auth/reset-password` | 400 | `password_policy_violation` |
| | 410 | `invalid_reset_token` |
| `POST /invites/{token}/accept` | 400 | `invite_email_mismatch`, `email_already_registered`, `password_policy_violation` |
| | 410 | *(existing, unpinned — gets `invalid_invite_token`)* |
| `POST /invites` | 400 | `email_already_member` |
| | 409 | `invite_already_pending` |

`email_already_member` is **org-scoped** (`invites.py:46`); `email_already_registered` is
**global** (`invites.py:82`, the deliberate anti-probing design at contract L811-813). The
names carry that difference on purpose.

## Work

1. **reset-password codes + 410** — `routers/auth.py`: split the combined `except` into
   `InvalidResetTokenError` → `ApiError(410, code="invalid_reset_token")` and
   `PasswordPolicyError` → `ApiError(400, code="password_policy_violation")`.
2. **accept-invite codes** — `routers/invites.py`: split the 3-way `except` into the three
   codes above; pin the existing `410`.
3. **create-invite: live-invite check** — `services/invites.py`: take
   `pg_advisory_xact_lock(<namespace>, hashtext(org_id::text || lower(email)))` first, then the
   existing member check, then a new `PendingInviteError` when an unconsumed, unexpired invite
   exists for `org_id` + `lower(email)`. Router maps it to `ApiError(409, …)`. The lock releases
   on commit or rollback — no explicit unlock, no cleanup path. Nothing in this repo uses
   advisory locks yet, so the two-argument namespaced form goes in to keep a future second user
   from colliding; the namespace constant lives next to the call.
4. **Contract** — add `ResetPasswordRejected`, `ResetTokenGone`, `AcceptInviteRejected`,
   `InviteCreateRejected` mirroring the `PasswordChangeRejected` pattern (`allOf` + pinned
   `enum` + examples). Retitle change-password's `401`. Delete the L775-777 marker.
5. **Fidelity test** — extend `test_contract_fidelity.py` to extract pinned codes from those
   response components and assert the routes emit exactly that set.
6. **Route tests** — per-code assertions on all four surfaces, plus three precedence tests
   (dead token + weak password → *token*; member + pending → *member*) and one asserting a
   second invite to a live address mints no second token.
7. **Regenerate** `frontend/src/types/openapi.d.ts` via `npm run gen:types`.

### Added by user decision 2026-08-03 — token in the invite-accept path

Scope was widened from the issue's fence at the user's explicit direction ("we are not building
another issue, lets do it all here"). The second research note relocated the problem:

- **The email-link difference is cosmetic.** W3C's `strip-url` removes fragment, username and
  password — never path or query. The one spec that discriminates between URL components puts
  path and query on the same side, and RFC 9110 §10.1.3 offers one remedy for both. The
  `invite_link` / `reset_link` inconsistency at `mailer.py:45-52` has no security significance.
  **No change.**
- **The real finding is our own API.** `routers/invites.py:51` takes the invite token as a
  **path parameter**, so uvicorn's default access logger (no log config exists in this repo)
  writes a live single-use credential to a log line, as does any edge proxy. OWASP Logging
  mandates that access tokens be "removed, masked, sanitized, hashed or encrypted" in logs.
  `/auth/reset-password` takes its token in the body and does not have this problem.
- **The fragment option is folklore.** Three specs agree it never reaches a server, but no
  primary source recommends it for emailed links, and RFC 9110 §17.11 documents a
  redirect-inheritance hazard.

**Change:** move the token out of the path — `POST /api/v1/invites/accept` with the token in the
request body alongside `email` and `password`. Contract, router, `mailer.py` link target and the
route's `OPTIONS` preflight all move together.

**Cost is near zero right now and rises the moment DMI-87 ships:** `frontend/src/` has no
`/invite` or `/reset-password` route yet, so nothing consumes the current shape. DMI-87 and
DMI-90 must be told the route changed.

**Deliberately not decided here:** OWASP says "don't automatically log the user in" after a
*reset*, but `invites.py:59` returns a token pair on invite acceptance (contract ask C7,
resolved deliberately at L845-846). No source says whether the reset guidance extends to invite
acceptance. Left alone — reopening C7 is out of scope.

## Testing

Per-code and precedence assertions live with their surface (`test_auth_routes.py`,
`test_invite_routes.py`), not in `test_error_envelope.py` — that module's
`_assert_error_envelope` is private and this issue shouldn't refactor it. Duplicate the one
assertion that matters rather than promoting a helper.

## Gates

- `./database.sh --test` — a bare `uv run pytest` **skips** every DB-backed test and proves
  nothing here. Expect 665 passed / 0 skipped (measured 2026-08-03 at completion; the 619 this
  line previously quoted predated the feature).
- `uv run ruff check src tests`. **Never `ruff format`** — backend is hand-formatted.
- `cd frontend && npm run typecheck && npm run build` after regenerating types.

## Out of scope

- Invite resend/revoke — DMI-76.
- Rate limiting (NIST §5.2.2) and a concurrent-Argon2id cap. Both surfaced by the research,
  neither in DMI-77's Expected list. Follow-up issue.
- `WWW-Authenticate` on existing `401`s — RFC 9110 makes it a MUST and we don't send it.
  Pre-existing, app-wide, not this issue.
- Password strength meter, MFA, session cap, logout-everywhere.

## Open questions

None. All decisions above are settled; implementation can start.
