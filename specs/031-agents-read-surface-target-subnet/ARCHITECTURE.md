# ARCHITECTURE — Agent read surface and the Pi's target network (DMI-78)

Implements `TRUTH.md`. Single layer: `backend/` only. No `hardware-agent/` work, no `frontend/`
work beyond regenerating the contract type file (see the naming table). No `INTEGRATION.md` — the
only cross-layer artefact is `contracts/openapi/openapi.yaml`, covered here.

---

## 1. System context

The Pi command channel already exists end to end. This feature adds a **read surface over the
state that channel already produces**, plus one small write.

```text
Pi daemon ──WSS──> /api/v1/agents/{agent_id}/commands        (DMI-64/66, untouched)
                        │
                        ├─ register()/unregister()  ─────> agent_connections  (in-memory)
                        │                                    · is_online()
                        │                                    · last_seen_at()
                        │                                    · get_hello() -> (version, subnets)
                        │
                        ├─ hello frame → set_hello() ──────> available_subnets (never persisted)
                        │
                        └─ mark_connected/disconnected ───> agents.connected_at / last_seen_at (DB)

Web SPA ──JWT──> GET   /api/v1/agents            (NEW)  ─┐
                 GET   /api/v1/agents/{agent_id}  (NEW)  ├─> services/agents.py ─┬─> agents table
                 PATCH /api/v1/agents/{agent_id}  (NEW)  ─┘                      ├─> agent_connections
                                                                                 └─> commands.active_command_for
                 POST  /api/v1/agents/{id}/commands  (EXISTS — DMI-64)
                       └─ ONE added refusal in _claim_agent: the named subnet must be
                          one the Pi is reporting right now (§3.7). Everything else on
                          this path — delivery, lifecycle, busy, unreachable — untouched.
```

Three facts have three different homes, and this feature never mixes them:

| Fact | Source | Persisted? |
|------|--------|-----------|
| `online` | `agent_connections.is_online()` | never |
| `available_subnets` | `agent_connections.get_hello()` | never |
| `last_seen_at` | registry first, `agents.last_seen_at` fallback | the fallback only |
| `target_subnet` | `agents.target_subnet` (new column) | yes |
| `active_command_id` | `commands.active_command_for()` | yes (`commands` row) |

### Request-path walks

**`GET /api/v1/agents`** — `require_user` → `list_agents(session, org_id=caller.org_id)` →
`SELECT * FROM agents WHERE org_id = :org ORDER BY created_at, id` → for each row:
`agent_connections.is_online(id)`, `agent_connections.last_seen_at(id) or row.last_seen_at`,
`commands.active_command_for(session, id)` → `AgentListResponse(data=[AgentSummary, ...])`. Never
404s; an org with no agents gets `{"data": []}`. `available_subnets` is not touched here.

