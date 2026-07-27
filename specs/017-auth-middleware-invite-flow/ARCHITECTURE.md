# ARCHITECTURE — Auth middleware + invite flow (DMI-61)

Implements `TRUTH.md`. This is a **BACKEND** feature (`backend/src/api/…`, FastAPI + SQLModel +
Alembic). It touches no hardware-agent code, no `scanner/`, no `tui/`: there are no Textual
screens and no `ScanRunner` / `ScanProgressScreen` call sites, so the `.claude/CLAUDE.md`
ScanRunner thread-through rule is **N/A here**. Single layer — **no `INTEGRATION.md`**.

**No new infrastructure.** Device auth is **Ed25519** (ADR-005 as amended 2026-07-24): the backend
stores only each device's **public key** and verifies signatures with it. There is no shared
secret, so — unlike the retired ADR-015 design — this feature needs **no new environment secret,
no `AGENT_SECRET_ENC_KEY`, no sealed Railway variable**. Nothing here requires new hardware,
daemons, or services. (`cryptography` becomes a backend dependency for Ed25519 verify; that is a
library, not infrastructure.)

## System context

DMI-60 (`specs/016-sessions-auth-routes/`) shipped sessions but mounted them on nothing. DMI-59
(`specs/016-command-channel-data-model/`) shipped the `agents` table with three
encrypted-secret columns and explicitly **deferred the nonce/replay store**. Since ADR-005 was
amended to Ed25519 (2026-07-24), those three columns are wrong — the backend stores no secret —
so this feature **replaces them with a single `public_key` column** and lands the deferred nonce
store. It builds the two gates the rest of the product mounts, closes tenancy on the four live
read routes, and lands the invite flow.

Where each piece sits in the FastAPI request path:

```
                        ┌─ dependency layer (backend/src/api/dependencies/) ─────────────┐
HTTP request ──routing──┤ require_user ──► CallerIdentity(sub, org_id, role)   [DMI-60]  │
                        │ require_admin ─► CallerIdentity, 403 if role != admin  (new)   │
                        │ require_agent ─► AgentIdentity(agent_id, org_id)       (new)   │
                        └──────────────────────┬────────────────────────────────────────┘
                                               │
   routers/ ──────────────────────────────────►│◄──────────────── services/ (no FastAPI types
   hosts.py   scans.py   findings.py  (+require_user, +org_id)     except the cookie helpers)
   invites.py (new)                   (+require_admin on create)
   auth.py    (DMI-60, gains public login-response helpers)
                                               │
   services/read.py         org-scoped queries ┤
   services/invites.py      create / accept    ┤──► services/auth.py::issue_session (new, shared)
   services/device_sig.py   pure canonical-string + Ed25519 sign/verify (no DB, no secret)
   services/nonces.py       insert-or-replay + prune
   management/provision_agent.py  register a device public key (vendor CLI)
                                               │
   models/command.py  Agent (DMI-59, secret cols → public_key) + AgentNonce (new table)
   models/identity.py Org / User / Invite (DMI-58 — unchanged, already sufficient)
```

**What DMI-62/63 later mount, and this feature does not:** the agent gate is verification only.
No route in DMI-61 depends on it — not the WS upgrade (`…/agents/{agent_id}/commands`, DMI-62),
not `POST /api/v1/scans` ingest (DMI-63). It ships tested against a throwaway test app.
`require_admin` is mounted here only on `POST /api/v1/invites`; the trigger-scan route (DMI-64)
mounts it later.

**The gate is split core + adapter, and this is load-bearing for DMI-62.** ADR-011 §2 mounts the
same signature envelope on a **WebSocket upgrade**, where there is no `Request` and no body. A
FastAPI dependency declaring `request: Request` is never populated on a WS route, so a
single HTTP-shaped `require_agent` would be un-mountable by its own stated consumer. Therefore:

- `authenticate_agent(...)` — **transport-agnostic core**. Takes `method`, `path`, `headers`,
  `body` as plain values; holds the entire 8-step order; raises `AgentAuthError` subclasses. No
  FastAPI import. This is what DMI-62 and DMI-63 reuse verbatim.
- `require_agent(request, session)` — **HTTP adapter**, ~6 lines: `await request.body()`, call the
  core, map `AgentAuthError` → `HTTPException(401)` / `HTTPException(403)`. Ships and is tested
  here.
- `require_agent_ws(...)` — **DMI-62 owns it.** Not written here. It will pass `body=b""` (ADR-011
  §2 empty-body hash) and close with `1008` instead of raising `HTTPException`. Adding it later is
  new code against a frozen core, not a rewrite of one.

The core takes `expected_agent_id: UUID | None = None` **now**, unused in this feature. ADR-011:55
requires the WS path's `{agent_id}` to match `X-Device-Id`; when supplied, a mismatch is `401`
(same enumeration reasoning as an unknown device). It is on the core signature from the start
because widening a shared core's signature later is the churn this split exists to avoid.

Routes match `contracts/openapi/openapi.yaml`. The contract declares `FrontendBearerAuth` plus
`401`/`403`/`404` on the four read routes and defines `/api/v1/invites` +
`/api/v1/invites/{token}/accept`.

**One contract edit is part of this feature (done):** `POST /api/v1/invites` declared only `201`,
while the route in fact returns `401` (no token), `403` (viewer) and `400` (already a member — new,
see the two-scope rule below). Those three responses were added, reusing the existing
`BadRequest` / `Unauthorized` / `Forbidden` response components, matching the house style of
`/api/v1/auth/login` (meaningful failures only — no `422`, no `500`). `frontend/src/types/openapi.d.ts`
was regenerated via `npm run gen:types`. `/api/v1/invites/{token}/accept` already declared `400`
and `410` and is **unchanged**.

The
ADR-005 Ed25519 amendment (2026-07-24) already updated the contract's agent-auth scheme
(`AgentHmacAuth` → `AgentSignatureAuth`, `X-Signature` pattern `^[0-9a-f]{128}$`); that edit is
done and is not re-litigated here — but since no agent route is mounted in this feature, it has no
runtime effect on DMI-61's code.

## Data model / contracts

### New table `agent_nonces` (SQLModel in `backend/src/api/models/command.py`)

Placed in `models/command.py` beside `Agent`, not a new module: `alembic/env.py` already imports
`command`, so no metadata-registration change is needed and the FK target is in the same file.

| Column | Type | Null | Notes |
|--------|------|------|-------|
| `id` | `UUID` (pk) | no | `default_factory=uuid4` |
| `agent_id` | `UUID` FK→`agents.id` | no | the device that presented the nonce |
| `nonce` | `str` | no | the raw `X-Nonce` header value (16–128 chars per contract) |
| `expires_at` | `datetime` (`UTC_TIMESTAMP`) | no | **`X-Timestamp` + `DEVICE_SIG_MAX_SKEW_SECONDS`** — not `seen_at + retention`; pruning key |
| `created_at` | `datetime` (`UTC_TIMESTAMP`) | no | `default_factory=utc_now` |

**Uniqueness is per device, not global:** `UniqueConstraint("agent_id", "nonce")` named
`uq_agent_nonces_agent_id_nonce`. Two different agents may legitimately use the same nonce
value (TRUTH acceptance row "Same nonce, different device"). The constraint's index is
`(agent_id, nonce)` with `agent_id` leading, so it doubles as the lookup index — **no separate
`agent_id` index.** One extra index `ix_agent_nonces_expires_at` on `expires_at` serves pruning.

