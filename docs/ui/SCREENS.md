# UI Screens — Specs

> **Status:** draft (2026-07-13) — **Foundations written**; the severity hexes are the only value
> still open. Home is drafted; remaining screens are templates.
>
> **This document is the source of truth for the UI.** Where it disagrees with an ADR or a roadmap
> doc, it wins and they get reconciled to it — [`ADR-008`](../adr/ADR-008-frontend-stack.md) owns
> the *stack*, this owns the *screens*. Bottom layer of the UI docs ladder:
> [`REFERENCE.md`](REFERENCE.md) (principles) → [`FLOWS.md`](FLOWS.md) (breadboards) →
> **SCREENS.md** (foundations, layouts, states, copy). A screen section may only be written after its
> flow is locked in FLOWS.md, and each section is filled **top to bottom** — the template order is the
> method: epicenter first, chrome last ([`REFERENCE.md`](REFERENCE.md) §2, §5, §6, §7).

## Foundations

Shared decisions every screen inherits. A screen spec may not re-decide any of these; if a screen
needs an exception, it changes the rule here or it doesn't ship.

### App shell

**Top bar, no sidebar.** One horizontal bar above every inside-shell screen: wordmark left, nav
items (Home · Scans · Hosts · Agents · Users · Settings), `[Log out]` right. **Users** is omitted
for viewers, not disabled.

**The nav is left-adjacent.** It was centred for as long as it held exactly one item, because a lone
link sitting beside the wordmark reads as an orphaned control rather than as navigation. That was
always transitional: spec 028 added `Settings` as the second item and reverted the centring, as
promised. *Decided 2026-07-31; reverted 2026-08-07.* Shipped today: `Home` and `Settings`, both
visible to either role.

**The nav names domains, not actions.** *Users* is the place user-related things live, and it keeps
that name even in v1, when the only thing in it is the invite form. Nav is muscle memory — an item
that renames itself between releases costs more than the thin page it was protecting the operator
from. New user-related surfaces are added *inside* Users rather than beside it.

A handful of destinations with no sub-levels do not earn a persistent vertical rail, and Home — a
mostly empty page whose epicenter is one centered sentence — is actively harmed by a heavy chrome
column beside it (§2 epicenter, §9 context over consistency). Nothing in the MVP has the
section/subsection depth a sidebar exists to express.

> [`ADR-008`](../adr/ADR-008-frontend-stack.md) §Roteamento previously described the `AppShell` as
> *"sidebar/navbar persistente"*; it was narrowed to **top bar, no sidebar** on 2026-07-13 to match
> this section.

### Theme

**Light only.** The MVP ships one theme: paper-white surface, body text near-black with a slight
grey cast (never pure `#000`), deep purple accent. There is no theme toggle and no
`prefers-color-scheme` branch — dark mode is not built, not detected, not stubbed.

The anchor references are light ([`nous-home.png`](nous-research/nous-home.png),
[`psyche-header.png`](nous-research/psyche-header.png)), and the paper/engraving/print direction is
native to a light surface. Shipping one theme halves the palette work and removes an entire class of
contrast bug — and a product with a point of view picks a look rather than exporting it to a toggle
(§8). Dark mode stays parked in [`IDEAS.md`](IDEAS.md) → Theming.

**Dark mode is planned, not abandoned** — it is deliberately a later, separate pass
([`IDEAS.md`](IDEAS.md) → Theming).

**Consequence for tokens:** every color below is validated against the light surface only. Do not
author `dark:` variants in Tailwind as you go — a half-built dark mode is the worst outcome, since
it costs dual tokens on every component and still ships a surface nobody validated. When dark mode
is scoped it re-derives its palette from scratch rather than inheriting inversions of the light one.

### Typography

**Two faces. Titles are set; everything else is typed.**

