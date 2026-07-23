# ADR-013: Ingest vocabulary unification — "device" retired, "host" end-to-end

> **Status:** Accepted (2026-07-22). **Supersedes [`ADR-011`](ADR-011-pi-command-channel.md) §5–§6**
> ingest-naming freeze: the clause that kept the `POST /api/v1/scans` payload field names as
> `devices` (while the read side had already been renamed to `hosts`) is lifted. See
> [`CONTEXT.md`](../../CONTEXT.md) for the domain glossary this ADR updates.

## Context

[`ADR-011`](ADR-011-pi-command-channel.md) renamed the host inventory read path from `/devices` to
`/hosts` (§6), but deliberately left the **ingest** payload alone: "empty `hosts` / `findings` arrays
(ingest payload field names unchanged in `POST /scans`)" (§5). That was a scope-limiting choice made
at the time to keep the WebSocket command-channel change small — not a principled decision that the
wire vocabulary should permanently differ from the domain vocabulary.

The result is a permanent two-vocabulary split: the Pi reports `devices[]` / `DevicePayload` /
`devices_received` on ingest, while everything else — read models, paths, filters, the UI, the domain
glossary in [`CONTEXT.md`](../../CONTEXT.md) — speaks **host**. `CONTEXT.md` records "Device" as
"deprecated, ingest-only" and pins its survival to "frozen by ADR-011 §5". This ADR removes that
exception.

Three things make now the right time:

1. **No live producer or consumer to break.** `backend/src/api/main.py` mounts only
   `GET /api/v1/health` — the ingest route (`POST /api/v1/scans`) is not yet implemented, so there is
   no deployed backend contract to violate. No Raspberry Pi is known to be deployed against this
   backend. A rename that would be a coordinated OTA + migration once Pis are in the field is, right
   now, an edit to code that has never run in production.
2. **The Pi already thinks in hosts.** `hardware-agent/src/agent/normalize/network_discovery.py`
   builds `HostInfo` internally. Only the wire contract layer,
   `hardware-agent/src/agent/normalize/contracts.py` (`ScanPayload.devices: list[DevicePayload]`),
   serializes that internal model back down to "device". This is a rename of one serialization
   boundary, not a change to the Pi's scanning or normalization logic.
3. **Not blocked by HMAC.** [`ADR-005`](ADR-005-security-model.md)'s v1 canonical string is
   `METHOD / PATH / X-Device-Id / X-Timestamp / X-Nonce / X-Body-SHA256` — header **names**, not body
   field names, and not header values. `X-Body-SHA256` is a hash of the raw body, so a renamed field
   inside that body re-verifies exactly the same way after a coordinated client+server deploy. The
   ingest naming change does not touch the signature scheme.

## Decision

Unify the ingest vocabulary to **host**, end to end:

- `POST /api/v1/scans` request body: `ScanIngestRequest.devices` → `hosts`.
- OpenAPI schema `DevicePayload` → `HostPayload` (same shape: `ip`, `mac`, `hostname`, `vendor`,
  `ports[]`).
- `ScanIngestAcceptedResponse.devices_received` → `hosts_received`.
- Pi contract layer: `hardware-agent/src/agent/normalize/contracts.py` — `ScanPayload.devices` →
  `ScanPayload.hosts`, `DevicePayload` → `HostPayload`.
- "Device" is retired from the wire entirely. The scanner (Pi) and backend now speak one vocabulary
  across both the ingest and read paths.

**`X-Device-Id` is explicitly out of scope and unaffected.** It identifies the *agent* (the Pi
itself), not a discovered host, and is frozen by ADR-005 as an HMAC-signed header name. Do not rename
it, and do not read this ADR as license to touch it — the two are unrelated identifiers that happen to
share a word by historical accident (see `CONTEXT.md`'s note on why "device" used to mean both the Pi
and the machines it found).

This ADR does not change transport, auth, or lifecycle — only the field/schema names inside the
existing `POST /api/v1/scans` ingest payload and its accepted-response.

## Consequences

- **`contracts/openapi/openapi.yaml`**: `ScanIngestRequest.devices` → `hosts`; schema `DevicePayload`
  → `HostPayload`; `ScanIngestAcceptedResponse.devices_received` → `hosts_received`. (The read side,
  `ScanDetailResponse.hosts`, is already named correctly and is unaffected.)
- **`hardware-agent/src/agent/normalize/contracts.py`**: rename `ScanPayload.devices` →
  `ScanPayload.hosts` and `DevicePayload` → `HostPayload`. No change to
  `network_discovery.py`/`HostInfo` — they already speak host. **Note: the rename's blast radius
  is wider than this one file** — `scanner/stages.py`, `scanner/runner.py`, and three TUI screens
  (`tui/screens/scan_view.py`, `scan_progress.py`, `home.py`) read the renamed field by name, and
  ~nine Pi test files reference it; see `specs/015-read-path/ARCHITECTURE.md` §"Rename blast
  radius" for the full call-site list. Still a mechanical rename (no scanning-logic change), just
  not confined to `contracts.py`.
- **Backend**: once the ingest route lands, its request model and persistence mapping must consume
  `hosts`/`HostPayload`, not `devices`/`DevicePayload`. There is no existing backend ingest code to
  migrate today, only a future implementation to get right the first time.
- **Storage naming stays layered, not literal**: the durable, cross-scan machine record remains
  **Host** (`host_id`-keyed, as in `CONTEXT.md`). The per-scan observation that a given ingest
  produces is a separate concept from the durable Host and is expected to be modeled as its own
  entity (proposed name: **ScanHost**) when that persistence design is done. This ADR unifies the
  *wire* vocabulary; it does not mean the per-scan row is literally named `host` in the data model.
- **`CONTEXT.md`**: the "Device — deprecated, ingest-only" glossary entry needs to be retired (its
  survival was pinned to "frozen by ADR-011 §5", which this ADR supersedes). Not edited by this
  change — tracked as a required follow-up, being made in a parallel session.
- **Risk / sequencing**: this must land before any real Pi is provisioned against this backend. Once
  Raspberry Pis are deployed in the field, the same rename becomes a coordinated OTA + backend
  migration instead of a docs-and-code edit with no live traffic — do this now, not later.

## Out of scope

- Any change to transport, HMAC scheme, or the `POST /api/v1/scans` canonical string (ADR-005
  unchanged).
- `X-Device-Id` (agent identity header) — stays exactly as named.
- The command-channel WebSocket envelope (`command`/`status`/`hello` frames) — untouched, no "device"
  wording there to begin with.
- Implementing the backend ingest route itself (still not built) — this ADR only fixes the vocabulary
  it must use when it is.

## References

- [`ADR-011`](ADR-011-pi-command-channel.md) — §5 (stub scan) and §6 (HTTP surface), whose
  ingest-naming freeze this ADR supersedes.
- [`ADR-005`](ADR-005-security-model.md) — HMAC canonical string (header names only; unaffected by
  this rename).
- [`CONTEXT.md`](../../CONTEXT.md) — domain glossary; "Device" entry to be retired as a follow-up.
- [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) — `ScanIngestRequest`,
  `DevicePayload`, `ScanIngestAcceptedResponse`.
- `hardware-agent/src/agent/normalize/contracts.py` — `ScanPayload`, `DevicePayload`.