**Replay detection is the INSERT, not a SELECT.** `services/nonces.py::remember_nonce` inserts
the row and lets the unique constraint decide; a `sqlalchemy.exc.IntegrityError` means replay.
A SELECT-then-INSERT is racy under concurrent identical requests. On `IntegrityError` the
function **must `session.rollback()`** before raising, or the poisoned transaction breaks the
rest of the request.

**The nonce is only recorded after the signature verifies.** Otherwise an unauthenticated
attacker could flood the table by spraying nonces. Order is fixed in the gate below.

**`expires_at` is derived from the request timestamp, not from server time.** A request stamped
`t` is accepted exactly while `now ∈ [t − skew, t + skew]`, so the nonce must be remembered until
exactly `t + skew` — no more, no less. Writing `expires_at = t + DEVICE_SIG_MAX_SKEW_SECONDS` makes
retention provably correct and **removes the need for a separate retention setting** (a
`seen_at + retention` scheme is only approximately right, and is silently wrong if anyone
configures retention below `2 × skew`: a request stamped `t = now + skew` would have its nonce
pruned while that timestamp was still acceptable, reopening the replay window the table exists to
close).

**Boundary, stated because it is an off-by-one waiting to happen:** the skew check rejects on
`abs(now − t) > skew`, so `now == t + skew` is still *accepted*. Pruning must therefore use a
**strict** `<`, or it would delete a row one instant before its last legitimate replay:

```sql
DELETE FROM agent_nonces WHERE expires_at < :now
```

**Pruning** is opportunistic, not a background job (there is no scheduler in this feature):
`prune_expired_nonces(session, *, now)` issues that one indexed `DELETE` and is called by the gate
on the successful path, before `remember_nonce`.

### Migration `backend/alembic/versions/20260724_09_agent_nonces.py`

- `revision = "20260724_09"`, `down_revision = "20260724_08"` (verified current head is
  `20260724_08_timestamptz.py`).
- `upgrade()` creates `agent_nonces`, then applies the same security fence
  `20260723_07_command_channel.py` uses: `ENABLE ROW LEVEL SECURITY`; the guarded
  `DO $$ … IF EXISTS pg_roles … REVOKE ALL PRIVILEGES … FROM anon / authenticated`; then
  `GRANT SELECT, INSERT, DELETE ON TABLE public.agent_nonces TO dmitri_runtime`.
- **The grant differs from every prior table**: this one needs `DELETE` (pruning) and does not
  need `UPDATE` (rows are insert-once, never mutated). Grant exactly
  `SELECT, INSERT, DELETE` — the migration test asserts `UPDATE` is *not* held.
- Column types follow the house style: `sa.Uuid()`, `sqlmodel.sql.sqltypes.AutoString()`,
  `sa.DateTime(timezone=True)` (matching the `20260724_08` timestamptz convention).
- `downgrade()` revokes the `dmitri_runtime` grant, then drops the table. No role create/drop.

### `agents` secret columns → `public_key` (migration)

DMI-59 shipped `agents` with `secret_ciphertext` / `secret_nonce` / `secret_key_version` for the
HMAC-encrypted-secret design. ADR-005 is now Ed25519, so those three columns are wrong: the
backend stores **only a public key** and holds no secret. No `agents` row has ever been created
(this feature is the first writer, via the provisioning CLI), so the swap is a clean drop-and-add,
not a data migration.

- New migration `backend/alembic/versions/20260724_11_agents_public_key.py`
  (`revision = "20260724_11"`, `down_revision = "20260724_10"`).
- `upgrade()`: `op.drop_column("agents", "secret_ciphertext")`, `"secret_nonce"`,
  `"secret_key_version"`; then `op.add_column("agents", sa.Column("public_key", sa.LargeBinary(),
  nullable=False))`. The table is empty, so a `NOT NULL` add needs no server default.
- `downgrade()`: drop `public_key`; re-add the three columns exactly as
  `20260723_07_command_channel.py` declared them (`secret_ciphertext`/`secret_nonce` `LargeBinary`
  NOT NULL, `secret_key_version` `Integer` NOT NULL). Since the table is empty this is safe; if a
  future environment holds rows, the down-migration is knowingly lossy (documented in the file).
- `models/command.py`: `Agent` drops the three secret fields and gains
  `public_key: bytes = Field(sa_type=LargeBinary)` — 32 raw Ed25519 public-key bytes, stored in
  the clear (a public key is not a secret). `revoked_at` / `last_seen_at` / `org_id` /
  `display_name` are unchanged.
- The security fence on `agents` (RLS + `dmitri_runtime` grants) is unchanged — the migration only
  swaps columns, it does not re-grant.

### Existing tables

`invites` (DMI-58, `models/identity.py`) already has exactly what the flow needs: `org_id`,
`email`, `role`, unique-indexed `token_hash`, `expires_at`, `consumed_at`, and the
`ck_invites_role` CHECK. **No migration touches `invites`.** (`users` **does** change — see the
email-uniqueness migration below.)

`users` **does** change — see below.

### `users` email uniqueness becomes global (migration)

`services/auth.py::login` resolves an account with
`select(User).where(func.lower(User.email) == email.lower()).first()` — **no org filter**, and
none is possible: the frozen `LoginRequest` (`openapi.yaml:2053`) is `{email, password}` with
no org selector. But DMI-58's index is `ix_users_org_email` UNIQUE `(org_id, lower(email))`,
which permits the same address in two orgs. Nothing has ever created a `User`, so the conflict
is currently unreachable; **`accept_invite` is the first writer, so this feature is what makes
it reachable** and therefore owns the fix.

- New migration `backend/alembic/versions/20260724_10_users_email_global_unique.py`
  (`revision = "20260724_10"`, `down_revision = "20260724_09"`).
- `upgrade()`: `op.drop_index("ix_users_org_email", table_name="users")`, then
  `op.create_index("ix_users_email", "users", [sa.text("lower(email)")], unique=True)`.
- `downgrade()`: the exact inverse, recreating `ix_users_org_email` as DMI-58 declared it
  (`20260716_02_identity_schema.py:57`).
- `models/identity.py`: replace the `Index("ix_users_org_email", "org_id", text("lower(email)"),
  unique=True)` entry in `User.__table_args__` with
  `Index("ix_users_email", text("lower(email)"), unique=True)`. The `ck_users_role` CHECK stays.
- `services/invites.py::accept_invite` checks for an existing user by email **globally**
  (`select(User).where(func.lower(User.email) == email.lower())`), not scoped to the invite's
  org → `DuplicateUserError` → `400`. The index is the backstop; the explicit check is what
  produces the clean status code instead of an `IntegrityError`.
- **Note for DMI-76 (users & invites admin API):** dropping `ix_users_org_email` leaves `users`
  with **no index on `org_id`** — the composite was the only one, and `User.org_id` is declared
  `Field(foreign_key="orgs.id")` with no `index=True`. Nothing in DMI-61 queries users by org, so
  no index is added here rather than shipping an unused one. DMI-76's "list the users in my org"
  endpoint is the first such query and should add `Index("ix_users_org_id", "org_id")` with its own
  migration.
- The migration is safe to apply unconditionally today (`users` is empty in every environment).
  It is **not** conditional or guarded — if a future environment holds a genuine cross-org
  duplicate, the index creation must fail loudly rather than silently pick a winner.

### `Host.org_id` / `Scan.org_id` are nullable — how NULL is treated

