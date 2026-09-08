# ARCHITECTURE — Design system v2 and the restyle onto it

Engineering shape only. `TRUTH.md` is approved and is not re-decided here. The visual
specification is [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md) — cited by section, never
restated. Per-screen mockups, copy and `data-testid` values are `DESIGN.md`'s job, not this
document's.

## Scope note — this is a frontend-only feature

Everything in this spec lives under `frontend/`. It changes **no API contract**: no file under
`contracts/`, `backend/` or `hardware-agent/` is touched, and `npm run gen:types` must produce a
clean diff at the end. There is therefore **no `INTEGRATION.md`** — nothing crosses a layer
boundary.

**The CLAUDE.md `ScanRunner` / `ScanProgressScreen` threading rule does not apply here.** That rule
is about `hardware-agent/src/agent/scanner/runner.py` and the Textual TUI, which have their own scan
path around `ScanOrchestrator`. No Python is touched by this feature. Do not go looking for a
`ScanRunner` call site to thread anything through. The equivalent obligation in this spec is the
**call-site sweep** in §9: every constructor and call site of a changed React component, hook or
route string is accounted for in the file table.

---

## 1. System context

The React SPA under `frontend/` reads the backend's read surface and writes only two things: the
per-box target subnet (`PATCH /agents/{id}`) and a scan command (`POST /agents/{id}/commands`). The
pipeline this feature sits at the end of is unchanged:

```
Pi box → discovery → port scan → NSE → ScanPayload → POST /scans (ingest)
                                                        ↓
                                       backend persistence + CVE enrichment
                                                        ↓
              GET /scans · /hosts · /findings · /agents · /commands   ← this feature
                                                        ↓
                       React SPA:  tokens → primitives → shared components → screens
```

The feature restyles the last box and re-cuts its routes. Four layers, bottom-up, and the
dependency runs one way only:

| Layer | Owns | Files |
| --- | --- | --- |
| **0 Tokens** | CSS custom properties, `@theme inline`, fonts, the lint rules that police them | `src/index.css`, `package.json`, `eslint-rules/` |
| **1 Primitives** | vendored shadcn/Radix controls, regenerated from `radix-maia` | `src/components/ui/**` |
| **2 Shared components** | Dmitri-owned presentation and page-state machines | `src/components/**` |
| **3 Screens + routes** | pages, column modules, screen-local hooks | `src/App.tsx`, `src/pages/**`, `src/hooks/**` |

A layer may import downward, never upward. `src/components/ui/**` is vendored: it stays exempt from
the local lint rules and is never hand-edited except to re-apply the documented local edits in §3.

---

## 2. Layer 0 — tokens, fonts, lint

### 2.1 `src/index.css`

Replaced wholesale with the values in FOUNDATIONS §Theme, §Type, §Color, §Spacing, §Radius,
§Containers, §Motion. The mechanical facts an implementer needs:

- **The `dark` custom-variant neutraliser stays**, verbatim, with its comment
  (`@custom-variant dark (&:is(.dmitri-dark-unused *))`). FOUNDATIONS §Theme says leave it alone,
  and §3 explains why it is load-bearing after the primitives are regenerated.
- **Deleted tokens:** `--font-title`, `--text-nav`, `--sev-critical|high|medium|low` and their four
  `--color-sev-*` mirrors. `--paper` becomes `--canvas` (FOUNDATIONS §Color names it `--canvas`).
- **`--radius: 0` → `0.75rem`**, plus a new `--control-radius: 0.5rem`. The `sm…4xl` ladder keeps
  its existing **multiplicative** `calc(var(--radius) * n)` form (FOUNDATIONS §Radius forbids the
  additive form); it is already correct in the file and must not be replaced by whatever the
  regenerated preset emits.
- **`--font-sans` is Inter Variable and is applied on `html`.** The current base layer reads
  `html { @apply font-mono }` — the whole app is monospaced today. That line becomes
  `@apply font-sans`, and mono becomes opt-in per FOUNDATIONS §Type (IP, MAC, port, CVE, UUID
  only). This is the single largest visual delta in the feature and it lands in one line.
- **Type scale re-valued and closed at seven tokens.** `--text-title-sm` 1.25rem → 1.375rem,
  `--text-body-md` 0.875rem → 0.9375rem, `--text-body-sm` 0.8125rem → 0.875rem,
  `--text-caption-md` 0.75rem → 0.8125rem. Every one of those four changes silently reflows
  existing screens; none of them fails a gate.
- **New custom utility for the table row height**, following the existing `@utility grid-cols-bar`
  precedent:

  ```css
  @utility h-row { height: 3.5rem; } /* 56px — FOUNDATIONS §Tables */
  ```

  A raw `h-14` would pass lint but re-states a magic number at every call site; the utility keeps
  the 56px in one place. `DataTable` is its only caller.

### 2.2 `package.json`

Added: `@fontsource-variable/inter`, and the Geist Mono Variable package
(`@fontsource-variable/geist-mono`). Removed: `@fontsource/im-fell-english`,
`@fontsource/ibm-plex-mono`, and their three `@import` lines in `index.css`.

### 2.3 Lint rules

There are **four** registered rules today, not five: `no-arbitrary-utility`, `no-raw-type-size`,
`spacing-scale`, `no-bare-interactive`. The fifth file, `class-strings.js`, is the shared AST
visitor they all use, not a rule. All four survive the token change; **none is deleted**, because
each still describes a rule FOUNDATIONS still makes. Two are added. Final set: six rules.

Re-keying required, all in the same commit as `index.css` (FOUNDATIONS §Type/§Color are the
authority; the rules hard-code token names and would otherwise recommend tokens that no longer
exist):

| Rule | Change |
| --- | --- |
| `no-arbitrary-utility` | Message drops `text-nav` from the list of legal type tokens. |
| `no-raw-type-size` | The `TYPE_SIZES` map is re-keyed to the new pixel values: `text-sm` (14px) → `text-body-sm`; `text-xs` (12px), `text-base` (16px) and `text-xl` (20px) now match **no** token and fall to `noMatchingToken`. Leaving `text-sm → text-body-md` in place would silently recommend a 15px token for a 14px need. |
| `spacing-scale` | Message cites `docs/ui/FOUNDATIONS.md` §Spacing instead of the retired `SCREENS.md`. |
| `no-bare-interactive` | Message cites `FOUNDATIONS.md` §Interaction states instead of `SCREENS.md` §Foundations. |
| **`no-raw-hex`** (new) | Bans a hex literal (`#rgb`, `#rrggbb`, `#rrggbbaa`) and `rgb()`/`hsl()` function calls inside an authored class string or a JSX `style` value. FOUNDATIONS §Color: colour is a token. **Scope limit, stated honestly:** ESLint only sees `.ts`/`.tsx`. It cannot police `index.css`, which is where every legitimate hex lives; the rule protects components, not the token file. |
| **`no-dark-variant`** (new) | Bans a `dark:` prefix on any class token in an authored class string. FOUNDATIONS §Theme: never authored. |

Both new rules reuse `createClassStringVisitor` from `class-strings.js` and ship with a
`*.test.js` beside them, mirroring `no-raw-type-size.test.js`. Both inherit the existing three
exemptions in `eslint.config.js` — `src/components/ui/**`, `src/**/*.test.{ts,tsx}`, `src/test/**` —
and **that exemption is why `no-dark-variant` and the neutraliser coexist**: the regenerated
primitives will ship `dark:` utilities that the app cannot author but must tolerate. Never widen an
exemption to make the gate pass.

