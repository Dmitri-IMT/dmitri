# DESIGN — Foundations guardrails and the four UI defects (top bar · auth card · Settings · the mark)

Five surfaces, all of them existing: the **top bar and app shell frame**, the **auth shell** and
`/login` inside it, the shared **mark** (`Ornament`) on auth and Home, **`/settings`** reordered,
and the new **change-password modal** it opens.

> **A sixth surface was cut 2026-08-22.** A development-only `/styleguide` page was specified
> here and in `ARCHITECTURE.md` §6; Guilherme withdrew it at the refine gate (`TRUTH.md`
> business rules 10–11). The rendered preview this document links serves the same purpose.

Behaviour authority is `TRUTH.md` (DMI-107, validated 2026-08-18) and nothing in it is re-decided
here. `docs/ui/SCREENS.md` §Foundations is inherited; this feature is the rare case that **amends**
it, and §14 below is the exact patch — every other Foundations decision (light only, IM Fell +
Plex Mono, the six neutrals, `--accent` `#7C3AED`, the four severity hexes, the 4px scale, zero
radius, desktop 1440/1280) stands untouched. The visual direction does not change; what changes is
that two properties it never wrote down — **interactive state** and **proportion** — are now
written down, and the four screens that drifted in those gaps are corrected under the new rules.

**On rendered previews.** Acceptance rule 12 of `TRUTH.md` — *a design is approved as rendered
pixels, not as ASCII* — is introduced **by this feature**, so this document is the first one it
applies to. The box-drawing renders below are the fat-marker layer: they carry **arrangement and
proportion only**, never measurement. Every number lives in the layout tables, named as a spacing
step or a container token. The rendered HTML preview for this spec is produced separately by the
operator and **renders from this document** — §3, §4, §5, §6, §7 and §8 are written to be its
source, which is why each carries an explicit token, step and state table rather than prose.

---

## 1. Screen flow

No route in the authenticated app changes. Two new edges, one new development-only route.

```
/login  (outside shell, public)
   │  card at --container-form, mark above it
   └─ credentials accepted ─────────────────────▶ /   (inside shell)

/  (inside shell)  ── one frame: bar and content both --container-frame, nav centred
   ├─ nav "Home"     ─▶ /
   ├─ nav "Users"    ─▶ /users        (admin only — absent for viewers, rule 3)
   ├─ nav "Settings" ─▶ /settings
   └─ [Log out]      ─▶ /login

/settings  (inside shell, admin and viewer alike)
   │
   │  section 1  Your details      — read-only email and role. NOTHING is focused on load.
   │  section 2  [Change password] — a trigger, not a form
   │  section 3  Activity          — heading, then a disclosure row
   │  section 4  Leave this organization
   │
   ├─ activate [Change password] ───────────────▶ PASSWORD MODAL over /settings
   │     │                                          (no route change, no history entry)
   │     ├─ Cancel · Escape · backdrop click ─────▶ closes, nothing sent,
   │     │                                          focus returns to [Change password]
   │     ├─ 400 wrong_current / policy / mismatch ▶ stays open, inline field error,
   │     │                                          focus moves to the offending field
   │     ├─ 5xx or network ───────────────────────▶ stays open, form-level error
   │     └─ 204 ─────────────────────────────────▶ closes, focus returns to the trigger,
   │                                                "Password changed." appears under it
   │
   ├─ activate the Activity disclosure ──────────▶ note expands in place, caret rotates
   │
   └─ activate [Delete my account] ──────────────▶ CONFIRM MODAL (spec 033, unchanged)

```

`ConfirmByTyping` and the leave-organization flow are **byte-for-byte unchanged**. This feature
moves the section that opens it and nothing else about it.

---

## 2. Draft copy for the two new §Foundations sections

