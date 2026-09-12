# DESIGN — OT agent hardening (terminal interface)

Scope: the Textual screens only. Binding authority is
[`TRUTH.md`](TRUTH.md); evidence is [`AUDIT.md`](AUDIT.md). Conventions follow
[`specs/042-nspi-modbus-ot/DESIGN.md`](../042-nspi-modbus-ot/DESIGN.md).

No new screen is added. Three existing screens change:

| Screen | File | Change |
|---|---|---|
| `ScanViewScreen` (S7) | `hardware-agent/src/agent/tui/screens/scan_view.py` | Device text shown literally and bounded; address ranges show status and a keyed digest, never process values. |
| `ScanProgressScreen` (S4) | `hardware-agent/src/agent/tui/screens/scan_progress.py` | Finished-with-incomplete-evidence split from stopped-early; stage time-ceiling line; refused-depth terminal state. |
| `ScanModeScreen` (S3) | `hardware-agent/src/agent/tui/screens/scan_mode.py` | No visual change. Kept as-is deliberately; see §6. |

Screen flow is unchanged: `home → network → category → mode → progress → view`,
side path `home → past scans → view`. `ScanProgressScreen` still dismisses
`(payload, view_requested)`; `ScanViewScreen` still dismisses `None`.

**Key bindings: nothing changes.** S7 keeps `escape` → Back. S4 keeps `ctrl+x`
Abort and the terminal `escape` / `↑↓` / `enter` set. The new refused state
enables the same terminal bindings as the existing fatal state
(`_enable_terminal_bindings(navigate=False)`): `escape` back, no arrow
navigation, because only one button is shown.

---

## 1. Untrusted device text in the scan view

### 1.1 The rule

`scan_view.py` builds one markup string and hands it to
`Static("#scan-view-content")`, which renders it with Rich markup enabled
(`:67`, `:77`). Every value below is supplied, in whole or in part, by the
scanned device, so each one can contain `[`, `]`, an unbalanced closing tag, an
ANSI escape, or a newline:

| Value | Source |
|---|---|
| `host.hostname`, `host.vendor` | reverse DNS / OUI lookup |
| `port.service`, `port.version` | nmap banner text |
| `operating_system.name` / `.vendor` / `.family` / `.generation` / `.device_type` / `.cpes[]` | nmap OS match strings |
| `service.mapping_source` | local profile name |
| `unit.status`, `unit.error` | decoder output, device-derived |
| `device_identification.vendor_name` / `.product_code` / `.product_name` / `.major_minor_revision` / `.model_name` / `.user_application_name` | FC43 |
| `device_identification.objects` keys and values | FC43 extras |
| `address_range.label` | mapping profile, may be device-selected |

Three rules apply to all of them, at the single point where a device value
enters the rendered string:

1. **Markup inert.** Rich markup in a device value is never interpreted. The
   value is displayed literally: a vendor string `Acme [/b] Ltd` appears on
   screen as `Acme [/b] Ltd`, and the screen does not raise `MarkupError`.
2. **Bounded length.** Each value is truncated for display at the limit in the
   table below. Truncation appends `…` (U+2026) and is counted.
3. **No layout escape.** Any character below `U+0020`, plus `U+007F` and any
   ANSI escape introducer, is replaced by `·` (U+00B7) before display, so a
   device cannot inject a line break, a tab, or a colour sequence into the
   layout.

Display limits (characters, counted after control-character replacement, before
the `…` is appended):

| Value | Limit |
|---|---|
| Identification strings (`vendor_name`, `product_code`, `product_name`, `major_minor_revision`, `model_name`, `user_application_name`) | 48 |
| `objects` key | 24 |
| `objects` value | 48 |
| `address_range.label` | 48 |
| `unit.error` | 80 |
| `port.version`, `port.service` | 64 |
| `hostname`, `vendor`, operating-system strings, `cpes[]` | 64 |
| `mapping_source` | 32 |

