# DESIGN — Scan progress screen: contingency & partial outcomes (S4)

Textual TUI spec. Keyboard interaction and copy, not pixels.

Scope: a **delta** on the existing `ScanProgressScreen`
(`hardware-agent/src/agent/tui/screens/scan_progress.py`) as redesigned in spec
`009-scan-progress-redesign`. This feature adds **no new screen**. It adds the screen states and
copy needed to surface scan contingency outcomes from spec 010 (TRUTH.md / report §6):

- degraded-but-running stage lines (skipped / timed-out units), instead of silent success;
- a terminal **Partial** outcome that is badged, viewable, and savable — never dismissed with `None`;
- a **timed-out** indication when a step was killed by the per-step timeout;
- a `_handle_error` that distinguishes a **Fatal** outcome (show error, nothing to keep) from a
  **Partial** outcome (offer "View partial scan");
- a **Cancelling** transition that reflects work actually stopping (subprocesses terminating)
  before the screen resolves to a Partial terminal state — not an instant `dismiss(None)`.

Everything in 009 that this document does not mention stays exactly as 009 specified (header,
spinner, progress bar, activity-log streaming, success state, end-action dismiss contract).

---

## What this changes vs. 009 (summary)

| 009 behaviour | 010 behaviour |
|---------------|---------------|
| Port/deep finish lines always read clean success (`✓ N open ports found`). | Finish lines gain a degraded variant when units were skipped/timed-out (`⚠`-toned, with skip count). |
| `action_abort` while running → `dismiss(None)` immediately; background work keeps running. | `action_abort` → **Cancelling** state; waits for the runner to terminate subprocesses and finalize, then resolves to **Partial** (data exists) or **Aborted/empty dismiss** (no data). |
| `_handle_error` only fires a `notify` toast. | `_handle_error` branches: **Fatal** terminal state (error + nothing to keep) vs **Partial** terminal state (badge + View partial scan). |
| Only one terminal "done" look (success). | Three terminal looks: **Completed**, **Partial**, **Fatal error** (+ the transient **Cancelling**). |
| `#scan-done-actions` always shows `View scan` + `Back to Home`. | Action set + labels vary by terminal outcome (see Copy → End actions). |

---

## Screen flow

- **Entry**: unchanged. Pushed from the scan-mode flow as `ScanProgressScreen(subnet, scan_mode)`;
  starts the `ScanRunner` on mount.
- **No new screens are pushed** by this screen.
- **Dismiss results** — the `(payload, view_flag)` tuple contract is unchanged; what changes is
  which outcomes carry a non-`None` payload:
  - **Completed (success)** — View scan → `dismiss((payload, True))`; Back to Home →
    `dismiss((payload, False))`. (unchanged)
  - **Partial** — View partial scan → `dismiss((payload, True))`; Back to Home →
    `dismiss((payload, False))`. The partial `payload` is a real, finalized `ScanPayload`
    (`metadata["partial_result"] is True`); it is **never** `None` and **never** discarded here.
  - **Fatal error** — Back to Home → `dismiss((None, False))`. Nothing to keep.
  - **Cancelling** — not a terminal state; it transitions into **Partial** (if discovery produced
    data) or, if no data exists yet, into the **Aborted** dismiss (`dismiss(None)`).
- The caller's branch on the tuple is unchanged: `True` pushes `ScanViewScreen`; `False` (or a
  `None` payload) returns Home. A Partial payload opens in `ScanViewScreen` exactly like a full one.

---

## Layout

Top to bottom, inside `compose_body`. Identical to 009 except for **one new widget** (`#scan-badge`)
inserted directly under the header, and the end-actions block gaining a third button id.

1. `DmitriHeader` (from base `compose`).
2. `Vertical` `#progress-container`:
   1. `Static` `#scan-header` — `Mode: {MODE_LABEL} · {subnet}`. (unchanged)
   2. **`Static` `#scan-badge`** — **new**. Hidden (`display=False`) while running and on clean
      success. Shown only in the **Partial** and **Fatal error** terminal states, where it renders
      the outcome badge + one-line reason (see Copy → Outcome badge).
   3. `Horizontal` `#progress-row` → `LoadingIndicator` `#scan-spinner` + `ProgressBar`
      `#progress-bar`. (unchanged)
   4. `RichLog` `#activity-log`. (unchanged; gains the new degraded/timeout/partial line templates
      below)
