# DESIGN — Attack surface and device profiles

The Textual TUI and React application share the stored category meanings defined here while using
independent data paths. The TUI reads only the in-memory or locally saved `ScanPayload`; it has no
backend connection. React reads only the backend API. Neither surface reclassifies a machine.

## Design decisions

- `ScanViewScreen` becomes a scan summary with a selectable device list. It no longer prints every
  device's full record into one long `Static`.
- Selecting a device pushes a new `DeviceDetailScreen`. Escape returns to the scan summary; it does
  not leave the saved-scan or completed-scan flow.
- The visual hierarchy is always **Inventory → Attack surface → Vulnerability findings**. Exposure
  attention is rendered in cyan with the literal prefix `ATTENTION`; vulnerability severity keeps
  its current severity colours and bracketed labels. Exposure attention never uses `LOW`,
  `MEDIUM`, `HIGH`, or `CRITICAL` by itself.
- Profile confidence is neutral prose (`Profile confidence: Medium`), not a coloured risk badge.
- Missing legacy enrichment is `Unavailable`, not `0`, `None`, `Unknown`, or a clean result.
- A partial-result warning stays visible in both summary and device detail. Every count is qualified
  as accepted evidence only.
- No filter, sort, search, edit, remediation, or profile-correction controls are added in v1.

## Screen flow

```text
HomeScreen ── completed scan / View full scan ──┐
                                                ├─> ScanViewScreen
PastScansScreen ── Enter on saved scan ─────────┘         │
                                                         │ Enter
                                                         v
                                               DeviceDetailScreen
                                                         │ Escape
                                                         └─> ScanViewScreen
```

- Existing entry points and `ScanViewScreen(scan_path=..., payload=...)` remain valid.
- `ScanViewScreen` loads and validates the payload exactly once, renders its summary, and populates
  the device list. Enter or an `OptionSelected` event pushes `DeviceDetailScreen(payload, host)`.
- Escape from `ScanViewScreen` preserves the existing `dismiss(None)` behaviour.
- Escape from `DeviceDetailScreen` uses `dismiss(None)` and reveals the same selected row in the
  underlying `ScanViewScreen`.
- Fresh and saved scans use the same two renderers. There is no separate legacy screen.
- Opening either form of local result performs no HTTP request and does not depend on backend
  availability or ingest completion.

## Visual language

| Meaning | Required rendering |
|---------|--------------------|
| Raw inventory | Plain text; section label `Inventory` |
| Exposure | Cyan `◇` and `[ATTENTION: {label}]`; section label `Attack surface` |
| Vulnerability | Existing severity colour and `[CRITICAL|HIGH|MEDIUM|LOW]`; section label `Vulnerability findings` |
| Profile confidence | Plain sentence, e.g. `Profile confidence: Medium` |
| Conflicting evidence | Yellow `⚠`, with the observed signals named |
| Finished with incomplete coverage | Yellow `⚠ INCOMPLETE EVIDENCE` banner |
| Interrupted scan | Red `■ STOPPED SCAN` banner |
| Legacy unavailable data | Dim `Unavailable — this scan predates ...` copy |

The exposure attention label is always namespaced by `ATTENTION`. Even if the data contract uses a
word also used by severity, the UI must render `ATTENTION: …` and the cyan diamond, never a
severity-coloured vulnerability badge.

Role labels are exact in both readers: `administration` → `Administration`, `api` → `API`,
`data_store` → `Data store`, `file_sharing` → `File sharing`, `remote_access` → `Remote access`,
`proxy` → `Proxy`, `device_control` → `Device control`, `discovery` → `Discovery`, `media` →
`Media`, `general_service` → `General service`, and `unknown` → `Unknown`.

## Scan summary — `ScanViewScreen`

### Layout

Top to bottom inside `Vertical` `#scan-view-container`:

1. `Static` `#scan-result-header`: title and scan metadata.
2. `Static` `#scan-partial-banner`: hidden unless `metadata.partial_result is True`.
3. `Static` `#scan-category-summary`: three separately labelled category rows.
4. `Static` `#scan-enrichment-note`: hidden for current scans; shown for legacy enrichment.
5. `Static` `#scan-devices-title`: `Devices ({count})`.
6. `OptionList` `#scan-device-list`: one option per host, in payload order.
7. `Static` `#scan-devices-empty`: hidden when hosts exist.

