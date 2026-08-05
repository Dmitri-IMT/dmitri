# ARCHITECTURE — Scan ingest endpoint (DMI-63)

Turns `TRUTH.md` into paths, contracts and tests. No business rules restated here beyond what is
needed to name the code that enforces them. Backend-only; no `DESIGN.md`, no `INTEGRATION.md`.

## System context

```
Pi (signed POST /api/v1/scans)
  -> require_agent                         [api/dependencies/agent_auth.py — unchanged]
  -> ScanIngestRequest (pydantic, extra="forbid")   [api/schemas/scan.py]
  -> routers/scans.py: ingest_scan_route
  -> services/persistence.py: ingest_scan
       -> command_for_scan                  [services/commands.py — new]
       -> persist_scan                      [services/persistence.py — reworked]
            -> upsert_hosts_for_scan         [services/hosts.py — unchanged]
            -> _enqueue_enrichment_jobs      [services/persistence.py — unchanged]
            -> apply_status(..., "done")     [services/commands.py — unchanged, reused]
  -> ScanIngestAcceptedResponse, 202
```

This is the missing write half of the pipeline described in `docs/adr/ADR-011-pi-command-channel.md`
§5–§6: a `Command` may already have delivered a stub `ScanRecord` (`status=pending` and rising
through `accepted`/`processing` as the Pi reports over WS); this feature is what turns that stub
into a completed scan, or — for a scan nobody requested — creates one outright. It does not touch
discovery, NSE, the WS command channel, or enrichment job *processing* (`services/enrichment.py`,
`services/worker.py`), all of which are unchanged. The organisation and identity of the caller come
from `require_agent`'s `AgentIdentity` (`agent_id`, `org_id`) — never from the payload, which the
contract's `ScanIngestRequest` does not carry an org/device field for in the first place.

## The route

`POST /api/v1/scans`, mounted in `backend/src/api/routers/scans.py` alongside the existing
`GET /api/v1/scans` and `GET /api/v1/scans/{scan_id}`.

```python
@router.post("/api/v1/scans", response_model=ScanIngestAcceptedResponse, status_code=202)
def ingest_scan_route(
    payload: ScanIngestRequest,
    identity: AgentIdentity = Depends(require_agent),
    session: Session = Depends(get_session),
) -> ScanIngestAcceptedResponse:
```

- **Request model**: `ScanIngestRequest` (`api/schemas/scan.py`), the pydantic model FastAPI binds
  the body to. `model_config = ConfigDict(extra="forbid")` is what makes an unrecognised field a
  422 (criterion 16) rather than a silent drop; `Host.ip` / `Finding.ip` are `IPv4Address`, which is
  what makes an IPv6 address a 422 (criteria 18, 19) instead of a stored-then-broken value.
- **Response model**: `ScanIngestAcceptedResponse` (same module), status `202`.
- **`require_agent` reads the body first, and that is safe.** `require_agent` calls
  `await request.body()` to verify the signature; Starlette caches the raw body on first read, so
  FastAPI's own body-to-`ScanIngestRequest` parsing (which happens when it solves the `payload`
  parameter) re-reads the identical cached bytes — one read, two consumers, no conflict. **Ordering
  is what satisfies criterion 21** ("shape before identity is not leaked"): FastAPI resolves every
  sub-`Depends` in `dependant.dependencies` (here, `require_agent` and `get_session`) *before* it
  parses declared body parameters into their pydantic model. `require_agent` raising `HTTPException`
  (401/403) therefore aborts the request before `ScanIngestRequest` validation ever runs — an
  unsigned request with a schema-invalid payload gets 401, never 422. This is a property of FastAPI's
  dependency-solving order combined with declaring `payload` as a plain body parameter (not
  hand-parsed inside the handler); it is not something the handler code has to enforce, but a test
  must pin it down (see Testing).
- **The ordering has one documented exception: syntactically malformed JSON.** In
  `fastapi/routing.py`'s `get_request_handler`, the raw body is JSON-decoded *before*
  `solve_dependencies` is called, and a `json.JSONDecodeError` raises `RequestValidationError`
  immediately — so a body that is not valid JSON is a 422 even when the request is unsigned, and
  the 401-before-422 ordering does not apply to it. Only *model* validation (unknown field,
  missing field, IPv6) happens after dependency solving. This is upstream behaviour, not
  something to work around: criterion 21 is scoped to well-formed-but-invalid payloads and its
  test must use syntactically valid JSON, while criterion 28 asserts the malformed-JSON case is
  a 422 that stores nothing.
- **No new dependency composition primitive is needed** — this is the same `Depends(require_agent)`
  / `Depends(get_session)` shape every WS/command route already uses.

## `ingest_scan` / `persist_scan` rework

Two functions, both in `backend/src/api/services/persistence.py`:

```python
class ScanOwnershipError(Exception): ...
class ScanClosedError(Exception): ...

def ingest_scan(
    session: Session,
    scan: ScanIngestRequest,
    *,
    identity: AgentIdentity,
    now: datetime,
) -> ScanRecord: ...

def persist_scan(
    session: Session,
    scan: ScanIngestRequest,
    *,
    org_id: UUID,
    agent_id: UUID,
    command: Command | None,
    now: datetime,
) -> ScanRecord: ...
```

`ingest_scan` is the new orchestration entrypoint the route calls; it decides which of the three
cases applies and does not itself write anything. `persist_scan` keeps its existing job — write
hosts/ports/services/findings/enrichment jobs for one scan — but no longer decides idempotency
itself and no longer contains the artifact loop.

