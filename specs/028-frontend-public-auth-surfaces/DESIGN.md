# DESIGN — Public auth surfaces and password settings (DMI-87)

> **Layer note.** This is a React SPA design specification, so Textual “key bindings” and
> “widget ids” are expressed as keyboard/focus behaviour and stable `data-testid` values.
>
> **Authority.** This document inherits `docs/ui/SCREENS.md` §Foundations without re-deciding it.
> `docs/ui/SCREENS.md`, `docs/ui/FLOWS.md`, and `contracts/openapi/openapi.yaml` are current where
> the DMI-87 ticket is stale. In particular, invite lookup is `POST /api/v1/invites/lookup`, invite
> acceptance sends `{ token, password }`, and Accept invite has no email input. Lookup `email` is
> consumed as typed contract data but is neither rendered nor sent back on acceptance.

---

## Screen flow

```text
 /login
    │
    ├── [Forgot password?] ───────────────► /forgot-password
    │                                          │
    │                                          ├── 204 ─► confirmation (same route)
    │                                          │              │
    │                                          │              └── [Back to sign in] ─► /login
    │                                          └── request email contains
    │                                               /reset-password?token=…
    │                                                          │
    │                                  missing/dead token ──────┤
    │                                                          ▼
    │                                           /reset-password?token=…
    │                                              │          │
    │                                              │ 204      └── 410 ─► dead-link state
    │                                              ▼                         │
    │                         /login + “Password set…” ◄─────────────────────┘
    │                                                               [Request a new link]
    │                                                                    │
    │                                                                    └──► /forgot-password
    │
 emailed invite: /invite?token=…
    │
    ├── already signed in ─► signed-in block (no lookup) ─► [Sign out] ─► /login
    │
    ├── mount, anonymous ─► POST /invites/lookup
    │               ├── 200 ─► account form (Password + Confirm; no email control or text)
    │               └── 410 ─► terminal dead-invite state
    │
    └── [Create account] ─► POST /invites/accept
                                ├── 201 LoginResponse ─► authenticated HOME `/`
                                ├── 400 ─► inline policy/account error
                                └── 410 ─► terminal dead-invite state

 authenticated HOME `/`
    │
    └── [Settings] ─► /settings
                         └── [Change password] ─► 204; remain on /settings
```

Accept invite, Forgot password, and Reset password use the outside auth shell: wordmark,
`Ornament`, and one centred card in the prose column, with no navigation or log-out control.
Settings uses the inside app shell. Adding Settings makes the nav contain two items, `Home` and
`Settings`, so Foundations' transitional one-item centring ends and the nav returns beside the
wordmark. Both admin and viewer see Settings.

---

## Visual mockups

All renders target the 1440 desktop viewport. The prose column is the inherited 720 maximum and
remains fluid. State crops below a full render replace only the card or form region shown; the
surrounding shell and proportions remain unchanged.

### Accept invite — `/invite?token=…`

#### Lookup loading

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  Create your account                       │                │
│                │                                            │                │
│                │  Checking your invite…                     │ #invite-loading│
│                │  ─────────────────────────────────────     │ aria-busy=true │
│                │  ───────────────────────────               │                │
│                └────────────────────────────────────────────┘                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

The shell is available immediately, but no password form is present until lookup proves the token
is live. The loading card preserves the final title and approximate text rhythm, preventing a form
from flashing before a `410` response removes it.

#### Already signed in

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  You're already signed in.                 │ #invite-signed-in
│                │                                            │                │
│                │  Sign out first to accept this invite.     │                │
│                │                                   (muted)  │                │
│                │                                            │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │              Sign out                │  │ #invite-sign-out
│                │  └──────────────────────────────────────┘  │                │
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

Accepting an invite while signed in would replace the visitor's own session and role with the
invited account's, silently and with no way back. The lookup is not performed, so the invitation is
untouched and the emailed link still works after signing out. The signed-in account is not named:
the visitor already holds that session, and the block's job is the next step, not identification.
This block outranks every other Accept invite state except a missing token, which is dead regardless
of who is looking at it.

