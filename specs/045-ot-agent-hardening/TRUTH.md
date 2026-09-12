# TRUTH — OT agent hardening

Domain language and verifiable behaviour only.

This spec is the single record of the work required to correct everything the audit found in the
active-scanning and operating-system work: the eight commits merged as PR #137, and the two
commits pushed directly to the main line on 2026-09-11. [`AUDIT.md`](AUDIT.md) is the evidence
behind every rule below, and states what is excluded.

## Narrative

Dmitri's agent now speaks an industrial protocol directly to the devices it scans. That inverts
the trust direction: the agent parses data supplied by a device which, on an assessment network,
may be hostile or simply broken. Today a single malformed response can crash the operator's
terminal interface, erase evidence the scan already gathered, or steer the scan toward a wider
set of addresses than the operator intended.

The active scanning work also shipped only half of itself. Industrial observations are collected,
sent to the cloud, accepted by the ingest contract — and then discarded, because the persistence
that gives them meaning was never built. Operators are told by the laboratory checklists to look
for results that cannot arrive.

Two safety promises are unkept. Identification probes ignore the pacing rule, and the wall-clock
limit on mapping cannot be reached in the shipped configuration.

The schema history has forked: two independent changes claim the same predecessor, so there is no
single current version to upgrade to and applying pending changes fails before any of them are
applied. Until that is repaired the database-backed part of the suite cannot run, so none of the
behaviour below can be verified. Worse, a missing database makes that suite report success while
testing almost nothing — which is how the fork reached the main line unnoticed.

Finally, a later change to the scan lifecycle reports a scan that finished as a scan that failed.

Every behaviour in this specification was reproduced or traced during the audit. None of it is
speculative.

## Business rules

### Untrusted device data

- Data supplied by a scanned device is untrusted, at every surface it reaches.
- A device response that cannot be parsed affects only that response. It never discards evidence
  already gathered for other units, ports or hosts.
- A device cannot make the operator's terminal interface fail by the content of its replies.
- Identification and product strings reported by a device are bounded in length and in number
  before they are stored or displayed.
- A parse failure is recorded, never silently swallowed.
- A device's reported text is classified by what it means, not by whether it contains a
  substring that resembles an error.
- A computed summary of absent data reports absence, never a value that implies data was present.
- A lookup of data the caller is expected to have provided fails visibly when it is missing,
  rather than depending on every caller to have prepared it.
- Validation of device data at the point of collection is at least as strict as validation of the
  same data when it reaches the cloud.

### Scope and consent

- A device's self-reported identity may select a more conservative scanning profile. It may never
  select a more aggressive one.
- A scanning profile broader than the conservative baseline applies only when the device matches
  on something it cannot cheaply forge: network address range or link-layer address.
- The component that performs a scan validates the scan depth it was asked for. A safety decision
  is not left to the caller.

### Bounds on active scanning

- Every OT active path observes a minimum delay between requests, a maximum request count,
  and a wall-clock ceiling. Port and deep inspection keep their existing Nmap and subprocess
  budgets. This feature does not add a reachable wall-clock default to those stages.
- A declared bound is in force in the shipped configuration. A bound that cannot be reached is
  not a bound.
- The agent does not accept inbound network connections.
- The absence of a write operation is demonstrated by the reachability of the code, not by the
  naming of its functions.
- Counters that report protocol activity report measured values.

### Industrial observations reach the product

- Industrial observations survive the whole lifecycle: local result, cloud ingestion, persisted
  inventory, and read interface describe the same observation.
- An industrial unit is an identifiable thing. A risk attributed to one unit is distinguishable
  from a risk attributed to another unit reached through the same port, because one port may front
  several devices with different firmware.
- Observation detail that is not read on its own — address ranges, identification extras — is
  stored with the unit it belongs to rather than as separately addressable records.
- Repeated ingestion of the same scan does not duplicate industrial observations.
- Industrial observations are readable only within the organisation that owns the scan.
- Raw process values are not persisted by default, and are never returned by the read interface.
  Aggregate statistics over those values are treated as process data and are likewise not
  returned.
- Change between scans is detectable without retaining the values. Any digest used for that
  purpose is keyed with an organisation-scoped secret, so it cannot be reversed by trying every
  possible value.
- Process values are never written to logs or to operator-facing output.
- Persisted industrial observation detail has a stated retention period.
- The published collection contract does not carry fields for behaviour that does not exist.

### Scan outcome

- A scan that runs to completion is recorded as completed, even when some hosts produced
  incomplete evidence. Partial evidence and failure are distinct outcomes and are reported
  distinctly.
- A record of where a scan stopped names a stage only when the scan actually stopped there.
- A host with open ports that reaches the end of a scan carries the service evidence the scan was
  able to gather, and the loss of one enrichment step does not silently erase evidence an earlier
  step already established.

### Stored records and schema history

- A stored record that a newer version of the software cannot interpret does not prevent unrelated
  records from being served.