**This is the feature's primary deliverable.** Written in the voice of the surrounding Foundations
sections, to be inserted into `docs/ui/SCREENS.md` §Foundations — §Interaction states immediately
after §Color, and §Proportion and containers immediately after §Viewport (it is the section
§Viewport's content-column bullet defers to).

---

### §Interaction states

> **Every interactive element declares all five of its states.** Rest, hover, focus-visible,
> active and disabled are each a designed property, specified beside the colour and the type. An
> element the user can act on and which looks identical under the pointer is a **defect**, not a
> style preference — the user has no way to learn it is a control except by clicking things at
> random to find out.
>
> This section exists because the rest of Foundations specified every *static* property
> exhaustively and never said the word `cursor`. Everything that drifted, drifted here: the
> Activity disclosure shipped as a bare native `<button>` with a text colour and nothing else, and
> it read as a label. *Decided 2026-08-18 (DMI-107).*
>
> **The five states, and what each owes:**
>
> | State | Owes |
> | --- | --- |
> | **Rest** | It looks like a control: a colour, a border, a caret or an underline that a paragraph beside it does not have. Accent purple, a hairline `--edge` boundary, or a caret — one of the three, at least. |
> | **Hover** | `cursor: pointer`, **always**, with no exception for text-shaped controls. Plus one visible change: an underline, a background wash, or a colour shift. Tailwind v4's preflight sets `cursor: default` on `<button>`, so the pointer is something you add, never something you inherit. |
> | **Focus-visible** | A ring at `--ring`, never `outline: none` and never a ring so faint it needs looking for. Keyboard users get the *same* affordance the pointer gets, not a lesser one — so a control that underlines on hover also underlines on focus. |
> | **Active** | A pressed acknowledgement — the 1px downward nudge the button primitive already carries. A control that does not move when pressed feels dead on slow connections, which is exactly when reassurance is worth most. |
> | **Disabled** | Reduced opacity, `pointer-events: none`, and out of the tab order. **Only for the progress carve-out** of Consistency rule 3 — an action the user is permitted to take but has not yet supplied the input for. A permission the user does not hold is *absent*, and has no disabled state to design. |
>
> **Only shared UI primitives are interactive.** Application screens compose primitives; they do
> not hand-roll a native `<button>`, `<a>` or `<input>`. This is not a stylistic preference — it is
> the only thing that makes the table above enforceable in one place instead of at every call
> site, and it is why the one hand-rolled control in the product is also the one that looked
> broken. `frontend/src/components/ui/` is where interactivity is allowed to be defined; every
> screen consumes it.
>
> **Motion is a transform, and it is small.** Carets rotate, buttons nudge. No fades on layout, no
> easing curves worth naming, nothing that outlasts a key press.

---

### §Proportion and containers

> **Containers have names, and the names are the only widths.** A layout width is one of the three
> named containers below or it is a bug. `max-w-[45rem]` is the same bug as `p-[13px]`: a number
> that was right once, copied to a second place where nobody re-asked whether it was still right.
> That copy is precisely how the login card became a 720px letterbox band around 336px of form.
> *Decided 2026-08-18 (DMI-107).*
>
> | Token | Value | Is the width of |
> | --- | --- | --- |
> | `--container-frame` | `70rem` (1120px) | The **frame** — the top bar's contents *and* the page content beneath it. One width for the whole shell. |
> | `--container-form` | `24rem` (384px) | The **form column** — a short form standing on its own, above all the auth card. |
>
> Both are maxima, fluid below themselves (§Viewport). Nothing else is a layout width.
>
> **Two containers, not three.** A separate 720px prose column was specified and then removed:
> once the bar and the content share one frame there is nothing left for it to measure. What it
> was really protecting — a comfortable *reading measure* — is a different job done by a different
> tool, below. *Decided 2026-08-21 (DMI-107).*
>
> **A card sizes to its content, never to its column.** A short form in a wide column is a narrow
> card centred in that column — not a wide card with a lake of padding on either side of a 336px
> input. The column and the card are two different measurements and only one of them is about the
> viewport.
>
> **The frame and the content share one width.** The top bar's contents and the page beneath it
> both span `--container-frame`, so the wordmark and the page title start on the same vertical.
> The shell reads as one column of paper rather than as chrome floating over a narrower sheet.
> *Decided 2026-08-21 (DMI-107); this replaces an earlier draft that held the content to a
> narrower measure than the bar.*
>
> **Column width and reading measure are different problems.** Widening the column does not widen
> the prose in it: a paragraph is still held to about 65 characters by `max-w-prose`, because past
> that the eye loses the line it is returning to. The column decides where the page's structure
> sits; the measure decides how long a line of text is allowed to get. Setting one from the other
> is how a wide layout becomes unreadable — and it is why the frame can widen without any body
> copy changing.
>
> **Type sizes come from the named scale.** `--text-title-lg|md|sm|xs`, `--text-body-md|sm`,
> `--text-caption-md`, `--text-nav`. The framework's raw size utilities (`text-sm`, `text-xs`) are
> not part of the scale, and using one is a violation **even when it renders the identical
> pixels** — the point of the token is that the value can be changed in one place, which a raw
> utility silently opts out of.
>
> | Token | Value | Used for |
> | --- | --- | --- |
> | `--text-nav` | `0.6875rem` (11px) | **Navigation only.** Top-bar nav items. It is a wayfinding label, not reading matter, and it is deliberately quieter than body copy so the page beneath the bar is the loud thing. Body copy stays 14px; this size never leaks into it. |
>
> **A mechanical rule is enforced by the linter, not by memory.** Arbitrary-value widths, raw type
> utilities, off-scale spacing and native controls in screens are all decidable by reading the
> source text, so all four are lint failures the moment they are written. The evidence for this is
> the spacing scale, which is enumerable and was obeyed **100%**, next to every rule that needed
> judgement, which was not.

---

## 3. Tokens this feature adds

Added to `frontend/src/index.css` under `@theme inline`, beside the existing scale. No token is
changed or removed; **three** are added.

| Token | Value | Utility | Role |
| --- | --- | --- | --- |
| `--container-frame` | `70rem` (1120px) | `max-w-frame` | the frame — top bar contents **and** page content |
| `--container-form` | `24rem` (384px) | `max-w-form` | form column — the auth card |
| `--text-nav` | `0.6875rem` (11px) | `text-nav` | top-bar nav items, and nothing else |

All three were compiled against Tailwind 4.3.3 and verified to emit the utilities above.

> **Three tokens, not four — and this resolves an open question rather than dodging it.**
>
> Earlier drafts specified a fourth token, a 720px prose column, and it caused trouble twice. An
> early draft of this section claimed `--container-prose: 45rem` would yield a `max-w-prose-col`
> utility; `ARCHITECTURE.md` claimed it would *override* Tailwind's built-in `max-w-prose`.
> Compiling settled it: **neither is true.** Tailwind ships `--max-width-prose: 65ch`, and
> `--max-width-*` beats `--container-*`, so `--container-prose` would have emitted no working
> max-width utility at all — an implementer writing `max-w-prose` would have silently got 546px.
> The fix was going to be a rename, `--container-page` or `--max-width-prose-col`, put to the
> operator as an open decision.
>
> **Option C removed the need for the token.** With the bar and the content sharing one frame,
> nothing in the product is 720px wide, so the token has no call site and is not declared. The
> naming question dissolves with it, and the two remaining container tokens collide with no
> built-in.
>
> *If the shell is ever reverted to a narrower content column, the token comes back — and it must
> come back as `--container-page` or `--max-width-prose-col`, never as `--container-prose`.*
> Recorded so the trap is not re-entered.

**`max-w-prose` (65ch) is untouched and keeps its own job** — constraining the *measure* of a
paragraph inside a column, at §6.6's Activity note and Leave body and in the seven dialog
descriptions. The width of a column and the measure of a paragraph are different problems, which is
exactly why they must not share a name. All nine existing call sites are unaffected by this
feature.

Nothing else is added. The accent purple and the four severity hexes were auditioned during the
build and are already locked in §Color — there is no colour left to decide in this feature, and
this document decides none.

---

## 4. The top bar and the app frame

> **Resolved 2026-08-21 — option C.** The operator selected a **centred navigation** and a
> **content column matching the bar**, from four combinations rendered in the preview artifact.
> This section previously specified a left-adjacent nav and a narrower content column; both are
> replaced. `SCREENS.md` §App shell is amended in §14.9, and `TRUTH.md`'s 32px wordmark→nav
> criterion is replaced by a centring criterion.
>
> **Centring is the standing default, permanently.** §App shell recorded centring as a workaround
> for a lone link and reverted it on 2026-08-07 when a second item arrived. That reversal is
> itself now reverted, and with a different justification: the nav is centred **because it is the
> product's spine**, not because of how many items it holds. It stays centred at three items and
> at eight.

### 4.1 Regular state — 1440px

```text
│◀───────────────────────────── viewport 1440 ─────────────────────────────▶│
│                                                                            │
│        ┌──────────────────── --container-frame ───────────────────┐        │
├────────┼──────────────────────────────────────────────────────────┼────────┤
│        │ DMITRI        Home  Users  Settings            [ Log out ]│        │  ← bar
├────────┼──────────────────────────────────────────────────────────┼────────┤
│        └──────────────────────────────────────────────────────────┘        │
│  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ hairline --rule, full bleed across the window ╌╌╌╌╌╌╌ │
│                      ▲                                                     │
│                      └─ nav centred on the BAR, not on the space left over │
│        ┌──────────────────── --container-frame ───────────────────┐        │
│        │                                                          │        │
│        │  Settings                                                │        │
│        │  ────────────────────────────────────────────────────────│        │
│        │                                                          │        │
│        │  (page content — same left edge as the wordmark)         │        │
│        │                                                          │        │
│        └──────────────────────────────────────────────────────────┘        │
```

**One frame, one left edge.** At 1440px both the wordmark and the page title begin 160px from the
window edge. There is no asymmetry to explain and nothing for a future implementer to "fix".

**The nav is centred on the bar, which is not the same as centred in the leftover space.** The bar
is a three-column grid — `1fr auto 1fr` — with the wordmark in the first column, the nav in the
second, and `[Log out]` in the third. Centring the nav inside a flex row instead would put it in
the middle of whatever the wordmark and the button left behind, so it would drift sideways every
time `[Log out]` changed width or `Users` appeared for an admin and vanished for a viewer. The grid
pins it to the true centre of the frame, and it **grows symmetrically from that centre** as
destinations are added. A viewer, who has no `Users` item, sees the remaining items centred on the
same axis an admin does.

### 4.2 Bar detail

```text
   DMITRI              Home    Users    Settings              [ Log out ]
   ▲                   └─16px──┴─16px───┘                     ▲
   │                            ▲                             │
   │                            └─ text-nav (11px), sentence case, --ink-muted
   │                               active item: --accent + 2px bottom border
   │                                                          │
   └─ IM Fell, --text-title-xs (16px), tracking-wide, --ink   └─ ghost button
      pinned to the frame's left edge                            pinned right

   │◀───────────────────── --container-frame ─────────────────────▶│
                                  ▲
                    the nav's centre is the frame's centre,
                    regardless of what sits either side of it
```

### 4.3 Layout table

| Region | Width | Padding | Type | Colour |
| --- | --- | --- | --- | --- |
| Bar band | full bleed | — | — | `--card`, bottom hairline `--rule` |
| Bar contents | `max-w-frame`, centred, **grid `1fr auto 1fr`** | step 4 horizontal, step 3 vertical | — | — |
| Wordmark `DMITRI` | intrinsic, `justify-self: start` | — | IM Fell `--text-title-xs` (16px), `tracking-wide` | `--ink` |
| Nav | intrinsic, **`justify-self: center`** | — | `text-nav` (11px), sentence case | `--ink-muted`; active `--accent` |
| Active nav marker | — | — | — | 2px bottom border `--accent` |
| `[Log out]` | intrinsic, `justify-self: end` | button primitive, `ghost` | primitive | primitive |
| Page content | **`max-w-frame`**, centred | step 4 horizontal, step 12 vertical | per screen | per screen |

**Vertical rhythm (binding for the shell):** step 3 inside the bar · step 12 between the bar and
the page content · **step 6** between page sections (§6.6).

**Horizontal rhythm:** between nav items, **step 4 (16px)** — unchanged. The wordmark→nav gap is
**no longer a specified measurement**: with a centred nav it is whatever the frame leaves, which at
1440px is large and at 1280px is smaller. That is the one thing option C costs, and it is why
`TRUTH.md`'s "the gap to the first nav item is 32px" criterion was replaced rather than kept.

**What does not change:** the wordmark stays 16px IM Fell at the frame's left edge, the nav labels
stay `Home`, `Users`, `Settings` in sentence case, `Users` stays absent for viewers rather than
disabled, `[Log out]` stays a `ghost` button on the right, and the active-item treatment is
untouched.

### 4.4 What widening the content column does, and does not, do

The column carries **structure**, not line length. Widening it to 1120px moves where sections,
rules and controls sit; it does not lengthen a single line of body copy, because every paragraph is
already held to `max-w-prose` (65ch ≈ 546px) — see §2 §Proportion and containers, and §6.6.

Two consequences are visible and worth stating rather than discovering:

1. **Horizontal rules get long.** The hairline under a page title and the dashed rules between
   Settings sections now span 1120px instead of 720px. On Settings, where §6.1 puts a rule at every
   section boundary, this is the change most likely to read as heavy. It is the interaction of two
   separate operator decisions, so it is called out here rather than buried.
2. **Short content sits in a wide field.** Settings' details grid and its buttons are intrinsically
   narrow and now sit at the left of a 1120px column. This suits a ledger reading and is consistent
   with the left edge the wordmark establishes.

---

## 5. The auth shell and the mark

### 5.1 `/login` — regular state, 1440px

```text
│◀───────────────────────────── viewport 1440 ─────────────────────────────▶│
│                                                                            │
│                                                                            │
│                              D M I T R I                                   │  ← IM Fell, 24px
│                       ──────────────◆──────────────                        │  ← step 2 below the
│                                                                            │     wordmark; 336px,
│                                                                            │     ending on the
│                     ┌───────────────────────────┐                          │     input edges
│                     │                           │                          │
│                     │  Sign in                  │                          │
│                     │                           │                          │
│                     │  Email                    │                          │
│                     │  [_______________________]│                          │
│                     │                           │                          │
│                     │  Password                 │                          │
│                     │  [_______________________]│                          │
│                     │                           │                          │
│                     │  [      Sign in         ] │                          │
│                     │                           │                          │
│                     └───────────────────────────┘                          │
│                          Forgot password?                                  │
│                                                                            │
│                     │◀──── 384px, portrait ────▶│                          │
```

### 5.2 `/login` — error state

Only the region between the last field and the button changes. The card grows downward; nothing
reflows sideways, because the card's width is a container token and not a function of its content.

```text
                      ┌───────────────────────────┐
                      │  Password                 │
                      │  [_______________________]│
                      │                           │
                      │  That email and password  │  ← --sev-critical, --text-body-sm,
                      │  don't match.             │     role="alert", above the button
                      │                           │
                      │  [      Sign in         ] │
                      └───────────────────────────┘
```

### 5.3 `/login` — submitting state

```text
                      │  [    Signing in…       ] │  ← disabled, primitive's disabled opacity
```

### 5.4 `/login` — arrival note (account deleted / password reset)

```text
                      ┌───────────────────────────┐
                      │  Your account has been    │  ← --accent, role="status", focused on
                      │  deleted.                 │     mount, does not survive a reload
                      │                           │
                      │  Sign in                  │
```

### 5.5 Layout table — auth shell

| Region | Width | Spacing | Type |
| --- | --- | --- | --- |
| Page | viewport, vertically centred | step 4 horizontal padding | — |
| Stack (brand group, card) | `max-w-form`, centred | **step 4** between the two | — |
| Brand group (wordmark + mark) | `w-full px-6` = **336px content measure**, centred | **step 2** between the two | — |
| Wordmark | intrinsic | — | IM Fell `--text-title-md` (24px), `tracking-wide` |
| Mark | 100% of the brand group (**336px**) | — | — |
| Card | `max-w-form` (384px) | step 6 padding | — |
| Card title | — | — | IM Fell `--text-title-sm` (20px) |
| Field group (label + input) | full | step 2 label→input | `--text-body-md` |
| Between field groups | — | step 4 | — |
| `Forgot password?` link | — | step 4 below the card, centred | `--text-body-md`, `--accent` |

**Vertical rhythm (three steps):** step 2 intra-group · step 4 inter-group · step 6 card padding.

**This is the letterbox fix, and it is one token.** The card was `max-w-[45rem]` — 720px of card
around a form whose fields are the only content, so the card read as a band. It is now
`max-w-form`, and at 384px wide by roughly 380px tall it stands as a portrait card in the middle of
the paper. Nothing inside the card changes: same fields, same order, same copy, same button.

All five outside-shell screens (`/login`, `/invite`, `/forgot-password`, `/reset-password`, and any
later addition) inherit this from `AuthShell` and none of them re-decides it. The screens whose
forms are longer — Accept invite and Reset password, which carry a password field plus a confirm
field plus the policy hint — grow **taller** at the same 384px. That is the intended behaviour: the
column is a measure, not a budget.

### 5.6 The mark — geometry

The Unicode ornament `· · ❦ · ·` is gone. **The mark is inline SVG and never a glyph** — a
font-dependent character cannot be given a size, a stroke weight or a rule to sit on, and it
renders differently on every machine that lacks the face. `Ornament` keeps its name and its three
call sites (`AuthShell.tsx`, `pages/Home.tsx`, `pages/home/HomeBlank.tsx`); only its contents
change.

**Candidate C, "Lozenge rule"** — a filled lozenge centred on a hairline that runs the full width
of its container, the rule broken either side of it. A printer's section break, which is what the
ornament was always trying to be.

```text
   ◀──────────────── container width (100%) ────────────────▶

   ───────────────────────────◆───────────────────────────
                            ▲ │ ▲
              gap step 2 ───┘ │ └─── gap step 2
                              │
                    lozenge: 12 × 12px, rotated square,
                    filled currentColor, centred on the rule


   detail, at scale:            ┌─ y = 6 (the rule's line)
                                │
            ────────────    ◆   │ ────────────
                            ▲
                    12px point-to-point, both axes
```

> **Amended 2026-08-21 from operator review of the rendered preview.** Two changes, both from
> comments on the published artifact:
>
> 1. **The rule stops at the card's content measure, not its outer edge.** On the auth shell it
>    is **336px** (384px card − 24px padding each side), so the line terminates on exactly the
>    vertical the email and password inputs do. A rule that ends on nothing is arbitrary; a rule
>    that ends on the input edge is a measure the eye can verify.
> 2. **The wordmark-to-mark gap halves to step 2 (8px).** The wordmark and the mark become one
>    group, and that group sits step 4 (16px) above the card. Previously all three were step 4
>    apart, which read as three unrelated objects.
>
> The sizing rule therefore changes from *"the full width of its container"* to **"the content
> measure it is given"** — which is what the component always did; only the container it is
> handed is now inset. `Ornament` still takes no size prop.

> **Structural amendment approved 2026-08-22.** The human approved the three-SVG
> composition and tokenized 12px fixed detail after the fourth Task 5 review triggered
> `STRUCTURAL_REEVAL.md`. The amendment preserves the operator-reviewed 336px auth
> measure, step-2 wordmark-to-mark gap, step-4 brand-group-to-card gap and
> `text-muted-foreground` colour above. This contract is authoritative.

| Property | Value | Why |
| --- | --- | --- |
| Row | `display: flex`, `width: 100%` (`w-full`), centred, step-2 (8px) gap, 12px high | Explicit width makes the row consume the measure its parent gives it; the two gaps create the break without a background-coloured knockout |
| Rules | Two independent 1px-high inline SVGs, each flexible in width | Only the rules respond to the container |
| Rule aspect ratio | `viewBox="0 0 1 1"` and `preserveAspectRatio="none"` | Non-uniform horizontal stretching is intentional for the hairlines |
| Lozenge | A separate `12 × 12px` inline SVG with `viewBox="0 0 12 12"`, `size-3 shrink-0`, and a filled diamond path | The nearest permitted size token gives one fixed detail at every container width |
| Lozenge aspect ratio | Omit `preserveAspectRatio`; the SVG default, `xMidYMid meet`, applies | The square view box and fixed square box preserve the lozenge without distortion |
| Colour | `currentColor`; the Ornament row itself sets `text-muted-foreground` (`--ink-muted`) | All three call sites get one visible appearance without parent styling, props, variants, or Home edits |
| Semantics | The outer row has `aria-hidden="true"`; every child SVG has `focusable="false"`; no title and no role | One boundary hides the whole decorative composition; the SVG attributes prevent legacy focus without creating three accessibility-tree items |
| Outer margin | none | Rhythm rule 1 — the parent screen supplies the space around it |

**Sizing is by container, never by prop.** The row explicitly fills the content measure it is
given with `w-full`; relying on flex-item auto width shrink-wraps the decoration and defeats the
measure. Its two rule SVGs split the remaining width equally through flex growth; the 12px
lozenge and the two step-2 gaps do not grow or shrink. The mark measures **336px** on the auth
shell — the card's content measure, not the 384px card — and the existing parent content
measure on Home, with no call-site configuration, size prop or variant.

On auth, a `w-full px-6` brand wrapper creates the 336px content measure from the 384px form
column using the existing step-6 padding token. That wrapper owns the wordmark-and-mark `gap-2`;
the outer auth stack keeps `gap-4` between the brand wrapper and card. No arbitrary width or
calculation is needed. The mark fills whatever measure it is handed, which is Building rule 2.

**Implementation arrangement:** use one `aria-hidden` flex row with
`w-full text-muted-foreground`, containing, in order:

1. `<svg className="h-px flex-1" viewBox="0 0 1 1" preserveAspectRatio="none" focusable="false">`
   with a `1 × 1` `currentColor` rectangle;
2. `<svg className="size-3 shrink-0" viewBox="0 0 12 12" focusable="false">` with the
   `currentColor` diamond path and no `preserveAspectRatio` override;
3. a second rule SVG identical to the first.

This composition removes the old paper-coloured knockout and its paper-only constraint. The gap
is real layout space, so the same mark can sit on any background without a variant.

> **Decision recorded 2026-08-22:** the human approved this three-SVG amendment,
> including the exact aspect-ratio and semantic rules and the operator-reviewed auth
> measure and rhythm. The earlier single-SVG, 11px, paper-knockout alternative is
> rejected.

---

## 6. `/settings`, reordered

### 6.1 Regular state — Activity collapsed

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ DMITRI      Home  Users  Settings                            [ Log out ]   │
├════════════════════════════════════════════════════════════════════════════┤
│                                                                            │
│    ┌──────────────────── --container-frame ────────────────────┐          │
│        │                                                   │               │
│        │  Settings                                         │               │
│        │  ─────────────────────────────────────────────────│  ← hairline   │
│        │                                                   │               │
│        │  Your details                                     │  ← IM Fell 20 │
│        │  Email      admin@dmitri.local                    │               │
│        │  Role       Admin                                 │               │
│        │  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ │  ← step 3 ·   │
│        │  Password                                         │    rule ·     │
│        │  [ Change password ]                              │    step 3     │
│        │  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ │               │
│        │  Activity                                         │               │
│        │  ▸ What's recorded?                               │  ← disclosure │
│        │  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ │               │
│        │  Leave this organization                          │               │
│        │  Your account is deleted and you lose access to   │               │
│        │  this organization's scans, hosts and findings    │               │
│        │  straight away. This can't be undone — an admin   │               │
│        │  would have to invite you again.                  │               │
│        │                                                   │               │
│        │  [ Delete my account ]                            │               │
│        └───────────────────────────────────────────────────┘               │
└────────────────────────────────────────────────────────────────────────────┘
```

**What the reorder is for.** The screen used to open on a current-password field with the cursor
already blinking in it, and told you nothing about whose password it was. Two questions were being
answered in the wrong order: *who am I signed in as* comes before *change my password*, always. The
identity is now the first thing on the page and needs no interaction to read, the password form has
become a single trigger, and the page's regular state is four short sections with air between them
instead of a wall of inputs.

**A dashed rule sits at every section boundary.** *Amended 2026-08-21 from operator review of the
rendered preview; this reverses an earlier draft of this paragraph, which kept the rule only above
`Leave this organization`.* Every boundary gets one — details │ password │ activity │ leave — and
every section added to this screen later gets one too. The rule is `--rule`, dashed, full column
width, `aria-hidden`.

The boundary is **step 6 (24px) end to end**, with the rule at its midpoint: **step 3 (12px) ·
rule · step 3 (12px)**. That keeps the halved rhythm the operator asked for rather than restoring
step 12 with a line dropped into it.

### 6.2 Activity expanded

```text
        │  Activity                                         │
        │  ▾ What's recorded?                               │  ← caret rotated 90°
        │  Your organization's admins can see when you last │
        │  used Dmitri and when you last signed in. We      │
        │  record only these times — not what you viewed or │
        │  did.                                             │  ← --ink-muted, max-w-prose
```

### 6.3 After a successful password change

The modal has closed, focus is back on the trigger, and the confirmation sits under it.

```text
        │  Password                                         │
        │                                                   │
        │  [ Change password ]     ← focus ring here        │
        │  Password changed.                                │  ← role="status", --ink-muted
```

The confirmation is **not** a toast. `Toast` is for actions whose result the user has navigated
away from; this one happens under the user's eye, and Consistency rule 2's toast clause is about
*failures* of actions, not confirmations of forms. It clears when the modal is opened again.

### 6.4 Error state — the page

`/settings` has no page-level fetch of its own: the email and role come from the session already in
memory (`user` on `SessionContext`), and if that is absent the user is not on this screen at all —
`RequireSession` has already sent them to `/login`. There is therefore no loading skeleton and no
page-level retry, and **that is a designed absence, not an omission**. Every failure on this screen
belongs to an action, and each is designed where the action is: the password modal (§7) and the
leave confirmation (spec 033, unchanged).

For the same reason there is no blank state. Recorded so nobody invents one to satisfy Consistency
rule 1.

### 6.5 Your details — read-only, and why

```text
        │  Your details                                     │
        │                                                   │
        │  Email      admin@dmitri.local                    │
        │  Role       Admin                                 │
```

| Field | Source | Rendering |
| --- | --- | --- |
| Email | `UserProfileResponse.email` | `--text-body-md`, `--ink`. Never truncated — an email the user cannot read in full defeats the section. Long values wrap. |
| Role | `UserProfileResponse.role` | `admin` → **Admin**, `viewer` → **Viewer**. Capitalised, not a badge and not a pill. |

**No fields, no `[Save]`, no display name.** `TRUTH.md` §Out of scope: there is no self-profile
update operation and the model has no display name — **C3 stays open**. Rendering an input the user
can type into and cannot submit would be worse than rendering text. Two label/value rows, aligned
on a two-column grid, and the section grows an editing affordance the day C3 closes.

The labels are `--ink-muted` and the values are `--ink`: the value is the content, the label is the
key to it. The old §SETTINGS mockup's `Display name` row is gone with the rest of C3.

### 6.6 Layout table — `/settings`

| Region | Width | Spacing | Type |
| --- | --- | --- | --- |
| Page title `Settings` | full column | step 4 below, then a hairline `--rule` | IM Fell `--text-title-lg` (32px) |
| Section heading | full column | step 4 to its content | IM Fell `--text-title-sm` (20px) |
| Details rows | two-column grid, label column intrinsic | step 2 between rows, step 4 label→value | `--text-body-md` |
| `[Change password]` | intrinsic, left-aligned | — | button primitive, `default` |
| Success line | full column | step 2 under the trigger | `--text-body-sm`, `--ink-muted` |
| Activity disclosure row | intrinsic | step 2 under its heading | `--text-body-md`, `--accent` |
| Activity note | `max-w-prose` | step 2 under the row | `--text-body-md`, `--ink-muted` |
| Dashed rule | full column | **step 3** above and below — one at **every** section boundary | `--rule`, dashed, `aria-hidden` |
| Leave body | `max-w-prose` | step 2 under its heading | `--text-body-md`, `--ink-muted` |
| `[Delete my account]` | intrinsic, left-aligned | step 4 under the body | button primitive, `destructive` |
| Between sections | — | **step 6** end to end: step 3 · dashed rule · step 3 | — |

**Vertical rhythm (three steps, and no fourth):** step 2 intra-group · step 4 inter-group ·
**step 6** inter-section, with a dashed rule bisecting it.

> **Amended 2026-08-21 from operator review of the rendered preview.** Inter-section spacing on
> `/settings` halves from **step 12 (48px) to step 6 (24px)**. Two consequences, recorded because
> neither is local to this screen:
>
> 1. **This amends §Spacing; it is not a screen-local exception.** §Foundations is explicit — *a
>    screen spec may not re-decide any of these; if a screen needs an exception, it changes the
>    rule here or it doesn't ship.* §Spacing's table currently assigns step 12 to "between sections
>    of a screen", so the patch in §14 gains a sixth entry. See §14.7.
> 2. **Proximity does less grouping work now.** Inter-section (24px) is only 1.5× inter-group
>    (16px), where it was 3×. The section headings are IM Fell at 20px against Plex Mono body, so
>    the face change carries grouping the space used to carry alone — which is why this holds up.
>    If a future screen with weaker headings adopts the same rhythm it will read as one run-on
>    column, and **step 8 (32px)** is the fallback that keeps a 2× jump.
>
> This is a worked example of the classification `/remediate` exists to make: the specification
> said step 12 and the operator wants step 6, so it is a **CONTRADICTION**, not a violation — the
> spec changes first, with approval, and only then does a task get written.

---

## 7. The change-password modal

It renders inside the **existing** `DialogShell`. The extraction the issue asked for already
happened — `DialogShell` is in the tree and `ConfirmByTyping` already consumes it — so this modal
is a second consumer, not a second shell. `size="sm"` (`max-w-sm`), which is the size the shell
documents for "a short form that reads better narrow and tall": exactly this.

### 7.1 Regular state

```text
        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ← --ink at 20%
        ░░░░░░┌────────────────────────────────────┐░░░░░░░░░░░
        ░░░░░░│                                    │░░░░░░░░░░░
        ░░░░░░│  Change your password              │░░░░░░░░░░░  ← IM Fell 20px
        ░░░░░░│                                    │░░░░░░░░░░░
        ░░░░░░│  Current password                  │░░░░░░░░░░░
        ░░░░░░│  [________________________________]│░░░░░░░░░░░  ← focus on open
        ░░░░░░│                                    │░░░░░░░░░░░
        ░░░░░░│  New password                      │░░░░░░░░░░░
        ░░░░░░│  [________________________________]│░░░░░░░░░░░
        ░░░░░░│  At least 12 characters. Avoid     │░░░░░░░░░░░
        ░░░░░░│  names, dates, and passwords you've│░░░░░░░░░░░  ← the hint, before it is
        ░░░░░░│  used elsewhere.                   │░░░░░░░░░░░     violated, never after
        ░░░░░░│                                    │░░░░░░░░░░░
        ░░░░░░│  Confirm new password              │░░░░░░░░░░░
        ░░░░░░│  [________________________________]│░░░░░░░░░░░
        ░░░░░░│                                    │░░░░░░░░░░░
        ░░░░░░│         [ Cancel ] [Change password]│░░░░░░░░░░░
        ░░░░░░└────────────────────────────────────┘░░░░░░░░░░░
```

### 7.2 Field error state — wrong current password

```text
        ░░░░░░│  Current password                  │░░░░░░░░░░░
        ░░░░░░│  [________________________________]│░░░░░░░░░░░  ← aria-invalid, focused
        ░░░░░░│  That's not your current password. │░░░░░░░░░░░  ← --sev-critical, role=alert
```

The same shape carries the policy rejection under *New password* and the mismatch under *Confirm
new password*. **The error sits against the field that caused it**, never as a toast, and the modal
stays open with the typed values intact — the user fixes one field, not three.

### 7.3 Form-level error state — 5xx or network

```text
        ░░░░░░│  Couldn't reach Dmitri. Try again  │░░░░░░░░░░░  ← above the buttons,
        ░░░░░░│  in a moment.                      │░░░░░░░░░░░     --sev-critical
        ░░░░░░│         [ Cancel ] [Change password]│░░░░░░░░░░░
```

### 7.4 In-flight state

```text
        ░░░░░░│                  [Changing password…]│░░░░░░░░░░  ← disabled; Cancel is
        ░░░░░░└────────────────────────────────────┘░░░░░░░░░░░     absent, Escape inert
```

`DialogShell`'s `locked` prop is set while the request is in flight, which blocks Escape, the
backdrop and Cancel together — the same treatment `ConfirmByTyping` already uses for the same
reason. A dismissal mid-request would leave the user with no idea whether their password changed.

### 7.5 Success — the modal closes

**Decision: success closes the modal and the confirmation renders on `/settings`, under the
trigger.** It does not show an inline confirmation inside the modal.

The reasoning, since the alternative is defensible: a modal that succeeds and stays open leaves the
user holding a form they have finished with, and makes them hunt for a Cancel button to dismiss a
thing that did not fail — the dismiss control would now mean "close", which is not what Cancel
said. Closing on success also puts the confirmation where the user's attention returns anyway,
beside the control they pressed, and it keeps `SCREENS.md` §SETTINGS's promise verbatim — *success
is an inline confirmation, not a redirect; the user stays where they are.* They do: they stay on
`/settings`. Errors keep the modal open precisely because there is still work to do in it.

### 7.6 Focus contract

| Event | Focus goes to |
| --- | --- |
| Modal opens | **Current password** — via `DialogShell`'s `initialFocusRef` |
| Escape · backdrop click · `[Cancel]` | back to **`[Change password]`**, the trigger |
| Success (`204`) | back to **`[Change password]`**; the `role="status"` confirmation announces itself |
| `400 wrong_current_password` | **Current password**, `aria-invalid`, error announced |
| `400 password_policy_violation` | **New password** |
| Client-side mismatch | **Confirm new password** |
| `5xx` / network | stays where it is; the form-level `role="alert"` announces |
| While in flight | trapped in the dialog; every dismissal path is inert |

`DialogShell` already restores focus to the opener by hand, because every caller opens from state
rather than a `Dialog.Trigger` and Radix would otherwise drop focus on `<body>`. This modal gets
that behaviour for free by consuming the shell — which is the point of the shell.

### 7.7 Modal layout table

| Region | Spacing | Type |
| --- | --- | --- |
| Panel | `size="sm"`, step 6 padding, step 4 between children | — |
| Heading | — | IM Fell `--text-title-sm` (20px) |
| Field group (label + input + hint/error) | step 2 | `--text-body-md`; hint and error `--text-body-sm` |
| Between field groups | step 4 | — |
| Button row | step 6 above, step 2 between the two, right-aligned | primitives |

**Vertical rhythm (three steps):** step 2 intra-group · step 4 inter-group · step 6 panel padding
and pre-button gap.

**`ConfirmByTyping` is unchanged.** Not restyled, not resized, not re-copied. Its acceptance row in
`TRUTH.md` — *its behaviour is identical to before this feature* — is a constraint on this
document as much as on the code.

---

## 8. The Activity disclosure — the worked example

This is the defect §Interaction states exists for, so it is specified state by state rather than
described.

### 8.1 Arrangement

The heading is on **its own line**, and the disclosure row sits beneath it. The old arrangement put
`Activity` and `What's recorded?` side by side on one baseline, which made two different things —
a section heading and a control — look like one label and its continuation. That is why nobody
could tell the second half was clickable.

```text
   Activity                     ← IM Fell 20px, --ink. A heading. Not interactive.
   ▸ What's recorded?           ← step 2 below. A control, and it looks like one.
```

### 8.2 The five states

The row is the **button primitive**, `variant="link"`, never a hand-rolled `<button>` — that is
§Interaction states' second rule, and this element is the reason it is written.

| State | Caret | Label | Cursor | Ring |
| --- | --- | --- | --- | --- |
| **Rest** | ▸ right-pointing, 12px inline SVG, `currentColor`, `aria-hidden` | `--accent`, `--text-body-md`, no underline | `pointer` | none |
| **Hover** | unchanged | `--accent`, **underlined**, offset 4 | `pointer` | none |
| **Focus-visible** | unchanged | `--accent`, **underlined** — the keyboard gets the same affordance as the pointer | `pointer` | 3px ring at `--ring`, intact and unclipped in both the collapsed and expanded state |
| **Active** (pressed) | unchanged | unchanged | `pointer` | the primitive's 1px downward nudge |
| **Disabled** | — | — | — | **Not applicable, deliberately.** Both roles may read this note and it needs no input, so there is no state in which the control is present and unusable. Recorded so nobody adds a disabled style it can never enter. |
| **Expanded** (orthogonal to the five) | rotated **90° clockwise** (▾), transform-only, ~120ms | unchanged | `pointer` | unchanged |

`cursor: pointer` is listed on every row on purpose. Tailwind v4's preflight sets `cursor: default`
on `<button>`; the button primitive adds `cursor-pointer` back, and consuming the primitive is how
this element gets it. The bare `<button>` it replaces is exactly how it lost it.

### 8.3 Semantics

- `aria-expanded` on the control, flipping `false` ⇄ `true`.
- `aria-controls` pointing at the note.
- The note is `hidden` when collapsed — genuinely removed from the accessibility tree, not
  visually clipped.
- Keyboard: Enter and Space both toggle, which the native `<button>` under the primitive gives for
  free. Focus stays on the control when the note opens; the note is not focused and is not a
  dialog.
- The note is **information, not a setting.** No switch, no opt-out, no persistence.

---

## 9. `/styleguide` — cut

Withdrawn 2026-08-22 (`TRUTH.md` rules 10–11, `ARCHITECTURE.md` §6). This section specified the
page's six sections, their order, and what each owed. Nothing replaces it: the rendered preview
linked from this document is where the system is judged in one look, and the human visual check
that closes the feature (`TRUTH.md` rule 13) is where the built screens are checked against it.

---

## 10. Copy

Every string, final. Implementers invent no wording. Rows marked **unchanged** are quoted from
`SCREENS.md` §SETTINGS / §LOGIN and are reproduced so this document is complete, not because they
are being re-decided.

### Top bar

| Element | Copy |
| --- | --- |
| Wordmark | `DMITRI` — unchanged |
| Nav items | `Home` · `Users` · `Settings` — unchanged, sentence case |
| Log out | `Log out` — unchanged |

### `/login` — the two drifted strings

| Element | Copy | Change |
| --- | --- | --- |
| Title | `Sign in` | **unchanged in code.** §LOGIN is amended to match it (§14.12) — the contradiction resolved in the spec's direction, not the code's |
| Error — server/network | `Couldn't reach Dmitri. Try again in a moment.` | **changed in code.** `Login.tsx:58` stops hardcoding its own string and imports `SERVICE_ERROR` from `@/lib/copy`, as Settings, AcceptInvite, ResetPassword and ForgotPassword already do. No new string is written — the constant already exists and already reads this |

Nothing else on `/login` changes. Its layout change is the card width only (§5.1).

### `/settings`

| Element | Copy |
| --- | --- |
| Page title | `Settings` — unchanged |
| Section 1 heading | `Your details` — unchanged |
| Details label — email | `Email` |
| Details label — role | `Role` |
| Details value — role | `Admin` / `Viewer` |
| Section 2 heading | `Password` |
| Section 2 trigger | `Change password` |
| Success (on the page, under the trigger) | `Password changed.` — unchanged |
| Section 3 heading | `Activity` — unchanged |
| Activity disclosure row | `What's recorded?` — unchanged |
| Activity note | `Your organization's admins can see when you last used Dmitri and when you last signed in. We record only these times — not what you viewed or did.` — unchanged |
| Section 4 heading | `Leave this organization` — unchanged |
| Section 4 body | `Your account is deleted and you lose access to this organization's scans, hosts and findings straight away. This can't be undone — an admin would have to invite you again.` — unchanged |
| Section 4 trigger | `Delete my account` — unchanged |

### The change-password modal

| Element | Copy |
| --- | --- |
| Heading | `Change your password` — unchanged (it was §SETTINGS's section heading; it becomes the modal's) |
| Field labels | `Current password` / `New password` / `Confirm new password` — unchanged |
| Policy hint | `At least 12 characters. Avoid names, dates, and passwords you've used elsewhere.` — unchanged, `PASSWORD_HINT` |
| Submit | `Change password` · in flight: `Changing password…` — unchanged |
| Cancel | `Cancel` |
| Error — wrong current (`400 wrong_current_password`) | `That's not your current password.` — unchanged |
| Error — policy (`400 password_policy_violation`) | `That password isn't strong enough. Try a longer one that isn't based on a name or a date.` — unchanged, `PASSWORD_POLICY_ERROR` |
| Error — mismatch (client-side) | `Those two passwords don't match.` — unchanged, `PASSWORD_MISMATCH_ERROR` |
| Error — server / network | `Couldn't reach Dmitri. Try again in a moment.` — unchanged, `SERVICE_ERROR` |

### The leave-organization confirmation

Unchanged in every string (spec 033). Not restated.

---

## 11. Keyboard and focus

### `/settings`

| Order | Element |
| --- | --- |
| 1 | Top bar nav and `[Log out]` (shell, unchanged) |
| 2 | `[Change password]` |
| 3 | Activity disclosure row |
| 4 | `[Delete my account]` |

**Nothing is focused when the page loads.** `autoFocus` is removed from the current-password field
— which no longer exists on the page anyway. A settings screen that steals focus into a password
field on arrival tells a screen-reader user the page is a password form, which it is not, and moves
a sighted user's caret somewhere they did not ask for. Focus starts where the browser puts it: the
document.

The details rows are text, not fields, and are not in the tab order.

### The change-password modal

Focus opens on **Current password** and is trapped in the panel. Tab order: Current password → New
password → Confirm new password → `[Cancel]` → `[Change password]`. **Enter submits** from any
field — it is a real `<form>` with a real submit button, so password managers fill it and Enter
works without a key handler. Escape dismisses, unless a request is in flight. Every dismissal path
returns focus to `[Change password]`.

### The Activity disclosure

Reached by Tab, toggled by Enter or Space, focus stays on the control while the note appears below
it. The focus ring is unclipped in both states.

### `/login`

Focus opens on **Email** (unchanged). Enter submits. The arrival note, when present, takes focus on
mount so it is announced, then yields.

---

## 12. Data

No new endpoint, no contract change, no generated-type edit.

| Surface | Contract | Fields consumed |
| --- | --- | --- |
| Your details | `GET /api/v1/users/me` → `UserProfileResponse`, already held in `SessionContext.user` | `email`, `role` |
| Change-password modal | `POST /api/v1/auth/change-password` → `204` | request `current_password`, `new_password` (`minLength: 12`); errors `400` (`wrong_current_password`, `password_policy_violation`), `401` |
| Leave confirmation | `DELETE /api/v1/users/me` → `204`; `409 last_admin` | none — unchanged |
| Top bar, auth shell, mark | none | — |

`user_id` is read from `UserProfileResponse` by nothing on this screen and is not rendered.

---

## 13. `data-testid`

New and changed only. Every unlisted id in `frontend/src/**/*.test.tsx` keeps its current value.

| `data-testid` | Element | Status |
| --- | --- | --- |
| `top-bar` | the bar band | unchanged |
| `top-bar-nav` | the nav group | **new** — the 32px gap and the 11px size are asserted against it |
| `nav-home`, `nav-users`, `nav-settings`, `log-out` | nav items and log out | unchanged |
| `ornament` | the mark's `aria-hidden` flex-row root | **new** — the mark had no id as a `<p>` |
| `auth-card` | the auth shell's card | **new** — the container assertion targets it |
| `settings-idle` | the page container | unchanged |
| `settings-details` | Your details section | **new** |
| `settings-details-email` | the email value | **new** |
| `settings-details-role` | the role value | **new** |
| `settings-password-trigger` | `[Change password]` | **new** |
| `settings-password-dialog` | the modal panel (`DialogShell` `testId`) | **new** |
| `settings-form` | the form inside the modal | unchanged id, moved into the modal |
| `settings-current`, `settings-new`, `settings-confirm` | the three fields | unchanged ids, moved into the modal |
| `settings-current-error`, `settings-new-error`, `settings-confirm-error` | field errors | unchanged, moved |
| `settings-new-hint` | the policy hint | unchanged, moved |
| `settings-error` | form-level error | unchanged, moved |
| `settings-submit` | the modal's submit | unchanged, moved |
| `settings-password-cancel` | the modal's Cancel | **new** |
| `settings-success` | `Password changed.` | unchanged id, **moved out of the form onto the page**, under the trigger |
| `settings-activity` | the Activity section | unchanged |
| `settings-activity-label` | the `Activity` heading, now on its own line | unchanged |
| `settings-activity-disclosure` | the disclosure row | **renamed** from `settings-activity-info` — the old name described a decoration, the new one describes a control |
| `settings-activity-caret` | the caret SVG | **new** — the rotation is asserted on it |
| `settings-activity-note` | the note | unchanged |
| `settings-leave`, `settings-leave-body`, `settings-leave-trigger` | leave section | unchanged |
| `confirm-by-typing-*` | the leave confirmation | unchanged, all of them |

The one rename is deliberate and is called out here so it is not discovered in a red test run.

---

## 14. `SCREENS.md` amendments

Four edits, plus the two new §Foundations sections drafted in §2. Each quotes the phrase being
replaced.

### 14.1 §The auth shell — the frame bullet

**Replace:**

> - **Frame:** wordmark, `Ornament`, then a single centered card in the **720px prose column**
>   (§Viewport). The card is the page; there is no other content.

**With:**

> - **Frame:** wordmark, `Ornament`, then a single centered card in the **`--container-form` column
>   (384px)** (§Proportion and containers). The card is the page; there is no other content — and
>   because there is no other content, the card sizes to the form rather than to the viewport. It
>   is a portrait card, taller than it is wide, and it stays 384px on the longer screens (Accept
>   invite, Reset password) which simply grow downward. It was briefly 720px, which read as a
>   letterbox band around 336px of inputs; that is the defect §Proportion and containers exists to
>   prevent. *Corrected 2026-08-18 (DMI-107).*

### 14.2 §SETTINGS — the epicenter paragraph

**Replace:**

> **Epicenter** — change your own password. It is the reason this screen exists: voluntary
> self-service password change is the **only** change-password screen in the product — there is no
> forced rotation and no 403-triggered flow ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced
> periodic rotation is rejected as NIST-misaligned).

