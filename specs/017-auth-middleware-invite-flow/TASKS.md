# Tasks — Auth middleware + invite flow (`017-auth-middleware-invite-flow`)

15 tasks. **Unblocked now: #1, #2, #5, #7, #8, #10, #13**

Backend-only feature (`backend/src/api/…`). No `scanner/` or `tui/` code is touched, so the
`.claude/CLAUDE.md` `ScanRunner` / `ScanProgressScreen` thread-through rule is N/A here.
Order: config → models/migrations → pure logic → gates → services → routers → CLI.

---

## Task 1: Settings fields for skew and invite TTL
- **Description**: Add the two optional `Settings` fields from the ARCHITECTURE.md "`Settings` additions" table (`device_sig_max_skew_seconds` / `DEVICE_SIG_MAX_SKEW_SECONDS` default `300`; `invite_ttl_hours` / `INVITE_TTL_HOURS` default `48`) and document them in `.env.example` with their defaults. No `field_validator`, no required secret, and deliberately no nonce-retention knob. Also add the `seeded_org` and `bearer_headers` conftest fixtures described in the ARCHITECTURE.md Tests table.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/core/config.py`, `backend/.env.example`, `backend/tests/conftest.py`, `backend/tests/test_settings.py`]
- **Success Criteria**: both fields present with the stated defaults and env aliases; overrides parse from env; no `AGENT_SECRET_ENC_KEY` and no `AGENT_NONCE_RETENTION_SECONDS` anywhere; `bearer_headers(org_id, role)` returns a `Bearer` header built with the existing `create_access_token`; `seeded_org` returns a committed `Org`; `test_settings.py` covers default-present and override-parses for both fields with no required-key guard; `uv run pytest backend/tests/test_settings.py` and `uv run ruff check` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: `agent_nonces` model + migration
- **Description**: Add the `AgentNonce` SQLModel table to `models/command.py` (beside `Agent`, so no `models/__init__.py` or `alembic/env.py` edit is needed) per the ARCHITECTURE.md column table, with `UniqueConstraint("agent_id", "nonce", name="uq_agent_nonces_agent_id_nonce")` and `ix_agent_nonces_expires_at` — and **no** separate `agent_id` index. Write migration `20260724_09` creating the table plus the same security fence `20260723_07_command_channel.py` applies, granting `dmitri_runtime` exactly `SELECT, INSERT, DELETE`.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/command.py`, `backend/alembic/versions/20260724_09_agent_nonces.py`, `backend/tests/test_agent_nonce_migration.py`]
- **Success Criteria**: `revision = "20260724_09"`, `down_revision = "20260724_08"`; upgrade→downgrade round-trips clean; after upgrade the table has the five columns with house-style types (`sa.Uuid()`, `AutoString()`, `sa.DateTime(timezone=True)`); `relrowsecurity = true`; `anon`/`authenticated` hold no privileges; `dmitri_runtime` holds SELECT/INSERT/DELETE and **not** UPDATE/TRUNCATE/REFERENCES/TRIGGER; a duplicate `(agent_id, nonce)` insert is rejected while the same nonce under a different `agent_id` is accepted; `expires_at` is indexed and `agent_id` FKs `agents.id`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2.5: Fix the `_migrate` round-trip test helper
- **Description**: Pre-existing defect found during the Task 2 review, not introduced by this feature. `_migrate(engine, revision)` in `backend/tests/conftest.py:70` only ever calls `command.upgrade()` for a non-`"base"` target, so asking it to step **back** to an earlier revision is a silent no-op — every live "upgrade→downgrade round-trips clean" test then asserts against an unchanged database and fails. Make `_migrate` compare the requested revision against the database's current revision and call `command.downgrade()` when the target is behind it, keeping the existing `"base"` branch and the existing post-migration `GRANT dmitri_runtime` block unchanged. Test-infrastructure only — no `backend/src` change, no new test file.
- **Dependencies**: Task 2
- **Target Files**: [`backend/tests/conftest.py`]
- **Success Criteria**: `_migrate` downgrades when the target revision is behind the current head and still upgrades when it is ahead; the three live round-trip tests that fail on this defect pass with `DATABASE_URL_TEST` set (`test_agent_nonce_migration.py::test_live_migration_round_trip`, `test_command_migration.py::test_live_migration_round_trip_and_kept_engine_queries`, and the third instance the Task 2 reviewer identified); no other test file is edited; no test is deleted, skipped, or weakened to achieve the pass; the whole suite is no worse than before (`291 passed, 3 failed` was the pre-fix live baseline); `uv run ruff check` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2.6: Teach `test_migrations.py` the `agent_nonces` grant set
- **Description**: Regression introduced by Task 2 and missed by its review, confirmed independently by the Task 2.5 test engineer and reviewer: `test_migrations.py::test_live_migration_round_trip_and_security` asserts via a blanket privilege loop that **every** application table grants `dmitri_runtime` `SELECT/INSERT/UPDATE`, but Task 2's `agent_nonces` fence deliberately grants `SELECT/INSERT/DELETE` and withholds `UPDATE`. The test passes on a clean `main` and fails with `agent_nonces` present. Teach that loop the per-table expected grant set rather than relaxing the assertion — `agent_nonces` must still be asserted to hold exactly SELECT/INSERT/DELETE and to **lack** UPDATE, and every other table must keep the privilege expectation it has today. Test-only change; the `20260724_09` migration and the `AgentNonce` model are correct and must not be touched.
- **Dependencies**: Task 2, Task 2.5
- **Target Files**: [`backend/tests/test_migrations.py`]
- **Success Criteria**: `test_live_migration_round_trip_and_security` passes with `DATABASE_URL_TEST` set; the live suite reaches `294 passed, 0 failed` from the `293 passed, 1 failed` post-2.5 baseline; the assertion is made table-aware, **not** weakened, deleted, skipped, or xfailed — `agent_nonces` is still positively asserted to hold SELECT/INSERT/DELETE and to lack UPDATE/TRUNCATE/REFERENCES/TRIGGER, and no other table's expectation is loosened; no file outside `backend/tests/test_migrations.py` is edited; `uv run ruff check` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Global `users` email uniqueness
- **Description**: Per ARCHITECTURE.md "`users` email uniqueness becomes global": replace `Index("ix_users_org_email", "org_id", text("lower(email)"), unique=True)` in `User.__table_args__` with `Index("ix_users_email", text("lower(email)"), unique=True)`, and write migration `20260724_10` dropping the old index and creating the new one, with an exact-inverse downgrade. Unconditional, unguarded — a genuine cross-org duplicate must fail loudly. `ck_users_role` unchanged; no `org_id` index is added (that is DMI-76's).
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/models/identity.py`, `backend/alembic/versions/20260724_10_users_email_global_unique.py`, `backend/tests/test_users_email_unique_migration.py`]
- **Success Criteria**: `revision = "20260724_10"`, `down_revision = "20260724_09"`; after upgrade `ix_users_org_email` is gone and `ix_users_email` exists and is unique; two users with the same email in **different** orgs are rejected at the database level; upgrade→downgrade round-trips clean and restores `ix_users_org_email` as `20260716_02_identity_schema.py` declared it.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: `agents` secret columns → `public_key`
- **Description**: Per ARCHITECTURE.md "`agents` secret columns → `public_key`": drop `secret_ciphertext` / `secret_nonce` / `secret_key_version` from `Agent` and add `public_key: bytes = Field(sa_type=LargeBinary)` (32 raw Ed25519 bytes, stored in the clear). Migration `20260724_11` drops the three columns and adds `public_key` `LargeBinary` NOT NULL (table is empty, no server default); `downgrade()` re-adds the three columns exactly as `20260723_07_command_channel.py` declared them and documents that it is knowingly lossy if rows exist. The `agents` security fence is untouched.
- **Dependencies**: Task 3
- **Target Files**: [`backend/src/api/models/command.py`, `backend/alembic/versions/20260724_11_agents_public_key.py`, `backend/tests/test_agents_public_key_migration.py`]
- **Success Criteria**: `revision = "20260724_11"`, `down_revision = "20260724_10"`; after upgrade the three secret columns are gone and `public_key` exists NOT NULL; `revoked_at` / `last_seen_at` / `org_id` / `display_name` unchanged; the `agents` RLS + `dmitri_runtime` grants still hold; upgrade→downgrade round-trips clean; no module in `backend/src` references the removed columns.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: `services/device_sig.py` — Ed25519 primitives
- **Description**: Create the pure, DB-free signature module per the ARCHITECTURE.md naming table: `canonical_string`, `body_sha256`, `parse_timestamp`, `DeviceSigHeaders` (frozen dataclass), `parse_headers` raising `MalformedSigHeaders`, `verify(public_key, canonical, signature_hex)` raising `SignatureError`, plus `generate_keypair()` and `sign()` for tests/CLI. Canonical string is exactly `METHOD\nPATH\nX-Device-Id\nX-Timestamp\nX-Nonce\nX-Body-SHA256` (ADR-005 §1). Add `cryptography>=42.0` to `backend/pyproject.toml`; this is the **only** module that imports `cryptography`.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/device_sig.py`, `backend/pyproject.toml`, `backend/tests/test_device_sig.py`]
- **Success Criteria**: `canonical_string` asserted byte-exact against a literal six-field string; `sign` → `verify` round-trips; `verify` raises `SignatureError` for a wrong key, a mutated canonical string, a hex sig decoding to ≠ 64 bytes, and non-hex garbage — never `InvalidSignature` or a 500-shaped error; `generate_keypair` returns 32-byte private and public bytes; `body_sha256(b"")` asserted against the literal `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `parse_headers` raises `MalformedSigHeaders` for each missing header, non-hex signature, non-hex body hash, non-UUID device id, out-of-range nonce length, and a 64-hex (old HMAC width) signature; no `cryptography` import outside this module; error messages name the failure, not key material.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: `services/nonces.py` — insert-or-replay + prune
- **Description**: Create `remember_nonce(session, *, agent_id, nonce, expires_at)` raising `NonceReplayError(ValueError)` and `prune_expired_nonces(session, *, now)` per ARCHITECTURE.md. Replay detection is the INSERT plus the unique constraint (never SELECT-then-INSERT); on `IntegrityError` the function must `session.rollback()` before raising. Pruning is one indexed `DELETE … WHERE expires_at < :now` with a **strict** `<`.
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/services/nonces.py`, `backend/tests/test_nonces.py`]
- **Success Criteria**: first `remember_nonce` succeeds and an identical `(agent_id, nonce)` raises `NonceReplayError`; the same nonce string for two different `agent_id`s both succeed; after a `NonceReplayError` a subsequent insert on the same session succeeds (proves the rollback); `prune_expired_nonces` deletes rows with `expires_at < now` and leaves fresher rows; a row with `expires_at == now` **survives** the prune, asserted explicitly; `remember_nonce` takes `expires_at` and derives nothing itself.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6.5: Fix the `postgres_engine` teardown-ordering flake
- **Description**: Pre-existing test-infrastructure defect, hit three separate times across this feature (Task 4 test engineer, Task 6 coder, Task 6 reviewer) in an identical shape. The session-scoped `postgres_engine` fixture in `backend/tests/conftest.py` downgrades to `base` at teardown, but `_truncate_application_tables` only runs at the **start** of each test, so rows left by the final test in a run are still present when the downgrade tries to re-add `agents.secret_ciphertext` NOT NULL — which fails, leaving the live `dmitri_test` schema mid-downgrade and requiring a manual `alembic upgrade head` before anything else can run. Fix the ordering so the teardown downgrade runs against empty tables. Test-infrastructure only — no `backend/src` change, no production behavior change.
- **Dependencies**: Task 2.5, Task 6
- **Target Files**: [`backend/tests/conftest.py`]
- **Success Criteria**: *(corrected during review — the original wording "leaves the database at head" was wrong: `postgres_engine`'s pre-existing `finally: _migrate(engine, "base")` deliberately leaves the database at **base** after a live run, by design and predating this task)* the full live suite runs twice back-to-back with **no manual `alembic upgrade head` repair between runs**, and the schema is never left in the silently-unrepairable half-downgraded state where `alembic_version` reads head while the schema is missing a head-required column; the previously flaky `agents.secret_ciphertext` NOT NULL downgrade failure does not reproduce, including when the offending test is last in the run; the existing per-test truncate behavior and the `"base"` / downgrade logic added by Task 2.5 both still work; no test is deleted, skipped, xfailed, or weakened, and no test file other than `backend/tests/conftest.py` is edited; live count is no worse than the `340 passed, 0 failed` baseline; `uv run ruff check` passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: `require_admin` role gate
- **Description**: Add `ROLE_ADMIN = "admin"`, `ROLE_VIEWER = "viewer"`, and `def require_admin(caller: CallerIdentity = Depends(require_user)) -> CallerIdentity` raising `HTTPException(403)` to `dependencies/auth.py` per the ARCHITECTURE.md Touched table. `require_user` and `CallerIdentity` are unchanged. Extend `test_require_user.py` with the `require_admin` cases from Testing expectations.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/dependencies/auth.py`, `backend/tests/test_require_user.py`]
- **Success Criteria**: on a throwaway route an `admin` token → `200`, a `viewer` token → **`403` asserted as not `401`**, no token → `401`; the existing four `require_user` tests still pass untouched; `require_admin` reuses `require_user` rather than re-decoding the token.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Shared session-issuing, cookie, and mailer seams
- **Description**: Per the ARCHITECTURE.md Touched table: extract `issue_session(session, *, user) -> tuple[str, str, int]` from `services/auth.py::login` and call it from `login` and `refresh_session`; in `routers/auth.py` rename `_set_refresh_cookie`/`_clear_refresh_cookie` to `set_refresh_cookie`/`clear_refresh_cookie` (updating the three internal call sites) and add `login_response(response, access_token, refresh_token, expires_in) -> LoginResponse`, used by `login_route` and `refresh_route`. Add `send_invite_link(self, email: str, token: str) -> None` to the `Mailer` protocol and `LogMailer` — raw token, never a URL, and no base-URL setting.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/auth.py`, `backend/src/api/routers/auth.py`, `backend/src/api/services/mailer.py`, `backend/tests/test_mailer.py`]
- **Success Criteria**: existing `test_auth_service.py` / `test_auth_routes.py` pass unchanged; *(**amended during review — the original criterion and description were a spec defect.** They required `refresh_session` to call `issue_session`. It must not: `issue_session` calls `issue_refresh_token`, minting a new token in a **new** `family_id`, whereas `refresh_session` must call `rotate_refresh_token` to stay in the **same** family. The Task 8 test engineer reproduced the harm empirically — routing refresh through `issue_session` orphans a `RefreshToken` row in an unlinked family and leaves the original token's `rotated_at`/`revoked_at` NULL, so the original stays valid and reuse detection never fires.)* fresh-session issuance from a `User` exists in exactly one place (`issue_session`, used by `login` and later by `accept_invite`), while `refresh_session` keeps its own rotation path; the ~3 duplicated lines of access-token construction between the two are accepted under the CLAUDE.md "no abstractions for single-use code" rule; cookie-setting exists in exactly one place (`set_refresh_cookie`, reached via `login_response`); `LogMailer.send_invite_link` logs the token and is covered by a test; no `INVITE_LINK_BASE_URL` and no reuse of `cors_allowed_origins`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Device gate — `authenticate_agent` core + `require_agent` adapter
- **Description**: Create `dependencies/agent_auth.py` per the ARCHITECTURE.md naming table: `AgentIdentity`, `AgentAuthError` with `AgentUnauthenticated` (401) and `AgentRevoked` (403), the transport-agnostic core `authenticate_agent(session, *, method, path, headers, body, now, expected_agent_id=None)` holding the 8-step order exactly once, and the thin `async def require_agent(request, session)` adapter that awaits the body and maps errors to `HTTPException`. `path` is `request.url.path` (resolved, never a route template). No FastAPI import in the core; `require_agent_ws` is **not** written here. Mount on **no** product route. Add the `agent_keypair` / `provisioned_agent` conftest fixtures.
- **Dependencies**: Task 1, Task 4, Task 5, Task 6
- **Target Files**: [`backend/src/api/dependencies/agent_auth.py`, `backend/tests/conftest.py`, `backend/tests/test_require_agent.py`]
- **Success Criteria**: steps run in the ARCHITECTURE.md order with its exact statuses — missing/malformed header, unknown device, skew > `DEVICE_SIG_MAX_SKEW_SECONDS`, body-hash mismatch, bad/short signature and replay all `401`; a known agent with `revoked_at` set → **`403` asserted as not `401`**; `expected_agent_id` mismatch → `AgentUnauthenticated`; nonce is recorded only **after** the signature verifies, with `prune_expired_nonces` then `remember_nonce(expires_at=timestamp + skew)`; body hash compared via `hmac.compare_digest`, signature via `device_sig.verify` with no `==`; `AgentIdentity.org_id` always read from the `agents` row even when the request asserts another org; the symmetric window test passes (`±6 min` → `401`, `−4 min` → pass); each of the five headers missing in turn → `401`; two core-level tests call `authenticate_agent` with `body=b""` and a hand-built headers dict (no app) and cover `expected_agent_id`; the adapter contains no skew, signature, or nonce logic; the core imports nothing from FastAPI.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 10: Invite schemas
- **Description**: Create `schemas/invites.py` with `CreateInviteRequest`, `InviteCreatedResponse`, and `AcceptInviteRequest` exactly as the frozen contract declares them, all with `model_config = ConfigDict(extra="forbid")` matching `schemas/auth.py`, reusing `MIN_LENGTH` from `services/passwords.py` rather than a literal `12`.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/schemas/invites.py`, `backend/tests/test_invite_schemas.py`]
- **Success Criteria**: field names and types match `contracts/openapi/openapi.yaml` verbatim (`role` is `Literal["admin", "viewer"]`); an extra key such as `org_id` is rejected by `extra="forbid"`; `AcceptInviteRequest.password` minimum comes from `MIN_LENGTH`; no `openapi.yaml` edit.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 11: `services/invites.py` — create and accept
- **Description**: Create `create_invite(session, *, org_id, email, role, mailer) -> tuple[str, datetime]` and `accept_invite(session, *, token, email, password) -> tuple[str, str, int]` with `InviteTokenError`, `InviteEmailMismatchError`, `DuplicateUserError`, `AlreadyMemberError`, per ARCHITECTURE.md. Honor the **two-scope rule**: `create_invite`'s duplicate check is own-org only (`AlreadyMemberError` → 400); `accept_invite`'s is global (`DuplicateUserError` → 400). Reuse `validate_policy` and `hash_password` from `services/passwords.py` (passing `email=`) and `issue_session` from `services/auth.py`. Store only `sha256(raw)` in `token_hash`; `expires_at = now + INVITE_TTL_HOURS`; write `consumed_at` only on the success path, in the same commit as the `User` insert.
- **Dependencies**: Task 1, Task 3, Task 8, Task 10
- **Target Files**: [`backend/src/api/services/invites.py`, `backend/tests/test_invite_service.py`]
- **Success Criteria**: creation returns the raw token once and stores only its sha256, with `expires_at ≈ now + INVITE_TTL_HOURS`; an email already a user in the **same** org raises `AlreadyMemberError` and writes no invite row, while an email that is a user in **another** org creates a normal invite; acceptance creates the user with the invite's `org_id`, `role`, and `email` and returns the same triple `login` returns; unknown / expired / consumed token → `InviteTokenError`; body email ≠ invite email → `InviteEmailMismatchError`; an email existing in **any** org → `DuplicateUserError`; every failure leaves `consumed_at` NULL and no `User` row; the HIBP call is monkeypatched exactly as `test_password_policy.py` does, never a live network call; no second password rule and no second JWT mint.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 12: Invites router + app wiring
- **Description**: Create `routers/invites.py` with `router`, `create_invite_route` (`Depends(require_admin)`, `org_id` from `CallerIdentity`, never the body), `accept_invite_route` (`security: []`, `status_code=201`, returning `login_response(...)` from `routers/auth.py`), and `invite_preflight` via the derived-`OPTIONS` loop `routers/auth.py` uses. Map service errors to the ARCHITECTURE.md status table (400 / 410 / 403). Register the router in `main.py`.
- **Dependencies**: Task 7, Task 11
- **Target Files**: [`backend/src/api/routers/invites.py`, `backend/src/api/main.py`, `backend/tests/test_invite_routes.py`, `backend/tests/test_auth_wiring.py`]
- **Success Criteria**: admin bearer → `201` with exactly `invite_token` and `expires_at`; viewer → `403` with `select(Invite)` still empty; no bearer → `401`; already-a-member → `400`, no invite; another org's user → `201` with a body shape indistinguishable from a fresh address; `org_id` in the body → `422`; acceptance → `201` with a `LoginResponse` body **and** a `dmitri_refresh` `Set-Cookie`, and the returned access token immediately succeeds against `GET /api/v1/hosts`; second acceptance → `410` with only one `User`; expired → `410`; unknown token → `410`; weak and breached passwords → `400` with no `User` and `consumed_at` NULL; the route builds no `LoginResponse` and calls no `set_cookie` of its own; both invite routes and their `OPTIONS` preflights appear in `app.routes`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 13: Org scoping in `services/read.py`
- **Description**: Add a **required keyword-only** `org_id: UUID` to `list_hosts`, `get_host_detail`, `get_scan_detail`, and `list_findings`, with the filters in the ARCHITECTURE.md scoping table. `get_host_detail` must also scope its two inline `ScanRecord` queries (`latest_scan_host`, `scan_history_rows`) with `.where(ScanRecord.org_id == org_id)`. `list_findings` joins `ScanRecord` on `scan_id` before the `host_id` branch so the count and page queries share the predicate. A `NULL org_id` row is visible to nobody — plain `WHERE org_id = :org_id`, no `OR org_id IS NULL` and no fallback branch. Private helpers stay unscoped.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/read.py`, `backend/tests/test_read_service.py`]
- **Success Criteria**: `org_id` is keyword-only and required on all four functions; both the `count()` and the page query are scoped in `list_hosts` and `list_findings`; a foreign row fetched by id returns `None`; service-level tests with two seeded orgs prove filtering without the HTTP layer, including a host attached to a foreign org's scan via `ScanHostRecord` yielding empty `scan_history` and `ports`; a `NULL org_id` host/scan is returned to nobody, pinned by an explicit test; no backfill and no `NOT NULL` tightening.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 14: Mount `require_user` and org scope on the four read routes
- **Description**: Per the ARCHITECTURE.md Touched table, add `caller: CallerIdentity = Depends(require_user)` to both routes in `routers/hosts.py`, to `read_scan` in `routers/scans.py`, and to `read_findings` in `routers/findings.py` (keeping its `host_id` query param), passing `org_id=caller.org_id` into the read services. A service returning `None` for a foreign row becomes `404`, never `403`. **Additionally, Task 13 left a stopgap that this task must remove**: each of the three routers carries a local `_PLACEHOLDER_ORG_ID = UUID("00000000-...")` constant (marked with a `# ponytail:` comment) passed as `org_id=` to keep the suite green before `require_user` existed, and `backend/tests/test_read_endpoints.py`'s `_seed()` sets that same placeholder on its rows. Every trace of the placeholder must be gone — a hardcoded tenant id must not survive this feature.
- **Dependencies**: Task 7, Task 13
- **Target Files**: [`backend/src/api/routers/hosts.py`, `backend/src/api/routers/scans.py`, `backend/src/api/routers/findings.py`, `backend/tests/test_read_endpoints.py`, `backend/tests/test_auth_wiring.py`]
- **Success Criteria**: each of the four routes without a bearer → `401`, with a garbage bearer → `401`; `viewer` and `admin` tokens → `200` with only the caller's org records; a cross-org record by id → **`404` asserted as not `403`**; list routes return org-A rows only and `total` reflects the filtered count; the local test fixtures seed an `Org` and set `org_id` explicitly on every `HostRecord` / `ScanRecord`; `test_auth_wiring.py` structurally asserts `require_user` is in each of the four routes' dependency chains; **no `_PLACEHOLDER_ORG_ID` (or any hardcoded org UUID) remains anywhere in `backend/src` or `backend/tests`, asserted by a grep-style structural test so it cannot silently return**.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 15: Vendor management commands
- **Description**: Create `management/__init__.py`, `management/bootstrap_org.py`, and `management/provision_agent.py` per the ARCHITECTURE.md "Management commands" section, plus the two `[project.scripts]` entries `backend-bootstrap-org` and `backend-provision-agent` (the `backend-` prefix, not `dmitri-`). Both use `argparse`, the `for session in get_session():` idiom from `services/worker.py:36`, `DATABASE_URL` (the `dmitri_runtime` role — never `DATABASE_URL_DIRECT`), and `main(argv=None) -> int` returning `0`/`1` with one-line stderr messages instead of tracebacks. `bootstrap_org` refuses a duplicate org name case- and whitespace-insensitively **before** any insert, then adds the `Org`, **commits**, then calls `create_invite(..., role="admin")`. `provision_agent` validates the org and a 64-hex/32-byte public key, inserts the `Agent`, and prints the `agent_id`; it never receives a private key, though `--generate` may print one once for local testing behind a not-for-production banner. Secrets go to stdout exactly once and never through `logging`. No HTTP routes.
- **Dependencies**: Task 4, Task 5, Task 11
- **Target Files**: [`backend/src/api/management/__init__.py`, `backend/src/api/management/bootstrap_org.py`, `backend/src/api/management/provision_agent.py`, `backend/pyproject.toml`, `backend/tests/test_bootstrap_org.py`, `backend/tests/test_provision_agent.py`]
- **Success Criteria**: `main(["--org-name", "Acme", "--email", "a@acme.test"])` returns `0` and creates exactly one `Org` and one `role="admin"` `Invite` scoped to it, the printed token's sha256 equals the stored `token_hash`, and `accept_invite` on it yields a working admin; a second run with the same name — and with `"  acme  "` — returns `1`, writes stderr, and leaves **exactly one** `Org` and one `Invite` (counts asserted); the refusal precedes any insert; `provision_agent` inserts an `Agent` with the given `public_key` and `org_id` and prints the `agent_id`, and returns `1` for a bad-length hex key or an unknown `--org-id` without raising; no private key ever reaches the database; no `logging` call carries a token or key; both console-script names appear in `[project.scripts]` pointing at the two `main` callables, asserted structurally.
- **Status**: COMPLETED
- **Review Rejections**: 1

