# ARCHITECTURE — Attack surface and IoT profiling

## System context

This feature adds a deterministic local assessment step to the existing scan pipeline:

```text
discovery -> ports -> deep inspection -> OT inspection (NSPi)
          -> normalize: local assessment -> ScanPayload
          -> local JSON -> TUI
          -> optional signed ingest -> backend/Postgres -> React
```

The assessment consumes only evidence already accepted into `HostInfo`: host identity, open-port
and service fingerprints, OS/CPE data, selected bounded NSE facts, and Modbus inventory. It
performs no socket operation, subprocess, cloud lookup, or generative inference. It is a substep
of normalization, so it adds no progress stage, timeout, cancellation branch, scan-mode gate, or
constructor parameter. Spec 048 may later contribute structured targeted evidence through the
same assessment input without changing these ownership rules.

The three result categories remain different facts:

- inventory is the observed host/port/service data under `hosts`;
- exposures are one classified attack-surface record for every accepted open endpoint;
- findings are affirmative weaknesses and keep the existing severity/count/risk semantics.

An endpoint may have both an exposure and findings. They are persisted separately and linked for
reading by their shared `port_id`; neither record is converted into or deduplicated against the
other.

PR #143 / spec 046 is an implementation dependency: it establishes the backend inventory and the
canonical `MachineType`. This spec extends that classification with confidence, evidence,
conflicts, manufacturer and optional product details. It does not add `DeviceClass` or another
coarse type. Quick and Standard produce complete assessments from their smaller evidence set.

The TUI is not a backend client. `ScanProgressScreen` runs `ScanRunner`, and `ScanViewScreen` reads
the resulting in-memory or local JSON `ScanPayload`. Only the headless/daemon transport path can
submit that payload to FastAPI. React is the backend reader; it never reads the TUI's local file.

## Data model and contracts

### Shared assessment vocabulary

The cross-layer assessment contract uses the following exact string domains, and the canonical
OpenAPI copies every wire/read domain as an enum:

```text
ExposureRole = administration | data_store | file_sharing | remote_access | proxy |
               api | device_control | discovery | media | general_service | unknown
ExposureAttention = informational | review | priority
AssessmentConfidence = unknown | low | medium | high
ExposureConfidence = low | medium | high
EvidenceKind = manufacturer | hostname | operating_system | service | version | banner |
               certificate | protocol | port | cpe | industrial | web_path
MachineType = router | computer | camera | storage | tv | phone | printer | sensor | unknown
AssessmentStatus = available | unavailable
```

`unknown` is valid only for profile confidence and machine type; `ExposureConfidence` excludes it
because the open endpoint itself is confirmed even when its role is unknown. `AssessmentStatus`
is a backend read-model enum derived from the nullable policy marker; it is not serialized by the
agent or accepted on ingest.
Attention is deliberately not named low/medium/high and is never mapped to CVSS or vulnerability
severity.

`AssessmentEvidencePayload` has exactly `kind`, `source`, and `value`. Each string is trimmed;
`source` and `value` are bounded to 80 and 160 characters respectively. `observed_service`,
`observed_version`, manufacturer, product family, and model are each at most 160 characters;
`reason`, conflict, and limitation strings are each at most 240 characters. At most 12 evidence
items, 5 conflicts, and 5 limitations are emitted per record. Duplicate evidence is removed by
`(kind, source, casefold(value))` and sorted by kind, source, then value.

`ExposurePayload` has exactly:

```text
ip: IPv4Address
port: int 1..65535
protocol: tcp | udp
observed_service: non-empty string
observed_version: string | null
role: ExposureRole
attention: ExposureAttention
confidence: ExposureConfidence
reason: non-empty bounded string
evidence: list[AssessmentEvidencePayload]
```

`DeviceProfilePayload` has exactly:

```text
manufacturer: string | null
product_family: string | null
model: string | null
confidence: AssessmentConfidence
evidence: list[AssessmentEvidencePayload]
conflicts: list[string]
limitations: list[string]
```

`ScanPayload` and backend `ScanIngestRequest` add
`assessment_policy_version: str | None = None` and
`exposures: list[ExposurePayload] = Field(default_factory=list)`. `HostPayload` adds
`machine_type: MachineType | None = None` and
`device_profile: DeviceProfilePayload | None = None`. The type stays at host level, matching the
PR-143 inventory field; it is not duplicated inside the profile. The optional/defaulted ingest
shape is intentional: payloads saved before this feature validate as legacy data.

