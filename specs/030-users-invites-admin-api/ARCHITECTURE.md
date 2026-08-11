# ARCHITECTURE — Users and invites admin API (DMI-76, contract ask C4, backend only)

Implements [`TRUTH.md`](TRUTH.md). Decisions of record:
[`ADR-017`](../../docs/adr/ADR-017-account-removal.md) (last-admin invariant, self-demotion,
DMI-105 hardening), [`AUTH.md § Member activity`](../../docs/roadmap/AUTH.md),
[`ui/SCREENS.md § USERS & INVITES`](../../docs/ui/SCREENS.md),
[`docs/research/user-last-seen-tracking.md`](../../docs/research/user-last-seen-tracking.md)
(HOT/indexing constraints). Nothing here re-decides those documents; where they are silent the
choice is named as a decision below, and genuine gaps are flagged in
[§ Specification gaps](#specification-gaps).

**Scope:** `backend/`, plus **one** file under `frontend/` — the activity disclosure on Settings
(§ 11), added by operator decision on 2026-08-10 because the privacy duty it satisfies attaches the
moment the backend starts recording. Hence a small **`DESIGN.md`** covering that one control. No
`hardware-agent/`. No `INTEGRATION.md`: the only cross-layer artefact is
`contracts/openapi/openapi.yaml`, which this issue updates itself, and the disclosure consumes no
API. The admin screen that consumes these routes is DMI-90.

**CLAUDE.md `ScanRunner` rule — not applicable.** This feature touches no part of the scan
pipeline. `ScanRunner` (`hardware-agent/src/agent/scanner/runner.py`), `ScanProgressScreen`
(`hardware-agent/src/agent/tui/screens/scan_progress.py`) and `ScanOrchestrator` are not read,
called or parameterised by anything in this spec, and no constructor of a class changed here
lives outside `backend/src/api/`. The call-site sweep that the rule demands is instead applied to
the two functions this feature *does* change signatures/behaviour around — `issue_session()` and
`refresh_session()` — in [§ 6](#6-activity-stamping-issue_session--refresh_session).

**No `HUMAN_INFRA_REQUIRED`.** No new hardware, daemon, external service or dependency. The only
environmental prerequisite is the existing local Postgres (`./database.sh`).

---

## System context

Four new routes on the existing FastAPI surface, all inside the auth/identity slice. The pipeline
is the browser request path, not the scan path:

```
SPA  →  Bearer access token
        →  api/main.py  (RequestIdMiddleware, CORSMiddleware, error-envelope handlers)
          →  api/routers/users.py     GET  /api/v1/users
          |                            PATCH /api/v1/users/{user_id}
          →  api/routers/invites.py   GET  /api/v1/invites
                                       DELETE /api/v1/invites/{invite_id}
            →  api/dependencies/auth.py   require_admin  (all four)
              →  api/services/users.py    list_org_members, change_member_role
              |  api/services/invites.py  list_pending_invites, revoke_invite
              |    → api/services/org_lock.py  lock_org_admins()   ← the serialization point
                →  Postgres: users / invites, org-scoped in SQL
```

A second, orthogonal path is touched — the auth service, where the activity facts are recorded:

```
POST /api/v1/auth/login            →  services/auth.py  login()          →  issue_session()
POST /api/v1/invites/accept        →  services/invites.py accept_invite() →  issue_session()
POST /api/v1/auth/reset-password   →  (no session issued; unchanged)
POST /api/v1/auth/refresh          →  services/auth.py  refresh_session()
                                        issue_session()   → stamps last_login_at + last_seen_at
                                        refresh_session() → stamps last_seen_at only
```

Existing pieces reused unchanged:

| Piece | Where | Role here |
|---|---|---|
| `require_admin` | `backend/src/api/dependencies/auth.py:53` | The single unconditional gate on all four routes. Returns `CallerIdentity` (`sub`, `org_id`, `role`) from the JWT claims |
| `CallerIdentity.org_id` | `backend/src/api/dependencies/auth.py:18` | The org scope for every query. Never taken from the request |
| `ApiError(..., code=)` + global handler | `backend/src/api/errors.py:21`, `backend/src/api/main.py:62` | Shapes every refusal into the pinned `ErrorResponse` envelope |
| `count_org_admins` / `LastAdminError` | `backend/src/api/services/users.py:11,15` | Reused verbatim by the role change; **not** rewritten |
| Org-scoping → 404 | `get_host_detail` pattern: `backend/src/api/services/read.py:74` + `backend/src/api/routers/hosts.py:31`; already applied to a destructive verb by `delete_member` (`services/users.py:30`) | Foreign-org member/invite is `404`, never `403` |
| `pg_advisory_xact_lock` idiom | `backend/src/api/services/invites.py:36,47` (`INVITE_LOCK_NAMESPACE`) | The precedent the concurrency mechanism in § 7 follows |
| `utc_now`, `UTC_TIMESTAMP` | `backend/src/api/models/persistence.py:26` | `DateTime(timezone=True)` — the type both new columns take |

`GET /api/v1/users/me` (`routers/users.py:18`) and the delete routes from DMI-102 are unchanged.

---

## Data model / contracts

### 1. Migration — two activity columns, one grant

New revision `20260810_16_user_activity_and_invite_revoke.py`, `revision = "20260810_16"`,
`down_revision = "20260808_15"` (verified current head:
`backend/alembic/versions/20260808_15_user_delete_cascade.py:5-6`).

| Change | Detail |
|---|---|
| `users.last_login_at` | `sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)` |
| `users.last_seen_at` | `sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)` |
| `GRANT DELETE ON TABLE public.invites TO dmitri_runtime` | Required by the revoke decision in § 4. `users` already has `DELETE` from `20260808_15` |
| `downgrade()` | `REVOKE DELETE ... FROM dmitri_runtime`, then `op.drop_column` both columns |

Both columns are **`timestamptz`**, not naive `timestamp`: `20260724_08_timestamptz.py` converted
the schema and `20260731_13_command_delivery.py:18-25` records what a missed conversion costs when
the column is later compared against an aware value. `UTC_TIMESTAMP` on the model is
`DateTime(timezone=True)` (`models/persistence.py:26`), so this is also what avoids autogenerate
drift.

**Neither column is indexed, and no index may be added later without reopening this decision.**
PostgreSQL's heap-only-tuple path applies only when the update touches no indexed column; indexing
a column rewritten every ~15 minutes converts each stamp into a heap write plus an index write plus
index bloat, and at org scale the planner seq-scans regardless
([research § TL;DR, § 5.1](../../docs/research/user-last-seen-tracking.md)). No `fillfactor` change,
no `user_activity` table, no Redis.

**No backfill.** Existing rows get `NULL` for both columns. Backfilling `last_seen_at` from
`created_at` would fabricate an activity fact, which TRUTH explicitly forbids ("reports no
last-seen value rather than a fabricated one"). Every member who accepts an invitation *after* this
ships is stamped by `issue_session()` at acceptance, which is what makes TRUTH's "never-seen
member" row true going forward.

### 2. Model — `backend/src/api/models/identity.py`

```
class User(SQLModel, table=True):
    ...
    last_login_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
    last_seen_at: datetime | None = Field(default=None, sa_type=UTC_TIMESTAMP)
```

Placed after `password_changed_at`, before `created_at`, matching the existing field order style.
No `index=True` on either (§ 1). `Invite` is **unchanged** — see § 4.

### 3. `GET /api/v1/users` and `GET /api/v1/invites` — two resources, never one

`routers/users.py` → `list_org_users_route`; `routers/invites.py` → `list_invites_route`. Both
`require_admin`, both org-scoped in SQL by `caller.org_id`.

**Members and invites are not merged server-side** (TRUTH business rule; `ui/SCREENS.md:1317-1319`
— "two separate calls, merged here into one table — they have different lifecycles and different
row actions"). There is no union endpoint and no `?include=invites` parameter.

New schemas in `backend/src/api/schemas/users.py`:

```
class OrgMember(BaseModel):          # model_config = ConfigDict(extra="forbid")
    user_id: UUID
    email: str
    role: Literal["admin", "viewer"]
    last_seen_at: datetime | None

class OrgMemberListResponse(BaseModel):
    data: list[OrgMember]
```

and in `backend/src/api/schemas/invites.py`:

```
class PendingInvite(BaseModel):
    invite_id: UUID
    email: str
    role: Literal["admin", "viewer"]
    expires_at: datetime

class PendingInviteListResponse(BaseModel):
    data: list[PendingInvite]
```

**Decision — there is no `status` field (operator, 2026-08-10).** `users` has no state column, and
rows are created in exactly one place (`accept_invite`, `services/invites.py:112`), so every member
row is an accepted, active member. A `status` field could therefore only ever carry the constant
`"active"`, and a constant in a published contract is a promise that the value varies. It does not,
and ADR-017 § 1 decided it never will: "no `deactivated_at`, no soft-delete tombstone, and no
'disabled' account state anywhere in the product." Publishing the field is the affordance that
invites a later contributor to add `"suspended"` without reopening that ADR.

`ui/SCREENS.md`'s merged table keeps its Status column; DMI-90 fills it client-side, which it must
do for invite rows anyway ("Invited — expires in N days" is synthesised from `expires_at`, not
served). A member row reads "Active" because it came from `GET /users` — that is what the resource
means. Should a real member state ever land, it arrives as a new field plus a migration, which is
the honest cost of a decision that has not been made.

**Decision — `last_login_at` is not in `OrgMember`, in any form.** `extra="forbid"` plus the
fidelity fingerprint make its absence assertable, and TRUTH has a dedicated acceptance row for it.
The column is written now because login history cannot be reconstructed later
([`AUTH.md:128`](../../docs/roadmap/AUTH.md)); it has **no reader in this feature**, deliberately.

**Decision — no pagination.** `data` only; no `total`, no `page`, no `page`/`per_page` query
params, unlike `HostListResponse` (`services/read.py:47`). The realistic scale is a handful of
users per org, TRUTH asks for none, and unrequested query parameters are product behaviour this
spec is not entitled to invent. If it is ever needed the envelope is already shaped to gain
`total`/`page` additively.

**Ordering.**

| Route | `ORDER BY` | Why |
|---|---|---|
| `GET /users` | `nulls_last(User.last_seen_at.desc()), User.id.asc()` | Mandated by TRUTH and `AUTH.md:135`. Postgres orders `DESC` as NULLS FIRST by default, so `nulls_last(...)` is **required**, not decorative — a bare `.desc()` puts never-seen members at the top. The `id` tiebreak is unique and PK-backed, mirroring `list_hosts` (`services/read.py:61`) |
| `GET /invites` | `Invite.expires_at.asc(), Invite.id.asc()` | Soonest-to-expire first is the only time fact the pending row displays. All pending invites share one TTL, so this is also creation order |

*Observed, not fixed:* `list_hosts` (`services/read.py:61`) has the same latent NULLS-FIRST gap on
`HostRecord.last_seen_at`, but that column is `NOT NULL`, so it cannot bite. Do not touch it.

**`GET /invites` never returns `token_hash` or a token.** The raw token is shown once at creation
(`ui/SCREENS.md`), and `20260808_15`'s sibling decisions keep it out of every read. `invite_id` *is*
returned — it is the handle the revoke route needs, and disclosing it to an admin of the invite's
own org is not a secret (contrast `POST /invites/lookup`, which returns no id because it is
unauthenticated).

### 4. `DELETE /api/v1/invites/{invite_id}` — revoke is a hard delete

`routers/invites.py` → `revoke_invite_route`, `require_admin`, `status_code=204`, empty body.
Service: `revoke_invite(session, *, invite_id, org_id) -> bool` in `services/invites.py`, returning
`False` on miss exactly like `delete_member` (`services/users.py:30`); the router raises the `404`.

**Decision — delete the row; do not add `revoked_at`.** Both make the token immediately unusable.
The deciding arguments:

1. **A `revoked_at` column has to be honoured in three separate predicates or the acceptance
   criterion silently fails.** `accept_invite` (`services/invites.py:101`), `read_invite` (`:140`)
   and `create_invite`'s pending check (`:67-74`) each test `consumed_at IS NULL AND expires_at >
   now`. Every one would need `AND revoked_at IS NULL`, and forgetting it in `accept_invite` means
   *a revoked token still works* — the single behaviour TRUTH names. Deleting the row makes the
   invariant structural: no row, no acceptance, in all three predicates, with zero predicate edits.
2. **A retained revoked row breaks re-invitation.** `create_invite`'s pending check would match it
   and answer `409 invite_already_pending`, so an admin who revokes a mistyped invitation could not
   re-send to that address. That is the same class of self-inflicted block that ADR-017 § 1 used to
   reject soft-deleting users.
3. **Product precedent.** ADR-017 § 1: "There is no `deactivated_at`, no soft-delete tombstone, and
   no 'disabled' account state anywhere in the product," and ADR-017's Consequences already rule
   that an audit trail cannot live on a mutable business row — it needs its own table. A
   `revoked_at` nobody reads is history we have no surface for.
4. Nothing references `invites.id`; there is no FK to orphan.

Cost of the decision: the runtime role needs `GRANT DELETE ON public.invites` (§ 1) and
`RUNTIME_GRANTS_BY_TABLE` in `tests/test_migrations.py:38` gains
`"invites": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})`.

**"Pending" is defined by the lookup itself.** The org-scoped query is
`Invite.id == invite_id AND Invite.org_id == org_id AND Invite.consumed_at.is_(None) AND
Invite.expires_at > utc_now()`. An accepted, expired, foreign-org or unknown invitation therefore
all miss and all answer `404 not_found` — identical status, code and body, per TRUTH ("an
already-accepted or expired invitation is not a pending invitation") and the org-scoping
convention. The same predicate is the `WHERE` of `list_pending_invites`, so the two routes cannot
disagree about what pending means; factor it as one private helper in `services/invites.py` rather
than writing it twice.

**Nothing is emailed on revoke.** TRUTH is silent; ADR-017 § 6 sets the product's default (removal
sends no mail) and TRUTH's out-of-scope list rules out re-sending. Flagged in
[§ Specification gaps](#specification-gaps).

**Accepted consequence — a revoked invitation leaves no trace (operator, 2026-08-10).** After the
delete, nothing records that the invitation existed: not the address, not the role offered, not
that it was withdrawn. Revoke is therefore the only invite outcome that keeps nothing — an accepted
invite retains its row with `consumed_at` set, and an expired one retains its row until someone
removes it. "Who was invited into this org, and when" is a question a security product is
eventually asked, and this decision answers it with silence for revoked invitations.

That is accepted, not overlooked. The fix is not `revoked_at` — ADR-017's Consequences already rule
that an audit trail cannot live on a mutable business row, because the row is deleted, rewritten or
consumed by the very operations the trail is meant to record. The fix is the audit table TRUTH puts
out of scope. Whoever builds it should know two things: invitation revocation is one of the events
it must capture, and **there is no back-history** — every revocation between this feature shipping
and that table existing is unrecoverable.

### 5. `PATCH /api/v1/users/{user_id}` — role change

`routers/users.py` → `update_user_role_route`, `require_admin`.

**Decision — route shape.** `PATCH` on the **existing** `/api/v1/users/{user_id}` path, body
`{"role": "admin" | "viewer"}`, response `200` with the `OrgMember` object from § 3.

| Alternative | Why not |
|---|---|
| `PUT /api/v1/users/{user_id}/role` | Invents a sub-resource that has no independent identity and no `GET`. The contract would publish a path only ever written to |
| `POST /api/v1/users/{user_id}/role` | An RPC verb in a resource-shaped API; the repo's `POST`s all create things |
| `PATCH /api/v1/users/{user_id}` (chosen) | `users` is a resource with several fields of which one is being changed — the literal definition of `PATCH`. The path already exists in the contract (`DELETE`, line ~950), so this adds an operation, not a path |

`204` was considered for the response and rejected: returning the updated `OrgMember` reuses a
component the contract already gains for the list, lets the SPA patch its row in place without a
refetch, and makes the route self-verifying for TRUTH's "role change takes effect" row.

Request schema in `backend/src/api/schemas/users.py`:

```
class UpdateUserRoleRequest(BaseModel):   # model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "viewer"]
```

`extra="forbid"` (matching every sibling schema) means an attempt to PATCH `email` or
`last_seen_at` is a `422 validation_error` from the existing global handler
(`main.py:87`) — the role is the only mutable field, enforced by the schema rather than by handler
code.

**Ordering inside the handler**, which is load-bearing:

1. `if user_id == caller.sub:` → `ApiError(409, ..., code="self_target")`. Compared **before** any
   query, so the self answer never depends on a lookup — the same ordering DMI-102 pinned for
   `delete_user_route` (`routers/users.py:46`).
2. `change_member_role(session, user_id=..., org_id=caller.org_id, role=body.role)`.
3. `None` returned → `ApiError(404, ..., code="not_found")` (unknown id **or** foreign org).
4. `LastAdminError` → `ApiError(409, ..., code="last_admin")`.

**Self-targeting uses the same shape as DMI-102's refusal** — `409`, `code="self_target"`, raised
as a literal `ApiError(...)` **inside the router function** (the fidelity gate AST-scans route
bodies, `test_contract_fidelity.py:359`). Only the message differs, because "Remove your account
from Settings instead." cannot describe a role change. Message: **`You cannot change your own
role.`** Rationale for `409` rather than `403`/`404` is ADR-017 § 4 + § 3 and DMI-102's precedent:
the caller holds every permission, and their own row is demonstrably visible to them on the same
screen, so `404` would deny something they can see.

**The `last_admin` branch is reachable and must not be dropped as dead code.** With self-targeting
refused, a sole admin cannot demote themselves — but `require_admin` reads the role from the JWT
claim, not the row (the known DMI-104 window), so a just-demoted admin's still-valid token can pass
the gate while the DB says otherwise, and the sole remaining admin is then someone else. Under
concurrency it is reachable without any stale token at all (§ 7). Message: **`Add another admin
before changing this role.`**

Service, `backend/src/api/services/users.py`:

```
def change_member_role(session, *, user_id: UUID, org_id: UUID, role: str) -> User | None:
    lock_org_admins(session, org_id=org_id)          # § 7 — first, before any read
    target = session.exec(select(User).where(User.id == user_id, User.org_id == org_id)).first()
    if target is None:
        return None
    if (
        target.role == ROLE_ADMIN
        and role != ROLE_ADMIN
        and count_org_admins(session, org_id=org_id) == 1
    ):
        raise LastAdminError("org would be left without an admin")
    target.role = role
    session.add(target)
    session.commit()
    return target
```

Setting the role to its current value is a no-op that still returns `200` with the unchanged member
— `PATCH` is idempotent and there is no reason to manufacture a refusal for it.

### 6. Activity stamping — `issue_session()` / `refresh_session()`

Both in `backend/src/api/services/auth.py`.

| Function | Stamps | Callers (the full sweep) |
|---|---|---|
| `issue_session` (`:38`) | `last_login_at` **and** `last_seen_at` | `login` (`services/auth.py:53`), `accept_invite` (`services/invites.py:132`) |
| `refresh_session` (`:56`) | `last_seen_at` **only** | `refresh_route` in `backend/src/api/routers/auth.py` |

There is no third caller of either function (grep `issue_session|refresh_session` across
`backend/src/`). `reset_password` (`services/auth.py:111`) issues no session and stamps nothing;
`logout` stamps nothing. This is what makes TRUTH's "renewing a session advances last-seen but
never last-login" hold, and it is why the stamp lives in the two service functions rather than in
the routers — invite acceptance is a real authentication event and reaches `issue_session` from a
different router entirely.

**The UPDATE must name only the stamped columns.** Implement one shared private helper in
`services/auth.py`:

```
def _stamp_activity(session: Session, *, user_id: UUID, login: bool) -> None:
    now = utc_now()
    values = {"last_seen_at": now}
    if login:
        values["last_login_at"] = now
    session.execute(update(User).where(User.id == user_id).values(**values))
```

A Core `update()` with an explicit `.values()` is mandated over `user.last_seen_at = now;
session.add(user)`. Plain attribute assignment happens to emit a narrow UPDATE today, but the
column list then depends on whatever else is dirty on that instance — a later contributor mutating
an unrelated field nearby silently widens the statement to include `email`, which touches
`ix_users_email` and defeats HOT
([research § TL;DR](../../docs/research/user-last-seen-tracking.md);
[`AUTH.md:137`](../../docs/roadmap/AUTH.md)). The Core form cannot widen by accident and is
assertable in a test.

**Transaction placement**, given that the token helpers commit:

- `issue_refresh_token` commits (`services/tokens.py:53`). In `issue_session`, call
  `_stamp_activity(..., login=True)` **before** `issue_refresh_token`, so the stamp rides that
  commit. No second round-trip, and a failure to issue the refresh token rolls the stamp back with
  it.
- `rotate_refresh_token` commits at its end (`services/tokens.py:100`). In `refresh_session`, call
  `_stamp_activity(..., login=False)` after the `session.get(User, user_id)` null check, followed by
  `session.commit()`. Stamping before rotation would record activity for a request that then fails
  reuse detection.
- The Core UPDATE leaves the in-memory `User` stale for these two columns. Nothing reads them in
  either function (both return only tokens), so no `session.refresh` / `expire` is needed. Do not
  add one.

**No middleware, no per-request stamping, no coalescing `WHERE`.** All three are explicitly out
(research § 2, § 1.5); the refresh interval already bounds accuracy to ~15 minutes, which is finer
than the screen displays.

**No conditional coalescing means `issue_session` and `refresh_session` write unconditionally.**
That is ~4 updates/user/hour, three orders of magnitude below where any mitigation earns its keep
(research § 1.4).

### 7. Concurrency — one org-scoped, transaction-scoped serialization mechanism

**The problem.** Self-target refusal plus a plain `count_org_admins` is not enough. Two admins A
and B, each demoting the other: both transactions read `count == 2` under READ COMMITTED, both pass
the check, both commit, and the org has **zero admins** — unrecoverable without running
`bootstrap_org` by hand (ADR-017 § 3). ADR-017 records exactly this as DMI-105's remit; this
feature must not ship the same hole on a second route.

**Decision: a Postgres transaction-scoped advisory lock keyed on the organisation id**, in a new
shared module so DMI-105 adopts it verbatim.

`backend/src/api/services/org_lock.py`:

```
ORG_ADMIN_LOCK_NAMESPACE = 8818

def lock_org_admins(session: Session, *, org_id: UUID) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:org_id))"),
        {"namespace": ORG_ADMIN_LOCK_NAMESPACE, "org_id": str(org_id)},
    )