**With:**

> **Epicenter** — **who you are signed in as, and what you can do about it.** The screen opens on
> your email and your role, read without interaction, and then offers the two things you can do to
> that account: change its password, or leave the organization. *Who am I* comes before *change my
> password*, always — a screen that opens with the cursor in a current-password field and never
> names the account has asked for a secret before saying whose it is. *Amended 2026-08-18
> (DMI-107); it previously read "change your own password".*
>
> Changing the password is still the most common reason anyone comes here, and it is still the
> **only** change-password screen in the product — there is no forced rotation and no 403-triggered
> flow ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced periodic rotation is rejected as
> NIST-misaligned). It is now reached through a `[Change password]` trigger that opens a modal, so
> the page's regular state is four short sections with air between them rather than three password
> fields and a wall of labels.
>
> **The details block is read-only** — email and role, no display name and no `[Save]`. Open
> question **C3** stays open: there is no self-profile update operation, and an input the user can
> type into but not submit is worse than text.

### 14.3 §SETTINGS — the Activity paragraph

**Replace:**

> **Activity disclosure is built for both roles** (spec 030). A visible `Activity` label sits beside
> `What's recorded?`; activating that button expands a persistent note.

**With:**

> **Activity disclosure is built for both roles** (spec 030). The `Activity` heading sits on **its
> own line**, and a disclosure row — a caret and the accent-coloured label `What's recorded?` —
> sits beneath it; activating that row expands a persistent note and rotates the caret. It was
> originally specced *beside* the heading, which made a section title and a control read as one
> label and left the control with no affordance at all; that arrangement is withdrawn. The row is
> the shared button primitive in its `link` variant and carries all five interactive states
> (§Interaction states) — it is the worked example that section is written for. *Corrected
> 2026-08-18 (DMI-107).*