For a new payload, `assessment_policy_version` is `LOCAL_ASSESSMENT_POLICY_VERSION` and every host
has a non-null `machine_type` plus a profile, including an explicit unknown type/profile. Every
unique open `(ip, protocol, port)` has
exactly one exposure; closed and filtered ports have none. Contract validators reject a non-null
version with missing/duplicate endpoint assessments, an exposure without a matching open port, or
a null version carrying exposures, host machine types, or profiles. A missing/null version therefore means unavailable,
not a clean assessment. This invariant is enforced independently by the agent and backend.

### Deterministic local policy

`hardware-agent/src/agent/assessment/policy.py` is the sole authority for per-scan profile and
exposure interpretation, source reliability, attention rules, score thresholds, and
`LOCAL_ASSESSMENT_POLICY_VERSION = "2026-09-15.1"`. No rule is read from environment variables,
live files, or mutable remote data. Any output-affecting change requires a new literal version and
new golden fixtures; historical payloads and rows are not rewritten.

The existing backend `classify_machine_type()` from spec 046 remains the compatibility fallback
for payloads sent by older agents that have no current `HostPayload.machine_type`. For a current
assessed payload, the ingested host-level `machine_type` is the classification observation and the
latest-scan inventory reconciliation copies that exact value to `HostRecord.machine_type`. The
backend must not independently reclassify the same current snapshot. This preserves one public
taxonomy while letting a disconnected TUI and the cloud display the same agent-produced result.

The analyzer first canonicalizes a strict allowlist of compact facts. It never copies an NSE body,
HTTP response body, tool stdout/stderr, credential value, token, cookie, private key, or raw
certificate. It may retain only a selected certificate subject/issuer label, structured protocol
identity and compact product/version/CPE. Values pass the assessment redaction and length bounds
before they can become evidence. Spec 048 must obey this same boundary when it later supplies
targeted observations.

Candidate machine types receive one score per independent `(kind, source)`; repeats cannot inflate
confidence. Protocol-confirmed/industrial identity weighs 3, product/CPE or OS fingerprint with at
least 90% Nmap accuracy weighs 2, and trusted OUI manufacturer, hostname, generic service, and port
registry evidence weigh 1. The versioned table maps explicit patterns to candidates. The result is:

- score below 2: class `unknown`, confidence `unknown`;
- score 2–3: `low`; score 4–5: `medium`;
- score 6 or more: `high` only with at least two different evidence kinds, otherwise capped low;
- if the runner-up scores at least 3 and is within one point of the leader, machine type is `unknown`,
  confidence is `low`, and the competing facts are recorded in `conflicts`.

`MACHINE_SIGNAL_RULES` starts from spec 046's exact public classification vocabulary but treats
each match as scored evidence rather than first-match truth. Matching is case-insensitive over
trimmed values and uses token/subsequence entries below; a numeric port is only a weight-1 `port`
fact.

| Candidate | Service/port patterns inherited from spec 046 | Vendor substrings inherited from spec 046 |
|---|---|---|
| camera | 554, 8554, `rtsp`, `onvif` | `hikvision`, `dahua`, `axis communications`, `reolink`, `amcrest` |
| printer | 631, 9100, `ipp`, `jetdirect`, `printer` | `brother`, `canon`, `epson`, `lexmark`, `xerox`, `kyocera`, `ricoh` |
| storage | 2049, 548, 3260, `nfs`, `afp`, `iscsi` | `synology`, `qnap`, `buffalo`, `western digital` |
| router | DNS (`53` or `domain`) plus web (`80`, `443`, or `8080`), or UPnP (`1900` or `upnp`) plus DNS | `mikrotik`, `tp-link`, `netgear`, `d-link`, `zyxel`, `technicolor`, `sagemcom`, `arris`, `ubiquiti`, `cisco`, `asustek` |
| tv | 8008, 8009, 7000, `airplay`, `dial` | `roku`, `vizio`, `sony visual`, `lg electronics` |
| phone | no port-only rule | `apple`, `oneplus`, `xiaomi`, `motorola` |
| sensor | 1883, 5683, `mqtt`, `coap` | `espressif`, `tuya`, `shelly`, `sonoff` |
| computer | 22, 445, 3389, 5900, `ssh`, `microsoft-ds`, `ms-wbt-server`, `vnc` | none |

