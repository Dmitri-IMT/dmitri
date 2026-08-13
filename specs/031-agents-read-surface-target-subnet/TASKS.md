# Tasks — Agent read surface and the Pi's target network (`031-agents-read-surface-target-subnet`)

6 tasks. **Unblocked now: #1**

Layer: `backend/` (one generated frontend file in #6). Test agent **`test-engineer`**, review agent
**`code-reviewer`**.

**Gate for every task** (`.claude/CLAUDE.md`): run `./database.sh` **first**, then from `backend/`
`uv run ruff check src tests` and `uv run pytest`. **Never** `uv run ruff format` or any repo-wide
formatter — backend Python is hand-formatted. A run with database-test skips is not a green run:
report the skip count or re-run with the database up. Task #6 additionally runs `npm run gen:types`
and `npm run typecheck` from `frontend/`.

This feature is a single cohesive API surface over existing state, so the chain is mostly linear —
there are no independent parallel tracks to split out, and inventing some would only create
tasks that edit each other's files.

---

## Task 1: Add the `target_subnet` column and model field
- **Description**: Alembic migration adding one nullable `agents.target_subnet`, plus the matching
  SQLModel field. Per ARCHITECTURE.md §3.1 and §3.2.
- **Absorbed**: The `Agent` model field — a nullable column declaration with no branching cannot
  fail a test of its own; the migration's live-column assertions are what prove it landed.
- **Dependencies**: —
- **Target Files**: [`backend/alembic/versions/20260811_17_agents_target_subnet.py`,
  `backend/src/api/models/command.py`,
  `backend/tests/test_agents_target_subnet_migration.py`]
- **Tests**: `test_agents_target_subnet_migration.py`, mirroring
  `tests/test_user_activity_migration.py` — proves the revision chain, that exactly one nullable
  unindexed column is added, that `downgrade()` drops exactly it, and that no stray `GRANT` is
  issued.
- **Success Criteria**:
  - `revision == "20260811_17"`, `down_revision == "20260810_16"`.
  - `upgrade()` adds exactly `("agents", "target_subnet")`, `sa.String`, `nullable is True`, no index.
  - `upgrade()` executes **no** raw statements — `agents` already grants `SELECT, INSERT, UPDATE` to
    `dmitri_runtime` from `20260723_07`, and `tests/test_migrations.py::RUNTIME_GRANTS_BY_TABLE`
    must stay unchanged.
  - `downgrade()` performs exactly one `drop_column`.
  - Live against `postgres_engine`: `information_schema.columns` reports
    `("character varying", "YES")`; no index in `pg_indexes` mentions the column.
  - AC *Online is never stored* / *Reported networks are never stored* at the storage level: after
    head, `agents` has no `online` and no `available_subnets` column. Do **not** assert "no
    connection state is stored" — `agents.connected_at` exists and `sweep_stale_commands` depends
    on it (ARCHITECTURE.md §7.2).
  - `Agent(...)` construction sites are untouched — the field is nullable with a default.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Schemas, read service, and `GET /api/v1/agents`
- **Description**: New `schemas/agents.py` and `services/agents.py`, plus the list route and its
  CORS preflight on the existing router. Per ARCHITECTURE.md §3.3, §3.4, §3.5 and the request-path
  walk in §1.
- **Absorbed**: The `AgentSummary` / `AgentListResponse` pydantic models and the private response
  builder — shape declarations and an unexported helper with no observable behaviour of their own;
  the route tests are what would fail if either were wrong.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/schemas/agents.py`,
  `backend/src/api/services/agents.py`,
  `backend/src/api/routers/agents.py`,
  `backend/tests/test_agent_read_routes.py`]
- **Tests**: `test_agent_read_routes.py` (new), mirroring `tests/test_get_command.py` for the client
  fixture and org-scoping seeds and `tests/test_users_admin_routes.py` for list shape.
- **Success Criteria**:
  - AC *List the org's scanners*: one provisioned agent returns one row whose keys are exactly
    `{agent_id, display_name, online, last_seen_at, target_subnet, active_command_id}`.
  - AC *List is org-scoped*: a second org's agent is absent. Filtering is in the SQL
    (`Agent.org_id == caller.org_id`), not in the handler.
  - `available_subnets` is **not** a key on any list row.
  - AC *Viewer may read* (list half): a viewer token gets 200. Auth is `require_user`.
  - AC *Current command surfaces* / *No command in flight* (list half): an agent with a non-terminal
    command carries that `active_command_id`; an agent with only a `done` command carries `null`.
  - An org with no agents returns `{"data": []}`, never a 404.
  - `online` comes from `agent_connections.is_online()` and `last_seen_at` from
    `agent_connections.last_seen_at(id) or row.last_seen_at`; `active_command_id` from
    `commands.active_command_for()`. No new presence helper, no second active-command query, no new
    field on `AgentConnection`.
  - Service functions are plain `def` and use only the non-async registry helpers; they never call
    `register` / `set_hello` / `touch`.
  - The existing `POST`, WebSocket route and `add_api_route` preflight in `routers/agents.py` are
    untouched.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: `GET /api/v1/agents/{agent_id}` with the reported networks
- **Description**: The detail route — already published in the contract but never implemented —
  carrying `available_subnets` from the connection registry alongside the fields the list returns.
  Extends the Task 2 builder so list and detail cannot drift, per ARCHITECTURE.md §3.4.
- **Absorbed**: The `AgentDetail` model and its preflight — a shape declaration and a 204 stub,
  both exercised by this task's route tests.
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/schemas/agents.py`,
  `backend/src/api/services/agents.py`,
  `backend/src/api/routers/agents.py`,
  `backend/tests/test_agent_read_routes.py`]