**No lint rule catches a deleted token.** Tailwind v4 emits nothing for an unknown utility: after
`--font-title` is gone, `className="font-title"` compiles, lints, type-checks and builds clean, and
the heading silently falls back. The only defence is the atomicity rule in §8 plus this grep as a
commit success criterion:

```
grep -rn "font-title\|text-nav\|sev-critical\|sev-high\|sev-medium\|sev-low" frontend/src
```

must return nothing but `index.css`'s own absence of them (i.e. zero hits) before the token commit
is considered done. `font-title` appears in **29 files** today; `text-nav` in `TopBar.tsx`;
`sev-*` in `SeverityBadge.tsx` and `StatusPill.tsx`.

---

## 3. Layer 1 — primitives

`components.json`: `"style": "radix-nova"` → `"radix-maia"`. `iconLibrary` stays `lucide`,
`baseColor` stays `neutral`, `cssVariables` stays true.

Existing primitives regenerated from the preset: `ui/button.tsx`, `ui/input.tsx`, `ui/label.tsx`,
`ui/select.tsx`. New primitives: `ui/card.tsx`, `ui/tabs.tsx`, `ui/pagination.tsx`,
`ui/dialog.tsx`. **Tooltip is not generated** — see the flag below.

**Local edits to re-apply after regeneration** (the whole reason this is a listed step rather than a
command to run):

1. `ui/button.tsx` — the `link` variant is used by `DataTable` sort headers and by
   `Disclosure`/`FindingDeck`-style text controls with heavy `className` overrides at the call
   site. Verify the regenerated variant names still include `link`, `outline` and `ghost`; a
   renamed variant is a compile error, a re-cut variant is a silent restyle.
2. `ui/button.tsx`, `ui/input.tsx` — confirm `cursor-pointer` is present on the button base.
   FOUNDATIONS §Interaction states: Tailwind preflight sets `cursor: default` on `<button>` and the
   pointer is never inherited.
3. `ui/select.tsx` — the Users role cell strips the trigger to
   `h-auto rounded-none border-0 px-0 py-0`. Those overrides live at the **call site**
   (`pages/users/DirectoryTable.tsx`), so regeneration does not lose them, but a regenerated trigger
   with different internal padding will move the Role column's left edge. FOUNDATIONS §Tables
   requires the inline select to align with its column header — re-check after regeneration.
4. Any `dark:` utility the preset emits **stays**. It is inert (§2.1) and hand-stripping vendored
   source guarantees a diff on the next regeneration.

`DialogShell.tsx` currently imports `Dialog` from `radix-ui` directly. Once `ui/dialog.tsx` exists,
`DialogShell` composes it, so the panel radius comes from `--radius` rather than a hand-written
class. Its public props (`open`, `onOpenChange`, `testId`, `size`, `locked`, `initialFocusRef`) do
not change — all four modal call sites are untouched.

> **Resolved — `ui/tooltip.tsx` is not generated.** Nothing in `TRUTH.md` or `FOUNDATIONS.md`
> names a screen that needs one; truncated IDs use the native `title` attribute (FOUNDATIONS
> §Tables), and `Timestamp` already uses `title` for the exact value. `DESIGN.md` was written
> against all ten screens and names **no** tooltip call site, so generating the primitive would be
> exactly the speculative code `.claude/CLAUDE.md` §No temporary code forbids. It is dropped from
> the generation list; add it in the feature that first needs one.

---

## 4. Layer 2 — shared components

### 4.1 `DataTable` — the contract it must expose

`DataTable` is the epicentre of this feature. Its existing generic shape stays
(`DataTable<Row, SortKey>`, discriminated `rowAction: link | expand | absent`, typed
`DataTableSort`, `DataTableColumn` union). Four additions, no removals:

| Addition | Shape | Why |
| --- | --- | --- |
| Fixed row height | Rows and header render `h-row` (56px) instead of `h-8`; every cell keeps `truncate` and the row never grows. | FOUNDATIONS §Tables: "Fixed and equal for every row — 56px. Written into `DataTable`." |
| Lucide sort markers | The `▲▼` / `▲` / `▼` glyph spans in the sortable `<th>` are replaced by `ChevronsUpDown` (inactive), `ChevronUp` (asc), `ChevronDown` (desc) from `lucide-react`, at `size-4`, `aria-hidden`. `aria-sort` on the `<th>` is unchanged — it, not the icon, is what tests assert. | FOUNDATIONS §Icons: "Sort markers — Lucide chevron/arrow icons … never `▲▼` glyphs." |
| Muted row tone | New optional prop `rowTone?: (row: Row) => 'muted' \| undefined`. `'muted'` puts the row in `--ink-muted`. No icon, no chip, no colour. | FOUNDATIONS §Tables, Silent devices. |
| Secondary line in a cell | No new prop. A column's `render` may return two stacked lines; 56px is what buys the room. The second line is the caller's (`Not seen for N weeks`). | Same. |
| Collapsed trailing group | New optional prop `collapsedGroup?: { rows: Row[]; label: (count: number) => string; testId: string }`. `DataTable` renders `rows` normally, then one group row spanning every column, with `aria-expanded` / `aria-controls` over the group's own `<tr>`s, always last — after the sort. Closed by default. Group members honour `rowTone` and `rowAction` exactly like ordinary rows. | FOUNDATIONS §Tables: "collapse into one group row at the bottom of the table … The group row is always last, after the severity/name sort. This is a `DataTable` pattern." |

**What `DataTable` must *not* grow:** no `onRowClick`, no `href` string, no `expandable` boolean, no
per-row `className` escape hatch. Those would each add an interaction the component has no five
states for. Whole-row navigation already exists as `rowAction: { kind: 'link' }` and the stretched
anchor stays exactly as documented in `.claude/docs/frontend/tables.md` — including the constraint
that **tests click the row's link, never the `<tr>`**, because jsdom does no layout and the overlay
span covers nothing there.

The group row is itself an interactive control, so it uses the shared `Button` (`variant="link"`),
not a bare `<button>` — `no-bare-interactive` enforces this.

> **Flag — the silent group is per-page, not per-dataset.** `GET /hosts` paginates 20 rows a page
> and sorts server-side; there is no `last_seen_at` filter and no count of silent hosts in
> `HostListResponse`. `Not seen recently (N)` therefore counts **the silent rows on the current
> page**, and the group is last on that page, not last in the inventory. This satisfies the
> acceptance criterion as written for a single-page fixture and is honest about what the API can
> supply; a dataset-wide group needs a backend change and is out of scope per `TRUTH.md`.

### 4.2 `SeverityWord` replaces `SeverityBadge`

`src/components/SeverityWord.tsx`, default export, props `{ severity: Severity | null | undefined }` (corrected 2026-09-03: `highest_severity` is
declared optional *and* nullable in `openapi.d.ts`, so three of the five call sites can pass
`undefined`). Renders
the capitalised word in `font-semibold` primary ink; renders `<EmptyMark />` (the existing em-dash
component) when `severity` is null. No border, no background, no hue — FOUNDATIONS §Color.

