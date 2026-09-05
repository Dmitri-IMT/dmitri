# Tasks — Home events, activity log, and attention paging (`044-home-feed-and-attention-pagination`)

10 tasks. **Unblocked now: #1, #5**

> **This feature's blast radius is `backend/` *and* `frontend/`. The agents differ per task** —
> each task's `Layer` line names them. Do not spawn the Python agents on a frontend task.
>
> | Layer | Test agent | Review agent | Gate |
> |---|---|---|---|
> | `backend/` | `test-engineer` | `code-reviewer` | `./database.sh --test` **first**, then `uv run ruff check src tests` + `uv run pytest` |
> | `frontend/` | `frontend-test-engineer` | `frontend-code-reviewer` | from `frontend/`: `npm run lint && npm run typecheck && npm run test && npm run build` |
>
> **Never run `uv run ruff format` or any repo-wide formatter** (`.claude/CLAUDE.md`). `ruff check`
> is the backend's only Python gate; `backend/` is formatted by hand to match its neighbours.
>
> **A backend run with database skips is not green.** Without `DATABASE_URL_TEST` pointing at a live
> `dmitri_test`, `conftest.py` *skips* every DB-backed test and prints a false pass. Every backend
> task here touches the database. If the skip count is non-zero, say so or re-run with the database
> up. Alembic owns `dmitri_test` — never point `supabase db reset|push|migration` at it.
>
> **The `ScanRunner` / `ScanProgressScreen` threading rule does not apply.** `hardware-agent/` is
> untouched: no orchestrator parameter is added and the TUI is out of scope
> (`ARCHITECTURE.md` §Scope note, `TRUTH.md` out-of-scope).

## Staging (binding — from `ARCHITECTURE.md` §1)

The spec fixes four stages, each leaving Home working. Tasks may not be reordered across a stage
boundary.

| Stage | Tasks | State at the boundary |
|---|---|---|
| 1 | #1 | `activity` table and writer exist; nothing user-visible |
| 2 | #2 #3 #4 #5 #6 #7 | Home works end to end on one snapshot; **TRUTH user story 4 delivered** |
| 3 | #8 #9 | Activity panel fills |
| 4 | #10 | Events panel fills |

**Empty `events` / `activity` arrays at stage 2 are the final wire shape with no rows yet, not a
stopgap.** Stage 2 ships the panels rendering their real empty state (`TRUTH.md` rules 12 and 19),
which is behaviour it owes anyway. No placeholder panel, no fake row, no "coming soon" — the
`.claude/CLAUDE.md` no-temporary-code rule is in force.

## Rules that apply to every task

1. **`TRUTH.md` is the behaviour source.** Every acceptance row it lists is gated by a named test
   below. A task may not soften a criterion to make its own suite pass.
2. **Paths come from the naming tables** — `ARCHITECTURE.md` §3 and `DESIGN.md` §6. Do not invent
   files. Nothing outside those tables is created or edited unless a gate fails and needs a fixture
   fix.
3. **`occurred_at` is always the API's own clock** (`utc_now()` at the append site), never a
   timestamp that arrived over the wire (`ARCHITECTURE.md` §2.3). A Raspberry Pi has no
   battery-backed RTC; mixing clocks puts *finished* above *started* in a newest-first log.
4. **Both paged queries carry an `id` tiebreaker.** `ORDER BY … , id DESC` is mandatory, not
   decoration — without it OFFSET paging can repeat a row on two pages or drop it from both
   (`ARCHITECTURE.md` §2.4).
5. **Insert before hard delete.** `append_activity` runs before `session.delete` on users and
   invites; `actor_user_id` carries no FK so rows survive the deletion.

---

## Task 1: `activity` table, `append_activity`, and `activity_text`
- **Layer**: `backend/` — `test-engineer` / `code-reviewer`
- **Description**: Stage 1. Create the `activity` store and its two pure-ish functions per
  `ARCHITECTURE.md` §2.2 and §2.3. `ActivityRecord` with an **int autoincrement PK** (house style,
  and the monotonic tiebreaker rule 4 relies on), `org_id`, `kind` under a CHECK, `occurred_at`,
  nullable `actor_user_id` (**no FK**), nullable `subject_id`, JSONB `payload`. Migration
  `20260905_19_home_activity_feed.py`, `down_revision = "20260904_18"`, creating the table, the
  kind CHECK, the partial unique index `uq_activity_org_kind_subject`, and the paging index
  `(org_id, occurred_at DESC, id DESC)`. `append_activity` inserts one row in the caller's
  transaction and **does not commit** — a duplicate on the unique key is a silent no-op.
  `activity_text(kind, role, payload)` renders the admin/viewer sentence matrix in
  `ARCHITECTURE.md` §2.4. No callers yet.