**`GET /api/v1/agents/{agent_id}`** — `require_user` → `get_agent_detail(session, agent_id=...,
org_id=caller.org_id)` → row lookup scoped by `org_id`; `None` → router raises
`HTTPException(404)` (so a foreign org's agent is indistinguishable from a missing one) → else the
same four derivations as the list **plus** `agent_connections.get_hello(agent_id)`, whose subnet
list is passed through as-is, or `[]` when the helper returns `None` (offline, or connected but
pre-hello) → `AgentDetail`.

**`PATCH /api/v1/agents/{agent_id}`** — `require_admin` (viewer → 403 before any DB work) →
`set_target_subnet(session, agent_id=..., org_id=caller.org_id, target_subnet=body.target_subnet)`,
which resolves in this fixed order:

1. row missing or `org_id` mismatch → return `None` → router raises `404 not_found`;
2. `agent_connections.get_hello(agent_id) is None` → raise `AgentOfflineError` → router raises
   `409 device_offline`;
3. the value is not among the reported `cidr`s → raise `SubnetNotReportedError` → router raises
   `422 subnet_not_reported`;
4. otherwise assign `agent.target_subnet`, `session.commit()`, and return the freshly built
   `AgentDetail` (same builder as the GET) so the SPA needs no refetch.

Nothing on this path writes a command or reads `CreateCommandRequest`. It imports one exception
type from `services/commands.py` (§3.7) and calls `active_command_for`; that is the whole of its
contact with the command module.

---

## 2. Decisions (rationale for the three open points)

**Verb and shape.** `PATCH /api/v1/agents/{agent_id}` with body `{"target_subnet": "10.0.0.0/24"}`.
The house already has exactly this shape one file over — `PATCH /api/v1/users/{user_id}` with
`UpdateUserRoleRequest` carrying a single required field and `extra="forbid"`
(`backend/src/api/routers/users.py:69`). The path is already published in the contract with its
`AgentId` parameter and its OPTIONS preflight, so nothing new is invented in the URL space. The
request model has exactly one **required** field and forbids extras, so this is a single-field
update, not an agent-wide mutable resource: adding a second mutable agent field later is a
deliberate contract change, not a silent widening. Response is `AgentDetail` — the same read shape
the GET returns, mirroring `PATCH /users/{user_id}` returning `OrgMember`.

**`last_seen_at` when the Pi is offline.** Coalesce: `agent_connections.last_seen_at(agent_id) or
agent.last_seen_at`. The registry value only exists while connected, and the persisted column is
maintained on exactly the events that matter — `mark_connected` on upgrade
(`services/agent_presence.py:29`), `async_touch_agent_last_seen` on every `hello`
(`services/agent_ws.py:99`) and `touch_agent_last_seen` on every `status`
(`services/agent_ws.py:59`) — and is **not** cleared on disconnect (`mark_disconnected` only nulls
`connected_at`). So the fallback is the honest "when we last heard from it", which is the whole
point of the field on an offline row. Returning `null` for an offline Pi that has connected before
would be a regression against a value the DB already holds correctly. `null` therefore means
exactly one thing: this agent has never connected.

**`device_offline` at 409 as well as 503.** Kept as decided, with a caveat recorded in
§7 Concerns. The code names the condition ("the Pi is not holding a connection"), the SPA copy for
both is the same sentence, and both operations are on the same agent resource. To avoid attaching
the trigger's delivery semantics to this refusal, the 409 gets its **own** response component
(`AgentOfflineConflict`) rather than reusing the `DeviceOfflineError` component at a second status
— the description text differs, the machine code does not.

---

## 3. Data model and contracts

### 3.1 Migration

`backend/alembic/versions/20260811_17_agents_target_subnet.py`

```
revision = "20260811_17"
down_revision = "20260810_16"
```

- `upgrade()`: `op.add_column("agents", sa.Column("target_subnet", sa.String(), nullable=True))`.
- `downgrade()`: `op.drop_column("agents", "target_subnet")`.
- **No grant statements.** `agents` already carries the default `SELECT, INSERT, UPDATE` grant to
  `dmitri_runtime` from `20260723_07_command_channel.py:80`, which is everything this feature
  needs. `tests/test_migrations.py::RUNTIME_GRANTS_BY_TABLE` must stay unchanged — if a
  `GRANT`/`REVOKE` appears in this migration, that is a mistake.
- **No index.** One agent per org today; the column is never a filter or a sort key.
- Nullable with no server default and no backfill: "unchosen" is `NULL`, per TRUTH.

### 3.2 ORM model

`backend/src/api/models/command.py` — `class Agent` gains one field, declared last:

```
target_subnet: str | None = None
```

Additive and nullable, so **no existing `Agent(...)` construction site changes** — verified by
grep, 17 sites (`management/provision_agent.py:63` and 16 test seeds).

### 3.3 New schemas — `backend/src/api/schemas/agents.py`

Imports: `AvailableSubnet` from `api.schemas.agent_frames`, `SubnetCIDR` from `api.schemas.scan`.
All models set `model_config = ConfigDict(extra="forbid")`. **Do not define a second subnet type.**

`AgentSummary` (list row):

| Field | Type | Required in schema | Nullable |
|-------|------|--------------------|----------|
| `agent_id` | `UUID` | yes | no |
| `display_name` | `str` | yes | no |
| `online` | `bool` | yes | no |
| `last_seen_at` | `datetime \| None` | yes | yes |
| `target_subnet` | `SubnetCIDR \| None = None` | no | yes |
| `active_command_id` | `UUID \| None = None` | no | yes |

`AgentDetail` (detail):

| Field | Type | Required in schema | Nullable |
|-------|------|--------------------|----------|
| `agent_id` | `UUID` | yes | no |
| `display_name` | `str` | yes | no |
| `online` | `bool` | yes | no |
| `last_seen_at` | `datetime \| None` | yes | yes |
| `available_subnets` | `list[AvailableSubnet]` | yes | no (empty list when offline) |
| `target_subnet` | `SubnetCIDR \| None = None` | no | yes |
| `active_command_id` | `UUID \| None = None` | no | yes |

Rule the shapes follow: **every field `AgentSummary` shares with `AgentDetail` has an identical
shape**, and `AgentDetail`'s already-published fields keep the requiredness the contract already
states (`active_command_id` optional-nullable). The `= None` on the two optional fields is what
makes the generated schema match the published `AgentDetail`; changing it silently breaks
`test_contract_fidelity.py`.

`AgentListResponse`: `data: list[AgentSummary]` (required). Mirrors `OrgMemberListResponse`. No
paging — there is no paging in the contract for this resource and TRUTH asks for none.

`UpdateAgentTargetSubnetRequest`: `target_subnet: SubnetCIDR` — required, non-nullable. There is no
"clear the choice" operation; TRUTH says a choice is replaced, never emptied.

### 3.4 Service — `backend/src/api/services/agents.py`

```
class AgentOfflineError(ValueError): ...
class SubnetNotReportedError(ValueError): ...

def list_agents(session: Session, *, org_id: UUID) -> list[AgentSummary]
def get_agent_detail(session: Session, *, agent_id: UUID, org_id: UUID) -> AgentDetail | None
def set_target_subnet(session: Session, *, agent_id: UUID, org_id: UUID,
                      target_subnet: str) -> AgentDetail | None
```

- Missing/foreign agent → `None` (house pattern: `get_command_detail`, `change_member_role`). The
  two exceptions are refusals only.
- These are **new** exception types, deliberately not `commands.DeviceOfflineError`: that one means
  "delivery failed and the command expired". Do not import it here.
- All three functions are plain `def`, called from plain `def` routes, so FastAPI runs them in a
  worker thread and no DB call blocks the event loop that the live Pi sockets share. Only the
  **non-async** registry helpers (`is_online`, `last_seen_at`, `get_hello`) may be used — they are
  single-key dict reads. Never call `register`/`set_hello`/`touch` from this module.
- One private builder assembles `AgentSummary`/`AgentDetail` from `(Agent row, registry, active
  command)` so the list and the detail cannot drift.
- No `revoked_at` filter: revocation has no writer today and TRUTH does not mention it (§7).

### 3.5 Router — `backend/src/api/routers/agents.py`

Added to the existing file, above the existing `POST`/WebSocket block. Handler names take the
`_route` suffix where they would collide with the imported service function, as in `users.py`.

| Route | Handler | Auth | Success | Refusals |
|-------|---------|------|---------|----------|
| `GET /api/v1/agents` | `list_agents_route` | `require_user` | `200 AgentListResponse` | — |
| `GET /api/v1/agents/{agent_id}` | `read_agent_route` | `require_user` | `200 AgentDetail` | `404 not_found` |
| `PATCH /api/v1/agents/{agent_id}` | `update_agent_target_subnet_route` | `require_admin` | `200 AgentDetail` | `403` (viewer), `404 not_found`, `409 device_offline`, `422 subnet_not_reported` |
| `OPTIONS /api/v1/agents` | `options_agents` | none | `204` | — |
| `OPTIONS /api/v1/agents/{agent_id}` | `options_agent` | none | `204` | — |

- The two 404s are bare `HTTPException(status_code=404, ...)`; `DEFAULT_CODES_BY_STATUS` already
  renders `not_found`.
- The 409 and the 422 **must be literal `ApiError(...)` calls inside
  `update_agent_target_subnet_route`** — `test_contract_fidelity.py::test_error_code_fidelity`
  AST-scans the handler body, so raising them from the service instead makes the contract gate
  blind:
  - `ApiError(409, "Pi seems to be offline.", code="device_offline")`
  - `ApiError(422, "That network is not one the Pi reported.", code="subnet_not_reported")`
- New preflights use the `@router.options(..., status_code=204)` decorator (the form used in
  `routers/commands.py:28`). The existing `add_api_route` preflight for `.../commands` is left
  exactly as it is. CORS already allows `PATCH` (`middleware.py:54`), so no middleware change.

### 3.6 `contracts/openapi/openapi.yaml`

**New path `/api/v1/agents`** (place it immediately before `/api/v1/agents/{agent_id}/commands`):

- `get`: tags `[agents]`, `operationId: listAgents`, summary "List scanner agents",
  `security: [{FrontendBearerAuth: []}]`, no parameters, responses
  `200` (`AgentListResponse`), `401` → `Unauthorized`, `500` → `InternalServerError`.
- `options`: `operationId: optionsAgents`, `security: []`, `204` → `CorsPreflightNoContent`.

**Edit `/api/v1/agents/{agent_id}`** (~line 526) — keep `get` and `options` as published, add
`patch` between them:

- `operationId: updateAgentTargetSubnet`, summary "Set the agent's target network",
  `security: [{FrontendBearerAuth: []}]`, parameter `$ref AgentId`, `requestBody` required →
  `UpdateAgentTargetSubnetRequest`, responses: `200` (`AgentDetail`), `401` → `Unauthorized`,
  `403` → `Forbidden`, `404` → `NotFound`, `409` → `AgentOfflineConflict`,
  `422` → `TargetSubnetNotReported`, `500` → `InternalServerError`.
- The `get` description gains one clause: the detail also carries the networks the connected Pi
  reported and the network an admin chose.

**Edit `components.schemas.AgentDetail`** (~line 2571): add `available_subnets` to `required`
(after `last_seen_at`), and add two properties:

```yaml
        available_subnets:
          type: array
          items:
            $ref: '#/components/schemas/AvailableSubnet'
        target_subnet:
          type:
            - string
            - 'null'
          pattern: '^([0-9]{1,3}[.]){3}[0-9]{1,3}/[0-9]{1,2}$'
```

`active_command_id` stays out of `required` — do not "fix" it here.

**New `components.schemas`** (next to `AgentDetail`, above `AvailableSubnet`):

- `AgentSummary` — `additionalProperties: false`, `required: [agent_id, display_name, online,
  last_seen_at]`, properties exactly as §3.3 (uuid / string / boolean / nullable date-time /
  nullable patterned string / nullable uuid).
- `AgentListResponse` — `additionalProperties: false`, `required: [data]`, `data` an array of
  `AgentSummary`.
- `UpdateAgentTargetSubnetRequest` — `additionalProperties: false`, `required: [target_subnet]`,
  `target_subnet` a string with the CIDR pattern and `example: 10.0.0.0/24`.

**New `components.responses`** (next to `DeviceBusyError` / `DeviceOfflineError`), both using the
`allOf: [ErrorResponse, {error.code pinned}]` form the neighbours use:

- `AgentOfflineConflict` — 409. `code` const `device_offline`. Description: the Pi is not holding a
  connection, so it has reported no networks and there is nothing to choose from; the stored choice
  is unchanged. Same machine code as the trigger's 503 because the condition is the same; the
  status differs because nothing was dispatched. Example message: "Pi seems to be offline."
- `TargetSubnetNotReported` — 422. `code` const `subnet_not_reported`. Description: the value is a
  well-formed CIDR but is not one the connected Pi reported; the stored choice is unchanged.
  Example message: "That network is not one the Pi reported."
- `ScanSubnetNotReported` — 422. `code` const `subnet_not_reported`. The trigger's refusal (§3.7).
  Description: the network named for this scan is not one the Pi is currently reporting — the
  stored choice may predate a change of cabling or address range; no command was created and the
  stored choice is unchanged. Same machine code as `TargetSubnetNotReported` because it is the same
  rule; a separate component because the description and the operation differ, and because
  `ERROR_RESPONSE_ROUTES` in `test_contract_fidelity.py` maps **one component to exactly one
  handler** — sharing the component would leave one of the two `ApiError` literals unverified.

**Edit `/api/v1/agents/{agent_id}/commands`** (~line 429): the `post` operation's `responses` gains
`422` → `ScanSubnetNotReported`. Its `201`, `401`, `403`, `409` and `503` are untouched.

`AvailableSubnet` and the `AgentId` parameter are reused unchanged.

### 3.7 The trigger's reported-network check

`backend/src/api/services/commands.py` — `_claim_agent` (line ~291), after the `DeviceBusyError`
check and before `enqueue(...)`:

```
hello = agent_connections.get_hello(agent_id)
if hello is not None:
    _, reported = hello
    if subnet not in {entry.cidr for entry in reported}:
        raise SubnetNotReportedError
```

Four properties of this shape are load-bearing. Do not "simplify" any of them away.

1. **It only refuses on positive evidence.** `hello is None` — the Pi is disconnected, or connected
   but has not yet sent its hello — falls through unchanged. Nothing is known, so nothing is
   contradicted, and the existing unreachable-Pi behaviour stands.
2. **It must not raise `DeviceOfflineError` when there is no report.** Today's `503` is raised by
   `deliver()` *after* the command row exists, which is what makes the command `expired`
   (BACKEND.md B6 3e: `expired` is set synchronously with the 503). Raising it from `_claim_agent`
   would return a `503` with **no command row at all**, silently contradicting the lifecycle
   contract this feature is forbidden to touch.
3. **`SubnetNotReportedError` is declared in `services/commands.py`**, beside `AgentNotFoundError`,
   `DeviceBusyError` and `DeviceOfflineError` — **not** in `services/agents.py`. `agents.py`
   imports `active_command_for` from `commands.py`, so `commands.py` importing back would be a
   circular import. `agents.py` imports the exception from `commands.py`; the dependency runs one
   way only. `AgentOfflineError` stays in `agents.py`, since only the PATCH raises it.
4. **The check is against the report as of now**, not as of the moment the choice was stored. That
   is what makes a stale choice fail here rather than scan the wrong network.

`services/commands.py` already imports `agent_connections` for delivery, so no new import beyond
the exception class. The check is synchronous, runs inside the existing `run_in_threadpool` phase,
and touches no DB row.

**Comparison is exact string equality — do not normalise.** `SubnetCIDR`
(`schemas/scan.py:10`) is a bare regex with `strip_whitespace`; it does not parse addresses, so it
happily accepts `192.168.1.5/24` and even `999.999.999.999/99`. Reaching for
`ipaddress.ip_network(..., strict=False)` to make `192.168.1.5/24` match a reported
`192.168.1.0/24` is tempting and wrong here: the only client echoes back a string it received from
`available_subnets`, DMI-66 reports canonical CIDRs, and every non-exact value fails **closed** —
refused, never scanned. Parsing would add a second failure mode (malformed input raising inside the
enqueue path) to buy leniency nobody needs. Note the incidental hardening: before this check, a
regex-valid nonsense subnet like `999.999.999.999/99` was accepted and delivered to the Pi; now,
whenever a report exists, it is refused.

**Verified:** `tests/test_enqueue_command.py` never calls `set_hello`, so every existing test in it
resolves `hello is None` and passes unedited. That also means those tests now exercise the silence
branch rather than the validated one — which is why the new success case in §6 must register a
hello, or the validated path ships untested.

Router side, `backend/src/api/routers/agents.py` — `create_agent_command` gains one `except` arm.
It must be a **literal `ApiError` call in the handler body**, for the same AST-scan reason as §3.5:

```
except commands.SubnetNotReportedError as exc:
    raise ApiError(
        422, "That network is not one the Pi reported.", code="subnet_not_reported"
    ) from exc
```

Order the arms so `AgentNotFoundError` still maps to `403` first; the existing `DeviceBusyError`
and `DeviceOfflineError` arms are unchanged.

---

## 4. New files and naming (mandatory)

| Path | New / touched | What changes |
|------|---------------|--------------|
| `backend/alembic/versions/20260811_17_agents_target_subnet.py` | new | Revision `20260811_17` (down `20260810_16`): add nullable `agents.target_subnet`; downgrade drops it. No grants, no index. |
| `backend/src/api/models/command.py` | touched | `Agent` gains `target_subnet: str \| None = None`. Nothing else in the file changes. |
| `backend/src/api/schemas/agents.py` | new | `AgentSummary`, `AgentDetail`, `AgentListResponse`, `UpdateAgentTargetSubnetRequest`. Imports `AvailableSubnet` and `SubnetCIDR`. |
| `backend/src/api/services/agents.py` | new | `list_agents`, `get_agent_detail`, `set_target_subnet`, `AgentOfflineError`, one private response builder. Imports `SubnetNotReportedError` from `services/commands.py` — see §3.7(3), it must not be declared here. |
| `backend/src/api/services/commands.py` | touched | Declares `SubnetNotReportedError`; `_claim_agent` gains the reported-network check of §3.7. **Nothing else in this file changes** — not `enqueue`, `deliver`, `_record_delivery`, `sweep_stale_commands` or `active_command_for`. |
| `backend/src/api/routers/agents.py` | touched | Adds `list_agents_route`, `read_agent_route`, `update_agent_target_subnet_route`, `options_agents`, `options_agent`, and the imports they need. `create_agent_command` gains **one** `except commands.SubnetNotReportedError` arm raising a literal `ApiError(422, ...)`. The WebSocket route and existing preflight are untouched. |
| `contracts/openapi/openapi.yaml` | touched | New `/api/v1/agents` path (get + options); `patch` added to `/api/v1/agents/{agent_id}`; `422` added to the existing `post` on `/api/v1/agents/{agent_id}/commands`; `AgentDetail` gains two properties and one `required` entry; three new schemas; three new response components. |
| `frontend/src/types/openapi.d.ts` | touched (generated) | Regenerate with `npm run gen:types` from `frontend/` and commit. Not hand-edited. CI fails otherwise: `.github/workflows/ci.yml:184-190` regenerates and runs `git diff --exit-code -- src/types`. |
| `backend/tests/test_agents_target_subnet_migration.py` | new | Migration unit + live-column tests. Mirrors `tests/test_user_activity_migration.py`. |
| `backend/tests/test_agent_read_routes.py` | new | `GET /agents` and `GET /agents/{agent_id}`. Mirrors `tests/test_get_command.py` (client fixture, org-scoping seeds) and `tests/test_users_admin_routes.py` (list shape). |
| `backend/tests/test_agent_target_subnet_routes.py` | new | `PATCH /agents/{agent_id}` — success, 403, 404, 409, 422, re-choose. Mirrors `tests/test_users_admin_routes.py`. |
| `backend/tests/test_enqueue_command.py` | touched | Adds the §3.7 cases below. Existing assertions must keep passing untouched — they are the regression fence around DMI-64. |
| `backend/tests/test_contract_fidelity.py` | touched | `SCHEMA_NAMES` += `AgentSummary`, `AgentListResponse`, `AgentDetail`, `UpdateAgentTargetSubnetRequest`; `ERROR_RESPONSE_ROUTES` += `AgentOfflineConflict: ("agents.py", "update_agent_target_subnet_route", 409)`, `TargetSubnetNotReported: ("agents.py", "update_agent_target_subnet_route", 422)` and `ScanSubnetNotReported: ("agents.py", "create_agent_command", 422)`; `test_admin_operations_are_published` parametrize += `("/api/v1/agents", "get", "listAgents", {"200","401","500"})` and `("/api/v1/agents/{agent_id}", "patch", "updateAgentTargetSubnet", {"200","401","403","404","409","422","500"})`. If the POST on `.../commands` is already in that parametrize list, its expected status set gains `"422"`. |

### Call sites verified by grep — no change required

| Call site | Why it is safe |
|-----------|----------------|
| `backend/src/api/main.py:150` (`app.include_router(agents.router)`) | The router object is already mounted; new routes ride along. No registration edit. |
| `backend/src/api/management/provision_agent.py:63` (`Agent(...)`) | New column is nullable with a default. |
| 16 `Agent(...)` seeds across `backend/tests/` (`conftest.py:286`, `test_enqueue_command.py:81`, `test_get_command.py:69`, `test_agent_ws_channel.py:308,447`, `test_commands_service.py:27`, `test_worker_sweep.py:19`, `test_nonces.py:17`, `test_ingest_scan.py:62`, `test_scan_ingest_route.py:149`, `test_user_delete_routes.py:347`, plus the migration tests) | Same reason. |
| `backend/src/api/services/agent_connections.py` | Read-only reuse of `is_online` / `last_seen_at` / `get_hello`. **No new helper, no new field, no parallel presence path.** |
| `backend/src/api/services/commands.py:91` (`active_command_for`) | Called, not modified. Do not write a second active-command query. The **only** edits to this file are the two in §3.7. |
| `backend/src/api/schemas/commands.py` | `CreateCommandRequest.subnet` stays required. Untouched. |
| `backend/src/api/services/agent_presence.py` | Untouched; it is what keeps the `last_seen_at` fallback truthful. |
| `frontend/src/api/agents.ts` | Deliberately called by nothing. Out of scope (DMI-89). |
| `backend/tests/test_migrations.py` | Grant map and table set are unchanged by a column addition. |
| `.claude/docs/` code map, `docs/roadmap/BACKEND.md` | Updated by `/docs-sync` at the end of the pipeline, not by this spec. |

The `.claude/CLAUDE.md` `ScanRunner` / `ScanProgressScreen` rule does not apply: that is the
hardware-agent TUI scan pipeline, and this feature adds no orchestrator or runner parameter. The
grep discipline behind the rule was applied — the table above is its output.

---

## 5. Constraints

- **Reuse, do not re-implement.** `agent_connections.is_online()` / `last_seen_at()` /
  `get_hello()` are the only presence source. `AvailableSubnet` (`schemas/agent_frames.py:13`) is
  the only subnet type. `commands.active_command_for()` is the only active-command query.
- **Fence around the command write path, with one door.** `services/command_lifecycle.py`,
  `schemas/commands.py`, the WebSocket route, `enqueue`, `deliver` and the sweeper belong to DMI-64
  and are untouched. The single sanctioned change is §3.7: one refusal in `_claim_agent` and its
  `except` arm in `create_agent_command`. Anything beyond those two edits is out of scope. No
  "choose a network first" rule is added — the existing required `subnet` field already refuses.
- **Org scoping in SQL, not in the handler.** Every query filters `Agent.org_id == caller.org_id`.
  A foreign or unknown agent is `404` on both the read and the write, never `403`.
- **`online` and `available_subnets` are never written.** No column, no cache, no timestamp
  inference.
- **House style.** No comments or docstrings in new code, including tests, unless the code is
  genuinely non-obvious and the surrounding file already comments that kind of thing. Backend
  Python is hand-formatted.
- **Gates** (`.claude/CLAUDE.md`): `./database.sh` first, then from `backend/`:
  `uv run ruff check src tests` and `uv run pytest`. **Never** `uv run ruff format` or any
  repo-wide formatter. A run with database-test skips is not a green run — report the skip count or
  re-run with the database up. Frontend: only `npm run gen:types` plus `npm run typecheck` to prove
  the regenerated file compiles; no other frontend command is in scope.

---

## 6. Testing expectations

Every acceptance row in `TRUTH.md` has a home. `AC` = the Scenario column.

### `backend/tests/test_agents_target_subnet_migration.py` — mirror `test_user_activity_migration.py`

- Revision chain: `revision == "20260811_17"`, `down_revision == "20260810_16"`.
- `upgrade()` with `op.add_column` monkeypatched: exactly one column, `("agents",
  "target_subnet")`, `sa.String`, `nullable is True`, `column.index in (None, False)`.
- `upgrade()` with `op.execute` monkeypatched: **no statements** (proves no stray grant).
- `downgrade()`: exactly one `drop_column("agents", "target_subnet")`.
- Live (`postgres_engine`): `information_schema.columns` reports
  `("character varying", "YES")`, and `pg_indexes` has no index mentioning the column.
- Covers AC *Unchosen network reads as absent* at the storage level, and AC *Reported networks are
  never stored* / *Online is never stored* by asserting `agents` has **no** `online` and no
  `available_subnets` column after head (see §7 for the `connected_at` caveat).

### `backend/tests/test_agent_read_routes.py` — mirror `test_get_command.py` + `test_users_admin_routes.py`

Fixtures: the local `client` fixture overriding `get_session` with `administrative_session`;
`provisioned_agent`, `seeded_org`, `bearer_headers` from `conftest.py`. Simulated presence uses
`asyncio.run(agent_connections.register(agent_id, AsyncMock(), now=T0))` and
`agent_connections.set_hello(...)`, exactly as `test_enqueue_command.py` does; the autouse
`clear_agent_connections_registry` fixture cleans up.

| Test | AC covered |
|------|-----------|
| list returns one row with `online`, `last_seen_at`, `target_subnet`, `active_command_id`, and `data` keys exactly `{agent_id, display_name, online, last_seen_at, target_subnet, active_command_id}` | List the org's scanners |
| a second org's agent is absent from the caller's list | List is org-scoped |
| `available_subnets` is **not** a key on any list row | Reported networks belong to detail only |
| detail with a registered hello of two subnets returns both, in order, with `interface`, `cidr` and `is_default_route` (the wifi one `true`) | Detail reports both networks |
| detail for a never-connected agent → `available_subnets == []` and `last_seen_at is None`; detail after register→hello→unregister → `[]` and `last_seen_at` equal to the persisted row value, not `None` | Offline Pi reports nothing (+ the `last_seen_at` fallback decision) |
| **online flip**: register a socket → detail `online is True`; `agent_connections.unregister(...)` → detail `online is False`, same request otherwise | Online reflects the live connection |
| end-to-end flip through a real socket: `with client.websocket_connect(path, headers=ws_upgrade_headers(...)) as ws:` send `_hello_payload()`, `_sync(ws)`, then `client.get(detail)` inside the block asserting `online is True` and both subnets; after the block, `client.get(detail)` asserts `online is False` and `available_subnets == []` | Online reflects the live connection; Reported networks are never stored |
| after a hello, re-read the `agents` row from the session: it has no attribute/column carrying the reported subnets, and `target_subnet is None` | Reported networks are never stored |
| detail for an unknown uuid → 404; detail for another org's agent → 404 with an identical body | Unknown agent; List is org-scoped |
| viewer token reads both list and detail → 200 | Viewer may read |
| agent with a non-terminal command → both list row and detail carry that `active_command_id`; agent with only a `done` command → both `null` | Current command surfaces; No command in flight |

If issuing an HTTP request inside the `websocket_connect` block proves unreliable under the
TestClient portal (no existing test in the suite does it), split that one test: assert the
connected read via direct registry registration, and keep the real socket only for the
post-disconnect read. Both states stay covered; do not delete the flip assertion.

### `backend/tests/test_agent_target_subnet_routes.py` — mirror `test_users_admin_routes.py`

| Test | AC covered |
|------|-----------|
| connected Pi reporting two subnets, admin PATCHes one → 200, body is the full `AgentDetail` with the new `target_subnet`; a following `GET /agents` row and `GET /agents/{id}` both report it; DB row updated | Choosing a reported network |
| admin PATCHes a well-formed CIDR the Pi did not report → 422, `error.code == "subnet_not_reported"`, DB `target_subnet` unchanged | Choosing an unreported network |
| offline agent (nothing registered) → 409, `error.code == "device_offline"`, DB unchanged; and the connected-but-no-hello case → the same 409 | Choosing while the Pi is offline |
| agent already carrying a choice, admin picks the other reported subnet → 200 and the row holds only the new value | Re-choosing replaces |
| viewer token → 403, DB unchanged | Viewer may not choose |
| admin of org A PATCHes org B's connected agent → 404 (not 403), and B's `target_subnet` unchanged | Cross-org choose refused |
| unknown uuid → 404 | Unknown agent |
| body `{}`, an unknown extra key, or a malformed CIDR → 422 `validation_error` (the global handler), DB unchanged | contract hygiene for the request model |
| after a successful PATCH, `POST /agents/{id}/commands` with that subnet returns 201 and the command carries it; a POST with **no** `subnet` key is still 422 from `CreateCommandRequest` | Chosen network drives the scan; No network chosen blocks the scan |

### `backend/tests/test_enqueue_command.py` (edited) — the §3.7 check

Presence is simulated exactly as the file already does it: `agent_connections.register(...)` with an
`AsyncMock` socket, then `set_hello(...)` with the reported list. Every pre-existing test in this
file must keep passing **unedited** — if one needs a `set_hello` call it did not have before, that
is the signal that the check refuses too much, not a licence to rewrite the test.

| Test | AC covered |
|------|-----------|
| connected Pi reporting `192.168.0.0/24` and `10.12.0.0/16`, trigger names `192.168.0.0/24` → 201, command row created and delivered as before | Chosen network drives the scan |
| same Pi, trigger names a well-formed `172.16.0.0/24` it did not report → 422, `error.code == "subnet_not_reported"`, and **no `commands` row exists** for that agent afterwards | Unreported network cannot be scanned |
| agent whose stored `target_subnet` the Pi reported at PATCH time, then a reconnect whose `set_hello` reports a different set; trigger with the stored value → 422, and the `agents` row's `target_subnet` is **unchanged** | Stale choice is refused, not scanned |
| Pi registered but **no** `set_hello` yet, trigger any subnet → the pre-existing behaviour, not a 422 | Silence is not contradiction |
| Pi not registered at all, trigger any subnet → the pre-existing 503 `device_offline`, and the command row is `expired` exactly as `test_command_delivery.py` asserts | Silence is not contradiction; Everything else about triggering is untouched |
| busy agent (active command) with a reported subnet → still 409 `device_busy`, and the busy check still runs **before** the subnet check | Everything else about triggering is untouched |
| foreign-org agent → still 403, with no reported-subnet lookup reachable | Everything else about triggering is untouched |

### `backend/tests/test_contract_fidelity.py` (edited)

Parametrised additions cover AC *Contract published*: the four schemas fingerprint-match the app,
both new operations are published with `FrontendBearerAuth` and the exact status sets, and the two
pinned error codes match the literal `ApiError` calls in the handler.

### Suite-level

AC *Gates pass* is the `./database.sh` → `uv run ruff check src tests` → `uv run pytest` run, with
a zero skip count reported.

---

## 7. Concerns

1. **`device_offline` at two statuses — DECIDED 2026-08-11, keep the shared code.** The operator
   chose one code for one physical condition over a distinct `device_not_connected`: the SPA copy
   is the same sentence and the underlying condition really is identical. Two consequences are
   accepted knowingly. First, the published `DeviceOfflineError` description pins the code to
   delivery — "the command never reached the Pi … recorded as `expired`" — so the **409 must carry
   its own response component (`AgentOfflineConflict`) with its own description**, as §3.6
   specifies; do not collapse it onto `DeviceOfflineError` to save a stanza. Second, a metric that
   counts `device_offline` alone now mixes "a scan failed to dispatch" with "an admin opened the
   chooser while the Pi was down" — discriminate on `(status, code)` or `(route, code)`, never on
   the code by itself. Not an open question; do not reopen it at review.
2. **TRUTH's "no online value is persisted anywhere" is not literally true today, and the test must
   not assert it literally.** `agents.connected_at` already exists and is set on connect and
   cleared on disconnect by `agent_presence`, and `sweep_stale_commands` depends on it
   (`services/commands.py:171`). It is a persisted connection fact. The rule this feature must
   honour — and what the tests above assert — is that the API's `online` is computed from the
   registry and never read from or written to the database. A test asserting "no connection state
   is stored" would fail against DMI-64's design.
3. **422 carries two codes on the PATCH.** A malformed CIDR is rejected by the global
   `RequestValidationError` handler as `validation_error`; an unreported one by the handler as
   `subnet_not_reported`. Only the second is published, because `test_error_code_fidelity` pins the
   enum to the literal `ApiError` calls in the route. This matches every other route in the
   contract (only `POST /scans` publishes its `ValidationError`), but it does mean the published
   422 under-describes the operation.
4. **Revoked agents are still listed.** TRUTH puts revocation out of scope and no code path sets
   `revoked_at`, so I have specified no filter — inventing one would be speculative. The moment
   revocation ships, someone must decide whether a revoked Pi disappears from the list or shows as
   permanently offline. Cheap now, annoying later.
5. **`active_command_for` is not org-scoped** (`services/commands.py:91` filters on `agent_id`
   only). Safe here because the agent row is already org-checked before the call, but it is a
   latent footgun for the next caller. Not fixed here — DMI-64 owns that file.
6. **N+1 on the list.** One `active_command_for` per row. With the single-agent MVP this is one
   extra query; a grouped query would be premature and would mean not reusing the mandated helper.
   Revisit only if an org ever holds tens of agents.
7. **The published `GET /api/v1/agents/{agent_id}` declares a `403`** that `require_user` can never
   produce. Inherited from the contract written before the route existed. Left alone to keep the
   diff surgical; flagging it so it is a known inaccuracy rather than a surprise.
8. **`PATCH` on the agent resource is a shape risk, not a bug.** It is the right verb for a
   single-field update and matches `PATCH /users/{user_id}`, but the URL invites a future
   `display_name` or `revoked_at` to be smuggled in. `extra="forbid"` plus one required field is
   the guard; the reviewer of any future PR touching `UpdateAgentTargetSubnetRequest` should treat
   a second field as a product decision, not a refactor.
9. **Routed subnets are now unreachable by construction — the door, and where it is.** §3.7 means
   the product can only ever scan a network the Pi sits on directly. A subnet reachable through a
   gateway on the same segment is refused even by an admin who knows exactly what they are asking
   for. That matches the product today (FLOWS B4 is radio buttons over reported networks, never a
   CIDR field), and it was chosen knowingly on 2026-08-11. When it has to change, the change is in
   one place — the set comparison in `_claim_agent` — and it should arrive with an ADR, because
   "the scanner only scans what it is plugged into" is a security property people will have come to
   rely on, not merely a UI convenience.
10. **The 409 wins over the 422 on the trigger.** The busy check precedes the subnet check in
    `_claim_agent`, so a busy Pi with a stale stored subnet reports `device_busy` and the operator
    only discovers the stale network after the running scan finishes. Deliberate — busy is the
    condition they can act on right now — but it means the two refusals are not independent, and a
    test asserting both at once would be asserting the ordering, not the rules.
11. **The check trusts the last hello, not the wire.** Between the Pi's report and the trigger, its
    interfaces can change without a reconnect. The window is small and the Pi re-reports on every
    reconnect, but the backend's answer is only ever as fresh as the last frame. Closing that
    properly means asking the Pi at trigger time, which is a round trip on the critical path and a
    DMI-66 change; not worth it for the MVP, and worth remembering the first time someone reports a
    scan of a network the Pi "definitely isn't on any more".
