# DESIGN — Login, app shell, Home (DMI-81)

> **Layer note.** The `DESIGN.md` template in `specs/_templates/` is written for Textual
> screens under `hardware-agent/src/agent/tui/screens/`. This feature has no Textual screens —
> it is a React SPA. The template's structure (flow → mockup → layout → copy → states → ids)
> is kept; "key bindings" becomes keyboard/focus behaviour and "widget ids" becomes
> `data-testid` values, since that is what the tests in `frontend/src/**/*.test.tsx` assert on.
>
> **This document does not re-decide `docs/ui/SCREENS.md` §Foundations.** It fills the two
> values SCREENS.md deliberately deferred to the build (the accent purple and the severity
> ramp) and settles the layout and copy SCREENS.md left as prose. Where this document and
> SCREENS.md disagree, SCREENS.md wins and this document is the bug.

---

## Screen flow

```
                    ┌──────────────────────────────┐
  no session  ──►   │  /login       (outside shell)│
                    └──────────────┬───────────────┘
                                   │ credentials accepted
                                   ▼
                    ┌──────────────────────────────┐
                    │  /            (inside shell) │  ◄── boot-time silent refresh
                    │  HOME                        │      lands here directly
                    └──────────────┬───────────────┘
                                   │ [Log out]  ·  session lost  ·  refresh fails
                                   ▼
                                /login
```

Two shells, per SCREENS.md §The auth shell and §App shell:

- **Outside shell** — no top bar, no nav, no `[Log out]`. There is no session and nowhere to
  navigate. Wordmark, ornament, one centred card in the 720px prose column.
- **Inside shell** — the persistent top bar above every signed-in screen.

Only two routes exist in this feature. `/login` and `/`. Any other path renders the not-found
fallback described under **States** below; the nav items for screens that do not exist yet are
covered under **Top bar** below.

---

## Visual mockups

Renders are at the 1440px target. Every layout is fluid: the columns are `max-width`
maximums that shrink with the viewport down to 1280px and degrade gracefully below it
(SCREENS.md §Viewport). Nothing here has a fixed pixel width.

### LOGIN — `/login`

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│                                  DMITRI                    [wordmark]      │
│                             ·  ·  ❦  ·  ·                  #ornament       │
│                                                                            │
│            ┌──────────────────────────────────────────────┐                │
│            │                                              │                │
│            │  Sign in                        [IM Fell 28] │                │
│            │                                              │                │
│            │  Email                                       │                │
│            │  ┌────────────────────────────────────────┐  │                │
│            │  │ ana@northwind.example                  │  │ #login-email   │
│            │  └────────────────────────────────────────┘  │                │
│            │                                              │                │
│            │  Password                                    │                │
│            │  ┌────────────────────────────────────────┐  │                │
│            │  │ ••••••••••••                           │  │ #login-password│
│            │  └────────────────────────────────────────┘  │                │
│            │                                              │                │
│            │  ┌────────────────────────────────────────┐  │                │
│            │  │              Sign in                   │  │ #login-submit  │
│            │  └────────────────────────────────────────┘  │                │
│            │                                              │                │
│            └──────────────────────────────────────────────┘                │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
                            ◄─────── 720px max ───────►
```

**Error state** — the message sits between the password field and the button, so it is inside
the eye's path from the last thing typed to the thing about to be clicked. It is never a toast:
a toast that auto-dismisses takes the error away while the operator is still reading it.

```text
            │  ┌────────────────────────────────────────┐  │
            │  │ ••••••••••••                           │  │
            │  └────────────────────────────────────────┘  │
            │                                              │
            │  ⚠ That email and password don't match.      │  #login-error
            │                                              │
            │  ┌────────────────────────────────────────┐  │
            │  │              Sign in                   │  │
            │  └────────────────────────────────────────┘  │
```

**Submitting state** — the button is its own progress indicator and is disabled. No spinner.

```text
            │  ┌────────────────────────────────────────┐  │
            │  │            Signing in…                 │  │  disabled
            │  └────────────────────────────────────────┘  │