Five call sites migrate: `pages/home/ReviewItemCard.tsx` (deleted anyway),
`pages/scans/findingColumns.tsx`, `pages/scans/scanListColumns.tsx`,
`pages/hosts/HostScanHistoryTable.tsx`, `pages/hosts/hostListColumns.tsx`. Two of those
(`scanListColumns`, `hostListColumns`) currently branch `severity == null ? <EmptyMark/> : <Badge/>`;
that branch moves inside `SeverityWord`, so the columns become a bare `<SeverityWord severity={…} />`.

> **Flag — `informational` is not in the generated type.** FOUNDATIONS §Color says the API taxonomy
> is "critical / high / medium / low / informational", but
> `components['schemas']['Severity']` is `"low" | "medium" | "high" | "critical"`. `SeverityWord`'s
> label map stays four-wide and exhaustive over the real union; an `informational` word cannot be
> rendered and must not be hand-added (`.claude/skills/frontend-conventions` §Data and types: never
> hand-write an API type). If `informational` is real, it is a contract change and a different
> issue.

### 4.3 `StatusPill` is deleted, and its two helpers lose their tone

`StatusPill` and `StatusPill.test.tsx` go. Status becomes plain muted text — no new component,
because a non-interactive text span does not earn one.

The ripple is in two pure modules and must be handled deliberately:

- `lib/scanStatus.ts` — `ScanStatusPill` → `ScanStatusLabel { label: string }`; the exported
  `ScanStatusTone` type is deleted; `scanStatusPill()` → `scanStatusLabel()`.
- `lib/commandStatus.ts` — same shape; it currently **imports `StatusPillTone` from the component**,
  which is the import that breaks the build first. `commandStatusPill()` → `commandStatusLabel()`.

Callers: `pages/scans/scanListColumns.tsx`, `pages/scans/ScanUnfinishedNotice.tsx`,
`pages/scans/ScanFailedNotice.tsx`, `pages/agents/CommandStatus.tsx`.

### 4.4 `Pagination` is rebuilt on the shadcn primitive

`src/components/Pagination.tsx` keeps its exact props (`page`, `perPage`, `total`, `onPageChange`,
`testId`) and its `${testId}-pagination` / `-previous` / `-next` testids, so `ListSurface` and both
list screens are untouched. Inside, it composes `ui/pagination.tsx`: ghost icon-only
`chevron-left` / `chevron-right` with accessible names **"Previous page"** / **"Next page"**, page
numbers and an ellipsis (FOUNDATIONS §Pagination). The words *Previous* and *Next* leave the DOM.

The page-number window is arithmetic, not layout, so it goes in a pure, unit-tested module:
`src/lib/pageWindow.ts` — `pageWindow(page, pageCount): (number | 'ellipsis')[]`.

The existing "Showing 1–20 of 25" range line has no mandate in FOUNDATIONS §Pagination, which
specifies numbers instead. It is removed along with the `${testId}-range` testid.

### 4.5 Everything else in `src/components/`

| Component | Change |
| --- | --- |
| `Ornament.tsx` + `Ornament.test.tsx` | **Deleted.** Three call sites lose it: `AuthShell`, `EmptyState`, `pages/home/HomeBlank` (plus `Home` and `Agents`, both rewritten). |
| `EmptyState.tsx` | Ornament removed. FOUNDATIONS §Copy rules: one sentence + one button, nothing else — the `note` slot is retained only because `AgentsBlank` is the one blank state with no action, and `DESIGN.md` decides whether it survives. |
| `TopBar.tsx` | Nav renamed and re-routed (§6). `font-title` and `text-nav` removed; nav is `text-body-md`, active is **bold with no underline**, hover is also bold — the `border-b-2` affordance in `navLinkClass` goes. Wordmark becomes the word `Dmitri` (not `DMITRI`). Right side shows the user's **email**, truncated with an ellipsis when it would crowd the bar and carrying the full value in `title` — `UserProfileResponse` has no name field, and the owner confirmed the email on 2026-09-02. `FOUNDATIONS.md` §Chrome is amended to match (Task 12). |
| `PageHeader.tsx` | `font-title` → weight-and-size only. |
| `AppShell.tsx`, `AuthShell.tsx` | Container tokens unchanged (`max-w-frame`, `max-w-form`); ornament and font-title removed. |
| `Disclosure.tsx`, `ConfirmByTyping.tsx`, `DialogShell.tsx`, `Toast.tsx`, `ErrorRetry.tsx`, `NotFoundNotice.tsx`, `LoadingSkeleton.tsx`, `ReadDetailGate.tsx`, `ListSurface.tsx`, `Timestamp.tsx`, `EmptyMark.tsx`, `AdminOnly.tsx`, `FirstScanCta.tsx` | Token/class edits only, no API change. `FirstScanCta`'s `<Link to="/agents">` becomes `/devices` (§6). |

---

## 5. Data model and contracts

No API contract changes. Three client-side contract changes:

### 5.1 Scan modes become first-class client data

`src/api/agents.ts` **deletes `QUICK_SCAN_MODE`**. A new pure module carries the five real modes and
their verbatim FOUNDATIONS §Scan settings descriptions:

```ts
// src/lib/scanModes.ts
type ScanMode = components['schemas']['ScanMode']   // 'quick'|'standard'|'extensive'|'nspi'|'max'

export const SCAN_MODE_ORDER: readonly ScanMode[]          // tab order
export const SCAN_MODE_LABEL: Record<ScanMode, string>     // Quick · Standard · Extensive · Max · NSPi
export const SCAN_MODE_DESCRIPTION: Record<ScanMode, string> // ships verbatim from FOUNDATIONS
export const DEFAULT_SCAN_MODE: ScanMode = 'quick'
```

The union comes from the generated types, so a contract change to `ScanMode` breaks
`Record<ScanMode, …>` at compile time rather than dropping a tab silently.

> **Flag — a box has no stored default scan type.** `AgentDetail` is
> `{ agent_id, display_name, online, last_seen_at, available_subnets, target_subnet,
> active_command_id }`. There is no `default_scan_mode` field, and DMI-133 owns the daily-scan
> default (explicitly out of scope in `TRUTH.md`). Two acceptance criteria lean on a default that
> does not exist:
> - *"Scan now uses the selected type; the box's stored default is not changed"* — trivially true,
>   because there is nothing to change. Verifiable only as: the `POST /agents/{id}/commands` body
>   carries the selected `scan_mode`, and no `PATCH /agents/{id}` is issued.
> - *"Scan type never persists by accident … the selection has reverted to the box's default"* —
>   implementable as reverting to `DEFAULT_SCAN_MODE` (`'quick'`), a client constant, because
>   the selection lives in component state that unmounts with the route. Verifiable as written.
>
> `DEFAULT_SCAN_MODE` is therefore a **placeholder for a server field that DMI-133 introduces**, and
> that is exactly the kind of thing `.claude/CLAUDE.md` §No temporary code asks me to name rather
> than ship quietly. It is defensible here because it is one constant with one reader and DMI-133
> replaces it with a field read, not with a different design. Owner may prefer to hard-code
> `'quick'` at the single call site instead; either way, do not invent an `AgentDetail` field.

### 5.2 `useScanCommand` takes the mode at trigger time

```ts
// src/hooks/useScanCommand.ts
export type ScanCommand = {
  command: CommandDetail | null
  following: boolean
  triggering: boolean
  trigger: (scanMode: ScanMode) => Promise<TriggerOutcome>   // was: () => Promise<…>
}
```

