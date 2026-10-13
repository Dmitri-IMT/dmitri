# ADR-022: Scan and machine deletion

> **Status:** Accepted (2026-10-13). Decided in DMI-186.
> **Follows:** [ADR-017](ADR-017-account-removal.md) — hard delete, admin only, org-scoped, typed confirmation.
> **Depends on:** [ADR-014](ADR-014-host-identity-resolution.md) — a deleted machine that is found again gets a new `host_id`.

## Context

Admins could not remove test scans, wrong subnets or old machines. They stayed in every list, count and report.

The UI says **machine** for a host and **device** for a Pi ([FOUNDATIONS](../ui/FOUNDATIONS.md)). This ADR uses the UI words. The API keeps `hosts`.

## Decision

1. **Four admin routes.** `DELETE /scans/{id}`, `DELETE /scans`, `DELETE /hosts/{id}`, `DELETE /hosts`. A viewer gets `403`. Another org's scan or machine gets `404`. Single deletes return `204`. `DELETE /scans` returns `{deleted, skipped, machines_removed}`. `DELETE /hosts` returns `{deleted}`.
2. **Hard delete.** No soft delete, no restore. Each delete writes one activity entry (`scans_deleted` or `machines_deleted`) with the actor, a count, and a readable label for a single item.
3. **Only finished scans.** A scan in `pending`, `accepted` or `processing` returns `409 scan_running`. "Delete all" skips those scans and counts them in `skipped`.
4. **Deleting a scan** removes its machines' rows in that scan, ports, services, CPEs, exposures, industrial services, Modbus units, findings, risk snapshots, enrichment jobs, AI analysis and AI chat. Two rows stay with `scan_id` set to NULL: the Pi `commands` row (true Pi history) and `ai_usage` (money spent).
5. **Machines follow their scans.** After a scan delete, a machine that no other scan observed is deleted. Every other affected machine is rebuilt from its remaining scans: identity fields, first/last seen, open ports, highest severity, `host_ports` and `host_findings`.
6. **Deleting a machine** removes its rows from every old scan, its findings, its host-level and finding-level AI chat, and the machine. The scans stay. Their scan-level AI analysis and chat stay as a dated record, even if they name the machine.
7. **A deleted scan cannot come back.** `deleted_scans` keeps only `scan_id`, `org_id` and `deleted_at`. Ingest refuses an upload for a listed `scan_id` with the existing "scan closed" error. Without this, the late partial upload of a cancelled scan, or a Pi retry, would create the scan again.
8. **Typed confirmation for "delete all".** The admin types the org name (`org_name` is now on `GET /users/me`). The check is in the UI only, as in ADR-017 §5.
9. **Explicit deletes, not cascades.** One service deletes rows in order in one transaction. The runtime role gets `DELETE` on the scan and machine tables and column-level `UPDATE (scan_id)` on `ai_usage`. Shared caches (KEV, EPSS, NVD) are never touched.

## Consequences

- Admins can reset an org's data. Nothing can bring it back.
- A worker job (AI analysis, enrichment) that is running while its scan is deleted fails once and logs an error. It does not recreate data.
- `deleted_scans` grows by one row per deleted scan. It holds no scan content.