### 14.4 §Viewport — the content-column bullet

**Replace:**

> - **Content column:** prose-led screens (Home, all auth screens) center on a **720px max-width**
>   column; table-led screens (Scans, Hosts, Agents, Users) on **1120px max-width**. These are
>   *maximums*, not fixed widths — below them the column shrinks with the viewport.

**With:**

> - **Content column:** the widths are the named containers and only the named containers — see
>   §Proportion and containers. **Every inside-shell screen holds `--container-frame`**, prose-led
>   and table-led alike, and so does the top bar above it: one frame, one left edge. A standalone
>   short form — the auth card above all — holds `--container-form`. Both are *maximums*, not
>   fixed widths: below them the column shrinks with the viewport.
> - **Reading measure is separate from column width.** A paragraph is held to about 65 characters
>   wherever it sits. Widening a column never lengthens a line.

### 14.5 §Shared components — the `Ornament` row

**Replace** the row's description with:

> | `Ornament` | Home, auth screens — the engraving detail: a filled lozenge on a full-width hairline, broken either side. **Inline SVG, never a Unicode glyph** — a glyph cannot be given a stroke weight, a size or a rule to sit on, and it renders differently wherever the face is missing. Sizes to its container with no props. |

### 14.6 §Screen index

The Settings row's status note changes from *"password + Activity disclosure built; profile/removal
UI pending"* to *"◐ details (read-only), password modal, activity disclosure and removal built;
profile **editing** pending on C3"*.