Count limits:

| Collection | Shown | Overflow copy |
|---|---|---|
| `objects` entries per unit | first 8, sorted by key | `        … 3 more identification objects not shown` |
| `cpes` per host | first 8 | `      … 2 more platform IDs not shown` |

These are **display** bounds. The parse-time bounds that TRUTH.md requires on
stored values belong to `ARCHITECTURE.md`; the screen applies its own bound
regardless, because a payload from an older agent may already hold a long
string.

### 1.2 New widget

One Static is added above the content, between the scroll container's top and
the rendered body, shown only when at least one value was shortened:

```
#scan-view-notice   Static, display=False by default
```

Exact copy, chosen by the number of shortened values (`N`):

- `N == 1`: `⚠ Device-supplied text is shown literally. 1 value was shortened to fit its display limit.`
- `N > 1`: `⚠ Device-supplied text is shown literally. 4 values were shortened to fit their display limits.`

A second Static carries the process-value rule and is shown only when the
payload contains at least one industrial service with at least one address
range:

```
#scan-view-process-note   Static, display=False by default
```

Exact copy:

`Process values are never shown. Address ranges report status and a keyed change digest only.`

### 1.3 Mockup — benign device text

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                             Dmitri (v0.1.4)                                  │  DmitriHeader
├──────────────────────────────────────────────────────────────────────────────┤
│ ── Scan Results ──────────────────────────────                               │  #scan-view-scroll
│ Target:   192.168.10.0/24                                                    │   └ #scan-view-content
│ Date:     2026-09-12 14:20:12 UTC                                            │
│ Mode:     NSPi · Read-only mapping                                           │
│ Duration: 4m 12s                                                             │
│                                                                              │
│ ── Devices (1) ──────────────────────────────                                │
│                                                                              │
│ ▶ 192.168.10.30 (plc-cell-1) — Schneider Electric                            │
│   Operating system: Not detected                                             │
│   Ports:                                                                     │
│     502/tcp  open     modbus                                                 │
│   Industrial inventory:                                                      │
│     Modbus TCP 502 - CONFIRMED                                               │
│       Mapping plan: generic_baseline                                         │
│       Unit ID 1: responding; vendor Schneider Electric, product BMX P34,     │
│                  firmware 2.60                                               │
│         holding_register 0-15: readable · digest a1b2c3d4                    │
│         coil 0-3: illegal_address · exception 2                              │
│         input_register 0-3: timeout                                          │
│                                                                              │
│ Process values are never shown. Address ranges report status and a keyed     │  #scan-view-process-note
│ change digest only.                                                          │
│ ── Summary ──────────────────────────────────                                │
│ Total devices:          1                                                    │
│ Total open ports:       1                                                    │
│ Vulnerabilities found:  0                                                    │
│ Modbus services:        1                                                    │
│ Modbus Unit IDs:        1                                                    │
│ Modbus mapped ranges:   3                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back                                                                     │  Footer
└──────────────────────────────────────────────────────────────────────────────┘
```

What changed from today: the range lines. Today they read
`holding_register 0-15: readable · nonzero 3 · min 0 · max 1450`
(`scan_view.py:185-206`). `nonzero_count`, `value_min` and `value_max` are
statistics over process values, which TRUTH.md classifies as process data and
forbids in operator-facing output. They are gone. Focus starts on
`#scan-view-scroll`, as today. `#scan-view-notice` is not mounted visibly here
because nothing was shortened.

Range line grammar, exactly:

```
        <address_space> <start>-<end>: <status>[ · exception <code>][ · digest <8 hex>]
```

- `· exception <code>` appears only when `exception_code` is not null.
- `· digest <8 hex>` appears only when the range carries a digest; the value is
  the first 8 characters of the hex after stripping the `hmac-sha256:` prefix,
  lowercase.
- When `status == "readable"` and no digest is stored:
  `        holding_register 0-15: readable · digest not recorded`.
