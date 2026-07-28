# Tasks — Scan list and finding filters (`021-scan-list-and-finding-filters`)

12 tasks. **Unblocked now: #1, #2**

Order adapted to a backend read-path feature (there is no scan pipeline or TUI in this blast
radius): shared constants → schemas → schema constraint + migration → service layer → routers →
tests.

**CLAUDE.md integration rule: N/A, verified.** This feature touches `backend/src/api/` only. There
is no `ScanOrchestrator`, `ScanRunner` or `ScanProgressScreen` parameter anywhere in scope and
`hardware-agent/` is not touched — see ARCHITECTURE.md §Preamble. The rule's *spirit* is honoured
by Task 6 and Task 8, which sweep every call site of the widened `list_findings` signature, and by
Task 1, which sweeps every reader of the renamed severity constant.

> **Superseded in places — read ARCHITECTURE.md's as-built amendments first.** A pre-push nuke
> pass changed four decisions after these tasks were written and executed. This file is the
> ledger of what was instructed at the time and is left as-written; **ARCHITECTURE.md is the
> current truth.** Affected tasks are marked below. In summary: `SEVERITY_ORDER` lives in
> `schemas/read.py`, not `services/hosts.py` (Tasks 1, 3, 5); the migration imports nothing from
> `api.*` (Tasks 3, 4); the `list_scans`/`list_findings` filter params are domain-typed, not
> `str` (Tasks 5, 6); and the `list_scans` service tests live in `test_read_service_scans.py`
> (Task 9).

---