```

The card is the page — there is nothing else on it (SCREENS.md §LOGIN: *the epicenter is the
two fields and the button*). No "forgot password?" link: that screen is out of scope for this
feature and a link to a 404 is worse than no link. It arrives with the screen it points at.

### HOME — `/` — regular, all clear (the common case)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │  #top-bar
├────────────────────────────────────────────────────────────────────────────┤
│  ▔▔▔▔                                                                      │
│                                                                            │
│                                                                            │
│                     Nothing needs your attention.                          │  #home-verdict
│                              [IM Fell 40]                                  │
│                                                                            │
│         Last scan finished yesterday at 21:40 — 12 hosts, no               │  #home-context
│                       critical findings.                                   │
│                          [Plex Mono 15, --ink-muted]                       │
│                                                                            │
│                             ·  ·  ❦  ·  ·                                  │  #home-ornament
│                                                                            │
│                                                                            │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  Pi · online · last seen 2 min ago                                         │  #home-footer
└────────────────────────────────────────────────────────────────────────────┘
                            ◄─────── 720px max ───────►
```

The verdict is vertically centred in the space between the top bar and the footer, not pinned
to the top. On the common day this page is one sentence in a lot of paper, which is the point.
There is **no `PageHeader`** — SCREENS.md §Shared components is explicit that Home does not use
it, because the verdict *is* the header.

### HOME — regular, items pending

One finding is shown at a time. The operator steps through the rest with the arrows — the deck
never grows into a scroll, however bad the day is.

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│              7 things need your review.                                    │  #home-verdict
│                    [IM Fell 40]                                            │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │  #home-deck
│  │ FINDING                                              ┌─────────────┐ │  │  #home-deck-card
│  │ [--accent, 11px, letterspaced]                       │  Critical   │ │  │
│  │                                                      └─────────────┘ │  │
│  │ CVE-2024-4577 on synology-nas (192.168.1.42).                        │  │
│  │ Found in yesterday's 21:40 scan.                                     │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│           ┌───┐                                          ┌───┐             │
│           │ ← │            1 of 5                        │ → │             │  #home-deck-prev
│           └───┘         #home-deck-position              └───┘             │  #home-deck-next
│          disabled                                                          │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ SCAN                                                                 │  │  #home-item-scan
│  │                                                                      │  │
│  │ Last night's scan didn't finish.                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ COVERAGE                                                             │  │  #home-item-coverage
│  │                                                                      │  │
│  │ No successful scan in 6 days.                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  Pi · online · last seen 2 min ago                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

**The verdict counts everything; the deck shows one thing.** `7` above is
`critical total + high total + failed scan + stale coverage` as reported by the API — *not* the
five findings in the deck, and not the number of cards on screen. A screen that counts only what
it renders under-reports danger precisely when there is most of it (`TRUTH.md` acceptance
criterion 17).

**Stepping to the second card:**

```text
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ FINDING                                              ┌─────────────┐ │  │
│  │                                                      │    High     │ │  │
│  │                                                      └─────────────┘ │  │
│  │ Outdated OpenSSH on hp-printer (192.168.1.17).                       │  │
│  │ Found in yesterday's 21:40 scan.                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│           ┌───┐                                          ┌───┐             │
│           │ ← │            2 of 5                        │ → │             │
│           └───┘                                          └───┘             │
```

**One finding only** — no deck, no arrows, no position line. A single card with navigation
chrome around it reads as though something is being withheld.

```text
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ FINDING                                              ┌─────────────┐ │  │
│  │                                                      │  Critical   │ │  │
│  │                                                      └─────────────┘ │  │
│  │ CVE-2024-4577 on synology-nas (192.168.1.42).                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
```

### How the deck behaves

