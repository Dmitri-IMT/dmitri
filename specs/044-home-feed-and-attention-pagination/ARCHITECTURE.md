# ARCHITECTURE — Home events, activity log, and attention paging (DMI-136)

Spec: `specs/044-home-feed-and-attention-pagination/`. Truth: `TRUTH.md`. Layout this completes:
`specs/042-design-system/DESIGN.md` §3 and §16 (v4 exemplar Events/Activity panels).

This feature lives in **`backend/`** and **`frontend/`** only. `hardware-agent/src` is **not
touched**; scan ingest already lands through `POST /api/v1/scans` and command delivery through
the existing WebSocket channel. The CLAUDE.md `ScanRunner` / `ScanProgressScreen` integration rule
**does not apply** — no orchestrator parameter is added and the TUI is out of scope (TRUTH v1).

Arena shape is **closed**: one composite `GET /api/v1/home` snapshot with three independent page
integers. No public `GET /activity`, `GET /events`, or `GET /home-attention` in v1.

---

## 1. System context

Home today is a **client-composed** read: four parallel HTTP calls (`GET /scans` ×2,
`GET /findings` ×2), client-side severity merge/sort, no Events or Activity panels, and no
attention pagination (`frontend/src/hooks/useHomeReview.ts` + `frontend/src/lib/review.ts`).
Writes (role change, invite, revoke, delete, scan ingest) mutate domain tables but leave no
org-scoped feed row.

This feature replaces that composition with **one org-scoped snapshot read** and **write-time
activity append** at the mutations that already own the facts:

```
signed-in member opens Home (/)
  → GET /api/v1/home?attention_page=&events_page=&activity_page=
      → read_home_snapshot (services/home.py)
          → page_attention          — one SQL list: critical then high, detected_at desc, latest scan
          → scan-health notices     — failed latest scan + stale coverage (STALE_COVERAGE_DAYS = 3)
          → derive_home_events      — box offline, member idle, machine first-seen (derived, not stored)
          → list_org_activity       — stored rows, newest first, role-specific text at read
  → Home.tsx renders verdict + optional attention table + Events + Activity panels

mutation (same transaction as today, plus append_activity):
  POST command delivered     → scan_started        (commands._record_delivery)
  POST scan ingest completes → scan_finished       (persistence.persist_scan)
  command/scan failed        → scan_failed         (commands.apply_status, sweep_stale_commands)
  host insert on ingest      → machine_first_seen  (hosts.upsert_hosts_for_scan)
  PATCH user role            → role_changed        (users.change_member_role)
  POST invite                → member_invited      (invites.create_invite)
  DELETE invite              → invite_revoked      (invites.revoke_invite, before hard delete)
  DELETE member              → member_removed      (users.delete_member, before hard delete)
  DELETE self                → account_deleted     (users.delete_self, before hard delete)
```

**Idle-member events** use `users.last_login_at` (“has not **signed in** for 60 days”), not
`last_seen_at`. Session refresh without login does not reset idle. This is a deliberate departure
from `specs/_scratch-044-home-feed/HOW.md` (which recommended `last_seen_at`); product language
in TRUTH is sign-in specific.

**Box offline events** use registry-then-DB last-seen (`agent_connections.last_seen_at(id) or
agents.last_seen_at`), skip when `is_online`, threshold `BOX_OFFLINE_DAYS = 3`. That is **not**
the stale-coverage notice (age of last **completed** scan, `STALE_COVERAGE_DAYS = 3`).

### Staging (binding on `/create-tasks`)

This feature is large — roughly 35 files across `backend/` and `frontend/`, fusing attention
paging, a stored activity log, and derived events. It stays **one** spec and one contract, because
splitting it would define `HomeSnapshot` in one feature and reshape it in the next two, churning
the OpenAPI YAML, the generated types, and the MSW fixtures for no delivery gain.

`TASKS.md` must therefore order the work in four stages, each leaving Home working:

| Stage | Content | State at the boundary |
|-------|---------|-----------------------|
| 1 | `activity` table, migration, `append_activity`, `activity_text` | No reader yet; nothing user-visible |
| 2 | `GET /home` with attention paging, notices, verdict; `events` and `activity` present and **empty**; Home UI switches to `useHome`; `useHomeReview` / `review.ts` deleted | Home works end to end; TRUTH user story 4 delivered |
| 3 | The nine mutation write sites (§2.3) + `ActivityPanel` | Activity panel fills |
| 4 | `derive_home_events` + `EventsPanel` | Events panel fills |

Empty `events` / `activity` arrays at stage 2 are the **final** wire shape with no rows yet, not a
stopgap the next stage removes — the CLAUDE.md no-temporary-code rule is satisfied. Stage 2 must
not ship a placeholder panel, a fake row, or a "coming soon" state; the panels render their real
empty state (TRUTH rules 12 and 19), which is behaviour stage 2 owes anyway.

The `Pagination` `label` prop (DESIGN §2.2) lands in stage 2, with its three other call sites.

---

## 2. Data model and contracts

### 2.1 Named constants — server owns values; frontend mirrors names