- No other suffix is ever emitted. A range that produced nothing readable shows
  its status alone — never a zero, which would imply a value was read.

### 1.4 Mockup — hostile device text

A PLC reporting
`vendor_name = "Acme [/b][red]PWN[31m Industrie GmbH & Co. Kommanditgesellschaft"`,
`product_code = "M[bold]340"`, a 300-character `user_application_name`, and 11
`objects` entries:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                             Dmitri (v0.1.4)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ⚠ Device-supplied text is shown literally. 3 values were shortened to fit    │  #scan-view-notice
│ their display limits.                                                        │
│ ── Scan Results ──────────────────────────────                               │  #scan-view-content
│ Target:   192.168.10.0/24                                                    │
│ Date:     2026-09-12 14:20:12 UTC                                            │
│ Mode:     NSPi · Inventory                                                   │
│                                                                              │
│ ── Devices (1) ──────────────────────────────                                │
│                                                                              │
│ ▶ 192.168.10.30 (plc-cell-1) — Acme [/b][red]PWN· Industrie GmbH & Co. Komm… │
│   Operating system: Not detected                                             │
│   Ports:                                                                     │
│     502/tcp  open     modbus                                                 │
│   Industrial inventory:                                                      │
│     Modbus TCP 502 - CONFIRMED                                               │
│       Unit ID 1: responding; vendor Acme [/b][red]PWN· Industrie GmbH & Co.… │
│                  product M[bold]340, application Prozessdatenerfassung und…  │
│         Identification extras:                                               │
│           0x00 = Acme [/b][red]PWN· Industrie GmbH & Co. Kommanditgesellsc…  │
│           0x01 = M[bold]340                                                  │
│           0x02 = 2.60                                                        │
│           0x03 = http://example.invalid/[/link]                              │
│           0x04 = M340 CPU                                                    │
│           0x05 = Prozessdatenerfassung                                       │
│           0x06 = ·······                                                     │
│           0x80 = cell-1                                                      │
│           … 3 more identification objects not shown                          │
│       Unit ID 2: error; decode failed: frame shorter than declared length    │
│                                                                              │
│ ── Summary ──────────────────────────────────                                │
│ Total devices:          1                                                    │
│ Total open ports:       1                                                    │
│ Vulnerabilities found:  0                                                    │
│ Modbus services:        1                                                    │
│ Modbus Unit IDs:        2                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

Reading the mockup: `[/b]`, `[red]` and `[bold]` appear on screen as typed —
that is the whole point of the state. The ANSI `ESC[31m` became `·`. The
300-character application name and the two longest identification strings were
cut at their limits with `…`, and `#scan-view-notice` reports that three values
were shortened, which is how the acceptance criterion "the limit applied is
evident" is met on screen. `objects` shows eight entries and one overflow line.
Unit 2 failed to decode; it is listed with its `error` text (itself escaped and
bounded at 80 characters) and the other unit's evidence is intact — a single bad
unit does not remove the host, the service, or its sibling.

The screen does **not** raise. That is the assertion: opening S7 on this payload
renders and the operator can still press `Esc`.

### 1.5 Mockup — load error (unchanged, recorded for completeness)

```text
├──────────────────────────────────────────────────────────────────────────────┤
│ Failed to load scan results.                                                 │  #scan-view-content
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

Existing copy (`scan_view.py:73`) and existing behaviour. Kept exactly.

### 1.6 Test anchors — S7

| Selector | Assertion |
|---|---|
| `#scan-view-content` | renders without raising for a payload whose identification strings contain `[/b]`, `[red]`, `ESC[31m`, `\n` |
| `#scan-view-content` | contains the literal substring `[/b]` |
| `#scan-view-content` | contains no `nonzero `, no `min `, no `max ` token on a range line |
| `#scan-view-content` | contains `· digest a1b2c3d4` for a range with that digest |
| `#scan-view-content` | contains `… 3 more identification objects not shown` |
| `#scan-view-notice` | `.display is True` and text equals the `N > 1` string when values were shortened; `.display is False` otherwise |
| `#scan-view-process-note` | `.display is True` when any range exists; `False` for a non-NSPi payload |

