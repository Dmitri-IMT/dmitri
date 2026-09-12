# TRUTH — NSPi OT inventory and Modbus assessment

Status: accepted product behaviour; implementation is tracked in `TASKS.md`.

This document fixes the product behaviour. `ARCHITECTURE.md` explains where it
lives, `DESIGN.md` explains the protocol details, and `TASKS.md` is the execution
backlog.

## Product objective

The `nspi` mode is the Dmitri mode for an authorised assessment of an OT
network. Its first protocol-specific capability is Modbus TCP. It must discover
assets and exposed services, retain the existing vulnerability checks, identify
Modbus units, map explicitly authorised readable address ranges and, in its
most intrusive submode, validate an exact write on an isolated test point.

The primary product journey is plug-and-scan: a person without networking,
Modbus or cybersecurity expertise connects the appliance, chooses an NSPi
submode and receives an interpreted report. Specialist choices are resolved by
the agent or configured once by an installer; they are not requested from the
operator during every scan.

The result must answer these questions without changing the industrial process
outside an exact disposable point explicitly authorised for active validation:

1. Which hosts and services are reachable?
2. Which endpoints are confirmed or suspected to speak Modbus TCP?
3. Which Modbus Unit IDs and device-identification fields were observed?
4. Which explicitly authorised address ranges are readable through function
   codes 01, 02, 03 and 04?
5. When explicitly authorised, does one exact test coil or holding register
   accept a write without authentication, and was its original value restored?
6. Which known vulnerabilities or insecure exposures are supported by evidence?
7. What was not tested, timed out, or could not be identified?

## Binding behaviour

1. The current `nspi` discovery, two-pass port scan and all scripts in
   `NSPI_NSE_SCRIPTS` continue to run. New Modbus functionality extends that
   pipeline; it does not replace it.
2. `nspi` remains one top-level scan mode and gains the submodes `inventory`,
   `read_only_mapping` and `active_validation`. An omitted NSPi policy means
   `inventory`, so existing CLI, TUI and remote commands remain valid.
3. `inventory` is bounded active enumeration. It consumes `modbus-discover`
   output first and sends a minimal PyModbus identification fallback only when
   that can add information.
4. `read_only_mapping` is opt-in but automatic after selection. It discovers
   eligible targets and Unit IDs from the current scan, then resolves a bounded
   range plan from an installed site profile, a recognised vendor profile or a
   conservative built-in baseline. There is no automatic scan of addresses 0
   through 65535.
5. The `inventory` and `read_only_mapping` paths expose only FC01, FC02, FC03,
   FC04 and FC43/MEI 14. They have no access to a write-capable client.
6. `active_validation` uses a separate, guarded client which exposes only FC05
   (Write Single Coil) and FC06 (Write Single Register). It exposes no generic
   `execute(function_code)` or raw-PDU escape hatch.
7. FC15, FC16, FC22 and FC23, diagnostic mutation, arbitrary function codes,
   replay, spoofing, flooding and denial of service do not exist in the normal
   product scan pipeline.
8. Every active OT request is subject to a per-host request budget, response
   timeout, inter-request delay, one retry at most, the scan deadline and user
   cancellation. Test writes are never retried automatically.
9. OT protocol requests are sequential (`max_workers = 1`) on both Raspberry Pi
   3 and Raspberry Pi 4. “Sequential” describes concurrency and does not mean
   Modbus RTU or a physical serial port. Faster hardware does not justify
   concurrent requests to fragile controllers.
10. A timeout is not proof that an address is unused, and an open TCP/502 port is
   not by itself proof of a vulnerability. Results distinguish observations,
   Modbus exceptions, timeouts and findings.
11. A successful unauthenticated read may create a contextual exposure finding,
    but its evidence must say that legacy Modbus TCP lacks native
    authentication; it must not claim exploitation or assign a CVE without a
    product/version match.
12. A successful authorised FC05/FC06 test may create an “unauthenticated Modbus
    write accepted” finding. The evidence must include the exact target, Unit
    ID, address, captured original value, requested test value, read-back result
    and restoration status.
13. A single register value never determines the physical action of an
    address. Human labels come from an operator-supplied asset map. Behavioural
    inference requires repeat observations during an approved lab procedure and
    is labelled as an inference.
14. Raw coil/register values stay on the Pi. Mapping records a keyed HMAC digest, not a
    summary of the values. See `specs/045-ot-agent-hardening`.
15. Partial results survive cancellation, timeout and per-host failure using the
    existing partial-result behaviour.
16. The local JSON, ingest contract, backend persistence and read API represent
    the same OT observations. Inventory is not hidden in free-form log text or
    scan metadata.
17. New command parameters are threaded through every entry path: one-shot CLI,
    headless runner, daemon/WebSocket command, `ScanRunner`,
    `ScanProgressScreen` and TUI scan creation.
18. The output records the submode, policy version, evidence sources, probe
    counts, read/write counts, skipped targets and termination reason needed to
    reproduce and audit a scan.