Module `backend/src/api/core/home_constants.py` (leaf — no imports from `api.schemas` /
`api.services`):

| Name | Value | Role |
|------|------:|------|
| `BOX_OFFLINE_DAYS` | `3` | Derived event: box not live and last-seen older than this |
| `MEMBER_IDLE_DAYS` | `60` | Derived event: `last_login_at` older than this (or null) |
| `MACHINE_FIRST_SEEN_RECENT_DAYS` | `7` | Derived event: `hosts.first_seen_at` inside window |
| `STALE_COVERAGE_DAYS` | `3` | Notice only: last **completed** scan age (unchanged semantics) |
| `HOME_ATTENTION_PER_PAGE` | `8` | Fixed attention page size — short enough for laptop fold |
| `HOME_EVENTS_PER_PAGE` | `5` | Events strip page size (v4 exemplar) |
| `HOME_ACTIVITY_PER_PAGE` | `8` | Activity log page size |

Frontend exports the three `HOME_*_PER_PAGE` names from `frontend/src/api/home.ts` (same integers).
**No `per_page` query param on `GET /home`.** Existing list routes (`GET /scans`, `/hosts`,
`/findings`) keep their own `per_page` params unchanged; Home never sends `per_page`.

### 2.2 Storage — new `activity` table

Model `ActivityRecord` in `backend/src/api/models/activity.py`:

```python
class ActivityRecord(SQLModel, table=True):
    __tablename__ = "activity"
    # id: int autoincrement PK — matches FindingRecord / PortRecord house style, and gives
    #     paging a monotonic tiebreaker (§2.4). Never on the wire.
    # org_id: UUID FK orgs.id, indexed
    # kind: str with CHECK ActivityKind
    # occurred_at: timestamptz
    # actor_user_id: UUID | None   — no FK (user row may be gone)
    # subject_id: UUID | None     — scan_id, host_id, user_id, or invite_id
    # payload: JSONB               — denormalised facts at write; never returned on wire
```

**Stored kinds** (`ActivityKind`):

```python
ActivityKind = Literal[
    "scan_started",
    "scan_finished",
    "scan_failed",
    "machine_first_seen",
    "role_changed",
    "member_invited",
    "invite_revoked",
    "member_removed",
    "account_deleted",
]
```

`invite_revoked` satisfies TRUTH (“unused invite withdrawn”) and the arena graft from Candidate 1;
it was missing from Candidate 2's sketch.

**Partial unique index** (idempotent appends on retries / races):

```sql
CREATE UNIQUE INDEX uq_activity_org_kind_subject
ON activity (org_id, kind, subject_id)
WHERE subject_id IS NOT NULL
  AND kind IN (
    'scan_started', 'scan_finished', 'scan_failed',
    'machine_first_seen', 'member_invited', 'invite_revoked'
  );
```

`role_changed`, `member_removed`, and `account_deleted` are **not** unique — the same person can
change role twice; removals are one-shot but need no uniqueness guard.

**Alembic** `backend/alembic/versions/20260905_19_home_activity_feed.py` (new):

- `down_revision = "20260904_18"` (current head: scan box and duration).
- `upgrade()`: create `activity` table (int identity PK), kind CHECK, partial unique index above,
  and the paging index `(org_id, occurred_at DESC, id DESC)` that serves `list_org_activity`.
- `downgrade()`: drop table/indexes.

**Migration ownership:** Alembic owns `dmitri_test` (`./database.sh --test`). Never run Supabase
CLI schema commands against `dmitri_test`.

No backfill migration — TRUTH excludes reconstructing history from deleted invites/users.

### 2.3 Write path — `append_activity`

Module `backend/src/api/services/activity.py`:

```python
@dataclass(frozen=True)
class ActivityAppend:
    org_id: UUID
    kind: ActivityKind
    occurred_at: datetime
    actor_user_id: UUID | None
    subject_id: UUID | None
    payload: dict[str, str]


def append_activity(session: Session, row: ActivityAppend) -> None:
    """Insert one feed row in the caller's transaction.

    Duplicate unique-key insert → no-op (ON CONFLICT DO NOTHING or IntegrityError catch).
    Does not commit; mutation site owns commit.
    """
```

**`occurred_at` is the API's own clock, for every kind without exception** — `utc_now()` evaluated
at the append site, never a timestamp that arrived over the wire. A Raspberry Pi has no
battery-backed RTC, so a box that boots before NTP syncs reports a `scan.timestamp`
(`hardware-agent/src/agent/scanner/runner.py:102`, stamped when the payload is built) that can
precede the server-stamped `scan_started` row. Mixing the two clocks would put *finished* above
*started* in a newest-first log and break the first TRUTH acceptance row. One clock also keeps `id`
order in agreement with `occurred_at` order, which the §2.4 tiebreaker relies on.

Consequence, stated in TRUTH: a scan that ran overnight and uploaded at 06:12 is logged at 06:12.
The scan's own domain timestamp is unaffected — it stays on `ScanRecord.timestamp` and still drives
the Home last-scan line and the stale-coverage notice.

