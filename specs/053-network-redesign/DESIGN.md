# DESIGN — Network screens

> **Status:** approved by the owner on 2026-10-23.
> **Visual source:** [Dmitri scan visual cues canvas](https://claude.ai/artifact/UVnbjzroi7jkG1Xz6BsWFf),
> tab **Network page** (boards "Network · machine list" and "Network · one machine").
> **Shared rules:** tokens, hints, waiting state, the vulnerability view and the
> "For your IT person" pattern come from
> [`../052-ai-assistant-upgrade/DESIGN.md`](../052-ai-assistant-upgrade/DESIGN.md) (§3, §6,
> §7, §9, §14.2, §16). **Binding look:** [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md).
> **Depends on 052 for:** the AI cause sentence, the fix tasks (to-do list links, "What to
> do for this machine") and the machine-type counts. Every AI part has a non-AI fallback.

## 1. Network screens

Same shell, spacing and section style as 052 §14. Today's sources: `pages/Network.tsx`
(`ListSurface` with `hostListColumns`, quiet group), `pages/HostDetail.tsx`.

### 1.1 Machine list (board "Network · machine list")

Order, top to bottom:

1. **Header:** title `Network` (`title-lg`), line `{n} machines · last scan {date, time}`
   (`body-md`, `--ink-muted`). No actions.
2. **What is on your network** (card, title `title-xs`):
   - One tile per machine type found, **as many as there are** (no fixed count). Grid
     `repeat(auto-fill, minmax(180px, 1fr))`, gap 16px; tiles wrap to new rows.
   - Every tile is the same: 1px `--rule` border, radius 8px, padding 16px. **No thick or
     dashed borders** (owner decision).
   - Tile content: `{n} {type plural}` (`title-sm`) and one status line (`body-sm`):
     `{k} need attention` / `Needs attention` in 600 `--ink`; `No known problems` or
     `Did not answer` in `--ink-muted`.
   - Order: types that need attention first (by highest risk), then by count, `unknown`
     last.
   - Each tile is a `<button>` that filters the "All machines" table to that type
     (`aria-pressed` when active).
   - No helper text under the tiles (owner decision).
   - Source: `code`, from `machine_type` counts (052 §10 gap 4).
3. **Needs attention** (card, title `title-sm`, count `{n} machines` right): one row per
   machine with at least one problem, sorted by highest Dmitri risk. Row grid: name block
   | 120px risk | 200px next step | chevron.
   - Name (600, link to the machine page) + ` · {type}` (`--ink-muted`).
   - One sentence (`body-sm`, `--ink-muted`): plain cause (`AI`, fallback: top problem
     title) + `{n} problems, highest **{Level}**.`
   - `Risk {n}` (number only).
   - `Next: Task {k} · {short task title}` link to the to-do list task (052 §15). Hidden when
     there is no to-do list.
   - Hidden entirely when no machine has problems.
4. **All machines · {n}** (card): `Show` select (all types or one type; synced with the
   tiles). Table columns: Machine (bold when it has problems; `No name` in `--ink-muted`)
   | Type 140px | Address 160px mono | Problems 180px (`{n} · **{Level}**`, or `None known`,
   or `Not checked` in `--ink-muted`) | Dmitri risk 120px (number only, `—` when none) |
   Last seen 140px (`--ink-muted`). Default sort: risk, highest first. **Pagination**, not
   "show more" (owner decision): today's `Pagination` component (`Machine pages` label,
   previous / page numbers / next, 40px controls, current page with a 1px `--ink` border)
   plus a `{from}–{to} of {total}` count in `--ink-muted`. The quiet group stays as today: `Not seen recently ({n})`, collapsed,
   right of the button.

### 1.2 One machine (board "Network · one machine")

1. **Header:** `← Network`; meta `{Type} · seen {when}`; title = machine name
   (`title-lg`); address in mono under it. Right: outline button `Explain this machine`
   (opens the machine explanation task; same side panel pattern as 052 §18).
2. **About this machine** (card, 4-column definition list, same layout as 052 §4):
   - `What it is`: plain type (`A video camera`) + how Dmitri knows (`Probably a Hikvision
     camera. Dmitri guessed this from its web page and open doors.`).
   - `Open doors` (hint trigger, 052 §6): count + plain list of services (`Web page, video
     stream, remote setup.`).
   - `Problems`: count + `Highest: **{Level}** · Dmitri risk **{n}**`.
   - `History`: `In {n} scans` + `First seen {date}.` and a change sentence (`The same
     problems in every scan.` / `{n} new since the last scan.`).
3. **What to do for this machine** (card): the one fix task that fixes the most problems
   on this machine. Title sentence (600) `{task}. It fixes {both / k of n} problems.`;
   meta `{who} · about {time} · task {k} on your to-do list` (link); up to 3 steps; one
   fallback line. States follow 052 §17 (waiting, scanner fallback, nothing to fix: `No known
   problems on this machine.` + the 052 §5 not-safe line).
4. **Problems on this machine · {n}** (card): same table as 052 §16 without the Machine
   column; rows open the 052 §7 view inline.
5. **For your IT person** (052 §14.2 style): `Open ports · {n}` (today's `HostExposures` /
   `HostPortsTable`), `Machine profile` (address, MAC, vendor, software seen, type guess
   with confidence; today's `HostProfile` / `HostIdentity`), `Scan history · {n} scans`.

Replaces today's host page stack (identity, profile card, attack surface card, one-shot
AI explanation, vulnerabilities card, ports card).

Test ids: `network-types`, `network-type-{type}`, `network-attention`,
`network-attention-{host_id}`, `network-all`, `machine-about`, `machine-best-fix`,
`machine-problems`, `machine-explain-open`.
