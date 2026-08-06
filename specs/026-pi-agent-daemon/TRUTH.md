# TRUTH — Pi agent daemon command execution

## Narrative

The remote-control product needs an unattended device process that remains reachable from the
backend, accepts scan work, executes the established headless scan flow, and returns both progress
and results. Operators benefit because they can trigger and observe a scan without anyone being
present at the device. This closes the device half of the command channel needed for the first
end-to-end Control demonstration.

## Business rules

- The device initiates and maintains the command-channel connection; the backend never opens an
  inbound connection to the device.
- The device authenticates as itself using its asymmetric private key. A shared device secret is
  not accepted.
- A dropped command-channel connection is retried automatically so the device can become available
  again without operator intervention.
- A temporary authentication rejection is retried with a fresh proof after backoff so startup clock
  synchronization can recover without intervention.
- A permanent revocation signal, whether received while connecting, while connected, or during
  result upload, parks the daemon and prevents further reconnects or command acceptance. A
  connection replaced by another daemon instance follows the same no-reconnect rule; operator
  action is required to avoid an eviction loop.
- The daemon confirms the installed scanner executable is discoverable before appearing online. If
  it later becomes unavailable, the affected command fails through the normal scan-failure path.
- On every connection and reconnection, the device reports each usable IPv4 interface and subnet it
  can currently reach, including the interface name and whether it holds the default route.
- Reported networks describe current device state only. The device does not choose, guess, default,
  or persist which subnet should be scanned; that selection belongs to the backend and operator.
- Only valid scan commands are eligible for execution. Each command identifies the work and the
  backend-owned scan record, scan mode, and target subnet.
- A command identifier is idempotent: receiving the same command more than once acknowledges its
  known state and never starts another scan.
- The device executes at most one scan at a time. A different command received while the active
  command is running or uploading is rejected as busy and is not queued locally.
- An accepted command emits progress in order: running, then uploading, then exactly one terminal
  outcome of done or failed. Because delivery persistence can race the first status, the backend may
  omit the early running state from its stored history without changing the command's outcome.
- Results are uploaded through the existing ingest channel and are associated with the scan
  identifier supplied by the command.
- A command is done only after its results have been accepted by ingest.
- A scan failure, unavailable persisted result, rejected final upload, or other unrecoverable command
  error produces a failed terminal outcome and never a false done outcome.
- A scan that preserves usable partial results follows the upload lifecycle. If ingest accepts those
  results, the command is done and the result remains identifiable as partial.
- A terminally rejected late result is final and is not retried or queued for later delivery.
- Terminating the daemon does not preserve, resume, or locally queue active work. If no terminal
  status was delivered, the backend's disconnect policy eventually marks that command failed.
- The command channel carries lifecycle messages only; scan result payloads use the ingest channel.

## User stories

1. As an operator, I want an online device to execute a remotely issued scan, so that I can assess a
   network without being physically present.
2. As an operator, I want command progress and terminal status to reflect the device's real work, so
   that I can trust what the product reports.
3. As a platform operator, I want duplicate and concurrent command delivery handled safely, so that
   retries or races cannot launch unintended scans.
4. As a device installer, I want the daemon to reconnect after a channel interruption, so that normal
   connectivity changes do not require manual recovery.
5. As an operator, I want the device to report its reachable networks and identify its internet
   connection, so that I can choose the intended scan target without entering a CIDR.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Authenticated connection | A configured device has a registered identity and matching private key | The daemon connects to the command channel | The backend accepts the device connection and the daemon waits for commands |