**Transaction placement.** `_record_delivery` rolls back when a command leaves `queued` mid-send
(`services/commands.py:255-262`); appending inside that transaction is correct, because the rollback
must discard the `scan_started` row along with the stub `ScanRecord`.

**Payload keys** (denormalise at append; render `text` at read):

| Kind | Payload keys (minimum) |
|------|------------------------|
| `scan_*` | `scan_mode` |
| `machine_first_seen` | `hostname` |
| `role_changed` | `actor_email`, `target_email`, `new_role` |
| `member_invited` | `actor_email`, `invite_email`, `role` |
| `invite_revoked` | `actor_email`, `invite_email` |
| `member_removed` | `actor_email`, `target_email` |
| `account_deleted` | `email` |

Scan ingest and command paths pass `actor_user_id=None`. The admin who clicked Scan now is **not**
the actor of ingest/delivery rows.

**Write sites** (all in-process; no public append HTTP API):

| Kind | Service function | When | Actor |
|------|------------------|------|-------|
| `scan_started` | `commands._record_delivery` | Stub scan persisted on delivery | none |
| `scan_finished` | `persistence.persist_scan` | Scan ingest completes (`status` → completed path) | none |
| `scan_failed` | `commands.apply_status` | Terminal `failed`, after the `RETURNING` row proves the update won and `scan_id is not None` | none |
| `scan_failed` | `commands.sweep_stale_commands` | Per returned row where `command_status == "failed"` **and** `scan_id is not None` | none |
| `machine_first_seen` | `hosts.upsert_hosts_for_scan` | **Insert** of new `HostRecord`, **and** the org already had a completed scan before this one | none |
| `role_changed` | `users.change_member_role` | After role write, before commit | admin `caller.sub` |
| `member_invited` | `invites.create_invite` | After invite row flushed, before commit | admin `caller.sub` |
| `invite_revoked` | `invites.revoke_invite` | **Before** `session.delete(invite)` | admin `caller.sub` |
| `member_removed` | `users.delete_member` | **Before** `session.delete(user)` | admin `caller.sub` |
| `account_deleted` | `users.delete_self` | **Before** `session.delete(user)` | leaving user |

Router threading: `CallerIdentity.sub` and denormalised emails/names are passed into service
signatures from `routers/users.py` and `routers/invites.py`. Services must not re-query the actor
after a hard delete of that user.

Do **not** append at command enqueue — a queued command can expire without a scan.

**`scan_failed` always has a `scan_id` subject.** Both sites already hand it over and both already
guard the null case, so the append inherits the guard rather than adding one:

- `apply_status` (`services/commands.py:129-152`) filters on `Command.scan_id.is_not(None)`,
  `RETURNING`s the id, and rolls back when the update lost its race. Append **after** the
  `row is None` check and before `session.commit()`.
- `sweep_stale_commands` (`commands.py:186-212`) `RETURNING`s `(scan_id, command_status)` and
  already skips null `scan_id` when it updates `ScanRecord`. Append inside that same loop, under
  the same null guard, and only for the `failed` branch.

A `queued` command that expires (`expired` / `device_offline`, from the sweep or
`_expire_queued_command`) was **never delivered**, so it has no `scan_id` and no stub `ScanRecord`.
It writes **no** activity row: nothing started, so nothing failed. This keeps every `scan_failed`
row inside the partial unique index (which requires `subject_id IS NOT NULL`) and therefore
idempotent under a repeated sweep.

**Baseline scan suppression** (TRUTH rules 10 and 13a). `upsert_hosts_for_scan` inserts a
`HostRecord` for *every* host on an org's first scan, so an unguarded append writes one row per
machine and buries the scan rows. Guard it: append `machine_first_seen` only when the org has a
completed `ScanRecord` older than `scan_record.timestamp`. Compute that flag **once** before the
host loop (one `EXISTS` query), not per host. The scan rows themselves are always written.

The same flag suppresses the derived `machine_first_seen` events for that scan — see §2.4, where
the event query keys off `hosts.first_seen_at`, which equals the baseline scan's timestamp for
every host it introduced.

### 2.4 Read path — `read_home_snapshot`

Module `backend/src/api/services/home.py`:

```python
def read_home_snapshot(
    session: Session,
    *,
    org_id: UUID,
    role: str,
    attention_page: int,
    events_page: int,
    activity_page: int,
    now: datetime,
) -> HomeSnapshot:
    ...


def page_attention(
    session: Session, *, org_id: UUID, scan_id: UUID | None, page: int
) -> HomeAttentionPage:
    """Critical then high, newest findings.created_at first inside each severity, one OFFSET.

    Empty when there is no latest scan. Single query — do not concatenate two severity lists.
    """


def derive_home_events(
    session: Session, *, org_id: UUID, now: datetime
) -> list[HomeEvent]:
    """Current-state queries. Registry overlay for box last-seen.

    Sort: box_offline (longest quiet first), member_idle (longest idle first),
    machine_first_seen (newest first). Full list returned; snapshot handler slices page.
    """


def list_org_activity(
    session: Session, *, org_id: UUID, page: int, per_page: int
) -> tuple[list[HomeActivityItem], int]:
    """Newest first: ORDER BY occurred_at DESC, id DESC. Applies activity_text(role=...).

    The id tiebreaker is mandatory. One ingest writes scan_finished and every
    machine_first_seen row with the same occurred_at (the scan timestamp), so ties are
    guaranteed and OFFSET paging is otherwise non-deterministic. Descending id puts the
    later-written row first, which is what a newest-first log means: within one ingest the
    machine rows read above the scan_finished row that preceded them.
    """
```