---

## 2. Finished with incomplete evidence, versus stopped early

### 2.1 The distinction

`scan_progress.py:440-468` has one partial state. It reads
`metadata["terminated_by"]` for the reason and
`metadata["interrupted_stage"]` for the stage, defaulting the stage to
`"an earlier stage"` when it is absent. Under ADR-010 §3 a run that reached its
end with skipped hosts is `terminated_by="completed"`, `partial_result=True`,
`interrupted_stage=None` — so today's screen would label a finished scan
"interrupted during an earlier stage". The screen must therefore branch on
`terminated_by`, not only on `partial_result`.

Outcome table — the complete mapping the screen implements:

| `terminated_by` | `partial_result` | State | Badge class | Badge text |
|---|---|---|---|---|
| `completed` | `False` | `completed` | — (badge hidden) | — |
| `completed` | `True` | `incomplete` | `badge-incomplete` | ` FINISHED ` + `some hosts incomplete; all evidence kept` |
| `timeout` | any | `stopped` | `badge-stopped` | ` STOPPED ` + `a step timed out; partial results kept` |
| `error` | any | `stopped` | `badge-stopped` | ` STOPPED ` + `scan stopped early; partial results kept` |
| `user_cancel` | any | `stopped` | `badge-stopped` | ` STOPPED ` + `stopped by you; partial results kept` |
| anything else / absent | `True` | `stopped` | `badge-stopped` | ` STOPPED ` + `partial results kept` |

`#scan-badge` carries exactly one of the classes `badge-incomplete`,
`badge-stopped`, `badge-failed`, `badge-refused`, `badge-cancelling`, so a test
selects a state without parsing the rendered string. The existing cancelling and
fatal badges keep their current copy and gain `badge-cancelling` /
`badge-failed`.

`FINISHED` renders black on yellow, as the current partial badge does.
`STOPPED` renders white on red. Three signals differ at a glance: the word, the
colour, and the log glyph (`⚠` versus `✗`).

Button labels follow the state, because "partial" is wrong for a scan that
finished:

| State | `#btn-view-scan` label | `#btn-back-home` | Initial focus |
|---|---|---|---|
| `completed` | `View scan` | shown | `#btn-view-scan` |
| `incomplete` | `View scan` | shown | `#btn-view-scan` |
| `stopped` | `View partial scan` | shown | `#btn-view-scan` |
| `fatal` | hidden | shown | `#btn-back-home` |
| `refused` | hidden | shown | `#btn-back-home` |

A stage is named only when `interrupted_stage` is set. When it is absent, the
stage clause is omitted entirely — the screen never writes "an earlier stage",
because naming a stage the scan did not stop in is the defect ADR-010 forbids.

### 2.2 Mockup — finished, some hosts incomplete

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                             Dmitri (v0.1.4)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Mode: NSPi · Inventory · 192.168.10.0/24                                     │  #scan-header
│  FINISHED  some hosts incomplete; all evidence kept                          │  #scan-badge .badge-incomplete
│ ████████████████████████████████████████████████████████████████████  100%   │  #progress-bar
│ ✓ 14 hosts found                                                             │  #activity-log
│ ⚠ 37 open ports found (2 of 14 hosts skipped)                                │
│ ⚠ 12 of 14 hosts scanned (2 skipped)                                         │
│ OK 3 Modbus hosts inventoried                                                │
│ ⚠ Finished with incomplete evidence — 14 devices, 3 vulnerabilities          │
│   (2 of 14 hosts incomplete)                                                 │
│                                                                              │
│                            ┌─────────────────┐                               │  #scan-done-actions
│                            │   View scan     │  ← focus                      │  #btn-view-scan
│                            └─────────────────┘                               │
│                            ┌─────────────────┐                               │
│                            │  Back to Home   │                               │  #btn-back-home
│                            └─────────────────┘                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back   ↑↓ Navigate   Enter Select                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

