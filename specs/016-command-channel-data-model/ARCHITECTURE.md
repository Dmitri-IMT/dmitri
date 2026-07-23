# ARCHITECTURE — Command-channel data model + lifecycle state machine (DMI-59)

Implements the persistent foundation described in `TRUTH.md`. This is a **BACKEND** feature
(`backend/`). It touches no hardware-agent/scanner code and no TUI: there are no Textual screens
and no `ScanRunner` / `ScanProgressScreen` call sites, so the `.claude/CLAUDE.md` ScanRunner /
ScanProgressScreen integration rule is **N/A here**. Nothing needs new hardware, daemons, or
external tooling for this issue, so there is **no `HUMAN_INFRA_REQUIRED`** (the encryption key
env var and WS runtime that later issues need are out of scope for DMI-59).

## System context

Epic DMI-47 ("Command channel") lets an operator's "Scan now" drive a Raspberry Pi **Agent** over
an outbound WebSocket, receiving results via HMAC-signed ingest. That full pipeline is:

```
operator "Scan now"
  → enqueue Command (+ stub Scan)        [DMI-64, later]
  → deliver over agent WS                 [DMI-62, later]
  → Pi runs scan, uploads via HMAC ingest [DMI-63, later]
  → normalization (ScanPayload) → persistence → read API / UI
```

**DMI-59 lands only the shared schema and the single lifecycle rulebook that every later issue
builds on.** Concretely it adds two tables (`agents`, `commands`), their SQLModel definitions, and
a pure transition module. A **Command** is the audit record of one "Scan now"; it owns a lifecycle
and links to exactly one existing **Scan** (`ScanRecord` in `models/persistence.py`), whose status
is a pure projection of the Command status.

### What this issue deliberately does NOT do

- No endpoints, no WebSocket code, no delivery/enqueue logic.
- No HMAC encrypt/decrypt or verification logic — DMI-59 defines the encrypted-secret **columns**
  but writes/reads no secret (DMI-62/63 own that).
- No replay/nonce store — deferred to DMI-62.
- No `hosts` schema changes (the `devices`→`hosts` rename + `org_id` already landed).
- No renaming of the surviving read-path `devices` / `PersistedDevice` vocabulary — that belongs
  to the `persist_scan` rework in DMI-63.
- No enrichment/scoring model changes.
- No `online` column and no persistence code that sets it (online is derived from the WS registry).

## Data model / contracts

### Table `agents` (new — SQLModel in `backend/src/api/models/command.py`)

Mirrors `models/identity.py` style (`SQLModel, table=True`, `utc_now` default factory).

| Column | Type | Null | Notes |
|--------|------|------|-------|
| `id` | `UUID` (pk) | no | equals the Pi's `X-Device-Id`; minted by backend |
| `org_id` | `UUID` FK→`orgs.id` | no | tenancy, stored directly (no join needed); `index=True` |
| `display_name` | `str` | no | human-readable; the id is never shown |
| `secret_ciphertext` | `bytes` (`LargeBinary`) | no | AES-256-GCM ciphertext of the device secret (ADR-015) |
| `secret_nonce` | `bytes` (`LargeBinary`) | no | per-row random GCM nonce |
| `secret_key_version` | `int` | no | encryption-key tag for non-breaking key rotation |
| `revoked_at` | `datetime \| None` | yes | soft, timestamped tombstone; rejects future auth |
| `last_seen_at` | `datetime \| None` | yes | informational heartbeat (UI only); never an auth input; written by later issues |
| `created_at` | `datetime` | no | `default_factory=utc_now` |

No `secret_hash`, no plaintext `secret` column (ADR-015: HMAC needs a recoverable secret, so a
one-way hash is impossible; plaintext is forbidden). No `online` column.

### Table `commands` (new — same file)

| Column | Type | Null | Notes |
|--------|------|------|-------|
| `id` | `UUID` (pk) | no | command id |
| `org_id` | `UUID` FK→`orgs.id` | no | denormalized tenancy, direct; `index=True` |
| `agent_id` | `UUID` FK→`agents.id` | no | targets exactly one Agent; `index=True` |
| `scan_id` | `UUID` FK→`scans.scan_id` | **no (NOT NULL)** | one Command → exactly one Scan; **`UNIQUE`** (enforces the 1:1 invariant at the DB, doubles as the index) |
| `scan_mode` | `str` | no | request-of-record (also on the scan stub) |
| `subnet` | `str` | no | request-of-record (also on the scan stub) |
| `status` | `str` | no | `VARCHAR`/`AutoString`, NOT a Postgres ENUM, NO CHECK constraint — the transition function is the guard (matches `scans.status` / `enrichment_jobs.status` style) |
| `error_code` | `str \| None` | yes | nullable free-text; frozen `CommandDetail` types it `[string, null]`; NOT an enum. Distinct from the 409 `device_busy` / 503 `device_offline` HTTP trigger responses |
| `created_at` | `datetime` | no | = queued; `default_factory=utc_now` |
| `delivered_at` | `datetime \| None` | yes | set on `delivered` |
| `started_at` | `datetime \| None` | yes | = running |
| `completed_at` | `datetime \| None` | yes | = terminal (done/failed/expired) |

