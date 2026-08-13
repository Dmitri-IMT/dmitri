# ARCHITECTURE — Give a failed scan a readable reason (DMI-75)

Spec: `specs/032-failed-scan-error-code/`. Truth: `TRUTH.md`. Prior decision: ADR-011 (Pi command
channel — lifecycle, `expired` vs `failed`).

This feature lives in `backend/` and `frontend/`. `hardware-agent/src` is **not touched**; one
backend test fixture that names a code no Pi emits is corrected (item 9 below). The CLAUDE.md
`ScanRunner` / `ScanProgressScreen` integration rule does not apply — no orchestrator parameter is
added and the TUI is not in the path.

---

## 1. System context

The pipeline this feature sits in is the **command channel**, not the scan pipeline:

```
operator clicks Scan now
  → POST /api/v1/agents/{agent_id}/commands   (commands.enqueue_for_agent)
      → commands row: queued
      → WS command frame to the Pi
          ├─ delivered   → commands.scan_id set + stub scans row created
          └─ send failed → commands row: expired, no scan_id, 503 device_offline
  → Pi reports status over WS (AgentStatusFrame) → commands.apply_status
      → mirrored onto scans.status via command_lifecycle.scan_status_for
  → stale sweep (worker poll + enqueue pre-check) → commands.sweep_stale_commands
      → queued → expired ; delivered/running/uploading → failed
  → reader: GET /api/v1/scans/{scan_id}   (services/read.get_scan_detail)
            GET /api/v1/commands/{command_id} (services/commands.get_command_detail)
```

Two defects make the failure reason unreachable today:

1. `services/read.get_scan_detail` hardcodes `command_id=None` (`services/read.py:170`), so a client
   cannot even address the second request.
2. `sweep_stale_commands` writes `status` with no `error_code`, so the most common real failure —
   a Pi that stops responding mid-scan — leaves a NULL reason in the only row that has one.

The fix is **read-time only**. The reason is derived from the command row when the scan is read;
nothing is denormalised onto `scans`, there is no migration, and there is no backfill.

**ADR-011 constraint that shapes the test plan.** An `expired` command carries **no `scan_id`** —
the DDL enforces `CHECK (scan_id IS NOT NULL OR status IN ('queued','expired'))` (ADR-011 §4). So
the `queued → expired` sweep branch **can never surface on a scan detail response**: no scan row
exists for it. That branch is observable **only** via `GET /api/v1/commands/{command_id}`. The
`delivered|running|uploading → failed` branch is observable on **both** endpoints. Tests must
target the right endpoint per branch.

Scope fences carried from TRUTH: `ScanSummary` / `list_scans` are unchanged (no code on list rows);
no retry UI; no Scans page (DMI-88 builds it and imports the copy deck). The deck ships with its
test and **no caller** — deliberate and approved.

---

## 2. Data model and contracts

### 2.1 The shared alias — `api/core/error_codes.py` (new)

The alias must be importable by **both** `api/schemas/read.py` and `api/schemas/commands.py`
without a cycle. The existing import graph decides the home:

- `schemas/read.py` imports only `api.core.severity`.
- `schemas/commands.py` and `schemas/agent_frames.py` import only `api.schemas.scan`.
- `api/core/` imports nothing from `api.schemas` or `api.services`.

