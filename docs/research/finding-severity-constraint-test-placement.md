# Research: where the `findings.severity` CHECK-constraint tests belong

> **Scope.** Spec `specs/021-scan-list-and-finding-filters/` adds a named
> `CheckConstraint` on `findings.severity` (`low|medium|high|critical`) to
> `FindingRecord.__table_args__` (`backend/src/api/models/persistence.py:115-117`)
> plus one Alembic revision
> (`backend/alembic/versions/20260727_12_finding_severity_domain.py`, planned at
> `specs/021-scan-list-and-finding-filters/ARCHITECTURE.md:416`). Two acceptance
> criteria need a test home:
>
> - **AC 27** — the store refuses a finding written with an out-of-domain severity.
> - **AC 28** — an upgrade over a database with findings already recorded succeeds,
>   leaves them unchanged, and is reversible.
>
> ARCHITECTURE.md leaves both "pending — see Open item 6"
> (`specs/021-scan-list-and-finding-filters/ARCHITECTURE.md:551-552`) while the
> file table proposes `test_migrations.py` for AC 28
> (`ARCHITECTURE.md:417`) and `test_read_service.py` for the new read-path work
> (`ARCHITECTURE.md:420`). Primary source: the repo itself, read 2026-07-27.

---

## TL;DR verdict

- **AC 27 → a new file, `backend/tests/test_finding_severity_migration.py`.** The
  repo has an exact, one-to-one precedent: `test_invalid_role_is_rejected`
  (`backend/tests/test_identity_migration.py:168-179`) is a CHECK-constraint
  rejection test for `ck_users_role`, and it lives in the *migration* test file
  that introduced the constraint, not in the service test file. Every
  database-refuses-a-bad-write test in the suite lives in a migration test file.
  `test_read_service.py` has no such test today and is a pure read-path file.
- **AC 28 → the same new file.** `test_migrations.py` owns the *baseline* and
  whole-chain concerns; every subsequent revision gets its own
  `test_<slug>_migration.py`. Adding revision 12 to `test_migrations.py` breaks
  the convention seven files have followed.
- **One new file covers both**, matching how `test_users_email_unique_migration.py`
  and `test_agent_nonce_migration.py` each hold both the monkeypatched `op.*`
  assertions and the live constraint-rejection test.
- **No Postgres-skip hazard in CI.** `postgres_engine` does skip when
  `DATABASE_URL_TEST` is unset (`backend/tests/conftest.py:117-118`), but CI sets
  it (`.github/workflows/ci.yml:88`) *and fails the job if the suite reports any
  skips at all* (`.github/workflows/ci.yml:102-106`). A Postgres-only test cannot
  silently no-op in CI. It does silently skip on a local `uv run pytest` without
  the env var — documented behaviour (`backend/README.md:131`).
- **No precedent exists for row-level data survival across upgrade+downgrade.**
  The closest is a *column-metadata* survival check
  (`backend/tests/test_agents_public_key_migration.py:202-217`). AC 28's
  "every existing finding is unchanged" is new ground; say so and write it
  deliberately.
- **The spec's current proposal is wrong on both counts.** Say it plainly:
  `test_read_service.py` is the wrong home for AC 27, `test_migrations.py` is the
  wrong home for AC 28.

---

## Findings

### 1. The Postgres / SQLite split is not a two-way split — it is Postgres by default

**Postgres group** (uses `administrative_session`, `runtime_session`,
`migrated_database` or `postgres_engine` from `backend/tests/conftest.py`):

`test_agent_nonce_migration.py`, `test_agent_ws.py`, `test_agent_ws_channel.py`,
`test_agents_public_key_migration.py`, `test_auth_migration.py`,
`test_auth_routes.py`, `test_auth_service.py`, `test_bootstrap_org.py`,
`test_command_migration.py`, `test_error_envelope.py`, `test_health.py`,
`test_host_materialisation.py`, `test_identity_migration.py`,
`test_ingest_scan.py`, `test_invite_routes.py`, `test_invite_service.py`,
`test_migrations.py`, `test_nonces.py`, `test_provision_agent.py`,
`test_read_service.py`, `test_require_agent.py`, `test_require_agent_ws.py`,
`test_tokens.py`, `test_users_email_unique_migration.py`,
`test_worker_startup.py`.