| Face | Covers | Rationale |
| --- | --- | --- |
| **[IM Fell English](https://fonts.google.com/specimen/IM+Fell+English)** (regular + italic) | **Titles at every level** — the Home verdict, page titles, section and card titles, table captions, blank-slate headings | The brand face. 17th-century letterforms carry the engraving direction natively ([`IDEAS.md`](IDEAS.md) → Visual direction) |
| **[IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono)** | **All non-title text** — body copy, form labels and values, buttons, table cells, badges, and all technical data (IP, MAC, CVE, UUID, port) | Vintage-computer feel with real lineage (IBM Selectric / mainframe era) but legible at 13px in dense tables, which retro faces generally are not |

**No third face.** Prose and data share IBM Plex Mono, which is what
[`nous-home.png`](nous-research/nous-home.png) does — mono for section titles, body, *and* the
`OUTPUT / SEED` data. It works here because Dmitri has almost no long prose: the longest sentences
on any screen are the verdict and the blank-slate copy, and those are IM Fell.

**Escape hatch, if mono prose ever proves tiring:** [IBM Plex
Sans](https://fonts.google.com/specimen/IBM+Plex+Sans) — same superfamily, shared metrics, so it
drops in for body copy without re-tuning anything. Adopting it is a change to *this section*, not a
per-screen decision.

**Size floor:** IM Fell is **never set below 16px** — its inked, irregular letterforms degrade
below that. Any label small enough to need 13–14px is by definition not a title, and is therefore
Plex Mono. This rule is what keeps the split honest.

> **Note on the references:** [`hermes.png`](nous-research/hermes.png) — Nous's *product* UI — uses
> a neutral sans and reserves character for small letterspaced accent labels; the expressive
> typography lives on their *marketing* site. Dmitri deliberately goes further than Hermes. If a
> dense screen (Host inventory, Scan detail) later proves hostile to read, the size floor and the
> Plex Sans escape hatch are the two levers — not a per-screen exception.

### Color

#### Neutrals — locked

The whole product is these six values plus one accent. Ratios are WCAG, measured against the
surface each token actually sits on; there is no dark variant to validate (§Theme).

| Token | Hex | Role | Contrast |
| --- | --- | --- | --- |
| `--paper` | `#FAF8F4` | page surface — warm off-white, the "sheet of paper" | — |
| `--card` | `#FFFFFF` | raised surface: cards, table headers | 1.06 vs paper (separation by warmth, not by grey) |
| `--ink` | `#1A1917` | primary text. Near-black with a warm grey cast, **never** `#000` | **16.6** on paper (AAA) |
| `--ink-muted` | `#6B6862` | secondary text: the Home footer, timestamps, helper copy | **5.2** on paper (AA) |
| `--rule` | `#E5E0D8` | decorative separators — table row lines, the dashed rules | non-text |
| `--edge` | `#8C8880` | real UI-component boundaries: input and button borders | **3.3** on paper (meets the 3:1 floor for controls) |

Two borders, deliberately: `--rule` is decoration and may be as faint as it likes, but the outline
of an *input* is a control boundary and owes 3:1 (WCAG 1.4.11). Using the faint one for both is the
common way a paper-white UI ends up with invisible form fields.

#### Accent and severity

The deep purple and the four severity hexes were auditioned against real screens during the
build and are now locked, measured against `--paper` `#FAF8F4`, the only surface they appear on.

| Token | Hex | Contrast on `--paper` | White text on it | Role |
| --- | --- | --- | --- | --- |
| `--accent` | `#7C3AED` | **5.37:1** (AA) | **5.70:1** (AA) | active nav item, primary buttons, the review-item label. Nothing else. |

The **hues are assigned** and the rules are locked.

- **Purple is the brand accent, and nothing else.** It marks focal points — the active nav item,
  primary buttons, the review-item label on Home — the role the muted blue plays in
  [`hermes.png`](nous-research/hermes.png): small, saturated, the only loud thing on a quiet
  surface. **Purple never carries severity.** It was briefly considered for `critical` and
  rejected: a color that means both "act here" and "you are in danger" means neither, and on Home
  the critical badge would collide with the `[View finding]` button beside it.
- **Severity owns its own hues, and never borrows the accent.** The ramp is conventional on
  purpose — the org admin is non-technical (§10 zero training) and red already means *bad* to them
  without being taught.
- **Every value clears AA on `--paper`** before it ships. Severity badges are text, so they owe
  **4.5:1**, not the 3:1 control floor — the usual trap when picking a red that "looks right".

| Severity | Hue | Hex | Contrast on `--paper` | Usage |
| --- | --- | --- | --- | --- |
| Critical | **red** | `#B91C1C` | **6.1:1** (AA) | the loudest thing in the product; surfaces on Home |
| High | **orange** | `#C2410C` | **4.9:1** (AA) | surfaces on Home |
| Medium | **amber** | `#A16207` | **4.6:1** (AA) | never surfaces on Home |
| Low | **blue** | `#1D4ED8` | **6.3:1** (AA) | never surfaces on Home |
| Informational | **ink-muted** | `#6B6862` | **5.2:1** (AA) | visual token only — not a contract severity |

Blue appears here and nowhere else. The old "no blue anywhere" rule existed to protect the accent,
and it still does in that form: **no blue as a brand color** — but as a low-severity semantic token
it is doing a different job, exactly as red does at critical.

**These were the only unfilled values in Foundations**, now resolved.

### Spacing and rhythm

Building rule 1 says spacing comes from the token set. This is that set. **Whitespace is the
loudest thing on these screens** — on a normal day Home is one sentence in a lot of paper, and
that emptiness is the design, not an unfinished layout. Spacing is therefore specified as
deliberately as color.

**The base unit is 4px** — Tailwind v4's `--spacing` default, so the `p-*` / `gap-*` / `space-y-*`
utilities already resolve to it and no custom token layer is needed.

**Use these steps and no others:**

| Step | Value | Used for |
| --- | --- | --- |
| `1` | 4px | icon-to-text, badge internals |
| `2` | 8px | label-to-value, items inside one group |
| `3` | 12px | tight stack — table cell padding |
| `4` | 16px | default gap between related elements |
| `6` | 24px | card internal padding |
| `8` | 32px | between cards in a list |
| `12` | 48px | between sections of a screen |
| `16` | 64px | around the epicenter — the verdict's breathing room |
| `24` | 96px | top offset for a vertically-centred, near-empty screen |

Anything else — `p-5`, `gap-7`, `mt-[13px]` — is a bug by Building rule 1. An arbitrary-value
utility (`p-[13px]`) is the same bug wearing brackets: if a value is worth using it is worth
being a step.

**Four rhythm rules, binding:**

1. **The parent owns the space between children.** Components ship with **no outer margin** —
   they render flush to their own bounding box, and the layout that places them supplies the
   gap. A component with `mb-4` baked in dictates its own spacing everywhere it is ever reused,
   and the second use site always fights it. This is the single rule that keeps a component
   library composable.
2. **Gap, not margins between siblings.** Use flex/grid `gap-*` on the container. Sibling margins
   collapse unpredictably, leave orphaned space when an item is conditionally absent, and make
   "what is the space here" a question with two answers.
3. **Space groups things; it does not decorate.** Related elements sit closer than unrelated ones
   — proximity is how the eye parses the page, and it does more work than any rule or border.
   Where a rule and whitespace would both separate two regions, prefer the whitespace: the
   near-monochrome surface earns its calm by having fewer lines on it, not more.
4. **Vertical rhythm is consistent; horizontal is generous.** A screen uses at most three vertical
   step sizes (intra-group, inter-group, inter-section). Horizontal padding inside the content
   column never drops below step `6`, so text never runs to the edge of its card.

**One screen, one spacing owner.** A screen's page-level layout sets its section rhythm in one
place. A nested component never reaches out to adjust the space around itself.

### Viewport

**Desktop-only, but fluid within it.** Target **1440px**, minimum **1280px**. No tablet or mobile
layouts are designed: no stacked columns, no collapsed nav, no card-per-row fallback for tables.

The users are an org admin and a viewer at a desk; nobody triages a network scan on a phone. A
mobile layout is a problem when it's a problem (§12) — until real usage demands it, it is scope
paid for out of the quality of the desktop screens (§3).

**"Not designed for" is not "breaks".** Every layout is fluid, so the app degrades gracefully at
any width instead of shattering:

- **Content column:** prose-led screens (Home, all auth screens) center on a **720px max-width**
  column; table-led screens (Scans, Hosts, Agents, Users) on **1120px max-width**. These are
  *maximums*, not fixed widths — below them the column shrinks with the viewport.
- **No fixed pixel widths on layout containers.** Widths are `max-w-*` + fluid, or grid/flex
  fractions. A container never has a width it can't give back.
- **The page body never scrolls horizontally.** Wide content — tables above all — scrolls inside
  its own `overflow-x: auto` container, so the chrome and the verdict stay put.

### Building rules

How the above is enforced in code. These are binding on implementation, not suggestions.

1. **No magic numbers.** Spacing, type sizes, colors, radii and border widths come from the token
   set (Tailwind theme + CSS variables), defined once. A raw `padding: 13px` or `#6B21A8` in a
   component is a bug, not a shortcut — if a value is worth using it is worth being a token.
2. **Components size to their container, not to the viewport.** No component hardcodes a width
   because of what it happens to sit next to today.
3. **Relative units and intrinsic layout.** Flex and grid over absolute positioning; `min-w-0` on
   flex children so long values (UUIDs, hostnames) shrink instead of blowing out the row.
4. **Long values never break the layout.** Truncate with ellipsis, wrap, or scroll the container —
   a 64-character hostname must not widen the page (see Consistency rule 6, IDs truncate).
5. **Text sizes are tokens too.** The 16px floor on IM Fell (§Typography) is enforced by the scale,
   not by remembering it.

### Shared components

Only components that **two or more screens actually use**. Everything else is written inline in the
screen that needs it.

| Component | Used by |
| --- | --- |
| `TopBar` | every inside-shell screen |
| `PageHeader` | Scans, Hosts, Agents, Users — **not Home** (the verdict is the header) |
| `DataTable` | Scan list, Host inventory, findings on Scan detail, Users & invites |
| `SeverityBadge` | Home (critical item), Scan detail, Host detail |
| `StatusPill` | Agents (`queued → delivered → running → uploading → done`, online/offline), Scan list/detail (scan status) |
| `Timestamp` | everywhere a time is rendered — owns the relative/absolute rule below |
| `EmptyState` | every table-led screen + blank Home |
| `LoadingSkeleton` | every table-led screen |
| `Toast` | Scan now errors (503 `device_offline`, 409 `device_busy`), admin mutations |
| `Ornament` | Home, auth screens — the engraving detail |

**Cut from the candidate list:** `Sidebar` (top bar chosen above) · `MetricCard` (the MVP has no
metric cards, by decision) · `Breadcrumbs` (nothing is deeper than list → detail; parked in
[`IDEAS.md`](IDEAS.md)).

### Consistency rules

Cross-screen rules. A screen spec may cite these instead of restating them.

1. **Three states, no exceptions.** Every screen and every table ships a designed regular, blank
   and error state. A table never renders bare with no rows (§7).
2. **Errors have a next step.** Page-level failure = plain copy + `[Retry]`. Action failure =
   toast naming the thing that failed. Never a spinner that never resolves, never a skeleton
   standing in for a verdict (§7 get defensive).
3. **Absent, not disabled.** Actions a role cannot perform are omitted from the DOM, not greyed
   out. The viewer never learns what they're missing (§9).
4. **Whole rows are links.** In every table the entire row navigates; no trailing "View" button
   column.
5. **If it isn't a title, it's IBM Plex Mono.** There is no third face and no per-screen
   exception. IM Fell never appears below 16px (§Typography).
6. **IDs truncate, hover reveals.** UUIDs render as the first 8 characters; the full value is in
   the `title`. Never wrap a UUID.
7. **Timestamps:** relative inside 7 days (`yesterday 21:40`, `2 min ago`), absolute beyond it;
   the exact value always available on hover. One `Timestamp` component owns this.
8. **Buttons say what they do.** `Scan now`, `Invite user`, `Set password` — never `Submit`,
   `Execute`, `OK` (§6).
9. **Real content only.** Specs and mocks use real hostnames, real CVE ids, real IPs. No lorem
   ipsum, no `foo` (§6 use real words).

## Screen index

Status: `☐` not specced · `◐` draft · `✅` locked. Routes and roles per
[`FLOWS.md`](FLOWS.md) places inventory.

| Screen | Route | Shell | Roles | Flow | Status |
| --- | --- | --- | --- | --- | --- |
| Login | `/login` | outside | public | B1 | ◐ (C16) |
| Accept invite | `/invite?token=…` | outside | public | B2 | ◐ (C14 resolved; endpoint unconsumed — DMI-87) |
| Forgot password | `/forgot-password` | outside | public | B1 | ◐ |
| Reset password | `/reset-password?token=…` | outside | public | B1 | ✅ (C15 resolved) |
| Home | `/` | inside | admin, viewer | B2, B3 | ◐ |
| Scan list | `/scans` | inside | admin, viewer | B3 | ◐ |
| Scan detail | `/scans/:scanId` | inside | admin, viewer | B3, B4 | ◐ (C10) |
| Host inventory | `/hosts` | inside | admin, viewer | B3 | ◐ |
| Host detail | `/hosts/:hostId` | inside | admin, viewer | B3 | ◐ (C11 resolved — `?host_id=`) |
| Agents | `/agents` | inside | admin, viewer (ro) | B4 | ◐ ⚠️ blocked (C1, C2 — C12 resolved) |
| Users & invites | `/users` | inside | admin | B2 | ◐ **ships as invite-only** (C4, C18) |
| Settings | `/settings` | inside | admin, viewer | B5 | ◐ (password works; profile blocked — C3) |

---

## Per-screen template

Copy this block once per screen, in the order the screens get built (admin-first). Fill it top
to bottom; do not start the ASCII layout until everything above it is written.

```markdown
### <SCREEN NAME>

**Route:** `<path>` · **Shell:** <inside | outside> · **Roles:** <admin | viewer | public> ·
**Flow:** <B# in FLOWS.md>

**Epicenter** — the one thing this screen cannot live without; design it first, chrome last:
<one sentence>

**Data** — endpoints and fields consumed (contract names, not invented ones):
- `GET/POST <endpoint>` — <what it feeds>

**Three states** — each deliberately designed, none inherited by accident:
- **Regular:** <what the screen shows flush with data>
- **Blank:** <first-run state — what it teaches, and the CTA it offers>
- **Error:** <what failure looks like, and what the user can do next>

**Copy** — real words written here, never lorem ipsum; buttons say what they do:
| Element | Copy |
| --- | --- |
| <button / toast / empty state / error> | "<exact text>" |

**Layout** — ASCII wireframe, written LAST:
​```text
+----------------------------------------------------------+
| <sketch>                                                 |
+----------------------------------------------------------+
​```

**Open questions:** <list, or "none">
```

---

## Screens

### The auth shell

The five outside-shell screens share one frame, specced once here rather than four times below.
No top bar (there is no session yet, and nowhere to navigate), no nav, no `[Log out]`.

- **Frame:** wordmark, `Ornament`, then a single centered card in the **720px prose column**
  (§Viewport). The card is the page; there is no other content.
- **Never reveal whether an account exists.** Login's `401` and Forgot's `204` are both deliberately
  uninformative. This is why Forgot always shows the same confirmation, and why login's error names
  neither field ([`AUTH.md`](../roadmap/AUTH.md) → Forgot password).
- **State the password policy before it is violated, never after.** Every screen with a new-password
  field carries the same hint as SETTINGS: *"At least 12 characters. Avoid names, dates, and
  passwords you've used elsewhere."* Discovering the rules by failing is a §7 failure.
- **Confirm-password fields are client-side only.** No contract request body has one
  (`AcceptInviteRequest`, `ResetPasswordRequest` take a single `password` / `new_password`,
  `minLength: 12`). The mismatch error never reaches the server.
- **Submitting is a state.** The button becomes its own progress copy (`"Logging in…"`) and is
  disabled while in flight. Never a bare spinner (§7).
- **Password managers are a feature, not an edge case.** Real `<form>`, real `autocomplete`
  (`email`, `current-password`, `new-password`), submit on Enter, first field autofocused. An org
  admin forced to type a 12-character password without a manager will pick a bad one.

---

### LOGIN

**Route:** `/login` · **Shell:** outside · **Roles:** public · **Flow:** B1

**Epicenter** — the two fields and the button. Nothing else earns space on this page.

**Data:**
- `POST /api/v1/auth/login` → `LoginResponse` (`access_token`, `token_type`, `expires_in`); the
  refresh token arrives as an httpOnly `Set-Cookie` and the SPA never sees it
  ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client).
- `401` → wrong credentials. There is no other failure branch: login is `200`/`401` only
  ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced password rotation is dropped, so there
  is no expired-password 403 to route anywhere).

