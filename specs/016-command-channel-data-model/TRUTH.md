# TRUTH — Command-channel data model + lifecycle state machine

## Narrative

Delivers the persistent core of the command channel (DMI-59, epic DMI-47, milestone MVP —
Control): the tables and the single lifecycle rulebook that let an operator's "Scan now" be
recorded, tracked, and audited from enqueue to terminal outcome. The backend commands a
Raspberry Pi **Agent** over an outbound WebSocket and receives results via HMAC-signed ingest;
those live paths (WS endpoint, ingest, enqueue/delivery, the Pi daemon) are **later** issues in
the epic. This issue lands only the schema they all build on plus the transition logic that
keeps command state honest.

Two domain objects are new — the **Agent** (the Pi appliance, identified by a UUID and
authenticated by a per-device HMAC-SHA256 secret) and the **Command** (one "Scan now", carrying
its own lifecycle and serving as the audit record). The **Scan** already exists; this issue only
relates a Command to its Scan. See `CONTEXT.md` (Agent, Command, Scan, Org), ADR-011 (command
channel + lifecycle), ADR-005 (agent auth), and ADR-015 (agent secret storage at rest).

## Business rules

- An **Agent** belongs to exactly one **Org**. It is identified by a UUID minted by the backend
  (the same value the Pi signs as `X-Device-Id`). Humans read its `display_name`, never its id.
- An Agent's HMAC secret is stored **encrypted and recoverable**, never one-way hashed (HMAC
  verification recomputes the MAC and needs the raw secret) and never in plaintext — AES-256-GCM,
  key held outside the database (ADR-015).
- **Revoking** an Agent is a soft, timestamped tombstone (`revoked_at`): history is kept and every
  future authentication is rejected. Revoking is distinct from **rotating** the secret, which
  re-issues the HMAC secret and leaves the Agent active.
- An Agent's **online** status is never stored — it is derived from the live WebSocket registry.
  A persisted `last_seen_at` heartbeat is informational (for the UI) and is never an auth input.
- A **Command** targets exactly one Agent, belongs to one Org, and produces **exactly one Scan**,
  born together at enqueue (the Scan as a `pending` stub). A re-scan is a *new* Command; idempotent
  re-delivery of the same command reuses the same Scan.
- A Command moves through the lifecycle `queued → delivered → running → uploading → done | failed |
  expired`. Its terminal state splits on whether the Pi ever took the job: **never took it**
  (delivery gave up before the first `running`) → `expired`; **took it, then broke** → `failed`.
- Command state transitions are enforced in **one place**. Illegal transitions are rejected; a
  transition to the state a Command is already in is a no-op success (absorbs duplicate agent
  frames, which ADR-011 says are expected).
- A **Scan**'s status is a **projection** of its Command's status, never set independently:
  `queued`/`delivered` → `pending`; `running` → `accepted`; `uploading` → `processing`; `done` →
  `completed`; `failed`/`expired` → `failed`.
- **Org** is the tenancy boundary: `org_id` scopes Agents, Commands and Scans, and is stored
  directly on each so tenant filtering needs no joins.

## User stories

1. As the backend, I record a "Scan now" as a Command with a linked stub Scan, so the UI can link
   to the result before any content exists.
2. As the backend, when a Command's state changes, I move it only along a legal path, so the audit
   record can never reach a contradictory state.
3. As an operator, I see a Scan's friendly status (pending/accepted/processing/completed/failed)
   that always agrees with its Command, because the Scan status is derived, not independently set.
4. As an administrator, I revoke a compromised Agent so all its future authentication is rejected
   while its history is retained.
5. As every later command-channel issue (WS endpoint, ingest, enqueue/delivery), I build on
   Agent/Command tables and one transition rulebook instead of inventing my own.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Migration round-trips | the migration for the new tables | it is run up then down | both succeed and the existing kept-engine queries still work against `hosts` |
| Terminal is a hard sink | a Command in `done` | a transition to `running` is attempted | the transition is rejected with a domain error naming current and target |
| Every legal edge allowed | a Command in each non-terminal state | each transition in the lifecycle table is attempted | every legal edge is accepted and every illegal edge is rejected |
| Duplicate frame absorbed | a Command in `delivered` | a transition to `delivered` is attempted | it is a no-op success, not an error |
| Received-but-not-started expires | a Command in `delivered` | delivery gives up (no `running` ever seen) | `expired` is a legal terminal; `failed` from `delivered` is rejected |
| Scan status tracks Command | a Command in each status | its Scan status is projected | the Scan status matches the fixed mapping and is never set on its own |
| Secret is not one-way | the Agent schema | it is inspected | the secret is stored in a recoverable encrypted form (not a one-way hash), with no plaintext secret column |
| Revoke is a tombstone | an Agent | it is revoked | a `revoked_at` timestamp is set, the row is kept, and revocation is separate from secret rotation |
| Tenancy is direct | an Agent, Command, or Scan | it is queried by tenant | `org_id` is present on the row so filtering needs no join |
| Quality gates | the touched scope | `uv run pytest` and `uv run ruff check` run | both pass |

## Out of scope (v1)

- No endpoints, no WebSocket code, no delivery/enqueue logic, no HMAC encrypt/decrypt or
  verification logic (later epic issues: DMI-62 WS endpoint, DMI-63 ingest, DMI-64 enqueue/
  delivery). This issue defines the encrypted-secret **columns** but writes no secret.
- No replay/nonce storage — deferred to DMI-62, which owns the first HMAC-verifying endpoint.
- No changes to the enrichment/scoring model (kept as-is).
- No `hosts` schema changes — the `devices`→`hosts` rename and `org_id` already landed in prior
  issues.
- No renaming of the surviving read-path `devices`/`PersistedDevice` vocabulary — that
  cleanup belongs with the read/`persist_scan` rework in DMI-63, not here.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Domain language: `CONTEXT.md`; decisions: ADR-011, ADR-005, ADR-015; research:
  `docs/research/hmac-device-secret-at-rest.md`
- Execution ledger: `POOP.md` (written during orchestration)