**Latest scan pick** (attention + review state): same meaning as today's `getLatestScan` — newest
`scans.timestamp` for the org, **any status**. Latest **completed** scan (any status filter
`completed`) drives stale-coverage notice and the verdict's “last scan finished …” line.

**Attention SQL intent** (one list, stable order across pages):

```sql
WHERE scans.org_id = :org AND findings.scan_id = :latest_scan_id
  AND findings.severity IN ('critical', 'high')
ORDER BY CASE findings.severity WHEN 'critical' THEN 0 ELSE 1 END,
         findings.created_at DESC,
         findings.id DESC
OFFSET (:page - 1) * HOME_ATTENTION_PER_PAGE
LIMIT HOME_ATTENTION_PER_PAGE
```

**The `id` tiebreaker is mandatory, not decoration.** One ingest writes every finding through
`default_factory=utc_now` (`backend/src/api/models/persistence.py:142`), so `created_at` ties are
possible. Under a non-unique `ORDER BY`, Postgres may place a tied row on page 1 *and* page 2, or
on neither — which breaks TRUTH rule 1 ("order holds across pages"). `FindingRecord.id` is an
autoincrement int (`persistence.py:118`), so it is both unique and chronological.

Wire field `detected_at` on each row comes from `findings.created_at` via existing `FindingRead`
mapping (`read._to_finding_read`). Medium and low never appear on Home.

**Derived events rules:**

- **Box offline.** For each org `Agent`: effective last-seen =
  `agent_connections.last_seen_at(agent.id) or agent.last_seen_at`. Skip when
  `agent_connections.is_online(agent.id)`. Skip when last-seen is null or
  `now - last_seen <= BOX_OFFLINE_DAYS`. Copy: `{display_name} has been offline for {n} days`.
  Do not use `connected_at` (reconcile nulls it on process start).
- **Member idle.** SQL over `users` for `org_id` (Home uses `require_user`, not `GET /users`).
  Idle when `last_login_at IS NULL OR last_login_at < now - MEMBER_IDLE_DAYS`. Visible to **both**
  admin and viewer. Copy: `{given name or email} has not signed in for {n} days`.
- **Machine first seen recently.** `hosts.first_seen_at >= now - MACHINE_FIRST_SEEN_RECENT_DAYS`
  **and** `hosts.first_seen_at > baseline_at`, where `baseline_at` is the `timestamp` of the org's
  **earliest completed** scan. A machine whose `first_seen_at` is at or before `baseline_at` was
  part of the network the first scan mapped, not an arrival (TRUTH rule 10). `baseline_at` is one
  scalar subquery; when the org has no completed scan there are no hosts, so the clause is inert.
  Note `hosts.first_seen_at` is `min()`-ed across scans (`hosts.py:55`), so a host that appeared in
  the baseline scan can never later cross the threshold. Copy:
  `New machine joined the network: {hostname}`. Vocabulary is *machine*, not *device*.

**Activity viewer copy** (`activity_text` pure function in `activity.py`): same rows for admin
and viewer; only `text` differs. Scan and machine rows identical across roles. Admin may name
invite/role/remove verbs; viewer must not.

| Kind | Admin `text` | Viewer `text` |
|------|--------------|---------------|
| `scan_*` | `{Mode} scan started/finished/didn't finish` | same |
| `machine_first_seen` | `{hostname} first seen on the network` | same |
| `role_changed` | `{actor} changed {target}'s role to {role}` | `{target} is now a/an {role}` (`an` before `admin`) |
| `member_invited` | `{actor} invited {email}` | `{email} was invited` |
| `invite_revoked` | `{actor} withdrew the invitation for {email}` | `{email}'s invitation is no longer outstanding` |
| `member_removed` | `{actor} removed {target}` | `{target} is no longer a member` |
| `account_deleted` | `{email} deleted their account` | same |

The SPA prints `activity.data[].text` and `events.data[].text` verbatim — no client sentence
synthesis.

**Review state** on the snapshot:

| `review_state` | Condition |
|----------------|-----------|
| `blank` | No scan row for org (first-run) |
| `clear` | `review_count == 0` |
| `pending` | `review_count > 0` |

`review_count` = attention envelope `total` (critical+high on latest scan) + `len(notices)`.
Uses totals, not current page `data.length`. Notices (`failed_scan`, `stale_coverage`) stay in the
title block, outside the table — same placement as spec 042 §3.1.

When `review_state` is `clear`, the attention **table is not drawn**; Events and Activity panels
still render (TRUTH rule 20).

