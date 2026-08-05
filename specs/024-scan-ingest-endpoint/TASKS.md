# Tasks — Scan ingest endpoint (DMI-63)

Execution is sequential because the service and route work depend on the contract and persistence
model changes. Backend reviewers must run the live `dmitri_test` database gates described in
`ARCHITECTURE.md`; frontend reviewers must run the scoped frontend gates when the generated type
file changes.

## Task 1: Tighten ingest schemas and contract
- **Description**: Add the ingest-only `PortPayload` contract correction, rename the backend ingest models to the contract vocabulary, forbid unknown fields at every ingest depth, make contract-required fields required, remove artifact payload models/fields, update exports, and extend schema/contract fidelity coverage.
- **Dependencies**: —
- **Target Files**: [contracts/openapi/openapi.yaml, backend/src/api/schemas/scan.py, backend/src/api/schemas/__init__.py, backend/src/api/schemas/persistence.py, backend/tests/test_ingest_schema.py, backend/tests/test_contract_fidelity.py]
- **Success Criteria**: The OpenAPI change is exactly the `PortPayload` component plus the `HostPayload.ports` reference; Python ingest schemas match all five declared components and reject nested unknown fields, missing required fields, and IPv6; artifact payload traces are removed; read-side `Port` remains unchanged; the schema and contract fidelity tests cover the new names and endpoint contract expectations without broadening read responses.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Add persistence model and reversible migration
- **Description**: Record the submitting agent on scans, remove the obsolete artifact persistence model, add the `20260804_14` Alembic revision, and update migration-baseline and migration round-trip tests.
- **Dependencies**: 1
- **Target Files**: [backend/src/api/models/persistence.py, backend/alembic/versions/20260804_14_scan_ingest_rework.py, backend/tests/test_migrations.py, backend/tests/test_scan_ingest_migration.py]
- **Success Criteria**: `ScanRecord.agent_id` is nullable with the declared foreign key and no backfill; `ArtifactRecord` is gone; upgrading drops `artifacts` and adds `scans.agent_id`; downgrading recreates `artifacts` and removes only the new column; existing scan data survives the round trip; migration security/baseline tests pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Rework persistence into authenticated, atomic ingest
- **Description**: Add the scan lookup helper and implement `ingest_scan` plus the reworked single-transaction `persist_scan`, including requested-scan filling, unrequested-scan creation, ownership checks, terminal-command refusal, idempotent completed scans, enrichment preservation, and artifact-loop removal. Update affected service call sites and focused service tests.
- **Dependencies**: 1, 2
- **Target Files**: [backend/src/api/services/commands.py, backend/src/api/services/persistence.py, backend/src/api/services/hosts.py, backend/src/api/services/enrichment.py, backend/tests/test_ingest_scan.py, backend/tests/test_host_materialisation.py, backend/tests/test_read_schema.py, backend/tests/test_finding_severity_migration.py]
- **Success Criteria**: Requested placeholders are filled and linked to the submitting agent/organisation; unrequested scans are created complete; repeated owned submissions perform no duplicate writes; foreign and written-off scans are rejected; all ingest writes are atomic; existing host identity and enrichment behavior remains intact, including one `nvd_cpe` job per distinct CPE; direct tests cover ownership, identity stability, and both rollback paths; all changed `persist_scan` call sites pass the new keyword signature.
- **Status**: COMPLETED
- **Review Rejections**: 0
- **Note**: `backend/tests/test_finding_severity_migration.py` added to Target Files during execution — `test_live_upgrade_preserves_seeded_findings` seeds the `ScanRecord` ORM model against a schema downgraded to `20260724_11`, so Task 2's new `ScanRecord.agent_id` column makes the INSERT fail with `UndefinedColumn`. A regression introduced by this feature, not pre-existing.
- **Note**: `backend/tests/test_read_schema.py` added to Target Files during execution — its line 7 `from api.schemas import Host` and the `ScanHostView is not Host` assertions at lines 114-116 reference the name Task 1 renamed to `HostPayload`. Not listed in the original decomposition.

## Task 4: Expose the signed scan-ingest route and full integration coverage
- **Description**: Add `POST /api/v1/scans` with the existing agent authentication dependency, map service outcomes to the frozen response/status contract, and add signed-request integration tests for accepted, rejected, repeated, late, malformed, isolated, and completion scenarios.
- **Dependencies**: 3
- **Target Files**: [backend/src/api/routers/scans.py, backend/tests/test_require_agent.py, backend/tests/test_scan_ingest_route.py]
- **Success Criteria**: The endpoint is mounted as `ingestScan`, accepts valid signed submissions with the declared 202 acknowledgement, authenticates before model validation for syntactically valid invalid payloads, distinguishes 401/403/400/422 cases, preserves all-or-nothing behavior and organisation/device isolation, accepts separately re-signed repeats but rejects nonce replays, refuses late results after write-off, and leaves completed scans unchanged on late progress reports; route and auth regression tests cover the acceptance criteria and pass with no database skips.
- **Status**: COMPLETED
- **Review Rejections**: 1