3. `Vertical` `#scan-done-actions` (hidden until any terminal state):
   1. `Button` `#btn-view-scan` — `variant="primary"`. (reused; label varies by outcome)
   2. `Button` `#btn-back-home`. (reused)
4. `Footer` (from base `compose`).

CSS (add to `app.tcss`, beside the 009 rules):

- `#scan-badge { margin-bottom: 1; text-style: bold; display: none; }`
- No other layout changes; `#scan-done-actions` continues to show/hide whole buttons via
  `display` so a hidden button consumes no vertical space.

---

## Key bindings

The 009 binding table is preserved. Two behavioural changes (same keys, new semantics) and no new
keys:

| Key | Action | Shown | 010 notes |
|-----|--------|-------|-----------|
| ctrl+x | `abort` | yes (priority) | While running → enter **Cancelling** (request cancel, do **not** dismiss yet). In **Cancelling** → ignored (already stopping). In any terminal state → `dismiss((payload, False))` for Completed/Partial, `dismiss((None, False))` for Fatal. |
| escape | `no_op` | hidden while running / cancelling; `Esc Back` after any terminal state | After any terminal state → `dismiss((payload, False))` (Completed/Partial) or `dismiss((None, False))` (Fatal). No-op while running/cancelling. |
| ctrl+t | `no_op` | no | Swallowed. (unchanged) |
| j / k | `focus_next_btn` / `focus_prev_btn` | no | Active only after a terminal state with ≥2 visible buttons; guard becomes "terminal", not just `_done`. |
| up / down | `focus_prev_btn` / `focus_next_btn` | `↑↓ Navigate` after terminal | Same guard. With only one visible button (Fatal), navigation is inert. |
| enter | `press_focused` | `Enter Select` after terminal | Dismisses with the focused button's result. |

The guard that 009 expresses as `if not self._done: return` generalizes to a terminal predicate
covering **Completed | Partial | Fatal**. The transient **Cancelling** state is *not* terminal:
navigation/enter stay inert and only the (now ignored) Ctrl+X is live, so the operator cannot act
on a half-stopped scan.

Footer per state:
- Running: `Ctrl+X Abort`
- Cancelling: `Ctrl+X Abort` (visible but inert; label unchanged to avoid a flicker)
- Completed / Partial: `↑↓ Navigate · Enter Select · Esc Back · Ctrl+X Abort`
- Fatal error: `Esc Back · Ctrl+X Abort` (no `↑↓ Navigate` — single button)

---

## States

| State | `#scan-spinner` | `#progress-bar` | `#scan-badge` | `#activity-log` final line | `#scan-done-actions` |
|-------|-----------------|-----------------|---------------|----------------------------|----------------------|
| **Loading (scanning)** | visible, animating | eases to each `target_pct` | hidden | streaming activity lines | hidden |
| **Idle / long stage** | visible, animating | holds at last real value | hidden | last `●` stage line; per-host/skip lines append | hidden |
| **Cancelling** | visible, animating | holds at last real value (**no 100%**) | hidden | `[yellow]● Stopping scan — terminating running steps…[/yellow]` | hidden |
| **Completed (success)** | hidden | `100%` | hidden | `✓ Done — {devices} devices, {findings} vulnerabilities` | `View scan` (focused) + `Back to Home` |
| **Partial** | hidden | last real value (**no 100%**) | shown: `⚠ PARTIAL — {reason}` | `⚠ Partial — {devices} devices, {findings} vulnerabilities (interrupted during {stage})` | `View partial scan` (focused) + `Back to Home` |
| **Fatal error** | hidden | last real value (**no 100%**) | shown: `✗ SCAN FAILED — nothing to keep` | `✗ Scan failed: {error}` | `Back to Home` only (focused) |