`HostRecord.org_id` and `ScanRecord.org_id` are `UUID | None` (`models/persistence.py:27,70`).
`FindingRecord` has **no** `org_id` at all — a finding's tenant is reached through
`findings.scan_id → scans.org_id`.

Rule: **a row with `NULL org_id` belongs to no org and is invisible to every caller.** Scoping
is a plain `WHERE org_id = :caller_org_id`; SQL three-valued logic already makes that false for
NULL, so **do not add `OR org_id IS NULL`** and do not add a fallback branch. Consequences,
stated so nobody "fixes" them later:

- Legacy rows persisted before org attribution become unreadable through the read API. That is
  the correct security posture and these rows exist only in dev databases.
- **No backfill migration and no `NOT NULL` tightening in this feature.** Making the columns
  `NOT NULL` requires the ingest path to always supply an org, which is DMI-63's job.
- Test fixtures must therefore **seed an `Org` row and set `org_id` explicitly** on every
  `HostRecord` and `ScanRecord` they create, then mint the caller's token for that same
  `org_id`. Cross-org tests seed a second `Org` and a second set of records.

### Org scoping through `services/read.py`

Every public function gains a **required keyword-only `org_id: UUID`**. It is keyword-only and
required on purpose: a positional optional would let a caller silently skip tenancy.

| Function | New signature | Filter |
|----------|---------------|--------|
| `list_hosts` | `(session, *, org_id, page=1, per_page=20)` | `.where(HostRecord.org_id == org_id)` on **both** the `count()` and the page query |
| `get_host_detail` | `(session, host_id, *, org_id)` | replace `session.get(HostRecord, host_id)` with `select(HostRecord).where(HostRecord.id == host_id, HostRecord.org_id == org_id)`; returns `None` for a foreign row → router turns it into `404`. **Plus** `.where(ScanRecord.org_id == org_id)` on the two inline scan queries — see below |
| `get_scan_detail` | `(session, scan_id, *, org_id)` | same pattern on `ScanRecord.scan_id` / `ScanRecord.org_id` |
| `list_findings` | `(session, *, org_id, host_id=None, page=1, per_page=20)` | findings carry no `org_id`: add `.join(ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id).where(ScanRecord.org_id == org_id)` to the `base` select **before** the `host_id` branch, so the count subquery and the page query share it |

The private helpers (`_ports_for_scan_host`, `_to_host_summary`, `_to_finding_read`) stay
unscoped — they are reached only from an already-scoped parent row.

**`get_host_detail`'s two inline scan queries must be scoped too — scoping the host row is not
enough.** Both the `latest_scan_host` lookup (`read.py:47-53`) and the `scan_history_rows` lookup
(`read.py:60-65`) reach `ScanRecord` via `ScanHostRecord.host_id`, not via the host row's org, so
the `HostRecord.org_id` filter does not constrain them. Left alone, any `ScanHostRecord` linking
an org-A host to an org-B scan would surface org-B's scan timestamps, scan modes, severities and —
through `_ports_for_scan_host` — org-B's **open ports and service versions**, inside a `200` on a
host the caller legitimately owns. The by-id `404` test cannot catch that.

`ScanRecord` is already joined in both queries, so the fix is one predicate each:

```python
    .where(ScanHostRecord.host_id == host_id)
    .where(ScanRecord.org_id == org_id)
```

This holds the boundary regardless of how DMI-63 later resolves host identity across orgs. It is
deliberately **not** expressed as an invariant delegated to ingest: DMI-61's tenancy guarantee must
not depend on unwritten code.

A cross-org record fetched by id returns `404`, never `403`: a `403` would confirm the record
exists (TRUTH "Cross-org read is invisible").

### `Settings` additions (`backend/src/api/core/config.py`)

| Field | Env alias | Type | Default |
|-------|-----------|------|---------|
| `device_sig_max_skew_seconds` | `DEVICE_SIG_MAX_SKEW_SECONDS` | `int` | `300` (ADR-005: 5 minutes) |
| `invite_ttl_hours` | `INVITE_TTL_HOURS` | `int` | `48` (AUTH.md target 24–72 h) |

There is deliberately **no `AGENT_NONCE_RETENTION_SECONDS`**: nonce lifetime is derived from
`DEVICE_SIG_MAX_SKEW_SECONDS` (see `agent_nonces` above), so the two cannot be configured into
disagreement.

**Both have defaults — neither is required, and there is no new secret.** The Ed25519 switch
deletes the `AGENT_SECRET_ENC_KEY` field entirely, so the "required-field-with-no-default" trap
that DMI-60 hit with `JWT_SIGNING_SECRET` **does not recur here**: no `conftest.py`
`os.environ.setdefault` for a device key, no `.env.example` required entry, no `test_settings.py`
delete-loop exclusion. `test_settings.py` still gains coverage for the two new **optional**
fields (defaults present, override parses), but nothing can break the suite by absence.

No `field_validator` for a base64 key is needed. (`DEVICE_SIG_MAX_SKEW_SECONDS` is the renamed
`HMAC_MAX_SKEW_SECONDS` — the algorithm changed, so the env name follows; nothing in the repo
reads the old name yet, so this is a free rename, not a migration.)

### Management commands: session, credentials, transactions, exit codes

Both commands run **outside FastAPI**, so `Depends(get_session)` does not apply. None of this is
new machinery — every point below names an existing pattern to copy.

**Session.** Use the idiom already at `services/worker.py:36`:

```python
for session in get_session():
    ...
```

`get_session()` builds on `get_engine()`, which reads `settings.database_url`. Nothing else is
needed — no bespoke `create_engine`, no second settings object.

**Credentials — the runtime role, never the admin one.** `DATABASE_URL` resolves to
`dmitri_runtime`, which already holds `SELECT, INSERT, UPDATE` on `orgs` / `users` / `invites`
(`20260716_02_identity_schema.py:88`) and on `agents` (`20260723_07_command_channel.py:81`). That
covers every write these commands make, so **neither command needs `DATABASE_URL_DIRECT`.** This is
deliberate: `docs/cloud/railway/SETUP.md:217` confines the admin credential to "the operator's local
shell for a single `alembic` command," and these commands stay inside that fence rather than
widening it.

**Where they run.** From a backend checkout on the operator's machine, `DATABASE_URL` pointed at
the target database — the same posture as `alembic upgrade`. They are **never** installed as, or
invoked from, the `api` or `worker` Railway services: those are long-running and network-exposed,
and neither has any reason to be able to mint an org.

**`bootstrap_org` refuses a duplicate org name.** Running it twice for the same customer is an
operator slip — a second `Org` with its own admin invite, silently diverging from the first — and
the command must not do it. Before creating anything:

```python
existing = session.exec(
    select(Org).where(func.lower(func.trim(Org.name)) == name.strip().lower())
).first()
if existing is not None:
    print(f"org already exists: {existing.id} ({existing.name})", file=sys.stderr)
    return 1
```

The comparison is **case-insensitive on the trimmed name**, because `"Acme"` and `"acme "` are the
same mistake and an exact-match check would wave the second one through. The stored `Org.name`
keeps the operator's original casing — only the comparison is normalized.

This is enforced **in the command, not by a `UNIQUE` constraint on `orgs.name`**, and the
distinction is deliberate:

- It is a **guard against running the command twice**, not a product invariant. Two genuinely
  distinct customers could legitimately share a name ("Acme Security" in two regions), and a unique
  index would make that unbootstrappable — with no way out short of another migration.