| Rule | Why |
|---|---|
| **Stepping never fetches.** Both finding reads happen once, on load, at the contract's maximum page size. The arrows move through data already in memory | An arrow that issues a request is pagination in costume: it stutters on a slow link and can fail halfway through a review, leaving the operator unsure what they have seen |
| **It stops at both ends; it does not wrap.** At the first card `←` is disabled; at the last, `→` is | Wrapping leaves an operator unable to tell whether they have seen everything — the one doubt this screen must never create |
| **Arrow keys work only when focus is inside the deck.** The deck is a single tab stop; `←`/`→` step while it holds focus. There is **no document-level key handler** | A global arrow listener hijacks page scrolling and fights screen-reader navigation. Scoping it is an accessibility requirement, not a preference |
| **The card region is `aria-live="polite"`** and the position line is real text, not decoration | Stepping changes content without moving focus, so the change must be announced or it is invisible to a screen reader |
| **Order is critical → high, and within a severity newest first** | `ARCHITECTURE.md` §2.2: findings arrive in no caller-chosen order, so `review.ts` imposes this |
| **The scan and coverage cards are not in the deck** | They are not findings, there are at most two, and burying a failed scan behind an arrow press means it can go unseen |
| **The deck's position resets when the underlying data changes** and holds otherwise | Returning to card 1 on an unrelated re-render loses the operator's place; keeping a stale index past a data change shows the wrong finding |

Square-edged cards on `--card` over `--paper`, separated by whitespace rather than by rules.
The **item label** (`FINDING`, `SCAN`, `COVERAGE`) is the only place `--accent` appears on this
screen, per SCREENS.md §Color: *deep purple marks the item label; red appears only inside a
critical-severity badge*. The severity badge sits at the card's top-right, opposite the label,
so the two loud things do not collide — this is the collision SCREENS.md warns about when it
rejects purple-as-critical.

The verdict is **left-aligned in the items-pending state** and centred in the all-clear state.
This is deliberate: with cards below it, a centred sentence floats away from the column of
left-aligned content beneath it. The all-clear state has no such column, so centring holds.

The page is ordered **finding deck → failed scan → stale coverage**, and inside the deck
**critical before high**, within a severity newest first. The order is stable across renders so
the page does not reshuffle under the operator between visits.

### The review-item buttons are drawn but not built

`[View finding]`, `[See why]` and `[Check the Pi]` appear in every mockup above and in the copy
table below. **None of them is rendered in this feature.** Their destinations do not exist:
there is no finding-detail screen anywhere in the product (a finding opens as local state inside
scan detail — SCREENS.md line 834), scan detail is out of scope, and the Agents screen belongs to
DMI-78. A button that navigates nowhere is worse than no button: it is tab-reachable, announced
to a screen reader as an action, and does nothing when pressed — and no test can tell "not wired
yet" apart from "someone forgot to wire it".

This is the same treatment the Pi-status footer gets, for the same reason, and the same reason
LOGIN ships no "forgot password?" link. Drawing them here locks the card's final shape so the
feature that builds each destination adds the button without re-litigating the layout, and so the
screen does not visibly change under the operator when it arrives.

**The card without its button is still the whole promise:** label, severity badge, and a sentence
naming the CVE, the host and the IP. That is what `TRUTH.md` acceptance criteria 10, 12 and 13
now require.

### HOME — stale coverage item

```text
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ COVERAGE                                                             │  │
│  │                                                                      │  │
│  │ No successful scan in 6 days.                                        │  │
│  │                                                                      │  │
│  │ [Check the Pi]                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
```

