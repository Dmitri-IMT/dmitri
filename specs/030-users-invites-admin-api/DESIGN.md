# DESIGN — Activity disclosure on SETTINGS (DMI-76, § 11)

One control on one existing screen. Inherits `docs/ui/SCREENS.md` §Foundations and §SETTINGS
(`:1463`) unchanged; nothing there is re-decided. The admin member surface (member table, role
control, revoke) is **DMI-90 and is not designed here**.

Authority for the content: `ARCHITECTURE.md` § 11 and TRUTH's disclosure rules
(`TRUTH.md:56-63`) and acceptance rows *Disclosure is present / states the facts / is reachable
without a mouse / is not a setting*.

---

## 1. Screen flow

```
SETTINGS  /settings
  └── Activity disclosure  ── activate control ──▶ note revealed (same page, same scroll anchor)
                           ◀─ activate again ──── note hidden
```

- **No route change, no navigation, no push, no modal, no toast.** The control is a local reveal
  on `/settings`. It is the only interaction it has.
- Reachable by both roles at the existing entry to SETTINGS (top bar → Settings). No role branch:
  admin and viewer render byte-identical markup. There is no `role` read and therefore no
  absent-not-disabled decision to make here.
- It fetches nothing, so it has no entry state of its own — it is present on first paint.

---

## 2. Placement

Today `Settings.tsx` renders two children in a `flex flex-col gap-12` page column: the `Settings`
`<h1>` and the password `<form>`. The leave-the-organization block is specced in
`SCREENS.md` §SETTINGS but **is not built yet** (no `Leave this organization` string exists under
`frontend/src/`). Placement is therefore fixed structurally, not by adjacency to code that is
absent:

> The disclosure is a **sibling section of the page column**, rendered **after the password form
> and before anything that follows it**. When the leave-the-organization block lands it is appended
> after the disclosure, and the disclosure needs no edit.

Two consequences the implementer must not get wrong:

1. The control is **outside the `<form>` element**. A `<button>` inside a form defaults to
   `type="submit"`; putting the disclosure inside the password form would make Enter or a click
   attempt a password change. It is a sibling of the form, not a child of it.
2. It carries **no outer margin**. The `gap-12` on the existing page column supplies the space
   (rhythm rule 1).

---

## 3. Visual mockups (1440px target, 720px prose column)

Fat-marker renders: they show arrangement and proportion. Every number is in §4.

### 3.1 Collapsed — the default, and what a member sees on arrival

```text
+--------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings              [Log out]   |
+================================================================================+
|                                                                                |
|   SETTINGS                                                                     |
|   ---------------------------------------------------------------             |
|                                                                                |
|   CHANGE YOUR PASSWORD                                                         |
|                                                                                |
|   Current password       [__________________________________]                  |
|                                                                                |
|   New password           [__________________________________]                  |
|   At least 12 characters. Avoid names, dates, and passwords you've             |
|   used elsewhere.                                             (muted)          |
|                                                                                |
|   Confirm new password   [__________________________________]                  |
|                                                                                |
|                          [ Change password ]                                   |
|                                                                                |
|                                                                                |
|   ACTIVITY   What's recorded?                                                  |
|                                                                                |
|                                                                                |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -                |
|                                                                                |
|   LEAVE THIS ORGANIZATION                            (not built — DMI-102/     |
|   Your account is deleted and you lose access ...     SCREENS.md §SETTINGS)    |
|                                                                                |
|   [ Delete my account ]                                                        |
+--------------------------------------------------------------------------------+
```

**Walkthrough.** The page is unchanged above the submit button. Below it, a new section: the word
`Activity` set as a section label in the same type as `Change your password`, with the control
`What's recorded?` immediately to its right on the same line, set as body text. That line is the
entire section when collapsed — two elements, one row, nothing else. The gap above it is the page's existing
inter-section step, so it reads as a peer of the password section rather than a footnote hanging
off the form. The leave-org block is drawn greyed to fix the ordering; it is out of scope and this
feature does not build it.

Focus on arrival is unchanged: the `Current password` field still autofocuses. The disclosure never
steals focus.