- **Tests**: `test_agent_read_routes.py` (extended). Presence is simulated with
  `agent_connections.register(...)` + `set_hello(...)` as `tests/test_enqueue_command.py` does, with
  the autouse registry-clearing fixture.
- **Success Criteria**:
  - AC *Detail reports both networks*: a Pi reporting two interfaces returns both in order, each
    with `interface`, `cidr` and `is_default_route`, the wifi one `true`. Reuses
    `AvailableSubnet` from `schemas/agent_frames.py` — **no second subnet type**.
  - AC *Offline Pi reports nothing*: never-connected → `available_subnets == []` **and**
    `last_seen_at is None`; registered → hello → unregistered → `[]` **and** `last_seen_at` equal to
    the persisted row value, not `None`. `null` means exactly "never connected".
  - AC *Online reflects the live connection*: register a socket → `online is True`; unregister →
    `online is False` on an otherwise identical request.
  - AC *Reported networks are never stored*: an end-to-end pass through a real socket
    (`client.websocket_connect(...)`, send `_hello_payload()`, `_sync(ws)`) reads `online is True`
    with both subnets inside the block and `online is False` with `[]` after it; re-reading the
    `agents` row shows nothing carrying the reported subnets. If issuing an HTTP request inside the
    `websocket_connect` block proves unreliable under the TestClient portal, split the test per
    ARCHITECTURE.md §6 — assert the connected read via direct registry registration and keep the
    real socket for the post-disconnect read. **Do not delete the flip assertion.**
  - AC *Unchosen network reads as absent*: a newly provisioned agent reports `target_subnet: null`.
  - AC *Unknown agent*: an unknown uuid → 404; another org's agent → 404 with an **identical** body.
    Never 403.
  - AC *Viewer may read* (detail half) and AC *Current command surfaces* / *No command in flight*
    (detail half).
  - The `get_hello()` helper is the only source of `available_subnets`; `None` (offline, or
    connected but pre-`hello`) renders as `[]`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 4: `PATCH /api/v1/agents/{agent_id}` — choose the target network
- **Description**: The admin-only write that stores the chosen network, refusing anything the
  connected Pi did not report. Per ARCHITECTURE.md §2 (verb and shape) and §3.4/§3.5.
- **Absorbed**: `UpdateAgentTargetSubnetRequest` and `AgentOfflineError` — a single-field request
  model and an exception class, both observable only through this task's refusal tests.
- **Dependencies**: Task 3
- **Target Files**: [`backend/src/api/schemas/agents.py`,
  `backend/src/api/services/agents.py`,
  `backend/src/api/services/commands.py`,
  `backend/src/api/routers/agents.py`,
  `backend/tests/test_agent_target_subnet_routes.py`]