The existing `#scan-view-scroll` remains the outer scroll region. `#scan-view-content` is retired;
tests move to the semantic ids above. When devices exist, `#scan-device-list` receives focus on
mount. With no devices, the list is hidden and nothing in the body is focusable.

### Summary row copy

```text
Inventory:               {device_count} devices · {open_endpoint_count} open endpoints
Attack surface:          {exposure_count} exposures · {review_count} need attention
Vulnerability findings: {finding_count}
```

- Counts use singular grammar at `1`: `1 device`, `1 open endpoint`, `1 exposure`, `1 needs
  attention`, `1 finding`.
- `review_count` counts exposures whose attention is exactly `review` or `priority`. It is never
  added to `finding_count` and is not broken down under vulnerability severity.
- For a legacy payload where exposure/profile fields are absent, render:

```text
Inventory:               {device_count} devices · {open_endpoint_count} open endpoints
Attack surface:          Unavailable
Vulnerability findings: {finding_count}
```

The device option prompt is:

```text
{ip} · {machine_type_label} · confidence {confidence} · {exposure_count} exposures · {finding_count} findings
```

Singular grammar applies. `machine_type_label` presents the exact PR-143 machine type vocabulary:
`Router`, `Computer`, `Camera`, `Storage`, `TV`, `Phone`, `Printer`, `Sensor`, or `Unknown`.
More specific descriptions such as `home automation` or `voice assistant` belong to the separate
product-family field and never become another type value.
For unknown current profiles use `Unknown · confidence low`. For legacy hosts use:

```text
{ip} · Profile unavailable · exposures unavailable · {finding_count} findings
```

### State A — exposures present, no vulnerability findings

```text
┌──────────────────────────── Dmitri (v…) ────────────────────────────┐
│ Scan results                                      #scan-result-header│
│ Target: 192.168.0.0/24 · 2026-09-13 13:21:45 UTC · Standard        │
│ Duration: 3m 34s                                                     │
│                                                                      │
│ Inventory:               9 devices · 22 open endpoints               │
│ Attack surface:          22 exposures · 6 need attention             │
│ Vulnerability findings: 0                         #scan-category-summary│
│                                                                      │
│ Devices (9)                                      #scan-devices-title │
│ > 192.168.0.1 · Router · confidence high · 4 exposures…             │
│   192.168.0.6 · Sensor · confidence medium · 1 exposure…            │
│   192.168.0.12 · TV · confidence high · 7 exposures…                │
│                                                   #scan-device-list  │
│                                                                      │
│ ↑↓ Navigate   Enter Device details   Esc Back                        │
└──────────────────────────────────────────────────────────────────────┘
```

The zero finding count is factual but is not accompanied by `Safe`, `Clean`, a checkmark, or green
success copy. The attack surface remains the middle, independently counted category.

### State B — vulnerability findings plus exposures

```text
│ Inventory:               9 devices · 22 open endpoints               │
│ Attack surface:          22 exposures · 6 need attention             │
│ Vulnerability findings: 3                         #scan-category-summary│
│                                                                      │
│ Devices (9)                                                         │
│ > 192.168.0.15 · Computer · confidence high · 6 exposures · 2 findings│
│   192.168.0.12 · TV · confidence high · 7 exposures · 1 finding     │
```

Exposure and finding totals remain separate even when both refer to the same endpoint.

### State C — legacy data unavailable

```text
│ Inventory:               9 devices · 22 open endpoints               │
│ Attack surface:          Unavailable                                 │
│ Vulnerability findings: 0                         #scan-category-summary│
│                                                                      │
│ Unavailable — this scan predates attack-surface analysis and device  │
│ profiling. Re-run the scan to produce this data. #scan-enrichment-note│
│                                                                      │
│ > 192.168.0.12 · Profile unavailable · exposures unavailable · 0 findings│
```

Legacy absence is detected from the contract's missing/unavailable enrichment marker, never by
testing whether a current exposure list happens to be empty.

### State D — finished with incomplete coverage