- **Absorbed**: nothing.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/activity.py`, `backend/src/api/services/activity.py`,
  `backend/alembic/versions/20260905_19_home_activity_feed.py`,
  `backend/tests/test_activity_service.py`]
- **Tests**: `backend/tests/test_activity_service.py` — proves the duplicate append is a no-op
  rather than an `IntegrityError` escaping the caller's transaction, and pins every cell of the
  admin/viewer text matrix.
- **Success Criteria**:
  - Migration applies and reverses cleanly on `dmitri_test`; head advances from `20260904_18`.
  - A second `append_activity` with the same `(org_id, kind, subject_id)` for a guarded kind leaves
    exactly one row and raises nothing.
  - `role_changed`, `member_removed`, `account_deleted` are **not** guarded — two `role_changed`
    rows for the same target both persist.
  - `append_activity` does not commit: a caller that rolls back leaves no row.
  - `activity_text` viewer output for `role_changed`, `member_invited`, `invite_revoked`,
    `member_removed` names **no** action a viewer cannot take (no "invited", "changed … role",
    "removed"). Admin output names the actor and target. — *TRUTH: Viewer parity, Invite withdrawn*
  - `scan_*` and `machine_first_seen` text is byte-identical for admin and viewer. — *TRUTH rule 17*
  - Gate green with zero database skips.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 2: `read_home_snapshot` — attention paging, notices, verdict, activity read
- **Layer**: `backend/` — `test-engineer` / `code-reviewer`
- **Description**: Stage 2. The snapshot service per `ARCHITECTURE.md` §2.4 and the wire schemas of
  §2.5. `page_attention` is **one** SQL list (never two concatenated severity lists) ordered
  critical-then-high, `findings.created_at DESC`, `findings.id DESC` — it must **not** reuse
  `list_findings`, whose `id asc` order is wrong for paging (§5.1). Server-side notices
  (`failed_scan`, `stale_coverage`) and `review_state` / `review_count` migrate here from the
  client's `review.ts`. `list_org_activity` reads newest-first with the `id DESC` tiebreaker and
  applies `activity_text(role=…)` before returning. `derive_home_events` is **not** in this task —
  the snapshot returns `events` as an empty page (see staging note).
- **Absorbed**: `backend/src/api/core/home_constants.py` (thresholds and the three
  `HOME_*_PER_PAGE` sizes) and `backend/src/api/schemas/home.py` (`HomeSnapshot` and its nested
  types). Neither carries branching, a rule, or an error path, so neither can fail a test of its
  own; both are exercised end to end by this task's suite. Constants keep their own leaf module —
  the merge is of *task*, not of file.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/core/home_constants.py`, `backend/src/api/schemas/home.py`,
  `backend/src/api/services/home.py`, `backend/tests/test_home_snapshot.py`]
- **Tests**: `backend/tests/test_home_snapshot.py` — mirror `backend/tests/test_read_service_scans.py`
  for DB fixtures. Absorbs the stale-coverage boundary cases from the retired
  `frontend/src/lib/review.test.ts`.
- **Success Criteria**:
  - Attention order holds across pages: critical before high, `created_at DESC` inside each. —
    *TRUTH rule 1, Attention overflow*
  - **Tied `created_at` across a page boundary**: seed findings sharing one `created_at` spanning
    pages 1–2; the union is every row exactly once — no repeat, no gap. — *rule 4*
  - `review_count` equals `attention.total + len(notices)`, not `len(attention.data)` — proven with
    a page-2 read. — *TRUTH rule 5*
  - `review_state`: `blank` with no scan row, `clear` at `review_count == 0`, `pending` above it.
  - A page past the end returns `data: []` with the real `total` (no error), matching `GET /scans`.
  - Stale-coverage boundary: exactly `STALE_COVERAGE_DAYS` does not notice; one day past does.
  - A failed latest scan yields a `failed_scan` notice; notices are **not** merged into events.
  - Medium and low severities never appear in `attention.data`. — *TRUTH rule 6*
  - Activity rows tied on `occurred_at` page without repeat or gap, newest-written first. —
    *TRUTH rule 18*
  - `events` is an empty page with `total: 0` — the final shape, not a placeholder.
  - Gate green with zero database skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: `GET /api/v1/home` route and published contract
