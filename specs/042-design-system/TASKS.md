# Tasks — Design system v2 and the restyle onto it (`042-design-system`)

12 tasks. **All tasks COMPLETED** — pipeline done; human tail: `nuke` → `commit` → `create-pr`

> **This feature's blast radius is `frontend/` only.** The Python agents do not apply.
> Spawn **`frontend-test-engineer`** (not `test-engineer`) and **`frontend-code-reviewer`**
> (not `code-reviewer`). The gate for every task is run from `frontend/`:
>
> ```
> npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
> ```
>
> `uv run pytest` and `uv run ruff check` are not gates here — no Python changes in this feature.
> The `.claude/CLAUDE.md` `ScanRunner` / `ScanProgressScreen` threading rule concerns the Textual
> TUI and does not apply (see `ARCHITECTURE.md` §Scope note).

## Rules that apply to every task

1. **`toHaveClass` assertions are deleted, never exempted.** Each task removes the class
   assertions for the files it touches, rewriting only those that guard real behaviour as role,
   accessible-name or `data-testid` assertions (`ARCHITECTURE.md` §8). 41 across the suite at the
   start; zero at the end.
   **Ruling, reviewer, Task 2, 2026-09-03: the obligation follows the *test file*, not the
   component the test renders.** A task owes the deletions only for test files in its own Target
   Files, or that it had to edit to keep the suite green. Ledger after Task 2 — 24 remain:
   `DataTable.test.tsx` 7 and `Pagination.test.tsx` 2 → **Task 4**; `Agents.test.tsx` 9 →
   **Task 9**; `Disclosure.test.tsx` 5 and `Users.test.tsx` 1 → **Task 11** (assigned here so they
   are not stranded at the end).
   **Ruling, reviewer, Task 3, 2026-09-03 — paying a ledger re-expresses the guarantee, it does
   not delete it.** The `radix-maia` regeneration added `data-variant` / `data-size` on `Button`
   and `data-slot` on every primitive: stable DOM attributes, not class strings. So Task 4 rewrites
   its `link`-variant pin as `toHaveAttribute('data-variant', 'link')`, and Task 9 does the same
   for the variants it asserts. **`cursor-pointer` and `focus-visible:ring-3` are not
   re-expressible** — CSS-only, and jsdom computes no pseudo-class styling. Neither task may
   substitute a class assertion for them; their guard is the Chrome visual pass. Say so in the
   task's notes rather than letting the coverage lapse silently.
2. **Nothing renders without data behind it** (`TRUTH.md`). No placeholder columns, no em-dash
   stand-ins for absent fields. The list of what is deliberately not drawn is `DESIGN.md` §16.
3. **No new `dark:` classes, no raw hex, no off-scale spacing.** Task 1 makes the linter enforce
   this; later tasks must not add suppressions.
4. **Tasks 1 and 2 land as one commit.** Splitting them leaves the app visually broken with a
   green suite — see `ARCHITECTURE.md` §8. They are two tasks because they carry different tests,
   not because they ship separately.

5. **Tasks 8 and 9 land as one commit.** *Ruling, reviewer, Task 5, 2026-09-04.* Task 5 does not
   owe `/devices/:agentId`: its element `pages/DeviceDetail.tsx` is Task 9's file, and a stub is
   exactly the temporary code `.claude/CLAUDE.md` §No temporary code forbids. **Task 9 adds both
   `pages/DeviceDetail.tsx` and its `<Route path="/devices/:agentId">` in `App.tsx`** — `App.tsx`
   joins Task 9's Target Files. Task 8's device rows open that path, and a control that navigates
   nowhere cannot be approved alone, so 8 and 9 ship together on the rule-4 precedent.

6. **Never substitute a class assertion for a CSS-only state.** *Ruling, reviewer, Task 5,
   2026-09-04*, extending the Task 3 ruling to every later task. `font-bold`, `hover:font-bold`,
   the absence of `border-b-2`, `justify-self-center`, `cursor-pointer` and `focus-visible:ring-3`
   are class strings jsdom does not compute; pinning them is exactly the `toHaveClass` rule 1
   deletes. Assert `aria-current`, role, accessible name or a `data-*` attribute instead, and name
   in the task notes what the Chrome visual pass owns. A test that clones a DOM node and asserts
   the clone exists is hollow — delete it, do not rewrite it as another DOM walk.

7. **A repo-wide `rg` success criterion outranks the per-task Target Files for the strings it
   matches.** *Ruling, reviewer, Task 5, 2026-09-04.* Task 5's `\bfinding` criterion is scoped to
   all of `frontend/src`, so `ScanUnfinishedNotice.tsx:18` was correctly swept there though Task 7
   owns the file. Task 7 inherits the swept copy and must not re-litigate it; it still owns that
   file's restyle in every other respect.

8. **A shared component may absorb the minimal edit its consumer's spec forces, when the
   alternative is a prop.** *Ruling, reviewer, Task 6, 2026-09-04.* `DataTable.tsx:143` dropped
   `truncate` from the link-cell wrapper so a multi-line first cell can render; truncation belongs
   to the column render, which already carries its own. A `multiline?` prop for one caller would be
   the over-abstraction. **Standing consequence: a first column under `kind: 'link'` owns its own
   `truncate` — `DataTable` no longer supplies one.**

