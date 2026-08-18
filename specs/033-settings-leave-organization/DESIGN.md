# DESIGN — Leave this organization (SETTINGS · confirm modal · LOGIN arrival note)

Three surfaces, all existing: a new **last section on `/settings`**, the **confirm-by-typing modal**
it opens, and a **transient arrival note on `/login`**. Both roles see the same thing; nothing here
branches on `role`.

Inherits `docs/ui/SCREENS.md` §Foundations, §Consistency rules, §SETTINGS and §LOGIN unchanged —
nothing there is re-decided. Behaviour authority is `TRUTH.md`; copy authority is
`SCREENS.md` §SETTINGS and §LOGIN, quoted verbatim; the implementation contract is this spec's
`ARCHITECTURE.md`, which this document agrees with on every point of behaviour; the decision record
is `docs/adr/ADR-017-account-removal.md` §5–§6; the breadboard is `docs/ui/FLOWS.md` B5.

---

## 0. Copy note — the organization is not named (decided; `SCREENS.md` already carries it)

**Closed, not a deviation and not an open question.** An earlier draft of `SCREENS.md` §SETTINGS
named the org (`…you lose access to **Acme**'s scans…`). That string could never render: the only
profile a signed-in member can read is `UserProfileResponse`
(`contracts/openapi/openapi.yaml:2982`), whose three required properties are `user_id`, `email` and
`role`, and the one place `org_name` exists is `POST /api/v1/invites/lookup` — public, pre-session,
keyed by a token nobody holds here.

The operator accepted the org-neutral wording and **`SCREENS.md` has been patched**: its §SETTINGS
preamble now records that

> The copy does **not** name the organization. A signed-in member cannot read it —
> `UserProfileResponse` carries `user_id`, `email` and `role` only, and `org_name` exists solely on
> the pre-session invite lookup. The wording is org-neutral rather than adding a request to discover
> a name the heading has already supplied (spec 033).

and its copy table and its layout mockup both carry the shipping sentence:

> `Your account is deleted and you lose access to this organization's scans, hosts and findings straight away. This can't be undone — an admin would have to invite you again.`

