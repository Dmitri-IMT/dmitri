# TRUTH — Scan ingest endpoint (DMI-63)

Domain language and verifiable behaviour only. No file paths, no code, no SQL. The request and
response shapes are already frozen in `contracts/openapi/openapi.yaml`; `ARCHITECTURE.md` turns
this behaviour into paths, dependencies and queries.

## Narrative

An operator can ask for a scan and the scanning device can hear about it. The device can scan.
What it cannot do is **hand the results back**.

Everything on either side of that gap exists. The command channel delivers a scan request to a
device and creates a placeholder for the scan it will produce. The device reports its progress
back over the same channel. The engine that turns raw scan output into stored machines, ports,
services and findings — and that queues the enrichment work which decorates those findings with
severity and exploit intelligence — has existed since before the hosted product did. The read
surface can already answer questions about scans, machines and findings. The published API
contract even specifies the submission endpoint in full: its address, its payload, its signed
request envelope, and every way it can be refused.

The endpoint itself was never built. The results engine has no caller other than its own tests.
The consequence is that the contract advertises a documented, security-specified operation that
does not exist, and every scan a device performs is discarded. This feature builds that
endpoint and reworks the results engine to fit the world it now lives in — one with
organisations, registered devices, and operator-issued scan requests — instead of the
single-tenant world it was written for.

Two things make this more than plumbing. First, a scan is no longer necessarily new: when an
operator asked for it, a placeholder already exists and the results must **fill** it rather than
create a rival record. Second, the results engine writes to the store in several instalments, so
a failure partway through can currently leave a half-written scan behind. Both are corrected
here.

The work is deliberately narrow. The results engine's domain logic — how findings are deduped
and merged, how machines are recognised across scans, how enrichment work is queued — is
correct and is not touched. No shape is invented: where the contract speaks, it decides, and
where the payload is concerned it speaks completely.

## Business rules

### Who may submit

- **Only a registered device may submit results, and it must prove it.** A submission carries a
  signature the product verifies against the public key recorded for that device at
  registration. There is no shared secret and no password on this path.
- **An unproven submission changes nothing.** A missing, malformed, wrongly-signed, stale,
  or replayed request is refused as unauthenticated and leaves the store exactly as it was —
  no scan, no machines, no findings, no enrichment work.
- **A device whose registration was revoked is refused**, even when its signature is
  impeccable, and is told it is forbidden rather than unrecognised.
- **A device never says which organisation it belongs to.** The organisation is taken from the
  device's own registration, and every record the submission creates belongs to it. A device
  cannot claim, imply, or be tricked into writing for another organisation.

### What a submission means

- **A scan requested by an operator is filled, not duplicated.** When the results name the scan
  the operator's request created, that existing scan becomes the real one. Exactly one scan
  record exists for one request, before and after.
- **A device may only fill a scan that was issued to it.** Results naming a scan belonging to
  another device — or to another organisation — are refused, and nothing is written.
- **A device may also submit results nobody asked for.** A scan the device started on its own
  has no prior request and no placeholder; it is recorded in full, belongs to the submitting
  device's organisation, and is complete on arrival.
- **Results are the completion signal.** Successfully recorded results complete the scan and,
  where one exists, the operator's request — regardless of what the device does or does not
  say afterwards over the command channel. A device that uploads successfully and then
  vanishes has still succeeded.
- **Completion is never walked backwards.** A progress report arriving after the results are
  in cannot return a completed scan to an earlier state, and does not fail — it is simply
  without effect.
- **A request the product gave up on stays given up on.** Once a request has finished
  unsuccessfully — because its device dropped off the network and could not get back for long
  enough to be written off — results arriving afterwards are refused and nothing is stored. A
  device that was unreachable that long is not trusted to be reporting on the run the operator
  is still waiting for, and the operator has already been freed to ask again. The refusal is
  explicit: the device is told its results were not accepted, never told they were.
- **A device's proof of identity is single-use.** Each submission proves itself afresh; the
  proof attached to one submission can never be attached to a second. So a device that needs to
  send the same results again does not re-send the same request — it makes a new one.
- **A scan's results are recorded once.** A device that submits the same results a second time,
  as a new and separately-proven submission, neither duplicates its machines and findings nor
  corrupts what was stored, and is not told it failed. This is not in tension with a replayed
  request being refused: a *replay* is the same proof used twice, and is refused as
  unauthenticated; a *repeat* is the same results proven twice, and is accepted.

### What is stored

- **All of it, or none of it.** A submission that fails partway through leaves no trace: no
  scan, no partially-populated machine list, no orphaned findings, no enrichment work. A
  reader can never observe a half-written scan.
- **A machine observed in a scan resolves to the durable machine it is**, by the existing
  identity rules, so a machine seen in successive scans keeps one identity and one first-seen
  date.
