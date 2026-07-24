---
type: Module
title: Backend services — persistence, host identity, read, enrichment, risk
description: The real work — persist_scan, host-identity upsert, the read-path queries, the worker loop, the NVD/KEV/EPSS clients, and the explainable risk scorer.
resource: backend/src/api/services/persistence.py
tags: [backend, services, persistence, read, enrichment, worker, risk]
timestamp: 2026-07-22T00:00:00Z
---

# Backend services — persistence, host identity, read, enrichment, risk

## Purpose

`services/` is where the backend actually does its work. `persistence.py` writes an ingested
`ScanResult` into the [tables](/backend/models.md), resolves host identity, and enqueues enrichment
jobs. `hosts.py` resolves each scan's `ScanHostRecord`s to durable `HostRecord`s. `read.py` answers
the wired [read-path routers](/backend/routers.md) — list/detail queries over hosts, scans, and
findings. `worker.py` is the long-running poll loop. `enrichment.py` claims and processes jobs,
calling the three upstream clients — `nvd.py`, `kev.py`, `epss.py` — each of which caches in the DB.
`risk.py` computes a deterministic, explainable risk score. (`services/__init__.py` is a
placeholder.) `persist_scan` and the worker are still exercised by tests, not the live agent; the
read path and the [auth routes](/backend/auth.md) are the route groups actually reached over HTTP.
The auth services (`auth.py`, `tokens.py`, `passwords.py`, `mailer.py`) are documented in
[auth](/backend/auth.md).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `persist_scan()` | Idempotent on `scan_id` (returns the existing `ScanRecord` if present). Inserts the scan (with `scan_mode`, `status` defaulting `completed`) + artifacts, persists each host→port (writing `ServiceRecord` + `CPERecord`s) building `scan_host_index`/`port_index`, upserts each agent finding, calls `upsert_hosts_for_scan` in the same transaction, then enqueues enrichment jobs. | `backend/src/api/services/persistence.py:23` |
| `upsert_finding()` | Dedups on `finding_dedupe_key`. New → insert (initial confidence `probable` if `cve_id` else `tentative`) + `refresh_risk_snapshot`. Existing → merge references/source-labels, take `_max_severity`/`_max_confidence`, prefer the higher cvss, re-run risk. | `backend/src/api/services/persistence.py:90` |
| `finding_dedupe_key()` | `ip|protocol|port|(cve_id or lowercased title)`. | `backend/src/api/services/persistence.py:173` |
| `_persist_scan_host()` | Inserts one `ScanHostRecord` (`ip`/`mac`/`hostname`/`vendor`) for the scan. | `backend/src/api/services/persistence.py:191` |
| `_enqueue_enrichment_jobs()` | One `nvd_cpe` job per `(port, CPE)`; per finding with a `cve_id` → `nvd_cve` + `kev_cve` + `epss_cve`, dedup via a `seen` set. | `backend/src/api/services/persistence.py:229` |
| `identity_key()` | `mac:<MAC upper>` if a MAC is present, else `ip:<ip>` — the durable-identity key. | `backend/src/api/services/hosts.py:17` |
| `upsert_hosts_for_scan()` | For every `ScanHostRecord` in the scan: looks up a `HostRecord` by `(org_id, identity_key)`; creates one on first sight, else updates it **only if this scan is the newest seen so far** (extends `first_seen_at`, and on newest overwrites the ip/mac/hostname/vendor snapshot + `open_ports_count`/`highest_severity`); sets `scan_host.host_id`. | `backend/src/api/services/hosts.py:23` |
| `list_hosts()` | Paginated `HostRecord` list ordered by `last_seen_at desc` → `HostListResponse`. | `backend/src/api/services/read.py:29` |
| `get_host_detail()` | One host's latest `ScanHostRecord` (for current ports) + full scan history (ordered by `ScanRecord.timestamp desc`) → `HostDetailResponse`. | `backend/src/api/services/read.py:44` |
| `get_scan_detail()` | One scan's hosts (as `ScanHostView`, `host_id` required) + findings (host_id resolved via outer join) → `ScanDetailResponse`. | `backend/src/api/services/read.py:91` |
| `list_findings()` | Paginated `FindingRecord` list, optionally filtered by `host_id` (via join on `ScanHostRecord`) → `FindingListResponse`. | `backend/src/api/services/read.py:133` |
| `run_worker_loop()` | Reads poll interval + batch size from `Settings`, loops forever calling `run_worker_once()`, sleeps `poll_interval` when idle or after a logged exception. | `backend/src/api/services/worker.py:13` |
| `run_worker_once()` | Opens a session via `get_session()` and delegates to `process_pending_enrichment_jobs`. | `backend/src/api/services/worker.py:34` |
| `claim_pending_enrichment_jobs()` | Selects `pending` jobs by `created_at,id`; on Postgres uses `SELECT ... FOR UPDATE SKIP LOCKED`; flips them to `running`, bumps `attempts`, commits. | `backend/src/api/services/enrichment.py:22` |
| `process_claimed_enrichment_job()` | Dispatches by `job_type` to `_process_cpe/cve/kev/epss_job`; success → `completed`; exception → rollback + `failed` with `last_error`. | `backend/src/api/services/enrichment.py:52` |
| `_process_cpe_job()` | NVD-by-CPE → one new finding per match (source `nvd_enrichment`, confidence `probable`) via `upsert_finding`, resolving the `ScanHostRecord` (variable still named `device` locally) via `port_record.scan_host_id`. | `backend/src/api/services/enrichment.py:115` |
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
  [overview data flow](/backend/overview.md), and calls `upsert_hosts_for_scan` in the same
  transaction to resolve durable host identity.
- `read.py`'s functions back the [hosts/scans/findings routers](/backend/routers.md) directly — this
  is the one service group actually invoked over HTTP.
- The worker entry [`worker_main.py`](/backend/api.md) calls `run_worker_loop`; the loop's cadence
  and batch size come from `Settings` in [config](/backend/api.md).
- Every enrichment path ends in `refresh_risk_snapshot`, so a finding always has a current risk row.
- Upstream cache tables (`nvd_cache`, `kev_cache`, `epss_cache`) and result tables
  (`kev_records`, `epss_records`, `risk_snapshots`) are defined in [models](/backend/models.md).

## Notes / gotchas

- **Confidence ladder.** `tentative` → `probable` (agent CVE or CPE match) → `confirmed` (NVD-by-CVE).
  `upsert_finding` only ever raises confidence via `_max_confidence`, never lowers it.
- **Idempotency.** `persist_scan` returns early if the `scan_id` already exists — re-ingest is safe.
- **Host identity is scan-order-sensitive.** `upsert_hosts_for_scan` only overwrites the `HostRecord`
  snapshot (ip/mac/hostname/vendor/open_ports_count/highest_severity) when the incoming scan's
  `timestamp` is `>=` the current `last_seen_at`; an out-of-order (backfilled) scan only extends
  `first_seen_at`.
- **`SKIP LOCKED` is Postgres-only.** On other dialects the claim query runs without row locking, so
  concurrent workers are only safe against Postgres (the deployed DB).
- **Findings are hosts' findings** — they reference `ScanHostRecord` (per-scan observation) rows via
  `scan_host_id`; the durable `HostRecord` is resolved separately. See [glossary](/glossary.md).

# Citations

[1] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