### 14.7 §Spacing and rhythm — the inter-section step

*Added 2026-08-21 from operator review of the rendered preview (§6.6).*

The step table's row for `12` currently reads:

> | `12` | 48px | between sections of a screen |

Replace with:

> | `12` | 48px | between sections of a **table-led or long-section** screen |
> | `6` | 24px | card internal padding; **and between sections of a short-section screen** |

And append to the four binding rhythm rules, as a clause on rule 4:

> **The inter-section step is chosen per screen, from `6`, `8` or `12` — and only those.** A screen
> whose sections are two or three short rows (Settings: a label/value pair, a button, a disclosure)
> uses `6`; a screen whose sections are tables or long prose uses `12`; `8` is the middle case.
> What stays binding is the *shape*: three vertical steps, each visibly larger than the last, and
> the inter-section step never smaller than the inter-group step. *Decided 2026-08-21 (DMI-107).*
>
> The trade is explicit. At `6` the inter-section step is 1.5× the inter-group step rather than 3×,
> so **space alone stops carrying the grouping** and the section heading has to help. That works on
> Settings because its headings are IM Fell at 20px against Plex Mono body — a face change, not
> just a size change. A screen without that contrast picks `8` or `12` instead.

**Why this is a Foundations edit and not a Settings note:** §Foundations opens with *a screen spec
may not re-decide any of these; if a screen needs an exception, it changes the rule here or it
doesn't ship.* Halving Settings' rhythm inside `DESIGN.md` alone would be exactly the drift this
whole feature exists to stop.