High-accuracy Nmap `device_type` maps exact normalized values as follows: `router`, `firewall`, or
`wap` → router; `general purpose`, `workstation`, or `server` → computer; `webcam` or `camera` →
camera; `storage-misc` or `nas` → storage; `printer` → printer; `media device` → tv; `phone` →
phone; `sensor` → sensor. Product/CPE/protocol facts contribute only when they contain an exact
policy token already listed for that candidate or the explicit device nouns `camera`, `printer`,
`router`, `nas`, `television`, `smart tv`, `phone`, or `sensor`. Ambiguous vendor names such as
Samsung, LG, Sony, Apple, and Amazon may populate manufacturer but are not machine-type signals by
themselves. Modbus identity contributes to product family/model but does not label every controller
as a sensor.

A locally administered MAC address never contributes OUI manufacturer evidence and adds the
limitation `Locally administered MAC address; OUI manufacturer unavailable.` Manufacturer
candidates use the same independent-source scoring; tied material candidates produce null plus a
conflict. `product_family` requires a policy-matched product-bearing fact (protocol identity,
product string, CPE, selected title/banner, or certificate label) plus an independent corroborating
fact. `model` is emitted only from an explicit structured model/product identifier, never from a
manufacturer or port number. Missing requirements stay null and add a concise limitation.

Exposure role matching follows table order, strongest first: confirmed protocol/industrial
identity; product/CPE; structured selected script/targeted evidence; Nmap service/product; then
port number as a low-confidence fallback. A port-registry label by itself is preserved as
`observed_service` and can yield only low confidence. Role ties at the same reliability resolve to
`unknown`, not table order.

The initial exposure-role matcher uses these case-insensitive whole-name/token-boundary service
tokens and conservative port fallbacks (`ftp` never matches `sftp`; `http` never matches
`http-proxy`). `api` and `administration` require structured title/script/targeted evidence; a bare
web port remains `general_service`.

| Role | Accepted service/protocol tokens | Port-only fallback |
|---|---|---|
| administration | `management`, `webadmin`, `admin console`, `routeros` | none |
| api | `openapi`, `swagger`, `api documentation` | none |
| data_store | `mysql`, `postgresql`, `mongodb`, `redis`, `memcached`, `elasticsearch`, `cassandra`, `oracle-tns`, `ms-sql-s`, `influxdb`, `couchdb` | 1433, 1521, 27017, 3306, 5432, 6379, 9042, 9200, 11211 |
| file_sharing | `microsoft-ds`, `netbios-ssn`, `smb`, `samba`, `nfs`, `afp`, `iscsi`, `ftp` | 21, 139, 445, 548, 2049, 3260 |
| remote_access | `ssh`, `telnet`, `ms-wbt-server`, `rdp`, `vnc`, `winrm` | 22, 23, 3389, 5900, 5985, 5986 |
| proxy | `http-proxy`, `socks`, `squid` | 1080, 3128 |
| device_control | `modbus`, `mqtt`, `coap`, `bacnet`, `s7comm`, `ethernet/ip` | 502, 1883, 5683, 47808 |
| discovery | `mdns`, `ssdp`, `upnp` | 1900, 5353 |
| media | `rtsp`, `airplay`, `dlna`, `dial` | 554, 7000, 8008, 8009, 8554 |
| general_service | any other identified service, including bare HTTP/HTTPS, DNS, SMTP, or generic application traffic | any other known open endpoint |
| unknown | blank, `unknown`, or tied contradictory evidence | no reliable match |

Attention is a separate deterministic maximum:

- `review` baseline for administration, API, data store, file sharing, remote access, proxy,
  device control, and unknown listeners;
- `informational` baseline for discovery, media, and general service;
- `priority` only when accepted evidence also indicates a cleartext administrative/remote/control
  channel or an unauthenticated sensitive surface; the corresponding weakness remains a finding
  only if the existing finding pipeline has affirmative evidence.

`reason` names the selected role and the rule that set attention. It cannot claim exploitability.
Exposure order is IP address numerically, protocol, then port; host/profile evidence uses the
stable ordering above.

### Persistence model

The Alembic revision `20260920_33_attack_surface_profiles` has revision id `20260920_33` and
follows the current single Alembic head `20260919_32`, and adds:

- nullable `scans.assessment_policy_version`;
- nullable `scan_hosts.machine_type`, nullable JSON `scan_hosts.device_profile_json`, nullable
  JSON `hosts.device_profile_json`, and nullable `hosts.device_profile_policy_version`; PR #143's
  existing `hosts.machine_type` column is reused;
- table `exposures` represented by `ExposureRecord`.

`ExposureRecord` columns are `id`, `exposure_id`, `scan_id`, `scan_host_id`, `port_id`, `ip`,
`port`, `protocol`, `observed_service`, `observed_version`, `role`, `attention`, `confidence`,
`reason`, `evidence_json`, and `created_at`. `exposure_id` is a public UUID; `id` is the internal
integer key. The table has unique constraints on `exposure_id` and
`(scan_id, scan_host_id, port, protocol)`, check constraints for the three bounded enums, indexes
on `scan_id`, `scan_host_id`, `port_id`, `role`, and `attention`, and foreign keys matching the
existing scan/host/port ownership chain.

The table is in `public`, has RLS enabled, and exposes no policy to Data API roles. The migration
conditionally revokes all table/sequence privileges from `anon` and `authenticated`, then grants
`SELECT, INSERT, UPDATE` on the table and `USAGE, SELECT` on its sequence to `dmitri_runtime`,
matching the current child-record migration convention.
Application reads still enforce `ScanRecord.org_id`; no client talks to Supabase directly. The
migration runs over the direct port 5432 connection, never the transaction pooler.

During ingest, ports are persisted before exposures. Each exposure resolves through
`(ip, port, protocol)` to the already-created `ScanHostRecord` and `PortRecord`; an unresolved
reference aborts the transaction. Machine type and profile are stored as immutable scan snapshots.
Only a scan that wins the existing latest-observation reconciliation may update `HostRecord`: a
current assessed scan copies its type, profile, and policy version; a newer legacy scan applies the
PR-143 machine-type fallback and clears only the current profile projection/version so the UI
cannot present stale enrichment as current. An older scan never changes either projection.
Historical scan-host snapshots remain intact. Existing completed-scan idempotency remains
unchanged.

The public read models add `AssessmentStatus`. `ScanDetailResponse` adds
`assessment_status`, nullable `assessment_policy_version`, and `exposures: list[ExposureRead]`.
`ScanHostView` adds nullable `machine_type` and `device_profile`. `HostSummary` and
`HostDetailResponse` add nullable `device_profile`; their existing required PR-143 `machine_type`
remains unchanged. Host summary/profile fields come from the current `HostRecord` projection.
Host detail also adds `assessment_status`, nullable `assessment_policy_version`, and the latest
chronological scan's `exposures`; these three fields describe the same scan snapshot, so a newer
legacy scan is unavailable rather than silently falling back to older exposures. `ExposureRead`
adds backend identity to the payload fields:
`exposure_id`, `scan_id`, `host_id`, `related_finding_ids`, and `detected_at`.
`related_finding_ids` is deterministically sorted and contains findings with the same non-null
`port_id`; it is a presentation link only. Scan summaries and all finding counts remain unchanged.

For rows with null `assessment_policy_version`, reads return `assessment_status="unavailable"`,
`exposures=[]`, and null profiles. For new complete or partial rows they return `available`; the
existing `metadata.partial_result`, `interrupted_stage`, and `terminated_by` remain the authority
for scan coverage. No migration backfills or infers historical profiles/exposures.

## ScanRunner and reader call-path audit

No public constructor, command, or transport parameter is added. Assessment is called only from
`ScanRunner._build_payload`, which already serves successful, cancelled-after-evidence, timeout,
and error partial finalization paths.

| Entry path | Existing call chain | Required result |
|---|---|---|
| TUI | `HomeScreen -> ScanProgressScreen._start_scan -> ScanRunner(...) -> _build_payload` | Same automatic policy/version; result opens from memory/local JSON in `ScanViewScreen`, with no backend request. |
| Headless CLI | `cli._run_agent -> run_headless_scan -> ScanRunner(...) -> _build_payload` | JSON and upload contain identical assessment data. |
| Daemon command | `daemon -> run_headless_scan -> ScanRunner(...)` | Remote scans cannot opt out or select another policy. |
| Normal completion | `ScanRunner._run -> _build_payload` | All accepted hosts/endpoints are assessed once. |
| Partial completion | `ScanRunner._finalize_partial -> _build_payload` | Only accepted evidence is assessed; partial metadata is preserved. |
| Local history | `Workspace` JSON -> `ScanPayload.model_validate -> ScanViewScreen` | Legacy defaults load and display unavailable. |
| Cloud ingest | Headless/daemon `IngestClient -> POST /api/v1/scans -> ingest_scan -> persist_scan` | Optional path only; version/invariants validate before one transaction persists snapshots. It is not reached by the TUI. |
| Cloud scan detail | `GET /scans/{scan_id} -> get_scan_detail` | Inventory, exposures, findings, and status remain separate. |
| Cloud host detail | `GET /hosts/{host_id} -> get_host_detail` | Latest snapshot profile/exposures and historical unavailability are explicit. |