#### Ready / idle

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  Create your account                       │                │
│                │                                            │                │
│                │  You've been invited to Northwind Security │                │
│                │  with the viewer role. Pick a password and │                │
│                │  you're in.                       (muted)  │                │
│                │                                            │                │
│                │  Password                                  │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │ ••••••••••••                         │  │ #invite-password
│                │  └──────────────────────────────────────┘  │                │
│                │  At least 12 characters. Avoid names,      │                │
│                │  dates, and passwords you've used          │                │
│                │  elsewhere.                       (muted)  │                │
│                │                                            │                │
│                │  Confirm password                          │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │ ••••••••••••                         │  │ #invite-confirm
│                │  └──────────────────────────────────────┘  │                │
│                │                                            │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │          Create account              │  │ #invite-submit│
│                │  └──────────────────────────────────────┘  │                │
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

Lookup data establishes trust before the form through the organisation and offered role. The
lookup email is neither rendered nor sent back on acceptance. Password policy guidance sits
directly under Password, where the matching server error will appear. Confirmation is client-side
only.

#### Submitting

```text
                │  ┌──────────────────────────────────────┐  │
                │  │      Creating your account…          │  │ disabled
                │  └──────────────────────────────────────┘  │ #invite-submit
```

The values remain visible, the button becomes its progress indicator, and all submission paths are
locked until the request settles. A `201 LoginResponse` has no intermediate success card: it
establishes the session and replaces this route with Home.

#### Inline validation or acceptance error

```text
                │  Password                                  │
                │  ┌──────────────────────────────────────┐  │
                │  │ ••••••••••••                         │  │
                │  └──────────────────────────────────────┘  │
                │  That password isn't strong enough. Try a │ #invite-password-error
                │  longer one that isn't based on a name or │
                │  a date.                                  │
                │                                            │
                │  Confirm password                          │
                │  ┌──────────────────────────────────────┐  │
                │  │ ••••••••••••                         │  │
                │  └──────────────────────────────────────┘  │
                │  Those two passwords don't match.         │ #invite-confirm-error
```

Only one applicable field message is rendered at a time. A client mismatch makes no request.
`400 password_policy_violation` targets Password. `400 email_already_registered` appears as the
form-level message `That address already has an account. Sign in instead.`, with `Sign in instead.`
linking to `/login`. The form and entered values remain available.

#### Dead invite — absent token, lookup `410`, or accept `410`

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  This invite has expired.                  │ #invite-dead   │
│                │                                            │                │
│                │  Invite links can only be used once, and   │                │
│                │  they don't last long. Ask your admin to   │                │
│                │  send you a new one.              (muted)  │                │
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

All dead-token cases converge here. The password form is absent from the DOM. There is no retry or
self-service action because a fresh invitation can only come from an administrator.

#### Recoverable service failure

```text
                ┌────────────────────────────────────────────┐
                │  Couldn't reach Dmitri. Try again in a     │ #invite-error
                │  moment.                                   │
                │                                            │
                │                 [ Retry ]                   │ #invite-retry
                └────────────────────────────────────────────┘
```

A lookup failure replaces the not-yet-safe form with this retry state. The same message after an
accept request stays above the still-visible form, and the submit button is available again. No
failure is presented as a dead token unless the service returned `410 invalid_invite_token`.

### Forgot password — `/forgot-password`

#### Idle

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  Reset your password                       │                │
│                │  Enter your email and we'll send you a     │                │
│                │  link to set a new password.      (muted)  │                │
│                │                                            │                │
│                │  Email                                     │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │ ana@northwind.example                │  │ #forgot-email │
│                │  └──────────────────────────────────────┘  │                │
│                │                                            │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │          Send reset link             │  │ #forgot-submit│
│                │  └──────────────────────────────────────┘  │                │
│                │                                            │                │
│                │              Back to sign in              │ #forgot-back  │
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

The email request is the only task. The sign-in link is secondary and quiet. There is no account
existence feedback before or after submission.

#### Submitting and recoverable failure

```text
                │  ┌──────────────────────────────────────┐  │
                │  │              Sending…                │  │ disabled
                │  └──────────────────────────────────────┘  │

                │  Couldn't reach Dmitri. Try again in a     │ #forgot-error
                │  moment.                                   │
                │  ┌──────────────────────────────────────┐  │
                │  │          Send reset link             │  │ re-enabled
                │  └──────────────────────────────────────┘  │
```

Submitting prevents duplicate mail requests. Network or unexpected server failure preserves the
email and restores the same action; the error makes no claim about whether the address exists.