- **Recording results queues the enrichment work they imply**, exactly as the engine does
  today — every enrichable service and every named vulnerability gets its follow-up job.
- **The stored vocabulary is `hosts` throughout.** "Device" means the scanning appliance and
  never a machine on the scanned network.

### What may be submitted

- **The published contract defines the payload completely.** A submission is accepted only if
  it matches: the required facts about the scan, the machines found, and the findings raised.
  Nothing beyond the contract is accepted, and an unrecognised field is a rejection rather
  than something quietly ignored — **at every depth**, not only at the top of the payload. An
  unknown field on a machine or on a finding is refused exactly as an unknown field on the
  scan is.
- **A required fact is required wherever it sits.** The contract marks the machine list and
  the finding list as facts a submission must state — an empty list is a statement, an absent
  list is not. The same holds for the facts required of each machine.
- **The contract was found incomplete in one place, and corrected.** A machine's open port
  carries the software identifiers the scan detected for it, which is what the product turns
  into vulnerability lookups. The published contract omitted them while forbidding anything it
  did not name, which would have made a whole class of enrichment permanently unreachable —
  not a decision, an oversight from before the ingest path existed. The contract is corrected
  to name them, once, and nothing else about the payload is invented. Decided 2026-08-04.
- **Machines and findings are identified by IPv4 addresses.** An IPv6 address is an invalid
  payload and is refused at submission, not accepted and discovered later when a reader cannot
  render it.
- **A refusal for shape is distinguishable from a refusal for identity.** A caller can tell an
  unacceptable payload from an unaccepted signature.

### Artifacts

- **Scan artifacts are not part of this product.** No scanning device produces them, no reader
  consumes them, and the contract does not define them. The concept, its storage, and its
  remaining traces are removed rather than carried forward as an unused option.

## User stories

1. As a scanning device, I want to hand back the results of the scan I was asked to perform, so
   that the work I did becomes visible to the operator who asked for it.
2. As a scanning device, I want my upload alone to mark the job done, so that a dropped
   connection afterwards does not turn a successful scan into a reported failure.
3. As an operator, I want the scan I requested to become the scan I read, so that the request I
   watched and the results I open are the same thing.
4. As an organisation, I want certainty that another organisation's device cannot write into my
   data, and that mine cannot write into theirs.
5. As an operator, I want a failed upload to leave nothing behind, so that I never read a scan
   that is quietly missing half its machines.
6. As the enrichment engine, I want the work implied by newly recorded results to be queued as
   before, so that severity and exploit intelligence keep arriving.
7. As the maintainer of the published contract, I want the advertised submission endpoint to
   exist and to match what is documented, so that the contract stops describing a fiction.

