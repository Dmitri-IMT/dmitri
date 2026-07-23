# TRUTH — Read path: hosts, scan detail, and findings

Domain language and verifiable behaviour only. No file paths, no code.

> **Source issue:** DMI-74 "Add the missing read-path fields" (epic DMI-70, closes contract
> asks **C6, C9, C11**). The issue was written assuming the read endpoints already exist and
> only three fields were missing. In the current backend they do **not** exist — the app
> serves only `/health`, and there is no persistent host identity (only per-scan device rows).
> Per an explicit scope decision on 2026-07-22, this spec therefore covers the **whole read
> path** the three fields live on: the host-identity model plus the four read endpoints,
> built to the shapes already fixed in `contracts/openapi/openapi.yaml`. This deliberately
> exceeds DMI-74's "NOT expected: no new endpoints" fence — that fence assumed the endpoints
> were already there. It also folds in two **ingest corrections** (2026-07-22 decisions):
> (1) the stored `target_mode`/`scan_profile` are unused vestigial fields that do not match the
> real scanner upload, so they are replaced by `scan_mode` (+ a `status` column); and (2) the
> ingest payload is unified to the `host` vocabulary end to end — `devices`→`hosts`,
> `DevicePayload`→`HostPayload`, `devices_received`→`hosts_received` — per
> [`ADR-013`](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md), retiring "device"
> from the wire. Host identity resolution is fixed by
> [`ADR-014`](../../docs/adr/ADR-014-host-identity-resolution.md). Follow-ups (auth enforcement,
> failure reason C10, the full scan-lifecycle) stay separate.

## Narrative

The web UI is fully designed against a read contract that the backend has not yet built. An
admin needs three read screens to work: **HOME** (what machines are on my network, and which
are new), **SCAN DETAIL** (the hosts a given scan touched, each linking to its machine), and
**HOST DETAIL** (one machine's ports, its severity, and the findings that justify that
severity). Today the scanner persists devices **per scan** — the same physical machine seen
in two scans is two unrelated rows with no shared identity, no "first seen" date, and no
stable id a URL can point at. Without a persistent host, HOME cannot say "new device", a scan
row cannot link anywhere, and HOST DETAIL cannot show the findings behind the severity it
displays. This feature introduces the persistent **host** and serves the read endpoints that
expose it, matching the contract the frontend is already coded against.

## Business rules

- A **host** is a physical machine tracked across scans within one organisation. It has a
  stable identifier (`host_id`, a UUID) that does not change between scans.
- **Host identity** is resolved per organisation by MAC address when the scan observed one,
  otherwise by IP address. Two device observations that resolve to the same identity are the
  same host. *(Assumption — see approval gate; `first_seen_at` semantics depend on it.)*
- **`first_seen_at`** is the timestamp of the earliest scan in which the host was ever
  observed; it never moves once set. **`last_seen_at`** is the timestamp of the most recent
  scan that observed it.
- A host is **new** to the admin when its `first_seen_at` falls within the most recent scan —
  i.e. the host had never been seen before that scan. HOME uses `first_seen_at` to decide this.
- A host's mutable attributes (hostname, vendor, open ports, highest severity) reflect its
  **most recent** observation.
- **`scan_mode` is the single canonical name for a scan's intensity** — one of `quick`,
  `standard`, `extensive`, `nspi`, `max`. The scanner already produces exactly these values
  (they drive which scripts run and the timeouts) and the read screens already expect them, so
  the backend stores `scan_mode` verbatim. The previously-stored `target_mode`/`scan_profile`
  had no consumer anywhere (no behaviour branches on them, the scanner does not emit them, the
  frontend does not ask for them) and did not even match the scanner's real upload; they are
  removed. No second vocabulary (`scan_type`, `scan_profile`) is introduced.
- **`status` records a scan's lifecycle** — one of `pending`, `accepted`, `processing`,
  `completed`, `failed`. A scan that has been persisted is `completed`; the other states are
  owned by the command-channel work and are not produced here. The scanner does not send
  `status`; the backend assigns it.
- A **scan's** read detail exposes `scan_mode` and `status` **directly from the stored scan** —
  no translation between vocabularies, because there is only one vocabulary.
- Every host row returned on a **scan's** detail carries the `host_id` of the host it resolves
  to, so the UI can link a scan row to that machine's page.
- **Findings filter by host** using the same `host_id`: the identifier that fetches a host's
  detail is the identifier that fetches its findings. There is one host identifier with one
  name (`host_id`) across the read model. *(C11 was already resolved in the docs/contract by
  the `device_id`→`host_id` rename on 2026-07-13; this spec only ensures the implementation
  honours it.)*