- It needs no fourth migration, and `orgs` has no such constraint today.
- If a real duplicate-name customer ever appears, a `--force` flag is a two-line addition. It is
  **not** added now: nothing has asked for it, and an escape hatch nobody needs is an escape hatch
  someone will reach for by reflex.

The rule lives here rather than in `TRUTH.md` for the same reason — it constrains a vendor CLI's
behavior, not the product's domain model.

**Transaction ordering in `bootstrap_org` — the one real trap.** `create_invite` commits
internally (mirroring `forgot_password` in `services/auth.py`). `invites.org_id` is an FK to
`orgs.id`. So the `Org` must be added **and committed** before `create_invite` is called, or the
invite insert fails on a row that is not yet visible to its own transaction's constraint check.
Sequence is fixed: add `Org` → `commit()` → `create_invite(session, org_id=org.id, role="admin", …)`.

**Exit codes and output.** `main(argv: list[str] | None = None) -> int` per `worker_main.py`.
Return `0` on success, `1` on an expected failure (unknown `--org-id`, `--public-key` that is not
64 hex chars decoding to 32 bytes), with a one-line message on **stderr** — not a traceback, which
is noise for an operator running a documented command. `argv` defaults to `None` so tests call
`main([...])` directly, as `test_worker_startup.py` does with its entrypoint.

**Secrets on stdout.** `bootstrap_org` prints the raw invite token and `provision_agent --generate`
prints a private key. Both go to **stdout exactly once** and are never logged through the `logging`
module — a logger would put them in Railway's log stream. `--generate` prints a banner marking the
key as local-testing-only.

### Invite contract (frozen — `openapi.yaml` lines ~775–845, ~2116–2155)

**`POST /api/v1/invites`** — `security: FrontendBearerAuth`, admin only.

- Request `CreateInviteRequest`: `{ email: string(email), role: "admin" | "viewer" }`,
  `additionalProperties: false`.
- Response **201** `InviteCreatedResponse`: `{ invite_token: string, expires_at: date-time }`,
  `additionalProperties: false`.
- `org_id` is taken from `CallerIdentity.org_id` and is **never** accepted from the body — an
  admin cannot invite into another org.
- The raw token is returned exactly once; only `sha256(raw)` is stored in `invites.token_hash`.
- **The duplicate-email check is deliberately scoped differently at the two ends of the flow.**
  This asymmetry is the design, not an oversight — implementers must not "unify" the two:

  | Where | Scope of the `User` lookup | On hit |
  |-------|---------------------------|--------|
  | `create_invite` | `.where(func.lower(User.email) == email.lower(), User.org_id == org_id)` — **own org only** | `AlreadyMemberError` → `400`, no invite row |
  | `accept_invite` | `.where(func.lower(User.email) == email.lower())` — **global, no org filter** | `DuplicateUserError` → `400`, invite not consumed |

  Creation stays org-scoped because the caller is an authenticated admin of *another* tenant: a
  global check there answers "does this address have an account at some other company?" for any
  address an admin cares to type. Acceptance can be global because the caller already holds a valid
  single-use invite token for that specific address — they learn nothing they could not have
  learned by accepting it.

**`POST /api/v1/invites/{token}/accept`** — `security: []` (unauthenticated; the invitee has no
account). Path param `token`, `minLength: 16`.

- Request `AcceptInviteRequest`: `{ email: string(email), password: string(minLength 12) }`.
- Response **201**: a full `LoginResponse` (`access_token`, `token_type: "bearer"`,
  `expires_in`) **plus** the `Set-Cookie: dmitri_refresh=…` refresh cookie
  (`components/headers/Set-Cookie-Refresh`). Note the status is **201**, not the 200 the login
  route returns — set `status_code=201` on the route decorator.
- `400` for policy / duplicate / email-mismatch failures. `410` for expired, consumed, or
  unknown token.

**No invite URL is built anywhere in this feature, and no base-URL setting is added.**
`InviteCreatedResponse` is `additionalProperties: false` over exactly `{invite_token, expires_at}`,
so an `invite_url` field would require a contract change — and there is no consumer for it here.
The two eventual consumers need different things and neither is in scope:

- **The admin screen (DMI-76)** is the caller, so it already knows its own origin and composes
  `${window.location.origin}/invite/${invite_token}` client-side. It needs nothing from the
  backend but the token.
- **The invite email (DMI-71)** needs an absolute URL, because an email has no origin. DMI-71
  introduces the base-URL setting when it has a mailer that actually sends.

`send_invite_link(email, token)` therefore keeps a token-only signature; `LogMailer` logs the
token. Adding `INVITE_LINK_BASE_URL` now would configure a code path that only writes to a log.
(`cors_allowed_origins` in `core/config.py:54` is *not* to be repurposed for this — it is a
security control, and reading a display URL out of it couples the two.)

The body `email` must equal the invite's `email` case-insensitively; a mismatch is `400`.
Otherwise an intercepted link could mint an account for an arbitrary address. The account is
created with the invite's `email` and the invite's `role`, in the invite's `org_id`.

### Device-signature contract (`openapi.yaml` `AgentSignatureAuth` + parameters ~995–1040, ADR-005 as amended)

Five required headers: `X-Device-Id` (uuid — its **value is the `agent_id`**, per the frozen
parameter description; the header name is frozen even though it says "Device"), `X-Timestamp`
(ISO 8601), `X-Nonce` (16–128 chars), `X-Body-SHA256` (`^[0-9a-f]{64}$`), `X-Signature`
(**`^[0-9a-f]{128}$`** — a 64-byte Ed25519 signature, double the old 32-byte HMAC width).

Canonical string, newline-joined, **exactly** (ADR-005 §1 — unchanged by the amendment):

```
METHOD\nPATH\nX-Device-Id\nX-Timestamp\nX-Nonce\nX-Body-SHA256
```

`METHOD` is the uppercase HTTP method; `PATH` is the **resolved** request path (no query string) —
`request.url.path` in the HTTP adapter, never a route template. For the DMI-62 upgrade that is
`/api/v1/agents/<the-actual-uuid>/commands`, not `/api/v1/agents/{agent_id}/commands`. Stated
explicitly because the Pi side (DMI-57 / DMI-65) reads this doc to know what to sign, and a
template-vs-resolved mismatch fails as an opaque `401`. The remaining four are the raw header
values as sent.

`X-Signature` = lowercase hex `Ed25519_sign(device_private_key, canonical_string)`. The backend
never holds the private key; it **verifies** with the stored public key. Verification uses
`cryptography`'s `Ed25519PublicKey.from_public_bytes(agent.public_key).verify(sig_bytes,
canonical.encode())`, which raises `InvalidSignature` on any mismatch — there is no
`hmac.compare_digest`, and constant-time comparison is intrinsic to signature verification.

The gate's fixed order, implemented **once** in `authenticate_agent` — each step's failure status
is load-bearing:

1. All five headers present and shape-valid → else `401`.
1a. If `expected_agent_id` was supplied, `X-Device-Id` equals it → else `401` (ADR-011:55; unused
   in this feature, exercised by a core-level test).
2. `X-Device-Id` parses as UUID and an `agents` row exists → else `401`
   (**deviation from ADR-005**, which lists "unknown device" under `403`. `TRUTH.md` is the
   approved truth and says `401` — a `403` for an unknown id is a device-enumeration oracle.
   Only a *known* device that is revoked earns `403`.)
3. `agents.revoked_at is not None` → `403`.
4. `abs(now - X-Timestamp) > DEVICE_SIG_MAX_SKEW_SECONDS` → `401`.
5. `sha256(raw body).hexdigest() != X-Body-SHA256` → `401` (tampered body).
   **A bodyless request is not a special case.** `GET`, and the DMI-62 WS upgrade, hash the empty
   byte string: `body_sha256(b"")` is the well-known constant
   `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and the device must send
   exactly that in `X-Body-SHA256` (ADR-011 §2, "empty body hash"). There is no branch that skips
   the check when the body is empty — an omitted or blank header is a missing header and fails at
   step 1. Written out because the Pi side (DMI-57 / DMI-65) reads this doc to know what to send.