### 3.2 Revealed — after activating the control

```text
|                          [ Change password ]                                   |
|                                                                                |
|                                                                                |
|   ACTIVITY   What's recorded?                                                  |
|   Your organization's admins can see when you last used Dmitri and             |
|   when you last signed in. We record only these times — not what you           |
|   viewed or did.                                              (muted)          |
|                                                                                |
|                                                                                |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -                |
|                                                                                |
|   LEAVE THIS ORGANIZATION                                                      |
```

**Walkthrough — what changed.** Exactly one thing: a muted paragraph appears directly beneath the
`Activity` label row, at the same tight step the password hint uses beneath its field, so the note
is visibly *attached to* the label rather than floating between sections. Nothing above it moves;
the content below is pushed down by the paragraph's height (three lines at the 1440 target). The
control itself does not move, change size, or change its label — its pressed/expanded state is what
changes.

**Where focus sits:** on the control, both before and after. Activating does not move focus into
the revealed text, and hiding does not move focus either — the control is the thing the user is
operating and it stays under their finger and their focus ring. The revealed paragraph is the very
next thing in reading order, so a screen-reader user's next `Down`/`Tab`-adjacent read reaches it
without a focus jump.

---

## 4. Layout and spacing

Element order inside the disclosure section (top to bottom):

1. Label row: `Activity` label, then the `What's recorded?` control, side by side.
2. Revealed note (present in the DOM in both states — see §5).

| Relationship | Step | Why |
| --- | --- | --- |
| Page column → this section and its neighbours | **step 12** | Already on the page (`gap-12`). The disclosure is a peer section; the parent supplies this, the component supplies none of it. |
| Label ↔ control (horizontal) | **step 2** | The scale's label-to-value step. |
| Label row ↔ revealed note (vertical) | **step 1** | The same step the existing password hint uses under its field. Proximity is what says "this note belongs to that label". |

**Vertical rhythm on this screen — three steps, unchanged:** intra-group **1**, inter-group **4**,
inter-section **12**. The disclosure introduces no fourth step; step 2 is used horizontally only,
which rhythm rule 4 does not constrain.

**No new rule, border, box or card.** Whitespace does the separating (rhythm rule 3). The only
hairline on this page stays the one under the `Settings` title, and the only dashed rule stays the
one above the leave-org block when it ships.

**Line length of the revealed note.** The prose column is `max-w-[45rem]` (720px, set once in
`AppShell`). At the body mono size that is roughly 85 characters — past comfortable reading. The
note therefore carries **`max-w-prose`** (stock Tailwind, 65ch — a token, not an arbitrary value),
giving three lines at the 1440 target and wrapping to four at the 1280 minimum. No fixed pixel
width, no `<br>`, no manual line breaks. **Decided 2026-08-10** (operator): apply it.

**Type and color.** Label: the title face at the small title size, identical to `Change your
password` — it is a section label, and Foundations forbids the title face below 16px. Note: body
mono, muted foreground, the same treatment as the password hint. Control: body mono at body size,
no accent fill and no button chrome — the brand purple is not spent on a disclosure affordance.

---

## 5. Interaction, semantics and keyboard

**The control is a `<button type="button">` whose visible text is `What's recorded?`, carrying
`aria-expanded` and `aria-controls` pointing at the id of the note** — the WAI-ARIA APG disclosure
pattern.

The note element is **always in the DOM**, hidden with the `hidden` attribute when collapsed. This
is deliberate: `aria-controls` must resolve to a real element in both states, and a conditionally
mounted target makes the reference dangle exactly when it is being read.

Why not the alternatives — all **decided 2026-08-10** (operator):