- **Layer**: `backend/` — `test-engineer` / `code-reviewer`
- **Description**: Stage 2. Expose the snapshot per `ARCHITECTURE.md` §2.6 and §2.7. Three
  independent `Query(1, ge=1)` page integers, **no `per_page` parameter** — page sizes are server
  constants the client mirrors but cannot override (`TRUTH.md` rule 2). Auth is `require_user`, so
  a viewer reaches Home without the admin-only `GET /users`. Register in `main.py`. Hand-edit
  `contracts/openapi/openapi.yaml` with the path, the three page params and the component schemas,
  reusing `FindingRecord` and `ScanSummary`; extend `SCHEMA_NAMES` in the fidelity test.
- **Absorbed**: the OpenAPI YAML edit and the `SCHEMA_NAMES` extension — a hand-maintained
  contract has no test of its own, but `test_contract_fidelity.py` fails the moment it drifts from
  the router this task ships, so it is gated here rather than anywhere else.
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/routers/home.py`, `backend/src/api/main.py`,
  `contracts/openapi/openapi.yaml`, `backend/tests/test_contract_fidelity.py`,
  `backend/tests/test_home_route.py`]
- **Tests**: `backend/tests/test_home_route.py` — mirror `backend/tests/test_read_scans.py`.
- **Success Criteria**:
  - `GET /api/v1/home` authed returns `200` and a body validating as `HomeSnapshot`.
  - `attention_page=0` (and each other page param at `0`) returns `422`.
  - Unauthenticated returns the suite's standard auth failure, unchanged from sibling routes.
  - A **viewer** receives the same activity kinds, times and `total` as an admin — only `text`
    differs. — *TRUTH rule 17, Viewer parity*
  - The response carries no `per_page` field and the operation accepts no `per_page` param.
  - `test_contract_fidelity.py` green: the YAML and the live schema agree.
  - Gate green with zero database skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: `useHome` — one query replaces Home's four reads
- **Layer**: `frontend/` — `frontend-test-engineer` / `frontend-code-reviewer`
- **Description**: Stage 2. The client half of the snapshot per `ARCHITECTURE.md` §2.9 and
  `DESIGN.md` §6. Regenerate types (`npm run gen:types`) and commit `openapi.d.ts`. `useHome` is a
  single `useQuery` mapping the snapshot to `loading | error | blank | clear | pending`, exposing
  `retry` and the snapshot, keyed so the three page integers are independent. It sets
  `placeholderData: keepPreviousData` (TanStack Query v5) — a page change holds the previous
  snapshot rather than dropping the page to a skeleton (`DESIGN.md` §10 Q2). No component work.
- **Absorbed**: `frontend/src/api/home.ts` (`getHome` plus the three page-size constants) and the
  `queryKeys.home.snapshot` entry. `getHome` is a thin typed wrapper with no logic beyond the URL
  and the type; it is exercised end to end by this task's MSW suite and cannot fail a test of its
  own.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/types/openapi.d.ts`, `frontend/src/api/home.ts`,
  `frontend/src/api/queryKeys.ts`, `frontend/src/hooks/useHome.ts`,
  `frontend/src/hooks/useHome.test.ts`]
- **Tests**: `frontend/src/hooks/useHome.test.ts` — MSW matrix over the five states plus paging.
- **Success Criteria**:
  - Each of `loading`, `error`, `blank`, `clear`, `pending` is reached from a fixture, and `retry`
    refetches after an error.
  - Changing `attentionPage` leaves `eventsPage` and `activityPage` untouched in the query key and
    in the request. — *TRUTH rule 4, Independent paging*
  - After the first load, a page change keeps the previous snapshot rendered — the hook never
    returns `loading` again for a page change.
  - The three exported `HOME_*_PER_PAGE` constants equal the server values (8 / 5 / 8).
  - No request carries a `per_page` parameter.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: `Pagination` gains a per-surface accessible name