- The **ingest** payload the scanner Pi sends is unchanged and keeps its `devices`/`ip`
  vocabulary; the `host` concept is a read-model projection built during/after ingest, not a
  change to what the Pi uploads.
- Read responses match `contracts/openapi/openapi.yaml` exactly for the fields this spec
  touches (`HostSummary`, `HostDetailResponse`, `DevicePayload`, `FindingPayload`,
  `ScanDetailResponse` and their list envelopes).

## User stories

1. As an admin on HOME, I want to see which hosts are new on my network, so I notice what
   appeared without me.
2. As an admin viewing a scan, I want to click a host row and land on that machine's full
   history, so I can investigate it.
3. As an admin on HOST DETAIL, I want to see the findings behind the severity the page shows,
   so the severity is explained rather than asserted.
4. As an admin, I want a host's history to persist across scans, so "first seen" and a stable
   link to the machine are meaningful.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| host list carries first_seen | one host observed across two scans | `GET /api/v1/hosts` | every row has `first_seen_at`, equal to the earliest observing scan's timestamp, and it does not change when a later scan re-observes the host |
| new-device signal | a host first observed only in the latest scan | `GET /api/v1/hosts` | that host's `first_seen_at` equals the latest scan's timestamp (so the UI can flag it new) |
| stable identity across scans | the same machine (same MAC) in scan A and scan B | `GET /api/v1/hosts` | it appears once, with a single `host_id`, `last_seen_at` = scan B's timestamp |
| scan row links to host | a scan whose result includes a device | `GET /api/v1/scans/{scan_id}` | each host entry carries a `host_id` |
| scan detail shows mode+status | a persisted scan ingested with `scan_mode` | `GET /api/v1/scans/{scan_id}` | response carries `scan_mode` equal to the ingested value and `status` = `completed`, with no vocabulary translation |
| ingest accepts scanner payload | the scanner's real upload (`scan_id`, `timestamp`, `subnet`, `scan_mode`, `devices`, `findings`) | it is validated by the backend ingest schema | it is accepted (no `target_mode`/`scan_profile` required) and persists `scan_mode` + `status=completed` |
| that link resolves | the `host_id` from a scan detail row | `GET /api/v1/hosts/{host_id}` | returns that host's detail (200), including `first_seen_at` and `last_seen_at` |
| findings by host | a host with findings | `GET /api/v1/findings?host_id=<host_id>` | returns exactly that host's findings, using the same `host_id` that resolves host detail |
| host detail explains severity | a host whose detail shows `highest_severity` | `GET /api/v1/findings?host_id=<host_id>` | returns the findings whose severities include that highest severity (severity is explainable, not just asserted) |
| unknown host | a `host_id` that does not exist | `GET /api/v1/hosts/{host_id}` | 404 |
| contract shape | any of the above responses | validated against `openapi.yaml` | the touched fields (`first_seen_at`, `host_id`, `last_seen_at`, host/finding shapes) match the contract |
| quality gate | the touched backend scope | `uv run pytest` and `uv run ruff check` | both pass |

## Out of scope (v1)

- **Auth enforcement.** The contract marks these endpoints JWT-Bearer-protected; identity/JWT
  is a separate epic. This spec builds the read behaviour and data shapes; whether the routes
  are guarded now or left open for the auth epic to wrap is an architecture decision, but no
  login/JWT/role logic is built here.
- **Failure reason (C10)** on scan detail — separate ask.
- Search, sort, and pagination **behaviour** beyond what the endpoints need to return the
  correct rows and the contract's envelope shape (no new query features invented).
- **The scanner's scanning / normalization / scoring logic.** The Pi's discovery, enrichment and
  scoring are untouched. This feature **does** rename the Pi's ingest *contract layer* field names
  `devices` → `hosts` (`DevicePayload` → `HostPayload`) per [`ADR-013`](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md),
  but that is a serialization-name change only — the Pi already thinks in `HostInfo` internally and
  produces the same data.
- **Scan-lifecycle logic** beyond persisting `status = completed`. The `pending`/`processing`/
  `failed` transitions belong to the command-channel work, not here.
- New endpoints beyond the four named (`/hosts`, `/hosts/{host_id}`, `/scans/{scan_id}`,
  `/findings`). Note: this feature **does** correct the ingest *schema* — vocabulary
  `target_mode`/`scan_profile` → `scan_mode` (+ `status`), and `devices` → `hosts` end to end
  (ADR-013) — but it adds no new ingest endpoint and no new upload field the scanner must produce.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Contract (authoritative shapes): `contracts/openapi/openapi.yaml`
- Execution ledger: `POOP.md` (written during orchestration)