6. `Ed25519_verify(agent.public_key, canonical, sig)` → `InvalidSignature` → `401`. A malformed
   `X-Signature` (not 64 bytes after hex-decode) is also `401`, not a 500 — catch and map it.
7. `prune_expired_nonces(now=now)`, then
   `remember_nonce(expires_at=parsed_timestamp + skew)` → `IntegrityError` means replay → `401`.
8. Return `AgentIdentity(agent_id, org_id)` **read from the `agents` row**. Any `org_id` a
   device asserts in headers or body is ignored — the gate never reads one.

### Error-code / status mapping (authoritative)

| Situation | Status | Raised by |
|-----------|--------|-----------|
| No `Authorization` header on a business route | `401` | `require_user` (existing) |
| Malformed / expired / bad-signature JWT | `401` | `require_user` (existing) |
| JWT valid, `role != "admin"` on an admin route | `403` | `require_admin` (new) |
| Record exists but belongs to another org, fetched by id | `404` | `routers/hosts.py`, `routers/scans.py` (service returns `None`) |
| Cross-org rows in a list | omitted (`200`) | `services/read.py` filter |
| Invite create: email already a user in the **admin's own** org | `400` | `AlreadyMemberError` |
| Invite create: email already a user in **another** org | `201` (indistinguishable from a fresh address — deliberate, see above) | — |
| Invite accept: password policy violation | `400` | `PasswordPolicyError` |
| Invite accept: body email ≠ invite email | `400` | `InviteEmailMismatchError` |
| Invite accept: email already a user in **any** org | `400` | `DuplicateUserError` |
| Invite accept: token unknown / expired / consumed | `410` | `InviteTokenError` |
| Device sig: header missing, malformed, unknown agent, skew, body-hash mismatch, bad/short signature, replay | `401` | `require_agent` |
| Device sig: known agent with `revoked_at` set | `403` | `require_agent` |

`400`, `410`, and `403` on a failed accept **must not consume the invite** — `consumed_at` is
written only on the success path, in the same commit as the `User` insert.

Error bodies keep the existing `HTTPException(detail=…)` shape used by every current route. The
contract's `ErrorResponse` envelope (`{error: {code, message, details}}`) is **not** adopted
here — that divergence is pre-existing and is contract ask C15, owned by DMI-77.

## New files and naming (mandatory)

Every path is repo-relative. Public symbols are the naming contract — implementers use these
exact names.

### Created

| Path | Kind | Public symbols | Note |
|------|------|----------------|------|
| `backend/src/api/dependencies/agent_auth.py` | dependency | `AgentIdentity` (pydantic `BaseModel`: `agent_id: UUID`, `org_id: UUID`); `AgentAuthError(Exception)` with subclasses `AgentUnauthenticated` (→`401`) and `AgentRevoked` (→`403`); **core** `def authenticate_agent(session, *, method: str, path: str, headers: Mapping[str, str], body: bytes, now: datetime, expected_agent_id: UUID \| None = None) -> AgentIdentity`; **HTTP adapter** `async def require_agent(request: Request, session: Session = Depends(get_session)) -> AgentIdentity` | `authenticate_agent` imports no FastAPI type and is the only place the 8-step order exists — DMI-62/63 reuse it. `require_agent` is a thin `await request.body()` + `AgentAuthError`→`HTTPException` map, `async` for that reason. Mounted on **no** route in this feature. `require_agent_ws` is **not** written here (DMI-62) |
| `backend/src/api/services/device_sig.py` | pure logic, no DB, no secret | `canonical_string(method, path, device_id, timestamp, nonce, body_sha256) -> str`, `verify(public_key: bytes, canonical: str, signature_hex: str) -> None` raising `SignatureError`, `body_sha256(body: bytes) -> str`, `parse_timestamp(value: str) -> datetime`, `DeviceSigHeaders` (frozen dataclass of the five values), `parse_headers(headers) -> DeviceSigHeaders` raising `MalformedSigHeaders`, plus test/CLI helpers `generate_keypair() -> tuple[bytes, bytes]` (private_raw, public_raw) and `sign(private_key: bytes, canonical: str) -> str` | wraps `cryptography` Ed25519. `verify` decodes the hex sig, calls `Ed25519PublicKey.from_public_bytes(public_key).verify(...)`, and re-raises `InvalidSignature` / bad length as `SignatureError` — the gate maps that to `401`. **The only module that imports `cryptography`.** No `AESGCM`, no env key |
| `backend/src/api/services/nonces.py` | DB | `remember_nonce(session, *, agent_id: UUID, nonce: str, expires_at: datetime) -> None` raising `NonceReplayError(ValueError)`, `prune_expired_nonces(session, *, now: datetime) -> None` | takes `expires_at` (= `X-Timestamp` + skew), **not** `now` — the caller owns the derivation. `remember_nonce` rolls back before raising on `IntegrityError`; `prune_expired_nonces` uses strict `expires_at < now` |
| `backend/src/api/services/invites.py` | service | `create_invite(session, *, org_id: UUID, email: str, role: str, mailer: Mailer) -> tuple[str, datetime]`, `accept_invite(session, *, token: str, email: str, password: str) -> tuple[str, str, int]`, `InviteTokenError(ValueError)`, `InviteEmailMismatchError(ValueError)`, `DuplicateUserError(ValueError)`, `AlreadyMemberError(ValueError)` | `accept_invite` returns the same `(access_token, refresh_token, expires_in)` triple `services/auth.py::login` returns. `create_invite` raises `AlreadyMemberError` when the email is already a user **in `org_id`** — see the two-scope rule below |
| `backend/src/api/schemas/invites.py` | pydantic | `CreateInviteRequest` (`email: str`, `role: Literal["admin", "viewer"]`), `InviteCreatedResponse` (`invite_token: str`, `expires_at: datetime`), `AcceptInviteRequest` (`email: str`, `password: constr(min_length=MIN_LENGTH)`) | all with `model_config = ConfigDict(extra="forbid")`, matching `schemas/auth.py`; reuse `MIN_LENGTH` from `services/passwords.py`, never a literal `12` |
| `backend/src/api/routers/invites.py` | router | `router = APIRouter()`, `create_invite_route`, `accept_invite_route`, `invite_preflight` | mirrors `routers/auth.py`, including the derived-`OPTIONS` loop at the bottom |
| `backend/src/api/management/__init__.py` | package | — | empty |
| `backend/src/api/management/bootstrap_org.py` | management command | `def main(argv: list[str] | None = None) -> int`, `if __name__ == "__main__": raise SystemExit(main())` | run as `uv run backend-bootstrap-org --org-name "Acme" --email admin@acme.com`; `argparse`; **refuses a duplicate org name** (see below), then creates the `Org`, **commits it**, then calls `create_invite(..., role="admin")`; prints the org id and the raw invite token to stdout once. **No HTTP route, no bootstrap-token env var** |
| `backend/src/api/management/provision_agent.py` | management command | `def main(argv: list[str] | None = None) -> int`, `if __name__ == "__main__": raise SystemExit(main())` | run as `uv run backend-provision-agent --org-id <uuid> --display-name "NSPi lab" --public-key <hex>`; `argparse`; validates the org exists and the hex decodes to 32 bytes, inserts the `Agent` row with that `public_key`, prints the new `agent_id` (`DEVICE_ID`) to stdout. **Registers a public key only — never generates or receives a private key.** For an all-in-one dev convenience it MAY accept `--generate` to call `device_sig.generate_keypair()` and print the private key once for local testing, clearly labelled not-for-production. **No HTTP route** |
| `backend/alembic/versions/20260724_09_agent_nonces.py` | migration | `revision = "20260724_09"`, `down_revision = "20260724_08"` | `agent_nonces` + security fence (see above) |
| `backend/alembic/versions/20260724_10_users_email_global_unique.py` | migration | `revision = "20260724_10"`, `down_revision = "20260724_09"` | `ix_users_org_email` → `ix_users_email` UNIQUE `lower(email)` (see above) |
| `backend/alembic/versions/20260724_11_agents_public_key.py` | migration | `revision = "20260724_11"`, `down_revision = "20260724_10"` | drop `secret_ciphertext`/`secret_nonce`/`secret_key_version`, add `public_key` `LargeBinary` NOT NULL (see above) |