Exactly FOUR timestamps, matching the frozen `CommandDetail` schema. **Deliberately no
`uploading_at`** — the `uploading` transition happens but the contract exposes no column for it.

### Contract cross-check (FROZEN `contracts/openapi/openapi.yaml`)

- `CommandStatus` enum = `queued, delivered, running, uploading, done, failed, expired` → matches
  the `commands.status` value space.
- `ScanStatus` enum = `pending, accepted, processing, completed, failed` → the projection target.
- `CommandDetail` fields (`command_id, scan_id, agent_id, scan_mode, subnet, status, error_code,
  created_at, delivered_at, started_at, completed_at`) map 1:1 to the `commands` columns above.
- `CommandSummary` (`command_id, scan_id, agent_id, status`) is a subset — no new columns implied.

### Lifecycle module `backend/src/api/services/command_lifecycle.py` (new — PURE logic, no DB)

Legal edge table (source of truth):

| From | Allowed targets |
|------|-----------------|
| `queued` | `delivered`, `expired` |
| `delivered` | `running`, `expired` |
| `running` | `uploading`, `failed` |
| `uploading` | `done`, `failed` |
| `done` | — (terminal hard sink) |
| `failed` | — (terminal hard sink) |
| `expired` | — (terminal hard sink) |

Two separate pure functions plus one exception:

- `next_status(current: str, target: str) -> str` — returns `target` for a legal edge; raises
  `InvalidCommandTransition(current, target)` on an illegal edge. `target == current` is a
  **no-op success** (returns `current`) to absorb idempotent duplicate agent frames (ADR-011).
- `scan_status_for(command_status: str) -> str` — pure projection, no transition, so the read API
  can reuse it directly.
- `InvalidCommandTransition(current, target)` — small custom domain exception (NOT a bare
  `ValueError`) so callers can catch it specifically; message names current and target.

Kept as two separate functions on purpose: the projection must be reusable without a transition.

Scan-status projection mapping (`scan_status_for`):

| Command status | Scan status |
|----------------|-------------|
| `queued` | `pending` |
| `delivered` | `pending` |
| `running` | `accepted` |
| `uploading` | `processing` |
| `done` | `completed` |
| `failed` | `failed` |
| `expired` | `failed` |

### Migration `backend/alembic/versions/20260723_07_command_channel.py` (new)

- `revision = "20260723_07"`, `down_revision = "20260722_06"` (verified current head is
  `20260722_06_finding_uuid.py`).
- `upgrade()` creates `agents` then `commands` (agents first — `commands.agent_id` FK depends on
  it), then applies the security fence to BOTH tables exactly like `20260716_02_identity_schema.py`:
  `ENABLE ROW LEVEL SECURITY` per table; the guarded `REVOKE ALL PRIVILEGES … FROM anon` /
  `authenticated` (the `DO $$ … IF EXISTS pg_roles …` pattern); then
  `GRANT SELECT, INSERT, UPDATE … TO dmitri_runtime`. The `secret_ciphertext` column makes the
  fence mandatory.
- Binary columns use `sa.LargeBinary()`; string columns use
  `sqlmodel.sql.sqltypes.AutoString()`; uuid columns `sa.Uuid()`; timestamps `sa.DateTime()`.
- **Indexes:** `ix_agents_org_id` on `agents.org_id`; `ix_commands_org_id` on `commands.org_id`;
  `ix_commands_agent_id` on `commands.agent_id` (matching the `ix_scans_org_id` precedent). A
  **UNIQUE constraint on `commands.scan_id`** (`uq_commands_scan_id`) enforces the one-Command→one-Scan
  invariant and serves as that column's index — no separate `scan_id` index needed.
- `downgrade()` revokes the `dmitri_runtime` grants on both tables, then drops `commands` then
  `agents` (reverse FK order). No role create/drop (the runtime role is owned by the baseline).

## New files and naming (mandatory)