9. **A page reads its own data through the canonical query key, even when another page reads it
   too.** *Ruling, reviewer, Task 6, 2026-09-04.* TanStack Query's cache is the dedupe mechanism, so
   a shared key is reuse, not duplication — `Network` and `useHomeReview` share
   `queryKeys.scans.latest('completed')` and are one cache entry in the running app. Never drop a
   spec'd read to flatten a test's request counter.

10. **A clock read in a render body is accepted where every consumer's granularity is a day or
    coarser.** *Ruling, reviewer, Task 6, 2026-09-04.* `Network.tsx:27`'s `new Date()` feeds a
    14-day boundary and a 7-day floor and cannot tear across a commit; stabilising it with
    `useMemo`/`useState` is machinery with no user-visible effect. Anything at second granularity,
    or that must not tear across a concurrent re-render, states its epoch explicitly instead.

## Vocabulary, settled by the owner 2026-09-02

A **device** is the **Dmitri box** — the unit on site that runs scans, listed under `Devices`.
A thing found **on the customer's network** is a **machine**, listed under `Network`. Reader-facing
copy never calls a machine a device. `TRUTH.md`, `DESIGN.md` §3–§7 and `ARCHITECTURE.md` §12 are
already updated; `FOUNDATIONS.md` §Tables ("Silent devices") is corrected in Task 12.

Also settled: the top bar ships the **email**, truncated with an ellipsis when it crowds the bar,
full value in `title` (Task 5, and the `FOUNDATIONS.md` §Chrome edit in Task 12). Home's attention
table names a machine by its **address** (Task 10). Settings **keeps** its Activity disclosure and
`Delete my account` loses its red fill; the flow is **already a modal** — `ConfirmByTyping`
composes `DialogShell` — so it is restyled, not rebuilt (Task 11).

## Settled: page-local quiet grouping is accepted for v1

Owner, 2026-09-02. `GET /hosts` paginates the customer's machines at 20 with no quiet/active
split, so `Not seen recently (N)` counts the machines quiet **on the page being viewed**. The
default `last_seen_at desc` sort sinks quiet machines to the last page, so the common case reads
correctly; an organisation past 20 machines can see the group on more than one page. The
server-side split belongs to the machine-inventory follow-up issue. Task 6 ships the group row.

**No decisions remain open.**

---

## Task 1: Tokens, fonts and the six lint rules
- **Description**: Replace the token layer in `frontend/src/index.css` with the `FOUNDATIONS.md`
  values — the seven-token type scale (`--text-nav` deleted), the eight colour tokens
  (`--color-sev-*` deleted), `--radius: 0.75rem` + `--control-radius: 0.5rem`, the nine-step
  spacing scale, the motion tokens and the `prefers-reduced-motion` block, `--container-frame` /
  `--container-form`, and the `h-row` utility at 56px. `--font-title` is deleted and `html`
  flips from `font-mono` to `font-sans`. **Keep the `dark` custom-variant neutraliser**
  (`FOUNDATIONS.md` §Theme). Re-key the four existing lint rules to the new token names and add
  `no-raw-hex` and `no-dark-variant`, the latter exempting `src/components/ui/**` because the
  regenerated primitives ship `dark:` utilities. Per `ARCHITECTURE.md` §2.
- **Absorbed**: `frontend/package.json` dependency swap (`@fontsource-variable/inter` and Geist
  Mono Variable in; `@fontsource/im-fell-english` and `@fontsource/ibm-plex-mono` out) and the
  `main.tsx` font imports — a dependency edit carries no test of its own and is exercised by the
  token layer that consumes it.
- **Dependencies**: —
- **Target Files**: [`frontend/src/index.css`, `frontend/package.json`, `frontend/src/main.tsx`, `frontend/eslint-rules/no-raw-type-size.js`, `frontend/eslint-rules/spacing-scale.js`, `frontend/eslint-rules/no-arbitrary-utility.js`, `frontend/eslint-rules/no-bare-interactive.js`, `frontend/eslint-rules/class-strings.js`, `frontend/eslint-rules/index.js`, `frontend/eslint-rules/no-raw-hex.js`, `frontend/eslint-rules/no-dark-variant.js`, `frontend/eslint-rules/no-raw-type-size.test.js`, `frontend/eslint-rules/spacing-scale.test.js`, `frontend/eslint-rules/no-arbitrary-utility.test.js`, `frontend/eslint-rules/no-bare-interactive.test.js`, `frontend/eslint-rules/no-raw-hex.test.js`, `frontend/eslint-rules/no-dark-variant.test.js`, `frontend/eslint.config.js`]
- **Tests**: the six `frontend/eslint-rules/*.test.js` suites — each proves its rule reports the
  retired token or raw value and accepts the new one, and that `no-dark-variant` does not fire
  inside `src/components/ui/**`.