**Where the role comes from — 🔓 C16.** `LoginResponse` carries **only a token**. Every "absent, not
disabled" decision in this product (rule 3) — the `Users` nav item, `[Scan now]`, the invite form —
depends on knowing whether this user is an `admin` or a `viewer`.
[`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis says the role arrives **in the JWT claims**,
but the contract documents no claims at all. The frontend would be decoding an undocumented payload
to decide what to render.

**Three states:**
- **Regular:** the form.
- **Blank:** **not applicable.** A login form is never empty — it is its own content. Recorded so
  nobody invents an empty state to satisfy rule 1.
- **Error:** inline, above the button. Wrong credentials name neither field. A `5xx`/network failure
  is a *different* error and says so — telling someone their password is wrong when the server is
  down is the §7 sin.

**One arrival note, above the form.** A user who has just deleted their own account in SETTINGS
lands here ([`ADR-017`](../adr/ADR-017-account-removal.md)) — their session no longer exists, so
there is nowhere else to send them. It is a *confirmation*, not an error, and is styled as one:
they did something irreversible and deserve to be told it worked. It does not persist across a
reload; a stale "your account was deleted" on a shared machine would be both confusing and a small
disclosure.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Sign in to Dmitri" |
| Fields | "Email" / "Password" |
| Button | "Log in" · in flight: "Logging in…" |
| Link | "Forgot password?" |
| Error — 401 | "That email and password don't match." |
| Error — server/network | "Couldn't reach Dmitri. Try again in a moment." |
| Arrival — account deleted | "Your account has been deleted." |

**Layout:**
```text
+------------------------------------------------------------------------------+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                              D M I T R I                                     |
|                                                                              |
|              +------------------------------------------+                    |
|              |  SIGN IN TO DMITRI                       |                    |
|              |                                          |                    |
|              |  Email                                   |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |  Password                                |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |  That email and password don't match.    |  ← inline, on error|
|              |                                          |                    |
|              |            [ ▓   Log in   ]              |                    |
|              |                                          |                    |
|              |            Forgot password?              |                    |
|              +------------------------------------------+                    |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. **C16** — the role is not in the contract. Blocks role gating everywhere, not just here.

---

### ACCEPT INVITE

**Route:** `/invite?token=…` · **Shell:** outside · **Roles:** public · **Flow:** B2

**Epicenter** — choosing a password. This is the first thing anyone ever does in Dmitri, and the
account exists the moment it succeeds.

**Data:**
- `POST /api/v1/invites/accept` — body `{ token, password }` (`minLength: 12`). The invite
  token moved from the URL path into the body in DMI-77 (it was being written to access logs), so
  the route reads it from the request body and the emailed link is `/invite?token=…`. **The `email`
  field was removed** (spec 027 / DR-0002, 2026-08-06): once the lookup below supplies the address,
  retyping it proves nothing, and the account was always created from the invite record anyway.
  Sending one now returns **422** rather than being ignored.
- `POST /api/v1/invites/lookup` — body `{ token }`, public, returns `{ email, role, org_name }`.
  Reading does **not** consume the invite, so the page may call it on mount and the link still
  works. A dead token answers **410** here too, with the same body the accept route gives.
- **`201` returns a full `LoginResponse`.** ✅ **C7 RESOLVED — accepting an invite issues a
  session.** Store the access token, and the invitee lands on **HOME**, in its first-run blank state
  (B2). They are never sent back to LOGIN to type the password they just chose.
- **`410`** — invite expired or already used (**not** `400`; single-use, 24–72h TTL per
  [`AUTH.md`](../roadmap/AUTH.md)). **`400`** — password rejected by policy.

**The screen can now greet you — ✅ C14 resolved.** The lookup landed 2026-08-06 (DMI-86), so both
of the consequences this section used to list are gone: the page can say *"You've been invited to
Acme with the viewer role"* — the one sentence that tells a stranger the link is legitimate — and the
invitee no longer types their own email from memory, so a typo can no longer fail identically to a
dead link. **The endpoint is unconsumed**: building the screen against it is DMI-87, which is why
this screen is still `◐`.

**Three states:**
- **Regular:** the greeting (*"You've been invited to Acme with the viewer role"*, from the lookup) plus the
  form. Password + confirm — **no email field**.
- **Blank:** not applicable (a form is its own content).
- **Error — dead link (410):** the form is **removed**, not left there to be re-submitted. The link
  is spent; nothing the user types will fix it. The only honest next step is *ask your admin*, and
  there is no self-serve escape (§7 — get defensive, and don't offer an action that cannot work).
- **Error — policy (400):** inline under the password field; the form stays.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Create your account" |
| Body | "You've been invited to {org_name} with the {role} role. Pick a password and you're in." — org and role from the lookup. The article was dropped 2026-08-06 (DMI-87): `role` is the enum `admin \| viewer`, so "as a {role}" renders "as a admin" for every admin invite, and this wording needs no per-role branch |
| Fields | "Password" / "Confirm password" |
| Policy hint | "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere." |
| Button | "Create account" · in flight: "Creating your account…" |
| Error — 410 (heading) | "This invite has expired." |
| Error — 410 (body) | "Invite links can only be used once, and they don't last long. Ask your admin to send you a new one." |
| Error — 400 policy | "That password isn't strong enough. Try a longer one that isn't based on a name or a date." |
| Error — mismatch (client) | "Those two passwords don't match." |
| Error — already registered (400) | "That address already has an account. Sign in instead." |

**Layout:**
```text
+------------------------------------------------------------------------------+
|                        ~ small engraving ornament ~                          |
|                              D M I T R I                                     |
|                                                                              |
|              +------------------------------------------+                    |
|              |  CREATE YOUR ACCOUNT                     |                    |
|              |  You've been invited to Acme with the    |                    |
|              |  viewer role. Pick a password and        |                    |
|              |  you're in.                              |                    |
|              |                                 (muted)  |                    |
|              |                                          |                    |
|              |  Password                                |                    |
|              |  [__________________________________]    |                    |
|              |  At least 12 characters. Avoid names,    |                    |
|              |  dates, and passwords you've used        |                    |
|              |  elsewhere.                     (muted)  |                    |
|              |                                          |                    |
|              |  Confirm password                        |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |        [ ▓  Create account  ]            |                    |
|              +------------------------------------------+                    |
+------------------------------------------------------------------------------+
```

Dead link (410) — the form is gone:
```text
              +------------------------------------------+
              |  THIS INVITE HAS EXPIRED.                |
              |                                          |
              |  Invite links can only be used once, and |
              |  they don't last long. Ask your admin to |
              |  send you a new one.            (muted)  |
              +------------------------------------------+
```

**Open questions:**
1. ~~**C14** — no invite-lookup endpoint.~~ **✅ RESOLVED 2026-08-06 (DMI-86, spec 027) —
   `POST /api/v1/invites/lookup`**, token in the body (not a `GET` — a query string keeps the token
   out of the path but not out of the access log), returning `{ email, role, org_name }`, with
   `410 invalid_invite_token` for expired/used/unknown alike. The screen can now name the org, state
   the role, and skip the email field entirely; a dead link is reached **on mount**, before the form
   is ever submitted, so the 410 state no longer has to double as a typo message. **This screen
   stays `◐` for a different reason now:** the endpoint exists and nothing consumes it — building
   the page against it is DMI-87.

---

### FORGOT PASSWORD

**Route:** `/forgot-password` · **Shell:** outside · **Roles:** public · **Flow:** B1

**Epicenter** — one field and one button. The screen's real job is what it says *afterwards*.

**Data:**
- `POST /api/v1/auth/forgot-password` — body `{ email }`. **Always `204`.** There is no error
  branch and no 404: the contract cannot tell you whether the account exists, on purpose.

**The confirmation must be honest about being uninformative.** Since the response is identical for a
real and a fake address, the copy must not promise an email that may never arrive — *"Check your
inbox"* is a lie to anyone who mistyped. Say what was actually done and what it depends on: **if**
that address has an account. Wording around this is how products leak their user lists (§6 — the
copy *is* the security boundary here).

**Three states:**
- **Regular:** the form.
- **Blank:** not applicable.
- **Confirmed (the real second state):** the form is **replaced** by the confirmation. Leaving the
  field there invites the user to fire off three more emails when the first doesn't arrive in
  fifteen seconds.
- **Error:** only network/server failure can occur — a `204` is not a success signal about the
  address, merely that the request landed.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Reset your password" |
| Body | "Enter your email and we'll send you a link to set a new password." |
| Field | "Email" |
| Button | "Send reset link" · in flight: "Sending…" |
| Confirmation — heading | "Check your email." |
| Confirmation — body | "If **name@example.com** has a Dmitri account, a reset link is on its way. The link works once and expires shortly." |
| Confirmation — link | "Back to sign in" |
| Error — server/network | "Couldn't reach Dmitri. Try again in a moment." |

**Layout:**
```text
              +------------------------------------------+
              |  RESET YOUR PASSWORD                     |
              |  Enter your email and we'll send you a    |
              |  link to set a new password.    (muted)  |
              |                                          |
              |  Email                                   |
              |  [__________________________________]    |
              |                                          |
              |        [ ▓  Send reset link  ]           |
              |                                          |
              |            Back to sign in               |
              +------------------------------------------+
```

Confirmed — the form is replaced:
```text
              +------------------------------------------+
              |  CHECK YOUR EMAIL.                       |
              |                                          |
              |  If name@example.com has a Dmitri        |
              |  account, a reset link is on its way.    |
              |  The link works once and expires         |
              |  shortly.                       (muted)  |
              |                                          |
              |            Back to sign in               |
              +------------------------------------------+
```

**Open questions:** none.

---

### RESET PASSWORD

**Route:** `/reset-password?token=…` · **Shell:** outside · **Roles:** public · **Flow:** B1

**Epicenter** — the new-password field.

**Data:**
- `POST /api/v1/auth/reset-password` — body `{ token, new_password }` (`minLength: 12`). **The token
  travels in the body, not the path** — the screen reads it from the query string and posts it.
- `204` → **LOGIN**, with success copy. Reset does **not** issue a session (unlike accept-invite);
  the user logs in with the password they just set. That is the correct edge — it proves the
  password works and re-arms the recall the 7-day refresh window exists to encourage
  ([`AUTH.md`](../roadmap/AUTH.md) → Sessions).
- `410 invalid_reset_token` → the link is dead (never issued, already used, or expired). Remove the
  form; tell the user to request a new one.
- `400 password_policy_violation` → stay on the form; inline error under the new-password field.

**✅ C15 RESOLVED 2026-08-03 (DMI-77).** The two failures no longer share a status *or* a code. A
dead link is `410` with `error.code: invalid_reset_token`; a rejected password is `400` with
`password_policy_violation`. Both codes are pinned by an `enum` in the contract
(`ResetTokenGone` / `ResetPasswordRejected`) and gated by `test_contract_fidelity.py`, so the screen
can switch on `error.code` safely. The token is checked **before** the policy, so a dead link plus a
weak password yields the `410` — the link is the thing to fix first. `410` matches accept-invite, so
both token screens share one pattern.

**Missing token:** `/reset-password` with no `?token=` never renders the form — there is nothing to
submit. It shows the dead-link state directly.

**Three states:**
- **Regular:** the form.
- **Blank:** not applicable.
- **Error — dead link:** form removed, `[Request a new link]` → FORGOT PASSWORD. Same reasoning as
  the invite: nothing typed here can revive a spent token.
- **Error — policy:** inline; the form stays.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Set a new password" |
| Fields | "New password" / "Confirm new password" |
| Policy hint | "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere." |
| Button | "Set password" · in flight: "Setting your password…" |
| Success (on LOGIN) | "Password set. Sign in with your new password." |
| Error — dead link (heading) | "This link has expired." |
| Error — dead link (body) | "Reset links work once and don't last long." · [Request a new link] |
| Error — policy | "That password isn't strong enough. Try a longer one that isn't based on a name or a date." |
| Error — mismatch (client) | "Those two passwords don't match." |

**Layout:**
```text
              +------------------------------------------+
              |  SET A NEW PASSWORD                      |
              |                                          |
              |  New password                            |
              |  [__________________________________]    |
              |  At least 12 characters. Avoid names,    |
              |  dates, and passwords you've used        |
              |  elsewhere.                     (muted)  |
              |                                          |
              |  Confirm new password                    |
              |  [__________________________________]    |
              |                                          |
              |         [ ▓   Set password   ]           |
              +------------------------------------------+
```

**Open questions:**
1. **C15** — the `400` cannot be disambiguated. The screen's most common failure (a stale link,
   because reset emails sit in inboxes) is the one it cannot word correctly.

---

### HOME

**Route:** `/` · **Shell:** inside · **Roles:** admin, viewer ·
**Flow:** B2 (blank slate), B3

Home is not a metrics dashboard. Its job is a review: the product interprets and the operator
reads a judgment, not numbers (REFERENCE.md §6, §8, §10). On a normal day the page is mostly
empty on purpose.

**Epicenter** — the one thing this screen cannot live without, designed first, chrome last:
the verdict line — one plain sentence stating whether anything needs the operator's
attention since they last looked.

**Data** — endpoints and fields consumed (contract names):
- `GET /api/v1/scans?per_page=1` (default sort `timestamp` desc) — latest scan feeds the
  verdict, the scan-failed item (`status: failed`), and the context footer (`timestamp`,
  `host_count`, `finding_count`, `highest_severity`, `scan_mode`)
- `GET /api/v1/findings?scan_id={latest}&severity=critical` (and `severity=high`) — finding
  review items (`title`, `cve_id`, `ip`, `severity`)
- `GET /api/v1/agents/{agent_id}` — `online`, `last_seen_at`, `display_name` feed the
  coverage-stale item and the footer Pi status
- New-device item: `HostSummary` carries `first_seen_at` (**C6** resolved), so the item is no
  longer contract-blocked; it is still not built, and shipping it in v1 is a product call

**Three states** — each deliberately designed, none inherited by accident:
- **Regular, all clear (the common case):** verdict + context sentence, centered, generous
  whitespace; small engraving ornament; muted footer with Pi status. No review items, no
  empty-table scaffolding — the near-empty page *is* the design (positive framing).
- **Regular, items pending:** verdict states the count; below it, one square-edged card per
  review item in plain language, each linking where the operator deals with it (finding →
  scan detail, failure → scan detail, stale coverage → Agents). Deep purple marks the item
  label; red appears only inside a critical-severity badge. Medium/low findings and routine
  successful scans never appear here.
- **Blank:** first-run onboarding per B2 — explains what a scan is, admin gets
  [Run first scan] → AGENTS; viewer gets the explainer with "Ask your admin to run the
  first scan." instead of a CTA (affordance omitted, not disabled).
- **Error:** page-level failure copy + [Retry]; no partial skeletons pretending to be a verdict.

**Copy** — real words, buttons say what they do:
| Element | Copy |
| --- | --- |
| Verdict — all clear | "Nothing needs your attention." |
| Context — all clear | "Last scan finished yesterday at 21:40 — 12 hosts, no critical findings." |
| Verdict — items pending | "2 things need your review." |
| Review item — finding | "Critical: CVE-2024-4577 on synology-nas (192.168.1.42). Found in last night's scan." · [View finding] |
| Review item — scan failed | "Last night's scan didn't finish." · [See why] |
| Review item — coverage stale | "The Pi hasn't been seen since Tuesday." · [Check the Pi] |
| Blank — heading | "No scans yet." |
| Blank — body | "Dmitri scans your network for devices and known vulnerabilities, then reports anything worth your attention here." |
| Blank — CTA (admin only) | "Run first scan" |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the review." · [Retry] |
| Footer | "Last scan: yesterday 21:40 · 12 hosts · quick mode" / "Pi status: online · last seen 2 min ago" |

**Layout** — fat-marker fidelity; paddings and exact columns not fixed here:

Regular — items pending:
```text
+------------------------------------------------------------------------------+
| DMITRI          Home    Scans  Hosts  Agents  Users              [Log out]   |
+==============================================================================+
|                                                                              |
|   ~ small engraving ornament ~                                               |
|                                                                              |
|   2 THINGS NEED YOUR REVIEW.                                                 |
|   ------------------------------------------------------------------        |
|                                                                              |
|   +----------------------------------------------------------------+        |
|   | ▓ CRITICAL FINDING                                              |        |
|   |   CVE-2024-4577 on synology-nas (192.168.1.42)                  |        |
|   |   Found in last night's scan.                                   |        |
|   |                                              [View finding] →   |        |
|   +----------------------------------------------------------------+        |
|                                                                              |
|   +----------------------------------------------------------------+        |
|   | ▓ THE PI HASN'T BEEN SEEN SINCE TUESDAY                         |        |
|   |                                               [Check the Pi] →  |        |
|   +----------------------------------------------------------------+        |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Last scan: yesterday 21:40 · 12 hosts · quick mode         (muted)         |
|   Pi status: online · last seen 2 min ago                                    |
+------------------------------------------------------------------------------+
```

Regular — all clear:
```text
+------------------------------------------------------------------------------+
| DMITRI          Home    Scans  Hosts  Agents  Users              [Log out]   |
+==============================================================================+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                                                                              |
|                     NOTHING NEEDS YOUR ATTENTION.                            |
|                                                                              |
|          Last scan finished yesterday at 21:40 — 12 hosts,                   |
|          no critical findings.                                               |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Pi status: online · last seen 2 min ago                                    |
+------------------------------------------------------------------------------+
```

Blank — first run (admin):
```text
+------------------------------------------------------------------------------+
| DMITRI          Home    Scans  Hosts  Agents  Users              [Log out]   |
+==============================================================================+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                                                                              |
|                              NO SCANS YET.                                   |
|                                                                              |
|          Dmitri scans your network for devices and known                     |
|          vulnerabilities, then reports anything worth your                   |
|          attention here.                                                     |
|                                                                              |
|                        +---------------------+                              |
|                        | ▓  Run first scan   |   → Agents                   |
|                        +---------------------+                              |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. ~~New-device review item — blocked on contract (`first_seen_at` on `HostSummary` — **C6**).~~
   **✅ RESOLVED — `first_seen_at` is a required property on `HostSummary`.** The item is
   unblocked but still unbuilt; whether it ships in v1 is a product call, not a contract gap.
2. Coverage-stale thresholds: Pi `online: false` is immediate, but "no completed scan in
   N days" needs an N.
3. "Not seen before" phrasing needs a backend finding-delta (IDEAS.md backend note); v1
   copy claims only "found in last night's scan".

---

### SCAN LIST

**Route:** `/scans` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — the run log: every scan, newest first, each answering *did it work, and did it find
anything*. This is the one screen in the product that is honestly a table, and it should look like
one.

**Data:**
- `GET /api/v1/scans?page&per_page=20&sort_by=timestamp&sort_order=desc` → `ScanListResponse`
  (`data: ScanSummary[]`, `total`, `page`). Server-driven sorting and pagination already exist in
  the contract; **no client-side sorting.**
- `ScanSummary`: `scan_id`, `timestamp`, `subnet`, `scan_mode`, `status`, `host_count`,
  `finding_count`, `highest_severity` (nullable).

`ScanStatus` is `pending | accepted | processing | completed | failed` — **not** the command
lifecycle. A scan triggered from Agents appears here as `pending` **immediately** (the stub row is
created at enqueue, [`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-)), so this list
is live during a scan and must not look broken while a row is unfinished.

