# Open questions — 015-read-path

All design-tree decisions were resolved in the 2026-07-22 grilling session. Kept for
traceability; none are blockers.

| # | Question | Resolution |
|---|----------|-----------|
| 1 | C9 shared-schema break | Split response-only `ScanHostView`; ingest `HostPayload` untouched |
| 2 | `scan_mode`/`status` mapping gap | Fixed at source — vestigial `target_mode`/`scan_profile` removed; read directly |
| 3 | Device vs Host vocabulary | Unified to `host` end to end — **ADR-013** supersedes the ADR-011 ingest freeze |
| 4 | Host identity rule | MAC-else-IP, written at ingest — **ADR-014** (accepted limitations documented) |
| 5 | Two-level model + names | Durable **`Host`** + per-scan **`ScanHost`** (renamed `DeviceRecord`) |
| 6 | HOST DETAIL ports/severity | Latest scan's observation, not a union |
| 7 | Materialisation timing | At ingest, inside `persist_scan` |
| 8 | Packaging | Single cross-layer PR (option B) — `backend/` + `contracts/` + `hardware-agent/` |
| 9 | Migrations / data | Empty DB assumed; no backfill |
| 10 | `org_id` NULL | Transitional via `NULLS NOT DISTINCT` until the auth epic |
| 11 | Auth | No JWT enforcement now; routes structured to wrap later |

## Residual notes for implementers (not blockers)

- **Pi rename blast radius** is larger than ADR-013's "one serialization boundary" text: it
  reaches `scanner/stages.py`, `scanner/runner.py`, three TUI screens, and nine Pi test files.
  See `ARCHITECTURE.md` §"Rename blast radius".
- **`test_health.py` `DISCARDED_BUSINESS_PATHS`** must be re-checked once `/api/v1/findings` and
  `/api/v1/scans/{scan_id}` are mounted (they stop being 404s).
- **`PersistedDevice`** (`schemas/persistence.py`) is dead code left un-renamed deliberately —
  flagged, not fixed, to avoid scope creep.
