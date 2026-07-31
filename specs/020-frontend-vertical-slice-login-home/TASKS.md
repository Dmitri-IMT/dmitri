# Tasks — Frontend vertical slice: login → Home (`020-frontend-vertical-slice-login-home`)

9 tasks. **All COMPLETED.**

Order adapted to a single-layer React SPA feature (there is no scan pipeline and no Textual
screen in this blast radius): foundation → pure derivation → data layer → session → shells →
pages → routing + gate.

**Every task carries its own tests.** An earlier 15-task cut split this feature finely enough
that six tasks had nothing worth testing — `package.json` edits, four thin typed wrappers, MSW
fixtures, five copy-only components. Each would still have cost a full coder → tester →
reviewer cycle to land a change no test could meaningfully assert. Those six were folded into
the neighbours whose tests already cover them, listed under **Absorbed** on each task below.
The merge changed no scope: every file in `ARCHITECTURE.md`'s naming table is still built, and
every acceptance criterion is still gated.

**Use the frontend test and review agents.** This feature is React + Vitest. The coder is
`agent-developer` as usual — it loads the `frontend-conventions` skill for this layer — but spawn
`frontend-test-engineer` and `frontend-code-reviewer` for steps 2 and 3: `test-engineer` writes
pytest under `hardware-agent/tests/` and `code-reviewer` gates on `uv run pytest` +
`uv run ruff check`, neither of which exists in `frontend/`. The gate for
every task here is, from `frontend/`:

```
npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
```

**CLAUDE.md integration rule: N/A, verified.** This feature touches `frontend/` only —
`ARCHITECTURE.md` §Preamble. There is no `ScanOrchestrator`, `ScanRunner` or
`ScanProgressScreen` parameter anywhere in scope, and neither `hardware-agent/` nor `backend/`
is touched. The rule's *spirit* is honoured by Task 4, which sweeps every call site of the
replaced hard redirect, and by Task 9, which sweeps every provider wiring point.

**Blocked read, deliberately not worked around.** `GET /agents/{agent_id}` is unimplemented
(DMI-78, contract ask C1). `frontend/src/api/agents.ts` is written but never called, and the
Pi-status footer line is not built — `ARCHITECTURE.md` §2.2, `DESIGN.md` §The Pi-status footer
is blocked. No `VITE_AGENT_ID`, no hardcoded UUID, no inference from a scan.

---

## Task 1: Foundation — dependencies, the light-only token layer, and the shared components
- **Description**: Per `ARCHITECTURE.md` decisions (c) and (d), §3 (Shell and shared components), and `DESIGN.md` §Colour/§Layout/§Badge treatment.
  **(a) `frontend/package.json`**: add `react-router@^7` (**not** `react-router-dom` — v7 merged it), add `@fontsource/im-fell-english` (regular + italic) and IBM Plex Mono (`@fontsource-variable/ibm-plex-mono` if published, else `@fontsource/ibm-plex-mono`), remove `@fontsource-variable/geist`. No new scripts.
  **(b) `frontend/src/index.css`** rewrite: drop the Geist `@import`, `@custom-variant dark` (line 6), the whole `.dark` block (lines 91–123), the chart tokens (28–32, 59–63) and the sidebar tokens (34–41, 51–58); add `--font-title: 'IM Fell English', serif` and `--font-mono: 'IBM Plex Mono', monospace` inside `@theme inline`, deleting `--font-sans`/`--font-heading` and switching the base layer's `@apply font-sans` (line 133) to `font-mono`; add the locked neutrals `--paper #FAF8F4`, `--card #FFFFFF`, `--ink #1A1917`, `--ink-muted #6B6862`, `--rule #E5E0D8`, `--edge #8C8880`, the accent `--accent #7C3AED`, the ramp `--sev-critical #B91C1C` / `--sev-high #C2410C` / `--sev-medium #A16207` / `--sev-low #1D4ED8`, `--radius: 0`, and the `--text-title-*` / `--text-body-*` / `--text-caption-*` scale. **Spacing needs no custom tokens** — SCREENS.md §Spacing and rhythm fixes the base unit at Tailwind v4's 4px `--spacing` default, so the permitted steps (`1 2 3 4 6 8 12 16 24`) are already the stock `p-*`/`gap-*` utilities; do not invent a `--space-*` layer. Then remap the retained shadcn semantic tokens per the `ARCHITECTURE.md` §2.4(d) table. `color-scheme: light` stays.
  **(c) The shared components**: `Ornament.tsx` (the `· · ❦ · ·` engraving), `Timestamp.tsx` (consistency rule 7 — relative inside 7 days, absolute beyond, exact value in `title`), `SeverityBadge.tsx` (severity-coloured text on a 10% tint of the same hue with a 1px full-colour border, never white-on-solid), and shadcn `label` via `npx shadcn@latest add label`.