```text
│ ⚠ INCOMPLETE EVIDENCE — The scan finished, but some checks did not    │
│ complete. Counts use accepted evidence only.                          │
│                                                #scan-partial-banner   │
│ Inventory:               7 devices · 14 open endpoints               │
│ Attack surface:          14 exposures · 4 need attention             │
│ Vulnerability findings: 1                                             │
│                                                                      │
│ > 192.168.0.12 · TV · confidence medium · 5 exposures · 0 findings │
```

For `terminated_by="user_cancel"`, `"timeout"`, or `"error"`, the same banner region instead
renders `■ STOPPED SCAN — {stage} did not finish. Counts use accepted evidence only.` Stage names
use the complete mapping defined below; when absent, use `The scan did not finish`.

## Device detail — `DeviceDetailScreen`

### Layout

`DeviceDetailScreen` is read-only. A `VerticalScroll` `#device-detail-scroll` contains:

1. `Static` `#device-detail-header`: `{ip} · {hostname}` and observed MAC vendor when available.
2. `Static` `#device-partial-banner`: same partial qualification, hidden for complete scans.
3. `Static` `#device-profile`: inferred machine type, manufacturer/product assessment, confidence,
   concise evidence, limitations, and conflicts.
4. `Static` `#device-inventory`: original open endpoint and OS observations.
5. `Static` `#device-exposures`: one block per exposure.
6. `Static` `#device-findings`: one block per vulnerability finding.
7. Existing industrial inventory output, when present, in `Static` `#device-industrial`.

All observations are rendered from normalized stored data; presentation does not reclassify,
re-score, or call the network. Evidence list order is the stored deterministic order. Sections
with current but empty collections stay visible with explicit empty copy.

### State A — exposures present, no findings

```text
┌──────────────────────────── Dmitri (v…) ────────────────────────────┐
│ 192.168.0.12 · living-room-tv              #device-detail-header    │
│ Observed MAC vendor: Samsung                                          │
│                                                                      │
│ Profile                                           #device-profile    │
│ Machine type: TV                                                     │
│ Manufacturer: Samsung                                                │
│ Product/model: Smart TV family; exact model unknown                  │
│ Profile confidence: High                                             │
│ Based on: Samsung MAC vendor; TV hostname; Samsung HTTP response     │
│                                                                      │
│ Inventory                                         #device-inventory  │
│ Open endpoints: 7000/tcp, 7443/tcp, 8001/tcp, 8002/tcp, 8008/tcp…  │
│ Operating system: Not detected                                       │
│                                                                      │
│ Attack surface                                    #device-exposures  │
│ ◇ [ATTENTION: REVIEW] 8001/tcp · Device control                     │
│   Observed service: http                                             │
│   Why it matters: A device-control endpoint is reachable.            │
│   Evidence: open TCP endpoint; Samsung HTTP response                 │
│                                                                      │
│ Vulnerability findings                             #device-findings  │
│ No confirmed vulnerabilities found for this device.                  │
│                                                                      │
│ Esc Back                                                             │
└──────────────────────────────────────────────────────────────────────┘
```

`No confirmed vulnerabilities…` applies only to the findings section and must never be promoted
to a whole-device `safe` statement.

### State B — the same endpoint has an exposure and a finding

```text
│ Attack surface                                                        │
│ ◇ [ATTENTION: REVIEW] 22/tcp · Remote access                         │
│   Observed service: ssh · OpenSSH 8.9                                 │
│   Why it matters: A remote-access service is reachable.               │
│   Evidence: open TCP endpoint; SSH handshake                          │
│   Related finding: CVE-2023-12345 (see Vulnerability findings)        │
│                                                                      │
│ Vulnerability findings                                                │
│ [HIGH] CVE-2023-12345 — Weak SSH key exchange (CVSS 8.5)             │
│   Endpoint: 22/tcp · also listed in Attack surface                    │
```

The relationship is derived only from matching stored device/protocol/port references. It does
not merge the records or change either count.

### State C — unknown and conflicting IoT identity