- The schema history has exactly one current version.
- Applying all pending schema changes from any earlier state reaches that version without manual
  intervention, and can be reversed.
- A schema change that has already been released is never rewritten. A correction is expressed as
  a new change.
- A test run that cannot reach the database it needs fails. It never reports success. There is no
  way to suppress that failure.

## User stories

1. As an operator, I want a malformed or hostile device reply to leave my scan running and my
   terminal usable, so that one bad device does not end the assessment.
2. As an operator, I want the evidence already collected from a host to survive a failure later in
   that same host's scan, so that I do not lose work to a single bad unit.
3. As a security lead, I want a device to be unable to talk its way into a broader scan, so that
   the scope I authorised is the scope that runs.
4. As a plant engineer, I want every active probe to respect the declared pacing and time limits,
   so that scanning cannot disturb a fragile controller.
5. As a security lead, I want the read-only guarantee to be provable by a test that fails when a
   write becomes reachable, so that the guarantee survives future changes.
6. As an integrator, I want one unreadable stored record to not break a listing for the whole
   organisation, so that a single bad row is not an outage.
7. As an engineer, I want the pending schema changes to apply cleanly from any earlier state, so
   that deployment and the database-backed test suite both work.
8. As an engineer, I want a test run without a database to fail loudly, so that a green result
   always means the database-backed behaviour was actually exercised.
9. As an operator, I want a scan that finished with one unreachable host to be reported as
   finished, not as failed, so that I can tell a degraded scan from a broken one.
10. As an operator, I want the industrial evidence my scan collected to appear in the product, so
    that the laboratory checklists describe something that exists.
11. As a security analyst, I want a vulnerable firmware attributed to the specific unit running
    it, so that I can tell the engineer which device to go and look at.
12. As a customer, I want my plant's process values to stay in my plant, so that using Dmitri does
    not move my operational data into someone else's database.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Markup in identification | A device reports an identification string containing terminal markup characters | The operator opens the scan view for that host | The string is displayed literally and the screen does not fail |
| Oversized identification | A device reports an identification string longer than the permitted length, or more identification objects than permitted | The response is parsed | The value is truncated or rejected at the boundary, the unit is still recorded, and the limit applied is evident |
| Unparsable unit identifier | Device discovery output contains one unit identifier that cannot be read, alongside valid ones | The output is parsed | The valid units are retained and the unreadable entry is recorded as a parse failure |
| Malformed response mid-host | A host has several responding units and one returns a reply that cannot be decoded | The host inventory completes | Evidence for the other units is retained and only the failing unit is marked as failed |
| Error classification | A device reports a product name that merely contains a word resembling an error | The response is interpreted | The unit is not marked as failed on that basis |
| Absent data summarised | A range produced no readable values | Its summary is computed | The summary reports no value rather than a value implying data was read |
| Identity cannot widen scope | A device reports an identity matching a profile broader than the conservative baseline, and matches no address-range or link-layer selector | The mapping plan is resolved | The conservative baseline applies |
| Identity may narrow scope | A device reports an identity matching a profile narrower than the baseline | The mapping plan is resolved | The narrower profile applies |
| Corroborated profile | A device matches a broader profile on network address range or link-layer address | The mapping plan is resolved | The broader profile applies |
| Depth validated where it acts | A scan is started with a depth the product does not permit, through any entry point | The scan is prepared | It is refused before any active request is sent, and no result claims that depth was performed |
| Identification pacing | A host requires several identification probes | The host is inventoried | Consecutive probes are separated by at least the configured minimum delay |
| Wall-clock ceiling | A device answers every request slowly enough to exceed the stage's time ceiling | The stage runs | The stage stops at the ceiling, reports the reason, and retains the evidence gathered so far |
| Bounds are reachable | The software runs in its shipped default configuration | An active stage runs | Every declared bound — count, delay and time — is in force |
| No inbound listener | The agent is running in any mode | Its network state is inspected | It has no listening socket |
| Write reachability | A write operation is made reachable through any client the read-only session holds | The test suite runs | The suite fails |
| Write counter | Any active scan completes | The activity counters are read | The reported write count is the number of write requests actually sent |
| Observation survives the lifecycle | A scan finds an industrial service with identified units and probed address ranges | The scan is ingested and the host is read back | The read result describes the same service, units, identification and range statuses as the local result |
| Risk attributed to a unit | Two units behind one port report different firmware, one of which is vulnerable | The findings are read | The finding identifies which unit is affected |
| Idempotent ingestion | The same scan is ingested twice | The host is read back | The industrial observations appear once |
| Organisation isolation | Two organisations each have industrial observations | One organisation reads its hosts | It sees only its own observations |
| Process values withheld | A mapping scan captured values from a device | The observation is read through the interface | No raw value and no statistic derived from those values is returned |
| Change detection without retention | The same range is scanned twice with a different value each time | The two observations are compared | The change is detectable, and the stored digest cannot be reversed to either value without the organisation's secret |
| Values never logged | A mapping scan runs with value capture enabled | The logs and operator-facing output are inspected | No process value appears in them |
| Contract carries no unbuilt behaviour | The published collection contract is inspected | Its fields are compared with implemented behaviour | It carries no field for behaviour that does not exist |
| Completed with partial evidence | A scan reaches its end and one host produced no deep-evidence result | The result is recorded | The outcome is completed, the partial-evidence signal is set, and no stage is named as the stopping point |
| Genuine failure still reported | A scan stops because of an error, a timeout or operator cancellation | The result is recorded | The outcome names that cause and the stage where it stopped |
| Retention classifies correctly | A completed scan with partial evidence, and a failed scan | Stored runs are pruned | Only the failed run is treated as a failure |
| Service evidence survives one lost step | A host has open ports and its deep-evidence step returns nothing | The result is recorded | The host keeps the service evidence gathered earlier in the scan |
| Unreadable stored record | One stored host record cannot be interpreted by the current schema | The host list is requested | The remaining hosts are returned and the unreadable record is reported as unavailable rather than failing the request |
| Single current version | The schema history is inspected | The current version is requested | Exactly one version is reported |
| Upgrade from empty | An empty database | All pending schema changes are applied | Every change applies in order and the database reaches the current version |
| Upgrade from released state | A database at the last version released before this repair | All pending schema changes are applied | Every change applies and no already-applied change is reapplied or altered |
| Reversible | A database at the current version | The repair change is reversed | The database returns to a consistent earlier state |
| Database-backed suite runs | A live test database | The backend suite runs | The suite reaches its assertions instead of failing during setup |
| No database is a failure | No test database is reachable | The backend suite runs | The run fails, reports why, and cannot be made to pass without a database |