**SQLite group** — only three files build an in-memory engine as an app fixture:

- `backend/tests/test_read_endpoints.py:27-36` — `create_engine("sqlite://", …StaticPool)` + `SQLModel.metadata.create_all(engine)`
- `backend/tests/test_error_envelope.py:40-49` — same shape
- `backend/tests/test_users_routes.py:29-38` — same shape

Two more files mention `sqlite://` but only as a *rejected URL* string, not an
engine for app data: `backend/tests/test_db_session.py:45,67,120` and
`backend/tests/test_settings.py:51,223,271` (both assert the app refuses
non-Postgres `DATABASE_URL`s; the `create_engine("sqlite://")` at
`test_db_session.py:120` and `test_settings.py:271` are for engine-option
assertions, not schema).

The important correction to the spec's framing: **`test_read_service.py` is a
Postgres file**, not a SQLite one — every test takes `administrative_session`
(e.g. `backend/tests/test_read_service.py:117-118, 135-136`). So putting AC 27
there would *run*; it is simply in the wrong topical home. `test_error_envelope.py`
is a hybrid: a SQLite `session`/`client` pair (`:40-58`) plus a `postgres_client`
built on `administrative_session` (`backend/tests/test_error_envelope.py:95-97`).

### 2. Does the Postgres fixture actually run? Yes in CI, no locally by default

`backend/tests/conftest.py:23`:

```python
DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST")
```

`backend/tests/conftest.py:115-118`:

```python
@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    if DATABASE_URL_TEST is None:
        pytest.skip("DATABASE_URL_TEST not set")
```

`administrative_session` and `runtime_session` both depend on
`migrated_database` → `postgres_engine` (`conftest.py:150-179`), so the skip
propagates to every Postgres test.

The fixture is destructive and guarded: it refuses any database not literally
named `dmitri_test` (`conftest.py:44, 55-60`), creates the `anon`/`authenticated`
roles if missing (`conftest.py:131-134`), runs `alembic upgrade head`
(`conftest.py:137`), and on teardown truncates and downgrades to `base`
(`conftest.py:140-141`).

**CI behaviour.** `.github/workflows/ci.yml:74-88` stands up a `postgres:17`
service and exports
`DATABASE_URL_TEST: postgresql+psycopg://postgres:postgres@localhost:5432/dmitri_test`.
Then `.github/workflows/ci.yml:100-106`:

```yaml
uv run pytest -ra | tee pytest-output.log
if grep -qE '[0-9]+ skipped' pytest-output.log; then
  echo "::error::Database-test skips detected; CI requires a zero-skip backend suite."
  exit 1
fi
```

A zero-skip policy is enforced. **A Postgres-only test therefore cannot silently
no-op in CI** — that is the decisive fact, and it removes the main argument for
forcing AC 27 into a SQLite fixture.