**Filters are cut from v1** ([`IDEAS.md`](IDEAS.md) → Scans). The contract supports a `status`
filter; the screen does not use it. One Pi scanning one subnet does not produce a list that needs
filtering yet (§12).

**Three states:**
- **Regular:** one row per scan. Whole row navigates (rule 4). An unfinished scan shows a
  `StatusPill` instead of counts — it has no counts yet.
- **Blank:** no scans ever. Same content as blank Home, because it is the same fact — admin gets
  [Run first scan] → AGENTS, viewer gets the line instead of the affordance.
- **Error:** page-level copy + [Retry]. `LoadingSkeleton` for the table body on first load only —
  never on background refetch, which would make a live list flicker.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Scans" |
| Columns | "When · Mode · Status · Hosts · Findings · Highest severity" |
| Status — completed | (no pill; show the counts) |
| Status — pending/accepted/processing | "Running…" |
| Status — failed | "Failed" |
| Findings cell — zero | "None" |
| Highest severity — null on a completed scan | "—" |
| Pagination | "Showing 1–20 of 47" · [Previous] [Next] |
| Blank — heading | "No scans yet." |
| Blank — body | "Dmitri scans your network for devices and known vulnerabilities. Every scan you run shows up here." |
| Blank — CTA (admin only) | "Run first scan" |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the scans." · [Retry] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SCANS                                                                      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   WHEN            MODE    STATUS     HOSTS  FINDINGS  HIGHEST                |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   2 min ago       quick   Running…      -         -   -                      |
|   yesterday 21:40 quick   —            12         3   ▓ CRITICAL             |
|   Jul 11  21:40   quick   —            12         0   —                      |
|   Jul 10  21:40   quick   Failed        -         -   -                      |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Showing 1–20 of 47                          [Previous]  [Next]             |
+------------------------------------------------------------------------------+
```

**Open questions:** none.

---

### SCAN DETAIL

**Route:** `/scans/:scanId` · optional `?finding=:findingId` (deep link from Home, B3) ·
**Shell:** inside · **Roles:** admin, viewer · **Flow:** B3, B4

**Epicenter** — the findings list ([`REFERENCE.md`](REFERENCE.md) §2). Hosts are context; the
findings are why anyone opened this page. Design the findings table first, the host table second,
the header last.

**Data:**
- `GET /api/v1/scans/{scan_id}` → `ScanDetailResponse` — **one request, everything embedded**:
  `findings: FindingRead[]`, `hosts: ScanHostView[]`, `timestamp`, `subnet`, `scan_mode`,
  `status`, `host_count`, `finding_count`, `command_id` (nullable).
- **No `GET /findings` call here, and no `GET /findings/{id}`.** `FindingRecord` arrives complete —
  `severity`, `title`, `description`, `recommendation`, `evidence`, `references`, `cve_id`,
  `cvss_score`, `device_ip`, `port`, `protocol`, `service`. Opening a finding is **local state**.
- **Failure reason:** `ScanDetailResponse` has **no error field**. When `status: failed`, fetch
  `GET /api/v1/commands/{command_id}` for `error_code` — **C10**.

**Three states:**
- **Regular:** header (when · mode · subnet · counts), then findings sorted critical→low, then the
  host table. Clicking a finding row expands its panel **in place**; clicking a host row expands its
  ports **in place**. Neither navigates.
- **Regular, no findings (the good day):** the findings section says so in words and the host table
  carries the page. Positive framing, not an empty table (§7).
- **Regular, unfinished:** `status` is `pending`/`accepted`/`processing` — the scan is running right
  now. The page says so and polls; it does not render an empty findings table as though the answer
  were "nothing".
- **Regular, failed:** the failure **is** the content. Show the reason from `error_code` and what to
  do; suppress the empty findings and host tables entirely.
- **Error:** page-level copy + [Retry]. 404 gets its own line.

**Deep link:** `?finding=:findingId` — match the id in the already-loaded `findings`, scroll to that
row, open its panel. Absent or unmatched → render normally. No extra fetch (B3).

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Scan — yesterday 21:40" |
| Header line | "quick mode · 192.168.0.0/24 · 12 hosts · 3 findings" |
| Findings section title | "Findings" |
| Findings columns | "Severity · Finding · Host · Port · CVE" |
| No findings | "No findings. Every host in this scan came back clean." |
| Finding panel — labels | "What it is" / "What to do" / "Evidence" / "References" |
| Finding panel — CVSS | "CVSS 9.8" |
| Hosts section title | "Hosts" |
| Hosts columns | "Host · IP · MAC · Vendor · Open ports" |
| Unfinished | "This scan is still running." · "Findings appear here when it finishes." |
| Failed | "This scan didn't finish." · "The Pi reported: `<error_code>`." · [Try another scan] → AGENTS (admin only) |
| Failed, no `command_id` | "This scan didn't finish. No reason was recorded." |
| Error | "Couldn't load this scan." · [Retry] |
| 404 | "That scan doesn't exist." · [Back to scans] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SCAN — YESTERDAY 21:40                                                     |
|   quick mode · 192.168.0.0/24 · 12 hosts · 3 findings           (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   FINDINGS                                                                   |
|   SEVERITY    FINDING                      HOST          PORT   CVE          |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   ▓ CRITICAL  PHP CGI argument injection   synology-nas  443    CVE-2024-4577|
|   +----------------------------------------------------------------+        |
|   |  WHAT IT IS    <description>                                    |  ← open|
|   |  WHAT TO DO    <recommendation>                                 |        |
|   |  EVIDENCE      <evidence>                (mono)                 |        |
|   |  REFERENCES    <links>                        CVSS 9.8          |        |
|   +----------------------------------------------------------------+        |
|   ▓ HIGH      Outdated OpenSSH              pi-lab        22     CVE-2023-…  |
|   ▓ LOW       Telnet port open              printer-hp    23     —           |
|                                                                              |
|   HOSTS                                                                      |
|   HOST          IP             MAC                VENDOR      OPEN PORTS     |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   synology-nas  192.168.0.42   00:11:32:AA:BB:CC  Synology    4              |
|   pi-lab        192.168.0.17   DC:A6:32:11:22:33  Raspberry   2              |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. ~~**C9** — `DevicePayload` (the `devices` array) carries **no `host_id`**, so a host row here
   cannot link to HOST DETAIL.~~ **✅ RESOLVED 2026-08-02 (DMI-85) — the array is `hosts:
   ScanHostView[]` and `host_id` is required on it.** A host row can link to `/hosts/:hostId`;
   the affordance is available whenever this screen is built.
2. **C10** — `error_code` is a *code*, not a sentence. It needs a copy mapping
   (code → plain-language reason) before the failed state has real words.

---

### HOST INVENTORY

**Route:** `/hosts` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — the machines on the network: what is out there, and does any of it need attention.
This answers "what do I own", which is the second question every operator asks after "is anything
wrong".

**Data:**
- `GET /api/v1/hosts?page&per_page=20&sort_by=last_seen_at&sort_order=desc` → `HostListResponse`
  (`data: HostSummary[]`, `total`, `page`).
- `HostSummary`: `host_id`, `ip`, `mac` (nullable), `hostname`, `vendor`, `first_seen_at`,
  `last_seen_at`, `open_ports_count`, `highest_severity` (nullable).

**Search is cut from v1** ([`IDEAS.md`](IDEAS.md) → Hosts). The contract does define a free-text `q`
parameter on this endpoint, but v1 does not send it and the backend does not implement it — one
subnet does not produce a list you cannot read (§12). Sorting is server-driven; the contract allows
`last_seen_at | hostname | vendor | ip`.

**Hosts are cumulative, not per-scan** — this is the inventory of everything ever discovered, which
is why `last_seen_at` is the default sort and why a machine that has gone away still appears.

**`mac` can be null** — a host discovered across a router has no ARP entry, so there is no MAC to
show. The column renders "—" rather than being hidden; the machine is real, one identifier is not
observable from here.

**Three states:**
- **Regular:** one row per host, whole row navigates to `/hosts/:hostId`.
- **Blank:** no scan has ever run, so nothing has been discovered. Same fact as blank Home; same
  treatment — admin CTA to AGENTS, viewer gets the line.
- **Error:** page-level copy + [Retry].

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Hosts" |
| Subtitle | "Every device Dmitri has found on your network." |
| Columns | "Host · IP · MAC · Vendor · Open ports · Highest severity · Last seen" |
| Hostname missing | "(unnamed)" |
| MAC — null | "—" |
| Highest severity — null | "—" |
| Blank — heading | "No hosts yet." |
| Blank — body | "Once a scan runs, every device Dmitri finds on your network shows up here." |
| Blank — CTA (admin only) | "Run first scan" |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the hosts." · [Retry] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   HOSTS                                                                      |
|   Every device Dmitri has found on your network.                (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   HOST          IP            MAC               VENDOR     PORTS  SEV  SEEN  |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   synology-nas  192.168.0.42  00:11:32:AA:BB:CC Synology       4  ▓CRIT 2m   |
|   pi-lab        192.168.0.17  DC:A6:32:11:22:33 Raspberry      2  ▓HIGH 2m   |
|   printer-hp    192.168.0.31  3C:D9:2B:44:55:66 HP             3  ▓LOW  2m   |
|   (unnamed)     192.168.0.88  A4:83:E7:77:88:99 Apple          1  —     Jul 9|
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Showing 1–20 of 12                          [Previous]  [Next]             |
+------------------------------------------------------------------------------+
```