Implementation review must grep every `ScanRunner(`, `ScanProgressScreen(`, `ScanPayload(`,
`ScanPayload.model_validate`, `ScanIngestRequest(`, and `ScanIngestRequest.model_validate` call.
Because no constructor parameter exists, `ScanRunner` and `ScanProgressScreen` signatures stay
unchanged; every fixture/factory must still be checked for legacy versus current intent.

## New files and naming (mandatory)

Every file expected to be created or touched by implementation is fixed here.

| Layer | Path | Symbols / exact responsibility |
|---|---|---|
| Assessment package | `hardware-agent/src/agent/assessment/__init__.py` | Re-export `AssessmentResult` and `assess_hosts`. |
| Policy | `hardware-agent/src/agent/assessment/policy.py` | `LOCAL_ASSESSMENT_POLICY_VERSION`, PR-143-compatible `MachineType`, rule tables, weights, thresholds, bounds, and attention rules. |
| Analyzer | `hardware-agent/src/agent/assessment/analyzer.py` | `AssessmentResult`, `assess_hosts`, bounded evidence extraction/redaction, exposure classification, profile scoring/conflicts, stable ordering. |
| Agent contracts | `hardware-agent/src/agent/normalize/contracts.py` | `AssessmentEvidencePayload`, `ExposurePayload`, `DeviceProfilePayload`; optional legacy fields and cross-field invariants. |
| Contract exports | `hardware-agent/src/agent/normalize/__init__.py` | Export the three new payload models. |
| Runner | `hardware-agent/src/agent/scanner/runner.py` (`ScanRunner`) | Run `assess_hosts` inside `_build_payload` for normal and partial paths; set version/exposures/profiles. No constructor change. |
| Host normalization | `hardware-agent/src/agent/scanner/stages.py` | Extend `build_host_payload(..., device_profile=...)`; preserve raw inventory unchanged. |
| Local TUI summary | `hardware-agent/src/agent/tui/screens/scan_view.py` (`ScanViewScreen`) | Render category totals and device navigation while retaining current payload/file loading and caller behavior. |
| Local TUI detail | `hardware-agent/src/agent/tui/screens/device_detail.py` (`DeviceDetailScreen`) | Render inventory, attack surface, vulnerability findings, profile confidence/evidence/conflicts, and legacy/partial states specified by `DESIGN.md`. |
| Local TUI completion | `hardware-agent/src/agent/tui/screens/home.py` | Add the separate attack-surface total to the fresh-scan summary without changing scan launch paths. |
| Local TUI styles | `hardware-agent/src/agent/tui/app.tcss` | Style summary navigation and detail sections while keeping exposure attention distinct from finding severity. |
| Agent contract tests | `hardware-agent/tests/test_contract_models.py` | Current/legacy payload invariants, endpoint coverage, duplicates, enum/bound failures. |
| Policy tests | `hardware-agent/tests/unit/test_assessment_policy.py` | Frozen version, exact taxonomy/mappings/weights/attention and version-change golden fixture. |
| Analyzer tests | `hardware-agent/tests/unit/test_assessment_analyzer.py` | Endpoint cardinality, no closed/filtered exposure, scoring, mismatch, randomized MAC, conflict, unknown, redaction, bounds, deterministic ordering, exact PR-143 machine-type vocabulary and no I/O. |
| Runner tests | `hardware-agent/tests/unit/test_scan_runner_events.py` | Normal/partial payload integration and unchanged event sequence/constructor. |
| Workspace tests | `hardware-agent/tests/unit/test_workspace.py` | New round trip and pre-feature JSON defaults/unavailable marker. |
| TUI summary tests | `hardware-agent/tests/unit/test_tui_scan_view.py` | Category separation, navigation, counts, partial and legacy copy. |
| TUI detail tests | `hardware-agent/tests/unit/test_tui_device_detail.py` | Profile evidence/conflicts, exposure/finding separation, endpoint relationships, legacy and partial states. |
| TUI flow tests | `hardware-agent/tests/integration/test_tui_flows.py` | Fresh and saved scan summary/detail/back-navigation paths and stable widget IDs. |
| Agent integration | `hardware-agent/tests/integration/test_extensive_e2e.py` | General scan evidence reaches one deterministic assessment without extra network calls by 047. |
| Ingest schemas | `backend/src/api/schemas/scan.py` | Mirror agent models/defaults; enforce current-versus-legacy cross-field invariants. |
| Read schemas | `backend/src/api/schemas/read.py` | `AssessmentStatus`, `ExposureRead`, profile fields, related finding IDs and explicit availability. |
| Schema exports | `backend/src/api/schemas/__init__.py` | Export ingest assessment models. |
| ORM | `backend/src/api/models/persistence.py` | `ExposureRecord`; policy/profile columns and enum check constraints. |
| Model registration | `backend/src/api/models/__init__.py` | Existing persistence import registers `ExposureRecord`; update module description only if needed. |
| Migration | `backend/alembic/versions/20260920_33_attack_surface_profiles.py` | Revision `20260920_33`, down revision `20260919_32`; add nullable/versioned snapshots and secured `exposures` table with no backfill. |
| Ingest | `backend/src/api/services/persistence.py` | Persist version/profiles/exposures after endpoint resolution in the scan transaction. |
| Inventory reconciliation | `backend/src/api/services/inventory.py` | Extend PR #143's latest-scan reconciliation: current assessment copies type/profile/version; a newer legacy snapshot uses the existing classifier and clears the current profile projection; an older scan changes neither. |
| Read service | `backend/src/api/services/read.py` | Org-scoped exposure/profile reads, availability mapping, related finding link and stable ordering. |
| Ingest schema tests | `backend/tests/test_ingest_schema.py` | Legacy acceptance and current cross-field rejection matrix. |
| Persistence tests | `backend/tests/test_ingest_scan.py` | Atomic FK resolution, unique endpoints, idempotency, version/profile/exposure storage. |
| Inventory reconciliation tests | `backend/tests/test_inventory_reconcile.py` | Current agent profile wins, newer legacy payload uses the PR-143 fallback and exposes profile unavailable, older scans cannot change the projection, and unknown is stored. |
| Scan read tests | `backend/tests/test_read_scans.py` | Separate exposure/finding output, related IDs, org boundary, current/legacy/partial status. |
| Host read tests | `backend/tests/test_read_hosts.py` | Latest profile/exposures and unavailable legacy state. |
| Migration tests | `backend/tests/test_attack_surface_migration.py` | Upgrade/downgrade, constraints/indexes/FKs, null legacy columns, RLS and role grants/revokes. |
| Contract fidelity | `backend/tests/test_contract_fidelity.py` | FastAPI request/read schemas remain structurally identical to canonical OpenAPI. |
| Canonical contract | `contracts/openapi/openapi.yaml` | Add canonical schemas and fields to ingest, scan detail and host reads; no new endpoint. |
| Contract example | `contracts/examples/scan_result.example.json` | Current assessment version, one profile per host and one exposure per open endpoint. |
| Generated frontend types | `frontend/src/types/openapi.d.ts` | Regenerate only with `npm run gen:types`; never hand-edit. |
| Attention primitive | `frontend/src/components/AttentionWord.tsx` | Shared non-severity rendering for informational/review/priority. |
| Attention tests | `frontend/src/components/AttentionWord.test.tsx` | Exact labels and no severity semantics. |
| Exposure presentation | `frontend/src/pages/scans/ExposureTable.tsx` | Typed exposure table/disclosures and related finding links. |
| Exposure columns | `frontend/src/pages/scans/exposureColumns.tsx` | Exact endpoint, role, attention and confidence columns. |
| Scan detail | `frontend/src/pages/ScanDetail.tsx` | Separate vulnerability, attack-surface, and machine inventory sections; unavailable and partial states. |
| Scan detail tests | `frontend/src/pages/ScanDetail.test.tsx` | Separate counts/categories, relationships, empty, partial and legacy unavailable. |
| Host profile | `frontend/src/pages/hosts/HostProfile.tsx` | Device class/manufacturer/product/model, confidence, evidence, conflicts and limitations. |
| Host exposures | `frontend/src/pages/hosts/HostExposures.tsx` | Latest endpoint exposures and related finding links. |
| Host detail | `frontend/src/pages/HostDetail.tsx` | Compose profile, exposures, vulnerabilities, inventory, and legacy status. |
| Host detail tests | `frontend/src/pages/HostDetail.test.tsx` | Known/unknown/conflicting/randomized-MAC, exposure and legacy states. |
| Frontend fixtures | `frontend/src/test/scansHarness.ts` | Generated-contract assessment fixtures for scan detail. |
| Frontend fixtures | `frontend/src/test/hostsHarness.ts` | Generated-contract profile/exposure fixtures for host detail. |
| Architecture docs | `docs/architecture/ARCHITECTURE.md` | Record the assessment substep and `exposures` persistence entity after implementation. |

