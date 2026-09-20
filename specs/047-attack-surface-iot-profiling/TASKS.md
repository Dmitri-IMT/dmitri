# TASKS — Attack surface and IoT profiling

Execution is sequential. Every task passes through implementation, independent tests, and review before a dependent task starts.

## Dependency graph

```text
001 -> 002 -> 003
  |      |
  |      +-----> 005
  +-----------> 004 -> 005 -> 006 -> 007
```

## Status

| Task | Summary | Status | Review Rejections |
|---|---|---|---:|
| 001 | Agent assessment contracts and deterministic policy | DONE | 7 |
| 002 | Agent pipeline and local payload integration | DONE | 0 |
| 003 | Local TUI assessment presentation | DONE | 2 |
| 004 | Canonical contract and backend persistence | DONE | 1 |
| 005 | Backend reconciliation and read models | DONE | 0 |
| 006 | React scan assessment presentation | DONE | 0 |
| 007 | React host assessment presentation | DONE | 0 |

## Task 001 — Agent assessment contracts and deterministic policy

**Description:** Add the legacy-compatible assessment payload models and the pure, versioned local analyzer that turns accepted `HostInfo` evidence into one exposure per open endpoint plus a conservative device profile.

**Dependencies:** None.

**Target Files:**

- `hardware-agent/src/agent/assessment/__init__.py`
- `hardware-agent/src/agent/assessment/policy.py`
- `hardware-agent/src/agent/assessment/analyzer.py`
- `hardware-agent/src/agent/normalize/contracts.py`
- `hardware-agent/src/agent/normalize/__init__.py`
- `hardware-agent/tests/test_contract_models.py`
- `hardware-agent/tests/unit/test_assessment_policy.py`
- `hardware-agent/tests/unit/test_assessment_analyzer.py`

**Success Criteria:**

- Exact enums, bounds, defaults, current-versus-legacy invariants, endpoint cardinality, and canonical nine-value `MachineType` match `ARCHITECTURE.md`.
- `LOCAL_ASSESSMENT_POLICY_VERSION` is `2026-09-15.1`; rule tables, weights, thresholds, attention, confidence, and stable ordering match the approved deterministic policy.
- Analyzer covers open/closed/filtered endpoints, service-role mappings, conflicting and insufficient evidence, randomized MAC, bounded redacted evidence, deduplication, and unknown results without inventing identity.
- Repeated assessment of identical normalized evidence is byte-for-byte deterministic and performs no socket, subprocess, filesystem, cloud, or generative I/O.
- Focused contract, policy, and analyzer tests pass; hardware-agent Ruff passes for changed files.

**Status:** DONE

**Review Rejections:** 7

## Task 002 — Agent pipeline and local payload integration

**Description:** Execute the assessment as a normalization substep for normal and accepted-partial results, populate host profiles/types and top-level exposures, and preserve legacy workspace reads and existing runner event/constructor behavior.

**Dependencies:** Task 001.

**Target Files:**

- `hardware-agent/src/agent/scanner/runner.py`
- `hardware-agent/src/agent/scanner/stages.py`
- `hardware-agent/tests/unit/test_scan_runner_events.py`
- `hardware-agent/tests/unit/test_workspace.py`
- `hardware-agent/tests/integration/test_extensive_e2e.py`

**Success Criteria:**

- `_build_payload` assesses accepted hosts on normal and partial normalization paths in every scan mode without adding a stage, constructor parameter, event, timeout, or network operation.
- Each current host carries the canonical machine type and device profile; each unique accepted open endpoint has exactly one exposure; raw host/port/service evidence remains unchanged.
- Pre-feature JSON still validates as assessment unavailable, while current payloads round-trip without information loss.
- Every `ScanRunner`, `ScanProgressScreen`, `ScanPayload`, and validation call site is audited for current/legacy intent and existing call paths remain compatible.
- Focused runner/workspace/e2e tests pass; hardware-agent Ruff passes for changed files.

**Status:** DONE

**Review Rejections:** 0

## Task 003 — Local TUI assessment presentation

**Description:** Replace the raw scan dump with the approved local summary and device detail experience while keeping the TUI fully disconnected from backend transport.

**Dependencies:** Task 002.

**Target Files:**

- `hardware-agent/src/agent/tui/screens/scan_view.py`
- `hardware-agent/src/agent/tui/screens/device_detail.py`
- `hardware-agent/src/agent/tui/screens/home.py`
- `hardware-agent/src/agent/tui/app.tcss`
- `hardware-agent/tests/unit/test_tui_scan_view.py`
- `hardware-agent/tests/unit/test_tui_device_detail.py`
- `hardware-agent/tests/integration/test_tui_flows.py`

**Success Criteria:**

- Scan summary separately presents machines, attack-surface exposures, and vulnerability findings; exposure attention never changes finding/severity totals.
- Device detail shows raw identity/inventory, assessed profile with evidence/conflicts/limitations, exposures, findings, and endpoint relationships using the copy/states in `DESIGN.md`.
- Current-empty, legacy-unavailable, finished-incomplete, and stopped-interrupted states are distinguishable and never produce false clean/zero claims.
- Fresh and saved scan navigation summary → device detail → back works with stable widget IDs, and no TUI path imports or invokes backend transport.
- Focused TUI unit/integration tests pass; hardware-agent Ruff passes for changed files.

**Status:** DONE

**Review Rejections:** 2

## Task 004 — Canonical contract and backend persistence