| Reconnect after drop | An authenticated daemon has lost its command-channel connection | Connectivity becomes available again | The daemon reconnects automatically and resumes waiting without operator action |
| Recover after clock synchronization | A configured device is temporarily rejected because its clock is outside the accepted window | The clock becomes synchronized while the daemon is backing off | A fresh authentication proof is accepted and the daemon resumes normal connection behavior |
| Revoked identity at connection | A device identity has been revoked | The daemon's connection is permanently rejected | The daemon stays down without repeatedly reconnecting |
| Revoked identity while active | A connected device is revoked | The daemon receives the backend's documented permanent-revocation close or a forbidden result-upload response | The active command cannot report done, the daemon parks, accepts no more commands, and does not reconnect without operator action |
| Replaced connection | Another daemon connection for the same device identity takes ownership | The backend closes the older connection as replaced | The older daemon stays down and does not evict the replacement |
| Scanner missing at startup | The device installation cannot locate its scanner executable | The daemon starts | The daemon exits as a fatal startup failure before appearing online |
| Scanner disappears at runtime | The daemon connected successfully but the scanner executable is no longer available | A valid command starts | The command reports a scan failure and never reports uploading or done |
| Process termination during work | A command is running or uploading | The daemon process is terminated | The work is not resumed or queued locally, and the backend eventually records failure through its disconnect policy if no terminal status was received |
| Dual-homed network report | A device has target-network ethernet and internet-connected Wi-Fi interfaces | The daemon establishes its command-channel connection | Both subnets are reported before lifecycle status, and exactly one is identified as holding the default route |
| Network report refresh | A connected device's usable interfaces change before reconnection | The daemon reconnects | The newly reported list replaces the prior list and reflects the current interfaces |
| Single-homed network report | A device has one usable IPv4 interface | The daemon connects | That interface and subnet are reported without automatically selecting it as the scan target |
| Unknown default route | Usable IPv4 interfaces are available but the operating system does not identify a default-route interface | The daemon connects | Every usable subnet is reported with no default-route designation, the device remains online, and no target is guessed |
| No automatic target | One or more networks have been reported but the backend has no selected target | The device is online | No network is selected or persisted by the device, and no scan starts without a command naming a subnet |
| Execute a command | An authenticated idle daemon receives a valid command | The command is accepted | Exactly one headless scan starts with the requested mode and subnet, and the work is associated with the command's scan identifier |
| Successful lifecycle | An accepted command's scan succeeds and its result is available | The daemon uploads the result and ingest accepts it | The daemon emits running, uploading, and done in that order; the backend reaches done with the result under the supplied scan identifier even if it discarded an early running frame |
| Scan failure | An accepted command cannot complete its scan | The failure becomes unrecoverable | The daemon emits running followed by failed; the backend reaches failed with a stable error classification and receives neither uploading nor done after failure, even if it discarded the early running frame |
| Partial result | An accepted command preserves a valid partial result | Ingest accepts that result | The daemon emits running, uploading, and done; the backend reaches done, stores the available result, and identifies it as partial |
| Missing persisted result | The scan work finishes but no uploadable result was persisted | The daemon handles the command outcome | The backend observes failed and no upload attempt or done status occurs |
| Upload failure | A scan result is ready but ingest cannot accept it | The upload policy reaches an unrecoverable outcome | The daemon emits uploading followed by failed; the backend reaches failed and never reaches done |
| Closed scan rejection | Ingest reports that the scan is already terminal | The daemon receives the rejection | The result is not retried or queued, and the command reports failed unless it was already terminal |
| Duplicate active command | A command is already running or uploading | The same command identifier is delivered again | The daemon acknowledges the command's known state and does not start another scan |
| Duplicate completed command | A command has already reached a terminal outcome | The same command identifier is delivered again | The daemon acknowledges the recorded terminal outcome and does not start another scan or upload |
| Busy device | One command is running or uploading | A different command is delivered | The second command is rejected as busy, is not queued, and the active scan continues unchanged |
| Malformed or unsupported frame | The daemon is connected and idle or executing work | It receives a message that is not a valid supported command | No scan starts for that message, the active command remains unaffected, and the channel remains usable when safe |
| Command-channel payload boundary | A scan produces a result payload | The daemon reports progress and transfers results | Lifecycle messages travel over the command channel and the result payload travels only through ingest |

## Out of scope (v1)

- Service-manager packaging, installer steps, scheduled reboot policy, or hardware provisioning.
- Graceful mid-scan cancellation or resumption during daemon shutdown.
- Preempting an active scan, superseding an older command or daemon generation, fencing late work,
  or force-starting replacement work; tracked separately by DMI-101.
- TUI or web-interface changes.
- Queueing commands locally while disconnected or accepting offline work for later execution.
- An HTTP polling fallback, an external message broker, or multi-device scheduling.
- Credential generation, registration, rotation, or recovery workflows.
- Changes to the scan pipeline's discovery, inspection, normalization, or scan-mode behavior.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Cross-process contract: `INTEGRATION.md`
- Follow-up: DMI-101 — scan supersession and daemon replacement reconciliation

## Docs drift (docs-sync, 2026-08-06 — reported, not applied)

The `.claude/docs` code-map was updated in full. These `docs/` and root-script items need a human
call and were deliberately left alone:

1. **`docs/adr/ADR-011-pi-command-channel.md` §3** — the `hello` frame example still shows
   `{ "interface": …, "cidr": … }` without `is_default_route`, which is now **required** in
   OpenAPI, the backend model and the generated frontend type. A sender matching that example is
   rejected. ADRs are not auto-rewritten; run `architecture-adr-sync` or amend the ADR by hand.
2. **`docs/roadmap/BACKEND.md` C2, `docs/ui/FLOWS.md` C2, `docs/ui/SCREENS.md`** — all describe the
   WS half of C2 as carrying `interface` + `cidr`. Now three fields. `docs/roadmap/PI.md:66`
   already describes the default-route flag and needs no change. Belongs to `roadmap-sync`.
3. **`docs/roadmap/PI.md`** — DMI-66 is complete; its roadmap status was not advanced.
4. **`install.sh` / `install.ps1` next-steps** — bare `dmitri agent` is a new run command, but it
   needs `BACKEND_URL`, `DEVICE_ID` and `DEVICE_PRIVATE_KEY`, and there is no
   `hardware-agent/.env.example` for the installer to seed (DMI-65 established that scope and did
   not add one). Printing the command without seeding those would advertise something that exits
   `20`. Whether the installer should provision device credentials is a scope decision, not a
   doc fix. No script change was made; `uv sync` already installs the new `websockets` dependency,
   and no new system binary or gate was introduced.
