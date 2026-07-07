# DESIGN — Scan progress screen (S4): port-stage sub-batch feedback + responsive cancel

Textual TUI spec. Keyboard interaction and copy, not pixels. Scope is deliberately **minimal**:
the DMI-50 issue's NOT-expected list says "No progress-screen redesign beyond what the stall
fix requires." This document changes **only** two behaviours on the existing
`ScanProgressScreen` (`hardware-agent/src/agent/tui/screens/scan_progress.py`):

1. **Sub-batch progress feedback during the port stage** — the port-stage status line gains a live
   **elapsed-time counter** that ticks every ~1s on the screen's existing `_tick` interval, so the
   operator never sees a multi-minute silent gap. A coarse `(batch N/M)` counter from
   `port_batch_done` is folded into the same line for structure. **No new pipeline event.**
2. **Responsive cancelling state** — after `ctrl+x`, a prominent banner tells the operator the
   scan is stopping and partial results are being saved, while the UI keeps animating and
   accepting input.

No new screen, no new layout region, no restyle. Both changes reuse widgets and ids that
already exist on S4.

## Screen flow

Unchanged. `ScanProgressScreen` (S4) is pushed by the scan-mode/confirm flow and, on finish,
`dismiss((payload, view_now))` returns to the caller. The two changes are internal state/copy
updates within S4; they do not add or remove any push/dismiss edge.

- Cancelling is an intermediate state on the way to the existing terminal `partial` state:
  `running → cancelling → partial` (worker finalizes and calls `_handle_complete` with a
  `partial_result` payload). `dismiss` still only fires from a terminal state.

## Layout

Top to bottom, inside `#progress-container` (all pre-existing — nothing added or reordered):

```
#scan-header      Static  — "Mode: … · subnet"
#scan-badge       Static  — hidden while running; now ALSO used for the CANCELLING banner
#progress-row     Horizontal
  #progress-bar   ProgressBar
#activity-log     RichLog  — stage lines; the port-stage line now carries the batch counter
#scan-done-actions Vertical (hidden until terminal)
  #btn-view-scan  Button
  #btn-back-home  Button
```

## Change 1 — Port-stage elapsed-time heartbeat + coarse batch counter

The pipeline keeps emitting `port_batch_done` (`ScanEvent` with `batches_done` /
`batches_total`) **once per host-batch** — that cadence is unchanged, and it is what advances
`#progress-bar` (via `ProgressMapper`). With a batch of 8, that event can be minutes away, which
is the multi-minute silent gap TRUTH forbids. A pipeline-side `port_progress` heartbeat was
considered and **rejected** (refine-specs decision, see ARCHITECTURE.md "Design decision 2"):
with up to `max_workers=4` batches scanning concurrently through one shared runner, a per-nmap
percentage would jump and reset incoherently, and cost a new event + field + parser.

**Decision:** close the gap entirely on this screen with a monotonic **elapsed-time counter** and
**no pipeline change**. The screen already runs a `_tick` interval that repaints the active
stage's spinner glyph; this change records when the port stage started and appends a live
`Nm Ss` elapsed counter to the active `ports` line on each tick. It increments every ~1s — far
more often than once per host-batch, always increasing, race-free — and needs no `ScanEvent`, no
`progress.py` change, and no runner sink.

Today the screen's handler `on_scan_progress_screen_progress_updated` has **no branch** for
`port_batch_done`, so the active `"Scanning ports…"` line only spins. This change adds a
`port_batch_done` branch (for the `batch N/M` structure) and, on `port_stage_started`, stores a
start timestamp that `_refresh_active_stage_lines` reads each tick to render the elapsed counter.

**Behaviour:**

- `port_stage_started` — set and store the mode-aware base label (unchanged from today):
  `Scanning ports…` (nspi/quick/standard) or `Scanning all ports…` (extensive/max) — and record
  `self._port_stage_started_at = monotonic()`.
