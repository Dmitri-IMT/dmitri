# DR-0001 — Invite lookup travels as a body `POST`, not a query-string `GET`

**Status:** accepted
**Decided:** 2026-08-06, during `/refine-specs` on spec 027
**Scope:** this feature only. Not a service-wide rule about `GET` vs `POST`.

## Decision

The C14 invite lookup is:

```
POST /api/v1/invites/lookup
{ "token": "…" }
```

Not `GET /api/v1/invites?token=…`, despite that being the shape named by C14,
`docs/ui/SCREENS.md`, and the DMI-86 title.

## Why

The invitation token is a live single-use credential: accepting an invitation returns a
created session, so a leaked token is account creation inside the organisation, not a
disclosure of trivia.

Nothing under `backend/src/api/` configures logging for the web app — the only
`logging.basicConfig` is in the worker entrypoint. Uvicorn's **default access logger**
therefore applies, and its format writes the request target **including the query string**.
Under a `GET`, every read would write a live token to stdout, and to any edge proxy's logs.
Log aggregation is exactly where credentials outlive their TTL and get read by people who
should not see them.

A body `POST` avoids this with no configuration, and matches the precedent DMI-77 set
(2026-08-03, PR #110) when it moved this same token out of the **path** on the sibling
accept route, for the same reason.

## What was traded away

- **Verb honesty.** A non-mutating `POST` is mildly unidiomatic. Accepted: the alternative
  is a logging rule that a future change can silently break.
- **Cacheability.** Forfeited, and worthless anyway — the response is per-token and the
  token is single-use.

## Considered and rejected

**`GET` plus access-log scrubbing.** Preserves REST idiom, but requires logging
configuration the repo currently has none of, does not cover an edge proxy we do not
control, and encodes a standing rule that is invisible at the call site.

## Explicitly not a factor

These were raised and checked; neither moved the decision:

- **Browser history / address bar.** The emailed link is already a *frontend* URL,
  `{app_base_url}/invite?token=…` (`backend/src/api/services/mailer.py`). The token sits in
  history regardless of the API's shape. Mitigating that belongs to DMI-87.
- **`Referer` leakage.** Browsers default to `strict-origin-when-cross-origin`, so
  cross-origin subresources on the accept page receive only the origin, not the query.
- **Request tampering.** Not a differentiator — under either shape, the request contributes
  only the token. Role, organisation, and email are read from the invitation row at accept
  time (`services/invites.py:119-124`), so nothing a caller sends can escalate privilege.
  Recorded as a business rule in `TRUTH.md`.
- **Brute force.** Invite tokens are `secrets.token_urlsafe(32)` — 256 bits. Guessing is
  infeasible, which is what makes an unauthenticated, non-consuming lookup acceptable in the
  absence of any rate limiting.

## Consequence

The C14 registry described this ask as `GET /invites?token=…` in three places. All three
were corrected in the same session as this decision (2026-08-06), each marked *decided, not
yet built* so the docs do not claim an endpoint that does not exist:

- `docs/ui/FLOWS.md` — C14 row in § Contract asks
- `docs/roadmap/BACKEND.md` — C14 row in § B11
- `docs/ui/SCREENS.md` — the ACCEPT INVITE prose and its open-questions list

This matters because DMI-70 names that registry as canonical and DMI-87 (the frontend
accept-invite screen) will be planned from it; a stale `GET` there would have specced the
wrong client call.

Unrelated and deliberately untouched: `docs/ui/FLOWS.md:97` and `docs/ui/SCREENS.md:1319`
mention "no `GET /invites`" in the sense of **C4**, the admin invite *listing* endpoint
(DMI-76). Different ask, still open.

Still outstanding for `/docs-sync` after the code lands: the `.claude/docs` code-map entry
for the route and `read_invite`.