State rules:
- The spinner hides on every terminal state. Only **Completed** sets the bar to 100%; **Partial**,
  **Fatal**, and **Cancelling** leave the bar at its last real value (no fake completion).
- **Partial** and **Fatal** both reveal `#scan-done-actions`; **Partial** keeps both buttons,
  **Fatal** hides `#btn-view-scan` (there is nothing to view) and shows only `#btn-back-home`.
- **Cancelling** is transient and bounded by the runner's cancel/terminate path; the screen does
  not unmount on Ctrl+X. When the runner calls back:
  - with a finalized partial payload (`metadata["partial_result"] is True`) → render **Partial**;
  - with no payload because nothing was discovered yet → `dismiss(None)` (**Aborted**, matches the
    pre-010 cancel-with-no-data outcome).
- **Empty result is not an error**: discovery returning zero hosts finishes as **Completed**
  (success) with `✓ Done — 0 devices, 0 vulnerabilities`; the activity log shows the existing
  `✓ No hosts found` / `No hosts to inspect — skipping scripts` lines. No badge, full success look.

---

## Visual mockups

The chrome (DmitriHeader top, Footer bottom) is drawn once; later mockups elide it for focus.

### (a) Loading — degraded but running (skipped / timed-out units)

```text
┌────────────────────────────── Dmitri ──────────────────────────────┐
│  Mode: MAX · 192.168.1.0/24                          #scan-header     │
│                                                                      │
│  ⠹  [█████████████████████░░░░░░░░░░░░░░░░░░]  62%    #progress-row   │
│                                                                      │
│ ┌─ activity ─────────────────────────────────────────  #activity-log┐│
│ │ ✓ 20 hosts found                                                  ││
│ │ ⚠ 41 open ports found (3 of 20 hosts skipped)                     ││
│ │ ●  Running scripts…                                               ││
│ │   ↳ Scanned 192.168.1.10 (8/20)                                   ││
│ │   ↳ 192.168.1.11 timed out (skipped)                              ││
│ │   ↳ 192.168.1.12 failed (skipped)                                 ││
│ │   ↳ Scanned 192.168.1.13 (11/20)                                  ││
│ └───────────────────────────────────────────────────────────────────┘│
│                                                                      │
│                                          Ctrl+X Abort   (Footer)      │
└──────────────────────────────────────────────────────────────────────┘
```

The scan is still running and the bar still advances. The difference from 009 is that the log no
longer pretends everything succeeded. The port stage finished with a **degraded** finish line
(`⚠`, yellow) that names how many hosts were skipped, and during deep inspection individual units
that timed out or failed are reported inline as dim/yellow `↳` lines and then **skipped** — the
stage keeps going. Focus is nowhere actionable (no buttons yet); the only live key is Ctrl+X. The
spinner keeps animating because work continues despite the skips.

### (b) Terminal — Partial (badged, viewable, savable)

```text
│  Mode: MAX · 192.168.1.0/24                          #scan-header     │
│  ⚠ PARTIAL — a step timed out; partial results kept  #scan-badge      │
│                                                                      │
│     [█████████████████████████░░░░░░░░░░░░░]  71%    #progress-row    │
│                                                                      │
│ ┌─ activity ──────────────────────────────────────────────────────┐ │
│ │ ✓ 20 hosts found                                                 │ │
│ │ ⚠ 41 open ports found (3 of 20 hosts skipped)                    │ │
│ │ ● Running scripts…                                               │ │
│ │   ↳ Scanned 192.168.1.10 (8/20)                                  │ │
│ │   ↳ 192.168.1.11 timed out (skipped)                             │ │
│ │ ⚠ Partial — 12 devices, 7 vulnerabilities (interrupted during    │ │
│ │   deep inspection)                                               │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│   ┌──────────────────────┐  ┌──────────────────┐   #scan-done-actions │
│   │  View partial scan ▸ │  │  Back to Home    │   (#btn-view-scan     │
│   └──────────────────────┘  └──────────────────┘    focused)          │
│                                                                      │
│        ↑↓ Navigate · Enter Select · Esc Back · Ctrl+X Abort           │
└──────────────────────────────────────────────────────────────────────┘
```