### 14.8 §Spacing and rhythm — rule 3, the rule-versus-whitespace preference

*Added 2026-08-21 from operator review of the rendered preview (§6.1).*

Rhythm rule 3 currently ends:

> Where a rule and whitespace would both separate two regions, prefer the whitespace: the
> near-monochrome surface earns its calm by having fewer lines on it, not more.

Replace that sentence with:

> Where a rule and whitespace would both separate two regions, the choice is **per screen and
> stated once**, not left to the component. Prose-led screens with long sections prefer the
> whitespace — the near-monochrome surface earns its calm by having fewer lines on it. **A screen
> of short, unlike sections prefers the rule**: when sections are two or three rows each, the
> space between them is too small to do the separating on its own, and a hairline does the work
> that 48px of paper used to. `/settings` is the first of these. *Decided 2026-08-21 (DMI-107).*
>
> When a screen takes the rule, it takes it at **every** boundary, including sections added later.
> A rule that appears at one boundary and not the others stops reading as structure and starts
> reading as emphasis on whatever it happens to sit above.

**This is the second amendment in a pair, and they pull against each other by design.** §14.7
halves the space between sections; this one puts a line back into it. Taken together, `/settings`
moves from an airy column to something closer to a **printed ledger** — which is arguably more
native to the paper-and-engraving direction than airiness was, but it is a change of character on
that screen and is recorded as one rather than as two small tweaks.

