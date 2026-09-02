# UI Ideas — Parking Lot

Unvalidated UI ideas, grouped by topic. Nothing here is a commitment — feature requests start
at "no" ([`REFERENCE.md` §8](REFERENCE.md)). An idea graduates by becoming a decision in
[`ADR-008`](../adr/ADR-008-frontend-stack.md) / [`FLOWS.md`](FLOWS.md) / `SCREENS.md`, or a
Linear issue via the create-issue gate. Items marked *(salvaged)* come from the removed
March-era `wireframes.md` (2026-07-10).

## Table of contents

- [Navigation & app shell](#navigation--app-shell)
- [Home & data viz](#home--data-viz)
- [Scans](#scans)
- [Hosts](#hosts)
- [Agents & Scan now](#agents--scan-now)
- [Auth & admin](#auth--admin)
- [Copy & tone](#copy--tone)
- [States: blank, loading, error](#states-blank-loading-error)
- [Visual direction](#visual-direction)
- [Theming & accessibility](#theming--accessibility)
- [LLM explainer (deferred)](#llm-explainer-deferred)

## Navigation & app shell

- Global search in the top bar (hosts, scans, findings) *(salvaged)*
- Breadcrumbs in the top bar for list → detail navigation *(salvaged)*
- Keyboard shortcuts for power users (e.g. `g h` → Home)
- Long IDs truncated visually with a tooltip for the full value *(salvaged)*

## Home & data viz

- Severity cards click through to a filtered scans/findings view *(salvaged, marked "future")*
- Findings-over-time chart (bar/line) alongside the severity donut *(future only; deliberately outside MVP Home — Recharts remains available per [`ADR-008`](../adr/ADR-008-frontend-stack.md))*
- Fifth card with device/host count next to the four severity cards *(salvaged)*
- Dedicated aggregated Home endpoint when findings volume makes client-side counting costly *(salvaged backend note)*
- Backend finding-delta (new vs previously-seen finding) so Home can say "not seen before" honestly *(backend note; v1 approximates with latest-scan findings)*
- The "new device on your network" Home item — the contract gap is closed (`first_seen_at` is on `HostSummary`), the item itself is still unbuilt *(C6 resolved)*

## Scans

- Filters: status, mode, date range; server-driven sorting *(salvaged rule)*
- `highest_severity` computed by the backend, not recomputed per client *(salvaged backend note)*
- Scan mode badges (quick / extensive / max / NSPi) with distinct styling
- Scan duration column once the duration fix lands

## Hosts

- Search across hostname / IP / MAC / vendor *(salvaged)*
- First seen / last seen shown as a small timeline rather than two timestamps
- Vendor icons or grouping (Raspberry Pi, Synology, printers…)
- Consolidated per-host findings backed by backend consolidation *(salvaged backend note)*

## Agents & Scan now

- Command status as a stepper (queued → delivered → running → uploading → done) vs a single pill
- Agent "last seen" as relative time with exact timestamp on hover
- Auto-refresh of agent online/offline state while the Agents page is open
- Per-agent scan history on an agent detail view
- Estimated scan duration hint next to the trigger ("usually ~10 min")

## Auth & admin

- Auto-login after invite acceptance (FLOWS.md open decision #1 — needs contract support)
- Password strength meter mirroring the AUTH.md policy rules as-you-type
- Pending invite rows show TTL countdown (24–72 h) and a [Resend] affordance
- ~~Audit hint on user rows: last login~~ — **promoted 2026-08-08**, ships as the *Last seen* column
  (activity, counting silent refresh — see [`AUTH.md` § Member activity](../roadmap/AUTH.md) and
  [`ADR-017`](../adr/ADR-017-account-removal.md)). **Invited-by is still parked** — nothing records it.

## Copy & tone

- Severity explanations written for the non-technical org admin (plain language over CVSS vectors)
- Error toasts name the Pi by its human label, never by UUID
- 409 `device_busy` toast copy (FLOWS.md open decision #3)
- Empty search results suggest what to try, not just "no results"
- Voice stays plain and professional — 37signals' simplicity without their personal/"fun"
  register; no jokes or mascot energy in a security product

## States: blank, loading, error

- Blank Home doubles as onboarding: explains what a scan is and points at Scan now
- Positive framing for clean results ("No critical findings") instead of an empty table
- Loading skeletons for every table *(salvaged rule)*
- Scan-failed row links to a readable failure reason, not just a red badge

## Visual direction

Superseded by [`FOUNDATIONS.md`](FOUNDATIONS.md) (2026-09-02).

## Theming & accessibility

The MVP ships **light only** — see [`FOUNDATIONS.md`](FOUNDATIONS.md) §Theme. The items below are
what a later dark mode would have to answer; none of them are MVP work.

- Dark mode: re-derived from [`FOUNDATIONS.md`](FOUNDATIONS.md) from scratch, never an inversion
  of the light tokens
- Light/dark theme toggle in the top bar *(salvaged; deferred with dark mode — note a toggle is a
  preference, and §8 says the product should have a point of view instead)*
- Every token re-checked for AA contrast on the dark surface

## LLM explainer (deferred)

- In-context panel on scan/finding detail, not a separate page ([`AI.md`](../roadmap/AI.md))
- "Explain this finding" affordance per finding row feeding the panel