**Local behaviour.** Without the env var the DB tests skip, which
`backend/README.md:131` states explicitly ("Sem `DATABASE_URL_TEST` definida, os
testes que tocam banco pulam"), with the run command at
`backend/README.md:137`. So a developer running a bare `uv run pytest` will not
exercise AC 27/28 locally. This is pre-existing and applies equally to all 25
Postgres files; it is not a reason to deviate.

### 3. Where "the database rejects a bad write" is tested today

Every such test lives in a **migration** test file, uses a **Postgres session**
fixture, and follows the `pytest.raises(sa.exc.IntegrityError)` around
`session.commit()` + `session.rollback()` shape:

| Test | File:line | Constraint kind |
|---|---|---|
| `test_invalid_role_is_rejected` | `backend/tests/test_identity_migration.py:168-179` | **CHECK** (`ck_users_role`) |
| `test_duplicate_email_per_org_is_rejected_case_insensitive` | `test_identity_migration.py:141-165` | unique index |
| `test_invite_token_is_single_use_unique` | `test_identity_migration.py:183-200` | unique |
| `test_refresh_token_hash_is_unique` | `test_auth_migration.py:123-146` | unique |
| `test_refresh_token_rejects_unknown_user` | `test_auth_migration.py:149-162` | FK |
| `test_password_reset_token_hash_is_unique` | `test_auth_migration.py:165-188` | unique |
| `test_password_reset_token_rejects_unknown_user` | `test_auth_migration.py:191-203` | FK |
| `test_live_cross_org_duplicate_email_is_rejected` | `test_users_email_unique_migration.py:146-177` | unique index |
| `test_live_case_insensitive_duplicate_email_is_rejected` | `test_users_email_unique_migration.py:180-208` | unique index |
| `test_live_unique_constraint_per_agent` | `test_agent_nonce_migration.py:174-215` | unique (try/except form) |
| `test_live_commands_scan_id_unique_constraint` | `test_command_migration.py:210-263` | unique (try/except form) |

`test_identity_migration.py:168-179` is the template AC 27 should copy almost
verbatim — it is the repo's only existing CHECK-constraint rejection test, and
the constraint it guards (`sa.CheckConstraint("role IN ('admin','viewer')",
name="ck_users_role")`, created inline at
`backend/alembic/versions/20260716_02_identity_schema.py:54`) is the direct
analogue of the new severity domain.

**Write-path files, for contrast.** `backend/tests/test_ingest_scan.py:85-90` and
`backend/tests/test_host_materialisation.py:28-29` both take `runtime_session`
(Postgres, restricted role) and assert *persistence behaviour* — what
`persist_scan` writes — never that the DB refuses something.
`backend/tests/test_hosts_identity_key.py` is a pure-function unit file with no DB
at all (`test_hosts_identity_key.py:1-8`). None of the three is a home for a
constraint-rejection test.

### 4. `test_migrations.py` vs the seven per-revision files

**Naming pattern.** `test_<migration-slug>_migration.py`, one per revision (or per
tightly-coupled group):

| File | Revision(s) | Live Postgres? |
|---|---|---|
| `test_identity_migration.py` | `20260716_02_identity_schema` | yes — constraint tests only, via `administrative_session` |
| `test_auth_migration.py` | auth/session tables | yes — constraint tests only |
| `test_command_migration.py` | `20260722_06`→ commands | yes — `_migrate` round trip (`:152-171`) + unique test (`:210`) |
| `test_host_identity_migration.py` | `20260722_03`–`06` group | **no** — monkeypatched `op.*` only |
| `test_agent_nonce_migration.py` | `20260724_09` | yes — round trip (`:120-137`) + unique test (`:174`) |
| `test_agents_public_key_migration.py` | `20260724_11` | yes — round trip (`:98-186`) + column survival (`:202-217`) |
| `test_users_email_unique_migration.py` | `20260724_10` | yes — index round trip (`:100-123`) + rejection tests |

**Standard structure**, present in essentially all of them:

1. An `importlib.util.spec_from_file_location` loader that imports the revision
   file by path — `_load_migration()` at
   `test_agents_public_key_migration.py:13-22`,
   `test_users_email_unique_migration.py:16`, `test_agent_nonce_migration.py:19`,
   `test_command_migration.py:20`, and `_load_baseline()` at
   `test_migrations.py:62-69`.
2. A revision-chain test — `test_migration_revision_chain` asserting `revision`
   and `down_revision` (`test_agents_public_key_migration.py:25-28`,
   `test_users_email_unique_migration.py:28`, `test_agent_nonce_migration.py:29`).
3. Monkeypatched `op.*` assertions: replace `op.create_table` / `op.create_index`
   / `op.drop_column` / `op.execute` with recorders and call `upgrade()` /
   `downgrade()` (`test_agents_public_key_migration.py:31-95`,
   `test_migrations.py:207-217`, `test_identity_migration.py:29-69`).
4. Live `_migrate(engine, "<rev>")` round trips against Postgres, imported from
   `conftest` (`test_agent_nonce_migration.py:120-137`,
   `test_users_email_unique_migration.py:100-123`,
   `test_agents_public_key_migration.py:150-186`), always ending back at `head`.

**What `test_migrations.py` owns**, and only this: the Alembic *environment* URL
normalisation and redaction (`test_migrations.py:134-173`), the alembic.ini /
pyproject configuration assertions (`:176-195`), the **baseline** revision's shape
vs model metadata and the RLS/grant security fence (`:198-341`), the destructive
test-database guard (`:363-381`), the whole-chain live round trip base→head with
privilege, RLS, and timestamptz drift checks (`:405-568`), the pre-existing-role
failure path (`:571-588`), and the runtime-role privilege fence (`:600-642`). It
is baseline + chain-wide invariants. **It contains nothing revision-specific after
the baseline.** Adding revision 12's upgrade/downgrade there contradicts seven
files of precedent.

**Data survival across upgrade+downgrade: no precedent.** The closest thing is
`test_live_upgrade_leaves_other_agent_columns_unchanged`
(`test_agents_public_key_migration.py:202-217`), which snapshots
`information_schema.columns` for four untouched `agents` columns before and after
the upgrade and asserts equality — **schema** survival, not **row** survival. No
test in the suite seeds application rows, runs an upgrade, and asserts the rows
are byte-identical afterwards. `test_migrations.py:405-568` round-trips base→head
against an empty database. AC 28's "every existing finding is unchanged" is
therefore genuinely new coverage; it should be written explicitly rather than
described as "mirroring the existing migration tests"
(`ARCHITECTURE.md:417`).

**Mechanical caveat for AC 28.** `postgres_engine` is session-scoped, so any test
that calls `_migrate` must return the database to `head` before it ends — every
existing live test does (`test_agents_public_key_migration.py:170,212`;
`test_agent_nonce_migration.py:136`; `test_users_email_unique_migration.py:122`).
Also, downgrading to `base` **drops the tables** (`conftest.py:79-80`), so AC 28
must step down exactly one revision (`_migrate(engine, "20260724_11")`), seed
findings there, upgrade to `head`, compare, downgrade to `20260724_11` again to
prove reversibility, then return to `head`. Going to `base` would destroy the very
rows the AC is about.

### 5. SQLite will enforce the new constraint — and no fixture violates it

SQLite has enforced `CHECK` constraints since 3.3.0 and does so by default; the
Python `sqlite3` module ships a modern build, so the three
`SQLModel.metadata.create_all(engine)` fixtures
(`test_read_endpoints.py:27-36`, `test_error_envelope.py:40-49`,
`test_users_routes.py:29-38`) will emit and enforce the constraint. There is no
`PRAGMA ignore_check_constraints` anywhere in the tree.

**Audit of every `severity=` assignment in `backend/tests/`:**

| Site | Value | Column | Verdict |
|---|---|---|---|
| `test_read_service.py:92` | `"high"` | `FindingRecord.severity` | in domain |
| `test_read_endpoints.py:120` | `"high"` | `FindingRecord.severity` | in domain |
| `test_read_endpoints.py:164` | `"low"` | `FindingRecord.severity` | in domain |
| `test_read_endpoints.py:220` | `"low"` | `FindingRecord.severity` | in domain |
| `test_error_envelope.py:77` | `"none"` | `HostRecord.highest_severity` | **not** the constrained column — safe *only* because the constraint is scoped to `findings.severity` |
| `test_read_service.py:38`, `test_read_endpoints.py:82,138,194` | `None`/`"high"`/`"low"` | `HostRecord.highest_severity` | unconstrained column |

**Nothing breaks** — but note the trap: `highest_severity="none"`
(`test_error_envelope.py:77`) is an out-of-domain string sitting in the test tree
today. If the constraint is ever widened to `hosts.highest_severity`, that fixture
fails immediately. Keep the constraint on `findings.severity` only, as
`ARCHITECTURE.md:415` specifies.

Consequence for AC 27: because SQLite *would* enforce it, an AC 27 test could
technically be written against a SQLite fixture and would pass locally without
Postgres. **Do not do this.** It would test SQLite's CHECK implementation, not the
production database's, it has zero precedent in the suite (all 11 rejection tests
above are Postgres), and item 2 shows the Postgres path is not actually at risk of
silently skipping in CI.