The bar reaches 100% — the scan finished. The badge says `FINISHED`, in the
warning colour, and no stage is named. The closing log line is, exactly:

`⚠ Finished with incomplete evidence — {devices} devices, {findings} vulnerabilities ({skipped} of {total} hosts incomplete)`

The host counts come from `metadata["hosts_skipped"]` and
`metadata["hosts_total"]` when present. When they are not, the parenthetical is
omitted and the line ends after the vulnerability count. The view button says
`View scan`, not `View partial scan`: the operator has a complete run with
incomplete evidence on some hosts, and the difference is the message.

Zero-host edge case: today `_handle_partial` dismisses silently when
`payload.hosts` is empty (`scan_progress.py:441-443`). That behaviour is kept
**only** for the `stopped` state. A `completed`-with-`partial_result` run and no
hosts shows this screen with `✓ Done — 0 devices, 0 vulnerabilities` in the log
and the `FINISHED` badge. Silently returning home from a run that finished would
hide the outcome.

### 2.3 Mockup — stopped early

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                             Dmitri (v0.1.4)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Mode: NSPi · Inventory · 192.168.10.0/24                                     │  #scan-header
│  STOPPED  scan stopped early; partial results kept                           │  #scan-badge .badge-stopped
│ ████████████████████████████████████▏                                 52%    │  #progress-bar
│ ✓ 14 hosts found                                                             │  #activity-log
│ ⚠ 37 open ports found (9 of 14 hosts skipped)                                │
│ ✗ more than half of the hosts failed; scan stopped early                     │
│ ✗ Stopped during port scanning — 5 devices, 0 vulnerabilities                │
│   (partial results kept)                                                     │
│                                                                              │
│                            ┌─────────────────────┐                           │  #scan-done-actions
│                            │  View partial scan  │  ← focus                  │  #btn-view-scan
│                            └─────────────────────┘                           │
│                            ┌─────────────────────┐                           │
│                            │    Back to Home     │                           │  #btn-back-home
│                            └─────────────────────┘                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back   ↑↓ Navigate   Enter Select                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

The bar stops where the scan stopped — it is never forced to 100%. Closing log
line, exactly:

- with a stage: `✗ Stopped during {stage} — {devices} devices, {findings} vulnerabilities (partial results kept)`
- without a stage: `✗ Stopped — {devices} devices, {findings} vulnerabilities (partial results kept)`

`{stage}` uses the existing `_INTERRUPTED_STAGE_LABELS` map
(`scan_progress.py:38-45`), unchanged, with one entry added for the new time
ceiling (§3). An `interrupted_stage` value not in that map omits the stage
clause rather than printing the raw key.

### 2.4 Mockup — fatal (unchanged, recorded for contrast)