**Open questions:** none. (A "new device" badge needs no contract work — **C6** is resolved and
`first_seen_at` is a required property on `HostSummary` as well as `HostDetailResponse`.)

---

### HOST DETAIL

**Route:** `/hosts/:hostId` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — what this machine exposes: its open ports. Identity is a header; history is a
footnote; the attack surface is the page.

**Data:**
- `GET /api/v1/hosts/{host_id}` → `HostDetailResponse`: `ip`, `mac` (nullable — see HOST
  INVENTORY), `hostname`, `vendor`, `first_seen_at`, `last_seen_at`, `open_ports_count`,
  `highest_severity`, `ports: Port[]`, `scan_history: HostScanHistoryEntry[]`.
- `Port`: `port`, `protocol`, `state`, `service`, `version` (nullable).
- `HostScanHistoryEntry`: `scan_id`, `timestamp`, `scan_mode`, `open_ports_count`,
  `highest_severity`.
- **Findings are a second call:** `HostDetailResponse` carries **no findings array**, but
  `highest_severity` is shown — so the page must explain that severity. Use
  `GET /api/v1/findings?host_id={host_id}` → `FindingRead[]`, rendered with the same row +
  in-place panel as SCAN DETAIL.

**Three states:**
- **Regular:** identity header, findings (if any), ports table, scan history. Scan-history rows
  navigate to `/scans/:scanId` (whole row, rule 4).