A terminal **Partial** outcome. The spinner is gone and the bar holds at its last real value (it
does **not** jump to 100% — the scan did not complete). `#scan-badge` is now visible and reads
`⚠ PARTIAL — {reason}`, where the reason is derived from how the scan ended (cancel / timeout /
late-fatal). The activity log's final line restates the keep-set and which stage was interrupted.
Crucially, `#scan-done-actions` is shown with **both** buttons: `View partial scan` (primary,
focused) dismisses with `(payload, True)` and opens the partial in `ScanViewScreen`; `Back to Home`
dismisses with `(payload, False)`. Either way the finalized partial payload survives — it is never
`None` and never discarded. Focus starts on `#btn-view-scan`; `↑↓`/`j`/`k` move between the two
buttons.

### (c) Terminal — Fatal error (nothing to keep)

```text
│  Mode: MAX · 192.168.1.0/24                          #scan-header     │
│  ✗ SCAN FAILED — nothing to keep                     #scan-badge      │
│                                                                      │
│     [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  6%     #progress-row   │
│                                                                      │
│ ┌─ activity ──────────────────────────────────────────────────────┐ │
│ │ ● Finding hosts…                                                 │ │
│ │ ✗ Scan failed: nmap executable not found on PATH                 │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│                  ┌──────────────────┐               #scan-done-actions │
│                  │  Back to Home    │               (#btn-back-home     │
│                  └──────────────────┘                focused)          │
│                                                                      │
│                       Esc Back · Ctrl+X Abort                         │
└──────────────────────────────────────────────────────────────────────┘
```

A **fatal failure before any data** existed (e.g. nmap missing, bad arguments, permission denied,
workspace not writable). `#scan-badge` reads `✗ SCAN FAILED — nothing to keep`. The activity log's
final line carries the specific error. There is **no** `View` button — `#btn-view-scan` is hidden
because there is no payload to view; only `#btn-back-home` is shown and focused, dismissing with
`(None, False)`. The bar stays at wherever it died (no fake 100%). This replaces the pre-010
behaviour where `_handle_error` fired only a toast and the screen state was ambiguous.

### (d) Transient — Cancelling (between Ctrl+X and finalization)

```text
│  Mode: MAX · 192.168.1.0/24                          #scan-header     │
│                                                                      │
│  ⠼  [█████████████████████░░░░░░░░░░░░░░░░░░]  62%    #progress-row   │
│                                                                      │
│ ┌─ activity ──────────────────────────────────────────────────────┐ │
│ │ ✓ 20 hosts found                                                 │ │
│ │ ⚠ 41 open ports found (3 of 20 hosts skipped)                    │ │
│ │ ● Running scripts…                                               │ │
│ │ ● Stopping scan — terminating running steps…                     │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│                                          Ctrl+X Abort                  │
└──────────────────────────────────────────────────────────────────────┘
```

The operator pressed Ctrl+X. Instead of unmounting immediately, the screen requests cancellation
and shows a transient **Cancelling** state: spinner still animating, bar held, and a new
`● Stopping scan — terminating running steps…` line appended. No buttons appear and a second Ctrl+X
is ignored — the operator cannot act until work has actually halted. When the runner has terminated
in-flight subprocesses and finalized the partial, the screen resolves to **(b) Partial** (if any
host/port data was gathered) or, if nothing had been discovered yet, performs the plain
`dismiss(None)` **Aborted** exit. This is the visible counterpart of TRUTH.md's rule that
cancellation must actually stop work, not merely dismiss the screen.

---

## Copy

Exact, final strings. Mode tokens come from the existing `MODE_LABELS` map. Implementers must not
reword these.

### Header (`#scan-header`) — unchanged

```
Mode: {MODE_LABEL} · {subnet}
```

### Outcome badge (`#scan-badge`)

Hidden except in Partial / Fatal terminal states.