#### Confirmed — every `204`, known or unknown address

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  Check your email.                         │ #forgot-success
│                │                                            │                │
│                │  If ana@northwind.example has a Dmitri     │                │
│                │  account, a reset link is on its way. The  │                │
│                │  link works once and expires shortly.      │                │
│                │                                   (muted)  │                │
│                │                                            │                │
│                │              Back to sign in              │ #forgot-back  │
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

The form is replaced, not retained. The confirmation structure, wording, and timing are identical
for known and unknown addresses; only the literal address the user typed is interpolated.

### Reset password — `/reset-password?token=…`

#### Idle

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  Set a new password                        │                │
│                │                                            │                │
│                │  New password                              │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │ ••••••••••••                         │  │ #reset-password
│                │  └──────────────────────────────────────┘  │                │
│                │  At least 12 characters. Avoid names,      │                │
│                │  dates, and passwords you've used          │                │
│                │  elsewhere.                       (muted)  │                │
│                │                                            │                │
│                │  Confirm new password                      │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │ ••••••••••••                         │  │ #reset-confirm
│                │  └──────────────────────────────────────┘  │                │
│                │                                            │                │
│                │  ┌──────────────────────────────────────┐  │                │
│                │  │             Set password             │  │ #reset-submit │
│                │  └──────────────────────────────────────┘  │                │
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

The token is read from the query string and never displayed. The password and confirmation fields
are the epicenter; confirmation is omitted from the request body.

#### Submitting, inline validation, and recoverable failure

```text
                │  ┌──────────────────────────────────────┐  │
                │  │       Setting your password…         │  │ disabled
                │  └──────────────────────────────────────┘  │

                │  New password                              │
                │  ┌──────────────────────────────────────┐  │
                │  │ ••••••••••••                         │  │
                │  └──────────────────────────────────────┘  │
                │  That password isn't strong enough. Try a │ #reset-password-error
                │  longer one that isn't based on a name or │
                │  a date.                                  │

                │  Those two passwords don't match.         │ #reset-confirm-error

                │  Couldn't reach Dmitri. Try again in a     │ #reset-error
                │  moment.                                   │
```

The three lower blocks are alternatives, not simultaneous output. Mismatch is detected before any
request. A `400 password_policy_violation` remains beside New password. Network or unexpected
server failure remains form-level and preserves the values.

#### Dead reset link — missing token or `410 invalid_reset_token`

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  DMITRI                                      │
│                              ·  ·  ❦  ·  ·                                   │
│                                                                              │
│                ┌────────────────────────────────────────────┐                │
│                │  This link has expired.                    │ #reset-dead    │
│                │                                            │                │
│                │  Reset links work once and don't last      │                │
│                │  long.                            (muted)  │                │
│                │                                            │                │
│                │            Request a new link              │ #reset-request│
│                └────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

The form is absent. The link goes to `/forgot-password`. Reset has no preflight token lookup, so a
present-but-dead token can be discovered only on submit; that response still removes the form.

#### Success edge on Login

```text
                ┌────────────────────────────────────────────┐
                │  Password set. Sign in with your new       │ #login-success
                │  password.                                 │
                │                                            │
                │  Email                                     │
                │  ┌──────────────────────────────────────┐  │
                │  │                                      │  │
```

There is no reset success screen and no new session. `204` replaces the route with `/login`, where
the confirmation appears before the existing form. Refreshing Login removes the transient message.

### Settings — `/settings`

#### Idle

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ DMITRI    Home  Settings                                      [Log out]      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                SETTINGS                                                      │
│                ───────────────────────────────────────────                   │
│                                                                              │
│                Change your password                                          │
│                At least 12 characters. Avoid names, dates, and               │
│                passwords you've used elsewhere.                  (muted)     │
│                                                                              │
│                Current password                                              │
│                ┌──────────────────────────────────────────┐                  │
│                │ ••••••••••••                             │ #settings-current
│                └──────────────────────────────────────────┘                  │
│                                                                              │
│                New password                                                  │
│                ┌──────────────────────────────────────────┐                  │
│                │ ••••••••••••                             │ #settings-new   │
│                └──────────────────────────────────────────┘                  │
│                                                                              │
│                Confirm new password                                          │
│                ┌──────────────────────────────────────────┐                  │
│                │ ••••••••••••                             │ #settings-confirm
│                └──────────────────────────────────────────┘                  │
│                                                                              │
│                ┌──────────────────────────────────────────┐                  │
│                │             Change password              │ #settings-submit│
│                └──────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Settings is deliberately one finished section. The blocked profile section from the general screen
draft is not rendered. The password form uses the prose column inside the existing top-bar shell.