```text
│ Mode: Standard · 192.168.10.0/24                                             │
│ ✗ SCAN FAILED — nothing to keep                                              │  #scan-badge .badge-failed
│ ███████▏                                                              11%    │
│ ✗ nmap is not installed                                                      │
│                            ┌─────────────────┐                               │
│                            │  Back to Home   │  ← focus                      │  #btn-back-home
│                            └─────────────────┘                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

Existing copy and behaviour (`scan_progress.py:470-479`). It gains only the
`badge-failed` class. Three terminal words now exist and none of them overlap:
`FINISHED`, `STOPPED`, `SCAN FAILED`.

---

## 3. A stage that stopped at its time ceiling

TRUTH.md requires every active stage to have a reachable wall-clock ceiling, and
requires the stage to report the reason and keep the evidence gathered so far.
The operator therefore needs two things: a live line at the moment the ceiling is
hit, and a durable record when they open the result later.

### 3.1 Live line

The screen needs one new progress event. `ARCHITECTURE.md` owns the producer;
this design states the contract the screen consumes:

```
ScanEvent(kind="ot_stage_deadline", message=<reason>, units_skipped=..., units_total=...)
```

The existing `_INTERRUPTED_STAGE_LABELS` key `ot_inspection` already maps to
`Modbus inventory`. Do not add `ot_mapping`. The seconds that fired come from
scan metadata `modbus_stage_deadline_seconds` (or from the event message). They
are `MAX_OT_HOST_SECONDS` or `MAX_OT_STAGE_SECONDS`, whichever bound hit.

On receiving it, the screen replaces the active spinner line for that stage —
the same `_finish_stage` path the success lines use — with, exactly:

`⏱ Time limit reached during Modbus inventory ({limit_seconds}s) — evidence gathered so far is kept`

Rendered in yellow. The stage is then no longer active, so its spinner stops.
The scan continues into normalisation. The ceiling ends the OT stage, not the
run. The run's terminal badge follows §2.1 from `partial_result` (port/deep
skipped hosts only). An OT-only time stop does not flip `partial_result` and
does not use `badge-incomplete` by itself.

### 3.2 Mockup — mapping stopped on time

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                             Dmitri (v0.1.4)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Mode: NSPi · Read-only mapping · 192.168.10.0/24                             │  #scan-header
│                                                                              │  #scan-badge hidden (no port/deep skip)
│ ████████████████████████████████████████████████████████████████████  100%   │  #progress-bar
│ ✓ 6 hosts found                                                              │  #activity-log
│ ✓ 9 open ports found                                                         │
│ ✓ 6 hosts scanned                                                            │
│   -> Mapped 192.168.10.30 (1/3)                                              │
│   -> Mapped 192.168.10.31 (2/3)                                              │
│ ⏱ Time limit reached during Modbus inventory (90s) — evidence gathered so far │
│   is kept                                                                    │
│ ✓ Done — 6 devices, 1 vulnerabilities                                        │
│                                                                              │
│                            ┌─────────────────┐                               │
│                            │   View scan     │  ← focus                      │  #btn-view-scan
│                            └─────────────────┘                               │
│                            ┌─────────────────┐                               │
│                            │  Back to Home   │                               │  #btn-back-home
│                            └─────────────────┘                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back   ↑↓ Navigate   Enter Select                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

Two of three Modbus hosts were mapped; the third was not reached before the
ceiling. The `⏱` line names the stage, the limit, and says the evidence is kept.
The bar still reaches 100%. If no port or deep host was skipped, the incomplete
badge stays hidden: a bound doing its job is not partial evidence. The `⏱` line
carries the reason.

### 3.3 Durable record in the scan view

A time ceiling that is only in the live log is lost as soon as the operator
leaves the progress screen. When metadata `modbus_stage_deadline_reached` is
true, the results screen renders one line under `Duration:`, using
`modbus_stage_deadline_seconds`:

```text
│ Mode:     NSPi · Read-only mapping                                           │
│ Duration: 3m 07s                                                             │
│ Limits:   Time limit reached during Modbus inventory (90s)                   │
```

When the flag is absent or false the line is omitted.

### 3.4 Test anchors — time ceiling

| Selector | Assertion |
|---|---|
| `#activity-log` | after an `ot_stage_deadline` event with a 90s host bound, contains `Time limit reached during Modbus inventory (90s)` |
| `#scan-badge` | has no `badge-incomplete` class for a run that hit the OT ceiling and skipped no port/deep hosts |
| `#scan-view-content` | contains `Limits:   Time limit reached during Modbus inventory (90s)` when `modbus_stage_deadline_reached` is true; contains no `Limits:` line when it is not |

---

## 4. A refused scan depth