The mode is a **trigger argument, not hook state**. The hook stays stateless about selection, and
the retry path inside `CommandStatus` re-uses whatever mode the screen still has selected — one
source of truth, in the screen. Everything else about the hook is unchanged: the `409 device_busy` /
`503 device_offline` / `422 subnet_not_reported` branches, the 5s poll to terminal, and the
post-`done` invalidation sweep of `scans` / `hosts` / `findings` / `agents.detail`.

Call sites: `pages/agents/ScanControl.tsx` (both the primary trigger and `onRetry`). Two callers,
both inside `ScanControl`.

### 5.3 Query keys

`src/api/queryKeys.ts` is **unchanged**. `agents.list()` and `agents.detail(id)` already exist and
already carry the coarse→fine prefix shape the invalidation sweep depends on. The Devices list reads
`agents.list()`; the box detail screen reads `agents.detail(agentId)`. No new key family, and no key
is renamed — `/hosts` stays the query-key namespace because it is the API noun, even though the
route becomes `/network` (§6).

---

## 6. Routing

| Route | Element | Change |
| --- | --- | --- |
| `/network` | `pages/Network.tsx` | renamed from `/hosts` |
| `/network/:hostId` | `pages/HostDetail.tsx` | renamed from `/hosts/:hostId` |
| `/devices` | `pages/Devices.tsx` | renamed from `/agents`; now a **list of boxes** |
| `/devices/:agentId` | `pages/DeviceDetail.tsx` | **new** — the box detail screen |
| everything else | — | unchanged |

**No redirects from `/hosts` or `/agents`.** `TRUTH.md`: "`/hosts` and `/agents` are no longer
routes." Both fall through to the existing `*` → `NotFound`.

**Naming rule, applied once and stated here so nobody re-litigates it per file:** *URLs, nav labels
and reader-facing copy adopt the new vocabulary; code identifiers keep the API noun.* So
`pages/Network.tsx` imports `pages/hosts/hostListColumns.tsx` and calls `listHosts()` — the endpoint
is `/hosts`, the schema is `HostSummary`, and renaming six column modules and their imports would
be churn with no user-visible effect (`.claude/CLAUDE.md` §Surgical changes). Only the two
route-level page components are renamed, because a page component is named after its screen.

`index.html` `<title>` becomes `Dmitri`. Per-page titles are out of scope (`TRUTH.md`).

> **Flag — the word *device* is used two ways, and `TRUTH.md` and `FOUNDATIONS.md` disagree.**
> `TRUTH.md` §Business rules: "A *device* is a machine found on the customer's network; a *box* is
> the Dmitri unit that scans it." `FOUNDATIONS.md` §Vocabulary: "**Devices** (was Agents). A
> *device* is the Dmitri box running inside a network." Under TRUTH's glossary, `/devices` should
> list machines; under decisions 7–8 and the AC table ("Boxes are listed … the device list renders
> … every box appears as a row"), `/devices` lists boxes and `/network` lists machines. I have
> implemented the routes as directed, because the AC table is unambiguous about the behaviour. The
> unresolved part is **copy**: FOUNDATIONS §Vocabulary needs the same correction the owner already
> scheduled for §Scan settings, or `DESIGN.md` will have to invent the word the Devices list uses
> for its rows. This is a `DESIGN.md` blocker, not an implementation blocker.

---

## 7. Screens

### 7.1 Devices — `/devices`

A list of boxes driven by `listAgents()`. Columns per the AC: name · watched network · status ·
last reported. `available_subnets` is **not** on `AgentSummary`, so the network cell shows
`target_subnet` or the muted "no network chosen yet" line — it cannot show the interface label the
detail screen shows.

**`ListSurface` is not usable here.** It requires `query.data.total`, and `AgentListResponse` is
`{ data: AgentSummary[] }` with no total and no pagination parameters. `Devices.tsx` therefore
composes `DataTable` + `EmptyState` + `ErrorRetry` directly, with `rowAction: { kind: 'link', to:
(a) => '/devices/' + a.agent_id }`. A large fleet renders unpaginated; that is what the endpoint
supports today.

`AgentsBlank.tsx` survives as the no-box empty state (renamed `DevicesBlank.tsx`).

### 7.2 Box detail — `/devices/:agentId`

Composition, using components that already exist:

```
DeviceDetail
├─ useParams() → agentId
├─ useQuery(queryKeys.agents.detail(agentId), () => getAgent(agentId))
├─ readDetailState(agentId, query)      // lib/detailState.ts — unchanged
└─ ReadDetailGate                       // owns notFound → error → loading
   └─ (agent) =>
      ├─ AgentIdentity        (existing, unchanged)
      ├─ TargetSubnetSection  (existing — moved from AgentCard, unchanged API)
      │  └─ SubnetChooser     (existing, unchanged)
      ├─ ScanTypeTabs         (NEW — ui/tabs, SCAN_MODE_* , admin-only)
      └─ ScanControl          (existing — now receives the selected mode)
         └─ CommandStatus     (existing — StatusPill removed)
```

`AgentCard.tsx` is deleted: the box detail screen *is* the card's body, promoted to a screen, and its
two pieces of local state move up with it — `chooserOpen` (seeded
`user?.role === 'admin' && agent.target_subnet == null`, which is the AC "the network chooser is open
and the scan-now control is absent until a network is saved") and `savedTargetSubnet` (which drives
the autofocus after saving). The third piece of state is new: `selectedMode`, initialised to
`DEFAULT_SCAN_MODE`, held in the screen, passed to `ScanTypeTabs` and to `trigger(selectedMode)`.
Because it is component state on a route, leaving and returning resets it — the AC's "reverts"
behaviour needs no extra code.

`useAgentScreen.ts` and `usePrimaryAgent.ts` are **deleted**. Their loading/error/blank ladder is
`ReadDetailGate`'s job on the detail route and a plain query on the list route; neither hook has a
caller once Home is re-pointed (§7.3). `useUpdateTargetSubnet.ts` is unchanged.

Viewer behaviour is unchanged and already correct: `TargetSubnetSection` and `ScanControl` wrap
their controls in `AdminOnly`. `ScanTypeTabs` must do the same — a viewer reads the selected type as
text, with no tab strip (FOUNDATIONS §Interaction states, absent not disabled).

### 7.3 Home — `/`

The card deck retires. `pages/home/FindingDeck.tsx`, `FindingDeck.test.tsx` and `ReviewItemCard.tsx`
are deleted; `pages/home/AttentionTable.tsx` replaces them, rendering `DataTable` over the
already-fetched `deckFindings` with columns Vulnerability · Device · Severity and
`rowAction: { kind: 'link' }` to the finding's scan (`/scans/:scanId?finding=:findingId` — the
existing deep link `ScanDetail` already honours). No new query, no new query key: the data is
already in `useHomeReview`.

Two ripples that must not be missed:

- `deriveReview()` still returns `scanItem` (failed scan) and `coverageItem` (stale coverage), and
  `ReviewItemCard` was their **only** renderer. They become one-line notices in a new
  `pages/home/AttentionNotices.tsx` — sentences, no cards. Deleting them instead would change what
  Home reports, which `TRUTH.md` puts out of scope.