#### Submitting and field errors

```text
                │             Changing password…            │ disabled

                Current password
                ┌──────────────────────────────────────────┐
                │ ••••••••••••                             │
                └──────────────────────────────────────────┘
                That's not your current password.             #settings-current-error

                New password
                ┌──────────────────────────────────────────┐
                │ ••••••••••••                             │
                └──────────────────────────────────────────┘
                That password isn't strong enough. Try a      #settings-new-error
                longer one that isn't based on a name or a date.

                Those two passwords don't match.               #settings-confirm-error
```

These field errors are alternatives. A client mismatch makes no request. A
`400 wrong_current_password` targets Current password and never becomes a session-expired event. A
`400 password_policy_violation` targets New password. Settings stays open in every case.

#### Recoverable service failure and success

```text
                Couldn't reach Dmitri. Try again in a moment. #settings-error

                Password changed.                             #settings-success
```

The network/server message sits above the restored action. On `204`, all password fields are
cleared, the success line appears inline, and Settings remains open. The authenticated user and
current session remain intact.

---

## Layout and rhythm

Components render flush to their own box and carry no outer margin. Each parent screen owns every
gap around its children.

| Region | Rule |
|---|---|
| Auth frame | Outside-shell screens use the inherited fluid 720 prose-column maximum. The frame is centred with step `24` breathing room around the epicenter. Wordmark, ornament, and card are one group. |
| Auth card | `--card` ground, square edge, `--rule` hairline, step `6` internal padding. No shadow, gradient, or radius. |
| Auth vertical rhythm | Step `2` within a field group (label → control → hint/error); step `4` between form groups; step `24` around the centred epicenter. Card padding is its boundary, not sibling rhythm. |
| Settings column | Fluid 720 prose-column maximum beneath the top bar, centred with at least step `6` horizontal page padding. |
| Settings vertical rhythm | Step `2` within field and feedback groups; step `4` between related fields/actions; step `12` between page-level sections. Only the password section ships, but the page retains the section rhythm. |
| Page heading | `Settings` uses the existing page-title treatment and a quiet `--rule` separator. Auth titles sit inside their cards and use IM Fell English. IM Fell never drops below its inherited floor. |
| Inputs and buttons | Full available card/form width, square edges, `--edge` control boundary. Button width matches the field stack on auth screens; Settings uses the same calm single-column alignment. |
| Errors | Field errors occupy the field group at step `2`; form/page errors occupy their own group at step `4`. Space is reserved only while the message exists—no permanently empty error rows. |
| Long values | `org_name` and invited `email` wrap within the card; neither widens it. Tokens are never rendered. |
| Horizontal scroll | Never on the page body. These screens contain no wide region requiring an inner scroller. |

The only loud colour is the inherited `--accent` on primary actions, active Settings navigation,
and focus rings. Errors use the existing destructive token. Password success is text, not a new
green token or badge. Whitespace and proximity separate groups; no extra cards or rules are added.

---

## Keyboard and focus

| Where | Behaviour |
|---|---|
| All forms | Real `<form>` elements. Enter from any password/email field submits the owning form. During submission the action is disabled and the handler also rejects repeat submission. Escape has no special behaviour. |
| Password managers | Forgot uses `autocomplete="email"`. Invite and Reset use `autocomplete="new-password"` on both password fields. Settings uses `autocomplete="current-password"` for Current password and `autocomplete="new-password"` for both new-password fields. |
| Accept invite — signed in | The block's heading receives programmatic focus with `tabindex="-1"`; `Sign out` is the only tab stop. |
| Accept invite — loading | No interactive element receives focus while lookup is pending. The card is `aria-busy="true"`; loading completion is announced politely. |
| Accept invite — ready | Password receives focus only after a successful lookup. Tab order: Password → Confirm password → Create account. No email value or control is rendered. |
| Accept invite — errors | Mismatch focuses Confirm password; policy failure focuses Password. Already registered focuses the form-level alert, then Tab reaches `Sign in instead.` Dead invite or lookup failure focuses its heading/alert with programmatic `tabindex="-1"`; Retry is the next tab stop when present. |
| Forgot password | Email is focused on mount. Tab order: Email → Send reset link → Back to sign in. On recoverable failure focus returns to Email. On confirmation, the confirmation heading receives programmatic focus and Back to sign in is the only tab stop. |
| Reset password | With a token, New password is focused on mount. Tab order: New password → Confirm new password → Set password. Mismatch focuses Confirm; policy failure focuses New password. Missing/dead token focuses the dead-state heading; Request a new link is the only tab stop. |
| Reset success on Login | The success region receives programmatic focus after navigation, then Tab reaches the existing Login fields in their normal order. The message uses `role="status"`, not `role="alert"`. |
| Settings | Current password receives focus when the route opens. Tab order within the form: Current → New → Confirm new → Change password. Existing top-bar links and Log out remain keyboard reachable in DOM order. Wrong-current, policy, and mismatch responses focus the associated field. Success keeps focus on the submit button and is announced through `role="status"`. |
| Async failures | Field errors use `aria-describedby` and `aria-invalid`. Form/page failures use `role="alert"`. New async messages are announced without a toast and without silently replacing entered values. |
| Focus ring | Every interactive element retains the inherited visible accent focus ring. No screen removes or weakens it. |