```text
│ 192.168.0.6 · unknown                           #device-detail-header │
│ Observed MAC vendor: Tuya Smart                                    │
│                                                                      │
│ Profile                                                              │
│ Machine type: Unknown                                                │
│ Manufacturer: Tuya Smart (manufacturer assessment only)              │
│ Product/model: Unknown — available evidence does not support a model │
│ Profile confidence: Low                                              │
│ ⚠ Conflicting evidence: 6668/tcp has registry label “irc”, while the │
│   manufacturer and protocol evidence indicate device control.        │
│ Limitation: no reliable hostname, OS, certificate, or product banner │
│                                                                      │
│ Inventory                                                            │
│ 6668/tcp open · observed label: irc                                  │
│                                                                      │
│ Attack surface                                                       │
│ ◇ [ATTENTION: REVIEW] 6668/tcp · Device control                      │
│   Observed service: irc (registry label only; low confidence)         │
│   Why it matters: An unidentified control-like listener is reachable.│
```

The observed registry label remains visible, but the UI never rewrites it as confirmed IRC and
never invents a Tuya product. If no machine type is supported, `Unknown` is the result—not `IoT`.

### State D — legacy data unavailable

```text
│ Profile                                                              │
│ Unavailable — this scan predates device profiling. Re-run the scan to │
│ produce this data.                                                    │
│                                                                      │
│ Inventory                                                            │
│ 8001/tcp open · http                                                  │
│                                                                      │
│ Attack surface                                                       │
│ Unavailable — this scan predates attack-surface analysis.             │
│                                                                      │
│ Vulnerability findings                                               │
│ No confirmed vulnerabilities found for this device.                  │
```

Raw inventory and historical findings still render. The TUI does not reconstruct exposure or
profile information from old ports at view time.

### State E — finished with incomplete coverage

```text
│ ⚠ INCOMPLETE EVIDENCE — The scan finished, but some checks did not    │
│ complete. This device shows accepted evidence only.                  │
│                                                #device-partial-banner │
│                                                                      │
│ Profile                                                              │
│ Machine type: TV                                                     │
│ Profile confidence: Medium                                           │
│ Limitation: deep-inspection evidence may be missing.                  │
│                                                                      │
│ Attack surface                                                       │
│ ◇ [ATTENTION: REVIEW] 8001/tcp · Device control                      │
│                                                                      │
│ Vulnerability findings                                               │
│ No confirmed vulnerabilities in accepted evidence.                   │
```

For partial scans, empty findings copy is always `No confirmed vulnerabilities in accepted
evidence.` It must not use the complete-scan sentence.

## Keyboard behaviour

| Screen | Key | Action | Footer copy |
|--------|-----|--------|-------------|
| Scan summary | `↑` / `↓` | Move device selection | `↑↓ Navigate` |
| Scan summary | `j` / `k` | Move device selection; hidden binding | — |
| Scan summary | `Enter` | Push selected `DeviceDetailScreen` | `Enter Device details` |
| Scan summary | `Escape` | Dismiss to caller | `Esc Back` |
| Device detail | `Escape` | Dismiss to the same scan summary and selection | `Esc Back` |

Enter is inert when no device is selected. Device detail has no focusable widget; arrow keys and
Page Up/Page Down retain Textual's native `VerticalScroll` behaviour.

## Copy rules

- Screen titles: `Scan results`, `{ip} · {hostname}`.
- Category titles: `Inventory`, `Attack surface`, `Vulnerability findings`.
- Exposure lines: `◇ [ATTENTION: {label}] {port}/{protocol} · {role}`.
- Exposure detail labels: `Observed service:`, `Why it matters:`, `Evidence:`, optional
  `Related finding:`.
- Profile labels: `Machine type:`, `Manufacturer:`, `Product/model:`, `Profile confidence:`, `Based on:`,
  optional `⚠ Conflicting evidence:`, optional `Limitation:`.
- A current unknown value is `Unknown`; a field absent because of an old schema is `Unavailable`.
- Complete/current empty findings: `No confirmed vulnerabilities found for this device.`
- Partial empty findings: `No confirmed vulnerabilities in accepted evidence.`
- Current empty exposures: `No confirmed open endpoints for this device.` This is valid only when
  the current exposure collection exists and is empty.
- Never use `secure`, `safe`, `clean`, `risk-free`, or `no issues` for an empty finding set.

## Widget ids