**Paging semantics:** each panel returns `{ data, total, page }`. A page past the end is **200**
with `data: []` and the real `total` (same as `GET /scans`). Changing `attention_page` refetches
the full snapshot; `events_page` and `activity_page` query params are unchanged (independent panel
state lives in React, not the URL — TRUTH out of scope).

**Transport errors:** one HTTP status for the whole snapshot. Empty panels are `200` with
`total: 0`. No nested per-panel error objects (arena rejection of Candidate 1's composite error
shape).

### 2.5 Wire schemas — `backend/src/api/schemas/home.py`

```python
class HomeListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class HomeAttentionPage(HomeListPage):
    data: list[FindingRead]


class HomeEventKind(str, Enum):  # or Literal on wire
    box_offline = "box_offline"
    member_idle = "member_idle"
    machine_first_seen = "machine_first_seen"


class HomeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: HomeEventKind
    text: str
    occurred_at: datetime


class HomeActivityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ActivityKind
    occurred_at: datetime
    text: str


class HomeNoticeKind(str, Enum):
    failed_scan = "failed_scan"
    stale_coverage = "stale_coverage"


class HomeNotice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: HomeNoticeKind
    text: str
    days: Annotated[int | None, Field(default=None, ge=0)] = None


class HomeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_state: Literal["blank", "clear", "pending"]
    review_count: Annotated[int, Field(ge=0)]
    latest_successful_scan: ScanSummary | None
    notices: list[HomeNotice]
    attention: HomeAttentionPage
    events: HomeListPage  # data: list[HomeEvent]
    activity: HomeListPage  # data: list[HomeActivityItem]
```

OpenAPI component names: `HomeSnapshot`, `HomeAttentionPage`, `HomeEvent`, `HomeActivityItem`,
`HomeNotice`, `HomeListPage` (events/activity reuse `HomeListPage` with typed `data` items in
documented `oneOf` or separate list types if fidelity tests require — implementer picks the
simplest shape that keeps `test_contract_fidelity.py` green).

`FindingRead` fields on attention rows match `FindingRecord` in OpenAPI (existing schema).

### 2.6 Router — `GET /api/v1/home`

`backend/src/api/routers/home.py`:

```python
@router.get("/api/v1/home", response_model=HomeSnapshot)
def get_home(
    attention_page: int = Query(1, ge=1),
    events_page: int = Query(1, ge=1),
    activity_page: int = Query(1, ge=1),
    caller: CallerIdentity = Depends(require_user),
    session: Session = Depends(get_session),
) -> HomeSnapshot:
    return read_home_snapshot(
        session,
        org_id=caller.org_id,
        role=caller.role,
        attention_page=attention_page,
        events_page=events_page,
        activity_page=activity_page,
        now=utc_now(),
    )
```

Register in `backend/src/api/main.py`: `from api.routers import …, home` and
`app.include_router(home.router)`.

Auth: `require_user` (any org member). Idle-member events do not require opening admin-only
`GET /users`.

### 2.7 Published contract — `contracts/openapi/openapi.yaml`

Hand-maintained; gated by `backend/tests/test_contract_fidelity.py`.

Add path `GET /api/v1/home` with query parameters:

```yaml
    HomeAttentionPageFilter:
      name: attention_page
      in: query
      required: false
      schema: { type: integer, minimum: 1, default: 1 }
    HomeEventsPageFilter:
      name: events_page
      ...
    HomeActivityPageFilter:
      name: activity_page
      ...
```

No `per_page` parameters on this operation.

Add component schemas (properties mirror §2.5). Reuse `#/components/schemas/FindingRecord` for
attention row items and `#/components/schemas/ScanSummary` for `latest_successful_scan`.

Update `SCHEMA_NAMES` in `backend/tests/test_contract_fidelity.py` with new schema names.

Regenerate frontend types: `npm run gen:types` → commit `frontend/src/types/openapi.d.ts`.

### 2.8 Service signature changes (mutation threading)

Extend these functions to accept actor context; routers pass `caller.sub` and loaded emails:

| Function | New parameters (illustrative) |
|----------|-------------------------------|
| `users.change_member_role` | `*, actor_user_id: UUID, actor_email: str` |
| `users.delete_member` | `*, actor_user_id: UUID, actor_email: str` |
| `users.delete_self` | (actor is `user.id` / `user.email` — no router change beyond append call inside service) |
| `invites.create_invite` | `*, actor_user_id: UUID, actor_email: str` |
| `invites.revoke_invite` | `*, actor_user_id: UUID, actor_email: str` |

`hosts.upsert_hosts_for_scan` gains append on insert inside its existing loop (no actor).

Scan/command append helpers may live as private functions in `activity.py` called from
`commands.py` / `persistence.py` to keep payload shape in one module.

### 2.9 Frontend — single query Home

Replace the four-read hook with one snapshot hook:

