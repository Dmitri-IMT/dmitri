# TRUTH — Attack surface and IoT profiling

## Narrative

A completed scan can truthfully report no confirmed vulnerabilities while still revealing a
meaningful attack surface: administrative interfaces, databases, file sharing, proxies, cleartext
services, unknown listeners, and device-specific control endpoints. Operators need these
observations separated from vulnerability findings so that an absence of findings is not mistaken
for an absence of security-relevant exposure.

The same evidence is often difficult to interpret on home and small operational networks. Port
registries can label a Tuya control endpoint as IRC or a television endpoint as a database product,
while manufacturer, service, operating-system, hostname, certificate, and banner evidence point to
a different device role. Operators need a conservative device profile that combines independent
signals, exposes uncertainty and contradictions, and preserves the original observations.

This feature introduces attack-surface exposures as a first-class scan result alongside
vulnerability findings and enriches every discovered machine with an evidence-backed profile. It
extends the automatic machine classification introduced by PR #143 / spec 046; it does not create
a competing type vocabulary. It improves interpretation of evidence already collected by the
scan and does not add intrusive probing.

## Business rules

- A vulnerability finding represents affirmative evidence of a weakness. An exposure represents a
  reachable part of the attack surface and must never be presented as a confirmed vulnerability.
- Vulnerability totals, severity totals, and the meaning of a clean vulnerability result do not
  include exposures.
- Every confirmed open network endpoint is represented once in the attack-surface inventory.
  Closed and filtered endpoints are not exposures.
- An exposure identifies the device, endpoint, observed service, reason it matters, supporting
  evidence, confidence, and an operator attention level distinct from vulnerability severity.
- A versioned policy classifies exposures into stable roles such as administration, API, data
  store, file sharing, remote access, proxy, device control, discovery, media, and unknown.
- Policy can raise operator attention for security-relevant conditions such as a remotely reachable
  administrative surface, data store, cleartext service, proxy, file-sharing service, or
  unidentified listener. Raised attention requests review; it does not assert exploitability.
- A high or unusual port number alone is not evidence of a vulnerability or a specific service.
- An exposure and a vulnerability finding may refer to the same endpoint. They remain separate
  facts and are cross-referenced in presentation rather than deduplicated into one category.
- Each machine receives a profile containing the existing machine type, manufacturer assessment, optional
  product-family or model assessment, confidence, evidence, and any material conflicts.
- Machine type reuses the exact closed vocabulary introduced by spec 046: router, computer,
  camera, storage, TV, phone, printer, sensor, and unknown. Product-family and model assessments
  may describe a more specific IoT role, but they never introduce a second machine-type enum.
- Profiling evaluates all discovered devices. It does not require the system to prove that a device
  is IoT before producing a profile.
- Profiling combines available manufacturer, hostname, operating-system, service, version, banner,
  certificate, protocol, and port evidence. Original scan observations remain available unchanged.
- A port registry label by itself can support only a low-confidence service or device inference.
  Manufacturer identity by itself cannot establish an exact product model.
- Independent agreeing signals may increase confidence. Missing, generic, randomized, or
  contradictory signals must lower confidence or leave the relevant identity unknown.
- A conflicting profile explicitly describes the conflicting evidence instead of silently choosing
  one observation as truth.
- Unknown is a valid result. The profiler must not invent a manufacturer, model, machine type, or
  service to make the inventory appear complete.
- Profiling is deterministic for the same policy version and normalized evidence.
- Policy decisions are local, reviewable, versioned, and testable. Profiling does not depend on a
  cloud lookup, generative model, or live third-party service.
- Exposure and profile evidence must be concise and must not add secrets or full response bodies to
  the scan result.
- Partial scans produce exposures and profiles only from accepted evidence and preserve the
  existing terminal semantics: completed scans with isolated skipped/failed units are visibly
  incomplete but finished, while cancellation, deadline, or fatal interruption remains stopped.
  Missing coverage is never represented as a clean result.
- The TUI and cloud application are separate readers. The TUI reads only the in-memory or locally
  saved scan payload and has no connection to the backend. Headless/daemon execution may submit
  the same payload to the backend, and React reads only the backend API. Both preserve the
  distinction among inventory, exposures, and vulnerability findings.
- Previously saved scans that predate this feature remain readable. Their unavailable exposure and
  profile data is shown as unavailable or empty, never reconstructed as if it had been captured.
- This feature reuses evidence produced by general inspection. The later service-targeted
  assessment may add more evidence to the same exposure/profile model; it does not create a
  parallel classifier or recompute historical results.

## User stories

1. As a home-network operator, I want to see reachable services even when no vulnerability is
   confirmed, so that I know what should be reviewed or intentionally exposed.
2. As an analyst, I want exposures separated from findings, so that I can communicate attack
   surface without overstating risk.
3. As an operator, I want a device described by likely role and product family with visible
   confidence and evidence, so that misleading port labels do not become accepted identity.
4. As a reviewer, I want contradictory and insufficient evidence called out, so that I can trust
   the system when it says that a device is unknown.