| Outcome | Badge string (RichLog/Static markup) |
|---------|--------------------------------------|
| Partial | `[black on yellow] PARTIAL [/] {reason}` |
| Fatal error | `[bold red]✗ SCAN FAILED — nothing to keep[/bold red]` |

`{reason}` is selected from how the scan ended (read from `payload.metadata`; see Reporter contract):

| End cause (`metadata["terminated_by"]`) | `{reason}` |
|-----------------------------------------|-----------|
| `user_cancel` | `stopped by you; partial results kept` |
| `timeout` | `a step timed out; partial results kept` |
| `error` (post-discovery fatal or circuit breaker) | `scan stopped early; partial results kept` |
| missing / unknown | `partial results kept` |

### Activity-log lines — new / changed templates

Lines from 009 that are unchanged are not repeated. New and degraded variants:

| Trigger | Line (RichLog markup) |
|---------|------------------------|
| Port stage done, **no** skips | `[green]✓[/green] {N} open ports found` (unchanged) |
| Port stage done, **with** skips | `[yellow]⚠[/yellow] {N} open ports found ({S} of {T} hosts skipped)` |
| Deep stage done, **no** skips | `[green]✓[/green] {T} hosts scanned` (unchanged) |
| Deep stage done, **with** skips | `[yellow]⚠[/yellow] {M} of {T} hosts scanned ({S} skipped)` |
| Unit timed out (per host/batch) | `[yellow]  ↳ {ip} timed out (skipped)[/yellow]` |
| Unit failed (per host/batch, non-timeout) | `[yellow]  ↳ {ip} failed (skipped)[/yellow]` |
| Cancelling (transition) | `[yellow]● Stopping scan — terminating running steps…[/yellow]` |
| Terminal: Partial (final line) | `[yellow]⚠ Partial — {devices} devices, {findings} vulnerabilities (interrupted during {stage})[/yellow]` |
| Terminal: Fatal (final line) | `[red]✗ Scan failed: {error}[/red]` (unchanged from 009 failure line) |

Notes:
- `{S}` = skipped units, `{T}` = total units in the stage, `{M}` = units actually scanned
  (`{M} = {T} - {S}`), `{N}` = open ports. The `⚠` finish line replaces the `✓` finish line only
  when `{S} > 0`; otherwise the clean 009 line is used verbatim.
- `{stage}` is the human label of `payload.metadata["interrupted_stage"]`:

  | `interrupted_stage` key | `{stage}` label |
  |-------------------------|-----------------|
  | `discovery` | `host discovery` |
  | `port_scan` | `port scanning` |
  | `deep_inspection` | `deep inspection` |
  | `normalize` | `results generation` |
  | missing | `an earlier stage` |

- `{devices}` / `{findings}` come from the (partial) completion payload — `len(payload.devices)` /
  `len(payload.findings)` — exactly as the success line does, not from `ScanEvent` fields.
- The glyph vocabulary extends 009: `[yellow]⚠[/yellow]` = degraded-but-kept (a stage that finished
  with skips, or a partial outcome); `[red]✗[/red]` = fatal/aborted. `[green]✓[/green]` stays
  reserved for fully-clean milestones.

### End actions (`#scan-done-actions`)

Labels are state-dependent; ids are stable.

| Outcome | `#btn-view-scan` | `#btn-back-home` |
|---------|------------------|------------------|
| Completed (success) | `View scan` (shown, primary, focused) | `Back to Home` (shown) |
| Partial | `View partial scan` (shown, primary, focused) | `Back to Home` (shown) |
| Fatal error | hidden (`display=False`) | `Back to Home` (shown, focused) |

---

## Reporter / payload contract this screen consumes

Screen-side spec only; the producing changes belong to `ARCHITECTURE.md` (010). This screen renders
whatever it receives and degrades to the 009 behaviour when the new fields/events are absent, so it
is forward-safe if the pipeline lands incrementally.

The screen needs, in addition to the 009 event set:

1. **Skip accounting on stage-done events** — `port_stage_done` and the deep-inspection completion
   carry a skipped-unit count and a total (so the screen can compute `{S}` / `{T}` / `{M}`). If the
   count is `0` or absent, the screen emits the clean `✓` finish line.