```ts
// frontend/src/api/home.ts
export const HOME_ATTENTION_PER_PAGE = 8
export const HOME_EVENTS_PER_PAGE = 5
export const HOME_ACTIVITY_PER_PAGE = 8

export function getHome(pages: HomePages): Promise<HomeSnapshot> {
  return apiClient.get('/home', {
    params: {
      attention_page: pages.attentionPage,
      events_page: pages.eventsPage,
      activity_page: pages.activityPage,
    },
  })
}
```

```ts
// frontend/src/hooks/useHome.ts
export function useHome(pages: HomePages): HomeView
// HomeView = loading | error | blank | clear | pending wrapping HomeSnapshot + retry()
```

`Home.tsx` holds three `useState(1)` page integers. Each panel mounts `Pagination` with
`total <= perPage → null` (Foundations icon-only previous/next). Attention table pagination uses
`HOME_ATTENTION_PER_PAGE`; changing attention page refetches via `queryKeys.home.snapshot(pages)`
without resetting events/activity state.

**Removed from Home path** (orphan once migrated):

- `frontend/src/hooks/useHomeReview.ts` and `useHomeReview.test.ts`
- `frontend/src/lib/review.ts` and `review.test.ts` — verdict/notice logic moves server-side;
  backend tests absorb the stale-coverage boundary cases.

**New panel components** (DESIGN §3 completion): `EventsPanel`, `ActivityPanel`, optional
`HomeSidePanels` wrapper for layout gap/step-12 below attention. Names match `AttentionTable.tsx`.

`AttentionNotices` consumes `snapshot.notices[].text` (server-rendered). `AttentionTable` accepts
paginated `attention.data` plus pagination props.

`queryKeys.ts` gains:

```ts
home: {
  snapshot: (pages: HomePages) => ['home', 'snapshot', pages] as const,
},
```

MSW: add `GET /home` handler in `frontend/src/test/mswHandlers.ts`; retire the four-endpoint Home
fixture wiring in `Home.test.tsx`.

---

## 3. New files and naming (mandatory)

| Path | New/Touched | What |
|------|-------------|------|
| `backend/src/api/core/home_constants.py` | **New** | Threshold and page-size constants (§2.1). |
| `backend/src/api/models/activity.py` | **New** | `ActivityRecord`, `ActivityKind` CHECK. |
| `backend/src/api/schemas/home.py` | **New** | `HomeSnapshot`, nested wire types (§2.5). |
| `backend/src/api/services/activity.py` | **New** | `ActivityAppend`, `append_activity`, `activity_text`. |
| `backend/src/api/services/home.py` | **New** | `read_home_snapshot`, `page_attention`, `derive_home_events`, `list_org_activity`, notice builders. |
| `backend/src/api/routers/home.py` | **New** | `GET /api/v1/home` (§2.6). |
| `backend/src/api/main.py` | Touched | `include_router(home.router)`. |
| `backend/src/api/services/commands.py` | Touched | `_record_delivery` → `scan_started`; `apply_status` / `sweep_stale_commands` → `scan_failed` when scan terminal failed. |
| `backend/src/api/services/persistence.py` | Touched | `persist_scan` → `scan_finished` on completed ingest. |
| `backend/src/api/services/hosts.py` | Touched | `upsert_hosts_for_scan` → `machine_first_seen` on host insert only. |
| `backend/src/api/services/users.py` | Touched | Actor params + `append_activity` on role change, member remove, self delete (insert before hard delete). |
| `backend/src/api/routers/users.py` | Touched | Thread `caller.sub` + actor email into user service calls. |
| `backend/src/api/services/invites.py` | Touched | Actor params + `append_activity` on create; `invite_revoked` before delete on revoke. |
| `backend/src/api/routers/invites.py` | Touched | Thread `caller.sub` + actor email into invite service calls. |
| `backend/alembic/versions/20260905_19_home_activity_feed.py` | **New** | `activity` table + indexes (§2.2). |
| `contracts/openapi/openapi.yaml` | Touched | `GET /home`, schemas, page query params; no `per_page`. |
| `backend/tests/test_contract_fidelity.py` | Touched | Extend `SCHEMA_NAMES` for Home schemas. |
| `backend/tests/test_activity_service.py` | **New** | `append_activity` idempotency, `activity_text` admin/viewer matrix. |
| `backend/tests/test_home_snapshot.py` | **New** | `read_home_snapshot`, `page_attention` order, notices, review_state, paging past end. |
| `backend/tests/test_home_events.py` | **New** | `derive_home_events` thresholds, registry overlay, idle on `last_login_at`. |
| `backend/tests/test_home_route.py` | **New** | HTTP: auth, query validation, envelope shape. |
| `backend/tests/test_users_service.py` | Touched | Activity rows on role change / deletes. |
| `backend/tests/test_invite_service.py` | Touched | Activity on invite create / revoke. |
| `backend/tests/test_command_delivery.py` | Touched | `scan_started` row on deliver. |
| `backend/tests/test_ingest_scan.py` | Touched | `scan_finished` + `machine_first_seen` on ingest. |
| `backend/tests/test_hosts_service.py` | Touched | First-seen append only on insert (mirror if file exists; else cover in ingest test). |
| `frontend/src/types/openapi.d.ts` | **Generated** | `npm run gen:types`. |
| `frontend/src/api/home.ts` | **New** | `getHome`, page-size constants. |
| `frontend/src/api/queryKeys.ts` | Touched | `home.snapshot`. |
| `frontend/src/hooks/useHome.ts` | **New** | Single-query Home state machine. |
| `frontend/src/hooks/useHome.test.ts` | **New** | MSW matrix: blank/clear/pending/error/retry; independent page params. |
| `frontend/src/hooks/useHomeReview.ts` | **Removed** | Replaced by `useHome`. |
| `frontend/src/hooks/useHomeReview.test.ts` | **Removed** | Replaced by `useHome.test.ts`. |
| `frontend/src/lib/review.ts` | **Removed** | Logic moved to `read_home_snapshot`. |
| `frontend/src/lib/review.test.ts` | **Removed** | Cases move to `test_home_snapshot.py`. |
| `frontend/src/pages/Home.tsx` | Touched | `useHome`; three page states; side panels on all non-error states that show feed. |
| `frontend/src/pages/Home.test.tsx` | Touched | MSW `GET /home`; pagination; viewer copy; empty panel states. |
| `frontend/src/pages/home/AttentionTable.tsx` | Touched | Pagination props; `ListSurface` or table + `Pagination` below. |
| `frontend/src/pages/home/AttentionNotices.tsx` | Touched | Render server `notices[].text`. |
| `frontend/src/pages/home/EventsPanel.tsx` | **New** | Events list + pagination; empty state. |
| `frontend/src/pages/home/ActivityPanel.tsx` | **New** | Activity list + pagination; empty state. |
| `frontend/src/pages/home/EventsPanel.test.tsx` | **New** | Verbatim `text`, empty state, pagination visibility. |
| `frontend/src/pages/home/ActivityPanel.test.tsx` | **New** | Timestamp + `text` cells, empty state, pagination visibility. |
| `frontend/src/pages/home/HomeSidePanels.tsx` | **New** | Layout wrapper for Events + Activity (step-12 gap). |
| `frontend/src/test/mswHandlers.ts` | Touched | Default `GET /home` fixture; export snapshot builders. |
| `frontend/src/components/Pagination.tsx` | Touched | Required `label` prop → nav `aria-label` (DESIGN §2.2). |
| `frontend/src/components/ListSurface.tsx` | Touched | Required `pagination.label`, forwarded. |
| `frontend/src/pages/Scans.tsx`, `Network.tsx`, `agents/DeviceScanHistory.tsx` | Touched | Pass `pagination.label`. |
| `docs/ui/FOUNDATIONS.md` | Touched | §Pagination: nav named per surface. |
| `frontend/src/pages/Settings.tsx` | Touched | New `settings-activity-note` privacy copy (TRUTH rule 23, DESIGN §1). |
| `frontend/src/pages/Settings.test.tsx` | Touched | Assert the new disclosure sentence. |
| `hardware-agent/**` | **Unchanged** | Out of scope. **`ScanRunner` and `ScanProgressScreen` not threaded.** |

