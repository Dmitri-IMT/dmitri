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

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│              3 things need your review.                                    │  #home-verdict
│                    [IM Fell 40]                                            │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ FINDING                                              ┌─────────────┐ │  │  #home-item-0
│  │ [--accent, 11px, letterspaced]                       │  Critical   │ │  │
│  │                                                      └─────────────┘ │  │
│  │ CVE-2024-4577 on synology-nas (192.168.1.42).                        │  │
│  │ Found in last night's scan.                                          │  │
│  │                                                                      │  │
│  │ [View finding]                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ FINDING                                              ┌─────────────┐ │  │  #home-item-1
│  │                                                      │    High     │ │  │
│  │                                                      └─────────────┘ │  │
│  │ Outdated OpenSSH on hp-printer (192.168.1.17).                       │  │
│  │ Found in last night's scan.                                          │  │
│  │                                                                      │  │
│  │ [View finding]                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ SCAN                                                                 │  │  #home-item-2
│  │                                                                      │  │
│  │ Last night's scan didn't finish.                                     │  │
│  │                                                                      │  │
│  │ [See why]                                                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  Pi · online · last seen 2 min ago                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

Square-edged cards on `--card` over `--paper`, separated by whitespace rather than by rules.
The **item label** (`FINDING`, `SCAN`, `COVERAGE`) is the only place `--accent` appears on this
screen, per SCREENS.md §Color: *deep purple marks the item label; red appears only inside a
critical-severity badge*. The severity badge sits at the card's top-right, opposite the label,
so the two loud things do not collide — this is the collision SCREENS.md warns about when it
rejects purple-as-critical.

The verdict is **left-aligned in the items-pending state** and centred in the all-clear state.
This is deliberate: with cards below it, a centred sentence floats away from the column of
left-aligned content beneath it. The all-clear state has no such column, so centring holds.

Cards are ordered **critical findings → high findings → failed scan → stale coverage**, and
within a severity by detection time, newest first. The order is stable across renders so the
page does not reshuffle under the operator between visits.

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
│                    ┌──────────────────────┐                                │
│                    │   Run first scan     │                                │  #home-first-scan
│                    └──────────────────────┘        ADMIN ONLY — omitted    │
│                                                    entirely for viewers    │
│                             ·  ·  ❦  ·  ·                                  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

Viewer variant — the button is **absent from the DOM**, replaced by a sentence. This is the
literal test of consistency rule 3 and acceptance criterion 7:

```text
│                    Ask your admin to run the first scan.                   │  #home-viewer-note
```

The footer is omitted in the blank state: there is no scan history to summarise, and a Pi
status line under first-run onboarding competes with the one thing the page is asking for.

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

### HOME — loading

The first load renders **nothing below the top bar** — no skeleton, no spinner, no placeholder
sentence. Same reason as the error state: any placeholder in the verdict's position is read as
a verdict. The gap is a plain read of two or three fast endpoints; if it ever stops being fast,
that is a backend problem to fix rather than a spinner to add.

---

## Top bar

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Scans  Hosts  Agents  Users  Settings         [Log out]    │
│           ▔▔▔▔                                                             │
└────────────────────────────────────────────────────────────────────────────┘
  wordmark   nav (left)                                        action (right)
```

- Wordmark left, nav items left-adjacent, `[Log out]` right (SCREENS.md §App shell).
- The active item is marked with `--accent` — a 2px underline plus `--ink` text weight, not a
  filled pill. Nav is the only other place `--accent` appears in this feature.
- **`Users` is omitted for viewers**, not disabled. It is the shell's instance of rule 3.
- **Open question for the build — nav items whose screens do not exist yet.** Only `Home`
  exists in this feature; `Scans`, `Hosts`, `Agents`, `Users`, `Settings` all arrive in later
  features. Rendering them as links to a 404 teaches the operator the product is broken.
  Recommended: **render only `Home` in this feature and add each item with the feature that
  builds its screen.** SCREENS.md §App shell argues the nav is muscle memory and that items
  should not churn — but that argument is about *renaming* an existing destination, not about
  shipping links to nothing. Flag for approval; the mockups above draw the full nav so the
  final shape is visible.

---

## Colour — filling SCREENS.md's two deferred values

SCREENS.md §Color locks the neutrals and leaves the accent and severity hexes `<tbd>`,
deliberately, to be auditioned against real screens during this build. These are the proposals.
**All are measured against `--paper` `#FAF8F4`**, which is the only surface they appear on.

### Accent — deep purple