### Touched (existing files that must change)

| Path | Change |
|------|--------|
| `backend/src/api/models/command.py` | (1) `Agent`: drop `secret_ciphertext`/`secret_nonce`/`secret_key_version`, add `public_key: bytes = Field(sa_type=LargeBinary)`. (2) add `AgentNonce` SQLModel table; `UniqueConstraint("agent_id", "nonce", name="uq_agent_nonces_agent_id_nonce")` in `__table_args__`, `expires_at` indexed |
| `backend/src/api/models/identity.py` | `User.__table_args__`: `Index("ix_users_org_email", "org_id", text("lower(email)"), unique=True)` → `Index("ix_users_email", text("lower(email)"), unique=True)`. `ck_users_role` unchanged; no column changes |
| `backend/src/api/core/config.py` | two new **optional** `Settings` fields (`device_sig_max_skew_seconds`, `invite_ttl_hours`) — both with defaults, no `field_validator`, **no required secret** |
| `backend/src/api/dependencies/auth.py` | add `ROLE_ADMIN = "admin"`, `ROLE_VIEWER = "viewer"`, and `def require_admin(caller: CallerIdentity = Depends(require_user)) -> CallerIdentity` raising `HTTPException(403)`. `require_user` and `CallerIdentity` are **unchanged** |
| `backend/src/api/services/auth.py` | extract `def issue_session(session, *, user: User) -> tuple[str, str, int]` from the body of `login`; `login` and `refresh_session` call it; `services/invites.py::accept_invite` calls it. **Do not duplicate access-token + refresh-token issuance** |
| `backend/src/api/routers/auth.py` | rename `_set_refresh_cookie` → `set_refresh_cookie` and `_clear_refresh_cookie` → `clear_refresh_cookie` (update the three internal call sites); add `def login_response(response: Response, access_token: str, refresh_token: str, expires_in: int) -> LoginResponse` that sets the cookie and returns the body, and use it in `login_route` and `refresh_route`. `routers/invites.py` imports `login_response` — **the invite route must not build a `LoginResponse` or a cookie of its own** |
| `backend/src/api/services/mailer.py` | add `send_invite_link(self, email: str, token: str) -> None` to the `Mailer` protocol and to `LogMailer`. **Takes the raw token, not a URL** — see the link-construction note below |
| `backend/src/api/services/read.py` | required keyword-only `org_id` on `list_hosts`, `get_host_detail`, `get_scan_detail`, `list_findings`; filters per the table above (`list_findings` joins `ScanRecord`) |
| `backend/src/api/routers/hosts.py` | **both** routes: `caller: CallerIdentity = Depends(require_user)`; pass `org_id=caller.org_id` to `list_hosts` / `get_host_detail` |
| `backend/src/api/routers/scans.py` | `read_scan`: `Depends(require_user)`; `org_id=caller.org_id` |
| `backend/src/api/routers/findings.py` | `read_findings`: `Depends(require_user)`; `org_id=caller.org_id` (keep the `host_id` query param) |
| `backend/src/api/main.py` | `from api.routers import auth, findings, hosts, invites, scans` and `app.include_router(invites.router)` |
| `backend/pyproject.toml` | (1) add `cryptography>=42.0` (Ed25519 via `cryptography.hazmat.primitives.asymmetric.ed25519`) — not currently a dependency. (2) two `[project.scripts]` entries beside the existing `backend-worker`: `backend-bootstrap-org = "api.management.bootstrap_org:main"` and `backend-provision-agent = "api.management.provision_agent:main"` — **`backend-` prefix, not `dmitri-`**: `dmitri` is the *Pi's* console script (`hardware-agent/pyproject.toml:18`), a different package on a different machine, and the names must not read as one family |
| `backend/.env.example` | `DEVICE_SIG_MAX_SKEW_SECONDS=`, `INVITE_TTL_HOURS=` (both optional, shown with their defaults; **no device secret key, no nonce-retention knob**) |

**Metadata / registration call sites, checked explicitly:**

- `backend/src/api/models/__init__.py` — already does `from . import command, identity,
  persistence, session`. `AgentNonce` lives in `command.py`, so **no edit needed**.
- `backend/alembic/env.py` — already does `from api.models import command, identity,
  persistence`. **No edit needed** (this is precisely why `AgentNonce` goes in `command.py`
  rather than a new module).