- **Layer**: `frontend/` — `frontend-test-engineer` / `frontend-code-reviewer`
- **Description**: Stage 2, but **independent of every other task** — start it now. `Pagination`
  hardcodes `aria-label="Pagination"` on its `nav` root and has only ever been mounted once per
  page, through `ListSurface`. Home is the first screen with three, and three identically named
  navigations are ambiguous to a screen reader. Add a **required** `label: string` prop driving
  `aria-label`; give `ListSurface`'s `pagination` prop a matching required `label` and forward it;
  update the three call sites that paginate today (`DESIGN.md` §2.2 and §6). `Devices.tsx` mounts
  `ListSurface` without `pagination` and is untouched. Foundations §Pagination gains the rule.
  The `testId` contract and icon-only chevron behaviour are unchanged.
- **Absorbed**: the `docs/ui/FOUNDATIONS.md` §Pagination line — documentation of the rule this task
  enforces in code, gated by the same tests.
- **Dependencies**: —
- **Target Files**: [`frontend/src/components/Pagination.tsx`,
  `frontend/src/components/Pagination.test.tsx`, `frontend/src/components/ListSurface.tsx`,
  `frontend/src/components/ListSurface.test.tsx`, `frontend/src/pages/Scans.tsx`,
  `frontend/src/pages/Network.tsx`, `frontend/src/pages/agents/DeviceScanHistory.tsx`,
  `docs/ui/FOUNDATIONS.md`]
- **Tests**: `Pagination.test.tsx` and `ListSurface.test.tsx` — the nav is found by the name the
  caller passed, not by a generic one.
- **Success Criteria**:
  - `getByRole('navigation', { name: 'Scan pages' })` resolves on Scans and on DeviceScanHistory;
    `'Machine pages'` on Network.
  - `label` is required — omitting it is a **typecheck failure**, not a silent generic default.
  - Previous/next stay icon-only with names `Previous page` / `Next page`, and no visible
    Previous/Next words. — *TRUTH rule 3, Foundations §Pagination*
  - `Pagination` still returns `null` when `total <= perPage`.
  - Existing `testId`-based assertions across the suite still pass unchanged.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Events and Activity panels
- **Layer**: `frontend/` — `frontend-test-engineer` / `frontend-code-reviewer`
- **Description**: Stage 2. The two feed cards and their row per `DESIGN.md` §2.2, §3.2, §7.5 and
  §7.6 — white card on canvas, heading inside, step-6 padding, two equal columns at step-8 gutter.
  Events rows are one line of `events.data[].text`, truncating; Activity rows are a fixed-width
  `Timestamp` on `occurred_at` plus `activity.data[].text`. **The SPA prints `text` verbatim** — it
  never composes a sentence from `kind` or payload, and never formats a verb. Each panel mounts
  `Pagination` with its own label and renders its empty sentence when it has no rows. These ship in
  stage 2 with empty data and fill in stages 3–4 without further change.
- **Absorbed**: nothing.
- **Dependencies**: Task 5
- **Target Files**: [`frontend/src/pages/home/HomeSidePanels.tsx`,
  `frontend/src/pages/home/EventsPanel.tsx`, `frontend/src/pages/home/ActivityPanel.tsx`,
  `frontend/src/pages/home/EventsPanel.test.tsx`,
  `frontend/src/pages/home/ActivityPanel.test.tsx`]
- **Tests**: `EventsPanel.test.tsx`, `ActivityPanel.test.tsx`.
- **Success Criteria**:
  - A row renders its server `text` byte-for-byte; no test fixture text is transformed, pluralised
    or re-cased by the component.
  - Empty Events shows `Nothing to report right now.` at `home-events-blank`; empty Activity shows
    `Nothing has been recorded yet.` at `home-activity-blank`; neither panel throws or disappears.
    — *TRUTH rules 12 and 19, No events*
  - `home-events-list` / `home-activity-list` are omitted (not rendered empty) when blank.
  - Pagination is absent at `total <= perPage` and present above it, named `Events pages` /
    `Activity pages`. — *TRUTH rule 3, Short attention list*
  - The `data-testid` set matches `DESIGN.md` §7.5 and §7.6 exactly, including
    `home-activity-row-{i}-time` and `-text`.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Home composes the snapshot; the client review merge is deleted