5. As a product user, I want the same stored exposure and machine-profile meaning in local and
   cloud views, even though the TUI does not connect to the backend.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Clean scan with attack surface | A completed scan has open endpoints and no confirmed vulnerability | Results are normalized and displayed | Vulnerability findings remain zero and the open endpoints appear separately as exposures |
| Open endpoint inventory | A device has one confirmed open TCP endpoint | Exposures are produced | Exactly one base exposure identifies that device and endpoint |
| Closed or filtered endpoint | A port is closed or filtered | Exposures are produced | No exposure is created for that port |
| Administrative surface | An open endpoint is affirmatively identified as a management interface | Policy evaluates it | The exposure is classified as administration with review rationale and evidence, without becoming a vulnerability finding |
| Data-store surface | A database service is reachable from the scanned network | Policy evaluates it | The exposure is classified as a data store and asks for an intentional-exposure review |
| Unknown listener | An open endpoint has no reliable service fingerprint | Policy evaluates it | The endpoint remains an unknown exposure with uncertainty visible and no invented product |
| Vulnerable exposed service | An endpoint has both a confirmed vulnerability and exposure evidence | Results are displayed | The exposure and finding remain in their respective categories and the relationship is visible without double-counting vulnerability totals |
| Attention is not severity | An exposure has elevated operator attention but no affirmative weakness | Summary totals are calculated | It does not contribute to vulnerability severity or finding counts |
| Agreement raises confidence | Manufacturer and multiple service or protocol signals independently support the same machine type | A profile is produced | The type is reported with the supporting signals and a higher confidence than any single signal allows |
| Port-name mismatch | A conventional port name conflicts with manufacturer and protocol evidence | A profile is produced | The conventional name is preserved as observed evidence but does not determine the machine type or product identity |
| Manufacturer-only evidence | Only a manufacturer prefix is known | A profile is produced | Manufacturer may be reported, exact model remains unknown, and confidence is bounded |
| Randomized address | A device uses a locally administered or randomized hardware address | A profile is produced | No manufacturer is inferred from that address and the limitation is visible |
| Contradictory fingerprints | Manufacturer, operating-system, and service signals materially disagree | A profile is produced | Conflicts are listed and the affected inference is reduced in confidence or left unknown |
| Unknown device | Available evidence cannot support a machine type | A profile is produced | The type is unknown with the evidence gap stated |
| Deterministic policy | Identical normalized evidence and policy version are evaluated twice | Profiles and exposures are compared | Classification, confidence, and attention outputs are identical |
| Policy evolution | Classification rules change after release | A new scan is processed | The result records the new policy version and historical stored results are not silently rewritten |
| Partial scan that finishes | A scan reaches normalization after accepting only part of its evidence | Results are produced | Exposures and profiles reflect only accepted evidence and the scan is visibly finished with incomplete evidence |
| Interrupted partial scan | Cancellation, deadline, or fatal error interrupts a stage after evidence was accepted | Results are produced | Accepted exposures/profiles remain visible and the scan is visibly stopped at the interrupted stage |
| Local result | A local scan completes | The operator opens its result in the TUI | Inventory, exposures, findings, profile confidence, and evidence are distinguishable |
| Cloud result | A scan is ingested and later requested through the application | The operator opens scan or host detail | Stored exposures and profiles retain the agent's meaning and evidence |
| Disconnected TUI | Backend connectivity is absent or disabled | A TUI scan completes and its result is opened | The local profile and exposures remain available; no API request is attempted |
| Existing machine type | PR #143 has classified a machine with the canonical nine-value vocabulary | The richer profile is produced and ingested | The profile uses the same machine type; no parallel `device_class` value is exposed |
| Legacy result | A stored result predates exposure and profile fields | A supported reader opens it | The result remains readable and missing enrichment is not presented as a completed clean assessment |
| No extra probing | A scan contains enough evidence for exposure and profile processing | The feature runs | No additional network request or external lookup is made by this feature |
| No sensitive evidence expansion | A banner or response contains credential-like or secret material | Evidence is normalized | The new exposure and profile data contains no secret or full response body |
| Regression gates | The feature is complete | Contract, agent, backend, TUI, and frontend test suites run | Schema compatibility, classification, persistence, rendering, legacy reads, and category counts are covered and all required gates pass |

## Out of scope (v1)

- UDP discovery or scanning, full-packet inspection, passive traffic capture, and wireless
  fingerprinting.
- New network probes, authenticated inspection, credential attempts, exploitation, or
  device-control requests.
- Third-party manufacturer databases, cloud enrichment APIs, automatic Internet searches, machine
  learning, or generative-model classification.
- Automatic remediation, firewall changes, device isolation, or configuration changes.
- User-authored classification rules, manual profile corrections, and organization-specific risk
  scoring.
- Treating every exposure as a vulnerability or assigning CVSS scores to exposure observations.
- Implementing the later service-targeted assessment specified by
  `../048-service-targeted-tools/`.
- Retrospective inference of exposure or profile data for legacy scans that did not store it.

## Related specs

- Implementation: `ARCHITECTURE.md`, `INTEGRATION.md`, `DESIGN.md`
- Existing inventory classification: PR #143 / `../046-machine-inventory-depth/`
- Downstream targeted enrichment: `../048-service-targeted-tools/`