- `backend/tests/conftest.py::_truncate_application_tables` iterates
  `SQLModel.metadata.sorted_tables`, so `agent_nonces` is truncated automatically once the model
  is registered. **No edit needed for truncation.** No new env var is required either — the
  Ed25519 design adds no required secret, so `conftest.py` needs no `os.environ.setdefault` for
  device auth (contrast DMI-60's `JWT_SIGNING_SECRET`).

### Tests

| Path | Action | Mirrors |
|------|--------|---------|
| `backend/tests/conftest.py` | touch | add a `bearer_headers` factory fixture returning `{"Authorization": f"Bearer {create_access_token(...)}"}` for a given `org_id`/`role`; add a `seeded_org` fixture returning a committed `Org`; add an `agent_keypair` / `provisioned_agent` helper that calls `device_sig.generate_keypair()` and inserts an `Agent` with the public key. **No device-secret env setdefault** |
| `backend/tests/test_agent_nonce_migration.py` | create | `test_command_migration.py` |
| `backend/tests/test_agents_public_key_migration.py` | create | `test_command_migration.py` — asserts `secret_ciphertext`/`secret_nonce`/`secret_key_version` are gone, `public_key` exists and is NOT NULL, the `agents` security fence still holds, and the migration round-trips up→down |
| `backend/tests/test_users_email_unique_migration.py` | create | `test_identity_migration.py` — asserts `ix_users_org_email` is gone, `ix_users_email` exists and is unique, two users with the same email in **different** orgs are rejected at the DB, and the migration round-trips up→down |
| `backend/tests/test_device_sig.py` | create | `test_command_lifecycle.py` (pure unit, no DB) — canonical string is byte-exact; `sign` then `verify` round-trips; a tampered canonical, a wrong public key, a short/garbage hex sig each raise `SignatureError`; `generate_keypair` yields 32-byte raw keys; RFC 8032 test vector if convenient |
| `backend/tests/test_require_agent.py` | create | `test_require_user.py` (throwaway `FastAPI()` app + `TestClient`) — drives the whole gate order with a real generated keypair |
| `backend/tests/test_nonces.py` | create | `test_tokens.py` |
| `backend/tests/test_require_user.py` | touch | add `require_admin` cases |
| `backend/tests/test_invite_service.py` | create | `test_auth_service.py` |
| `backend/tests/test_invite_routes.py` | create | `test_auth_routes.py` |
| `backend/tests/test_invite_schemas.py` | create | `test_auth_schemas.py` |
| `backend/tests/test_read_endpoints.py` | touch | route-level auth + org scoping (its local sqlite fixtures must now seed an `Org` and set `org_id`) |
| `backend/tests/test_read_service.py` | touch | service-level org filtering |
| `backend/tests/test_bootstrap_org.py` | create | `test_worker_startup.py` (module entrypoint invocation) |
| `backend/tests/test_provision_agent.py` | create | `test_worker_startup.py` — runs the CLI, asserts an `Agent` row with the given public key and org, prints the `agent_id`; rejects a bad-length hex key and a missing org |
| `backend/tests/test_settings.py` | touch | the two new optional fields (default present; override parses). **No required-key regression guard** — there is no required device key |
| `backend/tests/test_mailer.py` | touch | `send_invite_link` on `LogMailer` |
| `backend/tests/test_auth_wiring.py` | touch | assert the invites router is mounted and the four read routes carry `require_user` |

**No hardware-agent, `tui/`, or `scanner/` file is touched.** There is no `ScanRunner` or
`ScanProgressScreen` in scope.

## Constraints

- **Reuse, do not reimplement.** `accept_invite` calls `validate_policy` and `hash_password`
  from `services/passwords.py` (with `email=` supplied so the personal-data rule fires) and
  `issue_session` from `services/auth.py`. The route calls `login_response` from
  `routers/auth.py`. A second password rule, a second JWT mint, or a second `set_cookie` call in
  this feature is a review rejection.
- **Signature verification is Ed25519, not a byte compare.** The gate calls
  `device_sig.verify(agent.public_key, canonical, sig_hex)`, which delegates to
  `Ed25519PublicKey.verify` — constant-time comparison is intrinsic; there is no `==` and no
  `hmac.compare_digest` in the signature path. The **body-hash** check (`X-Body-SHA256` vs
  `sha256(body)`) still goes through `hmac.compare_digest` to avoid a timing side-channel on the
  hash.
- **The backend never holds a device private key.** It stores only `agents.public_key`, in the
  clear. There is no secret to encrypt, log, leak, or rotate. `device_sig.SignatureError`
  messages name the failure, not any key material.
- **`services/device_sig.py` is the only module that imports `cryptography`.** The gate, the
  provisioning CLI, and tests reach Ed25519 solely through its `sign` / `verify` /
  `generate_keypair` surface — no scattered `from cryptography...` imports.
- **No route mounts `require_agent`.** DMI-62 (WS upgrade) and DMI-63 (ingest) mount it. Adding
  an agent route here is out of scope.
- **The 8-step order exists exactly once**, in `authenticate_agent`. Adapters transport-map and
  status-map only — an adapter that re-checks skew, re-verifies a signature, or re-inserts a nonce
  is a review rejection. This is the whole reason for the split.
- **Contract reconciled.** The ADR-005 Ed25519 amendment updated
  `contracts/openapi/openapi.yaml` (`AgentSignatureAuth`, 128-hex `X-Signature`), and this feature
  added the three missing failure responses on `POST /api/v1/invites` (above). Field names, status
  codes, and header names come from the contract verbatim; **no further contract edit is part of
  the code work** — an implementer who finds themselves editing `openapi.yaml` has drifted from the
  spec and should stop.
- **`frontend/src/types/openapi.d.ts` is generated, never hand-edited.** It was regenerated during
  refinement; if any later contract change slips in, rerun `npm run gen:types` from `frontend/`
  rather than patching the `.d.ts`.
- **Scope fence** — no users/invites listing, revoking, or resending (DMI-76); no HTTP device
  provisioning endpoint and no self-service pairing (Phase 2); no device-key rotation flow; no
  on-device keypair generation (Pi-side, DMI-57/65); no real mail provider (DMI-71 — the
  `LogMailer` seam only); no C15 wire codes (DMI-77); no MFA, no logout-everywhere.
- **No new infrastructure and no new required secret.** The Ed25519 switch removes the
  `AGENT_SECRET_ENC_KEY` the retired ADR-015 design would have needed. `cryptography` is a
  library, and the nonce store is a Postgres table — nothing here requires a Railway variable,
  daemon, or service.
- **Style** — no comments or docstrings in new code, including tests. Reuse `get_session`,
  `utc_now`, `UTC_TIMESTAMP`, and the existing SQLModel / pydantic-settings patterns.

## Testing expectations

Every `TRUTH.md` acceptance row maps to at least one test below.

### `backend/tests/test_require_user.py` (touch — mirrors its own existing shape)

- *Anonymous is refused*, *Invalid token refused* — already covered by the existing four tests;
  leave them.
- *Viewer may not mutate* — `require_admin` on a throwaway route: `admin` token → `200`;
  `viewer` token → **`403`, asserted explicitly as not `401`**; no token → `401`.

### `backend/tests/test_read_endpoints.py` + `test_read_service.py` (touch)

- *Anonymous is refused* / *Invalid token refused*: each of the four routes without a bearer →
  `401`; with a garbage bearer → `401`.
- *Viewer may read* / *Admin may read*: both roles → `200` and the body contains only the seeded
  org-A records.
- *Cross-org read is invisible*: seed a host and a scan in org B; an org-A admin requesting them
  by id → **`404`** (assert the status is 404, not 403).
- *Cross-org list is filtered*: seed hosts + findings in orgs A and B; `GET /api/v1/hosts` and
  `GET /api/v1/findings` as org A return org-A rows only, and `total` reflects the filtered
  count (the count query must be scoped too — a scoped page with an unscoped total is the
  likely bug).
- A `NULL org_id` host/scan is returned to nobody — one explicit test, so the behaviour is
  pinned rather than accidental.
- *Cross-org read is invisible*, second form — **the host-detail sub-read**: seed an org-A host,
  then attach it to an org-B `ScanRecord` via a `ScanHostRecord` (the DB permits this today). An
  org-A caller fetching that host gets `200`, and its `scan_history` and `ports` are **empty** —
  org-B's scan never appears. Without the `ScanRecord.org_id` predicate this test fails while
  every other org test still passes, which is why it is called out separately.
- Service-level equivalents in `test_read_service.py` calling the four functions directly with
  two orgs, so the filtering is proven without the HTTP layer.

### `backend/tests/test_invite_routes.py` / `test_invite_service.py` (mirror `test_auth_routes.py` / `test_auth_service.py`)

- *Admin creates invite*: `POST /api/v1/invites` with an admin bearer → `201`, body has exactly
  `invite_token` and `expires_at`, `expires_at ≈ now + INVITE_TTL_HOURS`, and the stored
  `invites.token_hash` equals `sha256(invite_token)` while no column holds the raw token.
- *Viewer cannot invite*: viewer bearer → `403` and `select(Invite)` is still empty.
- No bearer → `401`.
- *Inviting an existing member fails fast*: pre-create a user in the admin's own org, `POST` an
  invite for that address → `400` and `select(Invite)` is still empty.
- *Inviting another org's user is not an oracle*: seed a second `Org` with a user, then `POST` an
  invite for that address as an org-A admin → **`201`**, byte-comparable to inviting a brand-new
  address. Assert the status and body shape match the fresh-address case; that equivalence *is* the
  no-oracle property. A global check at creation would return `400` here and fail this test.
- An `org_id` in the request body is rejected by `extra="forbid"` (`422`) — the admin cannot
  target another org.
- *Invite is org-bound* + *Acceptance signs in*: accept a fresh invite → `201` with a
  `LoginResponse` body **and** a `dmitri_refresh` `Set-Cookie` on the response; the returned
  access token then successfully calls `GET /api/v1/hosts`; the new `User` row has the invite's
  `org_id` and `role`.
- *Single use*: accept twice → second call `410`, and only one `User` exists.
- *Expired invite*: seed an invite with `expires_at` in the past → `410`.
- *Unknown token*: a random token → `410`.
- *Weak password at acceptance*: a short/patterned password → `400`, no `User` created,
  `invites.consumed_at` still `NULL`.
- *Breached password at acceptance*: **stub the HIBP call** exactly as `test_password_policy.py`
  does (monkeypatch the `httpx` call in `services/passwords.py`) — never a live network call →
  `400`, no `User`.
- *Duplicate email, same org*: pre-create a user with that email in the invite's org → rejected
  `400` and `consumed_at` still `NULL`.
- *Duplicate email, different org*: seed a second `Org`, pre-create a user with that email
  **there**, then accept an invite for the same address in the first org → still rejected `400`,
  `consumed_at` still `NULL`. This is the regression guard for the global-uniqueness rule; a
  scoped `.where(User.org_id == invite.org_id)` check would pass the previous case and fail this
  one.
- Body email ≠ invite email → `400`, invite unconsumed.

### `backend/tests/test_device_sig.py` (pure unit, no DB)

- `canonical_string` produces the exact six newline-joined fields in ADR-005 order — assert
  against a literal string, not a re-derivation.
- `generate_keypair` returns a 32-byte private seed and a 32-byte public key; `sign` then
  `verify` round-trips a canonical string with no error.
- `verify` raises `SignatureError` for: a signature made by a *different* private key; a
  canonical string mutated after signing; a hex sig that decodes to ≠ 64 bytes; non-hex garbage.
- `body_sha256(b"")` equals the literal
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` — asserted against the
  constant, not against a re-computation, so the value the Pi hardcodes is pinned by a test.
- Optionally assert one RFC 8032 Ed25519 test vector to pin the primitive.
- `parse_headers` raises `MalformedSigHeaders` for each missing header, a non-hex signature, a
  non-hex body hash, a non-UUID device id, and an out-of-range nonce length. A 64-hex (old HMAC
  width) signature is rejected — only 128-hex is valid.

### `backend/tests/test_nonces.py`

- First `remember_nonce` succeeds; the identical `(agent_id, nonce)` raises `NonceReplayError`.
- *Same nonce, different device*: the same nonce string for two different `agent_id`s both
  succeed.
- After a `NonceReplayError` the session is usable — a subsequent insert on the same session
  succeeds (proves the rollback).
- `prune_expired_nonces` deletes rows whose `expires_at < now` and leaves fresher rows.
- **The boundary case, pinned:** a row with `expires_at == now` **survives** the prune, because a
  request stamped `t` is still accepted at `now == t + skew`. Assert this explicitly — a `<=` here
  is a one-instant replay hole and no other test would catch it.

### `backend/tests/test_require_agent.py` (mirror `test_require_user.py`'s throwaway-app shape)

Mount `require_agent` on a local `FastAPI()` test app — **not** on a product route.

Drive the cases below through the **HTTP adapter**, so the `401`/`403` mapping is proven. Add two
tests that call `authenticate_agent` **directly**, with no app at all, to pin the core as the
reusable seam DMI-62 will build on:

- a valid request with `body=b""` and a hand-built `headers` dict resolves an `AgentIdentity` —
  this is the WS upgrade's exact shape (ADR-011 §2 empty-body hash), proven mountable before
  DMI-62 needs it.
- `expected_agent_id` matching passes; a mismatched one raises `AgentUnauthenticated` (ADR-011:55).

- *Valid signature passes*: the dependency returns the agent's `agent_id` and the `org_id` from
  the `agents` row.
- *Bad signature refused* → `401`. *Tampered body refused* (valid signature, mutated body so the
  `X-Body-SHA256` no longer matches) → `401`. *Unknown device refused* (random uuid) → `401`.
- Each of the five headers missing in turn → `401`.
- *Stale timestamp refused*: `now - 6 minutes` and `now + 6 minutes` → `401`; `now - 4 minutes`
  → passes (the window is symmetric).
- *Replay refused*: the byte-identical request sent twice → first `200`, second `401`.
- *Revoked device refused*: a perfectly valid signature from an agent with `revoked_at` set →
  **`403`, asserted as not `401`**.
- *Device cannot claim an org*: send a request whose body and headers assert a different
  `org_id`; the resolved `AgentIdentity.org_id` is the one on the `agents` row.

### `backend/tests/test_agent_nonce_migration.py` (mirror `test_command_migration.py`)

- Upgrade→downgrade round-trips clean; after upgrade `agent_nonces` exists with the five
  columns.
- Fence: `relrowsecurity = true`; `anon` and `authenticated` hold none of
  SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER; `dmitri_runtime` holds
  SELECT/INSERT/**DELETE** and **not** UPDATE/TRUNCATE/REFERENCES/TRIGGER.
- The unique constraint is on `(agent_id, nonce)`: a second insert of the same pair is rejected,
  and the same nonce under a different `agent_id` is accepted (the DB-level proof of the
  per-device rule).
- `expires_at` is indexed; `agent_id` FKs `agents.id`.

### `backend/tests/test_bootstrap_org.py`

- *Bootstrap creates an org*: run `main(["--org-name", "Acme", "--email", "a@acme.test"])`
  against the migrated test DB → exactly one `Org` and one `Invite` with `role="admin"` scoped
  to it; the printed token's sha256 equals the stored `token_hash`; accepting that token via
  `accept_invite` yields a working admin user in that org.
- *Running it twice is refused*: run `main` a second time with the same `--org-name` → returns
  `1`, writes to stderr, and **exactly one** `Org` and one `Invite` still exist. Assert the counts,
  not just the exit code — a command that returns `1` after already having inserted the row is the
  failure mode worth catching.
- The refusal is case- and whitespace-insensitive: after bootstrapping `"Acme"`, a run with
  `"  acme  "` is also refused. This is the case an exact-match check would let through.
- The refusal happens **before** any insert: no partially-created org, no orphan invite.
- `main` returns `0` on success and `1` on a bad argument, and the failure path writes to stderr
  without raising — assert the return value, not an exception.
- Both console-script names resolve: `backend-bootstrap-org` and `backend-provision-agent` appear
  in `[project.scripts]` and point at the two `main` callables. A cheap structural assertion, so a
  renamed module cannot silently orphan the documented command.

### `backend/tests/test_auth_wiring.py` (touch)

- `POST /api/v1/invites` and `POST /api/v1/invites/{token}/accept` are present on `app.routes`,
  with their `OPTIONS` preflights.
- The four read routes each have `require_user` in their dependency chain — a structural
  assertion, so a future route cannot silently ship unauthenticated.

### Quality gates

`uv run pytest` and `uv run ruff check` both pass over the touched backend scope
(`TRUTH.md` "Suite green").