`frontend/src/api/scans.ts` and `frontend/src/api/hosts.ts` remain unchanged because they already
return generated canonical response types. No `/exposures` endpoint, global exposure page,
dashboard score, materialized view, or background enrichment job is introduced in v1.

## Constraints and compatibility

- The implementation must land after PR #143 / spec 046 because it extends that inventory and its
  exact nine-value `MachineType`. Spec 048 lands later and may contribute observations without
  introducing another classifier or changing historical snapshots.
- All classification executes on the Pi/local agent before serialization. Backend and clients
  validate, persist, and present current snapshots. The backend's PR-143 classifier remains only
  the explicit fallback for legacy agents that send no profile.
- TUI presentation depends only on `ScanPayload` and local workspace JSON. It must not import a
  transport/API client, require `AGENT_BACKEND_BASE_URL`, or wait for ingest. Backend and React
  failures cannot remove local assessment data from a completed TUI scan.
- Current payload invariants prevent a producer from labeling missing analysis as available.
  Legacy optional defaults remain readable by the agent, backend, OpenAPI clients, and TUI.
- The migration is additive and nullable. It does not lock/rewrite existing scan rows, derive old
  data, or change finding/risk aggregates. Create indexes in the normal Alembic upgrade; the
  expected table size is bounded by open endpoints per stored scan.