## Acceptance criteria (verifiable)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| 1 | Filling a requested scan | An operator's scan request delivered to a device, with its placeholder scan | The device submits results naming that scan | That scan holds the results, belongs to the request's organisation, is linked to the submitting device and to the request, and exactly one scan exists for the request |
| 2 | The request completes | A delivered scan request awaiting results | Its results are submitted successfully | The request and the scan both read as complete |
| 3 | Late progress report | A scan already completed by its results | The device afterwards reports progress over the command channel | The report is accepted without error and the scan stays complete |
| 4 | Unrequested scan | A registered device with no outstanding request | It submits results for a scan nobody asked for | The scan is recorded in full, belongs to the device's organisation, is linked to the device, is linked to no request, and reads as complete |
| 5 | Machines and findings recorded | A submission describing several machines with open ports, services and findings | It is accepted | Every machine, port, service and finding is readable afterwards through the existing read surface |
| 6 | Enrichment queued | A submission whose services and findings imply enrichment work | It is accepted | The same follow-up work the engine has always queued is queued — including the lookups driven by a port's detected software identifiers, not only those driven by named vulnerabilities |
| 7 | Durable machine identity | A machine already known from an earlier scan | A new submission observes it again | It resolves to the same durable machine, and its first-seen date does not move |
| 8 | Wrong key | A submission signed with a key that is not the device's | It is submitted | It is refused as unauthenticated and nothing whatsoever is stored |
| 9 | Missing or malformed signature | A submission with absent or unparseable signature information | It is submitted | It is refused as unauthenticated and nothing is stored |
| 10 | Stale or replayed submission | A submission whose timestamp is outside the accepted window, or that reuses a previous request's one-time value | It is submitted | It is refused as unauthenticated and nothing is stored |
| 11 | Revoked device | A device whose registration was revoked | It submits a perfectly signed payload | It is refused as forbidden — distinguishably from an unrecognised device — and nothing is stored |
| 12 | Another device's scan | A placeholder scan issued to one device | A different registered device submits results naming it | The submission is refused, the placeholder is untouched, and nothing is stored |
| 13 | Cross-organisation isolation | Two organisations, each with a device and scans | Either device submits | Every record it creates belongs to its own organisation, and no record of the other organisation is created, altered or revealed |
| 14 | All-or-nothing | A submission that fails partway through being stored | The failure occurs | No scan, machine, finding or enrichment job from that submission survives; a requested scan's placeholder is left as it was |
| 15 | Repeated submission | A scan whose results were already recorded | The same results are submitted again as a new, separately-proven submission | The device is not told it failed, and the stored machines and findings are neither duplicated nor corrupted |
| 15a | Repeat is not replay | A scan whose results were already recorded | The device re-sends its *first* submission unchanged, proof and all | It is refused as unauthenticated (criterion 10), not accepted — the two are distinguishable and both hold |
| 16 | Unknown field | A payload carrying a field the contract does not define, at the top level, on a machine, on a port, or on a finding | It is submitted | Each one is refused as an invalid payload |
| 17 | Missing required fact | A payload lacking something the contract requires — including an absent (not merely empty) machine list or finding list, or a machine missing a required fact of its own | It is submitted | Each one is refused as an invalid payload |
| 18 | IPv6 machine | A payload describing a machine by an IPv6 address | It is submitted | It is refused as an invalid payload — not accepted and not stored |
| 19 | IPv6 finding | A payload raising a finding against an IPv6 address | It is submitted | It is refused as an invalid payload |
| 20 | Acknowledgement | Any accepted submission | It succeeds | The device is told the scan was accepted, which scan it was, and how many machines were received, in the shape the contract declares |
| 21 | Shape before identity is not leaked | An unsigned submission whose payload is well-formed but does not match the contract | It is submitted | It is refused for identity — an unproven caller learns nothing about payload validity |
| 22 | Contract fidelity | The implemented endpoint | Its published schema and address are compared to the contract, at every depth of the payload | They match — no field added, renamed or missing, on the scan, on a machine, on a port or on a finding |
| 22a | The correction is confined to ingest | The one contract correction this feature makes | The read surface's published schemas are compared before and after | They are unchanged — no read response gains, loses or renames a field |
| 23 | The endpoint exists | The frozen contract | Every operation it declares for scans is looked for in the running product | Each one is present, including this submission endpoint |
| 24 | Artifacts are gone | The product after this feature | The concept of a scan artifact is looked for in payloads, storage and the contract | It exists nowhere, and the removal is a reversible upgrade that leaves all other recorded data untouched |
| 25 | Existing data survives | An existing store with scans, machines and findings already recorded | The upgrade is applied | It succeeds, is reversible, and every existing scan reads exactly as before |
| 26 | Quality gates | The feature's branch | The backend test suite and linter run against a live test database | Both pass on the touched scope, with no skipped database tests |
| 27 | Late results after a write-off | A request already given up on because its device dropped off the network | The device's results arrive afterwards | They are refused, nothing is stored, the request and scan keep the outcome they already had, and the device is told plainly that its results were not accepted — never told they were |
| 28 | Malformed body | A well-signed submission whose body is not valid JSON at all | It is submitted | It is refused as an invalid payload, and nothing is stored |

## Out of scope (v1)

- **Any change to enrichment or scoring.** How findings are deduped, merged, confidence-rated
  and scored, and how enrichment jobs are processed, is kept exactly as it is.
- **Any new read or query surface.** This feature writes; the existing read endpoints are not
  extended, and no endpoint is added beyond the one the contract already declares.
- **Any payload invention.** The contract is the source of truth for what a device may send. It
  proved insufficient in exactly one place — a port's detected software identifiers — and that
  was raised and decided rather than patched silently (see *What may be submitted*). No second
  gap is filled by fiat: another one is raised the same way, not invented.
- **Any new read or query surface, including from that correction.** The corrected field is
  accepted and stored; it is not returned by any read response. The read surface's shapes are
  identical before and after (criterion 22a).
- **The device-side client.** Signing and submitting from the scanning appliance is owned by
  DMI-65; this feature is the receiving half and is verified with its own signed requests. Two
  things DMI-65 inherits from decisions made here, and should not have to rediscover: the device
  must be able to *re-prove* a submission rather than re-send one, and it must learn to send the
  software identifiers it already detects, which it currently discards before sending.
- **Command channel behaviour** — delivery, progress reporting, disconnection sweeps, and the
  transition rules themselves. This feature *uses* the existing completion transition; it does
  not redefine it, adds no new state, and adds no new transition. A request that has already
  finished cannot be moved by anything this feature does (criterion 27).
- **Reviving a written-off request.** Considered and rejected on 2026-08-04: being written off
  requires a device to have been unreachable for a sustained period, which is a real fault, and
  the operator is free to scan again. Should late results later prove worth keeping, that is a
  product decision to revisit deliberately — not something this feature slips in.