- `useHomeReview` uses `usePrimaryAgent()` purely to feed `HomeFooter`'s Pi line, and
  `usePrimaryAgent` is being deleted. Replace with a plain
  `useQuery({ queryKey: queryKeys.agents.list(), queryFn: listAgents })` and pass
  `data?.data[0] ?? null`. `HomeFooter` reads only `online` and `last_seen_at`, both present on
  `AgentSummary`, so its prop type narrows `AgentDetail` → `AgentSummary` and nothing else moves.
  This also removes Home's second request (the `getAgent` detail read it never used).

The clear state renders the title and nothing else — FOUNDATIONS §Copy rules: "the Home attention
board renders **nothing at all**".

### 7.4 Network, Scans, Scan detail, Host detail, Users, Settings, auth screens

Restyle only: `font-title` removed, `SeverityBadge` → `SeverityWord`, `StatusPill` → text,
`/hosts` → `/network` and `/agents` → `/devices` in every `Link`, and the reader-facing word
*finding* → *Vulnerability* in column headings and copy. No data-fetching or state changes. The
`hostListColumns` `Highest severity` column keeps its place per FOUNDATIONS §Tables (severity closes
the row, or sits second-to-last where `Last seen` closes — which is exactly the current order).

`pages/Network.tsx` gains the silent-device split: partition the page's rows on
`last_seen_at` older than two weeks, pass the recent ones as `rows` and the silent ones as
`collapsedGroup.rows`, and give the silent rows `rowTone: 'muted'` plus the "Not seen for N weeks"
second line. The two-week threshold and the weeks calculation are pure and belong in
`src/lib/silentDevice.ts` (`SILENT_AFTER_MS`, `isSilent(lastSeenAt, now)`, `weeksSince(…)`), beside
`lib/review.ts`'s `STALE_COVERAGE_DAYS` precedent — not inline in a column renderer, so it can be
unit-tested at the boundary without rendering a table.

---

## 8. Migration risk — landing tokens before screens in one PR

The owner's decisions put the token change and the screen restyle in one PR. That is the right call
(a half-migrated design system is exactly the "temporary implementation" `.claude/CLAUDE.md`
forbids), but the ordering inside the PR is load-bearing, because **the gate cannot see a broken
style**. `npm run lint && format:check && typecheck && test && build` all pass while every heading
in the app silently loses its font. The risk is not a red build; it is a green build that is wrong.

**The atomicity rule: a token's deletion and its last consumer's removal are one commit.** Value
changes are safe alone; deletions are not.

| Deleted token | Last consumer | Must land together with |
| --- | --- | --- |
| `--font-title` | `font-title` in 29 files | the sweep of all 29 |
| `--text-nav` | `TopBar.tsx` | the TopBar rewrite |
| `--color-sev-*` | `SeverityBadge.tsx`, `StatusPill.tsx` | `SeverityWord` + `StatusPill` deletion + their 5 + 4 call sites |
| `--paper` → `--canvas` | `--background` alias in `index.css` | itself (no component names it) |

A commit order that keeps every commit green *and* correct:

1. **Tokens + lint + fonts + every retired-token consumer.** `index.css`, `package.json`, the six
   lint rules, `SeverityWord` in, `SeverityBadge`/`StatusPill`/`Ornament` out, all 29 `font-title`
   sites, `TopBar`'s `text-nav`. Big, and unavoidably so — that is what atomicity costs. Success
   criterion: the grep in §2.3 returns nothing.
2. **Primitives.** `components.json` + regeneration + the four local re-applications.
3. **`DataTable`, `Pagination`, `pageWindow`, `silentDevice`.** Shared components only; screens
   unchanged.
4. **Routes and the two renames** (`Network`, `Devices`) with every `Link` and testid swept.
5. **Box detail screen** (`DeviceDetail`, `ScanTypeTabs`, `scanModes`, `useScanCommand` signature,
   `AgentCard`/`useAgentScreen`/`usePrimaryAgent` deletion, the `useHomeReview` ripple).
6. **Home attention table.**
7. **Docs**: `FOUNDATIONS.md` §Scan settings edit, `FOUNDATIONS-DECISIONS.md` entry,
   `frontend-conventions` §Styling strip, the new `frontend-design-system` skill.

Commits 1 and 4 are the two that touch the most files and the two most likely to be reviewed as
"just a rename". Commit 1 is the one where a missed consumer is invisible.

**The other four risks, named:**

- **`html { font-mono }` → `font-sans`** flips the typeface of the entire application in one line.
  Every screenshot in every prior spec is stale from that commit onward.
- **`--radius: 0` → `0.75rem`** applies instantly to every bordered box through the shadcn ladder,
  including boxes nobody re-examined (`LoadingSkeleton` bars, `Toast`, the `EmptyMark` span's
  neighbours). Expect a visual sweep, not a diff review.
- **Four of the seven type tokens change value.** Nothing fails; everything reflows.
- **41 `toHaveClass` assertions are the only thing currently pinning any of this**, and they are all
  being deleted (§9). Between commit 1 and the rewritten assertions, the suite proves less about
  presentation than it did. Rewriting them as role / accessible-name / `data-testid` assertions
  **in the same commit as the component they guard** is what keeps that window closed.

---

## 9. New and changed files

Every path an implementer creates, renames or deletes. All paths relative to the repo root.

### Layer 0 — tokens and lint

| Path | Action | Purpose |
| --- | --- | --- |
| `frontend/src/index.css` | change | New token values; delete `--font-title`, `--text-nav`, `--color-sev-*`; `--radius: 0.75rem` + `--control-radius`; Inter/Geist Mono imports; `@utility h-row`; `html` → `font-sans`; keep the `dark` neutraliser. |
| `frontend/package.json` | change | Add `@fontsource-variable/inter` + Geist Mono Variable; remove `@fontsource/im-fell-english`, `@fontsource/ibm-plex-mono`. |
| `frontend/eslint.config.js` | change | Register `local/no-raw-hex` and `local/no-dark-variant` at `error`. |
| `frontend/eslint-rules/index.js` | change | Export the two new rules. |
| `frontend/eslint-rules/no-raw-hex.js` | **new** | Ban hex/`rgb()`/`hsl()` literals in authored class strings and `style` values. |
| `frontend/eslint-rules/no-raw-hex.test.js` | **new** | Rule tests, mirroring `no-raw-type-size.test.js`. |
| `frontend/eslint-rules/no-dark-variant.js` | **new** | Ban the `dark:` prefix in authored class strings. |
| `frontend/eslint-rules/no-dark-variant.test.js` | **new** | Rule tests. |
| `frontend/eslint-rules/no-raw-type-size.js` | change | Re-key `TYPE_SIZES` to the new pixel values. |
| `frontend/eslint-rules/no-raw-type-size.test.js` | change | Expectations follow the re-keyed map. |
| `frontend/eslint-rules/no-arbitrary-utility.js` | change | Drop `text-nav` from the message. |
| `frontend/eslint-rules/no-arbitrary-utility.test.js` | change | Message assertion follows. |
| `frontend/eslint-rules/spacing-scale.js` | change | Cite `FOUNDATIONS.md` §Spacing. |
| `frontend/eslint-rules/spacing-scale.test.js` | change | Message assertion follows. |
| `frontend/eslint-rules/no-bare-interactive.js` | change | Cite `FOUNDATIONS.md` §Interaction states. |
| `frontend/eslint-rules/no-bare-interactive.test.js` | change | Message assertion follows. |
| `frontend/eslint-rules/class-strings.js` | unchanged | Shared visitor; the two new rules reuse it. |