### HOME — blank (first run, no scan has ever run)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                                                                            │
│                        No scans yet.                                       │  #home-verdict
│                        [IM Fell 40]                                        │
│                                                                            │
│        A scan looks at every machine on your network and reports           │  #home-blank-body
│        what an attacker could see: which are exposed, and which are        │
│        running software with known vulnerabilities. It takes about         │
│        ten minutes and changes nothing on them.                            │
│                                                                            │
│                 Scanning is set up on the Pi itself.                       │  #home-blank-note
│                                                                            │
│                             ·  ·  ❦  ·  ·                                  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**No scan-triggering control ships in this feature, for either role.** `TRUTH.md` fences "Scan
now" and all command-status UI out of scope, and the SPA could not fire one anyway: dispatching a
command needs an `agent_id`, which is the exact thing contract ask C1 leaves unavailable
(§The Pi-status footer is blocked). A `[Run first scan]` button on a first-run screen would be the
worst possible dead control — the one thing the page asks the operator to do, doing nothing.

So the blank state ends on a plain sentence, identical for admins and viewers, that tells the
truth about where scanning currently lives. It is not a CTA and is not styled as one.

**Consequence for role gating:** the blank state no longer splits by role, so this feature's
proof of "absent, not disabled" (`TRUTH.md` AC 7) rests entirely on the `Users` nav item in the
top bar. That is real, rendered, and asserted absent for viewers — one honest instance beats two
where one is theatre.

The footer is omitted in the blank state: there is no scan history to summarise, and a Pi
status line under first-run onboarding competes with the one thing the page is explaining.

### HOME — error

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                                                                            │
│                    Couldn't load your network's status.                    │  #home-error
│                            [IM Fell 32]                                    │
│                                                                            │
│                    ┌──────────────────────┐                                │
│                    │        Retry         │                                │  #home-retry
│                    └──────────────────────┘                                │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

The top bar stays — the operator can still navigate away from a broken Home. No skeleton, no
partial cards: SCREENS.md §HOME forbids a skeleton standing in for a verdict, and a half-
rendered Home is indistinguishable from an all-clear Home, which is the dangerous failure.

### Not found — any unknown path

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home                                                [Log out]    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                                                                            │
│                     That page doesn't exist.                               │  #not-found
│                          [IM Fell 32]                                      │
│                                                                            │
│                          Go to Home                                        │  #not-found-home
│                                                                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

Rendered, **not redirected**. Silently bouncing a mistyped URL to Home makes the product look as
though it ignored the operator, and a stale bookmark then gives no clue why it stopped working.

It sits **inside the shell** when there is a session, so the top bar is still there to leave by —
the same reasoning as the error state. With no session, the route guard runs first and sends the
operator to `/login`: an unknown path is not a reason to skip the session check.

`Go to Home` is a link, not a button. It navigates somewhere that exists, which is the whole
difference between this control and the ones removed elsewhere in this feature.

### HOME — loading

The first load renders **nothing below the top bar** — no skeleton, no spinner, no placeholder
sentence. Same reason as the error state: any placeholder in the verdict's position is read as
a verdict. The gap is four plain reads issued together — the latest scan, the latest successful
scan, and the critical and high findings — and it is the only wait on this screen: stepping
through the deck afterwards touches no network at all. If the load ever stops being fast, that is
a backend problem to fix rather than a spinner to add.

---

## Top bar

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │
│           ▔▔▔▔   └──────────── not in v1 ─────────────┘                    │
└────────────────────────────────────────────────────────────────────────────┘
  wordmark   nav (left)                                        action (right)