- **Success Criteria**:
  - `rg -- '--font-title|--text-nav|--color-sev-|--paper' frontend/src/index.css` returns nothing.
  - `rg -- 'im-fell|plex-mono' frontend/package.json frontend/src` returns nothing.
  - The `dark` custom-variant neutraliser is still present in `index.css`.
  - `npm run lint` reports the new rules firing on a deliberately bad fixture and clean otherwise;
    the six rule suites pass.
  - `TRUTH.md` criterion *"Motion respects the reader"* holds: a global
    `prefers-reduced-motion: reduce` block drops non-essential animation to `0.01ms`, and no
    duration is written inline in a component.
  - The build succeeds. The app is expected to look wrong until Task 2 lands with it.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Severity, status and ornament retired; the `font-title` sweep
- **Description**: Add `SeverityWord` (bold `--ink` label, em-dash when null) and delete
  `SeverityBadge`, `StatusPill` (+ its test) and `Ornament` (+ its test). Scan and command status
  become plain text: `lib/scanStatus.ts` and `lib/commandStatus.ts` drop their tone types
  (`scanStatusPill` → `scanStatusLabel`, `commandStatusPill` → `commandStatusLabel`); the
  `StatusPillTone` import in `commandStatus.ts` is the one that breaks the build first. Sweep all
  29 `font-title` call sites and `TopBar`'s `text-nav`. Per `ARCHITECTURE.md` §4.1–4.3 and
  `DESIGN.md` §2.2. **Lands in the same commit as Task 1.**
- **Dependencies**: Task 1
- **Status note**: Task 1 approved 2026-09-03. `--destructive` stays as a permanent alias of
  `var(--ink)` (21 authored form-error call sites, none of them severity, none removed by Task 11);
  do not delete it in this task.
- **Target Files**: [`frontend/src/components/SeverityWord.tsx`, `frontend/src/components/SeverityWord.test.tsx`, `frontend/src/components/SeverityBadge.tsx`, `frontend/src/components/StatusPill.tsx`, `frontend/src/components/StatusPill.test.tsx`, `frontend/src/components/Ornament.tsx`, `frontend/src/components/Ornament.test.tsx`, `frontend/src/lib/scanStatus.ts`, `frontend/src/lib/commandStatus.ts`, `frontend/src/components/PageHeader.tsx`, `frontend/src/components/ErrorRetry.tsx`, `frontend/src/components/NotFoundNotice.tsx`, `frontend/src/components/EmptyState.tsx`, `frontend/src/components/AuthShell.tsx`, `frontend/src/pages/agents/AgentIdentity.tsx`, `frontend/src/pages/agents/CommandStatus.tsx`, `frontend/src/pages/home/HomeBlank.tsx`, `frontend/src/pages/home/HomeError.tsx`, `frontend/src/pages/hosts/hostListColumns.tsx`, `frontend/src/pages/scans/scanListColumns.tsx`, `frontend/src/pages/scans/findingColumns.tsx`]
- **Tests**: `SeverityWord.test.tsx` proves each severity renders as its word with no chip, badge
  or severity-coloured element and that a null severity renders the em-dash; the updated
  `scanStatus` / `commandStatus` consumers assert status by visible text, not by tone.
- **Success Criteria**:
  - `rg -- 'font-title|text-nav|SeverityBadge|StatusPill|Ornament' frontend/src` returns nothing.
  - No `sev-critical` / `sev-high` / `sev-medium` / `sev-low` class survives anywhere.
  - `TRUTH.md` criterion *"Severity reads as a word"* holds on every screen that renders one.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: shadcn primitives regenerated from `radix-maia`
- **Description**: Switch `components.json` `style` from `radix-nova` to `radix-maia`, regenerate
  `ui/button`, `ui/input`, `ui/label`, `ui/select`, and generate `ui/card`, `ui/tabs`,
  `ui/pagination`, `ui/dialog`. Re-apply the local edits the regeneration overwrites — the
  `link` / `outline` / `ghost` button variants, the explicit `cursor-pointer`, and the ghost
  inline-cell `Select` trigger alignment. `DialogShell` composes `ui/dialog` with its public props
  (`open`, `onOpenChange`, `testId`, `size`, `locked`, `initialFocusRef`) unchanged. **Tooltip is
  not generated** — no screen in `DESIGN.md` uses one. Per `ARCHITECTURE.md` §3.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/components.json`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/src/components/ui/label.tsx`, `frontend/src/components/ui/select.tsx`, `frontend/src/components/ui/card.tsx`, `frontend/src/components/ui/tabs.tsx`, `frontend/src/components/ui/pagination.tsx`, `frontend/src/components/ui/dialog.tsx`, `frontend/src/components/DialogShell.tsx`, `frontend/src/components/DialogShell.test.tsx`]
- **Tests**: `DialogShell.test.tsx` proves the four modal call sites still open, trap focus, close
  on `Escape` when unlocked and refuse to when locked — the regression that a regenerated
  primitive would break silently.
- **Success Criteria**:
  - `components.json` reads `"style": "radix-maia"`; no `ui/tooltip.tsx` exists.
  - Every existing dialog, select and button suite passes untouched.
  - Buttons carry an explicit `cursor-pointer`; no `outline: none` anywhere. **Reviewer ruling,
    2026-09-03**: the literal grep is unsatisfiable — `outline-none` + `focus-visible:ring-3` is
    the repo-wide idiom and already lives in authored files (`Disclosure.tsx:36`,
    `DataTable.tsx:120,143,200`). The enforceable form is *no control loses its focus affordance*.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: `DataTable`, `Pagination`, and the silent-device pattern