- **Layer**: `frontend/` — `frontend-test-engineer` / `frontend-code-reviewer`
- **Description**: Stage 2, and the task that delivers **TRUTH user story 4**. Rewrite `Home.tsx`
  onto `useHome` with three `useState(1)` page integers; mount the title block, the optional
  attention table, and `HomeSidePanels`. `AttentionTable` gains pagination below the table at step
  4; `AttentionNotices` renders the server's `notices[].text` instead of composing its own.
  `HomeBlank` allows panels beneath the first-run block. **Delete** `useHomeReview.ts`,
  `useHomeReview.test.ts`, `lib/review.ts` and `lib/review.test.ts` — their logic now lives in
  `read_home_snapshot` and their boundary cases in `test_home_snapshot.py`. Retire the
  four-endpoint fixture wiring in favour of one `GET /home` MSW handler.
- **Absorbed**: the `frontend/src/pages/Settings.tsx` privacy-disclosure rewrite and its
  assertion (`TRUTH.md` rule 23, `DESIGN.md` §1). It is a copy-only change on the same layer,
  gate and reviewer; the shipped paragraph promises that *admins* see sign-in times and that
  Dmitri records "not what you viewed or did", and this feature falsifies both halves. It must
  land no later than the feature it describes.
- **Dependencies**: Task 4, Task 6
- **Target Files**: [`frontend/src/pages/Home.tsx`,
  `frontend/src/pages/home/AttentionTable.tsx`, `frontend/src/pages/home/AttentionNotices.tsx`,
  `frontend/src/pages/home/HomeBlank.tsx`, `frontend/src/test/mswHandlers.ts`,
  `frontend/src/pages/Home.test.tsx`, `frontend/src/pages/Settings.tsx`,
  `frontend/src/pages/Settings.test.tsx`, `frontend/src/hooks/useHomeReview.ts`,
  `frontend/src/hooks/useHomeReview.test.ts`, `frontend/src/lib/review.ts`,
  `frontend/src/lib/review.test.ts`]
- **Tests**: `frontend/src/pages/Home.test.tsx` (rewritten onto the single handler) and
  `Settings.test.tsx`.
- **Success Criteria**:
  - Home issues **one** request. No `GET /scans` or `GET /findings` call remains on this page.
  - The four deleted files are gone and nothing imports them; `npm run build` proves it.
  - Attention pagination hidden at `total <= 8`, shown above it, named `Attention pages`. —
    *TRUTH: Short attention list, Attention overflow*
  - Changing the attention page leaves Events and Activity on their own pages **and still on
    screen** — assert both panels present on attention page 2. — *TRUTH rule 4, Independent paging,
    Last attention page*
  - `clear`: the table is **not drawn** and both panels render under the title. — *TRUTH rule 20*
  - `blank` (first-run): panels render with their rows or empty states; no attention rows are
    invented. — *TRUTH rule 21*
  - The title count comes from `review_count`, and is right on page 2 of a multi-page list. —
    *TRUTH rule 5*
  - A viewer sees the invite and role-change rows with the server's neutral copy. — *TRUTH:
    Viewer parity*
  - `settings-activity-note` reads the new paragraph from `DESIGN.md` §1 verbatim. — *TRUTH:
    Privacy copy is honest*
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Actor-caused activity — role, invite, revoke, remove, leave
- **Layer**: `backend/` — `test-engineer` / `code-reviewer`
- **Description**: Stage 3. The five human-caused write sites of `ARCHITECTURE.md` §2.3 and the
  router threading of §2.8. Extend `change_member_role`, `delete_member`, `create_invite` and
  `revoke_invite` to take `actor_user_id` and `actor_email`; `delete_self` reads its own user.
  Routers pass `caller.sub` and the loaded email. **Services must not re-query the actor after a
  hard delete** — the denormalised email in `payload` is the only surviving record of who they
  were. `invite_revoked`, `member_removed` and `account_deleted` append **before**
  `session.delete`.