| Alternative | Rejected because |
| --- | --- |
| A hover tooltip | Hover has no touch equivalent, so the disclosure would be unreachable on a tablet — and this is a legal notice, not a nicety. It also risks WCAG 1.4.13 (content on hover must be dismissable, hoverable and persistent) unless reimplemented as, effectively, a disclosure. Tooltip content is transient, and transient is the wrong shape for a disclosure a member may want to sit and read. |
| `<details>` / `<summary>` | The native element is genuinely accessible-ish but exposes an inconsistent role and state across screen readers and browser versions, gives no control over how "expanded" is announced, and drags in a marker that has to be un-styled to meet the square, hairline house style. It also invites the summary to *be* the label, which would fuse the subject label and the control into one element — but `Activity` must remain a plain visible label so the top layer of the notice reads as a statement even when nobody ever opens it. |
| An anchored popover / floating panel | It would avoid the reflow below, but costs click-outside dismissal, `Escape` handling, a z-index stacking decision and narrow-viewport positioning logic — real machinery, for no gain on a page this sparse. |
| An icon-only control (a glyph, no text) | See §6. The repo ships no icon set and this screen renders no icons; more importantly the top layer of a layered notice must name its subject in visible text. |

**Presentation: an inline paragraph in normal page flow**, not an anchored panel. **Accepted
consequence:** revealing pushes the content below it down by the note's height. That is acceptable
— the reflow is user-initiated, nothing *above* the control moves, and focus stays on the control,
so nothing the user is looking at or operating shifts under them. Recorded so it is not re-litigated
as a bug: converting this to an anchored panel later would be a **styling change, not a rewrite** —
the button semantics, the ids, the copy and the testids all survive it unchanged.

**Behaviour:**

| Event | Result |
| --- | --- |
| Click / `Enter` / `Space` on the control while collapsed | Note is revealed; `aria-expanded` becomes `true`; focus stays on the control. |
| Click / `Enter` / `Space` while revealed | Note is hidden; `aria-expanded` becomes `false`; focus stays on the control. |
| `Escape` | **Nothing — deliberately.** The note is inline and non-modal: it obscures no content and traps no focus, so there is nothing to escape from. Wiring `Escape` here would make an inline paragraph behave like a dialog and would collide with the removal modal when that ships. |
| Any other key | No handler. |

**Tab order** (page order, unchanged elsewhere): Current password → New password → Confirm new
password → **Change password** → **`What's recorded?`** → (leave-org trigger, when it ships).
The control is a single tab stop in both states. The revealed note contains no focusable content
and adds no tab stop.

**Focus ring** is the standard one, never removed. The control's text gives it an adequate hit area
without extra padding, which is one more thing the text control buys over a glyph.

---

## 6. Accessibility

- **Accessible name of the control:** `What's recorded?` — **its own visible text**. There is no
  `aria-label` and none may be added: an `aria-label` on a text-bearing control overrides the
  visible words, which breaks WCAG 2.5.3 (Label in Name) for speech-input users and creates two
  names to keep in sync. The name is **stable across both states** — state is carried by
  `aria-expanded`, and a name that flips between "Show…" and "Hide…" makes one control announce as
  two different ones. **Decided 2026-08-10** (operator): text control, so visible text *is* the
  accessible name.
- **How the note is announced:** by `aria-expanded` on the control (state) plus the note's position
  as the next element in reading order (content), with `aria-controls` binding them. It is **not** a
  live region and must not be given `role="status"` or `aria-live` — nothing arrives
  asynchronously, and a live region would speak over the expansion announcement. It also gets no
  `role="region"`, which would demand its own accessible name and add landmark noise for one
  paragraph.
- **Why an unlabelled icon-only control is rejected** (**decided 2026-08-10**, operator): the
  `Activity` text is not decoration — it is the *top layer* of a layered notice, and its job is to
  name the subject that the lower layer explains. Settings displays no activity data whatsoever, so
  a bare `(i)` would sit beside nothing and disclose nothing: a member who never activated it would
  learn only that something unspecified exists. The visible word `Activity` is what makes the
  unopened state honest. A glyph would also have needed an `aria-label` to be usable at all — a
  second, invisible string to keep in sync — and the repo ships no icon set, so it would have meant
  inventing one for a single control on a screen that renders no icons. Two visible words solve
  both problems and add no dependency.
- Both roles get identical markup, so there is no accessibility difference between admin and viewer.

---

## 7. Exact copy

Implementers invent no wording.