### Layer 1 — primitives

| Path | Action | Purpose |
| --- | --- | --- |
| `frontend/components.json` | change | `"style": "radix-nova"` → `"radix-maia"`. |
| `frontend/src/components/ui/button.tsx` | regenerate | Re-apply the `link`/`outline`/`ghost` variants and the explicit `cursor-pointer`. |
| `frontend/src/components/ui/input.tsx` | regenerate | — |
| `frontend/src/components/ui/label.tsx` | regenerate | — |
| `frontend/src/components/ui/select.tsx` | regenerate | Re-check the ghost inline-cell trigger alignment. |
| `frontend/src/components/ui/card.tsx` | **new** | FOUNDATIONS §Cards & sections. |
| `frontend/src/components/ui/tabs.tsx` | **new** | The scan-type segmented control. |
| `frontend/src/components/ui/pagination.tsx` | **new** | FOUNDATIONS §Pagination. |
| `frontend/src/components/ui/dialog.tsx` | **new** | Backs `DialogShell`. |

### Layer 2 — shared components

| Path | Action | Purpose |
| --- | --- | --- |
| `frontend/src/components/DataTable.tsx` | change | 56px `h-row` rows, Lucide sort markers, `rowTone`, `collapsedGroup`. |
| `frontend/src/components/SeverityWord.tsx` | **new** | Bold severity word in primary ink; em-dash when null. |
| `frontend/src/components/SeverityBadge.tsx` | **delete** | Replaced by `SeverityWord`. |
| `frontend/src/components/StatusPill.tsx` | **delete** | Status becomes plain muted text. |
| `frontend/src/components/StatusPill.test.tsx` | **delete** | — |
| `frontend/src/components/Ornament.tsx` | **delete** | Retired decoration. |
| `frontend/src/components/Ornament.test.tsx` | **delete** | — |
| `frontend/src/components/Pagination.tsx` | change | Composes `ui/pagination`; icon-only prev/next, page numbers, no range line. |
| `frontend/src/components/TopBar.tsx` | change | Nav names/routes, bold-active, `Dmitri` wordmark, user's name, no `text-nav`. |
| `frontend/src/components/AppShell.tsx` | change | Token/class only. |
| `frontend/src/components/AuthShell.tsx` | change | Ornament removed; token/class only. |
| `frontend/src/components/EmptyState.tsx` | change | Ornament removed. |
| `frontend/src/components/PageHeader.tsx` | change | `font-title` removed. |
| `frontend/src/components/DialogShell.tsx` | change | Composes `ui/dialog`; props unchanged. |
| `frontend/src/components/FirstScanCta.tsx` | change | `/agents` → `/devices`. |
| `frontend/src/components/Disclosure.tsx` | change | Token/class only. |
| `frontend/src/components/ConfirmByTyping.tsx` | change | Token/class only. |
| `frontend/src/components/Toast.tsx` | change | Token/class only. |
| `frontend/src/components/ErrorRetry.tsx` | change | `font-title` removed. |
| `frontend/src/components/NotFoundNotice.tsx` | change | `font-title` removed. |
| `frontend/src/components/LoadingSkeleton.tsx` | change | Bar height follows the 56px row. |
| `frontend/src/components/ListSurface.tsx` | change | Pass-through for `rowTone` / `collapsedGroup`; no state change. |
| `frontend/src/components/ReadDetailGate.tsx` | change | Token/class only. |
| `frontend/src/components/AdminOnly.tsx`, `EmptyMark.tsx`, `Timestamp.tsx` | unchanged | — |

### Layer 3 — libs, hooks, API

| Path | Action | Purpose |
| --- | --- | --- |
| `frontend/src/lib/scanModes.ts` | **new** | `SCAN_MODE_ORDER` / `_LABEL` / `_DESCRIPTION` / `DEFAULT_SCAN_MODE`. |
| `frontend/src/lib/silentDevice.ts` | **new** | `SILENT_AFTER_MS`, `isSilent()`, `weeksSince()`. |
| `frontend/src/lib/pageWindow.ts` | **new** | `pageWindow(page, pageCount)` → numbers + `'ellipsis'`. |
| `frontend/src/lib/scanStatus.ts` | change | `scanStatusPill` → `scanStatusLabel`; `ScanStatusTone` deleted. |
| `frontend/src/lib/commandStatus.ts` | change | Same; drops the `StatusPillTone` import. |
| `frontend/src/api/agents.ts` | change | Delete `QUICK_SCAN_MODE`. |
| `frontend/src/api/queryKeys.ts` | unchanged | `agents.list()` / `agents.detail()` already fit. |
| `frontend/src/hooks/useScanCommand.ts` | change | `trigger(scanMode: ScanMode)`. |
| `frontend/src/hooks/usePrimaryAgent.ts` | **delete** | No caller after Home and the Devices screens are re-pointed. |
| `frontend/src/hooks/useAgentScreen.ts` | **delete** | Replaced by `ReadDetailGate` + a plain list query. |
| `frontend/src/hooks/useHomeReview.ts` | change | Reads `listAgents` directly; `agent` narrows to `AgentSummary`. |
| `frontend/src/hooks/useUpdateTargetSubnet.ts` | unchanged | — |

### Layer 3 — routes and screens