- **Blank:** not reachable — a host exists only because a scan found it. A host with **zero open
  ports** is the nearest thing, and it gets positive framing rather than an empty table.
- **Error:** page-level copy + [Retry]; 404 its own line.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "synology-nas" (or the IP when `hostname` is empty) |
| Header line | "192.168.0.42 · 00:11:32:AA:BB:CC · Synology" |
| Seen line | "First seen Jul 3 · last seen 2 min ago" |
| Findings section title | "Findings" |
| No findings | "No findings on this host." |
| Ports section title | "Open ports" |
| Ports columns | "Port · Protocol · Service · Version" |
| No open ports | "No open ports. This host isn't exposing anything." |
| Version missing | "—" |
| History section title | "Seen in these scans" |
| History columns | "When · Mode · Open ports · Highest severity" |
| Error | "Couldn't load this host." · [Retry] |
| 404 | "That host doesn't exist." · [Back to hosts] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SYNOLOGY-NAS                                                               |
|   192.168.0.42 · 00:11:32:AA:BB:CC · Synology                   (muted)      |
|   First seen Jul 3 · last seen 2 min ago                        (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   FINDINGS                                                                   |
|   ▓ CRITICAL  PHP CGI argument injection      443    CVE-2024-4577           |
|      (row expands in place — same panel as SCAN DETAIL)                      |
|                                                                              |
|   OPEN PORTS                                                                 |
|   PORT   PROTOCOL   SERVICE     VERSION                                      |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   22     tcp        ssh         OpenSSH 8.4p1                                |
|   443    tcp        https       nginx 1.18.0                                 |
|   5000   tcp        http        Synology DSM                                 |
|                                                                              |
|   SEEN IN THESE SCANS                                                        |
|   WHEN              MODE    OPEN PORTS   HIGHEST                             |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   yesterday 21:40   quick            4   ▓ CRITICAL                          |
|   Jul 11  21:40     quick            4   ▓ CRITICAL                          |
|   Jul 10  21:40     quick            3   —                                   |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. ~~Does `GET /findings?device_id=…` accept the **`host_id`** UUID?~~ **✅ RESOLVED (C11) — the
   filter is `?host_id=`.** `read_findings()` takes `host_id: UUID | None`, and `FindingRead`
   carries `host_id`. The read model is `hosts` end to end; only the Pi ingest payload keeps
   `devices[]` (ADR-011 §5). Host detail can show findings.

---

### AGENTS

**Route:** `/agents` · **Shell:** inside · **Roles:** admin, viewer (read-only) ·
**Flow:** B4, and the first-run step of B2

**Epicenter** — *can I scan right now?* The agent's live state and the trigger, together
([`REFERENCE.md`](REFERENCE.md) §2). Everything else on this page is caption.

**Data:**
- `GET /api/v1/agents` → the row. **🔓 C1 — does not exist.** One agent in the MVP; `agent_id` is
  the provisioning `X-Device-Id` and the frontend cannot derive it.
- `GET /api/v1/agents/{agent_id}` → `AgentDetail`: `display_name`, `online`, `last_seen_at`,
  `active_command_id`. **Read on mount** — this is what lets a running scan's pill survive
  navigation and reload (B4). **🔓 C2 —** must also carry `available_subnets` + `target_subnet`.
- `POST /api/v1/agents/{agent_id}/commands` → `CommandSummary`. Body is
  `{ scan_mode: "quick", subnet: <agent.target_subnet> }` — **both are supplied by the system, never
  typed by the operator** (B4).
- `GET /api/v1/commands/{command_id}` → `CommandDetail`: `status`, `error_code`, `scan_id`. Poll
  **every 5s** while the status is pending.

`CommandStatus` is `queued | delivered | running | uploading | done | failed | expired` — **seven**
states, and the pill must render all of them. `expired` is a *backend*-set state (ADR-011): the Pi
**never took the command** — delivery gave up, and the operator already saw the `503` toast. It is not
the same event as `failed` and does not get the same words. **The split is `delivered_at` (C12):** a Pi
that dies *mid-scan* took the job, so it reports **`failed`**, not `expired`.

**Three states** — this screen has more than three; each is designed, none inherited:
- **Blank — no Pi at all.** No agent exists. **The admin cannot fix this themselves**: Pi
  provisioning is the installer's job, never the org admin's ([`AUTH.md`](AUTH.md) — B2B model). So
  the blank state must not offer a CTA it cannot honor; it explains and points at the vendor. This
  is the one blank slate in the product with **no action**, on purpose.
- **Needs a network (admin).** `target_subnet` is null. The Pi is online but **cannot be scanned**
  until a human says which network is the target — it is dual-homed and sees two (B4). `[Scan now]`
  is not shown; the choice is. This is also B2's missing first-run step.
- **Ready (admin).** Online, network chosen → `[Scan now]`.
- **Scanning.** A `StatusPill` on the row walks the lifecycle. The whole row stays readable; the
  pill is the only thing that moves.
- **Done.** Pill becomes `[View scan]` → SCAN DETAIL. Caches for scans/agents/findings invalidate.
- **Failed.** The Pi took the command and it broke — a scan error, a failed upload, or the Pi going
  dark **mid-scan**. Error pill carrying `error_code` + `[Retry]`.
- **Expired.** The Pi **never took the command** — delivery gave up after 2 retries. Distinct from
  `failed` — the operator's next step is *check the box*, not *try again* — so it points at the Pi and
  offers `[Retry]` second.
- **Offline.** `online: false`. `[Scan now]` **stays visible and enabled** — see Open questions.
- **Viewer.** Sees the row, the status and the network. No `[Scan now]`, no network chooser —
  omitted, not disabled (rule 3).
- **Error.** Page-level copy + `[Retry]`.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Agents" |
| Subtitle | "The Dmitri box on your network." |
| Row — online | "Online · last seen 2 min ago" |
| Row — offline | "Offline · last seen Tuesday 14:10" |
| Row — network | "Scanning: Ethernet · 192.168.0.0/24" · [Change] |
| Trigger | "Scan now" |
| Needs-network heading | "Which network should Dmitri scan?" |
| Needs-network body | "This box is connected to more than one network. Pick the one you want scanned — usually the office network, not the internet connection." |
| Needs-network options | "Ethernet · 192.168.0.0/24" / "Wi-Fi · 10.12.0.0/16 (internet connection)" |
| Needs-network confirm | "Scan this network" |
| Pill — queued | "Queued" |
| Pill — delivered | "Sent to the Pi" |
| Pill — running | "Scanning…" |
| Pill — uploading | "Uploading results…" |
| Pill — done | "View scan" |
| Pill — failed | "Scan failed — `<error_code>`" · [Retry] |
| Pill — expired | "The Pi never picked up the scan." · [Retry] |
| Hint under trigger | "A scan usually takes about 10 minutes." |
| Toast — 503 `device_offline` | "Pi seems to be offline." |
| Toast — 409 `device_busy` | "That Pi is already scanning. Showing the scan in progress." *(FLOWS open decision #2 — this is the proposed copy)* |
| Blank — heading | "No Pi connected yet." |
| Blank — body | "Dmitri scans your network from a small box installed on site. Your installer sets it up — once it's online, it shows up here and you can run your first scan." |
| Blank — viewer/admin line | "Contact whoever installed Dmitri if you were expecting to see one." |
| Error | "Couldn't load the agents." · [Retry] |

**Layout:**

Ready — admin:
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   AGENTS                                                                     |
|   The Dmitri box on your network.                               (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   +----------------------------------------------------------------+        |
|   |  DMITRI-NSPI-01                                                 |        |
|   |  Online · last seen 2 min ago                                   |        |
|   |  Scanning: Ethernet · 192.168.0.0/24            [Change]        |        |
|   |                                                                 |        |
|   |                                        +------------------+     |        |
|   |                                        | ▓   Scan now     |     |        |
|   |                                        +------------------+     |        |
|   |                       A scan usually takes about 10 minutes.    |        |
|   +----------------------------------------------------------------+        |
+------------------------------------------------------------------------------+
```

Needs a network — admin, first run:
```text
|   +----------------------------------------------------------------+        |
|   |  DMITRI-NSPI-01          Online · last seen 12 s ago            |        |
|   |  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -    |        |
|   |  WHICH NETWORK SHOULD DMITRI SCAN?                              |        |
|   |  This box is connected to more than one network. Pick the one   |        |
|   |  you want scanned — usually the office network, not the         |        |
|   |  internet connection.                                           |        |
|   |                                                                 |        |
|   |    ( ) Ethernet · 192.168.0.0/24                                |        |
|   |    ( ) Wi-Fi    · 10.12.0.0/16   (internet connection)          |        |
|   |                                                                 |        |
|   |                                   [ Scan this network ]         |        |
|   +----------------------------------------------------------------+        |
```

Scanning:
```text
|   |  DMITRI-NSPI-01          Online · last seen 4 s ago             |        |
|   |  Scanning: Ethernet · 192.168.0.0/24                            |        |
|   |                                         [ ▓ Scanning… ]         |        |
```

**Open questions:**
1. **Offline: keep `[Scan now]` or hide it?** Spec says **keep it visible and enabled.** `online` is
   derived from the WebSocket registry and can be momentarily stale, and the backend already
   **retries delivery twice** before giving up ([`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-)).
   Hiding the button on a flag that might be wrong denies a scan that would have worked; the `503`
   toast is the designed, honest failure. **This is not rule 3** — that rule is about what a *role*
   may do, not what is momentarily unavailable.
2. ~~**C12 — does a dead Pi produce `failed` or `expired`?**~~ **✅ RESOLVED 2026-07-13 — the split is
   `delivered_at`.** Never delivered → `expired`; delivered then broke → `failed`. The screen knows
   which it gets: **a Pi that dies mid-scan is `failed`** (it took the job), and `expired` is only
   *never picked up*. Pill copy updated accordingly.
3. Pill vs stepper for the five lifecycle states — pill chosen; stepper parked
   ([`IDEAS.md`](IDEAS.md) → Agents).
4. Blocked on **C1** (no `GET /agents`) and **C2** (no `available_subnets` / `target_subnet`). The
   screen is fully designed and cannot be built until both land.

---

### USERS & INVITES

**Route:** `/users` · **Shell:** inside · **Roles:** admin only · **Flow:** B2

**This screen ships as half a screen, on purpose (§3).** Of the four things B2 breadboarded here —
list users, list pending invites, change a role, revoke an invite — **exactly one has an endpoint**:
`POST /invites`. The other three are **C4**, and no amount of frontend work conjures them.

So v1 does not ship three dead sections and a table that says "coming soon". It ships **the one
thing that works, finished**: inviting a person. The full screen is specced below it so C4 has a
target to land against.

**The route and the nav item stay `Users` throughout.** *Users* names the domain, not today's single
action, and the page grows new user-related surfaces inside it rather than being renamed around them
(§App shell). In v1 the page is titled *Users* and its whole content is the invite form; when C4
lands, the user table appears **above** the invite action and nothing in the shell moves.

**Epicenter** — the invite form, and the link it produces. The link *is* the deliverable; the form
is how you ask for it.

**Data:**
- `POST /api/v1/invites` — body `{ email, role: "admin" | "viewer" }` → **`201`
  `InviteCreatedResponse`: `{ invite_token, expires_at }`.**
- **The backend emails the invite, *and* the screen shows the link. ✅ Decided 2026-07-13** —
  transactional email is in scope (provider TBD, [C17](#users--invites)); the backend sends
  `https://<app>/invite?token=<invite_token>` to the invitee.
- **🔓 C4** — listing users, listing pending invites, changing a role, revoking an invite and
  **removing a member** have **no endpoints**. When it lands the screen consumes `GET /api/v1/users`
  and `GET /api/v1/invites` as **two separate calls, merged here into one table** — they have
  different lifecycles and different row actions, so they stay separate resources.
- **Removal ✅ decided 2026-08-08** ([`ADR-017`](../adr/ADR-017-account-removal.md)) —
  `DELETE /api/v1/users/{user_id}`, admin-only, **hard delete**. It **refuses to target the caller**
  (`/users/me` is the self-service path, and it lives in SETTINGS, not here), which is why an
  admin's own row carries no Remove action. Changing a role likewise refuses to target the caller:
  **self-demotion is not possible**. Between them, an org can never reach zero admins.
- **`last_seen_at`** is served on the user row — when the person was last active, including silent
  refresh, rendered as relative time. Pending invites have none and render `—`.
- **🔓 C18** — `POST /invites` documents **only a `201`**. Inviting an email that already has an
  account, or that already has a live invite, has **undefined behavior** — and re-inviting someone
  is the single most likely thing an admin does twice.

**Email is the convenience; the link is the guarantee.** The screen shows the copyable URL *even
though* the invite was emailed, and that is not redundancy:

- **A security product's one-time login link is structurally indistinguishable from phishing.** It
  will sometimes land in spam no matter how clean the DNS is, and the admin needs a recovery that
  doesn't depend on the thing that just failed.
- Plenty of admins would rather send it over Slack or Teams anyway.
- It keeps the screen working while deliverability is still being tuned.

**The link is still shown once, and the screen still says so.** With no `GET /invites` (C4), a token
that scrolls off the page is **gone** — email softens this (the invitee has their own copy) but does
not fix it: the *admin* cannot retrieve the link again, and their only recovery is issuing a second
invite. So the warning stays, worded as a nudge rather than an alarm (§7).

**Three states:**
- **Regular:** the invite form. Email, role, `[Send invite]`.
- **Blank:** **not applicable in v1** — a form is its own content. (When C4 lands, the *user table*
  gets a blank state, and it is never truly empty: the admin reading it is in it.)
- **Created (the state that matters):** the form is replaced by a confirmation that the invite was
  **emailed**, plus the link, a `[Copy link]` button, when it dies, and the once-only nudge.
  `[Invite someone else]` returns to the form.
- **Error:** inline under the field. A duplicate invite (C18) has no defined status, so the copy
  below is provisional.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Users" |
| Section title (v1) | "Invite a user" |
| Subtitle (v1) | "Create a link that lets someone join your organization." |
| Fields | "Email" / "Role" |
| Role — viewer | "Viewer — can see scans, hosts and findings." |
| Role — admin | "Admin — can also run scans and invite people." |
| Button | "Create invite link" · in flight: "Creating…" |
| Created — heading | "Invite sent." |
| Created — body | "We emailed an invite to **name@example.com**. It works once, and expires **in 48 hours**." |
| Created — link label | "Or send them this link yourself:" |
| Created — nudge | "This is the only time you'll see this link. If they never get the email, copy it now." |
| Created — copy button | "Copy link" · after click: "Copied" |
| Created — again | "Invite someone else" |
| Error — bad email | "That doesn't look like an email address." |
| Error — duplicate (⚠️ C18, provisional) | "That person already has an account or a pending invite." |
| Error — server | "Couldn't create the invite." · [Try again] |
| Table columns (post-C4) | "Person · Role · Status · Last seen" |
| Active row (post-C4) | "Active" · "2 hours ago" · [Remove] |
| Pending row (post-C4) | "Invited — expires in 2 days" · "—" · [Revoke] |
| Own row (post-C4) | "Active · you" — **no Remove, no role control.** Leaving is done in Settings |
| Blank table (post-C4) | "You're the only person here." |
| Remove — confirm heading | "Remove name@example.com?" |
| Remove — confirm body | "They lose access immediately and their account is deleted. This can't be undone. You can invite them again later." |
| Remove — confirm prompt | "Type their email address to confirm." |
| Remove — confirm button | "Remove" · in flight: "Removing…" |
| Remove — error | "Couldn't remove that person." · [Try again] |

**"Added" was dropped, deliberately.** The earlier column deck carried *Person · Role · Status ·
Added*. `last_seen_at` replaces it rather than joining it: the one case where Added earns its place
— telling a brand-new member apart from a long-dormant one, both reading "Never" — cannot arise,
because accepting an invite issues a session immediately, so a user's first activity timestamp *is*
their join date. For a pending row, "expires in 2 days" already carries the only time fact worth
having. Four columns, not five.

**Layout — v1 (the buildable screen):**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   USERS                                                                      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   INVITE A USER                                                              |
|   Create a link that lets someone join your organization.       (muted)      |
|                                                                              |
|   Email                                                                      |
|   [__________________________________________]                               |
|                                                                              |
|   Role                                                                       |
|     (•) Viewer — can see scans, hosts and findings.                          |
|     ( ) Admin  — can also run scans and invite people.                       |
|                                                                              |
|   [ ▓  Create invite link  ]                                                 |
+------------------------------------------------------------------------------+
```

Created — the form is replaced by the confirmation:
```text
|   INVITE SENT.                                                               |
|                                                                              |
|   We emailed an invite to name@example.com. It works once, and expires       |
|   in 48 hours.                                                  (muted)      |
|                                                                              |
|   Or send them this link yourself:                                           |
|   +----------------------------------------------------------------+        |
|   | https://app.dmitri.io/invite?token=8f3c9a1e-…      [ Copy link ]|        |
|   +----------------------------------------------------------------+        |
|   This is the only time you'll see this link. If they never get the          |
|   email, copy it now.                                           (muted)      |
|                                                                              |
|   Invite someone else                                                        |
```

**Layout — post-C4 (the table lands above the invite action; the shell does not move):**
```text
|   USERS                                                                      |
|   ------------------------------------------------------------------        |
|   PERSON                  ROLE     STATUS                    ADDED           |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   anna@acme.com (you)     Admin    Active                    Jul 2           |
|   sam@acme.com            Viewer   Active                    Jul 8           |
|   new@acme.com            Viewer   Invited — expires in 2d   Jul 12  [Revoke]|
|                                                                              |
|                                            [ ▓  Invite a user  ]             |
```

**Open questions:**
1. **C4** — no `/users` endpoints. Everything except the invite form is unbuildable; the v1 page is
   the honest subset.
2. ~~**C17** — no email delivery exists anywhere in the product.~~ **✅ Decided 2026-07-13 —
   transactional email is in scope; provider TBD.** The code is small (`httpx` is already a backend
   dependency; two call sites, both at points where a token is already minted); the real work is a
   sending domain with **SPF/DKIM/DMARC**, without which these mails land in spam. **This is what
   unblocks FORGOT/RESET PASSWORD**, which — unlike invites — have no human in the loop to hand-carry
   a link. Remaining: pick the provider, own the sending domain.
3. **C18** — re-inviting an existing user or a pending invitee is undefined. It is also the most
   likely repeat action on this screen.
4. ~~Rename the nav item to "Invite" for v1?~~ **✅ Decided 2026-07-13 — no.** It stays **Users**,
   at `/users`, and grows more user-related surfaces inside it. Nav names domains, not the one
   action that happens to be buildable this month.

---

### SETTINGS

**Route:** `/settings` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B5

**Epicenter** — change your own password. It is the reason this screen exists: voluntary
self-service password change is the **only** change-password screen in the product — there is no
forced rotation and no 403-triggered flow ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced
periodic rotation is rejected as NIST-misaligned).

**Leaving the organization also lives here** ([`ADR-017`](../adr/ADR-017-account-removal.md), added
2026-08-08), for **both roles**. A viewer never sees the USERS screen, so this is the only place
they can remove their own account — and an account nobody can leave is the wrong default for a
product holding this data. It sits at the bottom, visually separated, and is the last thing on the
page: it is not what anyone came here to do.

**The scan target network is not here.** It is a property of the Pi, not of the user — one box
pointed at one network, identical for every admin in the org. It lives on AGENTS (B4).

**Data:**
- `POST /api/v1/auth/change-password` → **`204`**. Body: `{ current_password, new_password }`;
  `new_password` has `minLength: 12` in the contract. Errors: `400` (policy / bad request), `401`.
- Profile (display name, email) — **🔓 C3. There is no `/users` resource in the contract at all**,
  and `LoginResponse` returns only a token. The section is specced but cannot be built.
- `DELETE /api/v1/users/me` → **`204`**. No body. Any role. **Hard delete** — the account and its
  sessions are gone, not disabled. One error worth designing for: **`409 last_admin`** when the
  caller is their org's only admin, because an org with no admins can invite nobody and manage
  nothing. The route does **not** clear the refresh cookie and does not need to: deleting the user
  cascades their refresh tokens, so the cookie is already inert.

**Password policy** ([`AUTH.md`](AUTH.md) → Passwords) — stated up front, not discovered by failing:
minimum 12 characters; no common or breached passwords; no obvious patterns (repeated characters,
simple suffixes); no names or birth dates.

**Three states:**
- **Regular:** the form. Both sections stacked in the 720px prose column.
- **Blank:** **not applicable, deliberately.** A settings form is never empty — it always has its
  own fields. Recording this so nobody invents an empty state to satisfy rule 1.
- **Error:** field-level inline errors (wrong current password, policy rejection). No toast for form
  validation — the error belongs next to the field that caused it.
- **Success:** inline confirmation, not a redirect. The user stays where they are.
- **Confirming removal:** a modal over the page. It states what is lost, and the button stays
  inert until the user has typed **their own email address** — deletion is irreversible and kills a
  live session, so a single click is not proportionate to it. Same component as the USERS screen's
  Remove; two call sites is the bar §Shared components sets.
- **Removed:** not a state of this screen. The session is gone, so the SPA drops its in-memory token
  and redirects to LOGIN, which carries the confirmation line (see LOGIN copy).

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Settings" |
| Section — password | "Change your password" |
| Policy hint | "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere." |
| Fields | "Current password" / "New password" / "Confirm new password" |
| Button | "Change password" |
| Success | "Password changed." |
| Error — wrong current | "That's not your current password." |
| Error — policy | "That password isn't strong enough. Try a longer one that isn't based on a name or a date." |
| Error — mismatch (client-side) | "Those two passwords don't match." |
| Section — profile | "Your details" |
| Profile fields | "Display name" / "Email" |
| Profile button | "Save" |
| Section — leaving | "Leave this organization" |
| Leaving — body | "Your account is deleted and you lose access to **Acme**'s scans, hosts and findings straight away. This can't be undone — an admin would have to invite you again." |
| Leaving — trigger | "Delete my account" |
| Confirm — heading | "Delete your account?" |
| Confirm — prompt | "Type **you@example.com** to confirm." |
| Confirm — button | "Delete my account" · in flight: "Deleting…" |
| Confirm — cancel | "Cancel" |
| Error — last admin (`409`) | "You're the only admin. Make someone else an admin first, then you can leave." |
| Error — server | "Couldn't delete your account." · [Try again] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SETTINGS                                                                   |
|   ------------------------------------------------------------------        |
|                                                                              |
|   CHANGE YOUR PASSWORD                                                       |
|   At least 12 characters. Avoid names, dates, and passwords you've           |
|   used elsewhere.                                               (muted)      |
|                                                                              |
|   Current password       [____________________________]                      |
|   New password           [____________________________]                      |
|   Confirm new password   [____________________________]                      |
|                                                                              |
|                          [ Change password ]                                 |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|                                                                              |
|   YOUR DETAILS                                        ⚠️ blocked — C3         |
|   Display name           [____________________________]                      |
|   Email                  [____________________________]                      |
|                          [ Save ]                                            |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|                                                                              |
|   LEAVE THIS ORGANIZATION                                                    |
|   Your account is deleted and you lose access to Acme's scans,               |
|   hosts and findings straight away. This can't be undone — an                |
|   admin would have to invite you again.                         (muted)      |
|                                                                              |
|   [ Delete my account ]                                                      |
+------------------------------------------------------------------------------+
```

Confirming — a modal over the page; the button is inert until the address matches:
```text
+--------------------------------------------------+
|  DELETE YOUR ACCOUNT?                            |
|                                                  |
|  Your account is deleted and you lose access     |
|  straight away. This can't be undone.            |
|                                                  |
|  Type you@example.com to confirm.                |
|  [__________________________________]            |
|                                                  |
|            [ Cancel ]  [ Delete my account ]     |
+--------------------------------------------------+
```

**Open questions:**
1. **C3** — no user resource. The profile section cannot be built.
2. **Wrong current password: `400` or `401`?** The contract lists both and doesn't say which one a
   bad `current_password` produces. A `401` would trip the Axios refresh interceptor
   ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client) and could bounce the user to login
   for a mistyped field — so this must be a **`400`**, or the interceptor needs an exception for
   this route. **Confirm before building.**
3. Password strength meter — parked ([`IDEAS.md`](IDEAS.md) → Auth & admin). The policy hint is
   stated up front instead.