```

Rules that make it work, all of which are the implementer's responsibility:

- **Taken first, unconditionally,** at the top of every admin-reducing write, *before* the target
  lookup and *before* `count_org_admins`. A count read before the lock is a count from the losing
  snapshot.
- **One transaction per operation.** The lock is released by `COMMIT`/`ROLLBACK`, so the service
  must not commit between taking the lock and writing. `change_member_role` above satisfies this;
  the request's session has done nothing but reads before it.
- **Depends on READ COMMITTED**, which is the engine default and what `get_session` uses: after the
  loser's lock wait returns, its next statement takes a fresh snapshot and sees the winner's
  committed change, so its `count_org_admins` reads `1` and it raises `LastAdminError`. Under
  REPEATABLE READ the count would come from the pre-lock snapshot and the lock would be useless. Do
  not change the isolation level anywhere.
- **Taken on promotions too.** Cheap, and it removes any "did this branch take it?" reasoning.

Result for TRUTH's row: A demotes B and B demotes A concurrently → the winner commits (admins 2→1),
the loser wakes, re-counts `1`, and answers `409 last_admin`. **Exactly one admin remains, never
zero.**

**Why an advisory lock and not the alternatives:**

| Alternative | Assessment |
|---|---|
| `SELECT 1 FROM orgs WHERE id = :org_id FOR UPDATE` | Works today, and needs no new module. Rejected because it couples the invariant to an unrelated row: the lock's meaning is invisible at the lock site, and any future write to `orgs` (rename, settings) would take the same lock and create false contention, or worse, be written *without* it and look correct. It also requires the runtime role to hold `UPDATE` on `orgs` for `FOR UPDATE` — true today by accident of the default grant set, not by design |
| `SELECT ... FOR UPDATE` on the `users` rows | Cannot work: the rows to be protected include ones that must not exist yet or are about to be deleted, and two transactions locking two different member rows do not conflict at all |
| `SERIALIZABLE` isolation + retry | Correct but repo-wide in blast radius, and adds a retry loop to every route for one invariant on two |
| Unique partial index / check constraint ("at least one admin") | Postgres cannot express a cross-row cardinality floor declaratively |
| **`pg_advisory_xact_lock` (chosen)** | Already the repo's idiom for exactly this shape — `create_invite` serialises per `(org, email)` with `pg_advisory_xact_lock(INVITE_LOCK_NAMESPACE, hashtext(...))` (`services/invites.py:36,47`). Needs no privilege, no migration, no row, and its key *is* the invariant's scope. `hashtext` collisions across orgs cost only extra serialisation, never correctness |

`ORG_ADMIN_LOCK_NAMESPACE = 8818` must differ from `INVITE_LOCK_NAMESPACE = 8817` so the two lock
spaces cannot collide.

**Why its own module rather than `services/users.py`:** DMI-105 will call it from `delete_self` and
`delete_member` (`services/users.py:23,30`), and a later admin-reducing write may live elsewhere;
a leaf module with no imports from `services/` keeps it cycle-free and makes "who takes this lock"
greppable. `services/invites.py` does **not** call it — revoking an invitation cannot reduce the
admin count.

**DMI-105 closes the mixed race by adoption, not by redesign.** Today `delete_self` /
`delete_member` take no lock, so an admin *removing* another admin concurrently with a *demotion*
is still unserialized: the demotion holds the lock the removal never asks for. Adding
`lock_org_admins(session, org_id=...)` as the first statement of both removal services — no other
change — puts all four writes behind one lock and closes it. This feature ships the mechanism and
its shared home; DMI-105 ships the two call sites. **Do not partially adopt it in the removal
routes here** — a half-adopted lock is the "two partial, incompatible locks" TRUTH names.

Adopting it in the removal services *now* was considered and rejected by the operator
(2026-08-10): the two calls are trivial, but the concurrency tests that prove them are not, and
DMI-105 owns those. A lock taken on a path nobody has raced under test is the false confidence
ADR-017 § 3 warns about. The boundary is recorded as a comment in `test_org_lock.py` and nothing
else — see [§ Testing area 4](#area-4--concurrency-backendteststest_org_lockpy).

### 8. Routes, status codes and error codes — the complete refusal table

| Route | Auth | Success | Refusals |
|---|---|---|---|
| `GET /api/v1/users` | `require_admin` | `200` `OrgMemberListResponse` | `401 unauthorized` (missing/invalid token, from `require_user`), `403 forbidden` (viewer) |
| `GET /api/v1/invites` | `require_admin` | `200` `PendingInviteListResponse` | `401 unauthorized`, `403 forbidden` |
| `PATCH /api/v1/users/{user_id}` | `require_admin` | `200` `OrgMember` | `401 unauthorized`, `403 forbidden`, `404 not_found` (unknown id **or** foreign org), `409 self_target`, `409 last_admin`, `422 validation_error` (global handler; unpublished, see § 9) |
| `DELETE /api/v1/invites/{invite_id}` | `require_admin` | `204`, empty body | `401 unauthorized`, `403 forbidden`, `404 not_found` (unknown, foreign org, consumed, or expired) |

New pinned error codes: **none for the invite routes** (`not_found` and `forbidden` come from
`DEFAULT_CODES_BY_STATUS`, `errors.py:7`). `PATCH` reuses the two codes DMI-102 already pinned,
`self_target` and `last_admin`, with route-appropriate messages.

**Route declaration order (trap).** In `routers/users.py`, `GET /api/v1/users` and the existing
`/api/v1/users/me` operations must stay **above** `PATCH /api/v1/users/{user_id}`; FastAPI matches
in registration order, and a parameterised path declared first swallows `/me` into a uuid path
param and answers `422`. The file already orders `/me` first — keep it that way.

**`routers/invites.py` OPTIONS-twin loop (trap).** The module-level loop at `:94-98` adds an
`OPTIONS` twin for every route whose methods include `POST`. The new `GET` and `DELETE` routes must
be declared **above** that loop (with the other operations) and correctly receive **no** twin —
`CORSMiddleware` answers their preflight, matching how `/api/v1/users/*` already works. Do not add
`OPTIONS` operations for them in the contract either.

### 9. Contract — `contracts/openapi/openapi.yaml`

| Addition | Detail |
|---|---|
| New path `/api/v1/users` | `get`, `operationId: listOrgUsers`, `tags: [users]`, `security: [FrontendBearerAuth: []]`, responses `200` (schema `OrgMemberListResponse`, plus the four standard headers the sibling `getCurrentUser` carries: `X-Request-Id`, `Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials`, `Vary`), `401 → Unauthorized`, `403 → Forbidden` |
| `patch` on existing `/api/v1/users/{user_id}` | `operationId: updateUserRole`, request body `UpdateUserRoleRequest` (required), responses `200` (`OrgMember`), `401 → Unauthorized`, `403 → Forbidden`, `404 → NotFound`, `409 → #/components/responses/RoleChangeConflict` |
| New path `/api/v1/invites/{invite_id}` | `delete`, `operationId: revokeInvite`, `invite_id` path param (`type: string, format: uuid`), responses `204` (no `content`), `401`, `403`, `404 → NotFound` with a description stating that accepted, expired, foreign-org and unknown invitations are reported identically |
| `get` on existing `/api/v1/invites` | `operationId: listPendingInvites`, responses `200` (`PendingInviteListResponse`), `401`, `403`. Sits alongside the existing `post` and `options` on that path |
| New schemas | `OrgMember`, `OrgMemberListResponse`, `PendingInvite`, `PendingInviteListResponse`, `UpdateUserRoleRequest` — each with `additionalProperties: false` to match `extra="forbid"`, `required` listing every field (Pydantic makes all of these required), `last_seen_at` as `type: [string, "null"], format: date-time`. `OrgMember` has no `status` property |
| New `components/responses/RoleChangeConflict` | Modelled on `AcceptInviteRejected` (line 1482): `allOf: [ErrorResponse, {error.code enum: [last_admin, self_target]}]`. **One component with a two-value enum, not two components** — see the fidelity note below |
| `Access-Control-Allow-Methods` header example | `GET, POST, DELETE, OPTIONS` → **`GET, POST, PATCH, DELETE, OPTIONS`** |

**What `backend/tests/test_contract_fidelity.py` enforces, and what must stay in sync:**

1. `test_schema_matches_contract` fingerprints each name in `SCHEMA_NAMES` (`:27`) against the live
   FastAPI schema: `additionalProperties`, the sorted `required` list, and every property's
   type/format/enum/nullability. **Add the five new schema names to `SCHEMA_NAMES`.** A
   contract-only field, a missed `additionalProperties: false`, or a nullability mismatch on
   `last_seen_at` fails here.
2. `test_error_code_fidelity` AST-parses the named router **function body** for literal
   `ApiError(status, ..., code="...")` calls and asserts that the set of codes raised at that status
   equals the contract component's `error.code` enum. **This is why `RoleChangeConflict` is one
   component with `[last_admin, self_target]`:** `update_user_role_route` raises both at `409`, so
   any component referenced from that `409` must enumerate both — exactly the `AcceptInviteRejected`
   precedent (two codes at `400`). Add
   `"RoleChangeConflict": ("users.py", "update_user_role_route", 409)` to `ERROR_RESPONSE_ROUTES`
   (`:15`). Both `ApiError`s must be raised **in the router**, not the service, or the AST scan sees
   nothing.
3. `test_cors_allowed_methods_example_includes_delete` (`:338`) asserts the header example is
   **exactly** `"GET, POST, DELETE, OPTIONS"`. Adding `PATCH` breaks it — update the assertion (and
   consider renaming it, since it now covers `PATCH` too).
4. `test_delete_user_operations_are_published` (`:308`) asserts the *exact* set of response codes
   per operation. Add an equivalent parametrised case for the two new operations that publish
   business refusals; keep the existing DELETE cases untouched.
5. `test_response_status_codes_not_compared_open_item_1` documents that response-code sets are
   deliberately *not* compared globally — so **do not publish `422`** on the `PATCH`. `POST
   /api/v1/invites` publishes `400/401/403/409` and no `422`; follow it.

### 10. CORS — `PATCH` is not currently allowed

`backend/src/api/middleware.py:54` sets `allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]`. A
browser preflight for `PATCH /api/v1/users/{user_id}` is rejected before the route is reached, so
DMI-90 would fail in the browser while every backend test passed. Add `"PATCH"`. No security
widening: the route's own `require_admin` gate is unchanged. The invite `GET`/`DELETE` need nothing.

### 11. Activity disclosure — the one frontend change (operator, 2026-08-10)

`frontend/src/pages/Settings.tsx`, route `/settings`, **both roles** (`ui/SCREENS.md:1465`). The
audience is every monitored member, and a viewer never reaches the Users screen — so the admin-only
surface (DMI-90) is the wrong home, and DMI-87, which built Settings, is closed. It ships here,
with the recording it discloses.

**Layered, per the ICO's endorsement of layered notices.** Top layer visible on the page, lower
layer behind a control:

| Layer | Content |
|---|---|
| Visible | An `Activity` label with a text control beside it reading `What's recorded?` |
| Revealed | *Your organization's admins can see when you last used Dmitri and when you last signed in. We record only these times — not what you viewed or did.* |

**`DESIGN.md` is the authority for the exact on-screen strings; copy them from there, not from here.**
Note the spelling: on-screen copy is American (`organization`), matching every other user-facing
string in the product — `ui/SCREENS.md:1361, 1403, 1472, 1525`, including "Leave this organization",
which lands about 100px away on this same screen. The contract and these specs stay British
(`organisation`, `openapi.yaml` ×4). The split is by register: screen copy matches screen copy. Do
not normalise one into the other.

**The control is text, not an icon** (operator, 2026-08-10): the repo has no icon set and Settings
renders no icons, so a visible `What's recorded?` needs no glyph and is its own accessible name. It
is a click/keyboard disclosure, **not a tooltip** — hover content is unreachable on touch, risks
WCAG 1.4.13, and a legal notice that vanishes when the pointer moves is the wrong shape. The
revealed text is an inline paragraph, `max-w-prose`; it pushes content below it down, which is
accepted.

**The visible label is load-bearing, not decoration.** Settings displays no activity data, so an
unlabelled icon would sit next to nothing and disclose nothing; the top layer of a layered notice
must name its subject. The wording names `last_login_at`, which no screen shows — the duty follows
what is *recorded*, not what is displayed.

**Not a setting.** No toggle, no consent dialog, no privacy-policy page. The lawful basis is
legitimate interests, not consent; a switch would misdescribe it. The member's own last-seen and
last-login values are **not** displayed — this is disclosure, not a feature.

Placement, keyboard behaviour, focus, the reveal/hide interaction and the `data-testid` values are
`DESIGN.md`'s to fix. Layer conventions: the `frontend-conventions` skill, mandatory before the
edit. This is the **only** file under `frontend/` this feature touches.

---

## New files and naming (mandatory)

Every file an implementer creates or touches. Paths are exact, relative to the repo root.

| # | Kind | Path | Change |
|---|---|---|---|
| 1 | Model | `backend/src/api/models/identity.py` | `User` gains nullable `last_login_at`, `last_seen_at` (`sa_type=UTC_TIMESTAMP`, **no index**). `Invite` unchanged |
| 2 | Migration (**new**) | `backend/alembic/versions/20260810_16_user_activity_and_invite_revoke.py` | `revision = "20260810_16"`, `down_revision = "20260808_15"`. Adds both columns as `timestamptz` nullable; `GRANT DELETE ON TABLE public.invites TO dmitri_runtime`; `downgrade()` revokes and drops |
| 3 | Service (**new**) | `backend/src/api/services/org_lock.py` | `ORG_ADMIN_LOCK_NAMESPACE = 8818`; `lock_org_admins(session, *, org_id)`. Leaf module, imports nothing from `services/` |
| 4 | Service | `backend/src/api/services/users.py` | Adds `list_org_members(session, *, org_id) -> list[User]` and `change_member_role(session, *, user_id, org_id, role) -> User \| None`. Reuses `count_org_admins` / `LastAdminError` unchanged. **Does not** add the lock to `delete_self`/`delete_member` (DMI-105) |
| 5 | Service | `backend/src/api/services/invites.py` | Adds `list_pending_invites(session, *, org_id) -> list[Invite]` and `revoke_invite(session, *, invite_id, org_id) -> bool`, sharing one private pending-predicate helper. `create_invite` / `accept_invite` / `read_invite` unchanged |
| 6 | Service | `backend/src/api/services/auth.py` | Adds `_stamp_activity(session, *, user_id, login)` (Core `update()`, named columns only); `issue_session` calls it with `login=True` before `issue_refresh_token`; `refresh_session` calls it with `login=False` after the user null check, then commits |
| 7 | Schemas | `backend/src/api/schemas/users.py` | Adds `OrgMember`, `OrgMemberListResponse`, `UpdateUserRoleRequest`. No `status` field on `OrgMember` (§ 3). `UserProfileResponse` unchanged |
| 8 | Schemas | `backend/src/api/schemas/invites.py` | Adds `PendingInvite`, `PendingInviteListResponse` |
| 9 | Router | `backend/src/api/routers/users.py` | Adds `list_org_users_route` (`GET /api/v1/users`, `require_admin`) and `update_user_role_route` (`PATCH /api/v1/users/{user_id}`, `require_admin`, `200`). Raises `ApiError(409, ..., code="self_target")`, `ApiError(409, ..., code="last_admin")` and the `404` literally inside the handler. `/me` operations stay declared first |
| 10 | Router | `backend/src/api/routers/invites.py` | Adds `list_invites_route` (`GET /api/v1/invites`) and `revoke_invite_route` (`DELETE /api/v1/invites/{invite_id}`, `204`), both `require_admin`, both declared **above** the OPTIONS-twin loop at `:94` |
| 11 | Middleware | `backend/src/api/middleware.py` | `build_cors_middleware_kwargs`: `allow_methods` gains `"PATCH"` |
| 12 | Contract | `contracts/openapi/openapi.yaml` | Per § 9: `listOrgUsers`, `updateUserRole`, `listPendingInvites`, `revokeInvite`, five schemas, `RoleChangeConflict`, CORS methods example |
| 13 | Test (**new**) | `backend/tests/test_users_admin_routes.py` | Route tests for `GET /users` + `PATCH /users/{user_id}`. Postgres-backed, mirrors `backend/tests/test_user_delete_routes.py` / `test_invite_routes.py` |
| 14 | Test (**new**) | `backend/tests/test_invite_admin_routes.py` | Route tests for `GET /invites` + `DELETE /invites/{invite_id}`. Mirrors `test_invite_routes.py` |
| 15 | Test (**new**) | `backend/tests/test_org_lock.py` | Concurrency tests for `lock_org_admins` and the mutual-demotion race |
| 16 | Test (**new**) | `backend/tests/test_user_activity_migration.py` | Revision-chain + upgrade/downgrade + live column/index/grant assertions. Mirrors `test_user_delete_cascade_migration.py` and `test_identity_migration.py` |
| 17 | Test | `backend/tests/test_users_service.py` | Adds `list_org_members` + `change_member_role` cases |
| 18 | Test | `backend/tests/test_invite_service.py` | Adds `list_pending_invites` + `revoke_invite` cases |
| 19 | Test | `backend/tests/test_auth_service.py` | Adds the stamping cases (§ Testing, area 5) |
| 20 | Test | `backend/tests/test_users_schemas.py` | `OrgMember`, `OrgMemberListResponse`, `UpdateUserRoleRequest` shape/`extra="forbid"` cases |
| 21 | Test | `backend/tests/test_invite_schemas.py` | `PendingInvite`, `PendingInviteListResponse` cases |
| 22 | Test | `backend/tests/test_contract_fidelity.py` | `SCHEMA_NAMES` += the five new schemas; `ERROR_RESPONSE_ROUTES` += `RoleChangeConflict`; CORS example assertion updated to include `PATCH`; a published-operations case for the new routes |
| 23 | Test | `backend/tests/test_migrations.py` | `RUNTIME_GRANTS_BY_TABLE` gains `"invites": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})`, with a comment naming this revision |
| 24 | Test | `backend/tests/test_cors_headers.py` | `test_real_preflight_returns_204_with_cors_headers` asserts `"PATCH" in allow_methods` |
| 25 | Test | `backend/tests/test_auth_wiring.py` | Registration/dependency assertions for all four new routes, alongside `READ_ROUTES` (`:126`) and `DELETE_ROUTES` (`:146`) |
| 26 | Screen | `frontend/src/pages/Settings.tsx` | The activity disclosure (§ 11): visible `Activity` label + info control, revealed copy verbatim. Exact markup, ids and interaction per `DESIGN.md`. The only `frontend/` file this feature **authors** |
| 27 | Test | `frontend/src/pages/Settings.test.tsx` | Disclosure cases: label present for both roles, control reveals the exact copy, hides again, keyboard-reachable, revealed text associated with the control for assistive tech, and **no** toggle or member timestamp rendered |
| 28 | Generated | `frontend/src/types/openapi.d.ts` | `npm run gen:types` output for row 12. Never hand-edited, and regenerated even though no screen reads the new operations: the file tracks the contract, not the screens |

**Kept as one issue (operator, 2026-08-10).** 28 files is large, and splitting was considered. The
only clean seam is the invite half (`GET /invites` + revoke), which shares nothing with the users
half but `require_admin`; everything else is coupled by correctness, not convenience — the member
list serves `last_seen_at`, so the migration and stamping must land with it; the role route is
unsafe without the lock; and the disclosure's duty attaches the moment recording starts. Splitting
would buy two PRs waiting on one reviewer.

**Task ordering follows from that:** `create-tasks` should sequence the risky, subtly-wrong-able
work first — migration → stamping (§ 6) → lock + concurrency tests (§ 7, testing area 4) → the four
routes → contract → the disclosure (§ 11) — so the parts a reviewer must think hardest about are
read while attention is fresh, and the mechanical parts land last.

**Not touched, deliberately:** `backend/src/api/dependencies/auth.py` (no new gate — `require_admin`
is sufficient and DMI-104 owns making it row-backed); `backend/src/api/errors.py` (no new default
code); `backend/src/api/main.py` (both routers are already included at `:153` and `:157`);
`backend/src/api/services/read.py` and every read-path router; `delete_self` / `delete_member` in
`services/users.py` (**DMI-105** adds the lock call, not this issue);
`backend/src/api/routers/auth.py` (the stamp lives in the service); `backend/tests/test_users_routes.py`
(SQLite-backed, covers `GET /users/me` only); anything under `hardware-agent/` or `frontend/`.

---

## Constraints

- **HOT rules, both load-bearing.** (a) **Neither `last_login_at` nor `last_seen_at` may be
  indexed**, ever — not by `Field(index=True)`, not by a migration, not "to make the sort fast".
  (b) **The stamping UPDATE must name only the stamped columns**; a whole-object ORM write reaches
  `ix_users_email` and defeats HOT for the same reason. No Redis, no `user_activity` table, no
  `fillfactor` tuning, no per-request middleware, no coalescing `WHERE`.
- **No union endpoint.** Members and invitations are two resources with two routes. No merged list,
  no `?include=`, no synthesised "pending member" rows in `GET /users`.
- **Admin-only, on all four routes,** via the existing `require_admin` — one unconditional
  dependency per route, no role branching inside a handler (ADR-017 § 2).
- **Org scoping is done in SQL**, from `caller.org_id`, never from a request parameter. A foreign-org
  member or invitation is **`404`, never `403`** — indistinguishable from one that does not exist.
- **ADR-017 invariant: an organisation always has at least one admin.** Self-role-change is refused
  outright (ADR-017 § 4), and the last-admin check runs under the § 7 lock. Not "usually" — under
  concurrency too.
- **One serialization mechanism, shared.** `lock_org_admins` is the only lock this feature adds. Do
  not add a second lock, do not change the isolation level, do not add retry loops, and do not
  partially adopt the lock in the removal routes (DMI-105's job).
- **`last_login_at` is written and never read.** No route, schema or log may expose it in this
  feature.
- **No `ruff format`, ever.** Per `.claude/CLAUDE.md`, `backend/` has never been formatted;
  `uv run ruff check src tests` is the backend's only Python gate. Match neighbouring style by hand.
- **`./database.sh --test` before the suite.** Without a live `dmitri_test`, `conftest.py` *skips*
  every DB-backed test — which here is the migration, the grant, the ordering, the lock and the
  entire concurrency surface. A run with a non-zero skip count is not a green run.
- **Alembic owns `dmitri_test`.** Never point `supabase db reset|push|migration` at it.
- **Surgical diff.** No rate limiting, no audit record, no email on revoke, no new dependency, no
  refactor of `create_invite`/`accept_invite`.
- **Style:** no comments or docstrings in new code, including tests, except where an existing
  neighbour file uses a comment to record a non-obvious constraint (as `dependencies/auth.py:45`
  and `services/invites.py:121` do) — the lock's ordering requirement is such a case.

---

## Testing expectations

Every row of TRUTH's acceptance table maps to at least one test below. Mirror the named neighbour
for fixtures and style. Route tests are **Postgres-backed** (`administrative_session` + `seeded_org`,
`tests/conftest.py:158,183`) with the `client` fixture that overrides `get_session`
(`tests/test_invite_routes.py:33`); the advisory lock, `NULLS LAST` and the grants do not exist on
SQLite.

**`bearer_headers` (`conftest.py:192`) mints a token with `user_id=uuid4()`** — a subject with no
row. That is fine for the four routes here, since all of them gate on the claims-only
`require_admin`; but any test that needs the caller's own row (self-target, last-admin) must build
its token with `create_access_token(user_id=<seeded user id>, org_id=..., role=...)`, as
`test_invite_routes.py` does. Reuse the `_assert_error_envelope` helper shape from
`backend/tests/test_users_routes.py:19`.

### Area 1 — `GET /api/v1/users` (`backend/tests/test_users_admin_routes.py`)

| Test | Asserts |
|---|---|
| Admin lists members | `200`; every seeded member of the org present; each row's keys are exactly `user_id`, `email`, `role`, `last_seen_at` |
| No login history | `"last_login_at"` appears nowhere in the raw response text, even for a member whose column is populated |
| No status field | `"status"` appears on no row — asserted by the exact key-set check above, so a re-added field fails |
| Never-seen member | A member whose `last_seen_at` is `NULL` serialises as `null`, not `""`, not `created_at` |
| Ordering | Seed members with `last_seen_at` = recent / older / `NULL`; assert exact ordering — most recent first, `NULL`s **last**. A bare `.desc()` regression fails here |
| Stable tiebreak | Two members with identical `last_seen_at` come back in ascending `id` order across repeated calls |
| Org isolation | A second org's members are absent |
| Viewer forbidden | `403`, envelope `error.code == "forbidden"` |
| No bearer | `401 unauthorized`, envelope shape |

### Area 2 — `PATCH /api/v1/users/{user_id}` (same file)

| Test | Asserts |
|---|---|
| Promote takes effect | `200`; body is the updated `OrgMember` with `role == "admin"`; the row's role changed; a subsequent `GET /users/me` **as the promoted member** reports `admin` (TRUTH's wording) |
| Demote takes effect | `200`; role is `viewer` |
| Same-role PATCH | `200`, unchanged row — no manufactured refusal |
| Self-target | Caller PATCHes their own id → `409`, `error.code == "self_target"`, message `You cannot change your own role.`, role unchanged. **Explicitly assert it is not `404` and not `403`** |
| Last admin protected — envelope | **Override `require_admin` via `app.dependency_overrides` to return a `CallerIdentity` for a non-target admin of the seeded org**, then PATCH the org's sole admin to `viewer` → `409`, `error.code == "last_admin"`, message `Add another admin before changing this role.`, role unchanged, `count_org_admins` still `1`. Operator decision, 2026-08-10 — see the note below on why the override, and not a minted token |
| Foreign-org target | `404 not_found`; **assert it is not `403`**; the foreign row is untouched |
| Unknown uuid | `404 not_found` |
| Bad role value | `{"role": "owner"}` → `422`, `error.code == "validation_error"` |
| Extra field rejected | `{"role": "viewer", "email": "x@y.z"}` → `422` (proves `extra="forbid"`) |
| Viewer forbidden | `403`; target role unchanged |
| No bearer | `401` |
| Preflight | An `OPTIONS` preflight with `Access-Control-Request-Method: PATCH` is allowed (or assert `PATCH` in the allow-methods header — the DMI-90-blocking case) |

**Why the `last_admin` route test overrides the gate rather than minting an admin token for a
subject with no row (operator, 2026-08-10).** That setup only constructs because `require_admin`
reads the role from the JWT claim — the open DMI-104 window. When DMI-104 makes the gate
row-backed, a claims-only caller answers `401`/`403` before the handler runs, and such a test
becomes unbuildable and gets deleted. Worse, it encodes another issue's bug into this feature's
suite. The override asserts the same envelope and survives DMI-104 with a one-line edit to whatever
`require_admin` then returns.

**Note the consequence of a row-backed gate:** once DMI-104 lands, `409 last_admin` on `PATCH` is
reachable **only** under concurrency — the caller is an admin, the target is a *different* admin
(self-target is refused first), so demoting the target always leaves the caller standing, unless a
concurrent transaction removes or demotes the caller. Area 4 is what proves it then. This route
test proves the *mapping* — that the handler catches `LastAdminError` and shapes a `409` envelope —
which no other test does: area 4 calls the service directly, and `test_error_code_fidelity`
AST-parses the router source without executing it, so it cannot detect an unreachable branch, a
wrongly-named `except`, or an exception raised where the router cannot catch it. All three ship a
`500`.

### Area 3 — invite routes (`backend/tests/test_invite_admin_routes.py`, mirror `test_invite_routes.py`)

| Test | Asserts |
|---|---|
| List pending | `200`; a live unconsumed invite is listed with `invite_id`, `email`, `role`, `expires_at` |
| Consumed excluded | An invite with `consumed_at` set is absent |
| Expired excluded | An invite with `expires_at` in the past is absent |
| No token leakage | `token_hash` and any raw token appear nowhere in the response text |
| Ordering | Soonest `expires_at` first, `id` ascending as tiebreak |
| Org isolation — list | Another org's pending invite is absent |
| Viewer forbidden — list | `403` |
| **Revoke kills the token** | Revoke → `204`; then `POST /api/v1/invites/accept` with that raw token returns `410 invalid_invite_token`; and `POST /api/v1/invites/lookup` returns `410`. This is the acceptance criterion — assert against the real routes, not the service |
| Revoke removes the row | No `Invite` row with that id remains |
| **Re-invite after revoke** | `POST /api/v1/invites` for the same address now succeeds (`201`) — the regression the `revoked_at` alternative would have introduced |
| Revoke is pending-only — consumed | `404 not_found` |
| Revoke is pending-only — expired | `404 not_found` |
| Org isolation — revoke | Another org's pending invite → `404`; **assert it is not `403`** and the row survives |
| Unknown uuid | `404` |
| Viewer forbidden — revoke | `403`; the invite survives |
| No bearer, both routes | `401` |
| **Runtime grant** | Using the `runtime_session` fixture (`conftest.py:166`, `SET ROLE dmitri_runtime`): seed an invite as owner, revoke via the runtime role, assert the commit succeeds. `administrative_session` connects as the schema owner and can delete regardless of grants, so a missing `GRANT DELETE ON invites` would be invisible to every other test here and would `500` on the first real revoke in production |

### Area 4 — concurrency (`backend/tests/test_org_lock.py`)

This is the one area with a non-obvious test construction, and TRUTH's most important row.

- **Two connections, not one.** `administrative_session` and `runtime_session` are each bound to a
  single connection, and `runtime_session` binds the session to a connection it owns — a lock taken
  on that connection can never be contended from the same session. Open **two independent
  sessions** over the shared engine: `Session(migrated_database)` twice (the `migrated_database`
  fixture returns the session-scoped `Engine`, `conftest.py:152`). Seed the org and both admins
  through a third session and commit before the race starts.
- **Threads with a timeout, never serial calls.** The loser blocks inside
  `pg_advisory_xact_lock` until the winner commits, so calling the two services sequentially in one
  thread hangs the test process. Run each in a `concurrent.futures.ThreadPoolExecutor` worker and
  join with an explicit timeout (a few seconds); a timeout is a *failure*, and it is also how a
  regression that takes the lock after the count, or holds it across a commit, shows up.
- **A deterministic interleaving beats a racy one.** Barrier the two workers so both have entered
  their service call before either commits (`threading.Barrier(2)` released after each acquires its
  session), then assert on outcomes rather than on timing.

| Test | Asserts |
|---|---|
| **Concurrent mutual demotion** | Org with exactly two admins; worker A demotes B, worker B demotes A, both released together. Exactly one call returns normally and exactly one raises `LastAdminError`; afterwards `count_org_admins(...) == 1`. **Never zero** |
| The lock actually blocks | Transaction 1 calls `lock_org_admins` and holds its transaction open; transaction 2's `lock_org_admins` on the **same** `org_id` does not return within a short timeout, and returns promptly once transaction 1 commits |
| Different orgs do not block | Two transactions locking different `org_id`s both proceed immediately — the lock is org-scoped, not global |
| Lock is transaction-scoped | After commit (and after rollback), a second transaction acquires the same lock immediately — no leaked session-level lock |
| Namespace separation | `ORG_ADMIN_LOCK_NAMESPACE != INVITE_LOCK_NAMESPACE`, and a held invite lock does not block `lock_org_admins` for the same org |
| Concurrent promotions are safe | Two workers promoting two different viewers both succeed; `count_org_admins` ends at the expected total (the lock serialises without deadlocking) |
| ~~DMI-105 boundary~~ | **No test. Operator decision, 2026-08-10: a comment, not a test.** A test asserting that the removal-vs-demotion race is *still open* would assert wrong behaviour as correct, and DMI-105 would have to remember to delete it — the temporary code `.claude/CLAUDE.md` forbids. Record the boundary as one comment at the top of `test_org_lock.py` naming `delete_self`/`delete_member` and DMI-105, in the style of `services/invites.py:121`. Nothing to remove later |

Non-concurrent last-admin and self-target coverage lives in areas 2 and 5; this file is only about
the lock.

### Area 5 — activity stamping (`backend/tests/test_auth_service.py`, extend)

| Test | Asserts |
|---|---|
| Password login advances both | After `login(...)`, `last_login_at` and `last_seen_at` are both set and within a second of each other |
| Refresh advances only last-seen | Capture both after login; `refresh_session(...)`; `last_seen_at` strictly advanced, `last_login_at` **unchanged** |
| Invite acceptance stamps both | `accept_invite(...)` (in `test_invite_service.py` if fixtures live better there) leaves both columns set — this is what makes a never-refreshed member report a real last-seen |
| Logout / reset stamp nothing | `logout(...)` and `reset_password(...)` leave both columns unchanged |
| **The UPDATE names only the stamped columns** | Capture emitted SQL with a SQLAlchemy `before_cursor_execute` event listener (or `sqlalchemy.event.listen` on the engine) around a `refresh_session` call; assert the `users` UPDATE's `SET` clause mentions `last_seen_at` and **not** `email`, `password_hash` or `role`. This is the HOT constraint, and prose cannot enforce it |
| Failed login stamps nothing | Wrong password → `InvalidCredentialsError` and both columns unchanged |
| Reuse-detected refresh stamps nothing | A rotated/revoked token → `RefreshTokenError`, `last_seen_at` unchanged |
| Stamp is committed | Re-read the row through a **fresh** session, not the one that wrote it |

### Area 6 — migration (`backend/tests/test_user_activity_migration.py`, mirror `test_user_delete_cascade_migration.py` + `test_identity_migration.py`)

| Test | Asserts |
|---|---|
| Revision chain | `revision == "20260810_16"`, `down_revision == "20260808_15"` |
| `upgrade()` shape | With `op` monkeypatched (the neighbour's technique): both columns added to `users`, both `nullable=True`, both `DateTime(timezone=True)`; the `GRANT DELETE ... invites` is executed |
| `downgrade()` shape | Revokes the grant and drops both columns |
| Live column types | At head against `postgres_engine`, `information_schema.columns` reports `timestamp with time zone` and `is_nullable = YES` for both |
| **No index** | `pg_index`/`pg_indexes` for `users` contains no index whose column list includes `last_seen_at` or `last_login_at`. This test is the enforcement of the HOT constraint against a future well-meaning "optimisation" |
| Model/migration drift | Covered by `test_migrations.py`'s head round-trip (`HEAD_APPLICATION_TABLES` from `SQLModel.metadata`); make sure it still passes with the new columns |
| Runtime grant | `test_migrations.py`'s `RUNTIME_GRANTS_BY_TABLE` case covers `invites` gaining `DELETE`; assert the round-trip security test passes |

### Area 7 — service-level (`test_users_service.py`, `test_invite_service.py`, extend)

- `list_org_members` returns only the given org's members, in the documented order, including
  `NULL`-last.
- `change_member_role` returns `None` for an unknown id and for a foreign-org id, leaving the
  foreign row intact; raises `LastAdminError` when the target is the org's only admin; promotes a
  viewer; demotes an admin when a second admin exists.
- `count_org_admins` behaviour is already covered — do not duplicate it.
- `list_pending_invites` / `revoke_invite`: pending predicate (unconsumed **and** unexpired), org
  scoping, `False` on miss, row gone on success.

### Area 8 — wiring and contract

- `test_auth_wiring.py`: all four routes registered at the exact paths and methods, each carrying
  `require_admin` in its dependency set (extend the existing `DELETE_ROUTES` parametrisation shape).
- `test_contract_fidelity.py`: the five new schemas in `SCHEMA_NAMES`, `RoleChangeConflict` in
  `ERROR_RESPONSE_ROUTES`, the CORS example assertion updated, and a published-operations case
  asserting `operationId`, `security` and the exact response-code set for the four operations.
- `test_cors_headers.py`: `PATCH` present in the preflight's allowed methods.
- `test_users_schemas.py` / `test_invite_schemas.py`: `extra="forbid"` rejection, `last_seen_at`
  nullability, `UpdateUserRoleRequest` rejecting an unknown role.

### Gate

```bash
./database.sh --test                       # or ./database.sh, then export DATABASE_URL_TEST
cd backend && uv run ruff check src tests  # never `ruff format`
cd backend && uv run pytest                # non-zero DB skips ⇒ not a green run

cd frontend && npm run lint && npm run typecheck && npm test && npm run build   # § 11 only
```

The frontend gate runs only because of the one file in § 11. It is not optional: the disclosure is
the feature's legal obligation, not a cosmetic addition.

---

## Specification gaps

Flagged rather than invented. None blocks implementation; each is a named default that a human can
overturn at the approval gate.

1. ~~**`status` is a one-value enum.**~~ **Resolved by the operator, 2026-08-10: no `status` field.**
   The member list publishes only facts the database can vary; DMI-90 renders "Active" for member
   rows and synthesises the invite half of that column from `expires_at`, as it already must. See
   § 3. Accepted consequence: if a real member state ever lands, it is a new field and a DMI-90
   change, not an enum widening.
2. **Role-change response body.** TRUTH does not say what `PATCH` returns. **Default taken:** `200`
   with the updated `OrgMember`. `204` is the alternative if the SPA turns out to refetch anyway.
3. **No email on revoke.** TRUTH is silent on notifying an invitee whose invitation was revoked.
   **Default taken:** send nothing, consistent with ADR-017 § 6 and with re-sending being explicitly
   out of scope.
3a. **Revoked invitations leave no history.** Accepted by the operator, 2026-08-10, with the
   reasoning and the audit-table consequence recorded in § 4. No code follows from this — it is
   written down so the loss reads as a decision rather than an oversight.
4. **No pagination on either list.** Unspecified; **default taken:** none, with an envelope that can
   gain `total`/`page` additively (§ 3).
5. **`last_login_at` ships with no reader.** Intentional per `AUTH.md:128`, but it means this
   feature's own tests are the only thing keeping the column correct until the audit surface lands.
6. ~~**Privacy transparency is a product task.**~~ **Resolved — it ships in this feature (operator,
   2026-08-10).** Recording a member's activity for their org admin to read is workplace monitoring
   under UK GDPR: it may not be covert, and the duty attaches when the *recording* starts — this
   feature — not when a screen displays it. Shipping the disclosure separately is what would create
   the gap, so the feature takes one frontend change: see § 11. Not `HUMAN_INFRA_REQUIRED`.
7. **DMI-104 remains open and is load-bearing here.** `require_admin` reads the role from the JWT
   claim, so a just-demoted admin keeps admin capability for up to ~15 minutes, and a member removed
   or demoted mid-session can still act. This feature deliberately uses the existing gate rather than
   shipping a partial row-backed replacement. Do **not** write a test whose setup depends on the
   window — see [§ Testing area 2](#area-2--patch-apiv1usersuser_id-same-file). The `last_admin`
   branch stays reachable after DMI-104 regardless, via concurrency (§ 7).