- **Description**: `DataTable` gains fixed 56px rows via the `h-row` utility, Lucide chevron sort
  markers with `aria-sort` unchanged, `rowTone?: (row) => 'muted' | undefined`, and
  `collapsedGroup?: { rows, label, testId }` for the "Not seen recently (N)" group row, which is
  always last. Rebuild `Pagination` on `ui/pagination` — icon-only prev/next with accessible names
  "Previous page" / "Next page", page numbers, ellipsis; the words *Previous* / *Next* and the
  `Showing 1–20 of N` range line (with its `{testId}-range` id) leave the DOM. Add
  `lib/pageWindow.ts` and `lib/silentDevice.ts` as pure modules. `ListSurface` passes `rowTone`
  and `collapsedGroup` through with no state change. Per `ARCHITECTURE.md` §4.1, §4.4 and
  `DESIGN.md` §6.3.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/components/DataTable.tsx`, `frontend/src/components/DataTable.test.tsx`, `frontend/src/components/Pagination.tsx`, `frontend/src/components/Pagination.test.tsx`, `frontend/src/components/ListSurface.tsx`, `frontend/src/components/LoadingSkeleton.tsx`, `frontend/src/lib/pageWindow.ts`, `frontend/src/lib/pageWindow.test.ts`, `frontend/src/lib/silentDevice.ts`, `frontend/src/lib/silentDevice.test.ts`]
- **Tests**: `DataTable.test.tsx` — every row is one height regardless of content, a whole row
  navigates, sort markers are elements not glyphs, a muted row carries its tone, and the collapsed
  group renders last, announces its count and expands on `Enter` and `Space`.
  `pageWindow.test.ts` and `silentDevice.test.ts` are table-driven pure-function suites.
  `Pagination.test.tsx` finds prev/next by accessible name and proves the words and the range line
  are absent.
- **Success Criteria**:
  - `TRUTH.md` criteria *"Rows are one height"*, *"A whole row navigates"* and *"A quiet machine
    stays and says so"* are each covered by a named test.
  - `rg -- '\{testId\}-range|Showing \d' frontend/src` returns nothing. **Amended 2026-09-04**:
    the original `rg -- 'Showing |-range'` is unsatisfiable — it hits the unrelated toast copy
    *"That Pi is already scanning. Showing the scan in progress."* in `useScanCommand.ts:89` and
    `Agents.command.test.tsx`, both Task 9 files. The substance is: no pagination range line and no
    `-range` testid survives.
  - No `▲` or `▼` glyph anywhere in `frontend/src`.
  - `TRUTH.md` criterion *"No screen scrolls sideways"* holds at the component level: a wide table
    scrolls inside its own `overflow-x: auto` container and never widens the page body. Asserted
    in `DataTable.test.tsx` on the overflow container, and spot-checked at 1280px and 1440px in
    the Chrome pass.
  - Gate green.
- **Notes**: `PaginationPrevious` / `PaginationNext` / `PaginationLink` from the vendored
  `ui/pagination` are **deliberately unused** — they render an `<a>` with no `href` (unfocusable,
  no button role) and hard-code `aria-label="Go to previous page"` against FOUNDATIONS §Pagination's
  "Previous page". The shared `Button` is the correct control; do not "restore" them.
  *"Rows are one height"* is in practice carried entirely by the Chrome visual pass — the in-jsdom
  substitute compares two rows' class strings and cannot fail short of deliberate sabotage.
- **Status**: COMPLETED
- **Review Rejections**: 2

## Task 5: Routes, chrome and the vocabulary sweep
- **Description**: Rename the routes — `/hosts` → `/network`, `/hosts/:hostId` →
  `/network/:hostId`, `/agents` → `/devices`, plus the new `/devices/:agentId` — with no
  redirects, and sweep every `Link`, `navigate()` and `data-testid`. Rewrite `TopBar`: nav reads
  Home · Scans · Network · Devices · Users · Settings, active is bold with no underline, hover is
  also bold, the `border-b-2` affordance goes, the wordmark is the word `Dmitri`, and `Users` is
  absent for viewers. `AppShell` holds `--container-frame`. `index.html` title becomes `Dmitri`.
  Sweep *finding* → *Vulnerability* in all reader-facing copy. Per `ARCHITECTURE.md` §6 and
  `DESIGN.md` §2.1, §13, §14.
- **Absorbed**: `frontend/index.html` — a one-line title change with no branching, asserted by the
  routing suite's document title check.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/index.html`, `frontend/src/components/TopBar.tsx`, `frontend/src/components/TopBar.test.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/components/AuthShell.tsx`, `frontend/src/components/FirstScanCta.tsx`, `frontend/src/components/NotFoundNotice.tsx`, `frontend/src/components/ReadDetailGate.tsx`]
- **Tests**: `TopBar.test.tsx` — the six nav names in order, the active item bold with no
  underline or border, `Users` absent (not disabled) for a viewer, the wordmark reading `Dmitri`.
  `App.test.tsx` — `/network` and `/devices` resolve, `/hosts` and `/agents` are 404s, and the
  document title is `Dmitri`.