| Widget | ID | Status |
|--------|----|--------|
| Summary outer scroll | `#scan-view-scroll` | reused |
| Summary container | `#scan-view-container` | new |
| Summary metadata | `#scan-result-header` | new |
| Summary partial warning | `#scan-partial-banner` | new |
| Category counts | `#scan-category-summary` | new |
| Legacy note | `#scan-enrichment-note` | new |
| Device-list heading | `#scan-devices-title` | new |
| Device options | `#scan-device-list` | new |
| Empty-device copy | `#scan-devices-empty` | new |
| Detail outer scroll | `#device-detail-scroll` | new |
| Detail header | `#device-detail-header` | new |
| Detail partial warning | `#device-partial-banner` | new |
| Profile section | `#device-profile` | new |
| Inventory section | `#device-inventory` | new |
| Exposure section | `#device-exposures` | new |
| Finding section | `#device-findings` | new |
| Industrial section | `#device-industrial` | new |

## Files and naming

| Status | Path | Required change |
|--------|------|-----------------|
| Touch | `hardware-agent/src/agent/tui/screens/scan_view.py` | Convert the full dump into summary/category counts and device navigation while retaining payload/file loading. |
| New | `hardware-agent/src/agent/tui/screens/device_detail.py` | Define `DeviceDetailScreen` and the read-only profile/inventory/exposure/finding renderers. |
| Touch | `hardware-agent/src/agent/tui/screens/home.py` | Add `Attack surface: {N} exposures · {R} need attention` to the fresh-scan summary band without altering its navigation. |
| Touch | `hardware-agent/src/agent/tui/app.tcss` | Layout for the summary list, partial/legacy notes, and detail sections; exposure styles stay distinct from severity styles. |
| Touch | `hardware-agent/tests/unit/test_tui_scan_view.py` | Replace monolithic-render assertions with category, legacy, partial, row-copy, and navigation assertions. |
| New | `hardware-agent/tests/unit/test_tui_device_detail.py` | Cover profile evidence/conflicts, exposure/finding separation, endpoint cross-reference, legacy, partial, and current-empty copy. |
| Touch | `hardware-agent/tests/integration/test_tui_flows.py` | Verify fresh and saved scan → summary → device detail → summary flows and stable widget ids. |

No new shared widget is warranted in v1. Rendering helpers stay private to the screen modules until
a second local screen needs them.

## Test expectations

- A current scan with open endpoints and zero findings displays a nonzero exposure total and an
  exact zero finding total; no safe/clean wording is present.
- Exposure attention never changes vulnerability totals or severity breakdowns, and its rendered
  markup contains `ATTENTION` plus the cyan diamond rather than a severity badge.
- A finding and exposure on the same IP/protocol/port render in separate sections with reciprocal
  cross-reference copy and count once in their own totals.
- Manufacturer, service, hostname, OS, banner/certificate/protocol evidence render in stored order;
  conflicts and limitations are visible and the original port/service observation remains intact.
- Unknown profiles do not gain a product/model or generic `IoT` class. Randomized-address
  limitations render without a manufacturer inference.
- Missing legacy fields produce `Unavailable` in summary and detail while raw inventory and old
  findings remain readable. A current empty exposure list produces `0`, proving legacy and empty
  are not conflated.
- Partial metadata reveals both coverage banners, uses accepted-evidence copy, and never renders the
  complete-scan empty-findings sentence.
- A zero-host current scan hides `#scan-device-list`, shows `No devices were discovered.` in
  `#scan-devices-empty`, and remains a valid complete scan unless partial metadata says otherwise.
- Pilot tests exercise arrow and `j`/`k` movement, Enter push, Escape return with selection
  preserved, and Escape from the summary to its caller.
- Existing OS and industrial-inventory assertions move to `DeviceDetailScreen`; no normalized
  evidence disappears in the redesign.

---

## Web application — React

This section extends the design to the inside-shell web routes `/scans/:scanId` and
`/network/:hostId`. It does not change or supply data to the TUI design above. Owner-facing copy uses
**Vulnerability** rather than the API term *finding*, and **machine** rather than *device*, as
required by `docs/ui/FOUNDATIONS.md`. Attack-surface attention is plain text, never a severity
badge or colour: `informational` → `For awareness`, `review` → `Needs review`, and `priority` →
`Priority review`. Confidence is `Unknown`, `Low`, `Medium`, or `High` in neutral prose.

### Shared presentation rules

- Data comes only from generated `components['schemas'][...]` aliases through the existing
  `getScan` and `getHost` functions and TanStack Query v5. No handwritten API types, extra fetch,
  effect, exposure endpoint, or client-side reclassification is introduced.
