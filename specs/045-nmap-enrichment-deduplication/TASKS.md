# Tasks — Nmap enrichment deduplication (`045-nmap-enrichment-deduplication`)

3 tasks. **All completed.**

Hardware-agent pipeline. Test agent: `test-engineer`. Review agent: `code-reviewer`.
Gate: `uv run pytest` and `uv run ruff check src tests` from `hardware-agent/`.

---

## Task 1: Make deep inspection the sole service and NSE authority
- **Description**: Implement the argument and mode policy defined by `ARCHITECTURE.md`: remove service and script enrichment from every port-enumeration pass, retain each mode's exact port scope and sole OS probe, and run one full-depth deep enrichment over the discovered open-port union. This includes both NSPi passes and preserves their distinct pacing, exact OT port set, catalog, thresholds, timeouts, batching, retries, and merge behavior.
- **Absorbed**: The effective version-intensity helper, metadata argument summary, and script-policy cleanup are consumed only by this command policy and are tested through the same captured argv; separate tasks would not produce independently useful artifacts.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/config.py`, `hardware-agent/src/agent/discovery/port_discovery.py`, `hardware-agent/src/agent/discovery/vulnerability_detection.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/tests/unit/test_quick_mode_argv.py`, `hardware-agent/tests/unit/test_scan_mode_scripts.py`, `hardware-agent/tests/unit/test_nmap_arguments_summary.py`, `hardware-agent/tests/unit/test_nspi_constants.py`, `hardware-agent/tests/unit/test_nspi_two_pass_merge.py`]
- **Tests**: Existing argument, script-policy, metadata, and NSPi suites prove zero port-stage `-sV`/NSE calls, exactly one deep enrichment per eligible host, intensity at least 7, unchanged catalogs/thresholds, unchanged port coverage, and exact NSPi `T4` broad plus `T2` OT passes.
- **Success Criteria**:
  - Quick and Standard retain the implicit default top-1,000 scope; Extensive retains exactly the top 10,000; MAX retains all 65,535 ports and its minimum rate.
  - NSPi still executes and merges exactly its broad default-top-1,000 pass and seven-port OT pass, while neither pass contains service detection or NSE scripts.
  - Every eligible host is deeply enriched once with `-sV`, the complete selected catalog, the declared CVSS threshold, DNS disabled after discovery, and effective version intensity no lower than the former implicit depth.
  - One OS probe remains in each regular port pass; NSPi retains its current bounded deep-stage OS probe and structured OS merge.
  - NSPi's subsequent serial Modbus inventory/mapping stage remains wired and unchanged.
  - `port_stage_scripts()` has no remaining call site; `deep_stage_scripts()` is the sole script catalog authority.
  - The recorded Nmap argument summary matches the executed policy for all five modes.
  - Tests: captured argv and merge tests fail on any duplicate enrichment, coverage change, NSPi pacing/scope change, catalog/threshold change, or metadata drift.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Prove evidence equivalence across the responsibility split
- **Description**: Preserve the additive merge and host-identity behavior required by `TRUTH.md` and `ARCHITECTURE.md`, then extend deterministic stage and integration coverage so the optimized pipeline retains all evidence admitted by each mode's declared threshold. No payload, normalization, progress, CLI, or UI contract changes are allowed.
- **Absorbed**: The end-to-end deterministic fixture coverage belongs with the evidence-preservation behavior because it is the only meaningful proof that internal merging reaches the final payload intact.
- **Dependencies**: Task 1
- **Target Files**: [`hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/tests/unit/test_stage_isolation.py`, `hardware-agent/tests/integration/test_extensive_e2e.py`]
- **Tests**: Stage isolation and deterministic end-to-end tests prove preservation of identity, open and filtered ports, service name/product/version/extra-info, banners, CPEs, port scripts, host scripts, CVEs, heuristic findings, and NSPi ports discovered only in the OT-specific pass.
- **Success Criteria**:
  - Successful deep evidence is merged by port and protocol without deleting discovery identity or filtered ports.
  - The finalized deterministic payload preserves services, versions, banners, CPEs, script evidence, and normalized findings for all established mode catalogs.
  - An NSPi target discovered only through an OT-specific port remains eligible for the single deep enrichment and produces its applicable industrial evidence.
  - No schema, serialized field, finding rule, event shape, or consumer behavior changes.
  - Tests: evidence-level comparisons exclude only run-specific metadata and naturally variable runtime text.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Mark incomplete enrichment as partial without discarding evidence
- **Description**: Implement the incomplete-unit finalization rules in `ARCHITECTURE.md`. Port and deep stages expose skipped-unit counts, eligible no-result deep scans count as failures, and `ScanRunner` normalizes retained evidence but never labels known missing enrichment as complete.
- **Dependencies**: Task 2
- **Target Files**: [`hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/runner.py`, `hardware-agent/tests/unit/test_stage_isolation.py`, `hardware-agent/tests/unit/test_scan_runner_partial.py`]
- **Tests**: Stage and runner partial-result tests cover port timeout/failure, deep timeout/failure/no-result, mixed successful and failed hosts, zero skips, and cancellation while asserting retained accepted evidence and correct existing metadata.
- **Success Criteria**:
  - A failed, timed-out, or no-result unit never clears evidence already accepted from a successful stage or host.
  - Later useful work and normalization continue when the existing circuit-breaker policy allows it.
  - Any known port or deep skip finalizes through the existing partial payload path with the affected stage identified; zero skips remains complete.
  - Cancellation launches no fallback probe and retains the original termination cause and all already accepted evidence.
  - Existing constructors, callbacks, retries, timeouts, workers, batching, stage order, progress events, payload fields, and exit-code mapping remain unchanged.
  - Tests: mixed-outcome scans cannot be falsely marked complete and successful-host evidence remains intact.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```text
#1 → #2 → #3
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Make deep inspection the sole service and NSE authority | COMPLETED |
| 2 | Prove evidence equivalence across the responsibility split | COMPLETED |
| 3 | Mark incomplete enrichment as partial without discarding evidence | COMPLETED |