Putting the alias in either schema module would make one schema module import the other, which is a
new edge in a graph that currently has none between `read.py` and `commands.py`. Putting it in
`api/core/` is a **leaf** and mirrors the existing precedent: `api/core/severity.py` holds the
`Severity` literal plus its domain rule for exactly this reason ("it lives here rather than beside
the response schemas so the model layer can import the domain without depending on the layer
above it").

New module `backend/src/api/core/error_codes.py`:

```python
from __future__ import annotations

from typing import Literal, get_args

ScanErrorCode = Literal[
    "device_offline",
    "device_busy",
    "agent_disconnected",
    "scan_failed",
    "invalid_command",
    "result_unavailable",
    "ingest_failed",
    "unknown",
]

SCAN_ERROR_CODES: frozenset[str] = frozenset(get_args(ScanErrorCode))

UNKNOWN: ScanErrorCode = "unknown"


def normalise_error_code(stored: str | None) -> ScanErrorCode | None:
    """Map a stored command error code onto the published set.

    NULL stays NULL; a code outside the published set becomes ``unknown``.
    """
    if stored is None:
        return None
    return stored if stored in SCAN_ERROR_CODES else UNKNOWN


def scan_error_code(scan_status: str, stored: str | None) -> ScanErrorCode | None:
    """The scan-detail rule: a failed scan always carries a reason, others never do."""
    if scan_status != "failed":
        return None
    return normalise_error_code(stored) or UNKNOWN
```

`normalise_error_code` is the single mapping rule; **both** `get_scan_detail` and
`get_command_detail` go through it. `scan_error_code` is a three-line wrapper that adds the
scan-status rule on top of it, so `services/read.py` carries no branching logic of its own.

Eight values, exactly. Plain strings, not ints, not a nested object. No `IntEnum`, no `StrEnum` —
a bare `Literal` matches `Severity`, `ScanStatus`, `ScanMode` and `CommandStatus`, and is what the
contract-fidelity fingerprint already expects (see §2.5).

### 2.2 `ScanDetailResponse` — new flat field

`backend/src/api/schemas/read.py`, in `ScanDetailResponse` (currently line 102-115), beside
`command_id`:

```python
error_code: ScanErrorCode | None = None
```

Flat, not nested. Optional with a `None` default, so it is **not** in `required` — matching
`command_id`, `metadata` and `highest_severity`. `model_config = ConfigDict(extra="forbid")` is
unchanged; `extra="forbid"` constrains input parsing only, and adding a declared field is additive
for every existing construction site.

`read.py` gains `from api.core.error_codes import ScanErrorCode` beside the existing
`from api.core.severity import Severity`.

`ScanSummary` is **unchanged**.

### 2.3 `CommandDetail` — type tightened

`backend/src/api/schemas/commands.py:47`:

```python
error_code: ScanErrorCode | None = None   # was: str | None = None
```

with `from api.core.error_codes import ScanErrorCode` added. Both endpoints now publish the same
type for the same concept.

**The implication that must not be missed.** `commands.error_code` is a free-text DB column
(`api/models/command.py:51`, `error_code: str | None = None`) fed from a deliberately permissive WS
frame. Any string can already be in there. `get_command_detail`
(`services/commands.py:72-92`) passes `command.error_code` **straight through** into `CommandDetail`
today. Tightening the schema without normalising there turns every legacy or version-skewed stored
value into a **pydantic `ValidationError` raised on read** — a 500 on `GET /commands/{command_id}`
for exactly the rows an operator most needs to see. The same normalisation rule therefore applies
on the command endpoint (§2.4).

### 2.4 Service changes

**`services/commands.py` — `get_command_detail` (line 72-92).** One line changes:

```python
error_code=normalise_error_code(command.error_code),
```

NULL stays NULL (a `queued` or `done` command has no reason and must not sprout one); an
unrecognised string becomes `unknown`. The scan-status rule of §2.2 does **not** apply here — this
endpoint reports the command's own record, and a command has statuses (`expired`, `done`) that the
scan-level rule knows nothing about.

**`services/read.py` — `get_scan_detail` (line 128-173).** Replace the hardcoded
`command_id=None` at line 170 and add the reason:

```python
command = commands.command_for_scan(session, scan_id)
...
    command_id=command.id if command else None,
    error_code=scan_error_code(scan.status, command.error_code if command else None),
```

Read-time join only, using the **existing** `commands.command_for_scan(session, scan_id)`
(`services/commands.py:103-105`). No new query helper.

*Import direction.* `services/commands.py` imports `api.models.*`, `api.schemas.agent_frames`,
`api.schemas.commands`, `api.services.agent_connections` and `api.services.command_lifecycle` — it
does **not** import `api.services.read`, and neither does anything it imports. `services/read.py` is
imported only by `routers/{scans,hosts,findings}.py`. So `read → commands` is a new edge into a
module that cannot reach back: **no cycle**. Import it the way `commands.py` itself imports its
sibling — module-form, not symbol-form:

```python
from api.services import commands
```

Module-form keeps the edge visible and survives any later symbol churn in `commands.py`.

*Note on scoping.* `command_for_scan` filters on `scan_id` only, with no `org_id` predicate. That is
safe here because `get_scan_detail` has already resolved the scan under `ScanRecord.org_id == org_id`
before the lookup runs, and a `scan_id` belongs to exactly one command. Do not "harden" it — that is
adjacent code.

**`services/commands.py` — `sweep_stale_commands` (line 160-212).** The `case()` expression that
already writes `status` and `completed_at` gains a third column, in the same `.values(...)`:

```python
error_code=case(
    (Command.status == "queued", "device_offline"),
    else_="agent_disconnected",
),
```

- `queued → expired` carries `device_offline` — the Pi was never connected to take the job. Per
  ADR-011 this row has no `scan_id`, so it is visible only on `GET /commands/{command_id}`.
- `delivered|running|uploading → failed` carries `agent_disconnected` — the Pi took the job and
  stopped responding. This is the failure TRUTH names as the most common one.

The `case()` reads `Command.status` pre-update, exactly as the two existing `case()` expressions in
the same statement already do; the three stay consistent by construction. No row is clobbered:
`NON_TERMINAL` excludes `failed`, so the sweep only ever touches rows whose `error_code` is NULL
(`apply_status` writes a code only on the terminal `failed`, which the sweep cannot select).

**`services/commands.py` — `apply_status` (line 107-157) stays exactly as it is.** It writes
`error_code` only when `status == "failed" and error_code is not None`. That is correct under this
design: a Pi that reports `failed` with a null code leaves NULL in the column, and NULL normalises
to `unknown` at read (§2.1). Writing a literal `"unknown"` at ingest time would destroy the
distinction between "the Pi said nothing" and "the Pi said something we do not publish", and would
be a write-time change to a read-time feature. Do not touch it.

### 2.5 The published contract — `contracts/openapi/openapi.yaml`

`contracts/openapi/openapi.yaml` is **hand-maintained** and gated by
`backend/tests/test_contract_fidelity.py`. Both `ScanDetailResponse` and `CommandDetail` are already
in that test's `SCHEMA_NAMES` tuple, so **no test-file edit is needed** — but both fingerprints move
and the YAML must move with them or the suite goes red.

What the gate compares (`test_schema_matches_contract` → `_schema_fingerprint`): for each schema,
`additionalProperties`, the sorted `required` list, and per property a shape of
`{type, enum (sorted), format, minimum, nullable}`. `$ref` is resolved before fingerprinting
(`_resolve_ref`), and `anyOf: [X, {type: 'null'}]` is folded into `{...X, nullable: true}`. So a
hand-written `$ref` to a named component fingerprints identically to FastAPI's inlined `Literal`.
This is already how `ScanStatus`, `ScanMode` and `CommandStatus` are written — Python `Literal`
aliases on one side, named YAML components on the other, green today. Follow that pattern.

Three edits:

1. **New component `ScanErrorCode`**, beside `CommandStatus` (~line 2120), in the same style:

```yaml
    ScanErrorCode:
      type: string
      enum:
        - device_offline
        - device_busy
        - agent_disconnected
        - scan_failed
        - invalid_command
        - result_unavailable
        - ingest_failed
        - unknown
```

2. **`ScanDetailResponse`** (~line 2436): add `error_code` to `properties`, after `command_id`.
   Do **not** add it to `required`.

```yaml
        error_code:
          anyOf:
            - $ref: '#/components/schemas/ScanErrorCode'
            - type: 'null'
```

3. **`CommandDetail`** (~line 2679): replace the existing untyped `error_code` block
   (`anyOf: [{type: string}, {type: 'null'}]`) with the same `$ref` form.

The naming is `ScanErrorCode` on both sides even though one of them is a command: it is one closed
set for one concept — why a scan failed — and TRUTH requires both endpoints to agree on the type.

`AgentStatusFrame` in the YAML is **unchanged** (see §2.6).

### 2.6 The inbound frame stays permissive — no change

`backend/src/api/schemas/agent_frames.py:35`, `AgentStatusFrame.error_code`, **remains
`str | None`**. Do not tighten it.

`AgentStatusFrame` has `extra="forbid"`; tightening the field would make a version-skewed Pi's
failure report fail validation. The frame would be rejected, the failure report lost, and the
command stranded non-terminal until the sweep eventually rewrote it — turning a truthful "the scan
failed for reason X" into a silent hang. TRUTH: "A newer field agent is never silenced by an older
backend." Unknown codes are accepted, stored verbatim, and normalise to `unknown` at read.

`backend/tests/test_agent_frames.py:106` asserts exactly this permissiveness by feeding
`"scan_timeout"` — an off-contract string — to `AgentStatusFrame`. **Leave that test alone**; it is
the guard for this decision, and replacing its string would delete the test's point.

### 2.7 Frontend — the copy deck

Per `frontend-conventions`: API types come only from `src/types/openapi.d.ts` via
`components['schemas'][...]`; never hand-write one. `npm run gen:types` regenerates that file from
`contracts/openapi/openapi.yaml` and must leave a clean diff. `erasableSyntaxOnly` is on — **no
`enum`**; a `Record` literal is the shape.

New file `frontend/src/lib/scanFailureReasons.ts`:

```ts
import type { components } from '@/types/openapi'

type ScanErrorCode = components['schemas']['ScanErrorCode']

// Approved copy (DMI-75). Every sentence names the Pi, says what happened, and ends with the
// operator's next action. No codes, no scanner output.
export const SCAN_FAILURE_REASONS: Record<ScanErrorCode, string> = {
  device_offline:
    "The Pi wasn't connected when the scan was requested. Check that it's powered on and online, then try again.",
  device_busy:
    'The Pi was already running another scan. Wait for it to finish, then try again.',
  agent_disconnected:
    "The Pi stopped responding while the scan was running. Check that it's powered on and online, then try again.",
  scan_failed:
    "The scan didn't finish on the Pi. Try again — if it keeps failing, contact support.",
  invalid_command:
    "The Pi couldn't read the scan request. Try again — if it keeps failing, contact support.",
  result_unavailable: 'The scan ran but produced no results to upload. Try again.',
  ingest_failed:
    "The Pi finished the scan but couldn't upload the results. Check its network connection, then try again.",
  unknown: 'The scan failed. No further detail was reported.',
}

export function scanFailureReason(code: string | null): string {
  if (code === null) return SCAN_FAILURE_REASONS.unknown
  const reasons: Record<string, string | undefined> = SCAN_FAILURE_REASONS
  return reasons[code] ?? SCAN_FAILURE_REASONS.unknown
}
```

Copy is verbatim and approved; **do not reword, re-punctuate, or "fix" the em dashes.**

**Why this exact shape (item 13 reconciled).** The two requirements pull in opposite directions and
are satisfied at two different times:

- *Compile time* — `Record<ScanErrorCode, string>` on the const is the drift gate. A code added to
  the YAML and pulled in by `npm run gen:types` widens the generated union and makes the object
  literal fail `tsc` with a missing-property error. `npm run typecheck` is in the gate, so a new
  backend code cannot ship without copy.
- *Runtime* — the **lookup** deliberately takes `string | null`, not `ScanErrorCode | null`, and
  reads through a widened `Record<string, string | undefined>` with a `??` default. The backend can
  publish a code before the frontend redeploys, and the browser must render a sentence rather than
  `undefined`. The widening is a local, deliberate `Record<string, …>` annotation, not an `as`
  cast on the caller's value — the caller never has to lie about its type.

TypeScript types are erased, so a Vitest **cannot enumerate the union at runtime**. State this
plainly: the union-coverage assertion is a *typecheck* obligation, and the test asserts the
observable behaviour that the type cannot (§4.3). The test additionally pins the key set as an
explicit literal array, so a code *removed* from the union — which `tsc` accepts silently, since a
narrower `Record` key type still permits the excess-property-free literal only via a widened
inference — fails loudly.

No page, no component, no hook, no query key, no route. The deck's only consumer today is its test.

---

## 3. New files and naming (mandatory)

| Path | New/Touched | What |
|------|-------------|------|
| `backend/src/api/core/error_codes.py` | **New** | `ScanErrorCode` `Literal` (8 values), `SCAN_ERROR_CODES`, `UNKNOWN`, `normalise_error_code(stored: str \| None) -> ScanErrorCode \| None`, `scan_error_code(scan_status: str, stored: str \| None) -> ScanErrorCode \| None`. Leaf module — imports nothing from `api.schemas` / `api.services`. |
| `backend/src/api/schemas/read.py` | Touched | `ScanDetailResponse` gains `error_code: ScanErrorCode \| None = None` (after `command_id`, ~line 113). Import the alias. `ScanSummary` untouched. |
| `backend/src/api/schemas/commands.py` | Touched | Line 47 `error_code: str \| None` → `ScanErrorCode \| None`. Import the alias. |
| `backend/src/api/services/read.py` | Touched | `get_scan_detail`: `from api.services import commands`; look up `commands.command_for_scan(session, scan_id)`; populate `command_id` for real (replaces the hardcoded `None` at line 170) and set `error_code=scan_error_code(scan.status, …)`. |
| `backend/src/api/services/commands.py` | Touched | `get_command_detail`: wrap the passthrough in `normalise_error_code`. `sweep_stale_commands`: add `error_code=case((Command.status == "queued", "device_offline"), else_="agent_disconnected")` to the existing `.values(...)`. `apply_status` **unchanged**. |
| `backend/src/api/schemas/agent_frames.py` | **Unchanged — do not edit** | `AgentStatusFrame.error_code` stays `str \| None` by design (§2.6). |
| `backend/src/api/models/command.py` | **Unchanged — do not edit** | `error_code: str \| None` stays a free-text column. No migration, no denormalised column on `scans`, no backfill. |
| `contracts/openapi/openapi.yaml` | Touched (hand-edited) | New `components.schemas.ScanErrorCode` enum; `ScanDetailResponse.properties.error_code` added (not required); `CommandDetail.properties.error_code` re-pointed at the `$ref`. `AgentStatusFrame` untouched. |
| `backend/tests/test_agent_ws_channel.py` | Touched (fixture only) | Lines 504 **and 513**: `"scan_timeout"` → `"scan_failed"`. No Pi in `hardware-agent/src` emits `scan_timeout`; the daemon emits `device_busy`, `scan_failed`, `invalid_command`, `result_unavailable`, `ingest_failed`. |
| `backend/tests/test_agent_frames.py` | **Unchanged — do not edit** | Line 106's off-contract `"scan_timeout"` is the deliberate permissiveness guard (§2.6). |
| `frontend/src/types/openapi.d.ts` | **Generated — never hand-edit** | Regenerate with `npm run gen:types` after the YAML edit; it gains `ScanErrorCode: "device_offline" \| … \| "unknown"` and the two `error_code` properties. Commit the generated diff. |
| `frontend/src/lib/scanFailureReasons.ts` | **New** | `SCAN_FAILURE_REASONS: Record<ScanErrorCode, string>` + `scanFailureReason(code: string \| null): string`. Verbatim approved copy. |
| `frontend/src/lib/scanFailureReasons.test.ts` | **New** | Vitest drift + behaviour gate. Beside the source, mirroring `frontend/src/lib/review.test.ts`. |
| `backend/tests/test_error_codes.py` | **New** | Unit tests for the pure helpers (§4.1). |
| `hardware-agent/**` | **Unchanged** | Out of scope. |

Nothing outside this table is created or edited. No new router, no new query, no new migration, no
new frontend page/component/hook.

---

## 4. Testing expectations

Mapped to the TRUTH acceptance-criteria table. Each row below names the gate and the existing test
file to mirror.

### 4.1 Pure helpers — `backend/tests/test_error_codes.py` (new)

No DB, no fixtures. Mirrors the shape of `backend/tests/test_read_schema.py` (plain unit asserts).

| Test | Asserts | TRUTH row |
|---|---|---|
| every published code round-trips | `normalise_error_code(c) == c` for all 8 | Reason on the scan |
| NULL stays NULL | `normalise_error_code(None) is None` | — |
| off-contract string normalises | `normalise_error_code("scan_timeout") == "unknown"` | Unrecognised code |
| the set is exactly eight | `len(SCAN_ERROR_CODES) == 8` and equals the literal set | Every code has a sentence |
| non-failed scan carries nothing | `scan_error_code(s, "scan_failed") is None` for `pending/accepted/processing/completed` | Never stale |
| failed scan is never bare | `scan_error_code("failed", None) == "unknown"`, and `== "unknown"` for an off-contract string | Never bare / No reason recorded |

### 4.2 Backend integration

| Area | File to add to | Mirror | Cases |
|---|---|---|---|
| `get_scan_detail` | `backend/tests/test_read_service_scans.py` | its existing `make_scan` / `read_factories` seeding | failed scan + command with a known code → that code, one request; failed scan + command with NULL code → `unknown`; failed scan with **no** command row → `unknown`; failed scan + command with an off-contract stored string → `unknown`; `completed` scan whose command holds `scan_failed` → `error_code is None`; **`command_id` is the real id, not null**; a scan list response is byte-identical to before (no `error_code` key on `ScanSummary`) |
| scan-detail route | `backend/tests/test_read_endpoints.py` | its existing `GET /api/v1/scans/{scan_id}` cases | the JSON body carries `error_code` and a non-null `command_id`; a non-failed scan's body has `error_code: null` |
| `get_command_detail` | `backend/tests/test_get_command.py` | its `_seed_command` helper and `TestClient` fixture | a stored off-contract code returns `200` with `"unknown"` (**not** a 500 — this is the §2.3 regression); a stored published code returns itself; a `queued` command returns `null`; **the `queued → expired` sweep branch is asserted here**, because ADR-011 forbids that row from having a `scan_id` |
| `sweep_stale_commands` | `backend/tests/test_commands_service.py` | its `T0` / `STALE` / `_seed_agent` helpers | stale `queued` → `expired` **and** `error_code == "device_offline"`; stale `delivered`/`running`/`uploading` → `failed` **and** `error_code == "agent_disconnected"`; the mirrored `scans.status` is still written; a swept `running` row's scan detail reports `agent_disconnected` |
| worker sweep still green | `backend/tests/test_worker_sweep.py` | — | no behaviour change expected; run it |
| permissive frame | `backend/tests/test_agent_ws_channel.py` | its existing failed-report case | after the fixture rename, add: reporting an **unpublished** code (e.g. `"warp_core_breach"`) keeps the socket open, stores the string verbatim, and `GET /commands/{id}` then reads `unknown` — TRUTH "Field agent ahead of backend" |
| contract | `backend/tests/test_contract_fidelity.py` | — | **no edit**; `ScanDetailResponse` and `CommandDetail` are already parametrised. It must go green off the hand-written YAML alone. |

### 4.3 Frontend — `frontend/src/lib/scanFailureReasons.test.ts` (new)

Mirrors `frontend/src/lib/review.test.ts`: plain Vitest beside the source, importing types via
`components['schemas'][...]`. No React, no MSW, no rendering.

| Test | Asserts | TRUTH row |
|---|---|---|
| deck covers the published set | `Object.keys(SCAN_FAILURE_REASONS).sort()` equals an explicit literal list of the 8 codes | Every code has a sentence |
| every sentence is present | each of the 8 lookups returns a non-empty string, asserted against the literal approved copy | Every code has a sentence |
| unknown code falls back | `scanFailureReason('warp_core_breach')` === the `unknown` sentence | Field agent ahead of backend |
| null falls back | `scanFailureReason(null)` === the `unknown` sentence | No reason recorded |
| copy is human | no sentence contains any of the 8 code strings, `_`, `nmap`, or `Traceback`; every sentence ends with `.` | Copy is human |

The compile-time half of the drift gate is `Record<ScanErrorCode, string>` plus `npm run typecheck`
in the gate — a type is erased, so no runtime test can enumerate the union. The explicit key list
above is the runtime complement.

### 4.4 Gates

**Backend** — from `backend/`:

```
./database.sh --test          # start Supabase, ensure dmitri_test, run the suite
uv run ruff check src tests
uv run pytest
```

A **non-zero skip count means NOT green**: without `DATABASE_URL_TEST` pointing at a live
`dmitri_test`, `conftest.py` skips every DB-backed test — which is most of §4.2 — and prints a
misleading pass. Re-run with the database up or say so.

**Never run `ruff format` (or any formatter) in `backend/`.** `ruff check` is the backend's only
Python gate; backend code is formatted by hand to match its neighbours.

**Frontend** — from `frontend/`:

```
npm run gen:types    # after the YAML edit; commit the diff
npm run lint
npm run typecheck
npm test
npm run build
```

`npm run format:check` if the local hook expects it. `npm run gen:types` must leave a clean diff on
re-run — if it does not, the YAML and the generated types have drifted.

---

## 5. Constraints and things that will bite

1. **ADR-011 `expired` has no `scan_id`.** The `device_offline` sweep branch is unreachable from
   `GET /scans/{scan_id}`. Do not write a scan-detail test for it; it will seed an illegal row and
   the DDL CHECK will reject it.
2. **`CommandDetail` tightening is a read-path hazard.** Ship §2.3 and §2.4 in the same change, or
   `GET /commands/{command_id}` starts 500ing on any legacy row.
3. **`extra="forbid"` is input-side.** Adding `error_code` to `ScanDetailResponse` does not break
   existing constructions, but any test that compares a full serialised body dict must gain the new
   key.
4. **The `case()` in `sweep_stale_commands` reads pre-update `Command.status`.** Correct, and
   consistent with the two `case()` expressions already there — do not "fix" it.
5. **`HUMAN_INFRA_REQUIRED`: none.** No new hardware, daemon, external tool, migration, or env var.

---

## 6. Not in this feature

`ScanSummary` / `list_scans`; any retry affordance; any Scans page or React component (DMI-88 owns
the screen and will import this deck); prose in the API payload; `hardware-agent/src`; any change
to the failure taxonomy beyond the two codes the sweep is now required to name.