TRUTH.md: "The component that performs a scan validates the scan depth it was
asked for. A safety decision is not left to the caller." `ScanRunner` is
constructed directly by `ScanProgressScreen` (`scan_progress.py:147`), so once
`ScanRunner` validates, the TUI is a call site that can be refused. The refusal
must be legible on screen, and must make clear that nothing was sent.

### 4.1 Behaviour

`_start_scan` may fail before any probe. When construction or `start()` raises
the depth-refusal error, the screen enters a new terminal state `refused`:

- Progress bar stays at 0%. No stage line is written.
- `#scan-badge` shows, with class `badge-refused`:
  `⛔ SCAN REFUSED — no request was sent`
- A new Static `#scan-refusal-detail` (`display=False` by default) shows the
  reason and the remedy, two lines.
- `#btn-view-scan` is hidden; `#btn-back-home` is shown and focused.
- Terminal bindings: `escape` back only (`navigate=False`), matching fatal.
- `dismiss((None, False))` on either `escape` or `Back to Home`. No payload
  exists, so `home` writes nothing.

`#scan-refusal-detail` copy, by refused depth:

| Refused value | Line 1 | Line 2 |
|---|---|---|
| `active_validation` | `NSPi active validation is not available in this version.` | `No host was contacted. Choose Inventory or Read-only mapping and start again.` |
| any other unpermitted value | `The requested NSPi mode is not permitted: {value}` | `No host was contacted. Choose Inventory or Read-only mapping and start again.` |

`{value}` is a device-independent internal value, but it is still escaped and
truncated at 32 characters by the §1.1 rule, so a refusal can never itself break
the screen. The screen selects the copy from the refused value, not from the
exception's message text; the exception message is not printed.

### 4.2 Mockup — refused depth

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                             Dmitri (v0.1.4)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Mode: NSPi · Active validation · 192.168.10.0/24                             │  #scan-header
│ ⛔ SCAN REFUSED — no request was sent                                         │  #scan-badge .badge-refused
│ NSPi active validation is not available in this version.                     │  #scan-refusal-detail
│ No host was contacted. Choose Inventory or Read-only mapping and start again. │
│                                                                       0%     │  #progress-bar
│                                                                              │  #activity-log (empty)
│                                                                              │
│                            ┌─────────────────┐                               │  #scan-done-actions
│                            │  Back to Home   │  ← focus                      │  #btn-back-home
│                            └─────────────────┘                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Esc Back                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

The header still states the mode the operator asked for, so the refusal is
attached to a request they recognise. The empty activity log and the 0% bar are
the visual proof that nothing ran; the detail line states it in words. There is
no `View scan` button, because there is no result — and no silent downgrade to
`inventory`, which would run a scan the operator did not choose and label it
with a depth that was refused.

### 4.3 Test anchors — refusal

| Selector | Assertion |
|---|---|
| `#scan-badge` | has class `badge-refused`, renders `⛔ SCAN REFUSED — no request was sent` |
| `#scan-refusal-detail` | `.display is True`, first line equals the table's line 1 for the refused value |
| `#btn-view-scan` | `.display is False` |
| `#btn-back-home` | `.has_focus is True` |
| `#progress-bar` | progress is 0 |
| `#activity-log` | `len(log.lines) == 0` |
| screen dismiss result | `(None, False)` |

---

## 5. Process values are never shown

Recorded against the current code so the implementer has the full list.

Today's operator-facing output in `scan_view.py:185-206` prints
`nonzero_count`, `value_min` and `value_max` for every range. `AUDIT.md`
finding 15 also records that `mapper.py:319-320` reports `0` for an empty value
list, so the screen can currently print `min 0 · max 0` for a range that
produced nothing — a value implying data was read, which TRUTH.md forbids twice
over (process statistics in operator output, and a summary of absent data
implying presence).

The screen therefore renders, for every range, only:

1. `address_space`, `start_address`-`end` — addresses are not values;
2. `status` — the literal contract value (`readable`, `illegal_address`,
   `illegal_function`, `timeout`, `error`, `skipped`);