- No new Supabase project, external service, daemon, hardware, dependency, or secret is required.
  `HUMAN_INFRA_REQUIRED` is not set. Deployment requires only running the committed Alembic
  revision through the existing direct migration connection.
- Keep evidence bounded and redact before constructing payload models. Original inventory remains
  intact; assessment output never becomes a second raw-artifact store.
- No application code is changed during feature planning.

## Testing expectations and gates

Agent tests use dataclass scan-evidence fixtures only. They monkeypatch socket/subprocess entry
points to fail if 047 causes I/O. Golden cases cover a Samsung television,
Tuya/home-automation endpoint mislabeled by port registry, Amazon device without enough product
evidence, trusted versus randomized MAC, Modbus/OT identity, ordinary computer, contradictory OS
and manufacturer, unknown listener, cleartext management, duplicate merged ports,
secret-like banners, and accepted partial evidence. A TUI integration test runs with transport
disabled/unconfigured and proves profile/exposure rendering makes no backend call.

Backend tests run against the existing local test database and assert SQL constraints as well as
Pydantic validation. Reads must prove organization isolation through `scans.org_id`; direct
exposure ID guessing cannot cross an organization because no standalone endpoint exists. The
migration test also asserts RLS and lack of `anon`/`authenticated` privileges when those roles
exist. No live Supabase change is part of test execution.

Frontend API types come only from `components['schemas'][...]`. Data continues through TanStack
Query, not an effect or a new HTTP client. Presentation must never reuse `SeverityWord`, CVSS copy,
or finding totals for attention. Interactive details use the shared `Disclosure` primitive.

Required gates:

```bash
# hardware-agent/
uv run pytest
uv run ruff check src tests

# backend/
uv run ruff check src tests
uv run pytest

# frontend/
npm run gen:types
git diff --exit-code -- src/types/openapi.d.ts   # after committing/regenerating the expected type change
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
```

The generated-type cleanliness check means a second `npm run gen:types` produces no diff; it does
not forbid the intentional generated type change in the feature commit. Never run a repository-wide
formatter. Before acceptance, validate `contracts/examples/scan_result.example.json` against both
agent and backend ingest schemas and audit all call sites listed above.