---

## Dependency graph

```
#1 ─┬─────────────────────────► #9 ◄─── #5 ◄─┐
    │                            ▲            │
#2 ─┼── #3 ── #4 ────────────────┘            │
    └── #6 ──────────────────────┘            │
#1, #3, #8, #10 ──► #11 ──► #12 ◄── #7        │
#11 ──────────────────────► #15 ◄── #4, #5 ───┘
#13 ──► #14 ◄── #7
```

Tracks that run in parallel:

- **Device gate**: #2 → #6, #5 → #9
- **Migrations**: #2 → #3 → #4
- **Invites**: #8, #10 → #11 → #12
- **Tenancy**: #13 → #14
- **Config**: #1 (feeds #9 and #11)

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Settings fields for skew and invite TTL | COMPLETED |
| 2 | `agent_nonces` model + migration | COMPLETED |
| 2.5 | Fix the `_migrate` round-trip test helper | COMPLETED |
| 2.6 | Teach `test_migrations.py` the `agent_nonces` grant set | COMPLETED |
| 3 | Global `users` email uniqueness | COMPLETED |
| 4 | `agents` secret columns → `public_key` | COMPLETED |
| 5 | `services/device_sig.py` — Ed25519 primitives | COMPLETED |
| 6 | `services/nonces.py` — insert-or-replay + prune | COMPLETED |
| 6.5 | Fix the `postgres_engine` teardown-ordering flake | COMPLETED |
| 7 | `require_admin` role gate | COMPLETED |
| 8 | Shared session-issuing, cookie, and mailer seams | COMPLETED |
| 9 | Device gate — core + HTTP adapter | COMPLETED (1 rejection) |
| 10 | Invite schemas | COMPLETED (1 rejection) |
| 11 | `services/invites.py` — create and accept | COMPLETED (1 rejection) |
| 12 | Invites router + app wiring | COMPLETED |
| 13 | Org scoping in `services/read.py` | COMPLETED |
| 14 | Mount `require_user` + org scope on read routes | COMPLETED |
| 15 | Vendor management commands | COMPLETED (1 rejection) |