**Description:** Extend the canonical OpenAPI and example, mirror ingest validation in FastAPI, add the additive secured migration/ORM model, and atomically persist immutable assessment snapshots and exposures.

**Dependencies:** Task 001.

**Target Files:**

- `contracts/openapi/openapi.yaml`
- `contracts/examples/scan_result.example.json`
- `backend/src/api/schemas/scan.py`
- `backend/src/api/schemas/__init__.py`
- `backend/src/api/models/persistence.py`
- `backend/src/api/models/__init__.py`
- `backend/alembic/versions/20260920_33_attack_surface_profiles.py`
- `backend/src/api/services/persistence.py`
- `backend/tests/test_ingest_schema.py`
- `backend/tests/test_ingest_scan.py`
- `backend/tests/test_attack_surface_migration.py`
- `backend/tests/test_contract_fidelity.py`

**Success Criteria:**

- OpenAPI, agent, and backend ingest models agree on exact enums, fields, limits, defaults, and current-versus-legacy cardinality/reference invariants; the canonical example validates in both Python layers.
- Migration revision `20260920_33` depends on `20260919_32`, is additive/no-backfill, creates the specified nullable snapshots and `exposures` table constraints/indexes/FKs, enables RLS, and grants only runtime SELECT/INSERT/UPDATE with a correct downgrade.
- Ingest resolves each exposure to its scan-host/open-port row and persists version, profile, type, evidence, and relationships atomically/idempotently without changing finding aggregates.
- Legacy payloads remain accepted and an invalid current payload returns validation failure before persistence.
- Focused backend schema, persistence, migration, and contract-fidelity tests pass; backend Ruff passes for changed files.

**Status:** DONE

**Review Rejections:** 1

## Task 005 — Backend reconciliation and read models

**Description:** Reconcile current/legacy inventory projections and expose organization-scoped assessment availability, profiles, exposures, and related findings through existing scan and host reads.

**Dependencies:** Tasks 002 and 004.

**Target Files:**

- `backend/src/api/schemas/read.py`
- `backend/src/api/services/inventory.py`
- `backend/src/api/services/read.py`
- `backend/tests/test_inventory_reconcile.py`
- `backend/tests/test_read_scans.py`
- `backend/tests/test_read_hosts.py`
- `backend/tests/test_contract_fidelity.py`

**Success Criteria:**

- Current assessed snapshots copy the agent machine type/profile/version; newer legacy snapshots use the existing PR-143 classifier and clear current profile/version; older scans change neither projection.
- Existing scan and host endpoints return explicit `available|unavailable`, immutable/latest profile data, stably ordered exposures, and related finding IDs without adding a standalone exposure endpoint.
- Reads remain organization-scoped and distinguish current-empty from legacy-unavailable and finished-incomplete from stopped-interrupted.
- Vulnerability counts, severities, risk semantics, and existing raw inventory remain unchanged.
- Focused reconciliation/read/contract tests pass; backend Ruff passes for changed files.

**Status:** DONE

**Review Rejections:** 0

## Task 006 — React scan assessment presentation

**Description:** Regenerate API types and present scan-level assessment status, category totals, exposure details, partial states, and finding relationships using existing query and disclosure patterns.

**Dependencies:** Task 005.

**Target Files:**

- `frontend/src/types/openapi.d.ts`
- `frontend/src/components/AttentionWord.tsx`
- `frontend/src/components/AttentionWord.test.tsx`
- `frontend/src/pages/scans/ExposureTable.tsx`
- `frontend/src/pages/scans/exposureColumns.tsx`
- `frontend/src/pages/ScanDetail.tsx`
- `frontend/src/pages/ScanDetail.test.tsx`
- `frontend/src/test/scansHarness.ts`

**Success Criteria:**

- Types are generated from canonical OpenAPI and application shapes use `components['schemas']` only.
- Scan detail separates inventory, attack surface, and vulnerabilities; attention is not rendered as severity/CVSS and exposure totals never affect vulnerability totals.
- Expansion preserves stored evidence order and related-finding controls reveal the referenced existing finding.
- Loading, error/404, available-empty, legacy-unavailable, finished-incomplete, and stopped-interrupted render the exact semantic states and required test IDs from `DESIGN.md` without false zeroes.
- Focused frontend tests pass, a second type generation is clean, and frontend lint/format-check/typecheck pass for the change.

**Status:** DONE

**Review Rejections:** 0

## Task 007 — React host assessment presentation

**Description:** Add the host profile and latest attack-surface sections to host detail while retaining independent vulnerability, inventory, history, loading, and error behavior.

**Dependencies:** Task 006.

**Target Files:**

- `frontend/src/pages/hosts/HostProfile.tsx`
- `frontend/src/pages/hosts/HostExposures.tsx`
- `frontend/src/pages/HostDetail.tsx`
- `frontend/src/pages/HostDetail.test.tsx`
- `frontend/src/test/hostsHarness.ts`

**Success Criteria:**

- Host detail composes assessed profile, exposures, vulnerabilities, services, and scan history in the approved order without replacing original observed identity.
- Confident, unknown, contradictory, randomized-MAC, null product/model, current-empty, and legacy-unavailable states preserve uncertainty and never invent an IoT class or model.
- Exposure relationships navigate to the relevant scan/finding while independently fetched vulnerability loading/error remains local to that section.
- Required accessibility names/test IDs and the exact unavailable/empty semantics in `DESIGN.md` are covered.
- Focused tests and the full frontend lint, format-check, typecheck, test, and build gates pass; regenerated types remain clean.

**Status:** DONE

**Review Rejections:** 0