- **`_tick` (existing interval, ~1s) — primary "no silent gap" mechanism** — when the active stage
  is `ports`, recompose its line to include the elapsed time
  `now - self._port_stage_started_at`, formatted `{m}m {s}s` (or `{s}s` under a minute), and let
  the existing spinner-repaint path render it. Do **not** touch `#progress-bar` here.
- `port_batch_done` — update the stored coarse `batch N/M` fraction and recompose the same line;
  the bar advances as today via the mapper. The elapsed counter keeps running across batches (it
  is stage-elapsed, not per-batch, so it never resets).
- `port_stage_done` — finish the line as today (`✓ N open ports found` / degraded variant); stop
  updating the elapsed counter. No change to the done copy.

The recomposed active line, using the stored base label + latest batch fraction + elapsed time:

| State of the port line | Rendered line (spinner + text) |
|------------------------|--------------------------------|
| after `port_stage_started`, before first tick | `⠙ Scanning ports…` |
| after a few ticks, before any batch done | `⠙ Scanning ports… (0m 12s)` |
| after `port_batch_done` + ticks (combined) | `⠙ Scanning ports… (batch 3/8 · 1m 20s)` |
| extensive / max variant | `⠙ Scanning all ports… (batch 3/8 · 1m 20s)` |

- Elapsed is wall time since `port_stage_started`, formatted `{m}m {s}s` (or `{s}s` when < 60s).
- Batch fraction is exactly ` (batch {batches_done}/{batches_total} · {elapsed})` when a batch
  count is known; before the first `port_batch_done` the line is `{base} ({elapsed})`.
- No ETA, no percentage. The elapsed counter is liveness only — the bar remains the source of
  truth for overall completion.

### Mockup — mid port stage, elapsed heartbeat visible

```text
┌──────────────────────────────────────────────────────────────────┐
│ Mode: NSPi · 10.0.12.0/24                          #scan-header    │
│                                                                    │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  23%  #progress-bar│
│                                                                    │
│ ┌── #activity-log ───────────────────────────────────────────────┐│
│ │ ✓ 8 hosts found                                                ││
│ │ ⠙ Scanning ports… (batch 3/8 · 1m 20s)                         ││
│ │                                                                ││
│ │                                                                ││
│ └────────────────────────────────────────────────────────────────┘│
│                                                                    │
│  Ctrl+X Abort scan                                                 │
└──────────────────────────────────────────────────────────────────┘
```

**Explanation.** Same three regions as today: header, progress bar, activity log. Discovery has
finished (`✓ 8 hosts found`). The port stage is active: its line is the last, still-spinning entry
in `#activity-log`, now carrying `(batch 3/8 · 1m 20s)`. The `1m 20s` is a wall-clock elapsed
counter that increments on the screen's existing `_tick` (~1s) — it changes every second, which
removes the multi-minute silent gap and satisfies TRUTH's "more than once per host-batch"
criterion without any new pipeline event. The `(batch 3/8)` structure comes from the coarser
`port_batch_done`, which is also the **only** event that moves `#progress-bar` (held at 23%
between batch events — it does **not** jump on the tick). Focus is not on any widget while running;
the only binding is `Ctrl+X Abort scan`.

## Change 2 — Responsive cancelling state

Today `ctrl+x` calls `_enter_cancelling`: sets `self._state = "cancelling"`, writes one activity
line, and calls `runner.request_cancel()`. The screen stays technically alive (the `_tick`
interval keeps running and the spinner keeps animating because `_active_stages` is not cleared),
but the only cue is a single log line that scrolls away, so the app *reads* as frozen while the
worker finalizes. This change makes the cancelling state **visibly** in-progress by showing a
persistent banner on the existing `#scan-badge` Static, and confirms input stays live.

**Behaviour:**

- On entering cancelling (`_enter_cancelling`):
  - Show `#scan-badge` (`display = True`) with the cancelling banner copy below.
  - Update the activity-log line copy to name the saving step.
  - Leave `self._active_stages` populated so the active stage line keeps spinning (the alive
    signal) — do **not** clear it here.
  - `runner.request_cancel()` returns immediately (sets a `threading.Event` and calls the
    non-blocking `terminate_active()`), so the Textual message pump and `_tick` interval are
    never blocked — the UI keeps repainting and keeps accepting keystrokes.