```

- Wordmark left, nav items left-adjacent, `[Log out]` right (SCREENS.md §App shell).
- **While the nav holds exactly one item, that item is centred in the bar. From the second
  item on it returns to left-adjacent, as drawn above. Decided 2026-07-31.** A single link
  floating beside the wordmark reads as an orphan rather than as navigation; a group of six
  does not. As shipped in v1:

  ```text
  ┌────────────────────────────────────────────────────────────────────────────┐
  │ DMITRI                        Home                            [Log out]    │
  │                               ▔▔▔▔                                         │
  └────────────────────────────────────────────────────────────────────────────┘
    wordmark                   nav (centred)                     action (right)
  ```

  The centring is true bar-centring, not the midpoint between the wordmark and `[Log out]` —
  those have different widths, and splitting the difference lands a few pixels off in a way
  that reads as a mistake. `TopBar` uses three grid tracks with equal `1fr` sides for this.
  **The feature that adds the second nav item owns reverting this**, and the rule is stated
  here rather than encoded in `TopBar` because a count-driven layout branch would be
  speculative machinery for a transition that happens exactly once.
- The active item is marked with `--accent` — a 2px underline plus `--ink` text weight, not a
  filled pill. Nav is the only other place `--accent` appears in this feature.
- **When `Users` arrives it is omitted for viewers**, never disabled — the shell's instance of
  rule 3. It is not in this feature; see below.
- **Only `Home` is rendered in this feature.** `Scans`, `Hosts`, `Agents`, `Users` and
  `Settings` arrive with the features that build their screens. Rendering them now would mean
  links to nothing — the same decision taken for the review-item buttons and the blank state's
  CTA, for the same reason. SCREENS.md §App shell argues the nav is muscle memory and should not
  churn, but that argument is about *renaming* a destination that exists, not about shipping
  links to screens that do not. **The mockups above draw the full nav** so the final shape stays
  visible and reviewable; only `Home` ships. (Decided 2026-07-28.)
- **In v1 the top bar renders `Home` alone, identically for admins and viewers.** `Users` is the
  role-gated item, and it arrives with the Users screen — carrying the role-gating primitive and
  the test that proves a viewer never sees it. Consequence: **this feature has no admin-only
  affordance at all**, so its guarantee is the stronger negative one — nothing anywhere renders
  in a disabled state (`ARCHITECTURE.md` §4).

---

## Colour — filling SCREENS.md's two deferred values

SCREENS.md §Color locks the neutrals and leaves the accent and severity hexes `<tbd>`,
deliberately, to be auditioned against real screens during this build. These are the proposals.
**All are measured against `--paper` `#FAF8F4`**, which is the only surface they appear on.

### Accent — deep purple

| Token | Hex | Contrast on `--paper` | White text on it | Role |
|---|---|---|---|---|
| `--accent` | `#7C3AED` | **5.37:1** (AA) | **5.70:1** (AA) | active nav item, primary buttons, the review-item label. Nothing else. |

**Chosen 2026-07-28**, replacing the earlier `#5B21B6` proposal. It clears AA both as text on
paper and as a button ground under white text, which is what lets one value do both jobs instead
of needing a darker "on-paper" variant and a lighter "button" variant.

It is brighter and more violet than the deep `#5B21B6` first proposed, and that is the point —
the accent should read as the one loud thing on a quiet page without going sombre. The trade is
real and worth stating: `#5B21B6` cleared **AAA** on both counts (8.5:1 and 9.0:1) where this
clears AA. Both are conformant for the uses above; only `#5B21B6` had headroom to spare.

**The floor is 4.5:1, not 3:1**, because `--accent` is used as *text* — the review-item label and
the active nav item — not merely as a control boundary. A lighter purple in this family fails
that bar: `#9F55D9`, considered and rejected the same day, measures 4.15:1 on paper and 4.40:1
under white text. Any future adjustment to this token must be re-measured against both numbers,
not eyeballed.

### Severity ramp

Conventional hues on purpose — the org admin is non-technical and red already means *bad*
without being taught. Badges are text, so each owes **4.5:1**, not the 3:1 control floor.

| Severity | Hue | Hex | Contrast on `--paper` | Surfaces on Home |
|---|---|---|---|---|
| Critical | red | `#B91C1C` | **6.1:1** (AA) | yes |
| High | orange | `#C2410C` | **4.9:1** (AA) | yes |
| Medium | amber | `#A16207` | **4.6:1** (AA) | never |
| Low | blue | `#1D4ED8` | **6.3:1** (AA) | never |
| Informational | — | `#6B6862` | 5.2:1 (AA) | never | 