**The fallbacks, if the rendered result reads as busy:** rules at the original step 12, or step 6
with no rules. Both are one-line reversions of these two entries.

### 14.9 §App shell — the nav is centred, permanently

*Added 2026-08-21. This reverses a decision the section records as already made and already
reverted once, so the history is restated rather than overwritten.*

The section currently reads:

> **The nav is left-adjacent.** It was centred for as long as it held exactly one item, because a
> lone link sitting beside the wordmark reads as an orphaned control rather than as navigation.
> That was always transitional: spec 028 added `Settings` as the second item and reverted the
> centring, as promised. *Decided 2026-07-31; reverted 2026-08-07.*

**Replace with:**

> **The nav is centred, and stays centred.** The wordmark holds the frame's left edge, `[Log out]`
> holds its right, and the navigation sits on the frame's centre line — growing symmetrically from
> it as destinations are added, never drifting toward either side. *Centred 2026-07-31; reverted
> to left-adjacent 2026-08-07; centred again and made permanent 2026-08-21 (DMI-107).*
>
> The 2026-08-07 reversal treated centring as a workaround for a **lone** link — an orphaned
> control needing somewhere to sit — and so undid it the moment a second item arrived. That framing
> is what changed. The nav is centred **because it is the product's spine**, not because of how
> many items it currently holds, so the count is no longer an argument either way: it is centred at
> three items and it will be centred at eight. Treating the count as the reason is what made this
> decision reversible twice, and naming the real reason is what stops it happening a third time.
>
> **Centred on the bar, not in the leftover space.** The bar is a three-column grid — `1fr auto
> 1fr` — so the nav's centre is the *frame's* centre regardless of the wordmark's or the button's
> width. A viewer, who has no `Users` item, sees their items centred on the same axis an admin
> does. Centring it inside a flex row instead would let it drift every time something beside it
> changed width, which is the failure this spelling exists to prevent.
>
> **Consequence, recorded:** there is no specified wordmark→nav gap any more. It is whatever the
> frame leaves over, and it changes with the viewport. Any rule or test asserting a fixed gap there
> is asserting something the layout no longer promises.

**Also replace** the section's opening sentence — *"wordmark left, nav items … `[Log out]` right"* —
so the middle position is stated in the sentence that introduces the bar:

> One horizontal bar above every inside-shell screen: wordmark left, nav items centred, `[Log out]`
> right. **Users** is omitted for viewers, not disabled.

### 14.10 §App shell — the frame

*Added 2026-08-21.*

**Append to §App shell:**

