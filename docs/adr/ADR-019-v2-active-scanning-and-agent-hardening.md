# ADR-019: V2 active scanning and agent hardening

> **Status:** Accepted (2026-09-12).
> **Supersedes:** ADR-002 §7 (v1 scope) and §8 first bullet, for V2 only.
> **Extends:** ADR-018 (NSPi Modbus submodes and active-scan safety boundary).

## Context

ADR-002 fixed v1 to "apenas Nmap + NSE + vulners NSE. Nenhuma ferramenta ativa
adicional", and required a new ADR for any tool addition. PR #137 shipped a
`pymodbus` dependency and an active Modbus client that opens its own TCP/502
sockets outside Nmap. The repository therefore contradicts its own accepted
decision, and ADR-018 did not supersede it.

V2 is the version where Dmitri begins authorised active assessment. The tool
list is the easy half of that decision. The half that matters is what protects
the plant being scanned and the Raspberry Pi doing the scanning.

Two properties of the agent were true by accident rather than by decision, and
this ADR makes them binding before further active work builds on them:

- **The agent has never listened on a port.** It reaches the backend over an
  outbound WebSocket, runs Nmap as a subprocess, and now opens outbound Modbus
  connections. There is no inbound listener in `hardware-agent/src/`.
- **Active scanning inverts the trust direction.** Before PR #137 every byte the
  agent parsed came from Nmap. It now parses application-layer data supplied by
  the scanned device — a device that, on an assessment network, may be hostile.
  Modbus has no authentication and no integrity, so any value it reports is
  spoofable.

Nmap OS fingerprinting (`-O`) has required raw-socket privileges since before
this work; it is not new, but the privilege level it implies now also applies to
the new device-data parsers.

## Decision

### 1. V2 authorises bounded active assessment

ADR-002 §7's v1 restriction no longer governs. V2 permits:

| Permitted in V2 | Bound |
|---|---|
| Active OT protocol reads (Modbus FC01–FC04, FC43) | ADR-018 caps and gates |
| `pymodbus` as a pinned dependency | Read-only surface only |
| Nmap OS fingerprinting (`-O`) | Deep stage, NSPi only |
| Additional ADR-002 v2 tools (enum4linux-ng, testssl.sh, Nikto, bounded credential checks) | Their own implementation card |

The following remain forbidden without a further ADR, legal review and explicit
stakeholder approval, unchanged from ADR-002 §8: Metasploit, OpenVAS, and any
flooding, replay, spoofing or denial-of-service technique. Modbus write
functions remain governed solely by ADR-018's two independent gates; nothing in
this ADR relaxes them.

### 2. The agent is egress-only

The agent must not bind or listen on any network port. All communication is
outbound: backend WebSocket, Nmap subprocess, OT protocol clients. This is an
invariant, not an observation, and it must be enforced by an automated test
rather than by review.

Test servers used by the suite bind `127.0.0.1` on an ephemeral port and are
never shipped in the runtime package.

### 3. All device-supplied data is untrusted input

Any value originating from a scanned device — service banners, Nmap script
output, OT protocol responses, identification strings — is untrusted. It must
be:

- **bounded at parse**, with explicit limits on string length and element count,
  never relying on a protocol's incidental frame size for safety;
- **escaped at render**, in the TUI and any other surface that interprets markup;
- **validated at every boundary it crosses**, with the agent-side models at least
  as strict as their backend counterparts.

### 4. Device-claimed identity may narrow scope, never widen it

A device's self-reported vendor or product may select a *more conservative*
scanning profile. It must not select a more aggressive one. Any profile broader
than the conservative baseline requires corroboration the device cannot forge
cheaply — network position (CIDR) or link-layer address.

### 5. The agent runs with least privilege

Raw-socket capability is granted to the Nmap binary through Linux capabilities
(`CAP_NET_RAW`), not by running the agent as `root`. The agent process itself
runs as an unprivileged service account, so device-data parsers never execute
with superuser rights.

Where the deployment cannot grant the capability, the affected scan stage
degrades with a reported reason. It must not fail silently.

### 6. Every active path is bounded in rate and in time

ADR-018 requires active traffic to be "sequential, delayed and bounded". That
obligation applies to **every** active path, including identification probes and
any future protocol, not only register mapping. A bound that exists in code but
is unreachable in the shipped configuration does not satisfy this decision.

Each active stage declares: a maximum request count, a minimum inter-request
delay, a wall-clock ceiling, and a connection-reuse policy.

### 7. The read-only boundary is proven, not asserted

The absence of a write path must be demonstrated by a test that fails when a
write becomes *reachable* — not by a test that checks method names are absent
from a namespace. Write-request counters report measured values, so that the
number stays honest when `active_validation` ships.

### 8. Process values stay on the Pi

Raw coil and register values, and every statistic derived from them, exist only
inside the agent process. They are not written to workspace JSON, the ingest
contract, the database, logs, or operator-facing output. Change between scans is
detected with an HMAC-SHA256 digest keyed by an organisation-scoped secret.
Without that secret the digest cannot be reversed by trying possible values.

## Consequences

- ADR-002 remains the authority for v1 and for the excluded-tools list. Readers
  must consult this ADR for V2 scope; ADR-002 §7 carries a pointer here.
- The Pi's egress-only posture becomes a tested contract. A future feature that
  needs an inbound port requires an ADR, not a pull request.
- Hardening work identified in the PR #137 audit becomes required, not optional:
  markup escaping, parse bounds, profile-selection corroboration, identification
  pacing, an enforced wall-clock bound, and a reachability-based read-only test.
- Deployment gains a provisioning step (`setcap` on the Nmap binary) and loses
  the assumption that the agent runs as `root`.
- Operators may install a local OT policy that only ever makes scanning gentler;
  the hard ceilings stay in code.
- Process values never leave the Pi. Cross-scan change uses a keyed digest, not
  stored summaries.
- Active assessment of a network Dmitri does not own remains an authorisation
  question, not a technical one. This ADR does not grant permission to scan.

## Rejected alternatives

- **Amend ADR-002 in place.** It is the accepted record of a v1 decision that was
  correct when made. Superseding a scoped section preserves that history.
- **Let ADR-018 carry the V2 scope change.** ADR-018 is about Modbus submodes.
  Tool-scope authority and agent-wide hardening are broader than one protocol
  and will outlive it.
- **Run the agent as `root` because Nmap needs raw sockets.** This grants
  superuser rights to every parser in the process to satisfy one subsystem.
  Capabilities scope the grant to the binary that needs it.
- **Treat device identification as trustworthy because the network is
  authorised.** An authorised network is not a trusted one; a compromised device
  is the common case an OT assessment exists to find.
- **Sanitise device strings only at the backend.** The TUI renders them before
  the backend ever sees them, and the agent is the component sharing a network
  with the hostile input.

## References

- [`ADR-002`](ADR-002-scanning-tools-selection.md) §7–8 — superseded scope
- [`ADR-018`](ADR-018-nspi-active-modbus-safety.md) — Modbus safety boundary
- [`ADR-005`](ADR-005-security-model.md) — security model
- [`AUDIT.md`](../../specs/045-ot-agent-hardening/AUDIT.md) — PR #137 audit that motivated this decision
- NIST SP 800-82 Rev. 3: https://csrc.nist.gov/pubs/sp/800/82/r3/final
- `capabilities(7)`: https://man7.org/linux/man-pages/man7/capabilities.7.html