| Path | Action | Purpose |
| --- | --- | --- |
| `frontend/index.html` | change | `<title>` → `Dmitri`. |
| `frontend/src/App.tsx` | change | `/network`, `/network/:hostId`, `/devices`, `/devices/:agentId`; no redirects. |
| `frontend/src/pages/Hosts.tsx` → `frontend/src/pages/Network.tsx` | rename + change | Network list; adds the silent-device split. |
| `frontend/src/pages/HostDetail.tsx` | change | Restyle + link sweep; keeps its API-noun name. |
| `frontend/src/pages/hosts/hostListColumns.tsx` | change | `SeverityWord`; silent second line. |
| `frontend/src/pages/hosts/HostFindings.tsx`, `HostIdentity.tsx`, `HostPortsTable.tsx`, `HostScanHistoryTable.tsx`, `portColumns.tsx` | change | Restyle, vocabulary, `SeverityWord`. |
| `frontend/src/pages/Agents.tsx` → `frontend/src/pages/Devices.tsx` | rename + rewrite | Box list over `listAgents`; `DataTable` + `EmptyState` + `ErrorRetry`, no `ListSurface`. |
| `frontend/src/pages/DeviceDetail.tsx` | **new** | Box detail screen at `/devices/:agentId`. |
| `frontend/src/pages/agents/deviceListColumns.tsx` | **new** | Name · network · status · last reported. |
| `frontend/src/pages/agents/ScanTypeTabs.tsx` | **new** | `ui/tabs` segmented control + the one-line description; admin-only. |
| `frontend/src/pages/agents/AgentCard.tsx` | **delete** | Its body is now the detail screen. |
| `frontend/src/pages/agents/AgentsBlank.tsx` → `frontend/src/pages/agents/DevicesBlank.tsx` | rename | No-box empty state. |
| `frontend/src/pages/agents/AgentIdentity.tsx` | change | `font-title` removed. |
| `frontend/src/pages/agents/ScanControl.tsx` | change | Takes and forwards the selected `ScanMode`. |
| `frontend/src/pages/agents/CommandStatus.tsx` | change | `StatusPill` → text; `commandStatusLabel`. |
| `frontend/src/pages/agents/TargetSubnetSection.tsx`, `SubnetChooser.tsx` | change | Restyle only; API unchanged. |
| `frontend/src/pages/Home.tsx` | change | Attention table replaces the deck. |
| `frontend/src/pages/home/AttentionTable.tsx` | **new** | Vulnerability · Device · Severity over `deckFindings`. |
| `frontend/src/pages/home/AttentionNotices.tsx` | **new** | Failed-scan and stale-coverage one-liners (were `ReviewItemCard`). |
| `frontend/src/pages/home/FindingDeck.tsx` | **delete** | Retired. |
| `frontend/src/pages/home/FindingDeck.test.tsx` | **delete** | Retired. |
| `frontend/src/pages/home/ReviewItemCard.tsx` | **delete** | Retired. |
| `frontend/src/pages/home/Verdict.tsx` | change | Becomes the count/quiet title line. |
| `frontend/src/pages/home/HomeFooter.tsx` | change | `agent` prop `AgentDetail` → `AgentSummary`. |
| `frontend/src/pages/home/HomeBlank.tsx`, `HomeError.tsx` | change | Ornament + `font-title` removed. |
| `frontend/src/pages/Scans.tsx`, `ScanDetail.tsx` | change | Restyle, vocabulary, link sweep. |
| `frontend/src/pages/scans/scanListColumns.tsx`, `findingColumns.tsx`, `FindingsTable.tsx`, `FindingPanel.tsx`, `ScanDetailHeader.tsx`, `ScanFailedNotice.tsx`, `ScanUnfinishedNotice.tsx`, `ScanHostsTable.tsx` | change | `SeverityWord`, status text, *finding* → *Vulnerability*, `/hosts` → `/network`. |
| `frontend/src/pages/Users.tsx`, `users/DirectoryTable.tsx`, `InviteDialog.tsx`, `RoleChangeDialog.tsx`, `RevokeDialog.tsx`, `RemoveMemberDialog.tsx` | change | Restyle; re-check the inline `Select` trigger after regeneration. |
| `frontend/src/pages/Settings.tsx`, `settings/AccountDetails.tsx`, `PasswordDialog.tsx` | change | Restyle. |
| `frontend/src/pages/Login.tsx`, `ForgotPassword.tsx`, `ResetPassword.tsx`, `AcceptInvite.tsx`, `NotFound.tsx` | change | Restyle; `font-title` removed. |

### Docs and skills