---

## Exact copy

Dynamic examples use `Northwind Security`, `viewer`, and `ana@northwind.example`; production text
interpolates the contract values without changing the sentence.

### Accept invite

| Element | Copy |
|---|---|
| Title | `Create your account` |
| Lookup progress | `Checking your invite…` |
| Body | `You've been invited to {org_name} with the {role} role. Pick a password and you're in.` |
| Fields | `Password` / `Confirm password` |
| Policy hint | `At least 12 characters. Avoid names, dates, and passwords you've used elsewhere.` |
| Button, idle | `Create account` |
| Button, in flight | `Creating your account…` |
| Dead heading | `This invite has expired.` |
| Dead body | `Invite links can only be used once, and they don't last long. Ask your admin to send you a new one.` |
| Policy error | `That password isn't strong enough. Try a longer one that isn't based on a name or a date.` |
| Mismatch error | `Those two passwords don't match.` |
| Existing account error | `That address already has an account. Sign in instead.` |
| Recoverable service error | `Couldn't reach Dmitri. Try again in a moment.` |
| Lookup retry | `Retry` |
| Signed-in heading | `You're already signed in.` |
| Signed-in body | `Sign out first to accept this invite.` |
| Signed-in action | `Sign out` |

### Forgot password

| Element | Copy |
|---|---|
| Title | `Reset your password` |
| Body | `Enter your email and we'll send you a link to set a new password.` |
| Field | `Email` |
| Button, idle | `Send reset link` |
| Button, in flight | `Sending…` |
| Confirmation heading | `Check your email.` |
| Confirmation body | `If {email} has a Dmitri account, a reset link is on its way. The link works once and expires shortly.` |
| Link | `Back to sign in` |
| Recoverable service error | `Couldn't reach Dmitri. Try again in a moment.` |

### Reset password

| Element | Copy |
|---|---|
| Title | `Set a new password` |
| Fields | `New password` / `Confirm new password` |
| Policy hint | `At least 12 characters. Avoid names, dates, and passwords you've used elsewhere.` |
| Button, idle | `Set password` |
| Button, in flight | `Setting your password…` |
| Success on Login | `Password set. Sign in with your new password.` |
| Dead heading | `This link has expired.` |
| Dead body | `Reset links work once and don't last long.` |
| Dead action | `Request a new link` |
| Policy error | `That password isn't strong enough. Try a longer one that isn't based on a name or a date.` |
| Mismatch error | `Those two passwords don't match.` |
| Recoverable service error | `Couldn't reach Dmitri. Try again in a moment.` |

### Settings

| Element | Copy |
|---|---|
| Nav and page title | `Settings` |
| Section title | `Change your password` |
| Policy hint | `At least 12 characters. Avoid names, dates, and passwords you've used elsewhere.` |
| Fields | `Current password` / `New password` / `Confirm new password` |
| Button, idle | `Change password` |
| Button, in flight | `Changing password…` |
| Success | `Password changed.` |
| Wrong current error | `That's not your current password.` |
| Policy error | `That password isn't strong enough. Try a longer one that isn't based on a name or a date.` |
| Mismatch error | `Those two passwords don't match.` |
| Recoverable service error | `Couldn't reach Dmitri. Try again in a moment.` |