---

## Recommendation

**Create one new file: `backend/tests/test_finding_severity_migration.py`.**

The name follows `test_<migration-slug>_migration.py`, matching
`test_agents_public_key_migration.py` (for
`20260724_11_agents_public_key.py`) and `test_users_email_unique_migration.py`.

It should contain, in the established order:

1. `_load_migration()` — importlib loader for
   `alembic/versions/20260727_12_finding_severity_domain.py`, copied from
   `test_agents_public_key_migration.py:13-22`.
2. `test_migration_revision_chain()` — `revision == "20260727_12"`,
   `down_revision == "20260724_11"`. Pattern:
   `test_agents_public_key_migration.py:25-28`.
3. Monkeypatched `op.create_check_constraint` / `op.drop_constraint` assertions
   for `upgrade()` and `downgrade()`, verifying the constraint **name matches
   between the two** and matches the model's
   (`persistence.py:115-117`). Pattern:
   `test_agents_public_key_migration.py:31-95`.
4. **AC 27** — `test_live_out_of_domain_severity_is_rejected(administrative_session)`:
   build a `FindingRecord` with `severity="urgent"`, `pytest.raises(sa.exc.IntegrityError)`
   around `.commit()`, then `.rollback()`. Copy
   `test_identity_migration.py:168-179` line for line.