19. Product/version-to-CPE mapping is deterministic and confidence-labelled.
    Only an accepted high-confidence CPE enters the existing NVD enrichment
    path.
20. Redpoint's `modicon-info.nse` is an optional Schneider-specific laboratory
    probe. It never joins the default `NSPI_NSE_SCRIPTS` tuple and is not run
    merely because port 502 is open.
21. MATRIX is not a production dependency. Its scenarios may inform isolated
    laboratory tests; its write, overflow, DoS, replay and spoof modules are
    laboratory threat cases only.
22. The agent does not run continuously or on an implicit schedule. Every scan
    has a visible trigger or an explicit future schedule and an approved
    maintenance window.
23. `active_validation` requires two independent permissions: the command/TUI
    request must acknowledge the intrusive submode, and a local policy prepared
    by an installer must enable it for the exact target network. A remote
    command cannot supply or override the local write points.
24. An installed active-validation rule names an exact device selector, open
    TCP port, Unit ID, address space, single address, expected current value and
    test value. The runtime resolves the selector against the discovered host
    and fingerprint; it never discovers writable addresses by sweeping or
    guessing.
25. Active validation performs read-before-write, one test write, read-back, one
    best-effort restoration of the captured original value and restoration
    verification. A mismatched original value skips the write.
26. Once a test write has been sent, cancellation is deferred until restoration
    has been attempted. An unverified restoration stops all further validation,
    produces a prominent incident result and is never reported as success.
27. The web command requires an administrator and explicit confirmation; the
    CLI/TUI require equivalent acknowledgement. The ordinary operator does not
    type IPs, Unit IDs or addresses. Merely choosing `nspi` is not consent to
    write.
28. If no approved validation point matches, `active_validation` still completes
    its inventory/read stages and reports validation as skipped. It does not
    fall back to a guessed write target.
29. Results use plain language, risk, evidence and recommended action. Raw NSE
    text, Modbus exception codes, CPEs and register notation remain available as
    technical detail but are not the only explanation shown to the operator.
30. Network/interface detection, candidate selection, Unit-ID reuse,
    fingerprinting, CVE correlation, result persistence and report generation
    are automatic after the scan is started.
31. The built-in mapping baseline is deliberately incomplete: four addresses
    starting at zero in each FC01-FC04 space, summary capture, one request at a
    time, at most four discovered Unit IDs and at most 32 total Modbus requests
    per host including identification. A local policy may reduce but never
    raise hard product ceilings.
32. The first FC43 correlation catalogue covers only exact Schneider
    Electric/Schneider Automation Modicon M340 and M580 families with a strict
    numeric firmware revision. Unsupported or ambiguous values produce no CPE
    and therefore no inferred CVE.

## Definition of the first usable release

The first usable release is complete when an operator can run `nspi` against a
PyModbus laboratory server and a real authorised test PLC and receive:

- the same Nmap/NSE coverage as today;
- structured Modbus endpoint, Unit ID and device-identification data;
- bounded read-only range results from an installed policy or the labelled
  built-in baseline;
- evidence-backed findings separated from inventory;
- a guarded FC05/FC06 validation against an explicitly configured disposable
  lab point, including verified restoration or an explicit failure state;
- matching local JSON and backend scan-detail data;
- correct progress, cancellation and partial results in CLI, TUI and daemon;
- measured runtime, memory and request count on a Raspberry Pi 3 Model B+ and a
  Raspberry Pi 4 4 GB.
- a successful plug-to-report usability trial in which a participant without
  Modbus expertise starts `inventory` without entering protocol parameters and
  can understand the principal results and recommended actions.

## Out of scope for this feature

- Modbus RTU/serial, Modbus Security on TCP/802 and passive packet capture.
- Automatic semantic naming of registers without documentation or a controlled
  process experiment.
- Subnet-wide or address-range write discovery, multiple-register/coil writes,
  arbitrary PDUs and unattended exploitation.
- FC15, FC16, FC22 and FC23 in the first active-validation release.
- Availability-impact testing in the normal product scan pipeline.
- A generic OT plugin framework before a second protocol is implemented.
- Redpoint protocols other than the optional Schneider Modicon probe.
- Importing MATRIX's CLI, formatting, packet-crafting or attack classes.
- Replacing the backend's existing NVD, KEV, EPSS or risk-scoring services.

## Authoritative references

- The attached TCC article, used for the Modbus threat model and bounded address
  mapping method.
- NIST SP 800-82 Rev. 3, especially the caution required for active scanning:
  https://csrc.nist.gov/pubs/sp/800/82/r3/final
- Modbus Application Protocol V1.1b3:
  https://modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
- Nmap `modbus-discover` documentation:
  https://nmap.org/nsedoc/scripts/modbus-discover.html
- PyModbus documentation: https://pymodbus.readthedocs.io/
- Redpoint: https://github.com/digitalbond/Redpoint
- MATRIX: https://github.com/SpiderLabs/MATRIX