---

## Contract data

Generated `components['schemas'][…]` types are consumed directly. No handwritten request or
response shapes are introduced.

| Screen | Operation | Request fields | Success fields / effect | Designed failures |
|---|---|---|---|---|
| Accept invite | `POST /api/v1/invites/lookup` | `InviteLookupRequest`: `token` | `200 InviteLookupResponse`: `email`, `role`, `org_name`; read does not consume invite | `410 invalid_invite_token` → dead state; network/unexpected response → retry state |
| Accept invite | `POST /api/v1/invites/accept` | `AcceptInviteRequest`: `token`, `password` (`minLength: 12`) | `201 LoginResponse`: `access_token`, `token_type`, `expires_in`; refresh cookie is httpOnly; establish session and navigate `/` | `400 password_policy_violation` → Password; `400 email_already_registered` → form alert/sign-in link; `410 invalid_invite_token` → dead state |
| Forgot password | `POST /api/v1/auth/forgot-password` | `ForgotPasswordRequest`: `email` | `204`; render the identical conditional confirmation for every address | Contract exposes no address-specific failure; network/unexpected response → recoverable form error |
| Reset password | `POST /api/v1/auth/reset-password` | `ResetPasswordRequest`: `token`, `new_password` (`minLength: 12`) | `204`; no session; navigate `/login` with transient success message | `400 password_policy_violation` → New password; `410 invalid_reset_token` → dead state |
| Settings | `POST /api/v1/auth/change-password` with `FrontendBearerAuth` | `ChangePasswordRequest`: `current_password`, `new_password` (`minLength: 12`) | `204`; stay on Settings, clear fields, show inline success | `400 wrong_current_password` → Current; `400 password_policy_violation` → New; `401` is only an actual Authorization-header/session failure and follows the existing global refresh/redirect path |

`Confirm password` and `Confirm new password` are client-only values. They are never added to a
contract body. Lookup's `email` remains available in the typed response but is not rendered and
must never be added to `AcceptInviteRequest`; OpenAPI forbids extra properties.

---

## States

| Screen | State | Trigger | Render / next step |
|---|---|---|---|
| Accept invite | signed in | session status is `authenticated` | signed-in block; lookup disabled; no request, no form; `Sign out` returns to Login |
| Accept invite | lookup loading | route has token; session `booting`, or lookup pending | shell + busy loading card; no form, no request while booting |
| Accept invite | ready | lookup `200` | org and role greeting; password form; no rendered email |
| Accept invite | submitting | valid matching fields; accept pending | progress button disabled; form retained |
| Accept invite | mismatch | confirmation differs | no request; inline Confirm error |
| Accept invite | policy error | accept `400 password_policy_violation` | inline Password error; form retained |
| Accept invite | account exists | accept `400 email_already_registered` | form alert with Login link; form retained |
| Accept invite | dead | token absent, lookup `410`, or accept `410` | dead explanation; form absent; ask administrator |
| Accept invite | service error | lookup/accept network failure or unexpected `5xx` | approved error; Retry for lookup or restored submit for accept |
| Forgot password | idle | mount | email form |
| Forgot password | submitting | valid email; request pending | `Sending…`, duplicate submission blocked |
| Forgot password | service error | network/unexpected failure | form and email retained; approved error |
| Forgot password | confirmed | every `204` | form replaced by identical conditional confirmation |
| Reset password | idle | token present | new/confirm form |
| Reset password | submitting | matching values; request pending | `Setting your password…`, duplicate submission blocked |
| Reset password | mismatch | client values differ | no request; Confirm error |
| Reset password | policy error | `400 password_policy_violation` | form retained; New password error |
| Reset password | dead | token absent or `410 invalid_reset_token` | form removed; Request a new link |
| Reset password | service error | network/unexpected failure | form and values retained; approved error |
| Reset password | success | `204` | navigate Login; show transient success; no session |
| Settings | idle | authenticated admin/viewer opens route | change-password form only |
| Settings | submitting | matching values; request pending | `Changing password…`; duplicate submission blocked |
| Settings | mismatch | client new values differ | no request; Confirm new error |
| Settings | wrong current | `400 wrong_current_password` | Current error; stay authenticated on Settings |
| Settings | policy error | `400 password_policy_violation` | New error; stay on Settings |
| Settings | service error | network/unexpected failure | form retained; approved error |
| Settings | success | `204` | clear values; inline success; stay on Settings |
| Settings | session failure | genuine `401` after refresh path fails | existing session-expired behavior navigates Login |