- The order on both details is **Profile/inventory → Attack surface → Vulnerabilities**. A current
  zero is different from `assessment_status="unavailable"`; only the latter says `Unavailable`.
- `AttentionWord` owns the three attention labels. It does not import `SeverityWord`, mention
  CVSS, add a badge, or contribute to `finding_count`.
- Exposure rows use the existing shared `DataTable` expansion. The trigger has an accessible name
  `Show details for {service} on {endpoint}`, `aria-expanded`, `aria-controls`, Enter/Space toggle,
  and Escape close/focus return. The panel shows `Why it matters`, `Evidence`, and, when present,
  `Related vulnerabilities`. Scan-detail relationship controls open the already-loaded finding in
  place; host-detail links go to `/scans/{scan_id}?finding={finding_id}`. No extra request is made.
- `HostProfile` uses the shared `Disclosure` labelled `Why this profile?` for stored evidence,
  conflicts, and limitations. Conflict text begins `Conflicting evidence:`; the warning icon is
  decorative. Unknown is a valid visible result and no generic IoT label is substituted.
- All sections are white `Card`s on the canvas, separated by `gap-8`; the page keeps
  `max-w-frame`. Tables scroll inside their own container. Only named type/spacing/colour tokens
  are used. No new route, filter, sort, edit, remediation, or profile-correction control ships.

### Scan detail — `/scans/:scanId`

Component hierarchy:

```text
ScanDetail
├─ ReadDetailGate
├─ ScanDetailHeader
├─ ScanSummaryStrip (Mode · Network · Machines · Attack surface · Vulnerabilities · Duration)
├─ incomplete/stopped notice (only metadata.partial_result === true)
├─ Card "Machines seen" → ScanHostsTable
├─ Card "Attack surface" → ExposureTable → DataTable → exposure detail panel
└─ Card(s) "Vulnerabilities" → existing FindingsTable/FindingPanel
```

`ExposureTable` receives `scan.exposures`, `scan.findings`, and the existing
`setOpenFindingId`. Columns are `Endpoint · Observed service · Role · Attention · Confidence`.
Endpoint is `{ip}:{port}/{protocol}` in mono. Roles use sentence-case labels from the stored enum;
the UI never infers a role from the port. The summary's attack-surface value is
`{N} reachable service(s) · {R} need(s) review`, where `R` counts `review` plus `priority`.

#### Completed: exposures and zero vulnerabilities

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ← Back                                                                       │
│ Scan · today 10:21                                                           │
│ Standard · 192.168.0.0/24 · 9 machines · 22 reachable services · 0 vulns    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Machines seen                                                               │
│ living-room-tv       192.168.0.12       Samsung                7 services    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Attack surface                                                              │
│ Endpoint              Observed service   Role             Attention          │
│ 192.168.0.12:8001/tcp  http               Device control   Needs review  ▸   │
│ 192.168.0.15:5432/tcp  postgresql         Data store       Needs review  ▸   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Vulnerabilities                                                             │
│ No confirmed vulnerabilities were found in this scan.                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

The zero sentence is scoped to vulnerabilities; it never says safe, clean, or no issues.

#### Completed: exposures and vulnerabilities

```text
│ Standard · 9 machines · 22 reachable services · 3 vulnerabilities           │
│ Attack surface                                                              │
│ 192.168.0.15:22/tcp  ssh  Remote access  Needs review  High             ▾   │
│   Why it matters  A remote-access service is reachable.                     │
│   Evidence        SSH handshake · OpenSSH 8.9                               │
│   Related vulnerability  CVE-2023-12345  [Open vulnerability]               │
│ Vulnerabilities                                                             │
│ High                                                                         │
│ Weak SSH key exchange · 192.168.0.15 · 22/tcp · CVE-2023-12345             │
```

Opening `Open vulnerability` expands and focuses that existing finding row. Exposure and finding
remain separate rows and each is counted once in its own category.

#### Legacy enrichment unavailable

```text
│ Quick · 9 machines · Attack surface unavailable · 0 vulnerabilities         │
│ Machines seen                                                               │
│ …raw historical inventory remains readable…                                 │
│ Attack surface                                                              │
│ Unavailable — this scan predates attack-surface analysis.                    │
│ Re-run the scan to produce this data.                                        │
│ Vulnerabilities                                                             │
│ No confirmed vulnerabilities were found in this scan.                       │
```