Only critical and high have a rendered badge in this feature; medium and low are specified now
because the ramp is a set — picking two of five and deferring the rest guarantees a mismatched
pair later. Blue appears here and nowhere else, exactly as SCREENS.md permits: no blue as a
brand colour, blue as a low-severity semantic token.

**These are proposals for the approval gate.** If they are approved they are written back into
`docs/ui/SCREENS.md` §Color as part of this feature — that section is the product's source of
truth for colour, and leaving it `<tbd>` while the code carries real hexes is exactly the drift
the doc exists to prevent.

### Badge treatment

Severity badges are the severity colour as **text on a 10%-tint ground of the same hue**, with
a 1px border at the full colour — not white-on-solid. A solid red block at the top-right of a
card out-shouts the accent label and turns a quiet page into an alarm. The tint keeps the
badge legible as a label while the sentence beneath it stays the thing being read.

---

## Layout

| Region | Rule |
|---|---|
| Prose column | `max-width: 720px`, centred. Both screens (SCREENS.md §Viewport: Home and all auth screens are prose-led). |
| Top bar | Full-bleed `--card` ground, `--rule` bottom border, contents constrained to the same 720px column so the wordmark aligns with the verdict. |
| Home vertical rhythm | All-clear: verdict block vertically centred in the viewport minus chrome. Items-pending: verdict at the top of the column, cards below, page scrolls normally. |
| Review card | Square edges (`--radius: 0`), `--card` ground, 1px `--rule` border, generous internal padding. Full column width. The card's action button is drawn in the mockups but **not built in this feature** — see below. |
| Footer | `--ink-muted`, small, pinned below the content — not fixed to the viewport bottom. **⛔ Not implementable in this feature** — see below. |
| Long values | Hostnames and IPs in review items wrap; they never widen the column (§Building rules 4). UUIDs do not appear on either screen. |
| Horizontal scroll | Never on the page body. Neither screen has wide content in this feature. |

---

## Keyboard and focus

| Where | Behaviour |
|---|---|
| Login | Email autofocused on mount. Real `<form>`; Enter submits from either field. `autocomplete="email"` and `autocomplete="current-password"` — password managers are a feature, not an edge case (SCREENS.md §The auth shell). |
| Login error | The error region is `role="alert"` so it is announced, not just drawn. |
| Login submitting | Button `disabled` — Enter and repeat clicks cannot double-submit. |
| Top bar | Nav items are real links, tab-reachable in reading order, `[Log out]` last. |
| Home | Nothing is autofocused; the page is read, not operated. No review-item buttons and no scan CTA ship in this feature. |
| Home — finding deck | One tab stop for the whole deck. While it holds focus, `←` and `→` step between findings; the handler is bound to the deck, **never to `document`**, so page scrolling and screen-reader keys are untouched elsewhere. The `←`/`→` buttons are separately tab-reachable and do the same thing on click or Enter. A disabled end arrow is skipped by Tab. The card region is `aria-live="polite"` so a step is announced without stealing focus. |
| Focus ring | `--accent` at 2px offset, on every interactive element. Never removed. |

---

## Copy

Exact strings. Real hostnames, real CVE ids, real IPs — no lorem, no `foo` (§Consistency rule 9).

### Login

| Element | Copy |
|---|---|
| Title | `Sign in` |
| Email label | `Email` |
| Password label | `Password` |
| Button, idle | `Sign in` |
| Button, in flight | `Signing in…` |
| Error — rejected credentials | `That email and password don't match.` |
| Error — backend unreachable | `Can't reach the server. Check your connection and try again.` |

The credential error names neither field and distinguishes no case — it is the same string
whether the email is unknown or the password is wrong (SCREENS.md §The auth shell: *never
reveal whether an account exists*). The network error is deliberately a different string,
because "your password is wrong" is a lie when the server is down and sends the operator to
reset a password that was fine.

### Home