- **Absorbed**: nothing.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/users.py`, `backend/src/api/routers/users.py`,
  `backend/src/api/services/invites.py`, `backend/src/api/routers/invites.py`,
  `backend/tests/test_users_service.py`, `backend/tests/test_invite_service.py`]
- **Tests**: `test_users_service.py` and `test_invite_service.py`, extended.
- **Success Criteria**:
  - Role change writes one `role_changed` row naming actor and target; a second change to the same
    target writes a **second** row (this kind is not unique-guarded).
  - Removing a member leaves the `member_removed` row readable after the user row is gone, with the
    actor's email intact. — *TRUTH rule 14, Delete survives*
  - Revoking an unused invite leaves an `invite_revoked` row after the invite is gone. — *TRUTH:
    Invite withdrawn*
  - `delete_self` writes `account_deleted` before the delete and survives it.
  - `occurred_at` on every row is the API clock, not a value from the request body. — *rule 3*
  - Existing behaviour is unchanged: `LastAdminError` still guards the last admin on both
    `change_member_role` and `delete_self`, and no test in these files regresses.
  - Gate green with zero database skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Box-caused activity — scan lifecycle and first-seen machines
- **Layer**: `backend/` — `test-engineer` / `code-reviewer`
- **Description**: Stage 3. The four box-driven write sites of `ARCHITECTURE.md` §2.3, all with
  `actor_user_id=None` — the admin who clicked Scan is **not** the actor of an ingest row.
  `scan_started` in `_record_delivery` (inside its transaction, so the lost-race rollback discards
  it with the stub `ScanRecord`); `scan_finished` in `persist_scan`; `scan_failed` in `apply_status`
  after the `RETURNING` row proves the update won, and in `sweep_stale_commands` per returned row
  where the status is `failed` **and** `scan_id is not None`. A `queued` command that expires was
  never delivered, carries no `scan_id`, and writes **nothing** — nothing started, so nothing
  failed. `machine_first_seen` fires in `upsert_hosts_for_scan` on host **insert only**, and is
  **suppressed on the org's first completed scan** — that scan establishes the baseline and would
  otherwise write one row per machine on the network, burying the scan rows. Compute the baseline
  flag once before the host loop, not per host.
- **Absorbed**: nothing.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/commands.py`,
  `backend/src/api/services/persistence.py`, `backend/src/api/services/hosts.py`,
  `backend/tests/test_command_delivery.py`, `backend/tests/test_ingest_scan.py`,
  `backend/tests/test_hosts_service.py`]
- **Tests**: `test_command_delivery.py`, `test_ingest_scan.py`, `test_hosts_service.py` (create the
  last if absent; otherwise cover host insert in the ingest test).
- **Success Criteria**:
  - Delivery writes `scan_started`; a **rolled-back** delivery (command left `queued` mid-send)
    writes no row.
  - Ingest completion writes `scan_finished`.
  - A `queued` command that expires via the sweep writes **no** activity row.
  - `scan_failed` is written once per failed scan and is idempotent under a repeated sweep.
  - **Baseline**: the org's first completed ingest finding many hosts writes the scan rows and
    **zero** `machine_first_seen` rows. — *TRUTH rule 13a, Baseline scan is quiet*
  - A **later** ingest introducing a new host writes exactly one `machine_first_seen` row; a host
    already known writes none. — *TRUTH rule 10*
  - **Clock skew**: an ingest whose `scan.timestamp` predates its own `scan_started` row still
    reads `scan_finished` **above** it. — *TRUTH rule 14a, Box clock is wrong*
  - No existing scan-lifecycle test regresses.
  - Gate green with zero database skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 10: `derive_home_events` — box offline, member idle, new machine
- **Layer**: `backend/` — `test-engineer` / `code-reviewer`
- **Description**: Stage 4. The three derived, **never stored** current-state facts of
  `ARCHITECTURE.md` §2.4, filling the `events` page the snapshot has returned empty since Task 2.
  **Box offline**: effective last-seen is `agent_connections.last_seen_at(id) or agents.last_seen_at`
  — the registry overlay is mandatory, since SQL-only last-seen disagrees with Devices while the box
  is connected. Skip when `is_online`; never read `connected_at` (reconcile nulls it on process
  start). **Member idle** queries `users.last_login_at`, not `last_seen_at` — a session refresh
  without a sign-in is not a sign-in — and is visible to viewers as well as admins; do **not** add
  `last_login_at` to member JSON. **New machine** filters `first_seen_at` inside the 7-day window
  **and** strictly after the org's earliest completed scan. Sort: box offline (longest quiet
  first), then member idle (longest idle first), then new machines (newest first). Copy says
  *machine*, never *device*. This is the one place the stale-coverage notice and box-offline share
  a number (3) and must not be merged — different clocks.