This branch is selected only by `assessment_status="unavailable"`, never by an empty exposure
array.

#### Finished with incomplete coverage

```text
│ INCOMPLETE EVIDENCE                                                          │
│ The scan finished, but some checks did not complete. Counts below use       │
│ accepted evidence only; missing coverage is not a clean result.              │
│ Standard · 7 machines · 14 reachable services · 1 vulnerability             │
│ …Machines seen, Attack surface, and Vulnerabilities from accepted evidence… │
```

This branch requires `metadata.partial_result=true` with `terminated_by="completed"`, matching
`ScanProgressScreen`'s yellow `FINISHED` terminal. For an actually interrupted result
(`terminated_by` is `user_cancel`, `timeout`, or `error`), render the red `STOPPED SCAN` banner and
name the unfinished stage. The stage mapping is `discovery` → `Host discovery`, `ports` → `Port
scanning`, `deep_inspection` → `Deep inspection`, `ot_inspection` → `Industrial inspection`,
`targeted_assessment` → `Targeted service assessment`, and `normalize` → `Results generation`;
absent/unrecognised is `The scan did not finish.` Empty partial vulnerability copy is `No
confirmed vulnerabilities in accepted evidence.` Both banners are textually labelled and use
`role="status"`; colour is not their only signal.

#### Loading, empty, and error

```text
Loading                         Current empty                    Error
Scan                            Attack surface                   Scan
[summary skeleton]              No reachable services were      Couldn't load this scan.
[three table skeleton rows]     found in this scan.              [Retry]
                                Machines seen
                                No machines were discovered.
```

Loading uses existing skeleton styling and does not announce zeroes. A current empty assessment
requires `assessment_status="available"`. Existing failed/unfinished scan states stay authoritative
and suppress enrichment tables until accepted result data is available. Existing 404 and retry
behaviour remains unchanged.

### Host detail — `/network/:hostId`

Component hierarchy:

```text
HostDetail
├─ ReadDetailGate
├─ HostIdentity (unchanged raw identity and seen dates)
├─ Card "Machine profile" → HostProfile → Disclosure "Why this profile?"
├─ Card "Attack surface" → HostExposures → ExposureTable
├─ Card "Vulnerabilities" → existing HostFindings
├─ Card "Services running on this machine" → existing HostPortsTable
└─ Card "Scan history" → existing HostScanHistoryTable
```

#### Confident profile

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ← Back                                                                       │
│ living-room-tv                                                               │
│ 192.168.0.12 · 84:25:19:AA:BB:CC · observed vendor Samsung                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Machine profile                                                             │
│ Likely type       TV                                                        │
│ Manufacturer      Samsung                                                    │
│ Product family    Smart TV                                                   │
│ Model             Unknown                                                    │
│ Profile confidence High                                                      │
│ ▸ Why this profile?                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Attack surface · 7 reachable services · 3 need review                       │
│ 8001/tcp  http  Device control  Needs review  High                       ▸   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Vulnerabilities                                                             │
│ No confirmed vulnerabilities were found on this machine.                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

`Manufacturer` is the assessed value; `observed vendor` in the header remains the original scan
observation. Null product family/model render `Unknown`, not a guessed product.

#### Unknown or conflicting profile

```text
│ Machine profile                                                             │
│ Likely type        Unknown                                                   │
│ Manufacturer       Tuya Smart                                                │
│ Product family     Unknown                                                   │
│ Model              Unknown                                                   │
│ Profile confidence Low                                                       │
│ ▾ Why this profile?                                                         │
│   Conflicting evidence: 6668/tcp is labelled “irc”, while manufacturer and  │
│   protocol evidence indicate device control.                                │
│   Limitation: No reliable hostname, OS, certificate, or product banner.     │
│ Attack surface                                                               │
│ 6668/tcp  irc (observed)  Device control  Needs review  Low              ▸   │
```

The registry label stays explicitly observed; it is not presented as confirmed IRC. A randomized
MAC renders `Limitation: Locally administered MAC address; OUI manufacturer unavailable.` and an
unknown manufacturer.