- While cancelling, input is still accepted: a second `ctrl+x` is a deliberate idempotent no-op
  (guarded by `if self._state == "cancelling": return` in `action_abort`), and other keys are
  handled but intentionally inert until the state becomes terminal. The point is that the event
  loop processes them, not that they act.
- On finalize, the worker calls `_handle_complete` with a `partial_result` payload →
  `_handle_partial`, which **overwrites** `#scan-badge` with the existing PARTIAL badge and shows
  `#scan-done-actions`. No change to that terminal path — the cancelling banner is simply
  replaced by the PARTIAL banner.

**Copy** (exact, final):

| Location | String |
|----------|--------|
| `#scan-badge` banner (cancelling) | `[black on yellow] CANCELLING [/] saving partial results…` |
| `#activity-log` line on cancel request | `[yellow]● Stopping scan — saving partial results, no new probes will start…[/yellow]` |
| `#scan-badge` after finalize (unchanged) | `[black on yellow] PARTIAL [/] stopped by you; partial results kept` |

The activity-log line replaces today's `● Stopping scan — terminating running steps…` so the
copy matches TRUTH's promise that the partial result is saved and no new probe starts.

### Mockup — cancelling / saving-partial state

```text
┌──────────────────────────────────────────────────────────────────┐
│ Mode: NSPi · 10.0.12.0/24                          #scan-header    │
│  CANCELLING  saving partial results…               #scan-badge     │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  23%  #progress-bar│
│                                                                    │
│ ┌── #activity-log ───────────────────────────────────────────────┐│
│ │ ✓ 8 hosts found                                                ││
│ │ ⠙ Scanning ports… (batch 3/8 · 1m 22s)                         ││
│ │ ● Stopping scan — saving partial results, no new probes will   ││
│ │   start…                                                       ││
│ └────────────────────────────────────────────────────────────────┘│
│                                                                    │
│  Ctrl+X Abort scan                                                 │
└──────────────────────────────────────────────────────────────────┘
```

**Explanation.** After `ctrl+x`, `#scan-badge` (normally `display: none` while running) becomes
visible directly under the header with the yellow `CANCELLING` chip and the `saving partial
results…` reason — a stable, non-scrolling cue that the app is working. The activity log gains
the `● Stopping scan…` line, and the port-stage line keeps its animated spinner glyph, so the
screen visibly moves while the worker finalizes. The progress bar holds at its last value (it is
not driven to 100% on cancel). No focus lands on a widget yet; `#scan-done-actions` stays hidden.
When the worker finishes finalizing, `#scan-badge` flips to the existing PARTIAL banner,
`#scan-done-actions` appears, and focus moves to `#btn-view-scan` (labelled "View partial scan")
— the current terminal-`partial` behaviour, unchanged.

## Key bindings

Unchanged. **No new bindings are added** — the responsiveness fix does not require any.

| Key | Action | State-dependence |
|-----|--------|------------------|
| `ctrl+x` | `action_abort` — first press: enter cancelling; while cancelling: idempotent no-op; when terminal: dismiss | already exists (`priority=True`) |
| `esc` | `action_no_op` — dismiss only when terminal | already exists |
| `↑`/`↓` / `j`/`k` / `enter` | navigate/select terminal action buttons; inert until terminal | already exists |

## States

| State | Behavior |
|-------|----------|
| Running — port stage | Active `ports` line spins and shows `… (batch N/M · Nm Ss)`; the elapsed counter refreshes every `_tick` (~1s); the bar advances **only** on `port_batch_done` and is held between batch events. |
| Cancelling (new visible treatment) | `#scan-badge` shows `CANCELLING · saving partial results…`; `#activity-log` shows the stopping line; spinner keeps animating; input still processed; bar holds. |
| Partial (terminal, unchanged) | `#scan-badge` = PARTIAL banner; `#scan-done-actions` shown; `#btn-view-scan` = "View partial scan", focused. |
| Fatal / Completed (unchanged) | As today. |