It reads naturally under the `Leave this organization` heading: the heading has already named the
subject, so the possessive refers back to it. The modal's own body was always org-neutral and is
unchanged. **No contract ask is raised, and none is pending** (`TRUTH.md` §Out of scope: "no
member-readable source for it"). §6 is the copy authority for this feature and agrees with
`SCREENS.md` word for word.

---

## 1. Screen flow

```
/settings  (inside shell, admin and viewer alike)
   │
   │  section "Leave this organization" — last on the page
   │
   ├─ activate [Delete my account] ──────────────▶ CONFIRM MODAL opens over /settings
   │                                                  (no route change, no history entry)
   │
   │   CONFIRM MODAL — opens with ( Delete my account ) greyed, disabled, out of the tab order
   │     ├─ typed value empty / partial / different address
   │     │     └─▶ ( Delete my account ) stays disabled — cannot be clicked, keyed, or tabbed
   │     │         to; nothing can be requested from this state
   │     │
   │     ├─ [Cancel] · Escape · click the backdrop
   │     │     └─▶ modal closes, nothing requested, /settings unchanged,
   │     │         focus returns to [Delete my account]
   │     │
   │     └─ typed value matches the signed-in address — [ Delete my account ] becomes enabled
   │           └─ activate it or press Enter
   │                 └─▶ DELETE /api/v1/users/me   (once — disabled again while the request is out)
   │                        ├─ 204 ─────▶ drop the in-memory access token
   │                        │             ▶ navigate('/login', { replace: true,
   │                        │                 state: { accountDeleted: true } })
   │                        │             ▶ LOGIN renders "Your account has been deleted."
   │                        │
   │                        ├─ 409 last_admin ─▶ MODAL STAYS OPEN; session untouched and
   │                        │                    /settings unchanged behind it; the refusal
   │                        │                    message renders inside the modal; the typed
   │                        │                    address survives; the still-live confirm
   │                        │                    button is the retry
   │                        │
   │                        └─ any other failure ─▶ MODAL STAYS OPEN; same as above with the
   │                                                generic failure message. The two messages
   │                                                are never interchanged.
   │
/login   (outside shell)
   └─ arrival note above the form, once. Reload → gone (router state is consumed on mount).
```

**Why both failures stay in the modal** (decided by the operator; `ARCHITECTURE.md` §"The
error-code read path" and Constraint 4 are binding and say the same). The person is mid-action and
still signed in: nothing behind the modal has changed, so sending them back to an unchanged page
with a message on it would make them re-open the dialog and re-type the address to do the thing they
were already doing. Keeping it open puts the message where the eyes already are, keeps what they
typed, and makes the next attempt one click.

**The two branches differ in what the next step actually is, and the copy must not pretend
otherwise.** For a `5xx`, a network drop or an unexpected code, the still-live confirm button is a
real retry — the attempt may well succeed. For a `409 last_admin` it is not: nothing the person can
reach from inside the dialog changes the answer, so confirming again returns the identical refusal.
The button stays live there for consistency — one control, one accessible name, no state where a
person who typed the address correctly finds the action taken away — but the refusal's own next step
is to dismiss the dialog and make someone else an admin. **That remedy has no screen in v1** (the
contract has `updateUserRole`, the Users screen that calls it is DMI-90), which is why the refusal
carries no link: see `TRUTH.md` §Out of scope. Consistency rule 2 is satisfied either way — both
messages are plain copy naming a next step.

**There is exactly one confirming control, in every state.** `SCREENS.md` §SETTINGS writes the
server error as *"Couldn't delete your account." · [Try again]* — the bracket is the confirm button
that is already on screen, **not a second control to add**. No `Try again` button, link or toast is
rendered anywhere in this feature, and the section behind the modal never grows an action.

**No control navigates nowhere.** The last-admin refusal tells the person to make someone else an
admin; it carries **no link to `/users`**, because that screen is not built (DMI-90). When Users
ships, adding the link is a copy amendment, not a redesign.

---

## 2. Visual mockups — 1440px target, 720px prose column

Fat-marker renders: arrangement and proportion only. Every number is a step in §3.

### 2.1 Regular — `/settings` with the new section

```text
+------------------------------------------------------------------------------+
| DMITRI    Home   Settings                                      [ Log out ]    |
+==============================================================================+
|                                                                              |
|   SETTINGS                                                                   |
|   -------------------------------------------------------------------        |
|                                                                              |
|   CHANGE YOUR PASSWORD                                                       |
|                                                                              |
|   Current password       [__________________________________]                |
|                                                                              |
|   New password           [__________________________________]                |
|   At least 12 characters. Avoid names, dates, and passwords you've           |
|   used elsewhere.                                              (muted)       |
|                                                                              |
|   Confirm new password   [__________________________________]                |
|                                                                              |
|                          [ Change password ]                                 |
|                                                                              |
|                                                                              |
|   ACTIVITY   What's recorded?                                                |
|                                                                              |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -        |
|                                                                              |
|                                                                              |
|   LEAVE THIS ORGANIZATION                                                    |
|   Your account is deleted and you lose access to this organization's         |
|   scans, hosts and findings straight away. This can't be undone — an         |
|   admin would have to invite you again.                        (muted)       |
|                                                                              |
|   [ Delete my account ]                                                      |
|                                                                              |
+------------------------------------------------------------------------------+
```

**Walkthrough.** Everything above the dashed rule is today's screen, untouched: the page title with
its hairline, the password form, the Activity disclosure. Below it, one dashed hairline runs the
full width of the prose column with the page's inter-section step above *and* below it — the rule is
a sibling of the sections, not a border baked into one of them, so no section grows an outer margin
(rhythm rule 1). It is the only new line on the page and it is there because whitespace alone cannot
say "separated": every section on this page is already a step-12 apart, so more of the same gap
would read as one more section rather than as the end of the page (rhythm rule 3 is about *equal*
alternatives; here they are not equal).

The section itself is exactly three elements stacked: the title `Leave this organization` in the
title face at the section size, the muted explanation directly under it, and the trigger below that.
**Nothing else is ever added to it** — no message region, no second action, no state — because every
outcome of the removal is rendered inside the modal or is a navigation away from this page. The
section ends the page; nothing follows it.

**Focus on arrival is unchanged** — `Current password` still autofocuses. The new section never
takes focus and never scrolls itself into view. Tab order simply extends: … → `Change password` →
`What's recorded?` → **`Delete my account`**.

Both roles render byte-identical markup. There is no `role` read, so nothing here is blocked on
C16.

---

### 2.2 Confirming — modal open, value empty / partial / a different address

```text
+------------------------------------------------------------------------------+
|  DMITRI    Home   Settings                                     [ Log out ]    |  <- page behind,
|  ...........................................................................  |     dimmed and
|  ....   SETTINGS                                                        ....  |     inert
|  ....                                                                   ....  |
|  ....         +---------------------------------------------+          ....  |
|  ....         |                                             |          ....  |
|  ....         |   DELETE YOUR ACCOUNT?                      |          ....  |
|  ....         |                                             |          ....  |
|  ....         |   Your account is deleted and you lose      |          ....  |
|  ....         |   access straight away. This can't be       |          ....  |
|  ....         |   undone.                          (muted)  |          ....  |
|  ....         |                                             |          ....  |
|  ....         |   Type ana@northwind.example to confirm.    |  <- the label   |
|  ....         |   [ana@north|                            ]  |  <- focus here  |
|  ....         |                                             |     on open     |
|  ....         |              [ Cancel ]  ( Delete my account )         ....  |
|  ....         |                                             |          ....  |
|  ....         +---------------------------------------------+          ....  |
|  ...........................................................................  |
+------------------------------------------------------------------------------+
```

**Walkthrough.** The page behind is covered by a flat ink scrim at low opacity — no blur, no
gradient, no shadow under the panel. The panel is a white `--card` surface with a square
`--edge` hairline border, centred horizontally and held to a readable measure well inside the prose
column; it is separated from the page by contrast and by its border, not by elevation.

Inside, four groups top to bottom: the heading (title face, the dialog's accessible name); the muted
consequence paragraph (the dialog's accessible description); the prompt sentence, which **is the
form label** and carries the signed-in address in full ink against the muted rest; and the actions
row, right-aligned, `Cancel` first and the destructive confirm last.

**What changed from 2.1:** the modal exists, the rest of the app is inert, and focus has moved from
the trigger into the confirmation field. The section behind is otherwise unchanged — the trigger is
still rendered, still un-dimmed, simply unreachable while the dialog is open.

**The confirming action is visibly different from 2.3, and that difference is the point (amended
2026-08-17 — ADR-017 §5).** It carries the real `disabled` attribute and renders greyed — shown in
this mockup with parentheses in place of the square brackets a live button gets, the convention
this document uses throughout for a non-clickable control (§5.3). It is out of the tab order for
as long as the typed value does not match; the label does not change. Watching it turn live as the
typing becomes correct is the gate — continuous feedback the person reads without pressing
anything.

The button cannot be clicked or focused while it is `disabled`, and `Enter` in the field does not
submit the form either — a browser resolves an implicit `Enter` submit to the form's default
button, and a `disabled` default button does not fire. Nothing is sent and nothing changes on
screen; what was typed is left exactly as typed, and nothing the person wrote is cleared out from
under them.

---

### 2.3 Confirming — the exact address typed

```text
         +---------------------------------------------+
         |                                             |
         |   DELETE YOUR ACCOUNT?                      |
         |                                             |
         |   Your account is deleted and you lose      |
         |   access straight away. This can't be       |
         |   undone.                          (muted)  |
         |                                             |
         |   Type ana@northwind.example to confirm.    |
         |   [ana@northwind.example|                ]  |
         |                                             |
         |              [ Cancel ]  [ Delete my account ]
         |                                             |
         +---------------------------------------------+
```

**Walkthrough — what changed from 2.2.** The panel does not resize and no confirmation tick
appears, but the confirm button does change: it goes from the greyed, parenthesised, out-of-tab-
order rendering of 2.2 to a live button in square brackets, back in the tab order, the instant the
typed value matches — that transition is the continuous feedback the gate is built to give
(ADR-017 §5). Activating the confirm action now — or pressing `Enter` from the field — issues
exactly one `DELETE /api/v1/users/me`.

Matching is **case-insensitive and ignores surrounding whitespace** on both sides. This is not
leniency for its own sake: the product's own identity rule is case-insensitive (`users` carries a
unique index on `lower(email)`, and login looks the address up with `func.lower`), so
`Ana@Northwind.example` *is* this person's address, and a pasted value with a trailing space is the
same address too. Nothing else is normalised — a different address, a partial address or an empty
field never matches.

---

### 2.4 In flight

```text
         +---------------------------------------------+
         |                                             |
         |   DELETE YOUR ACCOUNT?                      |
         |                                             |
         |   Your account is deleted and you lose      |
         |   access straight away. This can't be       |
         |   undone.                          (muted)  |
         |                                             |
         |   Type ana@northwind.example to confirm.    |
         |   [ana@northwind.example                 ]  |
         |                                             |
         |                          ( Deleting… )      |
         |                                             |
         +---------------------------------------------+
```

**Walkthrough — two changes from 2.3.**

1. The confirm action's label becomes `Deleting…` and the button is **held** — it carries
   `disabled` for exactly as long as the request is outstanding, the same treatment
   `[Change password]` eight inches above it on this very screen already gets
   (`Settings.tsx:168`), and `[Sign in]` on LOGIN (`Login.tsx:113`). It reports work in progress;
   it does not announce that the action is unavailable, and it is released the instant the answer
   arrives. Holding it is also what guarantees the "requested once" rule: no second delete can
   leave while the first is in the air. Focus does not move — it stays wherever it was (the
   button, if it was clicked or keyed; the field, if `Enter` submitted the form).
   **This is the second of two moments the confirm button is held, not the only one (amended
   2026-08-17 — ADR-017 §5).** At an empty, partial or non-matching value the button is *also*
   `disabled` (§2.2, §5.3), out of the tab order, and greyed — that is the typing gate itself, not
   a separate state. The two moments are different in kind even though both use the same
   attribute: one is the product waiting on a *person* and reads `Delete my account`, greyed until
   the address matches; the other is the product waiting on a *server* and reads `Deleting…`,
   held until the response arrives. Do not conflate their labels or their reasons — only their
   mechanism (`disabled`) is shared.

2. **`Cancel` is absent**, not disabled. The request is already gone and the deletion it asks for is
   irreversible; a control still labelled `Cancel` would be a lie about what it can do. Removing it
   cannot strand focus, because focus can only be on the field or on the confirm action at the
   moment the request leaves.

**Dismissal is inert for the length of the request** — `Escape` and a backdrop click are ignored
while a delete is outstanding, exactly as `Cancel` is absent. This follows from the failure now
rendering *inside* the modal: dismissing mid-flight would leave a `409` or a `5xx` with nowhere to
land, and a silently swallowed refusal is worse than a second of waiting. It is bounded — the
dialog settles the moment the response arrives, into 2.5, 2.6, or a navigation to `/login` — so it
is never a spinner that cannot be left (Consistency rule 2). Both dismissal paths come back the
instant the request settles.

The field keeps its value and stays editable — editing it changes nothing about the request already
sent, and freezing it would need a `readonly`/`disabled` treatment the product does not use.

---

### 2.5 Refused — `409 last_admin`, inside the still-open modal

```text
+------------------------------------------------------------------------------+
|  DMITRI    Home   Settings                                     [ Log out ]    |
|  ...........................................................................  |
|  ....   SETTINGS                                        (unchanged behind) ..  |
|  ....                                                                   ....  |
|  ....         +---------------------------------------------+          ....  |
|  ....         |                                             |          ....  |
|  ....         |   DELETE YOUR ACCOUNT?                      |          ....  |
|  ....         |                                             |          ....  |
|  ....         |   Your account is deleted and you lose      |          ....  |
|  ....         |   access straight away. This can't be       |          ....  |
|  ....         |   undone.                          (muted)  |          ....  |
|  ....         |                                             |          ....  |
|  ....         |   Type ana@northwind.example to confirm.    |          ....  |
|  ....         |   [ana@northwind.example                 ]  |  <- kept        |
|  ....         |                                             |                 |
|  ....         |   You're the only admin. Make someone       |                 |
|  ....         |   else an admin first, then you can         |                 |
|  ....         |   leave.                             (red)  |  <- focus here  |
|  ....         |                                             |          ....  |
|  ....         |              [ Cancel ]  [ Delete my account ]         ....  |
|  ....         |                                             |          ....  |
|  ....         +---------------------------------------------+          ....  |
|  ...........................................................................  |
+------------------------------------------------------------------------------+
```

**Walkthrough — what changed from 2.4.** The modal is still here and the page behind it is exactly
as it was; the session is intact and nothing was removed. Three differences:

1. A destructive-red message appears **between the field and the actions row**, at the field-error
   size and treatment already used by the password form on this screen. It sits there, not under the
   heading, because it is the answer to the attempt the field made — and because putting it directly
   above the actions row means the person reads the refusal on the way to the button that would
   repeat it.
2. **The typed address is still in the field**, untouched. This is what makes the recovery cheap: a
   sole admin can promote a colleague in a second tab, come back to this modal and confirm again in
   one click without retyping their own address.
3. `Cancel` is back — the request has settled, so there is something to dismiss again — and the
   confirm action is live again, reading `Delete my account`.

**The confirm button is the retry — really so for a transient failure (§2.6), and only nominally
here.** A second confirm after a `409 last_admin` sends a second request and gets the same refusal,
because the remedy is on another screen. It stays live anyway: taking the action away from someone
who typed their address correctly would be a worse answer than letting them press it again, and a
control that appears and disappears across states is the inconsistency §5.3 exists to avoid. Its
label does not change to `Try again`, it does not become a second control, and the section behind
the modal grows nothing. A stable accessible name is also what stops the same button announcing as
two different controls across states.

**Focus moves to the message container**, which is focusable programmatically only
(`tabIndex={-1}`, never a tab stop) and carries `role="alert"`. Focus was on the confirm button (or
in the field) when the response arrived; moving it to the message is what guarantees the refusal is
read before anything else, and one `Tab` from there reaches the actions row.

**The message clears when a new attempt is confirmed, and when the dialog is dismissed** — it is
never left standing next to a fresh attempt. It does **not** clear when the person edits the field:
the message is the caller's (`error`, per `ARCHITECTURE.md`), the typed value is the component's,
and the component never decides that a caller's message has stopped being true. The clearing is
the caller's, and it is a contract, not politeness: the caller sets `error` to `null` **before**
awaiting the request. That empty→filled transition is the whole announcement mechanism — a
`role="alert"` whose text does not change is not re-announced, and the focus effect keyed on the
message does not re-fire. **Two identical failures in a row therefore behave identically**: the
region empties, refills with the same string, announces, and takes focus both times.

---

### 2.6 Failed — any other server or network failure, inside the still-open modal

```text
         +---------------------------------------------+
         |                                             |
         |   DELETE YOUR ACCOUNT?                      |
         |                                             |
         |   Your account is deleted and you lose      |
         |   access straight away. This can't be       |
         |   undone.                          (muted)  |
         |                                             |
         |   Type ana@northwind.example to confirm.    |
         |   [ana@northwind.example                 ]  |  <- kept
         |                                             |
         |   Couldn't delete your account.      (red)  |  <- focus here
         |                                             |
         |              [ Cancel ]  [ Delete my account ]
         |                                             |
         +---------------------------------------------+
```

**Walkthrough — what changed from 2.5: the message, and only the message.** Same slot, same
treatment, same focus move, same preserved field, same live confirm button. The two strings are
**never interchanged**: a `409 last_admin` says why the org refuses and what to do first, and
anything else — `5xx`, a network drop, an unexpected code — says the attempt failed and implies
nothing about the org's state. Reusing one message for both would tell a sole admin the server was
broken, or tell everyone else to go promote a colleague.

Here the retry is immediately worth taking, and the control for it is already under the person's
hand: activating the confirm action again re-sends the same request with the address still typed.
That is the pinned `[Try again]` of `SCREENS.md`, discharged by the button that is already there.

---

### 2.7 Arrival — `/login` after a successful removal

```text
+------------------------------------------------------------------------------+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                              D M I T R I                                     |
|                                                                              |
|              +------------------------------------------+                    |
|              |                                          |                    |
|              |  Your account has been deleted.  (accent)|  <- focus lands here|
|              |                                          |                    |
|              |  SIGN IN                                 |                    |
|              |                                          |                    |
|              |  Email                                   |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |  Password                                |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |            [ Sign in ]                   |                    |
|              |                                          |                    |
|              |            Forgot password?              |                    |
|              +------------------------------------------+                    |
+------------------------------------------------------------------------------+
```

**Walkthrough.** The auth shell is untouched. The note is **the existing arrival region with
different text** — `Login.tsx` keeps exactly one `role="status"` element and switches its copy on
which arrival brought the person here (`ARCHITECTURE.md` §"Login: one region, two notes", Constraint
10). Same slot above the form, same accent colour (a confirmation, not an error — it is never red
and never sits in the `login-error` region), same `tabIndex={-1}`, same effect that focuses it on
mount so a screen reader speaks it before anything else. `Tab` from there reaches `Email`. No second
status region is added, and the region's test id is not renamed.

**It is transient by construction**, not by a timer. The router state that carries it is read once
into component state and then erased with `navigate(pathname, { replace: true })`, exactly as the
reset note does — so a reload, a back-navigation or a second visit shows a plain sign-in form. No
`sessionStorage`, no query parameter, no toast that can outlive the tab.

The two arrival notes are mutually exclusive **by construction and by structure**: one region exists,
so nothing can stack. One comes from `/reset-password`, the other from `/settings`, and a single
navigation carries one state object; if both flags were somehow present, the deletion note wins.

---

## 3. Layout and spacing

### 3.1 The section on `/settings`

Position: **last child of the existing page column**, after the Activity disclosure, preceded by the
dashed separator. The page column (`AppShell` → the `flex flex-col` on `Settings`) keeps supplying
the inter-section step; the section and the separator carry **no outer margin** of their own.

Element order inside the section, in every state: title → explanation → trigger. **The section has
no message region and no second action** — both failures render inside the modal (§2.5, §2.6), so
nothing on this page appears, disappears or moves after the first paint.

| Relationship | Step | Why |
| --- | --- | --- |
| Page column → separator, separator → section | **12** | The screen's existing inter-section step, supplied by the parent's `gap`. The separator is a zero-height sibling, so it gets the same air on both sides and looks deliberate rather than attached to either neighbour. |
| Section title ↔ explanation | **1** | The screen's existing intra-group step — the same one binding the Activity note to its label and the hint to its field. Proximity is what says "this paragraph explains that heading". |
| Explanation ↔ trigger | **4** | The screen's existing inter-group step, the same gap the password form puts between a field group and its button. |

**Vertical rhythm on this screen — three steps, unchanged: intra-group `1`, inter-group `4`,
inter-section `12`.** This section introduces no fourth step. If it appears to need one, the
grouping is wrong.

**Horizontal.** Nothing new: full width of the 720px prose column, whose padding is already set once
in `AppShell`. The explanation carries `max-w-prose`, the same measure the Activity note uses, so
its lines stay readable at 1440 and it wraps rather than widening anything at 1280.

**The separator** is a one-pixel dashed hairline in `--rule`, full column width, decorative only
(`aria-hidden`, or a bare `<hr>` left unnamed). It is the only new line on the page — no card, no
box, no panel, no coloured "danger zone" background. The house style separates with a hairline and
air, and the copy is what carries the weight of the section.

**Type and colour.** Title: title face at the section size, identical to `Change your password`.
Explanation: body mono, muted. Trigger: the destructive button treatment (red text on a tinted
ground) — this is not the brand purple, which is reserved for focal, non-severity actions and must
never mark a destructive one. The modal's messages use body-small in `--destructive`
(`--sev-critical`), identical to the password form's field errors on this same page.

### 3.2 The modal

Structure, top to bottom, inside one panel:

1. Heading — `Delete your account?`
2. Consequence paragraph — muted.
3. `<form>` containing: the prompt, which is the field's `<label>`; the text field; **the message
   region**; the actions row.

| Relationship | Step | Why |
| --- | --- | --- |
| Panel padding, all four sides | **6** | The scale's card-padding step; the horizontal minimum for a content column is also 6, so text never runs to the panel edge (rhythm rule 4). |
| Heading ↔ consequence ↔ prompt group | **4** | Inter-group. Three distinct statements, each read on its own. |
| Prompt ↔ field | **2** | Intra-group — label to its value. The tightest pairing in the dialog, because the sentence *is* the label. |
| Field ↔ message, when the message has text | **2** | Intra-group. The failure answers the attempt the field made, so it sits tight under it — the same pairing the password form uses between a field and its error. |
| Message ↔ actions row | **6** | The actions row is the end of the dialog, and the extra air is what stops a stray click on the field's neighbourhood from landing on a destructive button. The step is unchanged whether the message holds text or not, so the buttons do not jump when a failure arrives. |
| `Cancel` ↔ confirm action (horizontal) | **2** | Inside one group. Horizontal only; it adds no vertical step. |

**The message region is always mounted and empty when clean**, so it must contribute **no height and
no step of its own** while empty — an empty paragraph that still reserves a line would leave a hole
in a dialog most people never see a failure in, and a region that appears from nothing would not be
announced (frontend-conventions). The panel therefore grows by the message's height when a failure
arrives; the heading, consequence, prompt and field do not move, and only the actions row is pushed
down.

**Vertical rhythm inside the modal — three steps: `2` intra-group, `4` inter-group, `6` framing.**

**Panel size.** `max-w-md` — a stock size token, not a magic number — centred, and fluid below that
with step-4 padding against the viewport edge, so nothing is clipped at 1280 or narrower. No fixed
pixel width, no fixed height, no internal scroll: the content is a handful of short blocks and
always fits, message included.

**Panel surface.** `--card` white, a 1px `--edge` border, square corners, **no shadow and no
rounding** (`--radius` is `0` product-wide). Backdrop: a flat `--foreground` scrim at low opacity
covering the viewport, no blur.

**Position.** Centred in the viewport, fixed, so it does not depend on where the page is scrolled.
The page behind does not scroll while it is open.

### 3.3 The component boundary

The dialog is specced as a **shared component with two named callers** — this screen now, and the
Users screen's Remove action later (ADR-017 §5; `TRUTH.md` business rules). Consequences the
implementer must honour:

- **All copy is supplied by the caller** — heading, consequence, the address to type, the confirm
  label, its in-flight label, **and the failure message**. The component hard-codes no wording,
  invents no message and maps no error code, so the Users caller can say "Remove Ana?" and pass its
  own `last_admin` / `self_target` / generic strings without forking it.
- **The failure region belongs to the component, not to the caller's page** — it is what DMI-90
  inherits, and it is why neither call site has to design a failure surface of its own. The caller
  hands in a message (`error`, per `ARCHITECTURE.md` §"`ConfirmByTyping` — the exact props"); the
  component decides where it sits, that it is always mounted and empty when clean, and that it takes
  focus when it fills.
- **It carries no outer margin and no page-level spacing.** It is a fixed overlay; the parent screen
  contributes nothing around it.
- **It exposes no `disabled` prop and no substitute-rendering prop** — there is no `disabled` prop,
  no `isConfirmEnabled`, no "inactive" variant to pass. The greyed, disabled rendering is derived
  internally from the match and from the in-flight state; a caller cannot ask for it, and cannot
  ask it away either (ADR-017 §5, amended 2026-08-17). This is the one API rule that keeps the same
  gating behaviour from being re-litigated at the second call site — DMI-90 gets the identical gate
  with zero props of its own.
- **The caller still owns the request and the navigation.** The component reports "the person
  confirmed" and "the person dismissed", awaits the caller's `onConfirm`, and renders whatever
  message comes back through `error`; deciding *which* message that is, and where a success goes,
  stays on the screen.
- **It never fights the screen that replaced it.** Closing normally, the dialog returns focus to the
  control that opened it. When the success navigates the opener off the page, the dialog stands down
  and leaves focus wherever the new screen put it. That is one rule, derived from whether the opener
  is still in the document — not a success branch, and not a prop.

---

## 4. States

`SCREENS.md` §SETTINGS records that **a blank state is deliberately not applicable** to this screen —
a settings form is never empty. That is carried forward unchanged: this section adds no blank state
and none may be invented. It also has no loading state: it fetches nothing on mount (the address it
needs is already in the session query).

| State | Entered by | On screen | Message region |
| --- | --- | --- | --- |
| **Regular** | Any arrival at `/settings` | Title, explanation, `[ Delete my account ]`. No modal. | — (no modal) |
| **Confirming** | Activating the trigger | Modal over the page; field empty; page inert; confirm action **greyed**, `disabled`, out of the tab order | Empty |
| **Confirming — matched** | Typing the exact address | Modal over the page; field holds the typed value; confirm action now **live**, enabled, back in the tab order — the only visible difference from Confirming | Empty |
| **In flight** | Confirming with a match | Modal; the confirm action is **held** — `disabled`, reading `Deleting…`; `Cancel` absent; dismissal inert | Empty |
| **Refused (`409 last_admin`)** | The response | **Modal still open**; refusal message under the field; typed value kept; `Cancel` and the live confirm action back | Refusal copy |
| **Failed (anything else)** | The response | **Modal still open**; failure message in the same slot; typed value kept; confirm action is the retry | Failure copy |
| **Cancelled** | `Cancel`, `Escape`, backdrop click — including after a failure | Regular, exactly as before; nothing requested; the section behind is untouched | Cleared with the modal |
| **Removed** | `204` | **Not a state of this screen.** The token is dropped and `/login` renders the arrival note | — |

**`/settings` itself has three states, and only three** — regular, confirming, and gone. There is no
failed state of the *page*: every outcome of the removal renders in the modal or navigates away, so
the section never changes after first paint.

The modal's message region is **always mounted and empty when clean** — a live region that is
conditionally mounted is not announced when it appears. It is cleared when a new attempt is
confirmed — by the caller, which nulls `error` before awaiting the request (§2.5) — and by the
unmount that closing the dialog performs. Editing the field does **not** clear it: the component
owns the typed value, the caller owns the message, and neither reaches into the other.

**A re-opened dialog is always clean**, with an empty field and a held confirm action. That is not
free: the component outlives the dialog it renders, so it clears the typed value itself when it
opens (`ARCHITECTURE.md`, "the exact props"). The person types the address every time, which is
the point — a confirmation that remembers the answer to its own question is not a confirmation.

**One in-flight request, ever.** The confirm action is held for as long as the request is out, so a
double-click or a held `Enter` cannot send two deletes.

**A `401` needs no branch of its own.** The existing single-flight interceptor refreshes and retries
first; if the refresh also fails it ends the session and the app lands on `/login` **without** the
arrival note, because no deletion was confirmed here. If a `401` does reach this screen it falls into
the generic failure message like anything else (`ARCHITECTURE.md` §"The error-code read path").
Recorded so nobody wires a third path for it.

---

## 5. Keyboard, focus, and the greyed confirming action

### 5.1 Focus movement

| Event | Focus |
| --- | --- |
| Page load | `Current password` (unchanged) |
| Activate `Delete my account` | Moves into the **confirmation field** — the one thing the person must do. The dialog's name and description are announced first, from `aria-labelledby` / `aria-describedby` on the dialog element. The confirm action opens `disabled` and out of the tab order (§5.3). |
| `Tab` inside the dialog, value empty/partial/non-matching | Field → `Cancel` → back to the field. The confirm action is `disabled`, so it is **not a tab stop** — it is skipped, not merely unreachable by activation. `Shift+Tab` runs the same two stops backwards. |
| `Tab` inside the dialog, value matching | Field → `Cancel` → confirm action → back to the field. The confirm action rejoins the cycle the instant the value matches, with no other change to the trap. |
| `Tab` while in flight | The field is the only stop — `Cancel` is absent and the confirm button is `disabled` and out of the tab order for as long as the request is out, exactly as it is while the value does not match (§5.3). Focus stays inside the dialog; both stops return when the answer arrives. |
| `Cancel`, `Escape`, backdrop click | Returns to **`Delete my account`** in the section — the control that opened the dialog, exactly where the person left the page. Same after a failure: the dialog closes and focus lands on the trigger, not somewhere new. |
| `409` or any other failure | Moves to the **message region inside the dialog** (`tabIndex={-1}`, `role="alert"`), never to a control. Focus stays inside the dialog, which is still open. |
| `204` | The app navigates; `/login` moves focus to the arrival note — **and keeps it**. The dialog is never closed before the navigation, so it unmounts open, and Radix's focus restore is deferred by a timer that would otherwise fire afterwards and hand focus to a trigger that no longer exists (i.e. to `document.body`). The dialog suppresses that restore when the element that opened it is detached; on every dismissal path the trigger is still mounted, so the restore runs normally. Mechanism: `ARCHITECTURE.md` §"Focus restore on close is suppressed when the opener is gone". |

**There is no "activate the confirm action with no match" event any more.** A `disabled` button
cannot be clicked, keyed, or reached by `Tab`, so the "dead press" the earlier design routed back
to the field cannot happen — Q2 in §10 records this as dissolved, not answered, by the amendment.

The rest of the page is inert while the dialog is open — not merely visually covered. Background
controls are unreachable by `Tab` and hidden from assistive technology, so `Log out` cannot be
tabbed to from underneath. This is unchanged by a failure: the dialog stays open, so the section
behind it stays unreachable and the trigger cannot be double-fired from underneath a failure
message.

`Escape` closes the dialog in every state **except while a request is in flight**, where dismissal is
inert so the outcome has somewhere to land (§2.4); it is closable again the instant the response
arrives, failure included. The focus ring is the standard one and is never removed, on any control
here.

### 5.2 Submitting

The dialog's field and actions are a real `<form>`. `Enter` in the field submits it, which is the
same code path as activating the confirm action — including the match gate. There is no separate
key handler and no `keydown` on the field. The confirm action is the form's `type="submit"`;
`Cancel` is `type="button"` so it can never submit.

### 5.3 The confirming action is disabled until the address matches, and disabled again while a request is out

This is the rule the whole feature turns on, so it is stated exhaustively (amended 2026-08-17 —
ADR-017 §5, which reverses the always-live design this section previously specified). It turns on
**three moments**:

| Moment | The product is waiting on | The button |
| --- | --- | --- |
| Empty, partial, or a different address typed | **the person** | **Disabled.** Greyed, out of the tab order, reading `Delete my account` unchanged. Cannot be clicked, keyed, or tabbed to. |
| The typed value matches `expectedValue` | — | **Live.** Enabled, focusable, back in the tab order, full destructive treatment, unchanged label. |
| A `DELETE` is outstanding | **the server** | **Disabled again.** Reads `Deleting…`, released the moment the answer arrives. |

**Both disabled moments share one mechanism and one reason for existing, even though they answer
different questions.** The gate answers "has the person typed the right thing yet"; the hold
answers "is a request already out". Do not conflate *why* each fires, but do not invent two
different mechanisms for them either — both are the real `disabled` attribute on the same
`<button type="submit">`, derived as
`disabled={!matchesExpected(typed, expectedValue) || isSubmitting}`
(`ARCHITECTURE.md` §"`ConfirmByTyping` — the exact props").

**Why the gate uses the real `disabled` attribute, not `aria-disabled`.** `aria-disabled="true"`
would keep the button in the tab order and let a screen reader announce it as present but
unavailable — arguably a better signal for exactly the person this trade-off costs. The operator
was shown that alternative and chose the real `disabled` attribute instead: native `<button
disabled>` semantics, native click/`Enter` suppression (§2.2), and the same convention GitHub's own
type-to-confirm dialog uses. **The cost is real and it is accepted, not hidden behind a
technicality** — see "Accepted accessibility trade-off" below.

**Why both moments use the one the product already had.** `[Change password]` already carries
`disabled={isSubmitting}` (`Settings.tsx:168`) and `[Sign in]` does the same (`Login.tsx:113`); the
confirm button's in-flight state now uses the identical mechanism, and the typing gate uses it too.
`TRUTH.md`'s rule (amended 2026-08-17) states it precisely: an action a role cannot perform is
absent from the page; an action the person **is** allowed to take, but hasn't yet supplied the
required input for or whose request is outstanding, is greyed out and not clickable until it's
ready. The DMI-81 invariant test stays named `'renders nothing disabled at idle'` because it has
always been about rest, with the modal closed (`ARCHITECTURE.md` Constraint 3, amended
2026-08-17) — it says nothing about the open dialog, where this section now applies.

**Accepted accessibility trade-off (ADR-017 §5).** A real `disabled` button is removed from the
accessibility tree's tab sequence entirely — a screen reader does not find it, dimmed or otherwise,
the way it would with `aria-disabled`. A sighted person watching the button turn from grey to live
gets continuous feedback and never needs to press anything to learn where they stand. A
screen-reader user who mistypes the address tabs from the field, does not find a confirm button,
and gets no signal distinguishing "you typed it wrong" from "this dialog is broken". The operator
was shown this cost before deciding and accepted it. It is a narrow carve-out for one control — an
action the person **is** permitted to take but has not yet supplied the required input for — not a
reopening of "absent, not disabled" for role-gated actions generally.

**What a screen reader announces, verbatim in shape:**

| Moment | Announcement |
| --- | --- |
| Dialog opens | *"Delete your account?, dialog. Your account is deleted and you lose access straight away. This can't be undone. Type ana@northwind.example to confirm., edit text, blank."* — name from the heading, description from the consequence paragraph, then the focused field with its label. The confirm action is not yet in the tab sequence. |
| `Tab` from the field, value still not matching | *"Cancel, button"* — the confirm action is skipped; it is not in the tree to announce, dimmed or otherwise. **This is the accepted cost above, not a bug to fix.** |
| The typed value becomes a match while focus stays in the field | No guaranteed announcement — a screen reader does not reliably narrate a control elsewhere in the document changing state while focus is not on it. A person relying entirely on audio finds out the gate is satisfied by tabbing forward and reaching the button at all. |
| `Tab` from the field, value matching | *"Delete my account, button. Type ana@northwind.example to confirm."* — the button's `aria-describedby` points at the **same prompt element that labels the field**, so the condition is spoken every time the action is reached. No second string exists to keep in sync. |
| Activating it (only possible once matched) | *"Deleting…"* if the reader re-reads the focused button; a state change on a control the person is already standing on is **not** reliably re-announced by every screen reader, and the design does not depend on it. The outcome is what carries the news: the alert region on a failure, or the arrival note on `/login` after a success. Both take focus, so the person is never left listening to a held button for word of what happened. |
| While held, if the browser blurs the newly `disabled` button | Focus is repaired by the outcome — the failure moves focus to the message region, the success navigates and focuses the arrival note. **No state of this feature ends with focus on `document.body`.** |
| A failure arrives, matched value kept, button live again | *"Alert. You're the only admin. Make someone else an admin first, then you can leave."* — the region is `role="alert"` and pre-existing in the DOM, so filling it is announced without waiting for focus; focus then lands on that same region, so the message is not spoken twice as two different things. The action is **not** re-announced as newly enabled — it announces exactly as it did the first time it was reached matched. |
| `Tab` off the message after a failure | *"Cancel, button"*, then *"Delete my account, button. Type ana@northwind.example to confirm."* — the retry is reached in one or two keystrokes and announces exactly as it did before the failure, because the typed value that matched is still in the field. |

**A failure never changes what the action announces.** The message region carries the news; the
button keeps one accessible name across regular, matched, refused and failed states, so a
screen-reader user retrying after a `409` operates the control they already know rather than
discovering a new one called `Try again`.

**There is no "dead activation" to describe any more.** A `disabled` button cannot be clicked,
keyed, or tabbed to, so there is no non-matching press that "does nothing" — the earlier design's
entire point in this subsection. Q2 in §10 records this as dissolved by the amendment, not answered.

**The field itself** is never `readonly` and never `disabled`, in any state, in flight included —
the `disabled` attribute lives on the confirm button and on nothing else, in both of its moments.
It carries `type="text"` (not
`type="email"` — this is a confirmation token, not an address to validate, and a browser bubble
reading "please enter an email address" is noise here), `autoComplete="off"`,
`autoCapitalize="none"`, `autoCorrect="off"`, `spellCheck={false}` (`ARCHITECTURE.md`, same
section: an autofill dropdown or a helpful capitalisation would defeat the deliberate act of typing
the address), and **no `placeholder`** — the label above it is a full sentence, and a placeholder
would duplicate it and then vanish exactly when it is being used.

### 5.4 Tab order, end to end

`/settings`, in every state of the page: Current password → New password → Confirm new password →
`Change password` → `What's recorded?` → **`Delete my account`** → end of page. The section never
gains or loses a tab stop.

Inside the dialog, value not yet matching: field → `Cancel`, cycling — the confirm action is
`disabled` and not a tab stop (§5.1, §5.3). Once the typed value matches: field → `Cancel` →
confirm action, cycling. Unchanged by a failure — the message region is `tabIndex={-1}` and never a
tab stop, and no retry control is added; the matched value is still in the field, so the confirm
action is still in the cycle.

`/login` after a deletion: the arrival note holds focus on arrival but is not a tab stop; `Tab` goes
Email → Password → `Sign in` → `Forgot password?`.

---

## 6. Exact copy

Implementers invent no wording. **Every string below is verbatim from the current `SCREENS.md`
§SETTINGS and §LOGIN** — including the org-neutral explanation, which `SCREENS.md` now carries
(§0). Apostrophes are plain ASCII `'`; the dash in the section explanation is a true em dash `—`;
the ellipsis in `Deleting…` is the single character `…`, matching `Changing password…` and
`Signing in…` already in the codebase.

| Element | Copy (verbatim) |
| --- | --- |
| Section title | `Leave this organization` |
| Section explanation | `Your account is deleted and you lose access to this organization's scans, hosts and findings straight away. This can't be undone — an admin would have to invite you again.` |
| Section trigger | `Delete my account` |
| Modal message — last admin (`409 last_admin`) | `You're the only admin. Make someone else an admin first, then you can leave.` |
| Modal message — server, network, or anything else | `Couldn't delete your account.` |
| Modal heading | `Delete your account?` |
| Modal consequence | `Your account is deleted and you lose access straight away. This can't be undone.` |
| Modal prompt — also the field's label | `Type ana@northwind.example to confirm.` — the address is the signed-in member's own, from `UserProfileResponse.email`; nothing else in the sentence is variable |
| Modal confirm action | `Delete my account` |
| Modal confirm action, in flight | `Deleting…` |
| Modal cancel action | `Cancel` |
| `/login` arrival note | `Your account has been deleted.` |

> ### The pinned `[Try again]` is not a string and not a control
>
> `SCREENS.md` §SETTINGS writes the server error as *"Couldn't delete your account." · [Try again]*.
> **The bracket names the retry affordance, not a label to render.** That affordance is the confirm
> button already on screen, which stays live and keeps reading `Delete my account`. Nothing in this
> feature ever renders the words `Try again` — not in the modal, not in the section, not in a toast.
> An implementer reading the bracket literally would add a second control that
> `ARCHITECTURE.md` Constraint 4 forbids.

**Two messages, never interchanged.** The `409 last_admin` string is used **only** for
`status === 409 && code === 'last_admin'`; every other outcome uses the generic string. Telling a
sole admin the server broke, or telling everyone else to go promote a colleague, are both worse than
saying nothing. Neither string is ever shown outside the modal, and the generic one is **not** the
shared `SERVICE_ERROR` from `lib/copy.ts` — "Couldn't reach Dmitri" would misdescribe a `5xx` that
arrived perfectly well.

**Spelling is American — `organization`** — matching `SCREENS.md` §SETTINGS and the Activity note
that ships ~100px above it on the same page. Do not "correct" it to the British spelling used in
`TRUTH.md` prose and in the API descriptions; the repo's split is by register (on-screen copy is
American, contract descriptions are British) and the two strings on this page must agree.

**Copy that must not exist anywhere in this feature:** no second confirmation ("Are you sure?",
"This is permanent — confirm again"), no countdown, no "type DELETE", no checkbox acknowledgement,
no toast (both failures render in the modal; success is a navigation), no "Danger zone" heading, no
"deactivate"/"disable"/"suspend" anywhere — the product has no such state (ADR-017 §1), and no
inline hint about the address being wrong.

**Not added to `frontend/src/lib/copy.ts`.** That module holds wording shared *across screens*;
every string above appears on exactly one screen (`ARCHITECTURE.md` Constraint 6 fixes where each
one lives). The modal's strings — heading, consequence, both messages, both button labels — are
**props passed by the caller**, not constants owned by the component: that is what makes the Users
screen a zero-change second caller.

---

## 7. Data

| Consumed | Where from | Used for |
| --- | --- | --- |
| `UserProfileResponse.email` | `GET /api/v1/users/me`, already fetched by the session query and exposed as `useSession().user.email` | The address in the prompt, and the value the typed text is compared against |
| `DELETE /api/v1/users/me` → `204` | New call from this screen | Success: drop the in-memory access token, go to `/login` with the arrival state |
| `409` + `ErrorResponse.error.code === 'last_admin'` | Same route, pinned enum in the contract | The refusal message |
| `401` | Same route | No branch of its own: the interceptor refreshes and retries, and a `401` that still reaches the screen falls into the generic message (§4) |
| Anything else, including no response at all | Same route | The generic failure message |

- **No new request is made to render the section.** The address comes from the session profile the
  app already holds; there is no second `/users/me` fetch, no refetch on opening the modal, and no
  new query key.
- **No `org_name` is fetched or invented** (§0).
- **No role is read.** Both roles render identical markup, so nothing here depends on C16.
- **The refresh cookie is deliberately not cleared** (ADR-017 §6): the delete cascades the refresh
  tokens, so the residual cookie authenticates nothing and its next use is a `401`. Nothing in the
  UI acts on it.
- **Types come from `src/types/openapi.d.ts`** via `components['schemas'][...]`; no request or
  response shape is hand-written.

---

## 8. `data-testid`

Existing ids on both screens are unchanged, and **none is renamed** — `login-success` in particular
keeps its name (`ARCHITECTURE.md` file table row 5 and Constraint 10: one `role="status"` region on
LOGIN, two possible texts).

Two prefixes, because there are two owners:

- **`settings-leave-*`** — the section on `/settings`. Fixed by `ARCHITECTURE.md` row 4.
- **`confirm-by-typing-*`** — everything inside the shared modal. The dialog, its field and its
  message region belong to the component, not to this screen; DMI-90 renders the same ids at the
  second call site, so a `settings-*` id inside the component would be a lie the day Users ships.

| `data-testid` | Element | Owner | Present when |
| --- | --- | --- | --- |
| `settings-leave` | The section container — the state container for the section | Settings | Always, both roles |
| `settings-leave-body` | The explanation paragraph | Settings | Always |
| `settings-leave-trigger` | `Delete my account` in the section | Settings | **Always** — it is never replaced, removed or relabelled by any outcome |
| `confirm-by-typing-dialog` | The modal panel — the confirming state container | Component | Only while the modal is open |
| `confirm-by-typing-prompt` | The prompt sentence, which is the field's `<label>` | Component | With the dialog |
| `confirm-by-typing-input` | The typed confirmation field | Component | With the dialog |
| `confirm-by-typing-submit` | The confirming action | Component | With the dialog, in every dialog state |
| `confirm-by-typing-cancel` | `Cancel` | Component | With the dialog, **absent in flight** |
| `confirm-by-typing-error` | The single message region: `409 last_admin` copy or the generic copy, whichever the caller passed | Component | **Always mounted with the dialog**, empty when clean |
| `login-success` | The arrival note on `/login` — the existing region, carrying the deletion text | Login | On any arrival that carries a note |

**There is no `settings-leave-retry` and no `settings-leave-error`.** Both were in an earlier draft
that rendered failures on the page; the ruling moved them into the modal, and the retry is the
confirm button. An id for a `Try again` control must not reappear, because the control must not.

What the tests are expected to hang on these (stated so the ids are chosen once and not renamed
later):

- `settings-leave` renders for the admin profile **and** the viewer profile, with identical content,
  and its subtree is byte-identical between the two.
- The absent-not-disabled sweep is the house form — `queryAllByRole('button' | 'link' | 'textbox')`
  → `toBeEnabled()` and `not.toHaveAttribute('aria-disabled', 'true')`, never a
  `container.querySelectorAll('[disabled]')` (`ARCHITECTURE.md` Constraint 3). Run it on the
  section at idle — it holds there with no exception. Run it inside the open dialog too, but
  **exclude `confirm-by-typing-submit`**, which is the amendment's one named exception: at empty,
  partial and non-matching input it is legitimately `disabled`, and sweeping it along with
  everything else would assert the wrong invariant. This is precisely the scope `TRUTH.md`'s
  acceptance row now names.
- `confirm-by-typing-submit` `toBeDisabled()` at empty, partial and non-matching input, and
  `toBeEnabled()` at the exact match — its accessible name is `Delete my account` in every one of
  those states, unchanged by whether it is enabled, and it never carries `aria-disabled` (the
  mechanism is the real `disabled` attribute). **Assert the enabled/disabled split at every typed
  value, and again while a delete is outstanding** — while a delete is outstanding the button is
  legitimately `disabled` and reads `Deleting…`, exactly as `settings-submit` is while a password
  change is in flight, and it is released and re-evaluated against the still-matched field value
  when the answer arrives. A test asserting the button is always enabled, or always disabled, is
  asserting the wrong invariant.
- `confirm-by-typing-submit` cannot be activated at an empty, partial or different value — it is
  `disabled`, so no click, keypress or `Enter`-from-the-field reaches it — and **zero** requests are
  made; `confirm-by-typing-dialog` stays open.
- Once enabled, activating it with the exact value makes **exactly one** `DELETE
  /api/v1/users/me`; a double activation still makes one, because the button goes `disabled` again
  the instant the first request leaves. Case and surrounding whitespace do not defeat a correct
  address.
- `confirm-by-typing-error` is queryable in every dialog state (it is always mounted), so assert
  **text content**, not presence — a `queryByTestId` null-check would pass in every state and prove
  nothing.
- **The same failure twice announces twice.** Drive `409 last_admin`, confirm again, and take the
  same `409`: the region must empty and refill, and focus must land on it after the second attempt
  as it did after the first. This is the test that fails if the caller stops nulling `error` before
  the request, or if the component's focus effect is keyed on a value that never changes.
- After a `409 last_admin`: `confirm-by-typing-dialog` is **still open**,
  `confirm-by-typing-error` holds the refusal copy, `confirm-by-typing-input` still holds the typed
  address, `confirm-by-typing-submit` is present and enabled with an unchanged name, and
  `/settings` has not navigated. After a `500`: the same, with the generic copy. Assert the two
  strings are not interchanged by driving both branches in the same file.
- Confirming a second time after a failure sends a second request — the retry is real, not cosmetic.
- Prefer `getByRole('button', { name: 'Delete my account' })` scoped to the dialog for the confirm
  action, and to the section for the trigger, so the accessible name is asserted alongside the id.
- `login-success` holds `Your account has been deleted.` on the deletion navigation, holds the reset
  wording on a reset navigation, and there is never more than one `role="status"` region on the
  screen. After a reload of `/login` the note is **absent** — the transience is a test, not a
  comment.
- **Focus on the arrival note is asserted after timers flush, from the full path** — open the
  dialog on `/settings`, confirm, take the `204`, and assert inside a `waitFor` that the note still
  holds focus. A synchronous assertion, or one made from a `Login`-only render with no dialog in the
  tree, passes whether or not the deferred focus restore is suppressed and therefore proves nothing.


---

## 9. Out of scope — deliberate, v1

- **The Users screen and removing anybody else** (DMI-90). The dialog is built as a shared component
  with the second caller in mind, but the second caller is not written here and no `/users` route,
  link or control is added.
- **Naming the organization** — §0. No contract ask is made by this feature.
- **The profile section** (`Your details`) on Settings — still blocked by C3; no self-profile update
  operation exists. This feature does not add a stub for it.
- **A pre-refused last-admin state.** The section never renders "you can't leave" before the attempt,
  never fetches an admin count, and never hides or dims the trigger for an admin. The refusal exists
  only as an answer.
- **Undo, recovery, a grace period, a confirmation email, or any notification.** Removal is a hard
  delete (ADR-017 §1).
- **Clearing the refresh cookie** — inert after the cascade (ADR-017 §6).
- **A link from the refusal to the Users screen**, until that screen exists.
- **Any change to the password form, the Activity disclosure, the top bar, or the login form
  itself.** The only edit to `/login` is one more text for the arrival region it already has.
- **A page-level failure surface on `/settings`.** Both failures live in the modal; the section
  renders no message and no second action, in any state.
- **Mobile and tablet layouts** for the modal — desktop-only, fluid, per §Viewport.

---

## 10. Decisions and open questions

### Closed by the operator

| # | Question | Ruling |
| --- | --- | --- |
| **Q1** | The org could not be named (§0). Accept org-neutral copy, or raise a contract ask for `org_name`? | **Decided: org-neutral copy ships**, and `docs/ui/SCREENS.md` §SETTINGS has already been patched — its preamble, its copy table and its layout mockup all carry the wording in §6. No contract ask is pending. |
| **Q5** | Where does a failure render — on `/settings`, or in the modal? | **Decided: inside the modal, which stays open**, for the `409 last_admin` refusal and every other failure alike. The typed address survives, the still-live confirm button is the retry, no second control exists, and the two messages are never interchanged. `ARCHITECTURE.md` §"The error-code read path" and Constraint 4 say the same; §1, §2.5, §2.6, §3, §4, §5, §6 and §8 of this document were rewritten to match. |
| **Q6** | In flight, is the confirm button held (`disabled`) or kept live with `aria-busy` and a handler guard? An earlier draft of this document read `TRUTH.md`'s page-wide "nothing is disabled" row literally and chose the second. | **Decided: held, per `ARCHITECTURE.md` lines 300–301** — `disabled` while `isSubmitting`, reading `confirmPendingLabel`. The fault was in `TRUTH.md`'s wording, which the operator has since fixed: the invariant has always been about rest and about states the person controls, which is why the DMI-81 test is named `'renders nothing disabled at idle'` and why `[Change password]` (`Settings.tsx:168`) and `[Sign in]` (`Login.tsx:113`) already ship this way. A delete-confirm button behaving differently from the change-password button on the same screen would be an inconsistency with nothing behind it. **Superseded 2026-08-17 (ADR-017 §5):** this ruling's closing sentence — "the typing gate is untouched: empty, partial and non-matching input still render a live, enabled, focusable button" — no longer holds. The operator has since extended `disabled` to the typing gate itself, for the reasons in §5.3. |
| **Q2** | A non-matching activation moves focus back to the field so the requirement is re-announced. A stricter reading of "does nothing" would leave focus on the button and say nothing at all. Which? | **Dissolved, not answered, 2026-08-17 (ADR-017 §5).** The confirm button is now `disabled` until the address matches, so there is no dead press to recover focus from — a `disabled` button cannot be clicked, keyed, or tabbed to at all. The question presupposed a live button that could be pressed and ignored; that button no longer exists in this design. See §5.3, "There is no 'dead activation' to describe any more." |
| **Q3** | While a request is in flight, `Cancel` is absent and dismissal is inert (§2.4). Confirmed? | **Confirmed as designed.** There is nothing left to cancel, and now that the outcome renders *inside* the dialog, a mid-flight dismissal would throw away the refusal it is about to show. Both come back the instant the response arrives, so the wait is bounded by one request. |
| **Q4** | The email match is case-insensitive and whitespace-trimmed (§2.3). Confirmed against `TRUTH.md`'s word "exactly"? | **Confirmed.** It agrees with `ARCHITECTURE.md`'s `matchesExpected` (`typed.trim().toLowerCase() === expected.trim().toLowerCase()`). The account's identity in this system *is* `lower(email)`, so a case variant is the same account; the friction the gate exists to create is typing the address at all. |

### Still open — for the approval gate

**None.** Every question this document raised is closed above, including the two that were still
open as of the previous revision (Q3, Q4) and the one the 2026-08-17 amendment dissolved (Q2).

**Nothing in this design is blocked on a missing API contract.** `DELETE /api/v1/users/me` and its
pinned `409 last_admin` are published and implemented (spec 029); `UserProfileResponse.email` is
already read by the session.