- **Absorbed**: nothing.
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/services/home.py`, `backend/tests/test_home_events.py`]
- **Tests**: `backend/tests/test_home_events.py`.
- **Success Criteria**:
  - A box last seen 4 days ago and not live yields one offline event with the correct day count. —
    *TRUTH rule 8, Box offline*
  - A box live in the registry with a stale DB `last_seen_at` yields **no** event.
  - A member whose `last_login_at` is 61 days old yields an idle event; `last_login_at IS NULL`
    does too. — *TRUTH rule 9, Member idle*
  - **Session refresh only** — fresh `last_seen_at`, stale `last_login_at` — is **still idle**. —
    *TRUTH rule 9*
  - A viewer's snapshot carries the same idle events as an admin's. — *TRUTH rule 11*
  - A host first seen yesterday on a later scan yields one event; hosts introduced by the org's
    first completed scan yield **none**. — *TRUTH rule 10, Baseline scan is quiet*
  - Event copy uses *machine* for network hosts and *box* for the Dmitri device — no "device joined
    the network". — *TRUTH definitions*
  - Stale coverage stays a notice and never appears as an event. — *`ARCHITECTURE.md` §5.2*
  - Events paginate independently and an empty result is `total: 0`, not an error. — *TRUTH rule 12*
  - Gate green with zero database skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
backend feed                              frontend
────────────                              ────────
#1 activity store ──┬─→ #2 snapshot ──→ #3 route ──→ #4 useHome ──┐
                    │        │                                    │
                    │        └────────────────→ #10 events        ├─→ #7 Home + Settings
                    │                                             │
                    ├─→ #8 actor writes                           │
                    └─→ #9 box writes            #5 Pagination ──→ #6 panels ──┘
```

Two tracks run in parallel. **#5 is independent of the entire backend** — start it alongside #1.
After #1 lands, **#2, #8 and #9 are all unblocked together**.

| Stage boundary | Reached after |
|---|---|
| 1 → 2 | #1 |
| 2 → 3 | #7 (Home works; user story 4 delivered) |
| 3 → 4 | #9 |
| done | #10 |

## Status

| # | Task | Layer | Status |
|---|------|-------|--------|
| 1 | `activity` table, `append_activity`, `activity_text` | backend | COMPLETED |
| 2 | `read_home_snapshot` — attention paging, notices, verdict | backend | COMPLETED |
| 3 | `GET /api/v1/home` route and published contract | backend | COMPLETED |
| 4 | `useHome` — one query replaces Home's four reads | frontend | COMPLETED |
| 5 | `Pagination` gains a per-surface accessible name | frontend | COMPLETED |
| 6 | Events and Activity panels | frontend | COMPLETED |
| 7 | Home composes the snapshot; client review merge deleted | frontend | COMPLETED |
| 8 | Actor-caused activity — role, invite, revoke, remove, leave | backend | COMPLETED |
| 9 | Box-caused activity — scan lifecycle and first-seen machines | backend | COMPLETED |
| 10 | `derive_home_events` — box offline, member idle, new machine | backend | COMPLETED |

## Coverage — every `TRUTH.md` acceptance row is gated

| Acceptance row | Task |
|---|---|
| Scan start and finish | #9 |
| Box clock is wrong | #9 |
| Role change names people | #8, text matrix #1 |
| Box offline | #10 |
| Member idle | #10 |
| New machine | #10 |
| Baseline scan is quiet | #9 (write), #10 (event) |
| No events | #6 (panel), #2 (empty page) |
| Attention overflow | #2 (order), #7 (control) |
| Last attention page | #7 |
| Short attention list | #7, #6 |
| Independent paging | #4 (key), #7 (screen) |
| Viewer parity | #1 (text), #3 (totals), #7 (screen) |
| Privacy copy is honest | #7 |
| Delete survives | #8 |
| Invite withdrawn | #8 (row), #1 (viewer wording) |

## Out of scope — do not create tasks for these

Email or push notification; compliance audit trail, retention or archival; configurable thresholds
or page sizes; infinite scroll or a virtualized table; URL-synced page numbers; medium or low
severities on Home; backfilling activity from already-deleted history; public `GET /events` or
`GET /activity` routes; per-panel error envelopes inside a `200` snapshot; any `hardware-agent/` or
TUI change.

## Human tail (not agent tasks)

`DESIGN.md` §10 Q4 — the operator opens `preview.html` at desktop width and confirms spacing, panel
cards and pagination. **That check closes the feature**; no agent signs off on how it looks. Note
the preview predates the refine pass: it does not show the per-surface pagination labels or the new
Settings copy, though neither is a layout change.