### The three cases

```python
existing = session.get(ScanRecord, scan.scan_id)

if existing is None:
    # Case A — unrequested scan (criterion 4). No placeholder, no Command row can
    # reference this scan_id (a Command's scan_id is only ever set atomically with the
    # stub ScanRecord in commands._record_delivery — see ADR-011 §5), so "no ScanRecord"
    # implies "no Command" and this is unambiguously a fresh, self-initiated scan.
    return persist_scan(session, scan, org_id=identity.org_id, agent_id=identity.agent_id,
                         command=None, now=now)

if existing.status == "completed":
    # Case B — repeated submission (criterion 15). Ownership re-checked so a foreign
    # device/org cannot probe an existing scan_id and learn it exists via a 202.
    if existing.agent_id != identity.agent_id or existing.org_id != identity.org_id:
        raise ScanOwnershipError
    return existing  # no writes, no commit

# Case C — filling a placeholder (criteria 1, 2, 12, 13).
command = command_for_scan(session, scan.scan_id)
if command is None or command.agent_id != identity.agent_id or command.org_id != identity.org_id:
    raise ScanOwnershipError
if is_terminal(command.status):
    raise ScanClosedError                     # criterion 27, before any write
return persist_scan(session, scan, org_id=identity.org_id, agent_id=identity.agent_id,
                     command=command, now=now)
```

**There is no race branch, deliberately.** An earlier draft caught a `ScanAlreadyRecorded` raised
when `apply_status` returned `False`, for "a concurrent identical submission that committed first".
That branch is unreachable. `ScanHostRecord` carries `UniqueConstraint("scan_id", "ip")`
(`models/persistence.py:55`) and `scans.scan_id` is the primary key, so of two concurrent
submissions: if the winner commits *before* the loser's `session.get(ScanRecord, ...)`, the loser
reads `"completed"` and takes Case B; if it commits *after*, the loser is already in the host loop,
its `scan_hosts` insert blocks on the winner's uncommitted row under READ COMMITTED, and raises
`unique_violation` at `flush()` — long before `apply_status` is reached. Either way the loser never
executes the `if not applied` line. Case A fails the same way on the `scans` PK.

So concurrent duplicate submission of one scan surfaces as an unhandled `IntegrityError` → `500`,
and that is accepted: no acceptance criterion asks for it, no real device produces it, and the
device's retry lands in the ordinary Case B repeat path (criterion 15). `apply_status` returning
`False` after the up-front `is_terminal` check now means a genuine internal inconsistency, so it
raises and 500s rather than being translated into a success. Operator decision, 2026-08-04.

`command_for_scan(session, scan_id) -> Command | None` is a new one-line lookup in
`services/commands.py` (`select(Command).where(Command.scan_id == scan_id)`, relying on the existing
`unique=True` on `Command.scan_id`).

**Why `existing.status == "completed"` is the correct idempotency test**: a placeholder scan starts
at `scan_status_for("delivered") == "pending"` (`command_lifecycle.py`) and only reaches
`"completed"` when this endpoint calls `apply_status(..., "done")`. There is no other path to
`"completed"` for a command-linked scan, and an unrequested scan (Case A) is created already
`"completed"`. So the status column alone distinguishes "not yet filled" from "already recorded" —
no extra flag is needed.

### `persist_scan` body

Unchanged in shape from today except:

1. The artifact loop (`for artifact in scan.artifacts: ...`) is deleted; `ScanIngestRequest` has no
   `artifacts` field to iterate.
2. Fill-vs-create replaces the old `existing = session.get(...); if existing is not None: return
   existing` early exit:
   ```python
   if command is None:
       scan_record = ScanRecord(scan_id=scan.scan_id, org_id=org_id, agent_id=agent_id,
                                 timestamp=scan.timestamp, subnet=scan.subnet,
                                 scan_mode=scan.scan_mode, metadata_json=scan.metadata,
                                 status="completed")
       session.add(scan_record)
   else:
       scan_record = session.get(ScanRecord, scan.scan_id)  # the placeholder; always present
       scan_record.timestamp = scan.timestamp
       scan_record.subnet = scan.subnet
       scan_record.scan_mode = scan.scan_mode
       scan_record.metadata_json = scan.metadata
       scan_record.agent_id = agent_id
       session.add(scan_record)
   session.flush()
   ```
3. **Every `session.commit()` inside the host/port/finding loop is deleted.** The three existing
   mid-function commits (after the scan insert, after the host/port loop, at the very end) become
   `session.flush()` or nothing — `flush()` is enough to get PKs back for the `scan_host_index` /
   `port_index` dicts the finding loop needs; nothing must be visible to another transaction until
   the whole scan is in.
4. At the very end, in place of the old final `session.commit()`:
   ```python
   if command is None:
       session.commit()
   else:
       applied = apply_status(session, agent_id=agent_id, command_id=command.id,
                               status="done", now=now)
       if not applied:
           raise RuntimeError("command moved past 'done' between the terminal check and commit")
   ```
   `ingest_scan` already refused a terminal command up front, so `applied is False` here means the
   command changed underneath an open transaction — an inconsistency, not an expected outcome. It
   raises and 500s; it is never translated into a `202`. (`apply_status` has already rolled the
   transaction back on that branch, so nothing is stored either way — criterion 14 still holds.)

### A written-off command is refused before anything is persisted