| Path (absolute-from-repo-root) | Kind | Action |
|--------------------------------|------|--------|
| `backend/src/api/models/command.py` | SQLModel models | create — `Agent` + `Command` table models |
| `backend/src/api/services/command_lifecycle.py` | pure logic | create — `next_status`, `scan_status_for`, `InvalidCommandTransition` |
| `backend/alembic/versions/20260723_07_command_channel.py` | migration | create — `agents` + `commands` with security fence |
| `backend/tests/test_command_migration.py` | test | create — mirrors `backend/tests/test_migrations.py` |
| `backend/tests/test_command_lifecycle.py` | test | create — transition + projection unit tests |

Touched (import only, no schema change): `backend/src/api/models/persistence.py` supplies
`utc_now` and the `scans`/`orgs` tables that `command.py` FKs target — no edits required unless the
model registry needs the new module imported for Alembic autogenerate/metadata (verify the model
import path used by `alembic/env.py` / the package `__init__` and add the import there if the two
new models are not otherwise loaded).

**No hardware-agent files, no `tui/` files, no `scanner/` files are touched.** There is no
`ScanRunner` or `ScanProgressScreen` in scope — the CLAUDE.md thread-through rule does not apply.

## Constraints

- **ADR-015 secret rule:** the agent secret is stored as AES-256-GCM ciphertext across three
  columns (`secret_ciphertext`, `secret_nonce`, `secret_key_version`). No plaintext column and no
  `secret_hash` — HMAC verification recomputes the MAC and needs a recoverable secret, so a
  one-way hash is cryptographically impossible.
- **Scope fence — "define columns, write no secret":** DMI-59 adds only the columns. Encrypt/
  decrypt, key loading, and HMAC verification are DMI-62/63; do not add any crypto code here.
- **Deferred nonce/replay store → DMI-62.** No nonce-tracking table in this issue.
- **No `hosts` schema changes** and **no read-path `devices` / `PersistedDevice` rename.**
- **`commands.status` is unconstrained VARCHAR** (no ENUM, no CHECK); the lifecycle function is the
  only guard, matching the existing `scans.status` / `enrichment_jobs.status` precedent.
- **Security fence mandatory on both new tables** (RLS + revoke anon/authenticated + grant
  `SELECT, INSERT, UPDATE` to `dmitri_runtime`), copied from `20260716_02_identity_schema.py`.

## Testing expectations

Mapped to the `TRUTH.md` acceptance criteria.

### `backend/tests/test_command_migration.py` (mirror `test_migrations.py` patterns)

- **Migration round-trips** (`_migrate(engine, "base")` → `"head"` → offline shape checks, using
  the `_table_shape` / monkeypatched-`op` style): up then down both succeed; after `up`, `agents`
  and `commands` exist; existing kept-engine queries against `hosts`/`scans` still work.
- **Fence privileges** (mirror `test_live_migration_round_trip_and_security` / `_has_privilege`):
  both new tables have `relrowsecurity = true`; `anon` and `authenticated` hold none of
  SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER; `dmitri_runtime` holds SELECT/INSERT/
  UPDATE and NOT DELETE/TRUNCATE/REFERENCES/TRIGGER.
- **Secret is not one-way / no plaintext** (AC "Secret is not one-way"): assert `agents` has
  `secret_ciphertext`, `secret_nonce`, `secret_key_version` and NO `secret` / `secret_hash` column.
- **Tenancy is direct:** assert `org_id` present on both `agents` and `commands`.
- **FK/shape:** `commands.scan_id` is NOT NULL and FKs `scans.scan_id`; `commands.agent_id` FKs
  `agents.id`; the four timestamps exist and there is no `uploading_at` column.
- **Indexes + uniqueness:** `agents.org_id`, `commands.org_id`, `commands.agent_id` are indexed;
  `commands.scan_id` carries a UNIQUE constraint (assert a second command inserted with an
  already-used `scan_id` is rejected, proving the 1:1 invariant).

### `backend/tests/test_command_lifecycle.py` (pure unit tests, no DB)

- **Every legal edge allowed:** each row of the edge table returns its target from `next_status`.
- **Every illegal edge rejected:** each non-listed `(current, target)` raises
  `InvalidCommandTransition` whose message names current and target.
- **Terminal is a hard sink:** `next_status("done", "running")` (and from `failed`, `expired`)
  raises.
- **Received-but-not-started expires:** `delivered → expired` legal; `delivered → failed` rejected.
- **Duplicate frame absorbed:** `next_status(s, s)` returns `s` for every status (no error).
- **Scan status tracks Command:** `scan_status_for` returns the fixed mapping for all seven command
  statuses and is a pure projection (no transition performed).

### Quality gates

`uv run pytest` and `uv run ruff check` both pass over the touched backend scope.