## Task 1: Promote the severity ranking to a single public constant
- **Description**: Rename `_SEVERITY_ORDER` → `SEVERITY_ORDER` in `services/hosts.py:14` and update its sole reader at `services/hosts.py:83`. Per ARCHITECTURE.md §Design problem 2, this dict becomes the one definition of the severity domain and its ordering — the SQL rank expression (Task 5) and the check constraint (Task 3) both derive from it. No behaviour change.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/hosts.py`]
- **Success Criteria**: `SEVERITY_ORDER` is public and unchanged in value (`{"low": 1, "medium": 2, "high": 3, "critical": 4}`); `grep -rn "_SEVERITY_ORDER" backend/` returns zero hits; existing tests pass untouched.
- **Superseded**: the constant's home is `schemas/read.py`, derived from the `Severity` literal — not `services/hosts.py`. Placing it in a service made `models/persistence.py` (Task 3) import a service, inverting the layering. See ARCHITECTURE.md §Design problem 2, as-built amendment.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Add the scan list schemas
- **Description**: Per the ARCHITECTURE.md naming table, add to `schemas/read.py`: `ScanSortBy = Literal["timestamp","status","scan_mode"]` and `SortOrder = Literal["asc","desc"]` beside the existing literals (`schemas/read.py:9-11`), plus `ScanSummary` (8 fields) and `ScanListResponse` (`data`/`total`/`page`, mirroring `HostListResponse` at `schemas/read.py:114`). Reuse the existing `ScanMode`/`ScanStatus`/`Severity` literals — do **not** redeclare them.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/schemas/read.py`, `backend/tests/test_read_schema.py`]
- **Success Criteria**: `ScanSummary` uses `ConfigDict(extra="forbid")`; `subnet` is a plain `str` with **no** pattern (deliberate — see ARCHITECTURE.md, the contract gives `ScanSummary.subnet` no pattern unlike `ScanDetailResponse.subnet`); `highest_severity: Severity | None = None` is the only optional field, the other 7 required; `ScanListResponse` has no `per_page` key; `test_all_nine_read_models_importable` (`tests/test_read_schema.py:49`) is updated to 11 models and renamed accordingly.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Enforce the severity domain in the store
- **Description**: Per ARCHITECTURE.md §Severity domain constraint and §Migrations, add a named `CheckConstraint` on `findings.severity` to `FindingRecord.__table_args__` (`persistence.py:116`, which already holds a `UniqueConstraint`), restricted to the `SEVERITY_ORDER` keys so the allowed set is defined once. Add the one migration in scope, `down_revision = "20260724_11"` (verified current head). Model-side change only — no column type change, no default, no data rewrite.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/models/persistence.py`, `backend/alembic/versions/20260727_12_finding_severity_domain.py`]
- **Success Criteria**: Constraint name is identical in the model and in both `upgrade()`/`downgrade()`, so downgrade can drop it by name; `upgrade()` **guards first** — if any existing row is out of domain it fails loudly naming the offending values rather than dying inside `create_check_constraint`; plain `op.create_check_constraint`/`op.drop_constraint` (no batch mode — Alembic only ever runs against Postgres); expression follows the `ck_users_role` precedent (`20260716_02_identity_schema.py:54`).
- **Superseded**: the model imports `SEVERITY_ORDER` from `api.schemas.read` (see Task 1). The **migration** imports nothing from `api.*` and spells the four severities out — a revision is frozen history, so it must not shift when a live constant is edited. See ARCHITECTURE.md §Migrations file-table row.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Test the severity constraint and its migration
- **Description**: New test file covering TRUTH AC 27, 28 and the upgrade guard. Follow the repo's **one-test-file-per-revision** convention (seven precedents, e.g. `test_agents_public_key_migration.py`): importlib `_load_migration()`, a revision-chain test, monkeypatched `op.*` assertions, and a live round trip. Evidence for this placement: `docs/research/finding-severity-constraint-test-placement.md`.
- **Dependencies**: Task 3
- **Target Files**: [`backend/tests/test_finding_severity_migration.py`]
- **Success Criteria**: AC 27 — `pytest.raises(sa.exc.IntegrityError)` around `commit()` of a `FindingRecord` with `severity="urgent"` on `administrative_session`, with a trailing `session.rollback()` (copy `test_invalid_role_is_rejected`, `tests/test_identity_migration.py:168-179`); all four valid severities commit. AC 28 — step down **exactly one** revision via `_migrate(engine, "20260724_11")`, **never `base`** (which drops the tables and makes the test vacuous), seed findings, upgrade, assert every seeded row is unchanged, downgrade, restore to head. Guard — with a bad row pre-seeded, `upgrade()` fails with a message naming the value. `tests/test_migrations.py` is **not** modified.
- **Superseded**: also add a test asserting the migration's spelled-out severity set still equals `SEVERITY_ORDER` — the drift net for the non-import decided in Task 3. See ARCHITECTURE.md.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: Implement `list_scans` with per-scan aggregates
- **Description**: Per ARCHITECTURE.md §Design problems 1, 2, 3, 5 and 7, add to `services/read.py`: `_SCAN_SORT_COLUMNS` (a closed dict of column objects), a severity rank `case()` expression plus its inverse map both derived from `SEVERITY_ORDER`, a `_to_scan_summary(...)` mapper next to `_to_host_summary` (`services/read.py:211`), and `list_scans(session, *, org_id, page=1, per_page=20, status=None, sort_by="timestamp", sort_order="desc") -> ScanListResponse`.
- **Dependencies**: Task 1, Task 2
- **Target Files**: [`backend/src/api/services/read.py`]
- **Success Criteria**: Uses the **4-query strategy** (count, page, then two grouped aggregates restricted to the page's ids) — constant in `per_page`, never a per-row loop, never two direct joins onto `scans` (which would cartesian-fan `host_count`/`finding_count` to the same wrong number); `ids` empty ⇒ Q3/Q4 skipped entirely, no `IN ()`; severity ranked via the `case()` expression, never a lexical `max()`; `highest_severity` is `None` for a scan with zero findings — no `or "low"`, no `coalesce`; ordering is **total** (`sort_by`/`sort_order`, then `ScanRecord.scan_id` always ascending); org scoping is `ScanRecord.org_id == org_id`, never `IS NOT DISTINCT FROM`; the service performs no bounds checking; no string interpolation or `getattr` into the sort column.
- **Superseded**: `SEVERITY_ORDER` is imported from `api.schemas.read` (see Task 1), and `status` is typed `ScanStatus | None` rather than left bare `str` — matching the already-typed `sort_by`/`sort_order`. See ARCHITECTURE.md naming-table row for `services/read.py`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Extend `list_findings` with severity and scan filters
- **Description**: Per ARCHITECTURE.md §Design problem 4 and §Deterministic ordering, add keyword-only `severity: str | None = None` and `scan_id: UUID | None = None` to `list_findings` (`services/read.py:154`), composed onto the existing `base` select **before** either `total` or the page is derived. Add `FindingRecord.id` ascending as the ordering. `org_id` stays keyword-only and required.
- **Dependencies**: Task 5
- **Target Files**: [`backend/src/api/services/read.py`]
- **Success Criteria**: Both new filters are plain `WHERE` predicates on `FindingRecord`, so they attach regardless of which join branch ran and combine conjunctively; the existing `host_id` inner/outer-join branch (`services/read.py:162-174`) is **not edited**; `total` still derives from `base.subquery()` and counts matches not the page; the three existing call sites (`tests/test_read_service.py:247,251,256`) still pass **unmodified** because the new params are optional keywords; `severity` accepts a single scalar — not a list, comma-separated string, or range.
- **Superseded**: `severity` is typed `Severity | None`, not `str | None` — see the ARCHITECTURE.md naming-table row for `services/read.py`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Mount `GET /api/v1/scans`
- **Description**: Add `read_scans()` to `routers/scans.py` per the ARCHITECTURE.md §Design problem 6 signature, with all five params constrained via `Query(...)`, `Depends(get_session)` + `Depends(require_user)`, and `response_model=ScanListResponse`. Leave `read_scan` (`routers/scans.py:16`) untouched. **Blocking pair:** the route-surface allowlist must be updated in the same task or the suite breaks the moment the route mounts.
- **Dependencies**: Task 5
- **Target Files**: [`backend/src/api/routers/scans.py`, `backend/tests/test_health.py`]
- **Success Criteria**: Bounds are declarative (`ge=1`, `ge=1, le=100`) — no clamping, no `min()`, no hand-rolled `HTTPException(400)`; `sort_by`/`sort_order`/`status` are `Literal` types so unknown values are rejected by FastAPI before handler code runs; `org_id=caller.org_id` is passed into the service, tenant boundary in SQL not in the handler; `EXPECTED_ROUTE_SURFACE` (`tests/test_health.py:33`) gains `("/api/v1/scans", "GET")` **and** `"/api/v1/scans"` is removed from `DISCARDED_BUSINESS_PATHS` (`tests/test_health.py:27`), while `"/scans"` and `"/findings"` stay discarded; `main.py` is not touched (the router is already mounted).
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Widen the findings route
- **Description**: Widen `read_findings` (`routers/findings.py:17`) to accept `page`, `per_page`, `severity` and `scan_id` alongside the existing `host_id`, and forward all five to `list_findings`. Per the ARCHITECTURE.md naming table.
- **Dependencies**: Task 6
- **Target Files**: [`backend/src/api/routers/findings.py`]
- **Success Criteria**: Same declarative bounds as Task 7; `severity` is the existing `Severity` literal and `scan_id` a `UUID`, so bad values 422 before the handler; the existing `host_id` behaviour is unchanged; `FindingListResponse` is untouched — no field added, renamed or removed.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Service tests for `list_scans`
- **Description**: Cover TRUTH AC 1–11 and 26 in `test_read_service.py`, driving `api.services.read` directly against `administrative_session`. Seed per the ARCHITECTURE.md §Fixtures `scan_history_org` shape: one org with 25 scans of strictly increasing timestamps and mixed `status`/`scan_mode`, plus a second org with its own scans. Follow the existing local-helper style (`_make_org`, `_make_scan`, `_make_finding` at `tests/test_read_service.py:20-102`).
- **Dependencies**: Task 5
- **Target Files**: [`backend/tests/test_read_service.py`, `backend/tests/conftest.py`]
- **Success Criteria**: AC 9's aggregate test seeds a scan with 12 scan-hosts and 4 findings and asserts exactly `12`/`4` — the regression test for the cartesian-fanout trap; AC 10 asserts `highest_severity is None` for the zero-finding scan; AC 26 pages a `sort_by="status"` result and asserts the union covers every scan exactly once; AC 11 includes a `list_scans` twin of `test_null_org_id_host_and_scan_visible_to_nobody` (`tests/test_read_service.py:262`); AC 4 asserts the **sort column's** sequence is monotonic, not full row identity (ties are broken by `scan_id`, which is not contract behaviour). Also add the severity-ranking regression (a `{low, critical}` scan reports `critical`, a `{low, medium}` scan reports `medium` — both fail under lexical `max()`) and an N+1 guard asserting query count is constant across page size. Fixtures go in `conftest.py` only if Task 10 needs them too.
- **Superseded**: these cases live in a new `tests/test_read_service_scans.py`, not `test_read_service.py`, which would otherwise have crossed 1000 lines. The shared record builders moved to `tests/read_factories.py` (public `make_*` names) rather than `conftest.py`, being plain functions not fixtures; `conftest.py` is untouched. See ARCHITECTURE.md §Testing expectations, as-built amendment.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 10: Service tests for the finding filters
- **Description**: Cover TRUTH AC 12–20 and 25 in `test_read_service.py`. Seed per the ARCHITECTURE.md §Fixtures `mixed_severity_findings` shape: two orgs, two scans each, one host per scan, findings across all four severities, **one scan with zero findings**, and **one finding with `scan_host_id = NULL`**.
- **Dependencies**: Task 6
- **Target Files**: [`backend/tests/test_read_service.py`, `backend/tests/conftest.py`]
- **Success Criteria**: The zero-finding scan and the NULL-`scan_host_id` finding are actually asserted on — they are load-bearing, proving AC 10 and the outer-join branch respectively, not decoration; AC 14 asserts the combined count is strictly less than either filter alone; AC 18 asserts `len(data) == 20` **and** `total == 25` (total counts matches, not the page); AC 25 seeds 25 findings all tying on severity and timestamp, pages at 10, and asserts the union of pages is all 25 with empty pairwise intersections; AC 20 includes org A querying with org B's `scan_id`, `host_id`, and both. AC 15 regression: `test_list_findings_scopes_count_and_page_by_org` (`tests/test_read_service.py:227`) passes **unmodified — do not edit it**.
- **Superseded**: stays in `test_read_service.py`, but the record builders now come from `tests/read_factories.py` as public `make_*` names (see Task 9); `conftest.py` is untouched.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 11: Route-level tests
- **Description**: Cover the HTTP surface in `test_read_endpoints.py` — status codes, auth and wire shape — for both endpoints, per the ARCHITECTURE.md AC→test map (AC 5, 7, 10, 19, 20, 21, 22, 23).
- **Dependencies**: Task 7, Task 8
- **Target Files**: [`backend/tests/test_read_endpoints.py`]
- **Success Criteria**: Empty results assert HTTP **200 explicitly, and explicitly not 404 or 403** (AC 5, 7, 19, 20); AC 10 asserts the JSON key is present with value `null` (`body["highest_severity"] is None`, not `not in`); AC 21 adds `/api/v1/scans` to the three parametrised auth lists (`tests/test_read_endpoints.py:275`, `:284`, `:449`) asserting `body["error"]["code"] == "unauthorized"`; AC 22 covers `per_page=101`, `per_page=0`, `page=0`, `page=-1` → **422** with `code == "validation_error"`, plus a non-clamping assertion that `per_page=100` succeeds while `101` is refused; AC 23 covers `sort_by=nope`, `sort_order=sideways`, `status=bogus`, `severity=urgent`, `scan_id=not-a-uuid`. Assertions are on `code`, never on the error `message` (which is body-shaped even for query failures — pre-existing, ARCHITECTURE.md Open item 2).
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 12: Contract fidelity test
- **Description**: Per ARCHITECTURE.md §Contract fidelity, add a real comparison of `app.openapi()` against the parsed `contracts/openapi/openapi.yaml` (TRUTH AC 24). Nothing in the repo does this today — the only `openapi.yaml` reference in `backend/` is a comment (`main.py:98`). Add `pyyaml` to the `dev` extra (`pyproject.toml:33`); no YAML parser is currently installed.
- **Dependencies**: Task 2, Task 7, Task 8
- **Target Files**: [`backend/tests/test_contract_fidelity.py`, `backend/pyproject.toml`]
- **Success Criteria**: Compares field by field the `ScanSummary` and `ScanListResponse` schemas (property names, types, required set, `additionalProperties`) and the query parameters of `listScans` and `listFindings` (name, type, enum values, defaults, bounds); the test fails if a field is added, renamed or missing relative to the contract; scope is limited to what this feature touches — **not** a whole-document diff, which would fail on the pre-existing `400`/`422` divergence; response status codes are excluded, and the exclusion is asserted explicitly with a comment naming ARCHITECTURE.md Open item 1 so it reads as decided rather than forgotten; `pyyaml` lands in the `dev` extra only, never in the runtime `dependencies` list (`pyproject.toml:11-25`); `contracts/openapi/openapi.yaml` is **not** modified.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ─┬─→ #3 ──→ #4
    │
    └─┬─→ #5 ─┬─→ #6 ─┬─→ #8 ─┬─→ #11
#2 ──┘        │       │       │
              │       └──────→ #10
              │               │
              ├─→ #7 ─────────┴─→ #12
              │    │
              │    └─→ #11
              └─→ #9
```