| Element | Copy |
|---|---|
| Verdict — all clear | `Nothing needs your attention.` |
| Context — all clear | `Last scan finished yesterday at 21:40 — 12 hosts, no critical findings.` Sourced from the most recent **successful** scan and its own `host_count` (`ARCHITECTURE.md` §2.5) — "finished" must not describe a scan that failed |
| Verdict — one item | `1 thing needs your review.` |
| Verdict — several items | `{n} things need your review.` |
| Item label — finding | `FINDING` |
| Item label — scan | `SCAN` |
| Item label — coverage | `COVERAGE` |
| Review item — finding | `{CVE or title} on {hostname} ({ip}). Found in last night's scan.` |
| Deck position | `{i} of {n}` — `i` is the card in view, `n` the findings in the deck. Not the verdict's count, which is larger whenever a scan failed or coverage is stale |
| Deck previous | `←`, accessible name `Previous finding` |
| Deck next | `→`, accessible name `Next finding` |
| Review item — finding button | `View finding` ⛔ not built in this feature |
| Review item — scan failed | `Last night's scan didn't finish.` |
| Review item — scan failed button | `See why` ⛔ not built in this feature |
| Review item — stale coverage | `No successful scan in {n} days.` |
| Review item — stale coverage button | `Check the Pi` ⛔ not built in this feature |
| Footer — Pi online | `Pi · online · last seen {relative}` ⛔ blocked |
| Footer — Pi offline | `Pi · offline · last seen {relative}` ⛔ blocked |
| Blank — verdict | `No scans yet.` |
| Blank — body | `A scan looks at every machine on your network and reports what an attacker could see: which are exposed, and which are running software with known vulnerabilities. It takes about ten minutes and changes nothing on them.` |
| Blank — how scanning works | `Scanning is set up on the Pi itself.` — one sentence, both roles, not a button |
| Error | `Couldn't load your network's status.` |
| Error button | `Retry` |
| Not found — heading | `That page doesn't exist.` |
| Not found — link | `Go to Home` |

`last night's` is only correct when the scan ran overnight. The build renders the scan's
recency through the shared `Timestamp` rule instead: relative inside 7 days, absolute beyond
(§Consistency rule 7), so the finding item reads `Found in yesterday's 21:40 scan.` when that
is what happened. The strings above are SCREENS.md's, kept verbatim so the divergence is
visible and reviewable rather than silently "fixed".

---

## States

| Screen | State | Trigger | Render |
|---|---|---|---|
| Login | idle | mount | form, email focused |
| Login | submitting | submit | button reads `Signing in…`, disabled |
| Login | credential error | backend rejects | inline error above the button, form re-enabled, password preserved |
| Login | network error | request never lands | inline error above the button, different string |
| Home | loading | first load | nothing below the top bar |
| Home | blank | no scan has ever run | first-run onboarding + the sentence about where scanning lives; no CTA, no role split |
| Home | regular, all clear | recent scan, no critical/high, coverage fresh | verdict + context + ornament + footer |
| Home | regular, items pending | ≥1 critical/high finding, or last scan failed, or coverage stale | verdict + finding deck (when there are findings) + scan/coverage cards + footer |
| Home | items pending, one finding | exactly 1 critical/high finding | the card alone — no arrows, no position line |
| Home | items pending, no findings | 0 critical/high, but the scan failed or coverage is stale | no deck at all; the scan/coverage cards carry the page |
| Home | error | any required read fails | error copy + `[Retry]`, top bar intact |
| Any other route | not found | unknown path, signed in | not-found copy + link to Home, inside the shell |
| Any other route | — | unknown path, signed out | the route guard wins: redirect to `/login` |

**Blank vs all-clear is not the same emptiness.** Blank means *nothing has ever happened* and
teaches; all-clear means *something happened and it was fine* and reassures. Collapsing them
into one empty state is the most likely implementation shortcut here, and it produces a screen
that tells a first-run operator everything is fine when nothing has been checked.

---

## `data-testid` values

Named here so the tests in `ARCHITECTURE.md`'s testing table have stable anchors.

