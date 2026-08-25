# PLAN — `sort_by` / `sort_order` on `GET /hosts` (DMI-100)

**Issue:** [DMI-100](https://linear.app/dmitri-imt/issue/DMI-100) ·
**Branch:** `feat/dmi-100`

A plan, not a full spec. One enum, one router signature, one `order_by` clause, and a
guard entry. TRUTH / ARCHITECTURE / DESIGN would each be a paragraph, so they are folded
in here. `list_scans` already solved this exact problem; the work is to copy it.

Two questions the issue left open were resolved with the operator on 2026-08-25 and are
recorded below as **Decided:**. Nothing is left to confirm; this plan is ready to build.

## Goal

`GET /api/v1/hosts?sort_by=hostname&sort_order=asc` returns hosts in ascending hostname
order, and a bad enum value returns `422`. Nothing else about the endpoint changes.

## Current state — verified, not assumed

* `src/api/routers/hosts.py:23-28` — `read_hosts` accepts `page` and `per_page` only.
* `src/api/services/read.py:49-72` — `list_hosts` hardcodes
  `order_by(HostRecord.last_seen_at.desc(), HostRecord.id.asc())`.
* `src/api/schemas/read.py:15-16` — `ScanSortBy` and `SortOrder` exist; `HostSortBy` does not.
* `contracts/openapi/openapi.yaml:1257-1268` — `HostSortBy` is already declared with the
  four values `last_seen_at | hostname | vendor | ip`, default `last_seen_at`. **No contract
  change is needed.**
* FastAPI ignores unknown query parameters, so `?sort_by=hostname` today returns
  `last_seen_at` ordering and no error. That is the defect.

The reference implementation is `read_scans` (`routers/scans.py:53-70`) →
`list_scans` (`services/read.py:182-208`) → `_SCAN_SORT_COLUMNS`
(`services/read.py:40-44`). Mirror it exactly; do not invent a sorting helper.

## Decision 1 — the `q` collision

The issue asks for two things that contradict each other under the current guard:

* *"Add `/api/v1/hosts` to `OPERATION_PATHS` in `tests/test_contract_fidelity.py`"*
* *"Leave `q` unimplemented and leave it in the contract"*

`test_query_parameters_match_contract` asserts
`set(contract_params) == set(app_params)` (`tests/test_contract_fidelity.py:302`). The
contract declares five query parameters on `/api/v1/hosts` — `page`, `per_page`,
`sort_by`, `sort_order`, `q`. The implementation will expose four. **Adding the path to
`OPERATION_PATHS` as written makes the new test fail on `q`.**

Three ways out:

| | Effect | Cost |
|---|---|---|
| A. Implement `q` | Guard passes as-is | Directly violates the issue's NOT-expected fence — search is cut from v1 |
| B. Delete `q` from `openapi.yaml` | Guard passes as-is | Directly violates the issue's NOT-expected fence — it says leave it in |
| C. Give the guard a declared-but-unimplemented exemption | Guard passes; the other four params are covered | Adds one small mechanism the issue did not name |

**Decided 2026-08-25: C.** A and B each break a fence the issue set deliberately. C is the
only option that honours both, and it is not a stopgap: "the contract declares more of v1
than is built yet" is a standing condition of this project, not a temporary one, so a named
exemption is the mechanism's intended final shape.

Concretely — a module-level constant beside `OPERATION_PATHS`:

```python
# Parameters the contract declares that v1 deliberately does not implement.
# Search is cut from v1 (docs/ui/IDEAS.md → Hosts); see DMI-100.
UNIMPLEMENTED_PARAMS = {("/api/v1/hosts", "q")}
```

subtracted from `contract_params` inside `test_query_parameters_match_contract`. Drift on
the four real parameters is still caught, and the exemption is one grep away from anyone
who wonders why `q` is absent.

A and B are recorded above only so a later reader can see they were considered and why they
lost. Neither is a fallback — taking either would require re-editing the issue first.

## Decision 2 — what `sort_by=ip` means

`HostRecord.ip` is a plain `str` column (`models/persistence.py:68`), so a text sort orders
`192.168.0.1`, `192.168.0.10`, `192.168.0.2`. To an operator looking at a host inventory
that reads as broken.

* **Text sort** — zero extra code, matches the column type, looks wrong on screen.
* **`cast(HostRecord.ip, INET)`** — numerically correct, one line, Postgres-only.

**Decided 2026-08-25: cast to `INET`.** `ip` is the one sort field where the naive answer is
visibly wrong. The tiebreaker and every other column stay as they are.

**Correction, found during implementation:** this plan originally justified the cast with
"the suite runs against Postgres with no SQLite path". That is false.
`tests/test_read_endpoints.py:30` defines its own `session` fixture on in-memory **SQLite**,
shadowing conftest's Postgres fixtures, and SQLite cannot compile `INET`
(`UnsupportedCompilationError`). The decision stands — production is Postgres — but the
test for it cannot use this file's default fixture. See task 5.

So `_HOST_SORT_COLUMNS["ip"]` is `cast(HostRecord.ip, INET)` rather than the bare column,
while the other three entries are plain columns. `INET` comes from
`sqlalchemy.dialects.postgresql`.

The issue's test cases only exercise `hostname` and `vendor`, so this choice is unforced by
them — which is why task 5 below adds a sixth case the issue does not list: `sort_by=ip`
must order `192.168.0.2` before `192.168.0.10`. Without it the decision is untested and a
later refactor back to a text sort would go unnoticed.

## Tasks

1. **`schemas/read.py`** — add
   `HostSortBy = Literal["last_seen_at", "hostname", "vendor", "ip"]` on the line after
   `ScanSortBy`. → *verify:* imports cleanly.
2. **`services/read.py`** — add `_HOST_SORT_COLUMNS` beside `_SCAN_SORT_COLUMNS`, with
   `ip` mapped to `cast(HostRecord.ip, INET)` per Decision 2 and the other three mapped to
   plain columns; add
   `sort_by: HostSortBy = "last_seen_at"` and `sort_order: SortOrder = "desc"` keyword-only
   params to `list_hosts`; replace the hardcoded `order_by` with the resolved direction,
   **keeping `HostRecord.id.asc()` as the tiebreaker** so DMI-84's pagination guarantee
   holds under every sort. → *verify:* existing `test_list_hosts_*` tests still pass
   untouched — defaults must reproduce today's behaviour exactly.
3. **`routers/hosts.py`** — add the two `Query(...)` parameters in the same shape
   `read_scans` uses, and thread them into `list_hosts`. → *verify:*
   `?sort_by=not_a_column` returns `422`.
4. **`tests/test_contract_fidelity.py`** — add `/api/v1/hosts` to `OPERATION_PATHS`, plus
   the `UNIMPLEMENTED_PARAMS` exemption from Decision 1. → *verify:*
   `test_query_parameters_match_contract[/api/v1/hosts]` passes. Note the path also feeds
   the `400`/`422` assertion at line 273 — the contract has `400` on this path
   (`openapi.yaml:314`) and FastAPI emits `422`, so that test passes with no extra work.
5. **`tests/test_read_endpoints.py`** — the issue's five behavioural cases: ascending
   hostname, descending vendor, unspecified defaults to `last_seen_at desc`, bad enum →
   `422`, and 25 hosts across two pages under a non-default sort being disjoint and
   complete. Mirror the existing `test_list_scans_invalid_query_returns_validation_error`
   parametrize style for the `422` case. **Plus a sixth, from Decision 2:** hosts at
   `192.168.1.2`, `.10` and `.20` come back in numeric order under `sort_by=ip`, not
   lexicographic. That one test uses conftest's `administrative_session` +
   `seeded_org` (real Postgres) with a local `get_session` override, because the file's own
   SQLite fixture cannot compile the cast. The other five stay on the fast SQLite fixture.

## Out of scope

Free-text `q` (search is cut from v1). Sort fields beyond the contract's four. Sorting on
`GET /findings` — that endpoint declares none. Any frontend work; the Host Inventory screen
is DMI-88, which this issue unblocks. Any change to default ordering.

Also out of scope: **DMI-99** (the fidelity guard ignores `pattern`, `minLength`,
`maxLength`). `q` carries `minLength: 1`, so the two issues touch the same file — but DMI-99
is about schema shape and this is about the parameter set. They do not overlap in code.
Land this first; DMI-99 stays independent.

## Definition of done

* The six behavioural tests above pass.
* `test_query_parameters_match_contract[/api/v1/hosts]` passes.
* `contracts/openapi/openapi.yaml` is **unmodified**. If the fidelity test disagrees with
  the implementation, the implementation is what changes.
* `frontend/src/types/openapi.d.ts` is unmodified — no contract change means no regeneration.
* `./database.sh --test` green: `uv run ruff check src tests` and `uv run pytest` with
  **0 database skips**. A run with skips is not a green run.
* Per CLAUDE.md: `ruff check` only on `backend/`. Never `ruff format`.
* PR body includes "Fixes DMI-100".
