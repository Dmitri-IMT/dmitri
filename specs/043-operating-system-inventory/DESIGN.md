# DESIGN — Operating-system inventory in scan results

Textual TUI specification for presenting probabilistic operating-system evidence on each host.
This design changes the full scan result only; it does not add a new screen or alter navigation.

## Screen flow

`ScanViewScreen` remains the single place where an operator reads per-host details. It can be
reached through all three existing paths:

1. `ScanProgressScreen` completes (or retains a partial result) → **View scan** / **View partial
   scan** → `ScanViewScreen(payload=...)`.
2. `HomeScreen` → **View scan** or **View full scan** → `ScanViewScreen(payload=...)`.
3. `HomeScreen` → **Past scans** → select a saved result →
   `ScanViewScreen(scan_path=...)`.

The operating-system block is rendered identically regardless of entry path. Pressing `Esc`
dismisses `ScanViewScreen` and returns to the previous screen, as it does today.

`HomeScreen`, `PastScansScreen`, and `ScanProgressScreen` keep their current summaries. They do
not repeat operating-system information because they do not show host-level inventory.

## Visual mockups

### Host with a full detection

```text
┌─ Dmitri (v0.1.4) ───────────────────────────────────────────────────────────┐
│ ── Scan Results ─────────────────────────────────────────────────────────── │
│ Target:   192.168.0.0/24                                                   │
│ Date:     2026-09-08 14:30:00 UTC                                          │
│ Mode:     NSPi · Inventory                                                  │
│                                                                            │
│ ── Devices (1) ──────────────────────────────────────────────────────────── │
│                                                                            │
│ ▶ 192.168.0.10 (plc-01.local) — Schneider Electric                         │
│   Operating system:                                                        │
│     Detected: Linux 5.10 - 5.15 (98% confidence)                            │
│     Vendor: Linux                                                          │
│     Family: Linux                                                          │
│     Generation: 5.X                                                        │
│     Device type: specialized                                               │
│     Platform IDs:                                                          │
│       - cpe:/o:linux:linux_kernel:5                                         │
│   Ports:                                                                   │
│     502/tcp  open     modbus                                                │
│   Industrial inventory:                                                    │
│     Modbus TCP 502 - CONFIRMED                                              │
│                                                                            │
│ ── Summary ──────────────────────────────────────────────────────────────── │
│ Total devices:          1                                                   │
│ Total open ports:       1                                                   │
│ Vulnerabilities found:  0                                                   │
│                                                                            │
│ Esc Back                                                                   │
└────────────────────────────────────────────────────────────────────────────┘
                              #scan-view-scroll
                              #scan-view-content
```

The operating-system block appears immediately after the host identity and before ports. This
keeps identity evidence together and makes the detected name visible before the longer service,
industrial-inventory, and vulnerability sections. Optional structured attributes are vertically
aligned and platform identifiers are one item per line so long values remain readable when the
`VerticalScroll` content wraps. There is no focusable control in this screen; keyboard focus and
scroll behavior remain Textual's existing `VerticalScroll` behavior.

### Host without a detection, including a legacy result

```text
┌─ Dmitri (v0.1.4) ───────────────────────────────────────────────────────────┐
│ ── Scan Results ─────────────────────────────────────────────────────────── │
│ Target:   192.168.0.0/24                                                   │
│ Date:     2026-09-08 14:30:00 UTC                                          │
│ Mode:     Quick                                                            │
│                                                                            │
│ ── Devices (1) ──────────────────────────────────────────────────────────── │
│                                                                            │
│ ▶ 192.168.0.20 (printer.local) — HP                                         │
│   Operating system: Not detected                                           │
│   Ports:                                                                   │
│     80/tcp   open     http       HP Embedded Web Server                    │
│                                                                            │
│ ── Summary ──────────────────────────────────────────────────────────────── │
│ Total devices:          1                                                   │
│ Total open ports:       1                                                   │
│ Vulnerabilities found:  0                                                   │
│                                                                            │
│ Esc Back                                                                   │
└────────────────────────────────────────────────────────────────────────────┘
                              #scan-view-scroll
                              #scan-view-content
```

An absent detection is communicated explicitly and neutrally. The same presentation applies
when a current scan has no supported evidence and when an older result omits the optional
operating-system object. No placeholder structured attributes and no invented `unknown` values
are shown.

### Result file cannot be loaded

```text
┌─ Dmitri (v0.1.4) ───────────────────────────────────────────────────────────┐
│                                                                            │
│ Failed to load scan results.                                               │
│                                                                            │
│ Esc Back                                                                   │
└────────────────────────────────────────────────────────────────────────────┘
                              #scan-view-scroll
                              #scan-view-content
```

This existing error state remains unchanged. No host or operating-system block is rendered when
the result itself cannot be validated.

## Layout

Within the existing `#scan-view-scroll`, `#scan-view-content` continues to render one textual
document in this order:

1. Scan heading and metadata.
2. Devices heading.
3. For each host:
   1. IP address, hostname, and vendor.
   2. Operating-system detection block.
   3. Ports.
   4. IO-Link banner, when applicable.
   5. Industrial inventory, when applicable.
   6. Vulnerabilities, when applicable.
4. Existing summary.
5. Existing footer bindings supplied by `DmitriScreen`.

The block is always present exactly once per host. Only the name and confidence line is required
for a supported detection; optional detail lines are omitted individually when absent. Existing
host spacing and the vertical scrollbar handle mixed results and long lists without a new panel,
table, modal, or expansion interaction.

## Key bindings

| Key | Action |
|-----|--------|
| `Esc` | Dismiss `ScanViewScreen` and return to the previous screen |
| Mouse wheel / terminal scroll input | Scroll the existing `#scan-view-scroll` content |

No new binding is introduced.

## Copy

The following strings are exact and final:

| Situation | Copy |
|-----------|------|
| Section label with detection | `Operating system:` |
| Required detection line | `Detected: {name} ({confidence}% confidence)` |
| Optional vendor | `Vendor: {vendor}` |
| Optional family | `Family: {family}` |
| Optional generation | `Generation: {generation}` |
| Optional device type | `Device type: {device_type}` |
| One or more identifiers heading | `Platform IDs:` |
| Each platform identifier | `- {platform_id}` |
| No supported evidence | `Operating system: Not detected` |
| Invalid/unreadable result | `Failed to load scan results.` |

`Detected` and `% confidence` are mandatory language: the TUI must not shorten the result to an
unqualified operating-system name. Values are displayed verbatim from the normalized contract;
the TUI does not translate, infer, title-case, or replace missing values.

## States

| State | Behavior |
|-------|----------|
| Full detection | Show `Detected: {name} ({confidence}% confidence)`, followed by every available structured attribute in the fixed order vendor, family, generation, device type, platform IDs. |
| Minimal detection | Show the required detected name and confidence; omit all absent optional detail lines and do not leave blank labels. |
| Multiple platform identifiers | Show `Platform IDs:` once and render each identifier on its own indented `- {platform_id}` line, preserving contract order. |
| No detection | Show only `Operating system: Not detected` for that host. |
| Legacy result | An omitted optional operating-system object validates and renders exactly like **No detection**. |
| Mixed hosts | Render each host independently; a supported detection on one host never supplies or suppresses the state of another. |
| Partial scan | Render the evidence actually present in the partial payload; hosts without evidence show **No detection**. Do not imply the absence was caused by the interruption. |
| Empty scan | Keep the existing `Devices (0)` and summary. There is no host-level operating-system message because there are no hosts. |
| Loading | Loading remains synchronous and initially blank, as today; do not add a spinner for this small local parse. |
| Invalid or unreadable result | Replace the whole document with `Failed to load scan results.` and retain `Esc` recovery. |

## Widget IDs

No new widgets are required.

- `#scan-view-scroll` — existing vertical scroll region containing the complete result.
- `#scan-view-content` — existing `Static` whose rendered text includes every per-host
  operating-system block; tests query this widget or exercise `_render_payload`.

The structured lines are content, not controls, so they intentionally do not receive individual
widget IDs.

## Files and naming

| Area | Exact path | Required change |
|------|------------|-----------------|
| TUI result renderer | `hardware-agent/src/agent/tui/screens/scan_view.py` | Render one operating-system block per host in the specified order and copy. |
| TUI unit tests | `hardware-agent/tests/unit/test_tui_scan_view.py` | Cover full, minimal, multiple-platform, absent, legacy, mixed-host, and partial-result rendering; verify optional labels are omitted rather than fabricated. |
| TUI flow integration tests | `hardware-agent/tests/integration/test_tui_flows.py` | Verify both a freshly completed payload and a saved past scan reach `ScanViewScreen` with the detected name and confidence visible in `#scan-view-content`. |

No stylesheet change is needed because the feature reuses the existing scrollable `Static` and
its indentation conventions. No React frontend file or generated frontend API type is part of
this design.

## Acceptance checks

- Given a host with full supported evidence, the rendered result contains its detected name,
  confidence, and every supplied structured attribute under that same host.
- Given only name and confidence, the rendered result contains the required detection line and
  none of the optional labels.
- Given more than one host, detections and absence messages remain associated with the correct
  host sections.
- Given no detection or a legacy payload that omits the object, the host renders exactly
  `Operating system: Not detected` and still shows its remaining inventory.
- Given entry from scan completion or past scans, the same operating-system presentation is
  visible in `#scan-view-content`.
- Given a partial scan payload, available evidence is displayed without changing the existing
  partial-result navigation or status copy.

## Out of scope (v1)

- Filtering, sorting, grouping, risk scoring, or vulnerability matching by operating system.
- A separate host-detail screen, collapsible operating-system panel, confidence color scale, or
  confidence threshold warning.
- Adding operating-system counts to progress, home, past-scan rows, or the scan summary.
- Displaying raw fingerprints or lower-ranked candidates.
- Any React web frontend or generated frontend API type change.