`apply_status`'s guard is `_STATUS_RANK < next_rank` (`services/commands.py:126`), and `done`,
`failed` and `expired` all have rank `4` (`command_lifecycle.py:12-14`). So a command already swept
to `failed` would produce a zero-rowcount `UPDATE`, `apply_status` would roll the whole transaction
back, and — left unhandled — the device would receive a `202` for results that were discarded. That
lying `202` is the thing to prevent; the discarding itself is the intended outcome (TRUTH criterion
27).

`ingest_scan` therefore checks for it **up front, in Case C, before `persist_scan` is called at
all**:

```python
if is_terminal(command.status):
    raise ScanClosedError
```

`is_terminal` is `command_lifecycle.py:37`, already exported and already the codebase's single
answer to "has this command finished". No new lifecycle rule, no new state, and `apply_status` is
neither modified nor parameterised.

Doing the check before any writing — rather than letting `apply_status`'s rollback discard a
half-built tree — matters for three reasons: the device gets a truthful `400` instead of a `202`;
no work is done building a scan tree that is guaranteed to be thrown away; and `apply_status`
returning `False` at the end of `persist_scan` is left meaning one thing only — an inconsistency
that should 500 (see above), never a written-off command being silently reported as accepted. The
two situations the reviewed draft conflated stay separate.

**Why refuse rather than revive.** `sweep_stale_commands` (`commands.py:165-170`) requires *both*
`Agent.connected_at IS NULL` — the WebSocket is currently down, cleared only by `mark_disconnected`
on socket close (`agent_presence.py:38`) — *and* `last_seen_at` older than
`command_disconnect_grace_seconds` (default **900s**, `core/config.py:80`). `mark_connected` resets
both the instant the Pi reconnects. A healthy Pi mid-scan keeps its socket open and is never swept
no matter how long the scan runs; being swept means the device dropped off and could not
re-establish a connection for fifteen continuous minutes. Additionally, a terminal command frees
that agent under the `NON_TERMINAL` partial unique index, so the operator has already been able to
re-trigger — late results may well be arriving alongside their own replacement. Operator decision,
2026-08-04.

**This is the single-transaction boundary that satisfies criterion 14.** `apply_status` (unchanged,
`services/commands.py:99`) does its own `session.commit()` on success and `session.rollback()` on a
zero-rowcount conditional `UPDATE`. Because every write this function made — the scan row, every
`ScanHostRecord`/`PortRecord`/`ServiceRecord`/`CPERecord`/`FindingRecord`/`RiskSnapshotRecord` from
`upsert_hosts_for_scan` and `upsert_finding`, every `EnrichmentJobRecord` — is only `flush()`ed
(sent to Postgres inside the open transaction, never committed) before this call, `apply_status`'s
own commit is the *only* commit for the whole submission: it either lands everything atomically or,
on the rollback branch, discards all of it and the placeholder scan reverts to exactly its
pre-submission row (still `pending`/`accepted`/`processing`, per whatever the Pi last reported over
WS) — which is exactly what criterion 14 asks for. For Case A (`command is None`) there is no
lifecycle to advance, so the function's own `session.commit()` is the single commit point instead;
the guarantee comes from `get_session`'s `with Session(...)` (`db/session.py:23`) closing on an
exception and rolling the open transaction back, which is why that path needs its own criterion-14
test (see Testing).

"The only commit for the whole submission" means the only commit *of ingested data* — auth has
already committed the nonce row on this same session, before any of this runs (see *Auth commits
before the handler*).

**Reusing `apply_status` is what satisfies "ingest advances the lifecycle" without a hand-written
status update** — no new state, no new transition, no new column drives it;
`scan_status_for("done") == "completed"` is already `command_lifecycle.py`'s existing projection.

**Late progress report (criterion 3) needs no new code.** `apply_status`'s rank guard
(`_STATUS_RANK < next_rank`) already makes any Pi `status` frame arriving after `done` a silent
zero-rowcount no-op (`services/commands.py:99`, exercised today by `agent_ws.py`'s
`_apply_status_frame`); a command already at `done`'s rank cannot be moved by a later `running`/
`uploading`/`failed` frame. This existing behaviour just needs a new test that names it under this
feature.

## Authorization of the scan_id

| Situation | Check | Refusal |
|---|---|---|
| Unsigned / bad signature / stale / replayed | `require_agent` (unchanged) | `401` |
| Signature valid, device revoked | `require_agent` (unchanged) | `403` |
| Signature valid, scan_id names a placeholder issued to **another** agent or org | `command.agent_id != identity.agent_id or command.org_id != identity.org_id` in `ingest_scan` | `403` (new `ScanOwnershipError`) |
| Signature valid, scan_id names an **already-completed** scan belonging to another agent/org | `existing.agent_id != identity.agent_id or existing.org_id != identity.org_id` in `ingest_scan` | `403` (new `ScanOwnershipError`) |
| Signature valid, own scan, but the command was already written off (`failed`/`expired`) | `is_terminal(command.status)` in `ingest_scan`, before any write | `400` (new `ScanClosedError`) |
| Payload shape (unknown field, missing required, IPv6) | pydantic `ScanIngestRequest` | `422` |

`400` is chosen for `ScanClosedError` over `403` because the request is well-authorized — the right
device submitting its own scan — and it is the *scan* that is no longer accepting results; `403` on
this operation is documented by the contract as the revoked-device case. The contract already
declares `400` for `ingestScan` with no `code` enum, so `DEFAULT_CODES_BY_STATUS[400]` covers it
and no contract change is needed. `409` would fit the semantics better but the contract does not
declare it, and inventing an undeclared status here would be exactly the drift this feature exists
to remove.