- **Two submissions of one scan arriving at the same instant.** Recording the same results once
  (criterion 15) is about a device submitting again *after* the first submission settled, which is
  the only repeat a real device produces. Two genuinely simultaneous submissions of one scan are
  refused by the store's own uniqueness rules and reported as an internal failure; the device is
  free to submit again and lands on the ordinary repeat path. Nothing is duplicated or corrupted
  either way — only the refusal is less graceful than it could be. Decided 2026-08-04.
- **A readable reason for a failed scan.** Owned by DMI-75.
- **Device registration, key rotation and provisioning.** A device and its public key already
  exist by the time it submits.
- **A payload size ceiling.** The contract declares a refusal for an over-large submission; no
  limit is configured or enforced here beyond whatever the hosting platform already imposes.
- **Any frontend work.** No screen changes; the existing read screens display the results as
  they already do. The one contract correction obliges a mechanical regeneration of the
  frontend's published types — that is bookkeeping, not screen work, and nothing a user sees
  changes.
- **Performance work** beyond not being gratuitously wasteful — no batching layer, no
  streaming ingest, no new indexes unless a criterion above cannot otherwise be met.
- **Broader dead-code cleanup.** Only the artifact concept is removed. Other unused code found
  along the way is mentioned, not deleted (DMI-64 owns that pass).

## Dependencies

| Depends on | State |
|---|---|
| Command channel data model and lifecycle transitions (DMI-59) | ✅ Done |
| Device signature verification and the reusable auth dependencies (DMI-61) | ✅ Done |
| Command enqueue, delivery and the placeholder scan (DMI-22) | ✅ Done |
| Read path, durable machine identity, IPv4 narrowing (DMI-74, DMI-85) | ✅ Done |

No blockers. **DMI-65 — the device's submitting client — is blocked until this lands.**

## Scope note

DMI-63 as written fences out everything but the endpoint and the results-engine rework. The
artifact removal (criterion 24) is an addition the operator approved on 2026-08-04 after it was
established that no scanning device produces artifacts and no reader consumes them, making the
contract's silence on them a decision rather than a gap.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Contract (authoritative shapes): `contracts/openapi/openapi.yaml`
- Product brief: Linear DMI-63
- The consumer this unblocks: Linear DMI-65

No `DESIGN.md`: this feature has no user-facing screen.

## Docs drift (from `docs-sync`, 2026-08-05)

Applied automatically:

- `.claude/docs/` — `backend/schemas.md`, `backend/routers.md`, `backend/services.md`,
  `backend/models.md`, `backend/migrations.md`, `backend/api.md`, `backend/overview.md`,
  `backend/index.md`, `contracts.md`, `log.md`.
- `docs/architecture/ARCHITECTURE.md:215` — the Pi→Backend interface said
  `POST /api/v1/scans` was *"definido no contrato OpenAPI; ainda **não implementado** no backend —
  ver ADR-013 e DMI-63"*. Patched to record it as implemented in DMI-63, with the device-side upload
  still pending in DMI-66. Unambiguous factual drift: the note named this very issue as its tracker.

**Needs a human call — not edited:**

1. **`.claude/docs/MAINTAINING.md` "standing facts" are now stale.** Two of the four facts the
   playbook forbids agents from "fixing" have been invalidated by this feature:
   - *"ingest (`POST /api/v1/scans`) is contract-defined only"* — no longer true; the route is
     mounted and gated. Every doc that repeated this caveat has been corrected, so the playbook now
     contradicts the bundle it governs and will push the next agent to reintroduce the error.
   - *"Contract divergence: OpenAPI `ScanIngestRequest` (`scan_mode`) is out of step with the
     implemented `schemas/scan.py` + example JSON (`target_mode`/`scan_profile`)"* — this was
     **already** stale before DMI-63 (`contracts.md` has carried a "Resolved divergence" section for
     some time) and is doubly so now that the Python classes use the contract's own component names.

   Left untouched because the skill explicitly protects these entries. Recommend rewriting both.

2. **`docs/adr/ADR-013:25`** states *"the ingest route (`POST /api/v1/scans`) is not yet
   implemented"*. Now false, but it is context inside an accepted decision record — ADRs are
   append-only history, so this likely wants a dated amendment rather than an edit.

3. **`docs/roadmap/BACKEND.md`** — not touched. It arrived at this feature with **uncommitted,
   unrelated edits** (DMI-52/55/60/61/64/66/67/77), so no roadmap change here is safely separable
   from work in progress. Line 243 still lists ingest as unchecked
   (`- [ ] Pi daemon + Pi → backend ingest … DMI-66, DMI-65, DMI-63`) and line 328 still says the
   enrichment pipeline *"is not wired"*. The backend half of DMI-63 is done; the Pi half is not.
   Recommend a `roadmap-sync` pass once those in-flight edits are committed.