| id | Element |
|---|---|
| `login-form` | the `<form>` |
| `login-email` | email input |
| `login-password` | password input |
| `login-submit` | submit button |
| `login-error` | inline error region (`role="alert"`) |
| `top-bar` | the shell's top bar |
| `nav-users` | the Users nav item — **asserted absent for viewers** (criterion 7) |
| `log-out` | log out button |
| `home-verdict` | the verdict sentence |
| `home-context` | the all-clear context sentence |
| `home-deck` | the finding deck wrapper — the single tab stop, owns the arrow-key handler |
| `home-deck-card` | the finding card currently in view (`aria-live="polite"`) |
| `home-deck-position` | the `{i} of {n}` line — **absent when there is only one finding** |
| `home-deck-prev` | previous arrow — **asserted `disabled` on the first card** |
| `home-deck-next` | next arrow — **asserted `disabled` on the last card** |
| `home-item-scan` | the failed-scan card, outside the deck |
| `home-item-coverage` | the stale-coverage card, outside the deck |
| `home-item-severity` | severity badge inside the finding card |
| `home-blank-note` | blank-state sentence about where scanning lives — same for both roles |
| `home-error` | error copy |
| `home-retry` | retry button |
| `not-found` | not-found heading |
| `not-found-home` | the link back to Home |
| `home-footer` | Pi status footer |

---

## The Pi-status footer is blocked, and it is not this feature's blocker to clear

The footer (`Pi · online · last seen 2 min ago`) needs `AgentDetail.online` and
`last_seen_at`. The SPA cannot get them: `GET /agents/{agent_id}` needs an `agent_id`, and
**there is no `/api/v1/agents` collection anywhere in the contract** — only
`/agents/{agent_id}` (line 526) and `/agents/{agent_id}/commands` (line 429). That is contract
ask **C1**, owned by **DMI-78** (*Add `GET /agents` and the Pi's target network*).

No workaround is specified here — not a `VITE_AGENT_ID`, not a hardcoded UUID, not inferring
the agent from a scan. Each would harden a guess into the first real screen of the product.

**Consequence:** the footer is drawn in the mockups above but **is not built in this feature**.
The all-clear and items-pending states render without it. It arrives when DMI-78 lands.

**The stale-coverage item survives**, because the 3-day rule is computable from the timestamp of
the most recent *successful* scan and needs no agent read — that record is fetched with
`status: 'completed'` (`ARCHITECTURE.md` §2.5), which is why the copy can honestly say
"successful". Only SCREENS.md's *"The Pi hasn't been seen since Tuesday."* variant is blocked;
`No successful scan in {n} days.` is not.

One state that copy must cover: an organisation whose scans have **all** failed has no successful
scan to count days from. Show the failed-scan item alone and omit the stale-coverage line — Home
does not say "stale since never".

---

## Open questions for the approval gate

1. **Accent and severity hexes** (§Colour) — approve, or audition alternatives. If approved,
   this feature also writes them into `docs/ui/SCREENS.md` §Color, replacing the `<tbd>`s.
2. **Nav items for screens that do not exist yet** (§Top bar) — recommendation is Home-only,
   growing as screens land.
3. ~~**The `View finding` and `See why` destinations do not exist.**~~ **Resolved 2026-07-28:**
   the buttons are drawn in the mockups and **not rendered** in this feature. The item states the
   CVE, the host and the IP, which is what makes it actionable; each button arrives with the
   screen it points at. `TRUTH.md` story 3 and acceptance criteria 10, 12 and 13 were reworded to
   promise plain words rather than a control. See §The review-item buttons are drawn but not built.
4. ~~**`Run first scan` in the blank state.**~~ **Resolved 2026-07-28:** dropped for both roles.
   The blank state ends on `Scanning is set up on the Pi itself.` — a sentence, not a CTA.
   `TRUTH.md` acceptance criterion 14 was rewritten to drop its admin/viewer split, which now
   rests solely on the `Users` nav item. See §HOME — blank.