- **Tests**: `test_agent_target_subnet_routes.py` (new), mirroring `tests/test_users_admin_routes.py`.
- **Success Criteria**:
  - AC *Choosing a reported network*: 200, body is the full `AgentDetail` with the new value, and a
    following `GET /agents` row and `GET /agents/{id}` both report it. Same builder as the GET, so
    the SPA needs no refetch.
  - AC *Choosing an unreported network*: 422 with `error.code == "subnet_not_reported"`, DB unchanged.
  - AC *Choosing while the Pi is offline*: 409 with `error.code == "device_offline"`, DB unchanged —
    **and the connected-but-pre-`hello` case returns the same 409**, since one `get_hello() is None`
    check covers both.
  - AC *Re-choosing replaces*: the row holds only the new value.
  - AC *Viewer may not choose*: 403 before any DB work, DB unchanged. Auth is `require_admin`.
  - AC *Cross-org choose refused*: 404 (**not** 403), and the other org's value is unchanged.
  - Unknown uuid → 404. Body `{}`, an unknown extra key, or a malformed CIDR → 422
    `validation_error` from the global handler, DB unchanged.
  - Resolution order is fixed: missing/foreign row → 404, then no report → 409, then unreported
    value → 422, then commit.
  - The 409 and 422 are **literal `ApiError(...)` calls inside the handler body** — raising them
    from the service makes `test_contract_fidelity.py::test_error_code_fidelity`'s AST scan blind.
  - **`SubnetNotReportedError` is declared in `services/commands.py`**, beside `AgentNotFoundError`
    / `DeviceBusyError` / `DeviceOfflineError`, and imported by `services/agents.py`. It must
    **not** be declared in `services/agents.py`: that module imports `active_command_for` from
    `commands.py`, so declaring it there and importing back is a circular import
    (ARCHITECTURE.md §3.7(3)). This one-line declaration is the **only** change to
    `services/commands.py` in this task — the §3.7 check itself is Task 5.
  - `AgentOfflineError` stays in `services/agents.py`; only the PATCH raises it.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: The trigger refuses a subnet the Pi is not reporting
- **Description**: The one sanctioned change inside DMI-64's command write path — `_claim_agent`
  refuses a scan naming a network the Pi is not currently reporting. Per ARCHITECTURE.md §3.7 and
  the 2026-08-11 scope amendment on DMI-78.
- **Absorbed**: The `except` arm in `create_agent_command` — a four-line mapping from the service
  exception to the published 422, proved by this task's route-level refusal tests.
- **Dependencies**: Task 4
- **Target Files**: [`backend/src/api/services/commands.py`,
  `backend/src/api/routers/agents.py`,
  `backend/tests/test_enqueue_command.py`]
- **Tests**: `test_enqueue_command.py` (extended). **Every pre-existing test in this file must keep
  passing unedited** — verified: none of them calls `set_hello`, so all resolve `hello is None` and
  take the untouched path. If one suddenly needs a `set_hello` it did not have, that is the signal
  the check refuses too much, not a licence to rewrite the test.
- **Success Criteria**:
  - AC *Chosen network drives the scan*: a connected Pi reporting the named subnet → 201, delivered
    as before. This case **must register a hello**, or the validated branch ships untested.
  - AC *Unreported network cannot be scanned*: a well-formed unreported CIDR → 422
    `subnet_not_reported`, and **no `commands` row exists** for that agent afterwards.
  - AC *Stale choice is refused, not scanned*: a stored choice the Pi no longer reports → 422, and
    the `agents` row's `target_subnet` is **unchanged** — never corrected, never cleared.
  - AC *Silence is not contradiction*: registered but no `set_hello` → pre-existing behaviour, not a
    422. Not registered at all → the pre-existing 503 `device_offline` with the command row
    `expired`, exactly as `tests/test_command_delivery.py` asserts.
  - **The check must not raise `DeviceOfflineError` when there is no report.** Today's 503 is raised
    by `deliver()` *after* the row exists, which is what makes the command `expired`; raising from
    `_claim_agent` would return 503 with **no row** and contradict the lifecycle contract this
    feature may not touch.
  - Comparison is **exact string equality** against `{entry.cidr for entry in reported}`. Do not
    reach for `ipaddress.ip_network` — every non-exact value must fail closed, and parsing adds a
    failure mode inside the enqueue path (ARCHITECTURE.md §3.7).
  - AC *Everything else about triggering is untouched*: busy agent still 409 `device_busy` with the
    busy check still running **before** the subnet check; foreign-org agent still 403; delivery,
    lifecycle and sweeper behaviour unchanged.
  - AC *No network chosen blocks the scan*: a POST with no `subnet` key is still 422 from
    `CreateCommandRequest` — no new "choose first" rule is added.
  - The only edits to `services/commands.py` are the check in `_claim_agent`. `enqueue`, `deliver`,
    `_record_delivery`, `sweep_stale_commands` and `active_command_for` are untouched, as are
    `command_lifecycle.py`, `schemas/commands.py` and the WebSocket route.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Publish the contract and regenerate the frontend types
- **Description**: Bring `contracts/openapi/openapi.yaml` up to what the app now serves, extend the
  fidelity gate to cover it, and commit the regenerated type file. Per ARCHITECTURE.md §3.6 and the
  naming table.
- **Absorbed**: The `frontend/src/types/openapi.d.ts` regeneration — a generated artifact with no
  test of its own, gated by `npm run typecheck` and by CI's own diff check.