The router maps `ScanOwnershipError` to a plain `HTTPException(status_code=403, detail=...)` —
mirroring the existing `except commands.AgentNotFoundError as exc: raise HTTPException(403, ...)` in
`routers/agents.py:56`. No new `ApiError` code is introduced: the contract's `403` response for this
operation carries no `code` enum (unlike e.g. `PasswordChangeRejected`), so the default
`"forbidden"` envelope (`DEFAULT_CODES_BY_STATUS[403]`, `api/errors.py`) already matches it, and
`test_contract_fidelity.py`'s `ERROR_RESPONSE_ROUTES` table does not need a new entry for this
route.

Cross-organisation isolation (criterion 13) falls out of the same two checks: an org's device can
never name a scan_id whose `Command`/`ScanRecord` belongs to another org, because the ownership
comparison checks `org_id` alongside `agent_id` in both branches.

## Auth commits before the handler — what that does and does not affect

`require_agent` and the route share one `Session`: FastAPI caches `Depends(get_session)` per request,
so the `session` `require_agent` authenticates with *is* the `session` the handler writes with. And
authentication commits — twice: `prune_expired_nonces` (`services/nonces.py:29`) and `remember_nonce`
(`nonces.py:21`). `agent_auth.py:44-51` documents this as deliberate: a request whose signature
verifies durably burns its nonce before any handler work runs.

Three consequences:

- **Criterion 14 is unaffected.** Both commits land strictly before `ingest_scan` writes anything,
  so the ingest tree is still exactly one transaction, and `apply_status`'s `session.rollback()`
  unwinds to the post-nonce state — never further. Read "the single commit for the whole submission"
  below as *the single commit of ingested data*; the nonce row is auth's, is committed before ingest
  begins, and is meant to survive an ingest rollback.
- **Criterion 15 cannot be tested by re-sending the same bytes.** A byte-identical resend replays the
  nonce, so `authenticate_agent` raises `AgentUnauthenticated` and the request is `401` before
  `ingest_scan` is reached. Case B is reachable only by a **freshly signed** resubmission of the same
  payload (new `X-Timestamp`, new `X-Nonce`, new `X-Signature`, identical body). TRUTH criterion 15
  says "separately-proven" for this reason, and criterion 15a pins the 401 for the replay.
- **A device cannot retry identical bytes after a failure.** `400 ScanClosedError`, a `403`, or a
  transient `500` all leave the nonce burnt, so DMI-65 must be able to re-sign, not merely re-send a
  buffered request. This is the existing accepted tradeoff of insert-or-replay nonce semantics, not
  something this feature introduces; it is recorded here because DMI-65 depends on it.

## Idempotency

Handled entirely by the Case B branch above: a second identical submission for an
already-`"completed"` scan does zero writes and returns the existing row with the same shape as a
fresh success (`202`, same `scan_id`). `hosts_received` in that response is `len(payload.hosts)` —
the count in *this* submission, not a re-query of stored rows — since a client can only be
legitimately replaying its own prior payload (ownership already checked) and TRUTH does not require
detecting a payload that differs from the first one under the same `scan_id`; that divergence is out
of scope for this feature and is not exercised by any acceptance criterion.

## Data model / contracts

| Change | Where |
|---|---|
| `ScanRecord` gains `agent_id: UUID \| None` (nullable FK → `agents.id`, no index — no read surface queries it) | `api/models/persistence.py` |
| `ArtifactRecord` model deleted | `api/models/persistence.py` |
| `ScanResult` renamed `ScanIngestRequest`; `artifacts: list[Artifact]` field and the `Artifact` / `ArtifactKind` classes deleted | `api/schemas/scan.py` |
| `ScanIngestResponse` renamed `ScanIngestAcceptedResponse`; gains `status: Literal["accepted"]` and `model_config = ConfigDict(extra="forbid")` | `api/schemas/scan.py` |
| `Host` → `HostPayload`, `Port` → `PortPayload`, `Finding` → `FindingPayload`; each gains `model_config = ConfigDict(extra="forbid")` | `api/schemas/scan.py` |
| `ScanIngestRequest.hosts`/`.findings` and `HostPayload.mac`/`.ports` lose their defaults — required, matching the contract | `api/schemas/scan.py` |
| New `PortPayload` component (= existing `Port` + `cpes`); `HostPayload.ports` re-pointed at it; `Port` left untouched for the read path | `contracts/openapi/openapi.yaml` |
| `PersistedArtifact` class deleted; `PersistedScanDetail.artifacts` field deleted | `api/schemas/persistence.py` |

### Why the nested schemas are renamed and tightened

The reviewed draft kept `Host`/`Port`/`Finding` as-is on the grounds that "their wire shape already
matches the contract, only the OpenAPI component label differs cosmetically." That is wrong, and it
is what makes criterion 22 fail rather than pass. `test_contract_fidelity.py`'s `_property_shape`
(`:59`) resolves `$ref`s and, for array items carrying `properties`, recurses into
`_schema_fingerprint` (`:81-84` → `:90`) — which compares `additionalProperties`, `required` and the
full property key set. Component *names* are never compared; shapes are compared all the way down. Four real
divergences exist today:

| Contract | `api/schemas/scan.py` today |
|---|---|
| `ScanIngestRequest.required` includes `hosts`, `findings` | both `default_factory=list` → not required |
| `HostPayload.required` includes `mac`, `ports` | both defaulted → not required |
| `HostPayload` / `Port` / `FindingPayload` / `ScanIngestAcceptedResponse` are `additionalProperties: false` | only `ScanResult` sets `extra="forbid"`; the nested models emit no `additionalProperties` at all |
| `Port` properties are `port, protocol, state, service, version` | plus `cpes: list[str]` |

The `additionalProperties` row is also a live TRUTH bug independent of the test: today
`hosts[0].os = "linux"` is silently dropped, violating criterion 16. `api/schemas/read.py` already
carries `model_config = ConfigDict(extra="forbid")` on every one of its models (`read.py:19, 29, 63,
119`) for exactly this reason — the ingest schemas are the outlier, not the precedent.

The rename to `HostPayload`/`PortPayload`/`FindingPayload` is not cosmetic either. `read.py` defines
its own `Port` (`read.py:18`), and once `ScanIngestRequest` is mounted on a route both classes are
reachable from the app; FastAPI's model-name map sees the short-name collision and mangles one into
`api__schemas__scan__Port`. The fidelity test survives that (it follows `$ref`s), but the emitted
component names stop matching the contract's — precisely the drift criterion 22 exists to catch.
Adopting the contract's own names removes the collision and the drift together.

The device side already made this choice: `hardware-agent/src/agent/normalize/contracts.py` defines
`PortPayload`, `HostPayload`, `FindingPayload` under exactly those names. The backend is the outlier,
and the rename converges both halves of the pipeline on one vocabulary rather than inventing a third.

### The `cpes` contract correction

Contract `Port` has no `cpes` and is `additionalProperties: false`, so a contract-faithful payload
cannot carry CPEs at all. But `_persist_port` writes one `CPERecord` per `port.cpes`
(`services/persistence.py:223`) and `_enqueue_enrichment_jobs` builds every `nvd_cpe` job by
re-querying those rows (`persistence.py:236-249`) — so honouring the omission literally would make
the entire `nvd_cpe` branch permanently unreachable on the only path that ever feeds it, breaking
criterion 6. The device already parses CPEs out of nmap XML
(`hardware-agent/src/agent/utils/nmap_xml.py:40`), and neither the contract's inline example nor
`contracts/examples/scan_result.example.json` carries the field — the omission predates the ingest
path and is an oversight, not a decision. Operator decision, 2026-08-04: correct the contract.

The correction is a **new `PortPayload` component**, not an edit to `Port`. `Port` is referenced
three times (`openapi.yaml:1731` `HostPayload.ports`, `:1764` `ScanHostView.ports`, `:2122`
`HostDetailResponse.ports`), and the latter two are read schemas already pinned by `SCHEMA_NAMES`
whose Python counterpart (`read.Port`) deliberately has no `cpes`. Widening the shared component
would either break those two fingerprints or force CPEs onto the read surface, which TRUTH puts out
of scope. So:

```yaml
    PortPayload:            # ingest only; identical to Port plus cpes
      type: object
      additionalProperties: false
      required: [port, protocol, state, service]
      properties:
        # ...port, protocol, state, service, version exactly as Port...
        cpes:
          type: array
          items:
            type: string
            minLength: 1
          default: []
```

`HostPayload.ports.items.$ref` becomes `#/components/schemas/PortPayload`; `Port` is byte-identical
after the change, which is what makes criterion 22a hold. `cpes` stays optional with a `[]` default
(the frozen example payload omits it and must keep validating), so it is not added to `required`.

**Handoff to DMI-65, not work here.** `hardware-agent`'s `PortPayload`
(`normalize/contracts.py:18-24`) has no `cpes` either, so the device currently parses CPEs out of
nmap XML and then drops them at serialization. Adding the field there — and threading it from
`scanner/models.py:27` — is DMI-65's, and this feature must not touch `hardware-agent/**`. Until it
lands, the backend accepts `cpes` and no device sends any: `nvd_cpe` jobs are reachable and tested
but not yet produced in the field. Note it on DMI-65 so it is not re-derived.

Nothing else in `hardware-agent/tests/test_contract_models.py` is affected: its assertions read
`ScanMode`, `HealthResponse`, `HostSummary`, `ScanHostView` and the ingest example — none of which
this contract edit touches. Its `test_openapi_has_no_device_payload_or_devices_received` string scan
stays green (`PortPayload` contains neither forbidden substring).

Editing `openapi.yaml` obliges `cd frontend && npm run gen:types` (`frontend/package.json:12`) —
the regenerated `src/types/openapi.d.ts` gains a `PortPayload` type and no existing type changes.
That regeneration is the only frontend work this feature causes; TRUTH's "no frontend work" means
no *screen* work, and the two are not in conflict.

### Migration

One new revision, `backend/alembic/versions/20260804_14_scan_ingest_rework.py`
(`down_revision = "20260731_13"`), doing both schema changes this feature needs:

```python
def upgrade() -> None:
    op.add_column("scans", sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True))
    op.drop_table("artifacts")  # drops artifacts_id_seq with it (owned identity sequence)

def downgrade() -> None:
    op.create_table("artifacts", ...)  # mirrors 20260715_01_baseline.py's original definition
    op.drop_column("scans", "agent_id")
```