| Path | Action | Purpose |
| --- | --- | --- |
| `docs/ui/FOUNDATIONS.md` | change | §Scan settings: the block moves from the Scans page to the box detail screen. Also needs the §Vocabulary *device*/*box* correction — see the §6 flag. |
| `docs/ui/FOUNDATIONS-DECISIONS.md` | change | Record why the scan-settings block moved (per box, several boxes per customer). |
| `.claude/skills/frontend-conventions/SKILL.md` | change | §Styling stripped; points at the new skill. Also drop the "Four local lint rules" line — there are six — and the "Until DMI-132 lands" caveat. |
| `.claude/skills/frontend-design-system/SKILL.md` | **new** | The styling half, keyed to the shipped tokens. |
| `.claude/docs/frontend/*.md` | change | Code-map refresh — `tables.md`, `screens.md`, `agents-screen.md`, `linting.md`, `review.md`, `index.md`. Owned by `/docs-sync` at the end of the pipeline, not by the implementer mid-feature. |

---

## 10. Testing expectations

Vitest + Testing Library + MSW, run from `frontend/` as part of
`npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build`.

### 10.1 The `toHaveClass` sweep

All **41** assertions are deleted. Distribution, so nobody has to go looking:

| File | Count | What replaces it |
| --- | --- | --- |
| `src/components/TopBar.test.tsx` | 12 | Active nav asserted via `aria-current="page"` on the `NavLink`, plus the nav item's accessible name. Bold-vs-not is a visual fact, not a behavioural one — do not re-assert it as a class. |
| `src/pages/Agents.test.tsx` | 9 | Nothing — these guarded the card's layout classes. Behaviour moves to `DeviceDetail.test.tsx` (§10.3). |
| `src/components/DataTable.test.tsx` | 7 | Row height asserted once, on the `h-row` utility being present on a row, as the single deliberate exception (it is the only 56px assertion FOUNDATIONS makes testable); everything else becomes role/name assertions. |
| `src/components/Disclosure.test.tsx` | 5 | `aria-expanded` and content visibility, both already asserted elsewhere in the file. |
| `src/components/Ornament.test.tsx` | 3 | File deleted. |
| `src/components/Pagination.test.tsx` | 2 | `getByRole('button', { name: 'Previous page' })` and its `disabled` state. |
| `src/components/StatusPill.test.tsx` | 1 | File deleted. |
| `src/pages/Users.test.tsx` | 1 | `data-testid` on the row already present. |
| `src/pages/Scans.test.tsx` | 1 | Status asserted by its text. |

The rule to apply when deciding which of the 41 "guard real behaviour": a class assertion earns a
rewrite only if removing it would let a *user-visible* behaviour regress silently — a disabled
control staying clickable, a hidden panel staying in the accessibility tree, a row losing its link.
A class that only names a colour, a font or a spacing step is deleted outright; FOUNDATIONS plus
the lint rules own that, and a test that restates a class string is a second, weaker copy of the
design system.

### 10.2 MSW fixtures — `src/test/mswHandlers.ts`

This is the file that gates most of the new tests, and it needs real work:

- **Multi-agent fixtures.** Today there is exactly one agent (`defaultAgent`), `GET /agents` returns
  `{ data: [defaultAgent] }`, and `GET /agents/:agentId` returns `defaultAgent` **regardless of the
  id in the path**. The Devices list and the box detail route cannot be tested against that. Add:
  - `agentSummaries: AgentSummary[]` — at least three boxes: one online with a `target_subnet`; one
    online with `target_subnet: null` (the "no network chosen yet" cell, and the AC where the
    chooser opens and Scan now is absent); one offline with an old `last_seen_at`.
  - `agentDetails: AgentDetail[]` keyed by `agent_id`, `defaultAgent` among them.
  - `GET /agents` returns `{ data: agentSummaries }`; `GET /agents/:agentId` **looks up by
    `params.agentId`** and returns 404 for an unknown id, so `readDetailState`'s notFound branch is
    reachable. `PATCH /agents/:agentId` echoes the looked-up agent, not `defaultAgent`.
- **A silent host.** `hostFixtures`' oldest `last_seen_at` is about four hours ago; nothing in the
  set can be silent. Add a `weeksAgo(n)` helper beside `minutesAgo` and make two fixtures ~3 and ~6
  weeks old. Default sort is `last_seen_at desc`, so they land at the end of page 1 and the
  collapsed group is exercised without changing `total` (still 25) or any pagination expectation.
- **`POST /agents/:agentId/commands` must echo the request's `scan_mode`.** It currently ignores the
  body. Without this, "Scan now uses the selected type" is unassertable.

`src/test/agentsHarness.ts` gains `agentList(summaries)` and keeps `agentDetail(agent)`,
`noAgents()`, `agentsFail()`, `commandStatuses()`, `commandRefused()`, `withActiveCommand()` — all
still used by the box detail tests.

`src/test/renderWithProviders.tsx` — check every `initialEntries` for `/hosts` and `/agents`.

### 10.3 Per-area expectations

**Tokens and lint** — `eslint-rules/no-raw-hex.test.js` and `no-dark-variant.test.js` are new,
mirroring `no-raw-type-size.test.js`'s `RuleTester` shape: a valid case, an invalid case per
message id, and a case proving the vendored/test exemptions are not needed inside the rule itself
(they live in the config). `no-raw-type-size.test.js` changes because the size→token map changed;
the other three rule tests change only where they assert message text.

**`DataTable`** — `DataTable.test.tsx` is the most-changed test file in the feature. New cases:
a row renders at the fixed height; a sortable header renders a Lucide marker and the correct
`aria-sort` in all three states (asserted by `aria-sort`, never by the icon); `rowTone: 'muted'`
rows still expose their link; the `collapsedGroup` row renders last, is closed initially with
`aria-expanded="false"`, expands on click and on Enter, and its member rows are absent from the
accessibility tree while closed. Keep the existing rule: **click the row's link, not the `<tr>`** —
jsdom does no layout, so the stretched overlay covers nothing.

**`SeverityWord`** — new `SeverityWord.test.tsx`: each of the four severities renders its word; null
renders the em dash; **no element in the output carries a severity-specific class or inline colour**
(the one negative assertion worth keeping, because it is the acceptance criterion).

**`Pagination`** — `Pagination.test.tsx` loses its class assertions and gains: prev/next are found
by the accessible names "Previous page" / "Next page"; the words *Previous* and *Next* are absent
from the DOM; page numbers render and clicking one calls `onPageChange` with that page. New
`src/lib/pageWindow.test.ts` covers the ellipsis arithmetic as a pure function — table-driven, no
rendering.

**`silentDevice`** — new `src/lib/silentDevice.test.ts`: the boundary either side of two weeks and
the weeks rounding, with an injected `now` (the `deriveReview({ now })` precedent). No fake timers.

**Devices list** — `src/pages/Agents.test.tsx` → `src/pages/Devices.test.tsx`. Rewritten, not
edited: every box in `agentSummaries` renders as a row with its four cells; a box with no target
subnet shows the muted "no network chosen" copy and no error styling; clicking a row navigates to
`/devices/:id` (assert with `LocationProbe`, which already exists); `noAgents()` renders the blank
state; `agentsFail()` renders the error with a working retry.

**Box detail** — `Agents.command.test.tsx` → `src/pages/DeviceDetail.command.test.tsx`,
`Agents.invalidation.test.tsx` → `DeviceDetail.invalidation.test.tsx`, plus a new
`DeviceDetail.test.tsx`. Cases that must exist:
- an unknown `:agentId` renders the not-found block (newly reachable, thanks to the id lookup);
- the five scan-type tabs render with the five real modes, selecting one changes only the
  description and issues **no** request;
- Scan now posts the **selected** mode — assert on the intercepted request body, which is why the
  handler must echo `scan_mode`;
- navigating away and back resets the selection to `DEFAULT_SCAN_MODE`;
- a viewer sees the network and type as text with the change/select/scan controls **absent** (query
  by role and assert null, per absent-not-disabled);
- a box with no target subnet opens the chooser and renders no Scan now;
- the command-status region replaces Scan now and takes focus — the existing focus assertion in
  `Agents.command.test.tsx` carries over unchanged;
- the post-`done` invalidation sweep — `DeviceDetail.invalidation.test.tsx` keeps its current
  assertions; only the mount path changes.

**Home** — `Home.test.tsx` loses every deck assertion (`home-deck`, `home-deck-card`, the `←`/`→`
keyboard cases) and gains: the attention table lists the critical and high findings with
vulnerability, device and severity; a row navigates to the finding's scan; the clear state renders
the title **and no table and no card** (a `queryBy… === null` assertion, since "nothing is rendered
at all" is the acceptance criterion); the failed-scan and stale-coverage notices still appear as
sentences. `useHomeReview.test.ts` changes where it stubs the agent read — one query now, not two.
`pages/home/FindingDeck.test.tsx` is deleted.

**Network list** — `Hosts.test.tsx` → `Network.test.tsx`. Keeps every sort and pagination case
(none of that behaviour changes) and gains: a host unseen for weeks renders inside the collapsed
"Not seen recently (2)" group, muted, with its "Not seen for N weeks" second line; the group expands
on activation; recent hosts are outside it. Route assertions move to `/network`.

**Routing and chrome** — `App.test.tsx`: `/network` and `/devices` render their screens,
`/devices/:id` renders the detail screen, and **`/hosts` and `/agents` render NotFound** (the
acceptance criterion is that they are gone, so assert it, do not just delete the old cases).
`TopBar.test.tsx`: the six nav names in order, `Users` absent for a viewer (already covered), active
item via `aria-current`, wordmark text `Dmitri`.

**Everything else** — `Scans.test.tsx`, `ScanDetail.test.tsx`, `HostDetail.test.tsx`,
`Users.test.tsx`, `Settings.test.tsx` and the auth-screen tests change only where they assert a
severity badge, a status pill, a `/hosts`|`/agents` URL, or the word *finding*.
`lib/commandStatus.test.ts` and `lib/scanStatus.test.ts` drop `tone` from their expectations.
`src/api/client.test.ts` references an `/agents` URL as request-plumbing only — check it, but it is
not a route assertion.

### 10.4 What no test should assert

Colour, font family, spacing step, radius, or any class string other than the single `h-row`
exception in §10.1. FOUNDATIONS is the source of truth for those and the lint rules are the gate; a
test that re-states them is a copy that will drift.

---

## 11. `HUMAN_INFRA_REQUIRED`

None. No new hardware, daemon, service, environment variable or external tool. Two npm packages are
added and two removed; `npm install` covers it.

---

## 12. Open questions for the owner

Each of these is flagged in place above; collected here so none is lost.

1. ~~**`device` vs `box` (§6).**~~ **Resolved by the owner, 2026-09-02, in Foundations' favour:** a
   **device** is the Dmitri box; a thing on the customer's network is a **machine**. `TRUTH.md` and
   `DESIGN.md` §3–§7 are updated; `FOUNDATIONS.md` §Tables' "Silent devices" is corrected in Task 12.
2. **No stored default scan type (§5.1).** `AgentDetail` has no `default_scan_mode`. Two acceptance
   criteria reference "the box's default"; implemented against a client constant until DMI-133.
3. ~~**`ui/tooltip.tsx` has no call site (§3).**~~ **Resolved:** `DESIGN.md` names no tooltip on
   any of the ten screens. Dropped from the generation list.
4. **`informational` severity (§4.2).** In FOUNDATIONS, not in the generated `Severity` union.
5. **Silent-device grouping is per-page (§4.1).** `(N)` counts the current page, not the inventory.
6. **`Not seen recently` is a `DataTable` pattern used by exactly one table.** It is specified as a
   shared pattern by FOUNDATIONS §Tables, which is why it lives in `DataTable` rather than in
   `Network.tsx` — but it has one caller today, and a single-caller abstraction is normally a smell.
   Named here so the reviewer sees it was a decision, not an oversight.