#### Legacy, current empty, loading, and error

```text
Legacy                          Current empty                    Error
Machine profile                 Attack surface                   Machine
Unavailable — this scan         No reachable services were      Couldn't load this machine.
predates device profiling.      found on this machine.          [Retry]
Attack surface                  Vulnerabilities
Unavailable — this scan         No confirmed vulnerabilities
predates attack-surface         were found on this machine.
analysis.
```

For legacy host detail, raw services, historical vulnerabilities, and scan history still render.
During the host-detail load, retain the page heading and show section skeletons without empty copy.
The independently fetched vulnerability section keeps its existing local loading/error state:
`Couldn't load this machine's vulnerabilities.` with `Retry`; profile, attack surface, services,
and history remain visible.

### Exact test IDs

| Element | Test ID |
|---|---|
| Scan category summary | `scan-assessment-summary` |
| Scan partial notice | `scan-partial-notice` |
| Scan legacy note | `scan-assessment-unavailable` |
| Scan exposure table | `scan-exposures-table` |
| Exposure row | `scan-exposures-table-row-{exposure_id}` |
| Exposure panel | `scan-exposures-table-panel-{exposure_id}` |
| Related vulnerability control | `exposure-related-finding-{finding_id}` |
| Scan current-empty exposure copy | `scan-no-exposures` |
| Host profile card | `host-profile` |
| Profile disclosure | `host-profile-evidence` |
| Profile conflicts | `host-profile-conflicts` |
| Profile limitations | `host-profile-limitations` |
| Host legacy profile copy | `host-profile-unavailable` |
| Host exposure table | `host-exposures-table` |
| Host current-empty exposure copy | `host-no-exposures` |
| Host legacy exposure copy | `host-exposures-unavailable` |

Tests should prefer roles, accessible names, and visible copy; IDs identify repeated data rows and
state boundaries only.

### Web files and tests

| Status | Path | Required change |
|---|---|---|
| Generated | `frontend/src/types/openapi.d.ts` | Regenerate from canonical OpenAPI; never edit by hand. |
| New | `frontend/src/components/AttentionWord.tsx` | Render the exact non-severity attention labels. |
| New | `frontend/src/components/AttentionWord.test.tsx` | Assert all labels and absence of severity/CVSS semantics. |
| New | `frontend/src/pages/scans/ExposureTable.tsx` | Shared scan/host exposure table, expansion, evidence, and related-finding controls. |
| New | `frontend/src/pages/scans/exposureColumns.tsx` | Generated-type-backed columns and stored-enum presentation labels. |
| Touch | `frontend/src/pages/ScanDetail.tsx` | Compose category summary, partial/legacy states, exposures, vulnerabilities, and inventory. |
| Touch | `frontend/src/pages/ScanDetail.test.tsx` | Cover zero/findings, cross-reference, available-empty, partial, unavailable, loading, error, and 404. |
| New | `frontend/src/pages/hosts/HostProfile.tsx` | Present assessment, evidence disclosure, conflicts, limitations, and unavailable state. |
| New | `frontend/src/pages/hosts/HostExposures.tsx` | Present latest exposures and related scan links, including empty/unavailable states. |
| Touch | `frontend/src/pages/HostDetail.tsx` | Compose profile → attack surface → vulnerabilities → raw inventory/history. |
| Touch | `frontend/src/pages/HostDetail.test.tsx` | Cover confident, unknown, conflicting, randomized-MAC, empty, unavailable, loading/error, and relationship navigation. |
| Touch | `frontend/src/test/scansHarness.ts` | Add generated-contract available, unavailable, partial, and related-finding fixtures. |
| Touch | `frontend/src/test/hostsHarness.ts` | Add confident, unknown/conflicting, randomized-MAC, empty, and unavailable fixtures. |

Required assertions: exposure totals never change vulnerability counts; `assessment_status` (not
array length) separates current-empty from legacy; partial copy always qualifies accepted evidence;
stored evidence order is preserved; attention never renders through `SeverityWord`; relationship
navigation makes the referenced finding visible; unknown profiles never gain a model or generic
IoT class; no loading/error state renders a false zero. Finish with generated-type cleanliness and
the frontend lint, format-check, typecheck, test, and build gates from `ARCHITECTURE.md`.