Both directions are pure schema operations on empty-or-untouched columns/tables — no data
transformation, no backfill — which is what makes criterion 25 ("existing data survives, upgrade is
reversible") trivially true: no existing row's `scan_id`, `hosts`, `findings`, or other columns are
touched. Alembic owns `dmitri_test`'s schema; do not run this via `supabase db reset|push|migration`
(per `.claude/CLAUDE.md`).

## New files and naming (mandatory)

| Path | Change |
|---|---|
| `contracts/openapi/openapi.yaml` | New `PortPayload` component (`Port` + `cpes`); `HostPayload.ports` re-pointed at it. `Port` itself unchanged. No other contract edit |
| `frontend/src/types/openapi.d.ts` | Regenerated via `npm run gen:types`; not hand-edited. Gains `PortPayload`, changes nothing else |
| `backend/src/api/schemas/scan.py` | `ScanResult` → `ScanIngestRequest`; `Host`/`Port`/`Finding` → `HostPayload`/`PortPayload`/`FindingPayload`; `extra="forbid"` on all four nested/response models; drop the defaults on `hosts`, `findings`, `mac`, `ports`; add `PortPayload.cpes`; delete `Artifact`, `ArtifactKind`, the `artifacts` field; `ScanIngestResponse` → `ScanIngestAcceptedResponse` + new `status` field |
| `backend/src/api/schemas/__init__.py` | Update all renamed exports (`Finding`, `Host`, `Port`, `ScanResult`, `ScanIngestResponse`) |
| `backend/src/api/services/hosts.py` | Import/annotation rename `ScanResult` → `ScanIngestRequest` (`hosts.py:13, 23`). Host-identity logic untouched |
| `backend/src/api/services/enrichment.py` | Import/annotation rename `Finding` → `FindingPayload` (`enrichment.py:14`) only. This is the sole exception to "no change to `services/enrichment.py`" — a rename with no behavioural effect |
| `backend/src/api/schemas/persistence.py` | Delete `PersistedArtifact`; delete `PersistedScanDetail.artifacts` |
| `backend/src/api/models/persistence.py` | Delete `ArtifactRecord`; add `ScanRecord.agent_id` |
| `backend/src/api/services/persistence.py` | Rework `persist_scan` (new signature, fill/create, single commit path); add `ingest_scan`, `ScanOwnershipError`, `ScanClosedError`; delete the artifact loop. No race-handling exception — see *There is no race branch* |
| `backend/src/api/services/commands.py` | Add `command_for_scan(session, scan_id) -> Command \| None`. `apply_status` is untouched |
| `backend/src/api/services/command_lifecycle.py` | **Unchanged** — `is_terminal` is reused as-is |
| `backend/src/api/routers/scans.py` | Add `ingest_scan_route` (`POST /api/v1/scans`, 202) |
| `backend/alembic/versions/20260804_14_scan_ingest_rework.py` | New migration: `scans.agent_id` + drop `artifacts` |
| `backend/tests/test_ingest_scan.py` | Update `persist_scan` call sites to the new keyword signature (`org_id`, `agent_id`, `command`, `now`); add tests for criteria 5, 6, 7, 14 through `ingest_scan` |
| `backend/tests/test_host_materialisation.py` | Update its four `persist_scan(session, scan)` call sites to the new keyword signature (`org_id=uuid4(), agent_id=uuid4(), command=None, now=...` — these tests exercise host identity, not ownership, so any fixed org/agent id is fine) |
| `backend/tests/test_ingest_schema.py` | Update `ScanResult`/`Host` → `ScanIngestRequest`/`HostPayload` imports; drop the `artifacts=[]` kwarg from the `PersistedScanDetail` construction. Its `devices`-rejection and IPv6-rejection cases keep working unchanged and stay. Add the nested-unknown-field and absent-list cases (criteria 16, 17) |
| `backend/tests/test_require_agent.py` | Delete or rewrite `test_no_product_route_mounts_require_agent` — it currently asserts `require_agent` is mounted on **no** product route; that becomes false the moment `POST /api/v1/scans` ships |
| `backend/tests/test_migrations.py` | `test_baseline_matches_model_metadata_and_security_fence` currently asserts every table the baseline creates has a same-named table in `persistence.SQLModel.metadata.tables`; add `"artifacts"` to a new `dropped_tables` allowance (skip the per-table shape comparison for it, mirroring the existing `dropped_columns` handling for `scans.target_mode`/`scan_profile`) or the lookup `persistence.SQLModel.metadata.tables["artifacts"]` raises `KeyError` once the model is deleted |
| `backend/tests/test_scan_ingest_migration.py` | New — upgrade/downgrade round-trip for `20260804_14`, mirroring `test_command_delivery_migration.py`'s shape |
| `backend/tests/test_scan_ingest_route.py` | New — full signed-request route tests (see Testing) |

## Constraints

- Reuse `require_agent`, `apply_status` and `is_terminal` as-is; no new auth mechanism, no new
  command status, no new transition, no new `ScanStatus`/`CommandStatus` enum member.
- `apply_status` is not modified, not parameterised, and not given a bypass flag. A finished
  command stays finished, whatever arrives afterwards.
- `ScanRecord.agent_id` is added nullable with **no backfill**. Every scan row predating this
  migration therefore has `agent_id IS NULL`, so Case B's ownership check would refuse a
  resubmission against one with `403`. Harmless — no ingest route has ever run, so no such row can
  legitimately be resubmitted — but it is a deliberate choice, not an oversight, and a test should
  not be written that assumes otherwise.
- No change to `services/worker.py`, `services/risk.py`, `services/nvd.py`/`kev.py`/`epss.py`, or
  `services/hosts.py`'s host-identity logic. `services/enrichment.py` and `services/hosts.py` change
  by import/annotation rename only (see the naming table) — if a diff to either touches anything but
  a renamed symbol, it is out of scope.
- The `contracts/openapi/openapi.yaml` edit is exactly one added component plus one re-pointed
  `$ref`. Any other contract change — a new status code, a widened `Port`, a renamed field — is out
  of scope and means a decision was made that TRUTH does not record.
- No new read endpoint, no new field on `ScanDetailResponse`/`ScanSummary` — the submitting device
  is recorded (`ScanRecord.agent_id`) but not surfaced; exposing it is a future read-path change, not
  this feature's.
- `413 PayloadTooLarge` is declared by the contract but not enforced by any code this feature adds —
  per TRUTH's "out of scope," whatever ceiling exists is the hosting platform's (Railway/uvicorn),
  not application logic.
- The contract also declares `options: /api/v1/scans` (`optionsScans`, CORS preflight) — no router in
  this codebase implements per-path `OPTIONS` for `/api/v1/hosts` or `/api/v1/findings` either, and
  that gap predates this feature and is not one of TRUTH's acceptance criteria. Do not add an
  `OPTIONS` handler as part of this work.
- `400 BadRequest` is declared but not emitted — matches the existing precedent for the two GET scan
  operations (`test_contract_fidelity.py::test_response_status_codes_not_compared_open_item_1`
  already asserts `contract_codes != app_codes` is acceptable).

## Testing expectations

Run with a live `dmitri_test` database (`./database.sh --test`); a bare `uv run pytest` skips every
DB-backed test in the files below and must not be reported as green. `ruff check src tests` is the
only lint gate — never `ruff format`.

Because this feature edits `contracts/openapi/openapi.yaml`, two gates outside `backend/` also run:
`hardware-agent`'s `uv run pytest` (its `test_contract_models.py` reads the contract directly), and
after `npm run gen:types`, the frontend's `npm run lint && npm run typecheck && npm test && npm run
build`. Both are expected to pass unchanged; a failure in either means the contract edit was wider
than the one added component.

| Area | File | Criteria | Notes |
|---|---|---|---|
| Route, full signed requests | `backend/tests/test_scan_ingest_route.py` (new) | 1, 2, 4, 8–13, 16–22 | Mirror `test_require_agent.py`'s `_headers()` signer helper and `provisioned_agent`/`agent_keypair`/`seeded_org` fixtures (`tests/conftest.py`). Build a real `Command` via `services.commands.enqueue_for_agent`-style setup (or the lower-level `_record_delivery`) to get a genuine placeholder scan for fill-path tests, rather than hand-inserting a `ScanRecord`. Cover: fills a requested scan and links it (1); request+scan both read completed after ingest (2); unrequested scan recorded, linked to device, no command (4); wrong-key / malformed / missing-header / stale / replayed signature all refused 401 with nothing stored (8–10, mirror the parametrization already in `test_require_agent.py`); revoked device 403 (11); another device's placeholder refused 403 and placeholder untouched (12); cross-org isolation (13); unknown field / missing required / IPv6 host / IPv6 finding all 422 (16–19); acknowledgement shape matches `ScanIngestAcceptedResponse` (20); unsigned + invalid-payload request is 401 not 422 (21 — the ordering property described above; the body must be **syntactically valid JSON** that fails model validation, e.g. an unknown field or an IPv6 address, since malformed JSON is decoded before dependencies run and is 422 by criterion 28); contract fidelity for the two ingest schema names (22, see below). |
| Idempotency + races | `backend/tests/test_scan_ingest_route.py` | 15, 15a | Submit the same body twice, **re-signing for the second call** (fresh timestamp/nonce/signature): second response is `202`, not an error, and row counts (`ScanHostRecord`, `FindingRecord`, `EnrichmentJobRecord`) are unchanged between the two calls. Then a third call re-sending the *first* request's headers verbatim asserts `401` (15a). Comment both: a test that re-sends identical bytes and expects `202` is testing the wrong thing and will fail on the nonce, not on the ingest logic. |
| All-or-nothing, Case C | `backend/tests/test_ingest_scan.py` | 14 | Call `persist_scan` directly with a `command` already at `done` — bypassing `ingest_scan`'s `is_terminal` guard, which is the only way to reach `apply_status`'s rollback branch — and assert it raises with **zero** rows written (query `ScanHostRecord`/`FindingRecord`/`EnrichmentJobRecord` after and assert empty). This proves the flush-then-single-commit boundary discards a failed attempt. Note in the test that this state is not reachable through the route; the reachable Case C refusal is the `400` covered by the criterion-27 row. |
| All-or-nothing, Case A | `backend/tests/test_ingest_scan.py` | 14 | The Case C test above only exercises `apply_status`'s rollback, which Case A never calls — so it does not cover criterion 14 for an unrequested scan. Add a test that injects a failure part-way through an unrequested-scan ingest (monkeypatch `upsert_hosts_for_scan` or `_enqueue_enrichment_jobs` to raise after some hosts are flushed), lets the exception propagate out of the session scope, and asserts on a **fresh session** that no `ScanRecord`, `ScanHostRecord`, `PortRecord`, `FindingRecord` or `EnrichmentJobRecord` for that `scan_id` exists. The mechanism is `get_session`'s `with Session(...)` (`db/session.py:23`) closing on exception, which rolls the open transaction back — implicit, load-bearing, and currently untested on this path. |
| Late results after a write-off | `backend/tests/test_scan_ingest_route.py` | 27 | Deliver a command, then drive it terminal the way production does — `sweep_stale_commands` with a `now` past the grace window, having set `Agent.connected_at = None` and `last_seen_at` well in the past — so it lands on `failed`; then submit valid signed results for its `scan_id`. Assert **`400`**, and that nothing was written: zero `ScanHostRecord`/`FindingRecord`/`EnrichmentJobRecord` rows for that `scan_id`, the command still `failed` with its original `error_code`, the scan row still `failed`. Asserting the status code alone is not enough — the point of the up-front check is that no tree is ever built, so assert the row counts too. Repeat for an `expired` command. |
| Malformed body | `backend/tests/test_scan_ingest_route.py` | 28 | A correctly signed request whose body is not valid JSON (sign the actual malformed bytes so the body hash still matches) gets `422` and stores nothing. Pair it with the criterion-21 test and note in both why one is 401 and the other 422 — they look contradictory otherwise. |
| Late progress report | `backend/tests/test_scan_ingest_route.py` or `test_command_lifecycle.py` | 3 | After a completed ingest, send a Pi `status` frame (`agent_ws.handle_agent_frame` or `apply_status` directly) with a lower-ranked status for the same `command_id`; assert it returns `False`/no error and the scan/command stay `completed`/`done`. |
| Machine identity, enrichment | `backend/tests/test_ingest_scan.py` (existing pattern) | 5, 6, 7 | `test_ingest_scan_accepts_enriched_findings_example` already covers 5/6 shape against `contracts/examples/scan_result.example.json` — update its `persist_scan` call to the new signature. Add one case sending the same MAC across two `ingest_scan` calls (mirroring `test_host_materialisation.py`) confirming `first_seen_at` does not move (7). |
| Ownership/idempotency unit-level | `backend/tests/test_ingest_scan.py` | 12, 13, 15 | Direct `ingest_scan()` calls (no HTTP) asserting `ScanOwnershipError` is raised for a mismatched `agent_id`/`org_id` in both the placeholder-fill and already-completed branches. |
| Contract fidelity | `backend/tests/test_contract_fidelity.py` | 22 | Add `"ScanIngestRequest"`, `"ScanIngestAcceptedResponse"`, `"HostPayload"`, `"PortPayload"` and `"FindingPayload"` to `SCHEMA_NAMES`. All five Python class names now match the contract's component names, so `test_schema_matches_contract` covers them with no new test function — but only *after* the schema tightening in the Data model section lands. Adding the names to a run against today's models fails on all four divergences listed there; that failure is the point, and the tightening is what fixes it. Listing the nested three explicitly (rather than relying on the fingerprint's recursion through `ScanIngestRequest`) is deliberate: it names the failing component in the pytest id instead of burying it inside a nested dict diff. |
| Read surface unaffected by the contract edit | `backend/tests/test_contract_fidelity.py` | 22a | No new test needed — `"ScanHostView"` and `"HostDetailResponse"` are already in `SCHEMA_NAMES` and both fingerprint through `Port`. If the `cpes` correction is ever mistakenly applied to `Port` instead of the new `PortPayload`, those two parametrizations fail. Verify by running them, and do not "fix" such a failure by adding `cpes` to `read.Port`. |
| Endpoint existence | `backend/tests/test_contract_fidelity.py` or new `test_scan_ingest_route.py` | 23 | `test_contract_fidelity.py` today only checks schema shape and GET query params, explicitly not path existence (see its docstring-equivalent `OPERATION_PATHS` usage). Add one assertion that `app.openapi()["paths"]["/api/v1/scans"]` has a `post` key with `operationId == "ingestScan"`, matching the contract. |
| Payload schema unit tests | `backend/tests/test_ingest_schema.py` | 16–19 | Existing `test_scan_result_rejects_*` cases (top-level unknown field, IPv6) keep their assertions under the new class names. **New cases are required**, because the tightening adds behaviour the old model did not have: an unknown key inside a `hosts[]` entry, inside a `hosts[].ports[]` entry, and inside a `findings[]` entry each raise `ValidationError` (16); an entirely absent `hosts` or `findings` key raises, while `hosts: []` validates (17); an absent `mac` or `ports` on a host raises, while `mac: null` validates (17). Also assert `contracts/examples/scan_result.example.json` still validates against the tightened model — it omits `cpes` and `artifacts` and must keep passing. |
| CPE enrichment | `backend/tests/test_ingest_scan.py` | 6 | A submission whose ports carry `cpes` produces one `EnrichmentJobRecord` with `job_type="nvd_cpe"` per distinct CPE, alongside the `nvd_cve`/`kev_cve`/`epss_cve` jobs the example payload already exercises. This is the criterion the contract omission would have silently broken, so it must be asserted directly rather than left to the existing example-based test (which carries no `cpes`). |
| Migration | `backend/tests/test_scan_ingest_migration.py` (new) | 24, 25 | Mirror `test_command_delivery_migration.py`: migrate to `20260731_13`, insert a scan row (and an `artifacts` row, to prove it is droppable), migrate to head, assert the `artifacts` table is gone and `scans.agent_id` exists and is nullable, migrate back down, assert `artifacts` is recreated and the prior scan row's other columns are untouched. |
| Migration baseline comparison | `backend/tests/test_migrations.py` | 24 | Update `test_baseline_matches_model_metadata_and_security_fence` per the naming-table note above so it tolerates `artifacts` being a baseline-only, since-dropped table. |
| `PersistedScanDetail` schema | `backend/tests/test_ingest_schema.py` | 24 | `test_persisted_scan_detail_uses_scan_mode_and_status` drops the `artifacts=[]` kwarg. |