Nothing outside this table is created or edited unless a gate fails and requires a fixture fix.

---

## 4. Testing expectations

Mapped to TRUTH acceptance criteria. Each row names the gate and the file to mirror.

### 4.1 Activity write path — `backend/tests/test_activity_service.py` (new)

No HTTP. Mirror `backend/tests/test_error_codes.py` style for pure `activity_text`.

| Test | Asserts | TRUTH row |
|------|---------|-----------|
| Duplicate `scan_started` same `subject_id` | second append no-op | — |
| Pi clock behind server | ingest whose `scan.timestamp` predates the `scan_started` row still logs `scan_finished` above it | Box clock is wrong |
| Tied `occurred_at` across a page boundary | rows sharing one `occurred_at` page without repeat or gap; newest-written first | Newest first (rule 18) |
| `activity_text` viewer `role_changed` | no forbidden verb | Viewer parity |
| `activity_text` viewer `member_invited` | neutral wording | Viewer parity |
| `invite_revoked` viewer text | “no longer outstanding” | Invite withdrawn |

### 4.2 Home snapshot service — `backend/tests/test_home_snapshot.py` (new)

Mirror `backend/tests/test_read_service_scans.py` for DB fixtures.

| Test | Asserts | TRUTH row |
|------|---------|-----------|
| Attention order page 1 vs 2 | critical before high; `created_at` desc stable across pages | Attention overflow |
| Tied `created_at` across a page boundary | seed findings sharing one `created_at` spanning pages 1–2; assert the union is every row, no repeat, no gap | Attention overflow |
| `review_count` vs page rows | count uses `total`, not `data.length` | Title count honest |
| `review_state=clear` | zero findings and no notices | Short attention / clear |
| Page past end | `200`, `data: []`, `total` unchanged | — |
| Stale coverage boundary | exactly `STALE_COVERAGE_DAYS` vs +1 day | (migrated from `review.test.ts`) |
| Failed latest scan notice | `notices` contains `failed_scan` | — |