| Token | Hex | Contrast on `--paper` | White text on it | Role |
|---|---|---|---|---|
| `--accent` | `#5B21B6` | **8.5:1** (AAA) | **9.0:1** (AAA) | active nav item, primary buttons, the review-item label. Nothing else. |

It clears AAA both as text on paper and as a button ground under white text, which is what lets
one value do both jobs instead of needing a darker "on-paper" variant and a lighter "button"
variant. Deep and saturated rather than lavender — on a warm paper surface a lighter purple
goes muddy and stops reading as the one loud thing.

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
| Review card | Square edges (`--radius: 0`), `--card` ground, 1px `--rule` border, generous internal padding. Full column width. |
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
| Home | Nothing is autofocused; the page is read, not operated. Review-item buttons are tab-reachable in card order. |
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
| Context — all clear | `Last scan finished yesterday at 21:40 — 12 hosts, no critical findings.` |
| Verdict — one item | `1 thing needs your review.` |
| Verdict — several items | `{n} things need your review.` |
| Item label — finding | `FINDING` |
| Item label — scan | `SCAN` |
| Item label — coverage | `COVERAGE` |
| Review item — finding | `{CVE or title} on {hostname} ({ip}). Found in last night's scan.` |
| Review item — finding button | `View finding` |
| Review item — scan failed | `Last night's scan didn't finish.` |
| Review item — scan failed button | `See why` |
| Review item — stale coverage | `No successful scan in {n} days.` |
| Review item — stale coverage button | `Check the Pi` |
| Footer — Pi online | `Pi · online · last seen {relative}` ⛔ blocked |
| Footer — Pi offline | `Pi · offline · last seen {relative}` ⛔ blocked |
| Blank — verdict | `No scans yet.` |
| Blank — body | `A scan looks at every machine on your network and reports what an attacker could see: which are exposed, and which are running software with known vulnerabilities. It takes about ten minutes and changes nothing on them.` |
| Blank — admin button | `Run first scan` |
| Blank — viewer note | `Ask your admin to run the first scan.` |
| Error | `Couldn't load your network's status.` |
| Error button | `Retry` |
| Not found (any other route) | `That page doesn't exist.` + `Go to Home` |

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
| Home | blank | no scan has ever run | first-run onboarding, admin CTA or viewer note |
| Home | regular, all clear | recent scan, no critical/high, coverage fresh | verdict + context + ornament + footer |
| Home | regular, items pending | ≥1 critical/high finding, or last scan failed, or coverage stale | verdict + cards + footer |
| Home | error | any required read fails | error copy + `[Retry]`, top bar intact |
| Any other route | not found | unknown path | not-found copy + link to Home, inside the shell if signed in |

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
| `home-item` | each review card (queried as a set, ordered) |
| `home-item-severity` | severity badge inside a finding card |
| `home-first-scan` | blank-state admin CTA — **asserted absent for viewers** (criterion 14) |
| `home-viewer-note` | blank-state viewer sentence |
| `home-error` | error copy |
| `home-retry` | retry button |
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

**The stale-coverage item survives**, because the 3-day rule is computable from the latest
scan's `timestamp` alone and needs no agent read. Only SCREENS.md's *"The Pi hasn't been seen
since Tuesday."* variant is blocked; `No successful scan in {n} days.` is not.

---

## Open questions for the approval gate

1. **Accent and severity hexes** (§Colour) — approve, or audition alternatives. If approved,
   this feature also writes them into `docs/ui/SCREENS.md` §Color, replacing the `<tbd>`s.
2. **Nav items for screens that do not exist yet** (§Top bar) — recommendation is Home-only,
   growing as screens land.
3. **The `View finding` and `See why` destinations do not exist.** Both point at scan detail
   (`/scans/:scanId`), which is out of scope for this feature. Options: render the buttons and
   let them land on the not-found page (bad), omit the buttons until scan detail ships
   (leaves review items with no next step, violating consistency rule 2), or ship a minimal
   scan-detail route in this feature (scope creep). **Recommendation: omit the buttons in this
   feature and state the finding fully enough to be actionable without one** — the item still
   names the CVE, the host and the IP. Needs a decision; it is the one place where this
   feature's fence and SCREENS.md's copy genuinely conflict.
4. **`Run first scan` in the blank state points at Agents**, which is also out of scope, and
   "Scan now" is explicitly fenced out of this feature. Same problem as (3). Recommendation:
   keep the blank-state copy, omit the CTA for both roles in this feature, and show the viewer
   sentence to everyone until Agents ships. This weakens acceptance criterion 14's admin half —
   flagging rather than silently dropping it.