**Message lifetime — all four forms.** Field errors, form-level errors, and success confirmations
persist while the user edits. They are cleared only at the top of the next submit, before the
request is made. Typing never dismisses a message: a screen-reader user must be able to return to
the field, re-read the error beside it, and fix it without the text evaporating under them. So the
Settings `Password changed.` line survives until the next Change password press, and a
`That's not your current password.` error survives while its field is being corrected. A submit
blocked by a client mismatch still performs this clear, then renders only the mismatch error.

Blank is deliberately not applicable to any of these four forms: each form is its own content.
Forgot's confirmed state, token-screen dead states, and Settings' success state are the meaningful
alternatives and are designed explicitly rather than manufacturing empty states.

---

## Stable `data-testid` values

Every interactive control and every materially different state container has a stable anchor.

| id | Element / assertion |
|---|---|
| `invite-signed-in` | already-signed-in block; assert form and lookup absent |
| `invite-sign-out` | Sign out action in that block |
| `invite-loading` | lookup-loading state container (`aria-busy="true"`) |
| `invite-ready` | live-invite state container |
| `invite-form` | acceptance `<form>` |
| `invite-password` | Password input |
| `invite-password-hint` | policy hint |
| `invite-password-error` | policy field error |
| `invite-confirm` | Confirm password input |
| `invite-confirm-error` | mismatch field error |
| `invite-submit` | Create account / in-flight button |
| `invite-account-error` | `email_already_registered` form alert |
| `invite-sign-in` | Sign in instead link |
| `invite-dead` | terminal dead-invite state container; assert form absent |
| `invite-error` | recoverable service-error container |
| `invite-retry` | lookup Retry button |
| `forgot-idle` | idle state container |
| `forgot-form` | forgot-password `<form>` |
| `forgot-email` | Email input |
| `forgot-submit` | Send reset link / in-flight button |
| `forgot-error` | recoverable service-error container |
| `forgot-success` | non-enumerating confirmation container; assert form absent |
| `forgot-back` | Back to sign in link, in idle or confirmed state |
| `reset-idle` | idle state container |
| `reset-form` | reset-password `<form>` |
| `reset-password` | New password input |
| `reset-password-hint` | policy hint |
| `reset-password-error` | policy field error |
| `reset-confirm` | Confirm new password input |
| `reset-confirm-error` | mismatch field error |
| `reset-submit` | Set password / in-flight button |
| `reset-error` | recoverable service-error container |
| `reset-dead` | terminal dead-link state container; assert form absent |
| `reset-request` | Request a new link |
| `login-success` | transient reset-success status above existing Login form |
| `settings-idle` | regular Settings state container |
| `settings-form` | change-password `<form>` |
| `settings-current` | Current password input |
| `settings-current-error` | wrong-current field error |
| `settings-new` | New password input |
| `settings-new-hint` | policy hint |
| `settings-new-error` | policy field error |
| `settings-confirm` | Confirm new password input |
| `settings-confirm-error` | mismatch field error |
| `settings-submit` | Change password / in-flight button |
| `settings-error` | recoverable service-error container |
| `settings-success` | inline success status |
| `nav-settings` | Settings top-bar link, present for admin and viewer |

Submitting is asserted through the existing action test id: its copy changes and it is disabled.
There is no separate hidden “loading” element for form submissions.

---

## Implementation file and naming map

This table fixes placement and exported names without prescribing implementation code.