- **Dependencies**: Tasks 2, 3, 4, 5
- **Target Files**: [`contracts/openapi/openapi.yaml`,
  `frontend/src/types/openapi.d.ts`,
  `backend/tests/test_contract_fidelity.py`]
- **Tests**: `test_contract_fidelity.py` (extended) — schema fingerprints, published operations, and
  the pinned error codes.
- **Success Criteria**:
  - AC *Contract published*. New path `/api/v1/agents` (`listAgents` + `optionsAgents`); `patch`
    added to `/api/v1/agents/{agent_id}` as `updateAgentTargetSubnet`; `422` →
    `ScanSubnetNotReported` added to the existing `post` on `/api/v1/agents/{agent_id}/commands`.
  - `AgentDetail` gains `available_subnets` (in `required`, after `last_seen_at`) and
    `target_subnet`. `active_command_id` stays **out** of `required` — do not "fix" it.
  - New schemas `AgentSummary`, `AgentListResponse`, `UpdateAgentTargetSubnetRequest`, all
    `additionalProperties: false`.
  - New response components `AgentOfflineConflict` (409, `device_offline`),
    `TargetSubnetNotReported` (422, `subnet_not_reported`) and `ScanSubnetNotReported` (422,
    `subnet_not_reported`), each in the `allOf: [ErrorResponse, {error.code pinned}]` form the
    neighbours use. Three components rather than two because `ERROR_RESPONSE_ROUTES` maps **one
    component to exactly one handler** — sharing one would leave an `ApiError` literal unverified.
    `AgentOfflineConflict` must **not** collapse onto `DeviceOfflineError`: same machine code by
    decision (ARCHITECTURE.md §7.1), different description and status.
  - `SCHEMA_NAMES` += the four agent schemas; `ERROR_RESPONSE_ROUTES` += the three new components
    mapped to `update_agent_target_subnet_route` (409, 422) and `create_agent_command` (422);
    `test_admin_operations_are_published` += `("/api/v1/agents", "get", "listAgents",
    {"200","401","500"})` and `("/api/v1/agents/{agent_id}", "patch", "updateAgentTargetSubnet",
    {"200","401","403","404","409","422","500"})`.
  - `AvailableSubnet` and the `AgentId` parameter are reused unchanged.
  - `npm run gen:types` from `frontend/` produces a committed `openapi.d.ts`, and
    `npm run typecheck` passes. CI runs `gen:types` then `git diff --exit-code -- src/types`
    (`.github/workflows/ci.yml:184-190`), so an uncommitted regeneration fails the build.
    `frontend/src/api/agents.ts` is **not** touched — it belongs to DMI-89.
  - AC *Gates pass*: `./database.sh`, then `uv run ruff check src tests` and `uv run pytest` from
    `backend/`, reported with a zero skip count.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 → #2 → #3 → #4 → #5 → #6
```

`#1` unblocks everything (the column). `#3` extends `#2`'s shared builder so list and detail cannot
drift. `#4` declares the exception `#5` raises. `#6` needs every handler in place, because the
fidelity gate reads the literal `ApiError` calls out of them.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Add the `target_subnet` column and model field | COMPLETED |
| 2 | Schemas, read service, and `GET /api/v1/agents` | COMPLETED |
| 3 | `GET /api/v1/agents/{agent_id}` with the reported networks | COMPLETED |
| 4 | `PATCH /api/v1/agents/{agent_id}` — choose the target network | COMPLETED |
| 5 | The trigger refuses a subnet the Pi is not reporting | COMPLETED |
| 6 | Publish the contract and regenerate the frontend types | COMPLETED |

## Acceptance-criteria coverage

Every row of `TRUTH.md`'s table has a home.

| AC scenario | Task |
|---|---|
| List the org's scanners · List is org-scoped | 2 |
| Detail reports both networks · Offline Pi reports nothing · Online reflects the live connection · Unknown agent | 3 |
| Online is never stored · Reported networks are never stored | 1 (no column) + 3 (registry-derived, WS end-to-end) |
| Unchosen network reads as absent | 1 (storage) + 3 (API) |
| Viewer may read · Current command surfaces · No command in flight | 2 (list) + 3 (detail) |
| Choosing a reported network · Choosing an unreported network · Choosing while the Pi is offline · Re-choosing replaces · Viewer may not choose · Cross-org choose refused | 4 |
| Chosen network drives the scan · Unreported network cannot be scanned · Stale choice is refused, not scanned · Silence is not contradiction · Everything else about triggering is untouched · No network chosen blocks the scan | 5 |
| Contract published · Gates pass | 6 |
