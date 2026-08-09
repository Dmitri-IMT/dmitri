# ADR-017: Account removal — hard delete, self-service, and the last-admin invariant

> **Status:** Accepted (2026-08-08). **Amends** [`AUTH.md`](../roadmap/AUTH.md) Phase 1 — the role
> matrix gains a removal capability, and "Audit — who logged in" is no longer purely Phase 2.
> **Reverses** the "No user deletion/deactivation" exclusion carried by DMI-76 and DMI-90.

## Context

Dmitri has an invite flow but no way out of it. `POST /invites` creates members; nothing removes
them. [`AUTH.md`](../roadmap/AUTH.md) Phase 1's role matrix has four capabilities — read, trigger
scan, invite users, Pi provisioning — and none of them is "remove a member". Both issues that
touch the Users surface (DMI-76, DMI-90) list user deletion under **NOT expected**, and
[`ui/IDEAS.md`](../ui/IDEAS.md) parks last-login display as a later idea.

That leaves one real, immediate gap: **a person who leaves the company keeps a working account.**
Their password still authenticates, their refresh token still rotates for up to seven days, and
they still read every scan, host and finding in the org. For a security product this is the wrong
default, and it needs no new hardware, contract work or Pi involvement to fix.

A second, smaller gap sits next to it: an admin looking at their org cannot tell an active account
from a dormant one, because nothing records when anyone was last here.

Both were scheduled for Phase 2. Both are pulled into September by this ADR.

## Decision

### 1. Removal is a hard delete

`DELETE` the `users` row and cascade its dependents. There is no `deactivated_at`, no soft-delete
tombstone, and no "disabled" account state anywhere in the product.

Only two tables reference `users`, and both are session ephemera:

| Table | On removal |
|-------|------------|
| `refresh_tokens` | Cascade delete — also the mechanism that ends the removed user's live session |
| `password_reset_tokens` | Cascade delete |

Soft delete was rejected on a concrete, repo-specific ground rather than on taste.
[`models/identity.py`](../../backend/src/api/models/identity.py) puts a **globally unique index on
`lower(email)`**, and `create_invite` raises `AlreadyMemberError` from a member lookup. A retained
tombstone row would therefore occupy its email address permanently: the person could not be
re-invited after an honest mistake or a return to the company without additionally releasing the
address or converting the index to a partial one. Soft delete would buy history we have no surface
for, at the cost of breaking the single most likely follow-up action.

### 2. Two routes, two authorization rules

| Route | Auth | Target |
|-------|------|--------|
| `DELETE /api/v1/users/me` | `require_user` — **any role** | Always the caller |
| `DELETE /api/v1/users/{user_id}` | `require_admin` | **Never** the caller — self-targeting is refused |

Splitting on the resource rather than branching inside one handler follows the precedent already
set by `GET /api/v1/users/me`, and keeps each route's authorization rule a single unconditional
statement. A user in another org is **404, never 403**, per the org-scoping convention
[`AUTH.md`](../roadmap/AUTH.md) already establishes for business reads.

Self-service removal is available to **every** role, not just admins. A viewer has no access to the
Users screen, so Settings is their only route out of the org, and an account nobody can leave is
not an acceptable default for a product holding this data.

### 3. The last-admin invariant

**An org always has at least one admin.** An org with zero admins can invite nobody, promote
nobody and manage nothing; recovery requires running `bootstrap_org` by hand against the database.

The invariant is enforced by two rules, not by counting at every write point:

1. **`DELETE /users/{user_id}` and the role-change route both refuse to target the caller.** The
   caller is necessarily an admin and necessarily survives their own request, so neither route can
   reduce the admin count to zero. No query is needed.
2. **`DELETE /users/me` refuses when the caller is the org's only admin** — the one route that can
   remove the caller, and therefore the only place the count is load-bearing. It responds
   **`409 last_admin`**.

`409` follows the precedent already in the codebase for state conflicts (`invite_already_pending`,
`device_busy`) and RFC 9110's Conflict semantics. The caller is not forbidden — they hold every
permission required; it is the org's state that refuses. A `403` would misdescribe it.

### 4. Self-demotion is refused outright

An admin may delete themselves but may **not** change their own role. The asymmetry is deliberate:
leaving an organization is a legitimate intent, whereas downgrading yourself is not — you would
immediately lose the screen you are standing on, and an admin who genuinely wants viewer access can
be demoted by a colleague. Refusing it removes a class of self-inflicted state that is confusing to
explain and annoying to recover from, and it is what makes rule 1 above hold for role changes.

### 5. Removal is confirmed by typing the email address

Both removal surfaces — Settings (self) and Users (someone else) — require the operator to type the
**target's email address** before the action proceeds. Deletion is irreversible and cascades a live
session; a single click is not proportionate to it.

This is a shared component, not a per-screen control: two call sites is exactly the bar
[`ui/status.md`](../ui/status.md) sets for a component earning its place.

### 6. What the removed user experiences

Nothing is emailed. The removed session dies with its `refresh_tokens` rows, and the SPA drops its
in-memory access token and redirects to `/login` with a confirmation line.

**The refresh cookie is deliberately not cleared by the delete routes.** It is scoped to
`/api/v1/auth`, and the SPA's business Axios instance sends no credentials at all — an invariant
asserted by an existing test. The cascade already invalidates the token server-side, so the
residual cookie is inert and its next refresh is a `401`. Widening credentialed requests to clear a
cookie that no longer authenticates anything would trade a real security boundary for cosmetics.

## Consequences

- [`AUTH.md`](../roadmap/AUTH.md)'s Phase 1 role matrix gains a **remove a member** capability, and
  its Phase 2 **Audit** row no longer wholly owns "who logged in" — member activity ships in
  September (recorded in `AUTH.md`, not here).
- DMI-76 and DMI-90 both lose their "No user deletion/deactivation" exclusion. DMI-76 additionally
  gains self-rejection on its role-change route, without which rule 1 does not hold.
- **`Settings` is reopened.** It shipped in spec 028 with change-password only; self-service removal
  adds a second section to a built screen.
- **A future `requested_by` on commands must be nullable and `ON DELETE SET NULL`**, rendering as
  "deleted user". [`AUTH.md`](../roadmap/AUTH.md) already anticipates that column for Phase 2 audit;
  a hard delete makes its nullability mandatory rather than optional.
- Removal is **not** recoverable and leaves no audit trace of itself. Should Phase 2 audit require
  proof of who removed whom, that trail must be written to a separate audit table — it cannot be
  reconstructed from the `users` table afterwards.
- The org-scoping rule (foreign row → 404) now covers a destructive verb, not only reads.

## References

- [`AUTH.md`](../roadmap/AUTH.md) — Phase 1 role matrix and sessions; amended by this ADR
- [`SECURITY.md`](../roadmap/SECURITY.md) — cross-cutting posture; `AUTH.md` is the identity authority
- [`ui/SCREENS.md`](../ui/SCREENS.md) — Users, Settings and Login screen specs
- [`ADR-005`](ADR-005-security-model.md) — v1 security baseline
- RFC 9110 §15.5.10 (409 Conflict) — https://www.rfc-editor.org/rfc/rfc9110#name-409-conflict
- [`docs/research/user-last-seen-tracking.md`](../research/user-last-seen-tracking.md) — activity
  tracking research; GDPR/ICO findings that accompany surfacing member activity to an admin
