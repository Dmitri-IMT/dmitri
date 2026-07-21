---
type: Module
title: Backend services — persistence, worker, enrichment, risk
description: The real work — persist_scan, the worker loop, the NVD/KEV/EPSS clients, and the explainable risk scorer.
resource: backend/src/api/services/persistence.py
tags: [backend, services, persistence, enrichment, worker, risk]
timestamp: 2026-07-21T00:00:00Z
---

# Backend services — persistence, worker, enrichment, risk

## Purpose

`services/` is where the backend actually does its work. `persistence.py` writes an ingested
`ScanResult` into the [tables](/backend/models.md) and enqueues enrichment jobs. `worker.py` is the
long-running poll loop. `enrichment.py` claims and processes jobs, calling the three upstream
clients — `nvd.py`, `kev.py`, `epss.py` — each of which caches in the DB. `risk.py` computes a
deterministic, explainable risk score. (`services/__init__.py` is a placeholder.) None of this is
reached over HTTP today; tests call `persist_scan` and the worker functions directly.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `persist_scan()` | Idempotent on `scan_id` (returns the existing `ScanRecord` if present). Inserts the scan + artifacts, persists each device→port (writing `ServiceRecord` + `CPERecord`s) building `device_index`/`port_index`, upserts each agent finding, then enqueues enrichment jobs — all in one transaction. | `backend/src/api/services/persistence.py:22` |
| `upsert_finding()` | Dedups on `finding_dedupe_key`. New → insert (initial confidence `probable` if `cve_id` else `tentative`) + `refresh_risk_snapshot`. Existing → merge references/source-labels, take `_max_severity`/`_max_confidence`, prefer the higher cvss, re-run risk. | `backend/src/api/services/persistence.py:88` |
| `finding_dedupe_key()` | `ip|protocol|port|(cve_id or lowercased title)`. | `backend/src/api/services/persistence.py:171` |
| `_enqueue_enrichment_jobs()` | One `nvd_cpe` job per `(port, CPE)`; per finding with a `cve_id` → `nvd_cve` + `kev_cve` + `epss_cve`, dedup via a `seen` set. | `backend/src/api/services/persistence.py:227` |
| `run_worker_loop()` | Reads poll interval + batch size from `Settings`, loops forever calling `run_worker_once()`, sleeps `poll_interval` when idle or after a logged exception. | `backend/src/api/services/worker.py:13` |
| `run_worker_once()` | Opens a session via `get_session()` and delegates to `process_pending_enrichment_jobs`. | `backend/src/api/services/worker.py:34` |
| `claim_pending_enrichment_jobs()` | Selects `pending` jobs by `created_at,id`; on Postgres uses `SELECT ... FOR UPDATE SKIP LOCKED`; flips them to `running`, bumps `attempts`, commits. | `backend/src/api/services/enrichment.py:22` |
| `process_claimed_enrichment_job()` | Dispatches by `job_type` to `_process_cpe/cve/kev/epss_job`; success → `completed`; exception → rollback + `failed` with `last_error`. | `backend/src/api/services/enrichment.py:52` |
| `_process_cpe_job()` | NVD-by-CPE → one new finding per match (source `nvd_enrichment`, confidence `probable`) via `upsert_finding`. | `backend/src/api/services/enrichment.py:115` |
| `_process_cve_job()` | NVD-by-CVE → **upgrades** the existing finding to `confirmed`, refreshes cvss/severity/references, adds the `nvd` label + evidence, re-runs risk. | `backend/src/api/services/enrichment.py:167` |
| `_process_kev_job()` / `_process_epss_job()` | Fetch + `upsert_kev_record`/`upsert_epss_record`, tag the finding with the `kev`/`epss` label + evidence, re-run risk. | `backend/src/api/services/enrichment.py:199` |
| `NvdClient` + `parse_nvd_matches()` | `query_by_cpe`/`query_by_cve` with a `NvdCacheRecord` DB cache (12h TTL), sends the `apiKey` header when set; parser prefers CVSS V31→V30→V2, `_severity_from_cvss` (≥9 critical, ≥7 high, ≥4 medium, else low). | `backend/src/api/services/nvd.py:13` |
| `KevClient` + `parse_kev_record()` + `upsert_kev_record()` | Fetches the full CISA KEV JSON feed, scans `vulnerabilities[]` for the CVE (`date_added`, `known_ransomware` from `knownRansomwareCampaignUse`, `required_action`); per-CVE `KevCacheRecord` (24h TTL). | `backend/src/api/services/kev.py:13` |
| `EpssClient` + `parse_epss_record()` + `upsert_epss_record()` | FIRST EPSS query by CVE (`?cve=`), `epss_score` (0–1) + `percentile`; per-CVE `EpssCacheRecord` (24h TTL). | `backend/src/api/services/epss.py:13` |
| `refresh_risk_snapshot()` | Deterministic scorer (see below); upserts one `RiskSnapshotRecord` per finding. | `backend/src/api/services/risk.py:28` |

## The risk score

`refresh_risk_snapshot` (`backend/src/api/services/risk.py:28`) combines a severity weight
(low `.25` → critical `1.0`), a confidence weight (tentative `.5` → confirmed `1.0`), the EPSS
score, a KEV boost `+0.3`, a ransomware boost `+0.1`, and an exposed-service boost `+0.05`:

- `exploitability = min(1, epss*0.7 + kev_boost + ransomware_boost)`
- `risk_score = min(100, severity*45 + exploitability*35 + confidence*15 + exposed*100)`

with a human-readable `rationale` string. It is intentionally deterministic and explainable — any
ML/AI scoring is future work.

## How it connects

- `persist_scan` consumes a [`ScanResult`](/backend/schemas.md) and writes the
  [ORM models](/backend/models.md); it is called (by tests today) as step 2 of the
  [overview data flow](/backend/overview.md).
- The worker entry [`worker_main.py`](/backend/api.md) calls `run_worker_loop`; the loop's cadence
  and batch size come from `Settings` in [config](/backend/api.md).
- Every enrichment path ends in `refresh_risk_snapshot`, so a finding always has a current risk row.
- Upstream cache tables (`nvd_cache`, `kev_cache`, `epss_cache`) and result tables
  (`kev_records`, `epss_records`, `risk_snapshots`) are defined in [models](/backend/models.md).

## Notes / gotchas

- **Confidence ladder.** `tentative` → `probable` (agent CVE or CPE match) → `confirmed` (NVD-by-CVE).
  `upsert_finding` only ever raises confidence via `_max_confidence`, never lowers it.
- **Idempotency.** `persist_scan` returns early if the `scan_id` already exists — re-ingest is safe.
- **`SKIP LOCKED` is Postgres-only.** On other dialects the claim query runs without row locking, so
  concurrent workers are only safe against Postgres (the deployed DB).
- **Findings are hosts' findings** — they reference `DeviceRecord` (host) rows; see
  [glossary](/glossary.md).

# Citations

[1] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