| Element | Copy (verbatim) |
| --- | --- |
| Section label (visible, both states) | `Activity` |
| Control — visible text, and therefore its accessible name (both states) | `What's recorded?` |
| Revealed note | `Your organization's admins can see when you last used Dmitri and when you last signed in. We record only these times — not what you viewed or did.` |

> ### ⚠️ Spelling: `organization`, American — decided 2026-08-10 (operator)
>
> **The note above is the authority for this string. Do not "correct" it from `TRUTH.md` or
> `ARCHITECTURE.md` § 11, which spell it `organisation`.** Those are specs; this is copy, and the
> divergence is deliberate.
>
> The repo's split is by register, not by accident: every **user-facing** string is American
> (`docs/ui/SCREENS.md:1361, 1403, 1472, 1525` — including `Leave this organization`), while every
> **API description** is British (`contracts/openapi/openapi.yaml` ×4, and the generated
> `openapi.d.ts` ×4). On-screen copy matches on-screen copy. This note and `Leave this organization`
> will sit about 100px apart on the same page, so they must agree.
>
> `ARCHITECTURE.md` § 11 is being patched to point here as the authority for the exact copy.

Punctuation: the dash in the note is a true em dash (`—`). The apostrophes in `organization's` and
`What's` are **plain ASCII `'`**, matching `frontend/src/lib/copy.ts` and `Settings.tsx`
(`That's not your current password.`), which use no typographic quotes anywhere.

**Copy that must not exist anywhere in this section:** no toggle or switch label, no "Allow",
"Enable", "Opt out", "Manage", "Learn more", no link to a privacy page, no date or time value, no
"Last seen"/"Last signed in" field. The lawful basis is legitimate interests, not consent; a
control implying choice would misdescribe it (`TRUTH.md:62`).

These strings are **not** added to `frontend/src/lib/copy.ts`: that module exists for wording shared
across screens, and this wording appears on exactly one screen.

---

## 8. States

| State | Trigger | What is on screen | `aria-expanded` |
| --- | --- | --- | --- |
| **Collapsed** (default, on every mount) | Initial render; or activating the control while revealed | Label row only. The note is in the DOM but `hidden`. | `false` |
| **Revealed** | Activating the control while collapsed | Label row plus the note beneath it. | `true` |

**There is no loading, empty, error, success or disabled state, and none may be invented.** This
control **fetches nothing** — no query, no mutation, no endpoint, no cache key. Its entire state is
one boolean held in the component. There is nothing that can be pending, absent or fail. Rule 1's
three-states requirement is satisfied by recording this explicitly rather than by manufacturing
states, exactly as §SETTINGS already does for its blank state.

The state does **not** persist across mounts: no `localStorage`, no URL parameter, no server
preference. Leaving `/settings` and returning shows it collapsed again. Persisting it would make it
look like a saved setting, which it is not.

---

## 9. Data

**None.** This feature's frontend change consumes **zero contract endpoints and zero contract
fields.**

- No `GET /api/v1/users/me` read is added — the disclosure is role-independent, so nothing about
  the caller is needed to render it. (The page already lives behind the authenticated shell; that
  is unchanged.)