### 4.3 Derived events — `backend/tests/test_home_events.py` (new)

| Test | Asserts | TRUTH row |
|------|---------|-----------|
| Box offline 4 days, not live | event with day count | Box offline |
| Box online despite old DB last-seen | skipped when registry live | — |
| Member `last_login_at` 61 days ago | idle event | Member idle |
| Session refresh only | `last_seen_at` fresh, `last_login_at` stale → still idle | Idle = sign-in |
| Host first seen yesterday, org already had an earlier completed scan | `machine_first_seen` event | New machine |
| Baseline scan hosts | org's first completed scan finds 3 hosts → **zero** `machine_first_seen` events | Baseline scan is quiet |
| No events | empty `events.data`, panel-safe | No events |

### 4.4 Mutation integration

| Area | File | Cases |
|------|------|-------|
| Role change | `test_users_service.py` | row with actor + target; viewer `text` via snapshot read |
| Member delete | `test_users_service.py` | row survives after user gone | Delete survives |
| Invite revoke | `test_invite_service.py` | row before invite hard delete | Invite withdrawn |
| Expired queued command | `test_command_delivery.py` / sweep tests | queued→expired writes **no** activity row (no `scan_id`) |
| Scan deliver | `test_command_delivery.py` | `scan_started` | Scan start |
| Ingest complete | `test_ingest_scan.py` | `scan_finished` | Scan finish |
| Host insert | ingest/host tests | `machine_first_seen` on a **second** ingest that adds a host | — |
| Baseline ingest | ingest/host tests | first ingest for the org writes scan rows but **no** `machine_first_seen` rows | Baseline scan is quiet |

### 4.5 HTTP — `backend/tests/test_home_route.py` (new)

Mirror `backend/tests/test_read_scans.py`.

| Case | Assert |
|------|--------|
| `GET /api/v1/home` authed | `200`, `HomeSnapshot` shape |
| `attention_page=0` | `422` |
| Viewer role | same activity kinds/totals as admin; differing `text` only | Viewer parity |

Contract: `test_contract_fidelity.py` green after YAML edit.

### 4.6 Frontend

| File | Asserts | TRUTH row |
|------|---------|-----------|
| `useHome.test.ts` | loading/error/retry; blank/clear/pending | — |
| `useHome.test.ts` | change `attentionPage` does not reset other pages in query key | Independent paging |
| `useHome.test.ts` | a page change keeps the previous snapshot visible; no `home-loading` after first load | Independent paging |
| `Home.test.tsx` | pagination hidden when `total <= perPage` | Short attention list |
| `Home.test.tsx` | Events + Activity empty states render | No events |
| `Home.test.tsx` | viewer sees invite/role rows with neutral copy | Viewer parity |
| MSW | compile after `gen:types` | — |

### 4.7 Gates

**Backend** — from repo root / `backend/`:

```
./database.sh --test          # zero skips; dmitri_test required
uv run ruff check src tests    # never ruff format
uv run pytest
```

Never report the backend suite green if skip count is non-zero.

**Frontend** — from `frontend/`:

```
npm run gen:types
npm run lint
npm run typecheck
npm test
npm run build
```

---

## 5. Constraints and things that will bite

0. **Two clocks.** `scan.timestamp` is the Pi's clock at payload build; `occurred_at` is the API's.
   Never assign one from the other (§2.3). `ScanRecord.timestamp` keeps the Pi value — that is the
   scan's domain time and drives the last-scan line and stale coverage.
1. **Findings list order today is wrong for paging.** `list_findings` orders by `findings.id asc`;
   Home attention must **not** reuse that query. `page_attention` owns its own `ORDER BY` (§2.4).
2. **Coverage stale ≠ box offline.** Same 3-day number, different clocks — do not merge notices
   into derived events.
3. **Registry overlay is mandatory** for box offline. SQL-only last-seen disagrees with Devices
   while the box is connected.
4. **`last_login_at` is not on `GET /users`.** Idle events query `users` inside `home.py`; do not
   expose `last_login_at` on member JSON as part of this feature.
5. **Insert before hard delete.** `append_activity` must run before `session.delete` on users and
   invites; `actor_user_id` has no FK so rows survive deletion.
6. **Snapshot refetch coupling.** Changing attention page refetches events/activity payloads too —
   accepted arena cost for one document. `useHome` sets `placeholderData: keepPreviousData` so the
   untouched panels hold their rows instead of blinking (DESIGN §10 Q2).
7. **No backfill.** Revoked invites and removed members before this ships are gone; activity starts
   at deploy.
8. **`HUMAN_INFRA_REQUIRED`: none.** No new hardware, daemon, or env var.

---

## 6. Not in this feature

Email/push notifications; compliance audit trail or retention policy; configurable thresholds or
page sizes; infinite scroll; URL-synced page numbers; medium/low on Home; public list routes for events/activity; backfilling historical
activity; hardware-agent / TUI / `ScanRunner` / `ScanProgressScreen`; Supabase CLI against
`dmitri_test`; nested per-panel HTTP errors inside the snapshot.