> **The bar and the page share one frame.** The bar's contents and the content beneath it are both
> `--container-frame`, so the wordmark and the page title start on the same vertical. The bar's
> bottom hairline is full-bleed across the window, so the bar still reads as a band belonging to
> the window rather than as a floating object. *Decided 2026-08-21 (DMI-107).*

### 14.11 §SETTINGS — strike the stale `400`/`401` open question

*Added 2026-08-22.*

The section's open-question list currently reads:

> 2. **Wrong current password: `400` or `401`?** The contract lists both and doesn't say which one
>    a bad `current_password` produces. … **Confirm before building.**

**Delete that entry** and renumber the list. It was written before contract ask **C13** was
answered; the contract has since been explicit on the `changePassword` `401` response — *"A wrong
`current_password` is **never** `401`; it is the `400` above"* — and `backend/.../auth.py:94` and
`frontend/.../Settings.tsx:65` both implement it. Leaving it listed as open invites someone to
re-litigate a settled contract.

**In its place**, append to the section's **Data** bullet for change-password:

> Errors: **`400`** for both a wrong current password (`wrong_current_password`) and a policy
> rejection (`password_policy_violation`); `401` on this route means the session itself failed, not
> the field. This split is deliberate — the SPA's refresh interceptor
> ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client) acts on every `401`, so returning one
> for a mistyped field would refresh-and-retry, then sign the user out over a typo. *Settled by
> contract ask C13.*

---

### 14.12 §LOGIN — the title is `Sign in`

*Added 2026-08-22.*

The section's copy table reads:

> | Title | "Sign in to Dmitri" |

**Replace with:**

> | Title | "Sign in" |

The shipped screen has read `Sign in` since it was built (`frontend/src/pages/Login.tsx:86`). This
is a **contradiction** under `TRUTH.md` rules 14–15 — the specification, not the code, is what
changes — so it was put to the operator and **approved on 2026-08-22**. The product name already
sits above the form in the wordmark; repeating it in the title says it twice.

**The network error in the same table is not touched.** It stays `Couldn't reach Dmitri. Try again
in a moment.` — that one is a violation, and the code moves to meet it (§15, U6).

---

## 15. Out of scope (v1)

Inherited from `TRUTH.md` §Out of scope and restated where it bears on this document.

- **The visual direction does not change.** Paper, IM Fell, Plex Mono, `--accent` `#7C3AED`, the
  four severity hexes, zero radius: all untouched. This feature adds two Foundations sections and
  four tokens; it re-decides nothing.
- **No display-name editing and no self-profile update.** C3 stays open; Your details is text.
- **No password strength meter.** Parked. The policy hint is stated up front instead.
- **No change to `ConfirmByTyping`,** in behaviour, styling or copy.
- **No change to body type size.** 14px stays. The 11px `--text-nav` is navigation-only and appears
  nowhere else, by rule.
- **No dark variants, no theme toggle, no `prefers-color-scheme` branch.**
- **No mobile or tablet layout.** 1440 target, 1280 minimum, fluid between.
- **No screenshot or visual-regression testing.** The rendered preview is read by a human; no agent
  signs off on how anything looks.
- **No new screens at all**, product or development. The `/styleguide` page DMI-107 asked for was
  withdrawn 2026-08-22; see §9.
- **No changes to Home** beyond the shared mark it already renders.
- **`/login` copy drift — resolved 2026-08-22, and it split in two.** Both items are in scope now,
  but as different classes of work.
  - The **network error** is a **violation**: `frontend/src/lib/copy.ts:13` already exports
    `SERVICE_ERROR = "Couldn't reach Dmitri. Try again in a moment."`, the exact §LOGIN string, and
    Settings, AcceptInvite, ResetPassword and ForgotPassword all import it. Only `Login.tsx:58`
    hardcodes `Can't reach the server. Check your connection and try again.` The specification was
    right and one call site broke it. **Folded into this feature** — see §10 and U6.
  - The **title** is a **contradiction**: §LOGIN says `Sign in to Dmitri`, the shipped title says
    `Sign in`, and there is no shared constant or precedent to settle it. Guilherme decided
    **`Sign in` wins**; §LOGIN is amended, the code is not touched. See §14.12.

---

## 16. Open questions — for the approval gate

0. **✅ RESOLVED 2026-08-21 — the shell is option C.** Nav **centred**, content column
   **`--container-frame`** (1120px), matching the bar. Chosen by the operator from four
   combinations rendered in the preview artifact, with centring made the **standing default** for
   all future destinations rather than a treatment for the current item count.

   Three written decisions were reversed to land it, each amended rather than quietly dropped:
   `SCREENS.md` §App shell's left-adjacent nav (§14.9), its implicit narrower content column
   (§14.4, §14.10), and this document's own frame-wider-than-content argument (§2, §4).
   `TRUTH.md`'s "the gap to the first nav item is 32px" criterion was **replaced** — a centred nav
   makes that gap a leftover, not a measurement — by a criterion asserting the centring and one
   asserting it survives a fourth destination.

   **A side effect worth noting:** the 720px prose-column token now has no call site and is not
   declared, which dissolves the `--container-prose` naming problem that was itself an open
   question at this gate (§3). Three container tokens became two, and neither collides with a
   Tailwind built-in.


1. **C3 — no self-profile update operation.** Carried forward, unchanged. Your details ships
   read-only and gains editing when C3 closes. **Not blocking:** the section renders from
   `UserProfileResponse`, which exists.
2. **✅ NOT OPEN — wrong current password is `400`, and always was.** *Closed 2026-08-22 by
   reading all three layers.* This was carried forward from `SCREENS.md` §SETTINGS open question 2,
   which was written **before** contract ask C13 was answered and never updated. The spec inherited
   a question reality had already closed.

   | Layer | Says |
   |---|---|
   | `contracts/openapi/openapi.yaml`, `changePassword` → `401` | *"A wrong `current_password` is **never** `401`; it is the `400` above (contract ask C13)."* The `401` on this route is a session failure only — missing, malformed or expired `Authorization`. |
   | `backend/src/api/routers/auth.py:94` | `raise ApiError(400, str(exc), code="wrong_current_password")` |
   | `frontend/src/pages/Settings.tsx:65` | already branches on `status === 400 && code === 'wrong_current_password'` |

   **Why it mattered, recorded so the reasoning survives:** `frontend/src/api/client.ts:36` treats
   any `401` as an expired access token and silently refreshes-and-retries. Had this route answered
   `401` for a mistyped field, a typo would have triggered an unnecessary refresh and — when that
   refresh failed — bounced the user to `/login`. In a modal it would cost the modal, the page and
   the session at once. The contract chose `400` for exactly this reason; nothing here needs
   confirming and no implementation changes.

   The only action left is documentary: `SCREENS.md` §SETTINGS still lists this as open. §14.11
   strikes it.
3. **The mark renders on `--paper` only** (§5.6). If a future screen wants it on `--card`, the
   knockout token must change with it. Recorded as a constraint, not a blocker — all three current
   call sites are on paper.
4. **✅ CLOSED 2026-08-22 — and it was two questions, not one.** Both `/login` strings differ from
   §LOGIN, but they classify differently under `TRUTH.md` rules 14–15, and the evidence settled the
   first one without needing an opinion.

   | String | Class | Resolution |
   |---|---|---|
   | Network error | **violation** — `lib/copy.ts:13` already holds the §LOGIN string and four other screens import it; only `Login.tsx:58` hardcodes its own | code moves to the spec. Folded in as **U6** |
   | Title | **contradiction** — no constant, no precedent, a real choice | spec moves to the code: `Sign in` wins, §LOGIN amended (§14.12), approved by the operator |

   This pair is worth keeping on the record: it is the clearest live demonstration of the
   classification test the `remediate` skill (`ARCHITECTURE.md` §12.5) has to apply, and it shows
   the test is decided by evidence — does a shared constant already exist? — not by taste.
5. **✅ CLOSED 2026-08-22 — the page is cut, so the question is moot.** This document specced
   `/styleguide` **inside** the app shell (§9's mockup drew the top bar on it), while
   `ARCHITECTURE.md` §6.1 put the route **outside** `RequireSession` and its test asserted the page
   renders with no session user. Those cannot both hold: `AppShell` is a route-layout element under
   `RequireSession`, and `TopBar` reads `useSession()` and gates `Users` behind `AdminOnly`.

   Raised at the gate as a contradiction to resolve. Guilherme's answer was to withdraw the page
   entirely — the rendered preview already serves the purpose. Recorded so the contradiction is not
   re-introduced if the page is ever revived: **whoever revives it must answer this first.**