- **Absorbed**: the former standalone "dependencies and tokens" task. It edited two config files and had nothing to assert; the token layer is only observably correct once a component consumes it, which is what `Timestamp.test.tsx` and the later screens do.
- **Dependencies**: —
- **Target Files**: [`frontend/package.json`, `frontend/src/index.css`, `frontend/src/components/Ornament.tsx`, `frontend/src/components/Timestamp.tsx`, `frontend/src/components/Timestamp.test.tsx`, `frontend/src/components/SeverityBadge.tsx`, `frontend/src/components/ui/label.tsx`]
- **Tests**: `Timestamp.test.tsx` — both sides of the 7-day boundary and the `title` attribute carrying the exact value. `Ornament`, `SeverityBadge` and `label` get no test file of their own (none is in `ARCHITECTURE.md`'s naming table); `SeverityBadge` is asserted through `Home.test.tsx` in Task 8.
- **Success Criteria**: `npm run build` and `npm run typecheck` pass; `grep -rn "geist\|@custom-variant dark" frontend/src frontend/package.json` returns zero hits; `grep -rn "dark:" frontend/src` returns zero hits; `--chart-` and `--sidebar` tokens are gone; every `--text-title-*` token resolves to ≥ `1rem` (SCREENS.md building rule 5); `frontend/src/components/ui/{button,input}.tsx` are **not edited** and still render (they inherit the remapped names); no `jwt-decode` or equivalent token-decoding package is added; no raw hex and no raw pixel value in any component — `grep -rnE "#[0-9a-fA-F]{3,6}|[0-9]+px" frontend/src/components/*.tsx` returns zero hits; `SeverityBadge` renders `Critical`/`High` text meeting 4.5:1 on `--paper`; nothing here renders `disabled`; every spacing utility in the three new components is one of the nine permitted steps and no component carries an outer margin (SCREENS.md §Spacing and rhythm) — `grep -rnE "(p|m|gap|space)-(5|7|9|10|11|13|14|15)\b|\[[0-9]+px\]|^.*\bm[btlrxy]?-[0-9]" frontend/src/components/*.tsx` returns no hit that is an outer margin on a component root.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 2: The pure verdict derivation
- **Description**: Per `ARCHITECTURE.md` §2.5, §2.6 and `DESIGN.md` §How the deck behaves. `deriveReview({ latestScan, latestSuccessfulScan, criticalFindings, highFindings, now })` → `{ reviewCount, deckFindings, scanItem, coverageItem }`. Takes the two finding **envelopes**, not their `data` arrays. Owns `STALE_COVERAGE_DAYS = 3` — the only place the number appears. `reviewCount = criticalFindings.total + highFindings.total + (latestScan.status === 'failed' ? 1 : 0) + (coverageIsStale ? 1 : 0)`. `deckFindings` is the concatenation ordered **critical → high, newest first within a severity** — imposed here, because the API guarantees no caller-chosen order (§2.2). No React, no network; types come straight from `@/types/openapi`, so this task does not wait on the API modules.
- **Dependencies**: —
- **Target Files**: [`frontend/src/lib/review.ts`, `frontend/src/lib/review.test.ts`]
- **Tests**: `review.test.ts` is the rule table and the highest-value suite in the feature — the whole verdict is decidable here without a DOM.
- **Success Criteria**: AC 17 — a case with `total: 37` and 20 rows asserts `reviewCount` is 37, not 20. AC 9/10/11 — all-clear, items-pending, and medium/low-only (which yields no deck item and an all-clear verdict). AC 12 — `status: 'failed'` produces `scanItem`. AC 13 — both sides of the 3-day boundary measured against `latestSuccessfulScan`, **plus** a recent *failed* scan not masking stale coverage, **plus** `latestSuccessfulScan: null` with a non-null `latestScan`, which omits `coverageItem` rather than computing "stale since never". When both reads return the same completed scan it is not double-counted. `deckFindings` order is asserted against a shuffled input. The staleness constant is declared once and referenced by name.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: The data layer — resource modules, MSW handlers, and the Home read hook
- **Description**: Per `ARCHITECTURE.md` §2.3, §3 (API resource modules / Query hooks) and §7.
  **(a) Four thin modules** over `apiClient`, typed exclusively from `@/types/openapi` via `components['schemas'][...]`, mirroring `src/api/auth.ts` lines 3–6; path tails are relative to the `/api/v1` baseURL in `instances.ts:3` — never repeat the prefix. `users.ts`: `getCurrentUser()`. `scans.ts`: `LATEST_SCAN_QUERY = { per_page: 1, sort_by: 'timestamp', sort_order: 'desc' }`, `LATEST_SUCCESSFUL_SCAN_QUERY = { ...LATEST_SCAN_QUERY, status: 'completed' }`, `getLatestScan()` and `getLatestSuccessfulScan()` (§2.5 — two reads, not one). `findings.ts`: `HOME_SEVERITIES = ['critical','high']`, `HOME_FINDINGS_PER_PAGE = 100`, `listFindings({ scan_id, severity })` taking **one** severity per call and returning the whole envelope. `agents.ts`: `getAgent(agentId)` — written, **called by nothing** (blocked read, §2.2).
  **(b) `mswHandlers.ts`**: handlers for `GET /users/me`, `/scans`, `/findings`, `/agents/:agentId` plus exported fixtures (`adminProfile`, `viewerProfile`, `latestScan`, `criticalFinding`, …). `/scans` **must branch on `status`** so the two scan reads return different records; `/findings` **must branch on `severity`**. Real hostnames, IPs and CVE ids (consistency rule 9).
  **(c) `useHomeReview()`**: composes the four reads via TanStack Query, feeds `deriveReview()`, returns **one discriminated union** `{ state: 'loading' | 'blank' | 'clear' | 'pending' | 'error', … }` plus `retry()`. Blank is keyed off the unfiltered `latestScan` read (`total === 0` on a `200`), never off a `404`. **Any** of the four reads failing yields `error`.
- **Absorbed**: the former standalone "API resource modules" and "MSW handlers" tasks. The modules have no test files anywhere in `ARCHITECTURE.md`'s naming table — deliberately, since unit-testing a typed wrapper mocks the transport and asserts the URL string twice. Both are exercised for real, over MSW, by `useHomeReview.test.ts` here.
- **Dependencies**: Task 2
- **Target Files**: [`frontend/src/api/users.ts`, `frontend/src/api/scans.ts`, `frontend/src/api/findings.ts`, `frontend/src/api/agents.ts`, `frontend/src/test/mswHandlers.ts`, `frontend/src/test/setup.ts`, `frontend/src/hooks/useHomeReview.ts`, `frontend/src/hooks/useHomeReview.test.ts`]
- **Tests**: `useHomeReview.test.ts` — the state matrix over MSW, which is simultaneously the proof that the four resource modules build the right requests.
- **Success Criteria**: No hand-written request or response interface anywhere in the four modules (ADR-008 §Geração de Tipos). `getLatestScan`/`getLatestSuccessfulScan` return `null` on `{ data: [], total: 0 }` and do **not** treat a `404` as "no scans"; `listFindings` returns `total` alongside `data`; `severity` is a single value per request — no list, no comma-joined string; no paging value other than `per_page: 1` / `per_page: 100` is ever sent. `src/test/setup.ts` keeps `onUnhandledRequest: 'error'` and **gains one line**: `cleanup()` from `@testing-library/react` inside its existing `afterEach`. **This deviates from `ARCHITECTURE.md` §3, which lists `setup.ts` as "keep — Unchanged" — that line is wrong** (`docs/research/frontend-testing-vitest-testing-library-msw.md`): `vitest.config.ts` never sets `globals`, so it is `false`, and RTL registers its auto-cleanup `afterEach` only when a global `afterEach` exists. It is invisible today because both existing test files render once; every render-heavy file this feature adds would fail on its second test with "found multiple elements". Handlers branch on `new URL(request.url).searchParams` inside one resolver per path — `server.use()` prepends, so two handlers for one path resolve by registration order. AC 15 — MSW 500 on **each** of the four reads independently yields `state: 'error'`. AC 16 — a fail-then-succeed handler plus `retry()` lands on the correct terminal state. AC 14 — `{ data: [], total: 0 }` yields `blank`; a `404` yields `error`. The union makes a partial render unrepresentable: no field carrying verdict content is readable in the `error` or `loading` variants. Exactly four requests are issued on load and none after, except by `retry()`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 4: Session — expiry events, context, guard, and the shared test renderer
- **Description**: Per `ARCHITECTURE.md` decision (b), §3 (Session and role) and §5.
  **(a) `authEvents.ts`** exports `onSessionExpired(handler)` / `emitSessionExpired()` — module-scoped, **no React and no router import**. Replace `window.location.href = '/login'` at `client.ts:45` with `emitSessionExpired()`; leave `clearAccessToken()` (line 44) and the entire interceptor body (lines 10–42) untouched. Update the refresh-failure case in `client.test.ts` (lines 53–57) to assert the emitted event instead of stubbing `window.location`.
  **(b) `SessionProvider.tsx`** owns the boot silent `refresh()` (relocated from `App.tsx` lines 11–15, called exactly once), then the `['session']` query over `getCurrentUser()`;
  **The boot refresh must not live in a `useEffect`.** `docs/research/frontend-react19-vite-typescript-conventions.md` found this as a live bug in today's `App.tsx`: StrictMode double-invokes Effects in dev (React 19 softened that for `useMemo`/`useCallback`, **not** for Effects), so the Effect fires two `POST /auth/refresh` calls, and because ADR-008 specifies a **rotating** refresh token the second consumes what the first just rotated. It presents as a phantom dev-only logout that looks like a backend fault. Model the boot refresh as a query (`useQuery({ queryKey: ['session'], retry: false, … })`), which deduplicates, rather than porting the Effect across. exposes `{ status: 'booting' | 'authenticated' | 'anonymous', user, signIn, signOut }`; registers the `onSessionExpired` handler, which clears the token store and query cache and navigates to `/login` with `replace: true`. `signOut()` calls `logout()` then clears token + cache + state and navigates **whether or not the call succeeded**.
  **(c) `useSession.ts`** throws outside the provider — **the only** way any component reads identity or role. **(d) `RequireSession.tsx`**: `booting` → neither protected content nor a redirect; `anonymous` → `<Navigate to="/login" replace />`; `authenticated` → `<Outlet />`. **(e) `renderWithProviders.tsx`** wraps `MemoryRouter` + a per-test `QueryClient` + `SessionProvider`. The client is constructed **inside** the function (module scope shares a cache across a file and makes AC 20's "cache empty" assertion order-dependent) with `defaultOptions: { queries: { retry: false } }` — without it, AC 15/16's error paths blow past `findBy`'s 1000 ms window on Query's three-retry backoff. No `gcTime: Infinity`; that guidance is Jest-only. Consequently no `useQuery` in `src/hooks/` may set its own `retry`, since defaults are only a fallback.
- **Absorbed**: the former standalone `authEvents` task. It added two functions and one module-scoped variable; its only meaningful assertion is that the provider registered here actually receives the event, which is a `SessionProvider.test.tsx` case, not a suite of its own.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/api/authEvents.ts`, `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts`, `frontend/src/auth/SessionProvider.tsx`, `frontend/src/auth/useSession.ts`, `frontend/src/auth/RequireSession.tsx`, `frontend/src/auth/SessionProvider.test.tsx`, `frontend/src/test/renderWithProviders.tsx`]
- **Tests**: `SessionProvider.test.tsx` (AC 6, 8, 20, plus the expiry-event round trip) and the one edited assertion in `client.test.ts`.
- **Success Criteria**: `grep -rn "window.location" frontend/src/api/` returns zero hits; `client.ts` imports nothing from `react`/`react-router`; the other three `client.test.ts` cases — one-refresh-on-401, single-flight, cookie scoping — are **unmodified and still pass** (the regression signal that the interceptor was not disturbed). AC 8 — the role exposed by `useSession()` is the one on the `GET /users/me` response, and a token whose payload claims a different role does not change it; nothing decodes a token. AC 6 — a successful boot refresh never renders the login form. AC 20 — sign-out fires `POST /auth/logout`, clears the token store, empties the query cache and navigates to `/login` with `replace`, asserted on both a succeeding and a failing logout. `RequireSession` under `booting` renders no protected content **and** no `<Navigate>`. **Exactly one `POST /auth/refresh` is issued on boot** — asserted by counting MSW requests with the provider mounted under `<StrictMode>`, which is the only configuration that catches the double-invoke; no `useEffect` performs the refresh.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: The two shells and the top bar
- **Description**: Per `DESIGN.md` §Top bar/§Layout and `ARCHITECTURE.md` §3. `AppShell.tsx` — inside-shell frame: `<TopBar />` + `<Outlet />` in the fluid 720px-max prose column, **no sidebar**. `TopBar.tsx` — wordmark left, **`Home` alone** as the nav (Scans/Hosts/Agents/Users/Settings arrive with their screens — `DESIGN.md` §Top bar, decided 2026-07-28), `[Log out]` right calling `signOut`; active item marked with a 2px `--accent` underline, not a filled pill; `min-w-0` on flex children; **no role branch — it does not read `useSession().user.role`**. `AuthShell.tsx` — outside-shell frame: wordmark + `Ornament` + one centred card in the 720px column, no top bar.
- **Dependencies**: Task 1, Task 4
- **Target Files**: [`frontend/src/components/AppShell.tsx`, `frontend/src/components/TopBar.tsx`, `frontend/src/components/TopBar.test.tsx`, `frontend/src/components/AuthShell.tsx`]
- **Tests**: `TopBar.test.tsx` — it exists for AC 7 and is the feature's one structural proof of "absent, not disabled". `AppShell`/`AuthShell` are layout wrappers with no test file (none in the naming table); they are exercised by Tasks 6, 8 and 9.
- **Success Criteria**: AC 7 — the suite renders for **both** an admin and a viewer profile and asserts the trees are identical **and** that every element from `queryAllByRole('button'|'link'|'textbox')` is `toBeEnabled()` and carries no `aria-disabled="true"`. **Not** a `container.querySelectorAll('[disabled]')` sweep — it violates Testing Library's `no-container`/`no-node-access` rules and misses both `fieldset[disabled]` inheritance and `aria-disabled`, which is exactly the greyed-out control AC 7 exists to catch. `nav-users` is absent for both roles. `[Log out]` calls `signOut`. No nav link points at a route this feature does not register. The top bar's contents are constrained to the same 720px column as the verdict, and the page body never scrolls horizontally.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: The LOGIN screen
- **Description**: Per `DESIGN.md` §LOGIN, §Copy and §Keyboard and focus. Real `<form>` inside `AuthShell`: `Email` and `Password` with real `<label>`s, `autocomplete="email"` / `"current-password"`, email autofocused, Enter submits from either field. In-flight: button copy `Signing in…` and `disabled` — the one legitimate `disabled` in the feature, and no spinner. Inline error region (`role="alert"`, `data-testid="login-error"`) **between the password field and the button**, never a toast, distinguishing `That email and password don't match.` (401) from `Can't reach the server. Check your connection and try again.` (network/5xx) and naming neither field in either case. Redirects to `/` when already authenticated, and renders no form while `status === 'booting'`. No "forgot password?" link. Delete the DMI-20 throwaway.
- **Dependencies**: Task 1, Task 4, Task 5
- **Target Files**: [`frontend/src/pages/Login.tsx`, `frontend/src/pages/Login.test.tsx`, `frontend/src/pages/LoginStub.tsx`, `frontend/src/pages/LoginStub.test.tsx`]
- **Tests**: `Login.test.tsx` — AC 1, 2, 3, 4 and the feature's one legitimate `disabled`.
- **Success Criteria**: AC 2 — MSW 401 leaves the operator on `/login`, shows the error, and `getAccessToken()` is null. AC 3 — with a handler held open by MSW's `delay('infinite')` (never fake timers — DOM Testing Library's detector looks for a global `jest`, so `findBy` cannot advance Vitest's) the button reads `Signing in…` and is `disabled` **while in flight**, enabled before and after; a second Enter cannot double-submit. AC 4 — `HttpResponse.error()` produces the *other* string. AC 1 — valid credentials establish a session. The password value survives a credential error. `LoginStub.tsx` and `LoginStub.test.tsx` are deleted and `grep -rn "LoginStub" frontend/src` returns zero hits. `data-testid`s `login-form`, `login-email`, `login-password`, `login-submit`, `login-error` exist per `DESIGN.md`. The password field is reached by `getByLabelText` — `<input type="password">` has no implicit role, so a missing `<label>` fails the test rather than being routed around with `getByPlaceholderText`. The error region is rendered **always, empty when clean** — an `aria-live`/`role="alert"` region must pre-exist in the DOM to be announced, so a conditionally-mounted error is silent to a screen reader. AC 4 uses `HttpResponse.error()`, not a 5xx: only a true network error leaves `error.response` undefined, which is what `client.ts` branches on.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 7: Home's cards and the finding deck
- **Description**: Per `DESIGN.md` §HOME states, §Copy, §How the deck behaves, §The review-item buttons are drawn but not built, and `ARCHITECTURE.md` §2.6.
  **(a) The cards.** `Verdict.tsx` — the verdict + context sentence, shared by all-clear (`Nothing needs your attention.`, centred) and items-pending (`{n} things need your review.` / `1 thing needs your review.`, left-aligned); the context sentence comes from the **latest successful** scan and its own `host_count`. `ReviewItemCard.tsx` — square-edged card: label (`FINDING`/`SCAN`/`COVERAGE`, the only place `--accent` appears on this screen), severity badge top-right for findings, plain sentence; **it takes no `href` and no `onAction` prop**, so no dead control can be added without a visible diff. `HomeBlank.tsx` — `No scans yet.` + first-run body + `Scanning is set up on the Pi itself.`; **no CTA, no role branch, does not import `useSession`**. `HomeError.tsx` — `Couldn't load your network's status.` + `[Retry]`. `HomeFooter.tsx` — the last-scan line via `Timestamp`; **the Pi-status line is not built** and the footer is omitted entirely in the blank state.
  **(b) `FindingDeck.tsx`** — one finding at a time with `←`/`→` and a `{i} of {n}` line. It owns the index into the already-fetched array; **no `useQuery` is keyed on the index and no request is issued by stepping**. Stops at both ends, never wraps. A **single tab stop** with `onKeyDown` on its own root — **never a `document`-level listener**; the arrows are separately tab-reachable. Card region is `aria-live="polite"`. With exactly one finding: the card alone, no arrows, no position line. With none: renders nothing. The index resets when the underlying data changes.
- **Absorbed**: the former standalone "Home state components" task. Its five components are copy-and-token only, carry no test file in `ARCHITECTURE.md`'s naming table, and are asserted through `Home.test.tsx` in Task 8; the deck consumes `ReviewItemCard` directly, so splitting them put a review cycle in the middle of one card's construction.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/src/pages/home/Verdict.tsx`, `frontend/src/pages/home/ReviewItemCard.tsx`, `frontend/src/pages/home/HomeBlank.tsx`, `frontend/src/pages/home/HomeError.tsx`, `frontend/src/pages/home/HomeFooter.tsx`, `frontend/src/pages/home/FindingDeck.tsx`, `frontend/src/pages/home/FindingDeck.test.tsx`]
- **Tests**: `FindingDeck.test.tsx` — AC 18, and the only place the no-network-while-stepping property is provable.
- **Success Criteria**: AC 18 — stepping forward and back, both end-stops with no wrap, `{i} of {n}` tracking the card, arrow keys acting **only** while the deck holds focus (a keypress dispatched on `document` with focus elsewhere does nothing), the one-finding case rendering neither arrows nor `home-deck-position`, and `aria-live="polite"` on the card region. **No request is issued while stepping** — the test steps through every card with no handler beyond the initial load and passes only because `onUnhandledRequest: 'error'` would otherwise fail it. `grep -rn "document.addEventListener" frontend/src/pages/home/` returns zero hits. Arrows carry accessible names `Previous finding` / `Next finding`. Copy matches `DESIGN.md` §Copy verbatim including the singular/plural verdict split. `grep -rnE "<a |<Link|onAction|href=" frontend/src/pages/home/` returns zero hits; `HomeBlank.tsx` does not import `useSession` and renders no button; `HomeFooter` renders no Pi line and reads no agent data. No `[disabled]` element and no raw hex or pixel value anywhere in the directory.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 8: The HOME page
- **Description**: Per `ARCHITECTURE.md` §3 (Pages) and `DESIGN.md` §States. `Home.tsx` switches over `useHomeReview()`'s discriminated union and renders **exactly one** of loading / blank / clear / pending. Loading renders **nothing below the top bar** — no skeleton, no spinner, no placeholder sentence, because any placeholder in the verdict's position is read as a verdict. Items-pending order is finding deck → failed-scan card → stale-coverage card. Blank and all-clear are distinct states and are never collapsed. Delete the DMI-20 placeholder.
- **Dependencies**: Task 3, Task 7
- **Target Files**: [`frontend/src/pages/Home.tsx`, `frontend/src/pages/Home.test.tsx`, `frontend/src/pages/SignedInPlaceholder.tsx`]
- **Tests**: `Home.test.tsx` — the full state matrix, and the place every component absorbed into Tasks 1 and 7 is actually asserted.
- **Success Criteria**: AC 9, 10, 11, 12, 13, 14, 15, 16, 17 covered by MSW-driven render tests: all-clear shows verdict + context and **no** review item; items-pending shows the deck's first card naming the CVE, host and IP; medium/low-only shows the all-clear verdict and no finding; the failed-scan and stale-coverage cards render outside the deck; blank renders `home-blank-note` with **no scan-triggering control in the tree for either role**; error renders the copy and `[Retry]` with **no verdict text present**; retry recovers to the right state; the rendered verdict states the `total`-derived number when it exceeds the rows shown. AC 7 — the role-based enabled sweep from Task 5 (never a `[disabled]` attribute query) passes for both roles in every state. Loading renders no element in the verdict's position. `SignedInPlaceholder.tsx` is deleted and `grep -rn "SignedInPlaceholder" frontend/src` returns zero hits.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Routing, not-found, the colour write-back, and the feature gate
- **Description**: Per `ARCHITECTURE.md` §3 (Routing and app root), `DESIGN.md` §Not found and §Colour.
  **(a)** `main.tsx` wraps `BrowserRouter` → `QueryClientProvider` → `SessionProvider` → `App`. `App.tsx` is rewritten to the route table only — its boot refresh and three-way `status` state (lines 7–27) moved to `SessionProvider` in Task 4: `/login` → `Login`; `/` → `RequireSession` → `AppShell` → `Home`; `*` → `NotFound`, with the catch-all **inside** the `RequireSession`/`AppShell` branch. The catch-all **renders, it does not redirect**. `NotFound.tsx` — `That page doesn't exist.` plus a `Go to Home` **link**, inside the shell.
  **(b)** Replace the `<tbd>` accent and severity values in `docs/ui/SCREENS.md` §Color with the approved hexes and their measured contrast ratios (`DESIGN.md` §Colour makes this part of this feature). **Do not** edit any other section — the `device_count`→`host_count` fix and the ADR-008 §Papéis reconciliation are follow-ups outside this feature.
  **(c)** Run the full gate and fix what it reports.
- **Absorbed**: the former standalone "SCREENS.md write-back and gate" task — a `<tbd>` replacement in one doc section plus a command run, with nothing to test and nothing for a reviewer to reason about beyond the gate output it already produces.
- **Dependencies**: Task 4, Task 5, Task 6, Task 8
- **Target Files**: [`frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/pages/NotFound.tsx`, `frontend/src/pages/NotFound.test.tsx`, `docs/ui/SCREENS.md`]
- **Tests**: `App.test.tsx` + `NotFound.test.tsx` — AC 5, 6, 19; routing-level properties no component test can reach.
- **Success Criteria**: AC 5 — rendering at `/` with a failing refresh redirects to `/login` and **no Home text ever appears**. AC 6 — a successful boot refresh lands on Home and the login form is **never** rendered. AC 1 — a successful sign-in lands on `/`. AC 19 — signed in, an unknown path renders `not-found` with the top bar intact and `not-found-home` returns to `/`; signed out, the same path lands on `/login`. No `Navigate` on the catch-all. `App.tsx` contains no `useEffect`, no refresh call and no session state. AC 21 — `npm run lint`, `format:check`, `typecheck`, `test` and `build` all pass in `frontend/`, and `npm run gen:types` produces a **clean diff**. `git diff docs/ui/SCREENS.md` touches §Color only. Nothing under `backend/`, `hardware-agent/` or `contracts/` is modified anywhere in this feature's diff.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 (foundation: deps, tokens, shared components) ──────────► #7 (cards + deck) ──┐
                                                                                  │
#2 (review.ts) ──► #3 (data layer) ──► #4 (session) ──► #5 (shells) ──► #6 (login)│
                        │                                    │             │      │
                        └────────────────────────────────────┴─────────────┴──► #8 (Home)
                                                                                  │
                                                                                  ▼
                                                                     #9 (routing + gate)
```

Two parallel tracks once #1 and #2 start:

- **Track A — data and session**: #2 → #3 → #4 → #5 → #6
- **Track B — presentation**: #1 → #7

They converge at #8 (Home), then #9 closes the feature.

## Status

| # | Task | Test deliverable | Status |
|---|------|------------------|--------|
| 1 | Foundation — deps, token layer, shared components | `Timestamp.test.tsx` | COMPLETED |
| 2 | The pure verdict derivation | `review.test.ts` | COMPLETED |
| 3 | Data layer — modules, MSW handlers, read hook | `useHomeReview.test.ts` | COMPLETED |
| 4 | Session — expiry events, context, guard, renderer | `SessionProvider.test.tsx`, `client.test.ts` | COMPLETED |
| 5 | The two shells and the top bar | `TopBar.test.tsx` | COMPLETED |
| 6 | The LOGIN screen | `Login.test.tsx` | COMPLETED |
| 7 | Home's cards and the finding deck | `FindingDeck.test.tsx` | COMPLETED |
| 8 | The HOME page | `Home.test.tsx` | COMPLETED |
| 9 | Routing, not-found, colour write-back, gate | `App.test.tsx`, `NotFound.test.tsx` | COMPLETED |