Three tracks run independently once #1 and #2 land: the **constraint/migration** track (#3, #4),
the **read-path** track (#5 → #6 → routers → tests), and #12 which joins at the end.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Promote the severity ranking to a single public constant | COMPLETED |
| 2 | Add the scan list schemas | COMPLETED |
| 3 | Enforce the severity domain in the store | COMPLETED |
| 4 | Test the severity constraint and its migration | COMPLETED |
| 5 | Implement `list_scans` with per-scan aggregates | COMPLETED |
| 6 | Extend `list_findings` with severity and scan filters | COMPLETED |
| 7 | Mount `GET /api/v1/scans` | COMPLETED |
| 8 | Widen the findings route | COMPLETED |
| 9 | Service tests for `list_scans` | COMPLETED |
| 10 | Service tests for the finding filters | COMPLETED |
| 11 | Route-level tests | COMPLETED |
| 12 | Contract fidelity test | COMPLETED |

## Acceptance-criteria coverage

Every TRUTH.md criterion maps to at least one task.

| AC | Task | AC | Task |
|---|---|---|---|
| 1–8 Latest, order, sort, empty, paging, status filter | #9 | 17 No filter | #10 |
| 9 Per-scan aggregates | #5, #9 | 18 Paging and total | #10 |
| 10 No findings ⇒ null severity | #5, #9, #11 | 19 Empty filter result | #10, #11 |
| 11 Scan isolation | #5, #9 | 20 Finding isolation | #10, #11 |
| 12 Findings by severity | #6, #10 | 21 Unauthenticated | #11 |
| 13 Findings by scan | #6, #10 | 22 Invalid paging | #7, #8, #11 |
| 14 Filters combine | #6, #10 | 23 Invalid sort | #7, #11 |
| 15 Existing filter unchanged | #6, #10 | 24 Contract fidelity | #12 |
| 16 Machine and scan together | #6, #10 | 25 Stable finding paging | #6, #10 |
| 26 Stable scan paging under ties | #5, #9 | 27 Severity domain enforced | #3, #4 |
| 28 Existing data survives | #3, #4 | 29 Quality gates | all |

**Run the gates with `DATABASE_URL_TEST` set.** `postgres_engine` skips without it
(`tests/conftest.py:116-118`), which would silently no-op Tasks 4, 9 and 10. CI provisions Postgres
and **fails the job on any skip at all** (`.github/workflows/ci.yml:99-105`).