5. **AC 28** — `test_live_upgrade_preserves_existing_findings(migrated_database)`:
   `_migrate(engine, "20260724_11")` → seed valid findings → snapshot rows →
   `_migrate(engine, "head")` → assert rows identical and the constraint exists in
   `information_schema` → `_migrate(engine, "20260724_11")` → assert the constraint
   is gone and rows still identical → `_migrate(engine, "head")` to restore.
   Structurally closest to `test_agents_public_key_migration.py:202-217`, extended
   from column metadata to row data.

**Do not** put AC 27 in `backend/tests/test_read_service.py`. That file is
read-path only — 100% `read.list_hosts` / `read.list_findings` behaviour
(`test_read_service.py:105-262`) — and contains no write-rejection test. Its
`_make_finding` helper (`test_read_service.py:81-102`) exists to seed valid data,
not to probe constraints. The spec's `ARCHITECTURE.md:420` correctly assigns the
new *filter* cases (AC 12–20, 25–26) to that file; AC 27 does not belong with them.

**Do not** put AC 28 in `backend/tests/test_migrations.py`, contrary to
`ARCHITECTURE.md:417`. That file owns the baseline and chain-wide invariants
(item 4); every post-baseline revision has its own file. The one thing that *may*
touch `test_migrations.py` is incidental: `HEAD_APPLICATION_TABLES` and
`_table_shape` (`test_migrations.py:30, 91-122`) compare baseline vs model shapes
and only look at columns, FKs, unique constraints and indexes — `CheckConstraint`
is not in `TableShape`, so the new constraint is invisible there and no update is
required.

**Caveats that could change this.**

- If the zero-skip CI gate (`.github/workflows/ci.yml:102-106`) were ever removed
  *and* CI stopped provisioning Postgres, both tests would become dead weight
  outside a manual run. As of today that gate is in force, so Postgres is the
  right substrate.
- Local developers running a bare `uv run pytest` will skip both tests
  (`conftest.py:117-118`, `backend/README.md:131`). If the team wants AC 27
  verified on every local run regardless, the only zero-skip option is a SQLite
  `metadata.create_all` assertion — but that tests SQLite, has no precedent, and
  is not recommended.
- AC 28's guard interacts with the migration's own precondition check: the
  migration is specified to fail loudly if out-of-domain rows exist
  (`ARCHITECTURE.md:416`). That failure path deserves its own test in the same
  file — seed a bad row at `20260724_11`, attempt the upgrade, assert it raises
  with a message naming the offending value — otherwise the guard is untested.