## Widget ids

Ids the implementer creates/changes and tests assert on. **No new ids are introduced** — both
changes reuse existing widgets:

- `#activity-log` (`RichLog`) — asserted for the port-stage elapsed line: after `port_stage_started`
  plus a few `_tick`s the text contains the base label and an elapsed counter that grew between
  ticks (e.g. substrings `Scanning ports…` and `0m`, then a larger value); after a
  `port_batch_done` it contains `batch 3/8`. Also asserted for the cancelling line
  `Stopping scan — saving partial results, no new probes will start…`. (Matches the existing
  `_log_text(screen)` test helper.)
- `#scan-badge` (`Static`) — asserted `display is True` in the cancelling state and its rendered
  text contains `CANCELLING` and `saving partial results…`; then, after finalize, contains
  `PARTIAL`.
- `#progress-bar` (`ProgressBar`) — asserted it advances on `port_batch_done`, **does not change on
  a `_tick`** (its `progress` is unchanged by the elapsed-counter refresh), and holds (does not
  reach 100) while cancelling.

## Files to touch (naming table)

| File | Change |
|------|--------|
| `hardware-agent/src/agent/tui/screens/scan_progress.py` | On `port_stage_started` record a `_port_stage_started_at` timestamp; have `_refresh_active_stage_lines` (the `_tick` path) append the elapsed counter to the active `ports` line; add a `port_batch_done` branch to `on_scan_progress_screen_progress_updated` for the `batch N/M` structure (held bar); extend `_enter_cancelling` to show the `#scan-badge` CANCELLING banner and use the new stopping-line copy. |
| `hardware-agent/src/agent/tui/app.tcss` | **No change expected** — `#scan-badge` already exists (`display: none`, bold) and is reused; the cancelling banner needs no new rule. Listed for completeness only. |
| `hardware-agent/src/agent/tui/scanner.py` (`ScanRunner`) | **No change** — the elapsed heartbeat is rendered from `port_stage_started` / `port_batch_done` (already flowing `stages.run_port_stage → reporter → _ScreenReporter → screen`) plus a local timestamp; no new event or field is threaded. Listed only as a CLAUDE.md call site to confirm nothing changes. |

## Integration note (per CLAUDE.md)

This feature adds **no new reporter event and no new `ScanEvent` field** — the earlier
`port_progress` design was dropped in refine-specs in favour of a screen-side elapsed counter
(ARCHITECTURE.md "Design decision 2"). The elapsed heartbeat is rendered entirely inside
`scan_progress.py` from data the screen already receives (`port_stage_started` /
`port_batch_done`, flowing through the existing `reporter` path) plus a local `monotonic()`
timestamp.

Per the project integration rule the two TUI call sites were still checked and both are
**unchanged**: `ScanRunner` (`scan_progress.py:131`) needs no new parameter or field, and
`ScanProgressScreen` (`home.py:74`) keeps its current signature. The only edit here is inside
`scan_progress.py` itself; the cancel guard (ARCHITECTURE.md decision 3) is internal to the nmap
runner and does not touch the TUI. There is nothing to thread.

## Out of scope (v1)

- No layout, colour, or CSS redesign of S4 (explicit NOT-expected item in DMI-50).
- No new screens, bindings, or widgets.
- No change to the discovery, deep-inspection, normalize, completed, or fatal copy/behaviour.
- No change to Quick / Standard / Extensive / MAX rendering beyond the shared
  `(batch N/M · Nm Ss)` elapsed line that any mode's port stage naturally shows from
  `port_stage_started` / `port_batch_done`.
- No ETA, no percentage, no per-host port progress, and no fractional bar nudge on the tick (the
  bar moves only on `port_batch_done`, matching ARCHITECTURE §2); the elapsed counter is the only
  new sub-batch granularity, and it is text-only.
