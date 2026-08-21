# DESIGN — Users & invites (`/users`)

React web screen. Copy and interaction, not pixels.

Every string here is taken **verbatim** from `docs/ui/SCREENS.md` § USERS & INVITES. Where this
document and that one disagree, `SCREENS.md` wins (`docs/ui/status.md`). §Foundations — the two
fonts, the paper/ink neutrals, the purple accent, light theme only, square components — is
**inherited, never re-decided**.

Behaviour: [`TRUTH.md`](TRUTH.md). Implementation: [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 0. What is new here

This is the product's first admin-only screen, so it is also the first place the "absent, not
disabled" rule has anything to hide. Two visual facts follow from it and drive most of section 2:

- A viewer's top bar has **no `Users` item at all** — not greyed, not present.
- The admin's **own row** is visibly inert: role is plain text, no Remove. It is the only row of its
  kind, and it is what stops an org reaching zero admins from this screen.

## 1. Screen flow

```
TopBar ──(admin only)──> /users
                           │
                           ├── [Invite a user] ──> InviteDialog
                           │                         ├─ form ──submit──> created (link + Copy link)
                           │                         │                      ├─ [Done] ──> close + refetch
                           │                         │                      └─ "Invite someone else" ──> form
                           │                         └─ error ──> inline, form stays
                           │
                           ├── Role dropdown ──> RoleChangeDialog ──confirm──> toast + refetch
                           ├── [Remove] ────────> ConfirmByTyping  ──typed+confirm──> toast + refetch
                           └── [Revoke] ────────> RevokeDialog     ──confirm──> toast + refetch

viewer ──> /users ──> RequireAdmin ──> NotFound ("That page doesn't exist.")
```

All three confirmations are modal. None of them navigates.

## 2. Visual mockups — 1440px target, 1120px table column

### 2.1 The two top bars, side by side

The whole role-gating decision, visible in one place. Left, an admin; right, a viewer.

```text
ADMIN                                        VIEWER
+---------------------------------------+   +---------------------------------------+
| DMITRI   Home  Users  Settings [Log out]|  | DMITRI   Home  Settings      [Log out] |
+---------------------------------------+   +---------------------------------------+
                  ^^^^^                                    ^
          data-testid="nav-users"              nothing here — not a gap,
                                               not a greyed item, absent
```

The viewer's bar is not the admin's bar with a disabled item. `nav-users` is not in the DOM.

### 2.2 Populated — all four row kinds

The single most important mockup: every row kind this table can produce, in one view.

```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Users  Settings                                    [Log out]  |
+==============================================================================+
|                                                                              |
|   USERS                                                                      |
|   ------------------------------------------------------------------------   |
|                                                                              |
|   PERSON             ROLE         STATUS               LAST SEEN            |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -    |
|   anna@acme.com you  Admin        Active               2 hours ago           |
|   sam@acme.com      [Viewer  v]   Active               3 days ago  [Remove]  |
|   old@acme.com      [Viewer  v]   Active         Not recorded yet  [Remove]  |
|   new@acme.com       Viewer       Invited — 2 days              —  [Revoke]  |
|                                                                              |
|                                              [ ▓   Invite a user   ]         |
+------------------------------------------------------------------------------+
```

**Five columns, four headings.** The actions sit in a fifth cell at the right of the row, whose
header is visually empty and carries screen-reader text only:

```tsx
<th><span className="sr-only">Actions</span></th>
```

The named headings stay exactly the four TRUTH rule 3 and `SCREENS.md:1139` fix — *Person · Role ·
Status · Last seen*. **One person is one `<tr>`**, so `user-row-{id}` maps to a single row and the
cells align down the page. An earlier draft of this mockup drew `[Remove]` on a second line; that
was ASCII width, not a layout, and it is corrected above.

Row by row, and why each looks the way it does:

| Row | Role cell | Last seen | Action |
|---|---|---|---|
| `anna@acme.com` — **own row** | plain text "Admin" | relative time | **none** |
| `sam@acme.com` — member | dropdown | relative time | `[Remove]` |
| `old@acme.com` — member, never recorded | dropdown | "Not recorded yet" | `[Remove]` |
| `new@acme.com` — pending invite | **plain text** | `—` | `[Revoke]` |

- The own row carries the marker "you" after the address and is the only member row with no
  dropdown and no Remove. Leaving is done in Settings.
- The pending row's role is plain text because no endpoint changes an invite's role. A dropdown
  there would be a control with nothing behind it; fixing a wrong role means Revoke, then invite
  again.
- "Not recorded yet" is a **third** distinct cell value — not "Never", which would assert the
  person is dormant when the product simply was not measuring before 2026-08-10, and not the
  pending row's `—`. Those rows sort last among members, because the server orders
  `last_seen_at DESC NULLS LAST`.

### 2.3 Loading

```text
|   USERS                                                                      |
|   ------------------------------------------------------------------------   |
|                                                                              |
|   PERSON                ROLE          STATUS                  LAST SEEN      |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -    |
|   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒        ▒▒▒▒▒▒▒                  ▒▒▒▒▒▒▒▒▒      |
|   ▒▒▒▒▒▒▒▒▒▒▒▒          ▒▒▒▒▒▒        ▒▒▒▒▒▒▒                  ▒▒▒▒▒▒▒▒▒      |
|   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒       ▒▒▒▒▒▒        ▒▒▒▒▒▒▒                  ▒▒▒▒▒▒▒▒▒      |
```

Header row and column headings are real; only the cells are skeletons. `[Invite a user]` is
**hidden while loading** — it opens a dialog that would sit over a table that is not there yet.

### 2.4 Blank — you are the only person here

```text
|   USERS                                                                      |
|   ------------------------------------------------------------------------   |
|                                                                              |
|                     You're the only person here.                             |
|                                                                              |
|                                              [ ▓   Invite a user   ]         |
```

Never truly empty — the admin reading it is in the org. The table chrome is dropped entirely
rather than showing headings over nothing, and `[Invite a user]` stays, because it is the exact
action this state calls for.

### 2.5 Error — either list failed

```text
|   USERS                                                                      |
|   ------------------------------------------------------------------------   |
|                                                                              |
|                  Couldn't load your organisation.                            |
|                        [ Try again ]                                         |
```

**No rows render, whichever list failed.** A member list quietly missing its pending invites reads
as a complete answer to "who can reach our data" while being a wrong one. `[Invite a user]` is
hidden here too: inviting into a directory you cannot see is not a coherent action.

### 2.6 Invite dialog — form

```text
        +--------------------------------------------------+
        |  INVITE A USER                                   |
        |  Create a link that lets someone join your       |
        |  organization.                          (muted)  |
        |                                                  |
        |  Email                                           |
        |  [____________________________________________]  |
        |                                                  |
        |  Role                                            |
        |    (o) Viewer — can see scans, hosts and         |
        |        findings.                                 |
        |    ( ) Admin — can also run scans and invite     |
        |        people.                                   |
        |                                                  |
        |                Cancel   [ ▓ Create invite link ] |
        +--------------------------------------------------+
```

Viewer is preselected: the safer of the two, and the common case. In flight the button reads
"Creating…".

### 2.7 Invite dialog — created (the state that matters)

```text
        +--------------------------------------------------+
        |  INVITE SENT.                                    |
        |                                                  |
        |  We emailed an invite to new@acme.com. It works  |
        |  once, and expires in 48 hours.                  |
        |                                                  |
        |  Or send them this link yourself:                |
        |  +--------------------------------------------+  |
        |  | https://app.dmitri.io/invite?token=a1b2c3… |  |
        |  +--------------------------------------------+  |
        |                                    [ Copy link ] |
        |                                                  |
        |  This is the only time you'll see this link.     |
        |  If they never get the email, copy it now.       |
        |                                         (muted)  |
        |                                                  |
        |  Invite someone else            [ ▓    Done    ] |
        +--------------------------------------------------+
```

The reason this is a modal and not an inline section: the link is shown **once**, and a modal is
the only layout that cannot scroll out of view behind a long table or be dismissed by accident.
`[Copy link]` reads "Copied" after a click. `[Done]` closes and refetches; "Invite someone else"
resets to 2.6 with an empty form, because inviting two people in a row is a real sequence.

**No toast fires here.** This dialog *is* the confirmation.

### 2.8 Invite dialog — the three errors

Inline, under the email field, form intact so the address can be corrected:

```text
|  Email                                           |
|  [sam@acme.com_______________________________]   |
|  That person is already in your organization.    |   ← 400 email_already_member
```

```text
|  [new@acme.com_______________________________]   |
|  That address already has an invite waiting.     |   ← 409 invite_already_pending
|  Revoke it first if you need to send a new one.  |
```

```text
|  Couldn't create the invite.        [ Try again ]|   ← anything else
```

The first two must never collapse into one message. They lead to different actions — "nothing to
do" versus "revoke and reissue" — and re-inviting is the likeliest thing an admin does twice on
this screen. Note the second is a **`409`**, not a `400`; branching on status alone misses it. When
an address is both, `email_already_member` wins.

### 2.9 Role change — confirm, both directions

```text
   Promoting                              Demoting
   +-------------------------------+      +-------------------------------+
   |  MAKE SAM@ACME.COM AN ADMIN?  |      |  MAKE SAM@ACME.COM A VIEWER?  |
   |                               |      |                               |
   |  They'll be able to run scans |      |  They'll only be able to see  |
   |  and invite people.           |      |  scans, hosts and findings.   |
   |                               |      |                               |
   |    Cancel   [ ▓ Change role ] |      |    Cancel   [ ▓ Change role ] |
   +-------------------------------+      +-------------------------------+
```

**No text input.** One confirming click. A role set wrong is corrected in two clicks from the same
dropdown, so typing would be out of proportion — and making it feel identical to removal would
either make removal feel routine or make role changes feel dangerous. In flight: "Changing…".
Cancelling returns the dropdown to its previous value.

### 2.10 Remove — `ConfirmByTyping`, before and after the match

```text
   Not yet matching                        Exact address typed
   +--------------------------------+      +--------------------------------+
   |  REMOVE SAM@ACME.COM?          |      |  REMOVE SAM@ACME.COM?          |
   |                                |      |                                |
   |  They lose access immediately  |      |  They lose access immediately  |
   |  and their account is deleted. |      |  and their account is deleted. |
   |  This can't be undone. You can |      |  This can't be undone. You can |
   |  invite them again later.      |      |  invite them again later.      |
   |                                |      |                                |
   |  Type their email address to   |      |  Type their email address to   |
   |  confirm.                      |      |  confirm.                      |
   |  [sam@ac__________________]    |      |  [sam@acme.com____________]    |
   |                                |      |                                |
   |   Cancel    ░░░ Remove ░░░     |      |   Cancel    [ ▓  Remove  ]     |
   +--------------------------------+      +--------------------------------+
                 ^                                        ^
      greyed, really disabled, out of        live the instant the value
      tab order, plain arrow cursor            matches (trimmed, case-insensitive)
```

The typed value is **their** address, not the admin's — the one difference from the Settings call
site. `░░░` marks a real `disabled` button, `[ ]` a live one, per §Layout conventions. This is
ADR-017 §5 as amended 2026-08-17: continuous feedback beats letting someone press a button only to
be told no.

### 2.11 Revoke — confirm

```text
   +------------------------------------------+
   |  REVOKE THE INVITE TO NEW@ACME.COM?      |
   |                                          |
   |  Their link stops working immediately.   |
   |  You can invite them again later.        |
   |                                          |
   |          Cancel      [ ▓   Revoke   ]    |
   +------------------------------------------+
```

A single click, like a role change and unlike a removal: nothing is deleted but an unused token,
the invitee has no account yet, and a new invite can be issued at once. In flight: "Revoking…".

### 2.12 The three success toasts

```text
                                    +-------------------------------------+
                                    |  sam@acme.com is now an admin.      |
                                    +-------------------------------------+

                                    +-------------------------------------+
                                    |  sam@acme.com was removed.          |
                                    +-------------------------------------+

                                    +-------------------------------------+
                                    |  The invite to new@acme.com was     |
                                    |  revoked.                           |
                                    +-------------------------------------+
```

Each names the person and what happened. Without them the only feedback is a role cell changing or
a row vanishing — easy to miss, and indistinguishable from a mis-click. Demotion reads
"sam@acme.com is now a viewer."

**Dismissal contract** — settled 2026-08-20, and binding on the shared `Toast` that Agents will
later reuse (`SCREENS.md:251`):

| Question | Answer |
|---|---|
| Duration | 5 seconds, the Radix default. Not configurable per call site. |
| By hand | Yes — a close affordance, labelled "Dismiss". |
| Two at once | **The newest replaces the one showing.** `show()` never queues and never stacks. |
| Position | Bottom-right viewport, mounted once in `AppShell`. |

One at a time, rather than the stack Radix's viewport also supports. Every action on this screen
is a modal confirmation, so two successes within five seconds needs an admin to confirm, close,
reopen and confirm again inside that window — and if they manage it, the second message is the one
worth reading. It also keeps `data-testid="toast"` **unique**, so a test asserts
`getByTestId('toast')` without reaching for `getAllByTestId`."

### 2.13 Viewer at `/users`

```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Settings                                           [Log out]  |
+==============================================================================+
|                                                                              |
|                       That page doesn't exist.                               |
|                            Go to Home                                        |
+------------------------------------------------------------------------------+
```

The existing `NotFound` page, unchanged. Not a redirect, which would silently rewrite the address
bar; not "you don't have access", which would confirm the surface exists. Same reasoning as the
backend answering `404` and never `403` for another org's resources.

## 3. Layout

- Table column: **1120px max-width**, per §Foundations for table-led screens.
- `PageHeader` ("Users") with the rule beneath it. `SCREENS.md:244` names `PageHeader` a shared
  foundation for Scans, Hosts, Agents and Users — but **Users is the first of the four to be
  built**, so the component does not exist yet and this screen creates it. Do not go looking for
  a precedent; there is none, and the other three screens will call what is written here.
- `[Invite a user]` sits **below the table, right-aligned** — the table is the page's content and
  the invite is an action on it. Present in the populated and blank states; hidden in loading and
  error.
- Row actions are right-aligned in the row's fifth cell; the role dropdown sits in the Role column,
  not with the actions.

**Carve-out from `SCREENS.md` building rule 4.** That rule reads "Whole rows are links. In every
table the entire row navigates; no trailing 'View' button column." This table does neither, and
that is deliberate rather than an oversight:

- **Nothing to navigate to.** There is no user-detail screen, and none is planned — a person here
  is four fields, all of them already on the row. A row link needs a destination that holds more
  than the row does.
- **The banned control is a redundant `View` button**, one that duplicates a navigation the row
  itself already offers. `[Remove]` and `[Revoke]` duplicate nothing; they are the only way to
  reach those actions.

Rule 4 governs tables whose rows have a destination. This one has none, so it falls outside the
rule rather than breaking it. `SCREENS.md` is left unedited.
- Long addresses truncate with an ellipsis and never widen the page (§Building rules).
- All three dialogs are the same `max-w-md` centred modal used by `ConfirmByTyping`, over a
  `bg-foreground/20` overlay.

## 4. States

| Surface | Loading | Blank | Regular | Error |
|---|---|---|---|---|
| Table | skeleton rows under real headings (2.3) | "You're the only person here." (2.4) | rows (2.2) | "Couldn't load your organisation." + Try again, **no rows** (2.5) |
| Invite dialog | button reads "Creating…" | n/a — a form is its own content | form (2.6) → created (2.7) | inline under the field (2.8) |
| Role dialog | button reads "Changing…" | n/a | 2.9 | "Couldn't change that role." + Try again |
| Remove dialog | button reads "Removing…" | n/a | 2.10 | "Couldn't remove that person." + Try again |
| Revoke dialog | button reads "Revoking…" | n/a | 2.11 | "Couldn't revoke that invite." + Try again |

## 5. Keyboard and focus

Identical for all four dialogs, following the shipped `ConfirmByTyping`:

| Moment | Behaviour |
|---|---|
| Open | Focus moves to the first interactive element — the email field (invite), the text input (remove), the confirm button (role change, revoke). |
| Escape | Closes, **except while a request is in flight**, when it is ignored. |
| Close | Focus returns to the element that opened the dialog — the row's `[Remove]`, the role dropdown, `[Invite a user]`. Never to the top of the page. |
| In flight | Cancel is unmounted rather than disabled, so the only exits are completion or failure. |
| Tab order (remove, not yet matching) | input → Cancel → *(confirm is skipped — it is disabled)* → back to input. |
| Tab order (remove, matching) | input → Cancel → Remove. |

**The accepted trade-off, recorded in ADR-017 §5:** while the typed value does not match, the
confirm button is out of the tab order. A sighted person sees the grey and reads "not yet"; a
screen-reader user who mistypes finds no confirm button and gets no equivalent signal. The operator
accepted this on 2026-08-17 in exchange for the continuous-feedback pattern. Do not "fix" it here —
it is a decision, not an oversight, and changing it means amending the ADR.

## 6. `data-testid`

| Value | On |
|---|---|
| `nav-users` | the `Users` nav item — **must be absent for viewers** |
| `users-table` | the table wrapper |
| `users-loading` | the skeleton state |
| `users-blank` | the blank state |
| `users-error` | the whole-table error |
| `users-error-retry` | its Try again |
| `user-row-{id}` | one row; `id` is `user_id` or `invite_id` |
| `user-row-self` | the caller's own row |
| `row-role-{id}` | the role dropdown's **trigger button** (Radix `Select.Trigger`) — absent on own row and invite rows. A test opens it by clicking the trigger and then the option, not with `selectOptions` |
| `row-role-text-{id}` | plain-text role (own row, invite rows) |
| `row-status-{id}` | the Status cell |
| `row-last-seen-{id}` | the Last seen cell |
| `row-remove-{id}` | `[Remove]` (absent on own row) |
| `row-revoke-{id}` | `[Revoke]` |
| `invite-open` | `[Invite a user]` |
| `invite-dialog` | the invite dialog |
| `invite-email`, `invite-role` | its fields |
| `invite-submit` | "Create invite link" |
| `invite-error` | its inline error |
| `invite-created` | the created state |
| `invite-link` | the link text |
| `invite-copy` | `[Copy link]` |
| `invite-again` | "Invite someone else" |
| `invite-done` | `[Done]` |
| `role-dialog`, `role-confirm`, `role-error` | the role-change dialog |
| `revoke-dialog`, `revoke-confirm`, `revoke-error` | the revoke dialog |
| `toast` | a raised toast |
| `confirm-by-typing-*` | reused unchanged from spec 033 — do not rename |

## 7. Out of scope — deliberate, v1

- Search, filter, sort controls, pagination. The pilot org is small enough to read.
- Bulk selection or bulk actions of any kind.
- Any greyed-out control that a **viewer** would see. If they cannot use it, it is not rendered.
- Copy for `self_target` and `last_admin` on role change — unreachable from this screen.
- Showing an invite's issuing admin, or any audit of who changed whom.
- Re-sending an invite email. Revoke and invite again is the path.
- Dark theme variants.

## 8. Decisions carried in from the grilling session

All settled by the operator on 2026-08-18 and written into `docs/ui/SCREENS.md`:

1. The no-`[disabled]` rule governs **permission, not progress**.
2. Role change: dropdown + single-click confirm. Typing is reserved for removal.
3. Revoke: single-click confirm, same reasoning.
4. No copy for the two unreachable `409`s.
5. Invite form moves into a modal, keeping both `[Done]` and "Invite someone else".
6. Viewer at `/users` gets the not-found page, via `RequireAdmin`.
7. Either list failing → whole-table error, no rows.
8. Null last-seen reads "Not recorded yet".
9. Toasts on the three row-action successes; none on invite.
10. `Toast` is built here, with three real call sites.