## Known items, deliberately not fixed here

Carried from the audit so they are not lost. Each needs evidence this feature does not produce.

- The partial-scan signal is inferred from the absence of scanner host elements, which does not
  reliably indicate a host timeout. Correcting it requires deciding what "partial" means, and that
  decision is broader than this feature.
- Two unreproduced suspicions: a per-host scanner timeout that may exceed its own subprocess
  budget under host-group parallelism, and an identification decoder whose bounds depend on the
  protocol's frame size rather than on an explicit limit. Both need real slow targets or a fuzzing
  harness.
- The collected observation volume has never been measured on the target hardware.

## Out of scope

- Implementing the write-validation depth, or any industrial write operation. Its safety decision
  governs that work and it is not started here. Its absence is the reason the unbuilt storage and
  contract fields are removed rather than filled in.
- The web interface for industrial observations. This feature makes the observations persist and
  be readable; presenting them belongs to the feature that owns that screen.
- Granting raw-socket capability during provisioning, and running the agent unprivileged. A
  deployment change, tracked with the provisioning work.
- Additional active tools authorised for this version.

## Docs drift

Documentation that this feature must correct, because it describes behaviour that is not true.
Re-scope against the current main line before starting — a later commit already repaired part of
the code map.

- The daemon code map states that the branch rejecting an unpermitted scan depth is unreachable.
  It is now the only thing rejecting a remotely requested write depth. Highest consequence.
- The migrations code map documents a single-version convention that the forked history breaks,
  and its version table omits both recent changes.
- The command-line reference denies that a scan-depth argument exists. The command-line accepts it.
- One laboratory checklist states that the write depth is disabled everywhere; in the web
  interface it is absent rather than disabled. Another names the wrong branch.
- The code map has no entry for the industrial protocol package, its pipeline stage, its new
  dependency, or the current agent version.
- The developer setup guide omits the policy file and its environment variable, and must state
  that the backend suite now requires a live database.
- The documentation index does not list the active-scanning safety decisions, the laboratory
  checklists, or the example policy.
- The roadmap still shows the port-stage task open, although it has been done.
- The project instructions warn that a bare backend test run prints a false green. Once a run
  without a database fails, that warning describes something that can no longer happen.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md` (terminal interface changes)
- Supersedes: `specs/042-nspi-modbus-ot` §7 (backend persistence and reads)
- Predecessors: `specs/042-nspi-modbus-ot`, `specs/043-operating-system-inventory`
- Decisions: [`ADR-019`](../../docs/adr/ADR-019-v2-active-scanning-and-agent-hardening.md),
  [`ADR-018`](../../docs/adr/ADR-018-nspi-active-modbus-safety.md),
  [`ADR-012`](../../docs/adr/ADR-012-headless-exit-code-contract.md),
  [`ADR-010`](../../docs/adr/ADR-010-scan-contingency-policy.md) §1 and §3 — the authority on
  partial versus stopped, and on not inventing terminal states
- Evidence: [`AUDIT.md`](AUDIT.md) — blockers 1-2 and findings 4-9, 11-17, 19. Blocker 3 is
  discharged by ADR-019 (Accepted 2026-09-12); findings 10 and 18 are recorded, not fixed here