3. `exception <code>` when an exception code exists — a protocol rejection code,
   not process data;
4. `digest <8 hex>` when a digest exists, else `digest not recorded` for a
   readable range.

And never: `values`, `nonzero_count`, `value_min`, `value_max`, or anything
derived from them. `ModbusValidationPayload` fields (`original_value`,
`test_value`, `read_back_value`, `final_value`) are process values too; S7 does
not render `validations` today and must not start. If a payload from a future
build carries them, the screen ignores them.

The `#scan-view-process-note` Static (§1.2) states the rule on screen so the
absence reads as a policy, not as missing data.

The 8-character digest prefix is a display convenience for eyeballing change
between two scans. It is not the change-detection mechanism; comparison is the
product's job, and the digest's keying is `ARCHITECTURE.md`'s.

---

## 6. `ScanModeScreen` — deliberately unchanged

`_NSPI_OPTIONS` already carries
`Option("Active validation  —  Unavailable until guarded restoration ships", id="active_validation", disabled=True)`
(`scan_mode.py:33-37`). The copy is accurate and the option cannot be selected,
so nothing here changes. §4 exists because `disabled=True` is a presentation
guard on one screen, and TRUTH.md requires the refusal to live in the component
that acts. The two are layers, not alternatives: the option stays disabled, and
the refusal state is what the operator sees if the depth arrives by any other
path.

No key binding on S3 changes.

---

## 7. Out of scope, and judgement calls

Out of scope for this design:

- Any presentation of industrial observations in the web interface. TRUTH.md
  assigns it to the feature that owns that screen.
- Any screen for active validation beyond the refusal in §4. The depth does not
  exist in this version.
- Change comparison between two scans. S7 shows a digest prefix; comparing two
  results is not a v1 screen.
- Restructuring S7 into per-host widgets. It stays one `Static` plus the two new
  notice Statics — the finding is markup interpretation, not layout.
- Re-rendering the `#activity-log` for past scans. The `⏱` and `⚠` lines are
  live-only except for the `Limits:` line in §3.3.

Judgement calls, each of which `ARCHITECTURE.md` or a human may overrule:

1. **`FINISHED` as the word for completed-with-partial-evidence.** TRUTH.md
   requires the two outcomes be "reported distinctly" but does not name them.
   `PARTIAL` was rejected: it reads as "incomplete run", which is exactly the
   confusion ADR-010 §3 is about. `FINISHED` + `some hosts incomplete` names the
   run state first and the evidence state second.
2. **`ot_stage_deadline` event.** Settled. New `ScanEventKind` value. No new
   event fields. Seconds live in metadata `modbus_stage_deadline_seconds`.
3. **Durable Limits line.** Settled. Results screen shows it when
   `modbus_stage_deadline_reached` is true. No `stage_time_limits` list.
4. **8-character digest prefix.** Settled. Show 8 hex after stripping
   `hmac-sha256:`. Readable range with no key shows `digest not recorded`.
5. **Display limits (48 / 64 / 80 characters) and the 8-entry `objects` cap.**
   TRUTH.md requires bounds and does not set numbers. These are chosen for an
   80-column terminal. They are display-only and independent of the parse-time
   bounds.
6. **`hosts_skipped` / `hosts_total` in the incomplete-evidence log line.**
   Those metadata keys are not guaranteed present today, so the parenthetical is
   conditional. `AUDIT.md` finding 10 also records that the skipped-host signal
   is unreliable and is not being fixed here — the copy says "hosts incomplete",
   which is true of a skipped host whatever the reason, rather than "hosts timed
   out", which would over-claim.
7. **No screen for the pacing and inbound-listener rules.** TRUTH.md's pacing,
   request-count and no-listener rules have no operator-facing surface; they are
   verified by tests, not shown. Nothing was invented for them.