| Path under `frontend/src` | Status | Names / responsibility |
|---|---|---|
| `App.tsx` | modify | add public routes `/invite`, `/forgot-password`, `/reset-password`; add guarded `/settings` inside `AppShell` |
| `App.test.tsx` | modify | prove all three public routes render anonymously, Settings remains guarded, and authenticated Settings access works |
| `api/auth.ts` | modify | generated-type functions `lookupInvite`, `acceptInvite`, `forgotPassword`, `resetPassword` on the bare `authClient`; acceptance stores the returned access token exactly as Login does |
| `api/passwords.ts` | new | generated-type function `changePassword` on the intercepted `apiClient` imported from `./client`, so authenticated refresh/session handling remains centralized |
| `api/authHeader.test.ts` | modify | isolated-module proof that `passwords.ts` sends Bearer through the intercepted client, guarding the required `./client` import |
| `auth/SessionProvider.tsx` | modify | expose `acceptInvitation`; after `acceptInvite`, enable/invalidate the existing session query and navigate Home without a second Login |
| `auth/SessionProvider.test.tsx` | modify | prove invite acceptance stores the token, refetches the current user, exposes the authenticated session, and replaces navigation with Home |
| `pages/AcceptInvite.tsx` | new | default component `AcceptInvite`; owns query-token read, lookup lifecycle, org/role greeting, accept form, dead/retry states; does not render lookup email |
| `pages/AcceptInvite.test.tsx` | new | lookup/accept state, no-email-input, `201` session/Home, error-code and focus coverage |
| `pages/ForgotPassword.tsx` | new | default component `ForgotPassword`; owns idle/submitting/non-enumerating confirmed states |
| `pages/ForgotPassword.test.tsx` | new | identical known/unknown confirmation and recoverable failure coverage |
| `pages/ResetPassword.tsx` | new | default component `ResetPassword`; owns token read, form/dead states, and Login success navigation state |
| `pages/ResetPassword.test.tsx` | new | missing/dead token, policy, mismatch, service failure, and no-session success coverage |
| `pages/Settings.tsx` | new | default component `Settings`; owns voluntary change-password form and inline success |
| `pages/Settings.test.tsx` | new | both-role access, wrong-current no-redirect, policy/mismatch, failure and in-place success coverage |
| `pages/Login.tsx` | modify | add `Forgot password?`; render and consume transient reset-success navigation state |
| `pages/Login.test.tsx` | modify | forgot link and reset-success message coverage |
| `components/TopBar.tsx` | modify | add `Settings` link with `nav-settings`; visible to both roles; end the one-item centring per Foundations. The bar has no `Users` link today and this feature does not add one |
| `components/TopBar.test.tsx` | modify | Settings present for admin and viewer; two-item nav arrangement |
| `test/mswHandlers.ts` | modify | deterministic handlers for all five operations and their pinned error codes |

No new shared field abstraction is required. The forms are small and their labels, error routing,
and focus rules differ enough that a configurable “universal auth form” would obscure behaviour.
Existing `AuthShell`, `Ornament`, `Button`, `Input`, and `Label` are reused without outer margins.

---

## Out of scope

- Users and invitation administration, including listing, revocation, role changes, or resending.
- Profile viewing or editing in Settings; the page ships only voluntary password change.
- MFA, session-management UI, forced or periodic password rotation.
- Password-strength meters or extra password-policy controls.
- New backend endpoints, contract changes, handwritten API types, or an email-provider UI.
- Rendering or editing the invited email, email in `AcceptInviteRequest`, or a pre-submit
  reset-token lookup.
- Changes to Login or Home beyond Forgot navigation, reset-success confirmation, and the successful
  invite/session edge to Home.
- Mobile/tablet layouts, dark mode, alternate themes, rounded cards, shadows, gradients, or new
  colour tokens.

---

## Open questions for the approval gate

1. ~~**Already-authenticated visitors on outside-shell auth routes.**~~ **✅ RESOLVED 2026-08-06 —
   guard Accept invite only.** Acceptance returns a fresh `LoginResponse` and refresh cookie, so a
   signed-in visitor who accepts is silently re-identified and possibly demoted. `/invite` therefore
   renders the signed-in block above instead of the lookup. Forgot and reset stay public and
   unguarded for every visitor: neither can swap a session, reset issues no token, and a signed-in
   user recovering a forgotten password on another device is a legitimate case.
2. **Copy not verbatim in `SCREENS.md`.** Approve the new progress strings
   `Checking your invite…` and `Changing password…`, the signed-in block's
   `You're already signed in.` / `Sign out first to accept this invite.` / `Sign out`, plus reusing
   the existing approved auth error `Couldn't reach Dmitri. Try again in a moment.` on Accept invite,
   Reset password, and Settings. Those screen sections require recoverable network/server states but
   do not supply their own final string. Implementers must not substitute alternatives after these
   extensions are approved.
3. **No contract blocker remains for DMI-87.** C13, C14, and C15 are resolved in current OpenAPI.
   Transactional email delivery is operational work outside this frontend spec, but the frontend
   contract is complete and the confirmation deliberately does not infer delivery or account
   existence from `204`.