- `last_seen_at` on `OrgMember` (this feature's new contract field) is **read by nothing on this
  screen**. The member's own last-seen and last-login values are deliberately not displayed
  (`ARCHITECTURE.md` § 11).
- `last_login_at` is exposed by no endpoint at all and must not be requested.
- No new file under `frontend/src/api/` or `frontend/src/types/`. `npm run gen:types` must still be
  re-run and its output committed: the backend half of this feature adds four operations and five
  schemas to `contracts/openapi/openapi.yaml`, so `frontend/src/types/openapi.d.ts` changes even
  though this screen reads none of them. That generated file tracks the contract, not the screen.

Files touched: `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Settings.test.tsx`, and the
regenerated `frontend/src/types/openapi.d.ts` — and nothing else under `frontend/`, per
`ARCHITECTURE.md`'s file table (rows 26–28).

---

## 10. `data-testid`

Existing ids on this page (`settings-idle`, `settings-form`, `settings-current`, …) are unchanged.
New ids follow the same `settings-*` prefix.

| `data-testid` | Element | Present when | Notes for `Settings.test.tsx` |
| --- | --- | --- | --- |
| `settings-activity` | The disclosure section container | Always | The state container. Assert it renders for `adminProfile` **and** `viewerProfile`. |
| `settings-activity-label` | The visible `Activity` label | Always | Assert its text content is exactly `Activity`. |
| `settings-activity-info` | The `<button>` control | Always | Assert `aria-expanded` is `"false"` initially and `"true"` after activation; assert it is reachable and operable by keyboard alone (`Tab` to it, `Enter`/`Space` to activate); assert `aria-controls` equals the note's `id`. Prefer finding it as `getByRole('button', { name: "What's recorded?" })` — that asserts the accessible name comes from the visible text. |
| `settings-activity-note` | The revealed note paragraph | **Always in the DOM**, `hidden` when collapsed | Because it is always mounted, assert **visibility**, not presence: `expect(...).not.toBeVisible()` collapsed, `toBeVisible()` revealed, and `toHaveTextContent` the verbatim string. A `queryByTestId(...)` null-check will pass in both states and prove nothing. |

Naming note: the control's id is `-info`, not `-toggle`. `toggle` is the vocabulary of settings, and
tests are read as documentation.

Two assertions the test file should also carry, from TRUTH's acceptance rows: no element with a
`switch`/`checkbox` role exists inside `settings-activity`, and no timestamp is rendered in it.

---

## 11. Out of scope (explicit)

- **The admin member surface — DMI-90.** No member table, no role control, no revoke action, no
  pending-invitation list. Nothing on `/users` is designed or touched here.
- **The leave-the-organization block and its confirm modal.** Specced in `SCREENS.md` §SETTINGS,
  not built, and not built by this feature. This design only fixes the disclosure's position
  *relative* to it.
- **Displaying the member's own last-seen or last-login.** Deliberate: disclosure, not a feature.
- **A privacy or data-handling page, and any link to one.** The layered notice is two layers, both
  on this screen.
- **Persisting the revealed/collapsed state**, and any animation on the reveal.
- **Every other screen.** No shared component is added or modified; the disclosure is local to
  `Settings.tsx`, because one call site is below the §Shared components bar of two.

---

## 12. Decisions — closed

**No open questions remain.** All four were resolved by the operator on **2026-08-10**; each is
recorded in full at the section that implements it, and summarised here so none is reopened.

| # | Question | Decision (2026-08-10) | Reasoning | §  |
| --- | --- | --- | --- | --- |
| 1 | Constrain the note's line length? | **Yes — `max-w-prose`.** | 65ch stock token; the 720px column alone gives ~85-character lines, past comfortable reading. Not an arbitrary value, so Building rule 1 is satisfied. | §4 |
| 2 | `organisation` or `organization`? | **American — `organization`.** | The repo's split is by register: user-facing strings are American, API descriptions British. This note sits ~100px from `Leave this organization`; on-screen copy matches on-screen copy. **Diverges from TRUTH and `ARCHITECTURE.md` § 11 on purpose** — those are specs, not copy, and § 11 is being patched to point at §7 here as the authority. | §7 |
| 3 | What is the info control? | **Text, not an icon: `What's recorded?`** | The repo has no icon set and this screen renders no icons, so a glyph meant inventing one. Visible text is also its own accessible name, removing the `aria-label` an icon would have needed — one string instead of two, and WCAG 2.5.3 satisfied for free. | §5, §6, §7 |
| 4 | Inline paragraph or anchored panel? | **Inline, in page flow.** | A tooltip fails on touch and risks WCAG 1.4.13; a popover costs click-outside, `Escape`, z-index and narrow-viewport positioning for no gain on a page this sparse. Reflow below the control is the accepted cost — user-initiated, nothing above it moves, focus stays put. Converting to a panel later is a styling change, not a rewrite. | §5 |

**Nothing here is or was blocked on a missing API contract**, because nothing here consumes one.