- **Success Criteria**:
  - `rg -- '"/hosts|"/agents|to="/hosts|to="/agents' frontend/src` returns nothing.
  - `rg -i -- '\bfinding' frontend/src --glob '!**/api/**' --glob '!**/types/**'` returns no
    reader-facing string (the API noun survives in code and query keys by design).
  - `TRUTH.md` criteria *"The vocabulary is adopted"*, *"Nav names the domains"*, *"Viewers do not
    see Users"*, *"Routes follow the names"* and *"The browser names the product"* each covered.
  - The top bar shows the user's email, truncated with an ellipsis when it would crowd the bar,
    with the full value in `title`.
  - Gate green.
- **Notes**: The nav-centring guarantee (`justify-self-center` / `grid-cols-bar`) is CSS-only and owned by the Chrome visual pass.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Network list with the quiet-device group
- **Description**: Rename `pages/Hosts.tsx` → `pages/Network.tsx` and restyle it onto the new
  `DataTable`. Columns Device · Address · Vendor · Services · Highest severity · Last seen, with
  `Highest severity` second to last because `Last seen` closes the row. A host with no hostname is
  listed by its address in mono with a `No name yet` sub-line — the `(unnamed)` placeholder is
  deleted. Partition the page's rows with `isSilent()`: quiet rows go muted with a
  `Not seen for {n} weeks` second line and collapse into the `Not seen recently (N)` group.
  **Not drawn**: machine type, per-machine vulnerability count, search box, filter select. Per
  `ARCHITECTURE.md` §7 and `DESIGN.md` §6.
  **Ruling, reviewer, Task 4, 2026-09-04 — compose `DataTable` directly, as Task 8 does; do not
  use `ListSurface`.** `ListSurface.tsx:90` hard-codes `rows={query.data.data}`, so a caller
  passing `collapsedGroup.rows` cannot subtract them from the main body and every quiet machine
  renders twice. Network needs its own `EmptyState` / `ErrorRetry` / `Pagination` wiring anyway.
  **This task then deletes the dead `collapsedGroup` pass-through from `ListSurface`** (`rowTone`
  stays — Task 7's tables can use it). This task also owes the **all-quiet** end-to-end test
  (`DESIGN.md` §6.4): empty main body, group row holding every machine, never a bare table.
- **Dependencies**: Tasks 4, 5
- **Target Files**: [`frontend/src/pages/Hosts.tsx`, `frontend/src/pages/Network.tsx`, `frontend/src/pages/Network.test.tsx`, `frontend/src/pages/hosts/hostListColumns.tsx`, `frontend/src/test/mswHandlers.ts`]
- **Tests**: `Network.test.tsx` — a quiet host renders muted with its weeks line and inside the
  group; the group row is last after the sort and expands; a nameless host shows its address and
  `No name yet`; no device-type or vulnerability-count column exists.
- **Success Criteria**:
  - `TRUTH.md` criterion *"A quiet machine stays and says so"* passes end-to-end on the screen.
  - No `(unnamed)` string remains in `frontend/src`.
  - The page renders no column `DESIGN.md` §16 lists as not drawn.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 2

## Task 7: Scans, Scan detail and Network detail restyled
- **Description**: Restyle the three read screens onto the new tokens and components. Scans keeps
  its log shape and carries **no settings block**. Scan detail gains the summary strip aligned to
  its tables' width and one white `Card` per severity group, each heading a bold word; the single
  `findings-table` becomes four severity tables. Network detail renders vulnerabilities, then
  **"Services running on this device"**, then **"Scan history"** — the two wordings resolved in
  `DESIGN.md` §0. Status is plain text everywhere; no pill. Per `ARCHITECTURE.md` §7 and
  `DESIGN.md` §4, §5, §7.
- **Dependencies**: Tasks 4, 5
- **Target Files**: [`frontend/src/pages/Scans.tsx`, `frontend/src/pages/Scans.test.tsx`, `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/ScanDetail.test.tsx`, `frontend/src/pages/scans/scanListColumns.tsx`, `frontend/src/pages/scans/findingColumns.tsx`, `frontend/src/pages/scans/FindingsTable.tsx`, `frontend/src/pages/scans/FindingPanel.tsx`, `frontend/src/pages/scans/ScanDetailHeader.tsx`, `frontend/src/pages/scans/ScanFailedNotice.tsx`, `frontend/src/pages/scans/ScanUnfinishedNotice.tsx`, `frontend/src/pages/scans/ScanHostsTable.tsx`, `frontend/src/pages/HostDetail.tsx`, `frontend/src/pages/HostDetail.test.tsx`, `frontend/src/pages/hosts/HostFindings.tsx`, `frontend/src/pages/hosts/HostIdentity.tsx`, `frontend/src/pages/hosts/HostPortsTable.tsx`, `frontend/src/pages/hosts/HostScanHistoryTable.tsx`, `frontend/src/pages/hosts/portColumns.tsx`]
- **Tests**: `ScanDetail.test.tsx` — four severity tables addressed by `findings-{severity}`, the
  summary strip, and the failed state rendering the word `Failed` as text with its reason line and
  no pill. `HostDetail.test.tsx` — the two resolved headings, and a vulnerabilities-only failure
  leaving identity, services and history standing. `Scans.test.tsx` — no settings block, no
  Duration or Result column.
- **Success Criteria**:
  - `TRUTH.md` criteria *"Severity reads as a word"* and *"Nothing renders without data"* hold on
    all three screens.
  - The strings `Open ports` and `Seen in these scans` appear nowhere in `frontend/src`.
  - **Carried from Task 2's review**: `ScanUnfinishedNotice.tsx:17` reads *"Findings appear here
    when it finishes"*; `DESIGN.md` §5.1 specifies *"Vulnerabilities appear here when it
    finishes."* Fix it here — the file is this task's, not Task 2's.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Devices list
- **Description**: Rewrite `pages/Agents.tsx` → `pages/Devices.tsx` as a list of boxes over
  `listAgents`, composing `DataTable` + `EmptyState` + `ErrorRetry` directly — `ListSurface` is
  unusable because `AgentListResponse` has no `total` and no pagination. Columns Box · Network ·
  Status · Last report; the network cell renders the CIDR in `--font-mono`, or
  `No network chosen yet` in muted ink with no error styling; an offline box's row is muted and
  stays in the list. No per-row action — the whole row opens `/devices/:agentId`. The card and the
  three paragraphs of product copy go. Per `ARCHITECTURE.md` §7 and `DESIGN.md` §8.
- **Absorbed**: the multi-agent fixtures in `frontend/src/test/mswHandlers.ts` — test data carries
  no test of its own and is first consumed here.
- **Dependencies**: Tasks 4, 5
- **Target Files**: [`frontend/src/pages/Agents.tsx`, `frontend/src/pages/Devices.tsx`, `frontend/src/pages/Devices.test.tsx`, `frontend/src/pages/agents/deviceListColumns.tsx`, `frontend/src/pages/agents/AgentsBlank.tsx`, `frontend/src/pages/agents/DevicesBlank.tsx`, `frontend/src/test/mswHandlers.ts`]
- **Tests**: `Devices.test.tsx` — several boxes each render a row; an offline box is muted and
  present; a box with no network reads `No network chosen yet` with no error role or styling; a
  row navigates to `/devices/:agentId`; no trailing action column exists.
- **Success Criteria**:
  - `TRUTH.md` criteria *"Boxes are listed"* and *"A box with no network says so"* covered.
  - The retired product copy (`Scanning is set up on the Pi itself.` and its two paragraphs)
    appears nowhere.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 9: Device detail with the scan-type control
- **Description**: New screen at `/devices/:agentId`: back link, box name, presence line, the
  watched-network row with a `Change` control opening the existing `SubnetChooser`, the five-tab
  `ScanTypeTabs` with the `FOUNDATIONS.md` §Scan settings descriptions shipped verbatim, and
  `Scan now`. `useScanCommand.trigger` takes a `ScanMode` argument instead of the hardcoded
  `QUICK_SCAN_MODE`. Selection is preview-only, opens on `Standard` (`lib/scanModes.ts`
  `DEFAULT_SCAN_MODE`), never persists, and **no copy claims a stored default exists**. Viewers
  see the network and scan type and none of the controls. With no network chosen the chooser is
  open and `Scan now` is absent. A running command replaces `Scan now` on the same screen and
  takes focus. Delete `AgentCard`, `useAgentScreen` and `usePrimaryAgent`. Per
  `ARCHITECTURE.md` §5, §7 and `DESIGN.md` §9. **This task also owes two debts deferred from
  Task 2**: renaming `data-testid="agents-pill"` → `agents-status` in `CommandStatus.tsx` and its
  three assertions in `Agents.test.tsx` (the last stale id in the tree), and the 9 `toHaveClass`
  assertions in `Agents.test.tsx`.
- **Dependencies**: Tasks 3, 8
- **Target Files**: [`frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/pages/DeviceDetail.tsx`, `frontend/src/pages/DeviceDetail.test.tsx`, `frontend/src/pages/DeviceDetail.command.test.tsx`, `frontend/src/pages/DeviceDetail.invalidation.test.tsx`, `frontend/src/pages/agents/ScanTypeTabs.tsx`, `frontend/src/pages/agents/ScanControl.tsx`, `frontend/src/pages/agents/CommandStatus.tsx`, `frontend/src/pages/agents/TargetSubnetSection.tsx`, `frontend/src/pages/agents/SubnetChooser.tsx`, `frontend/src/pages/agents/AgentIdentity.tsx`, `frontend/src/pages/agents/AgentCard.tsx`, `frontend/src/hooks/useScanCommand.ts`, `frontend/src/hooks/useAgentScreen.ts`, `frontend/src/hooks/usePrimaryAgent.ts`, `frontend/src/api/agents.ts`, `frontend/src/lib/scanModes.ts`, `frontend/src/lib/scanModes.test.ts`, `frontend/src/pages/Agents.test.tsx`, `frontend/src/pages/Agents.command.test.tsx`, `frontend/src/pages/Agents.invalidation.test.tsx`]
- **Tests**: `DeviceDetail.command.test.tsx` — selecting `Max` and pressing `Scan now` posts
  `scan_mode: 'max'`, not `quick`. `DeviceDetail.test.tsx` — the tab strip opens on `Standard`;
  navigating away and back reverts the selection; no text names a stored or daily default; a
  viewer sees no change, select or scan control; with no network the chooser is open and
  `Scan now` is absent; the command status replaces the button and receives focus.
  `scanModes.test.ts` pins the five descriptions verbatim against `FOUNDATIONS.md`.
- **Success Criteria**:
  - `TRUTH.md` criteria *"A box owns its settings"*, *"Scan now uses the selected type"*,
    *"Scan type never persists by accident"*, *"No default is claimed"*, *"Viewers cannot configure
    a box"*, *"Scanning is unavailable without a network"* and *"A running scan reports where it
    started"* are each covered by a named test.
  - `rg -- 'QUICK_SCAN_MODE|usePrimaryAgent|useAgentScreen|AgentCard' frontend/src` returns
    nothing.
  - No `Daily scan uses` or `Use this scan type` string exists — that is DMI-133.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 10: Home attention table
- **Description**: Replace the card deck with the attention table — the page title states the
  count, the table lists Vulnerability · Device · Severity, and a whole row navigates. When
  nothing needs attention **nothing is drawn at all**: no table, no empty card. Failed-scan and
  stale-coverage items become one-line `AttentionNotices` sentences, preserving behaviour
  `ReviewItemCard` was the only renderer for. `useHomeReview` reads `listAgents` directly now that
  `usePrimaryAgent` is gone, and `HomeFooter`'s `agent` prop narrows to `AgentSummary`. Delete
  `FindingDeck` (+ its test) and `ReviewItemCard`. Per `ARCHITECTURE.md` §7 and `DESIGN.md` §3.
- **Dependencies**: Tasks 4, 5, 9
- **Target Files**: [`frontend/src/pages/Home.tsx`, `frontend/src/pages/Home.test.tsx`, `frontend/src/pages/home/AttentionTable.tsx`, `frontend/src/pages/home/AttentionNotices.tsx`, `frontend/src/pages/home/Verdict.tsx`, `frontend/src/pages/home/HomeFooter.tsx`, `frontend/src/pages/home/HomeBlank.tsx`, `frontend/src/pages/home/HomeError.tsx`, `frontend/src/pages/home/FindingDeck.tsx`, `frontend/src/pages/home/FindingDeck.test.tsx`, `frontend/src/pages/home/ReviewItemCard.tsx`, `frontend/src/hooks/useHomeReview.ts`, `frontend/src/lib/review.ts`, `frontend/src/lib/review.test.ts`]
- **Tests**: `Home.test.tsx` — with attention, the title states the count and each row navigates;
  with none, the title reads `Nothing needs your attention` and no table or empty card is in the
  DOM; a failed latest scan and a stale coverage window each render their one-line notice.
- **Success Criteria**:
  - `TRUTH.md` criteria *"Home states the count"* and *"Home stays quiet when clear"* covered, the
    second asserting absence, not emptiness.
  - No copy anywhere claims the network is safe.
  - `rg -- 'FindingDeck|ReviewItemCard' frontend/src` returns nothing.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 11: Users, Settings and the auth screens
- **Description**: Restyle the remaining screens. Users keeps the inline ghost `Select` role
  trigger aligned to its column header and the invite action below the table, bottom-right.
  Settings keeps account, password, leave-organisation **and its existing Activity disclosure**;
  the delete-account flow stays the modal it already is (`ConfirmByTyping` composes `DialogShell`)
  and is restyled, not rebuilt; `Delete my account` becomes a plain outlined button — one accent, no semantic colour, with the
  type-your-own-email confirmation carrying the weight. The auth screens and `NotFound` take the
  new tokens, the `Dmitri` wordmark and no ornament. Per `ARCHITECTURE.md` §7 and `DESIGN.md`
  §10, §11, §12.
- **Dependencies**: Tasks 3, 5
- **Target Files**: [`frontend/src/pages/Users.tsx`, `frontend/src/pages/Users.test.tsx`, `frontend/src/pages/users/DirectoryTable.tsx`, `frontend/src/pages/users/InviteDialog.tsx`, `frontend/src/pages/users/RoleChangeDialog.tsx`, `frontend/src/pages/users/RevokeDialog.tsx`, `frontend/src/pages/users/RemoveMemberDialog.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Settings.test.tsx`, `frontend/src/pages/settings/AccountDetails.tsx`, `frontend/src/pages/settings/PasswordDialog.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/ForgotPassword.tsx`, `frontend/src/pages/ResetPassword.tsx`, `frontend/src/pages/AcceptInvite.tsx`, `frontend/src/pages/NotFound.tsx`, `frontend/src/components/ConfirmByTyping.tsx`, `frontend/src/components/Disclosure.tsx`, `frontend/src/components/Toast.tsx`]
- **Tests**: `Users.test.tsx` — the role select changes a role and the `Remove` action is absent
  on your own row. `Settings.test.tsx` — all four sections render and the destructive flow still
  requires the typed confirmation.
- **Success Criteria**:
  - `TRUTH.md` criterion *"Every control shows it is a control"* holds — every interactive element
    on these screens has a visible focus ring and a pointer cursor.
  - No `--destructive` colour and no raw red hex survives in `frontend/src`.
  - Gate green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 12: Retire the superseded design decisions in the docs
- **Description**: Close the loop the owner asked for — the revamp removes the old decisions, it
  does not layer over them. Edit `FOUNDATIONS.md` §Scan settings so the block lives on the box
  detail screen, not below the scans table; correct §Vocabulary per the *device*/*box* answer;
  record the `--duration-*` gap — the tokens sit in `:root` (`index.css:37-39`) but not in
  `@theme`, so no `duration-base` utility is generated and `DESIGN.md`'s motion spec is unreachable
  without an arbitrary value;
  record that the `outline` button variant uses `border-border` (`--rule` `#E2E8F0`, ~1.2:1) where
  §Color assigns `--edge` `#64748B` to control boundaries and requires 3:1 per WCAG 1.4.11 — a
  pre-existing mismatch that spreads once the outlined button becomes the card-footer control;
  record the accent hover/active values (`#4338CA` / `#3730A3`, indigo-700/800) in §Color instead
  of the un-numbered "one step darker each";
  fix the §Color claim that the API taxonomy includes `informational` (the `Severity` union has
  four members); amend §Chrome to say the top bar shows the user's **email**; correct §Tables'
  "Silent devices" to "Silent machines" and §Vocabulary so a **device** is the Dmitri box and a
  thing on the customer's network is a **machine**. Record why the scan-settings block
  moved in `FOUNDATIONS-DECISIONS.md`. Replace `SCREENS.md` §Foundations with a pointer to
  `FOUNDATIONS.md`. Strip §Styling from the `frontend-conventions` skill, correct its "four local
  lint rules" line to six, drop its "Until DMI-132 lands" caveat, and point it at the new
  `frontend-design-system` skill carrying the shipped tokens. Per `ARCHITECTURE.md` §9 (Docs and
  skills).
- **Dependencies**: Tasks 1–11
- **Target Files**: [`docs/ui/FOUNDATIONS.md`, `docs/ui/FOUNDATIONS-DECISIONS.md`, `docs/ui/SCREENS.md`, `.claude/skills/frontend-conventions/SKILL.md`, `.claude/skills/frontend-design-system/SKILL.md`]
- **Tests**: none — this task delivers no runtime artifact. **Justified exception** to the
  every-task-ships-a-test rule: the change set is documentation and skill text with no executable
  surface, and it is kept separate rather than merged into Task 11 because it spans five files
  across three trees and would be the first thing dropped if buried in a screen task. The reviewer
  gates on the greps below and on reading the diff against `FOUNDATIONS.md`.
- **Success Criteria**:
  - `rg -- 'below the scans table' docs/ui/FOUNDATIONS.md` returns nothing.
  - `rg -- 'informational' docs/ui/FOUNDATIONS.md` returns nothing, or only where it names
    something other than the API taxonomy.
  - `docs/ui/FOUNDATIONS.md` §Vocabulary states the device/machine split, and §Tables no longer
    says "Silent devices".
  - `rg -- 'IM Fell|Plex Mono|radius 0|purple|severity pill' docs/ui/SCREENS.md` returns nothing.
  - `.claude/skills/frontend-conventions/SKILL.md` §Styling is gone and links to
    `frontend-design-system`; no "four local lint rules" line survives.
  - `.claude/docs/frontend/*.md` is **not** edited here — that is `/docs-sync` at the end of the
    pipeline.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ─┬─► #2                                     (land as one commit)
    └─► #3 ─┬─► #4 ─┬─► #6 ──────────────┐
            │       ├─► #7 ──────────────┤
            │       └─► #8 ─► #9 ─► #10 ─┤
            ├─► #5 ─┘  ▲              ▲  │
            └─► #11 ───────────────────  ┴─► #12
```

Read as: #1 unblocks everything. #2 rides with #1. #3 gates the primitives. #4 and #5 together
gate the screens. #6, #7 and #11 are independent of each other and can run in parallel. #8 → #9 →
#10 is the one deep chain, because Home's `useHomeReview` cannot lose `usePrimaryAgent` until the
Devices screens stop using it. #12 is last.

**Parallel tracks after #5:**

| Track | Tasks |
| --- | --- |
| Read screens | #6, #7 |
| Boxes and Home | #8 → #9 → #10 |
| Account screens | #11 |

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Tokens, fonts and the six lint rules | COMPLETED |
| 2 | Severity, status and ornament retired; the `font-title` sweep | COMPLETED |
| 3 | shadcn primitives regenerated from `radix-maia` | COMPLETED |
| 4 | `DataTable`, `Pagination`, and the silent-device pattern | COMPLETED |
| 5 | Routes, chrome and the vocabulary sweep | COMPLETED |
| 6 | Network list with the quiet-device group | COMPLETED |
| 7 | Scans, Scan detail and Network detail restyled | COMPLETED |
| 8 | Devices list | COMPLETED |
| 9 | Device detail with the scan-type control | COMPLETED |
| 10 | Home attention table | COMPLETED |
| 11 | Users, Settings and the auth screens | COMPLETED |
| 12 | Retire the superseded design decisions in the docs | COMPLETED |