2. **Per-unit outcome events** — an event identifying a unit (`ip`) that was **skipped** with a
   reason (`timeout` vs `failed`), so the screen can append the `↳ … (skipped)` lines. If absent,
   the stage still finishes; only the per-unit detail is missing.
3. **Partial-aware completion** — the existing `on_complete(payload)` path must be reachable for
   cancel / timeout / post-discovery-fatal finalizations, with `payload.metadata["partial_result"]`
   `True`, `payload.metadata["interrupted_stage"]` set, and (ideally)
   `payload.metadata["terminated_by"]` in `{user_cancel, timeout, error}`. The screen reads these to
   choose **Partial** vs **Completed** and to fill the badge reason / interrupted stage.
4. **Fatal vs partial on the error path** — `on_error` must let the screen tell a fatal-before-data
   failure (no payload → **Fatal error** state) from a finalize-with-partial outcome (payload routed
   through `on_complete` → **Partial** state). Concretely: `_handle_error` renders **Fatal** only
   when there is no kept payload; any keep-able outcome arrives via the completion path.
5. **Real cancellation** — `request_cancel()` must terminate in-flight subprocesses and then call
   back (complete-with-partial or, if no data, a no-payload finalize). The screen stays mounted in
   **Cancelling** until that callback fires; it does not `dismiss(None)` on the Ctrl+X keystroke.

---

## Widget ids

Stable ids for tests. Reused ids keep their 009 names.

| Widget | `#id` | Status |
|--------|-------|--------|
| `Vertical` progress container | `#progress-container` | reused |
| `Static` header line | `#scan-header` | reused |
| `Static` outcome badge | `#scan-badge` | **new** |
| `Horizontal` spinner+bar row | `#progress-row` | reused |
| `LoadingIndicator` spinner | `#scan-spinner` | reused |
| `ProgressBar` | `#progress-bar` | reused |
| `RichLog` activity log | `#activity-log` | reused |
| `Vertical` end actions | `#scan-done-actions` | reused |
| `Button` view (`View scan` / `View partial scan`) | `#btn-view-scan` | reused |
| `Button` back home | `#btn-back-home` | reused |

Tests target outcomes by: `#scan-badge` visibility + text (Partial vs Fatal vs hidden), the
`#btn-view-scan` visibility/label, and the `#activity-log` final line. The bar's non-100% value in
Partial/Fatal is observable via `#progress-bar`.

---

## Naming note — files & constants touched

- **Only file changed:** `hardware-agent/src/agent/tui/screens/scan_progress.py`
  (plus the `#scan-badge` CSS block in `hardware-agent/src/agent/tui/app.tcss`).
- **New widget id:** `#scan-badge` (one `Static`). All other ids are reused from 009.
- **No new screen module**, no new screen class.
- Per CLAUDE.md integration rule: the new contingency config knobs (per-step timeout, scan
  deadline, unit-failure threshold, transient retries) are threaded by `ARCHITECTURE.md` through
  `ScanRunner` and the `ScanProgressScreen._start_scan` call site; this DESIGN does not add new
  constructor parameters to `ScanProgressScreen` beyond what the orchestrator/runner already pass.

---

## Out of scope (v1)

- No new screen, no modal/confirm dialog for cancel — Ctrl+X still triggers cancellation directly
  (it now resolves to Partial/Aborted rather than an instant dismiss, but there is no extra prompt).
- No per-failure drill-down list, no "show all skipped hosts" expander — skipped units are only the
  inline `↳` log lines plus the stage-level count.
- No elapsed-time / ETA / deadline countdown readout (ETA stays disabled per 009).
- No "save as…" / export affordance — a partial payload is already persisted by the pipeline; the
  screen only offers to view it or return Home, both of which keep it.
- No retry-from-here / resume action; re-running is a fresh scan from the scan-mode flow.
- No change to the success state, the empty-result (zero hosts) success path, or the
  `(payload, view_flag)` dismiss contract beyond ensuring partial payloads ride the same tuple.
