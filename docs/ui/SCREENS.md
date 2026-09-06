# UI Screens — Specs

> **Status:** the look is decided (2026-09-02, DMI-131) and lives in
> [`FOUNDATIONS.md`](FOUNDATIONS.md); DMI-132 implements it. The screens re-decided by that
> research — Home, Scans, Scan detail, Network, Network detail, Users — are re-specced below
> against [`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html). Settings waits on
> DMI-110.
>
> **This document is the source of truth for the *screens*.** Where it disagrees with an ADR or a
> roadmap doc, it wins and they get reconciled to it — [`ADR-008`](../adr/ADR-008-frontend-stack.md)
> owns the *stack*, [`FOUNDATIONS.md`](FOUNDATIONS.md) owns the *look*, this owns the *screens*.
> Bottom layer of the UI docs ladder: [`REFERENCE.md`](REFERENCE.md) (principles) →
> [`FLOWS.md`](FLOWS.md) (breadboards) → **SCREENS.md** (layouts, states, copy). A screen section
> may only be written after its flow is locked in FLOWS.md, and each section is filled **top to
> bottom** — the template order is the method: epicenter first, chrome last
> ([`REFERENCE.md`](REFERENCE.md) §2, §5, §6, §7).

## Foundations

**Moved to [`FOUNDATIONS.md`](FOUNDATIONS.md)** (binding, 2026-09-02). Theme, type, colour,
spacing, radius, containers, interaction states, motion, icons, chrome and navigation, table
rules, cards, pagination and the copy rules all live there; the retired values and the reasoning
behind them live in [`FOUNDATIONS-DECISIONS.md`](FOUNDATIONS-DECISIONS.md).

A screen spec may not re-decide any of it. **Where this document disagrees with
`FOUNDATIONS.md`, `FOUNDATIONS.md` wins**, and this document gets corrected.

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
| Scans | `/scans` | inside | admin, viewer | B3 | ◐ built (DMI-88) |
| Scan detail | `/scans/:scanId` | inside | admin, viewer | B3, B4 | ◐ built (DMI-88; C10 resolved) |
| Network (was Host inventory) | `/hosts` | inside | admin, viewer | B3 | ◐ built (DMI-88) |
| Network detail (was Host detail) | `/hosts/:hostId` | inside | admin, viewer | B3 | ◐ built (DMI-88; C11 resolved — `?host_id=`) |
| Devices (was Agents) | `/agents` | inside | admin, viewer (ro) | B4 | ✅ built (DMI-89) — scan trigger, subnet chooser, command poll |
| Users & invites | `/users` | inside | admin | B2 | ◐ API ready (C4 closed); frontend screen not built |
| Settings | `/settings` | inside | admin, viewer | B5 | ◐ details (read-only), password modal, activity disclosure and removal built; profile **editing** pending on C3 |

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

- **Frame:** wordmark, then a single centered card in the **`--container-form` column
  (384px)** ([`FOUNDATIONS.md`](FOUNDATIONS.md) §Containers). The card is the page; there is no other content — and
  because there is no other content, the card sizes to the form rather than to the viewport. It
  is a portrait card, taller than it is wide, and it stays 384px on the longer screens (Accept
  invite, Reset password), which simply grow downward. It was briefly 720px, which read as a
  letterbox band around 336px of inputs; that is the defect [`FOUNDATIONS.md`](FOUNDATIONS.md) §Containers exists to
  prevent. *Corrected 2026-08-18 (DMI-107).*
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
disabled" decision in this product — the `Users` nav item, `[Scan now]`, the invite form —
depends on knowing whether this user is an `admin` or a `viewer`.
[`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis says the role arrives **in the JWT claims**,
but the contract documents no claims at all. The frontend would be decoding an undocumented payload
to decide what to render.

**Three states:**
- **Regular:** the form.
- **Blank:** **not applicable.** A login form is never empty — it is its own content. Recorded so
  nobody invents an empty state to satisfy the three-states rule.
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
| Title | "Sign in" |
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
|                              D M I T R I                                     |
|                                                                              |
|              +------------------------------------------+                    |
|              |  SIGN IN                                   |                    |
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

**Home is the work board.** Not a metrics dashboard and not a scan launcher: what needs review,
what changed, what happened. *Re-specced 2026-09-02 against
[`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html); the earlier verdict-line
screen is withdrawn.*

**Epicenter** — the **attention table**: the vulnerabilities waiting to be reviewed, worst first,
each row clicking through to where it is dealt with.

**Data** — endpoints and fields consumed (contract names):
- `GET /api/v1/scans?per_page=1` (default sort `timestamp` desc) — the latest scan feeds the
  scan-failed event and the last-scan facts (`timestamp`, `host_count`, `finding_count`,
  `highest_severity`, `scan_mode`)
- `GET /api/v1/findings?scan_id={latest}` — the attention table's rows (`title`, `cve_id`, `ip`,
  `severity`)
- `GET /api/v1/agents/{agent_id}` — `online`, `last_seen_at`, `display_name` feed the
  device-silent event

**Layout — three regions, top to bottom:**

1. **Page title.** It carries the state of the board; there is **no "To review" heading**.
2. **The attention board** — a `DataTable` of vulnerabilities, fixed 56px rows, whole row
   navigates to the vulnerability's scan detail. The board has a **fixed height**, so its empty
   state does not shift what is below it.
3. **Step 12 (48px)**, then a **half/half split**: on the left an **event board** (paginated) of
   small-scoped events; on the right a **minimal log panel** with a title. Neither panel renders a
   trailing empty row.

**Three states:**
- **Regular:** the attention table with rows, the event board, the logs.
- **Blank (nothing needs review):** **nothing is rendered in the attention board at all** — no
  text, no empty card. The canvas shows through and the **page title carries the message**. This
  overrides the usual one-sentence-plus-button empty state, for this surface only.
- **First run (no scan has ever happened):** the onboarding case of B2 — one sentence and one
  button for an admin; a viewer gets the sentence and no button (absent, not disabled).
- **Error:** page-level copy + `[Retry]`. Never a skeleton standing in for the board.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title — nothing to review | "Nothing needs your attention." |
| Page title — items pending | "2 things need your review." |
| Attention columns | "Vulnerability · Device · Port · CVE · Severity" |
| Event — device silent | "The Pi hasn't been seen since Tuesday. It's likely dead — check on it." |
| Event — scan failed | "Last night's scan didn't finish." |
| Event board title | "Events" |
| Log panel title | "Activity" |
| First run — heading | "No scans yet." |
| First run — CTA (admin only) | "Run first scan" |
| First run — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the review." · [Retry] |

**Never certify safety.** The all-clear title is *"Nothing needs your attention."* — never *"Your
network is safe."*

**Open questions:**
1. The event board's use cases are still being collected. Owned by **DMI-117 / DMI-123**; noted
   for **DMI-127**.
2. Coverage-stale threshold: the Pi's `online: false` is immediate, but "no completed scan in N
   days" still needs an N.

---

### SCANS

**Route:** `/scans` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — the run log: every scan, newest first, each answering *did it work, and did it
find anything*. This is honestly a table and it looks like one. *Re-specced 2026-09-02 against
[`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html).*

**Data:**
- `GET /api/v1/scans?page&per_page=20&sort_by=timestamp&sort_order=desc` → `ScanListResponse`
  (`data: ScanSummary[]`, `total`, `page`). Server-driven sorting and pagination; **no
  client-side sorting.**
- `ScanSummary`: `scan_id`, `timestamp`, `subnet`, `scan_mode`, `status`, `host_count`,
  `finding_count`, `highest_severity` (nullable).
- `POST /api/v1/agents/{agent_id}/commands` — `[Scan now]`, admin only, with the currently
  selected scan type.

`ScanStatus` is `pending | accepted | processing | completed | failed`. A scan triggered here
appears as `pending` **immediately** (the stub row is created at enqueue,
[`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-)), so this list is live during a
scan and must not look broken while a row is unfinished.

**Mode is a column, not a control.** The mode switcher above the table is cut. Filters stay cut
from v1 ([`IDEAS.md`](IDEAS.md) → Scans).

**Two regions:**

1. **The scans table.** Fixed 56px rows, whole row navigates. Pagination below it.
2. **The Scan settings section**, below the table — the tabs-and-description pattern in
   [`FOUNDATIONS.md`](FOUNDATIONS.md) §Scan settings pattern, with `[Use this scan type]` and
   `[Scan now]` beside it. `[Scan now]` is **admin only** and is absent for a viewer.

**Three states:**
- **Regular:** one row per scan. An unfinished scan shows its status instead of counts.
- **Blank:** no scans ever. One sentence and, for an admin, `[Scan now]`; a viewer gets the
  sentence alone. Scan settings still renders — it explains what a scan is.
- **Error:** page-level copy + `[Retry]`. `LoadingSkeleton` for the table body on first load only.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Scans" |
| Columns | "When · Type · Status · Devices · Vulnerabilities · Highest severity" |
| Status — completed | "Completed" |
| Status — pending/accepted/processing | "Running…" |
| Status — failed | "Failed" |
| Vulnerabilities cell — zero | "None" |
| Highest severity — null on a completed scan | "—" |
| Scan settings — section title | "Scan settings" |
| Scan settings — tabs | "Quick · Standard · Extensive · Max · NSPi" |
| Scan settings — descriptions | the five lines in [`FOUNDATIONS.md`](FOUNDATIONS.md), verbatim |
| Scan settings — set default | "Use this scan type" |
| Scan settings — confirm | "Make Max your daily scan? Every morning's scan will take 45 minutes or more instead of about 8 minutes." |
| Run once (admin only) | "Scan now" |
| Blank — heading | "No scans yet." |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the scans." · [Retry] |

**Open questions:** none. Scan-type switching and per-device scans are **DMI-127** and future
work respectively.

---

### SCAN DETAIL

**Route:** `/scans/:scanId` · optional `?finding=:findingId` (deep link from Home, B3) ·
**Shell:** inside · **Roles:** admin, viewer · **Flow:** B3, B4

**Epicenter** — the vulnerabilities ([`REFERENCE.md`](REFERENCE.md) §2). Devices are context.
*Re-specced 2026-09-02 against
[`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html).*

**Data:**
- `GET /api/v1/scans/{scan_id}` → `ScanDetailResponse` — **one request, everything embedded**:
  `findings: FindingRecord[]`, `hosts: ScanHostView[]`, `timestamp`, `subnet`, `scan_mode`,
  `status`, `host_count`, `finding_count`, `command_id` (nullable), `error_code`
  (`ScanErrorCode | null`).
- **No `GET /findings` call here.** `FindingRecord` arrives complete — `severity`, `title`,
  `description`, `recommendation`, `evidence`, `references`, `cve_id`, `cvss_score`, `host_ip`,
  `port`, `protocol`, `service`. Opening one is **local state**.
- **Failure reason:** on `status: failed`, `error_code` is on this same body. Map it through
  `scanFailureReason()` in `frontend/src/lib/scanFailureReasons.ts`. Do not fetch
  `GET /commands/{id}` for the sentence.

**Layout — top to bottom:**

1. **Back link**, then the page title.
2. **Summary strip** — the key/value facts (when · type · subnet · devices · vulnerabilities),
   **aligned to the width of the table below it**.
3. **Vulnerabilities, grouped by severity.** Each group — `Critical`, `High`, `Medium`, `Low` —
   is **one white card on the canvas with its plain heading inside the card**. The card never
   varies with severity. A row expands its panel **in place**; it does not navigate.
4. **The devices-seen table.**

**Three states:**
- **Regular:** as above, groups ordered critical → low; empty groups are not rendered.
- **Regular, no vulnerabilities (the good day):** the section says so in words and the devices
  table carries the page.
- **Regular, unfinished:** `pending`/`accepted`/`processing`. The page says the scan is running
  and does **not** poll; the cache is invalidated when the command completes. It never renders an
  empty vulnerabilities section as though the answer were "nothing".
- **Regular, failed:** the failure **is** the content. Show the reason and the next step; suppress
  the empty tables entirely.
- **Error:** page-level copy + `[Retry]`. 404 gets its own line.

**Deep link:** `?finding=:findingId` — match the id in the already-loaded `findings`, scroll to
that row, open its panel. Absent or unmatched → render normally. No extra fetch (B3).

**Copy:**
| Element | Copy |
| --- | --- |
| Back link | "Back" (Lucide `arrow-left`) |
| Page title | "Scan — yesterday 21:40" |
| Summary strip | "quick · 192.168.0.0/24 · 12 devices · 3 vulnerabilities" |
| Group headings | "Critical" / "High" / "Medium" / "Low" — bold ink, no colour |
| Vulnerability columns | "Vulnerability · Device · Port · CVE · Severity" |
| No vulnerabilities | "No vulnerabilities. Every device in this scan came back clean." |
| Panel — labels | "What it is" / "What to do" / "Evidence" / "References" |
| Panel — CVSS | "CVSS 9.8" |
| Devices section title | "Devices in this scan" |
| Devices columns | "Device · IP · MAC · Vendor · Services" |
| Unfinished | "This scan is still running." · "Vulnerabilities appear here when it finishes." |
| Failed | "This scan didn't finish." · the plain-language reason · [Try another scan] (admin only) |
| Failed, no `command_id` | "This scan didn't finish. No reason was recorded." |
| Error | "Couldn't load this scan." · [Retry] |
| 404 | "That scan doesn't exist." · [Back to scans] |

**`Port` and `CVE` sit no closer than step 6 (24px)**, from fixed column widths.

**Open questions:** none.

---

### NETWORK

**Route:** `/hosts` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

The nav item and the page title are **Network** — the screen shows the client's network. The
route is unchanged. *Re-specced 2026-09-02 against
[`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html), approved as drawn.*

**Epicenter** — the table of devices on the network: what is out there, and does any of it need
attention.

**Data:**
- `GET /api/v1/hosts?page&per_page=20` → `HostListResponse` (`data: HostSummary[]`, `total`,
  `page`).
- `HostSummary`: `host_id`, `ip`, `mac` (nullable), `hostname`, `vendor`, `first_seen_at`,
  `last_seen_at`, `open_ports_count`, `highest_severity` (nullable).

**Sorted by severity, then name.** Silent devices sort last regardless (see below). Sorting is
server-driven.

**Above the table:** a **search input** and a **ghost filter select**. These are approved on the
mockup; the contract's free-text `q` parameter is what search consumes when it is implemented.

**Devices are cumulative, not per-scan** — this is everything ever discovered, which is why a
machine that has gone away still appears.

**`mac` can be null** — a device discovered across a router has no ARP entry. The cell renders
"—" rather than being hidden.

**Silent devices** follow the `DataTable` pattern in [`FOUNDATIONS.md`](FOUNDATIONS.md) §Tables: a
muted row with a **"Not seen for N weeks"** second line, and those rows also collapse into a
**"Not seen recently (N)"** group row at the bottom of the table.

**Three states:**
- **Regular:** one row per device, fixed 56px rows, whole row navigates to `/hosts/:hostId`.
- **Blank:** no scan has ever run. One sentence, and `[Scan now]` on Scans for an admin.
- **Error:** page-level copy + `[Retry]`.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Network" |
| Search placeholder | "Search devices" |
| Columns | "Device · IP · MAC · Vendor · Services · Highest severity · Last seen" |
| Hostname missing | "(unnamed)" |
| MAC — null | "—" |
| Highest severity — null | "—" |
| Silent device second line | "Not seen for 6 weeks" |
| Silent device group row | "Not seen recently (3)" |
| Blank — heading | "No devices yet." |
| Blank — body | "Once a scan runs, every device on your network shows up here." |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load your network." · [Retry] |

**Open questions:**
1. **Device naming fallback** when no name is found — hostname → vendor + address → address?
   Open; belongs to this screen's issue.

---

### NETWORK DETAIL

**Route:** `/hosts/:hostId` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — what this device exposes and what is wrong with it. *Re-specced 2026-09-02
against [`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html).*

**Data:**
- `GET /api/v1/hosts/{host_id}` → `HostDetailResponse`: `ip`, `mac` (nullable), `hostname`,
  `vendor`, `first_seen_at`, `last_seen_at`, `open_ports_count`, `highest_severity`,
  `ports: Port[]`, `scan_history: HostScanHistoryEntry[]`.
- `Port`: `port`, `protocol`, `state`, `service`, `version` (nullable).
- `HostScanHistoryEntry`: `scan_id`, `timestamp`, `scan_mode`, `open_ports_count`,
  `highest_severity`.
- **Vulnerabilities are a second call:** `GET /api/v1/findings?host_id={host_id}` →
  `FindingRecord[]`, rendered with the same row + in-place panel as SCAN DETAIL.

**Layout — header → vulnerabilities → services → scan history.** Vulnerabilities come **before**
services; that ordering is decided, not a preference. The header shows the device name as the
title, with address and vendor secondary; **when the device has no name, the address is the
title**.

Each section is a **white card on the canvas with its heading inside**.

**Three states:**
- **Regular:** as above. Scan-history rows navigate to `/scans/:scanId`.
- **Blank:** not reachable — a device exists only because a scan found it. A device with nothing
  exposed is the nearest thing, and it gets positive framing rather than an empty table.
- **Error:** page-level copy + `[Retry]`; 404 its own line.

**Copy:**
| Element | Copy |
| --- | --- |
| Back link | "Back" (Lucide `arrow-left`) |
| Page title | "synology-nas" — or the IP when `hostname` is empty |
| Header line | "192.168.0.42 · 00:11:32:AA:BB:CC · Synology" |
| Seen line | "First seen Jul 3 · last seen 2 min ago" |
| Vulnerabilities section title | "Vulnerabilities" |
| No vulnerabilities | "No vulnerabilities on this device." |
| Services section title | 🔓 **open** — a plain phrase about the services running on this device. The word *ports* is retired; the exact wording is the one item still open in [`FOUNDATIONS.md`](FOUNDATIONS.md) §Copy rules & vocabulary |
| Services columns | "Port · Protocol · Service · Version" |
| Nothing exposed | "Nothing is exposed on this device." |
| Version missing | "—" |
| Scan-history section title | 🔓 **open** — *"Seen in these scans"* is rejected and has no replacement yet (same open item) |
| Scan-history columns | "When · Type · Services · Highest severity" |
| Error | "Couldn't load this device." · [Retry] |
| 404 | "That device doesn't exist." · [Back to Network] |

**Open questions:**
1. The two section headings above. Blocked on the one open Foundations item, not on a contract.

---

### DEVICES

**Route:** `/agents` · **Shell:** inside · **Roles:** admin, viewer (read-only) ·
**Flow:** B4, and the first-run step of B2

> **Decided 2026-09-02 (DMI-131):** the nav item and page title are **Devices** — a device is the
> Dmitri box running inside a network. The route is unchanged. The **manual scan trigger moved to
> the Scans page as `[Scan now]`**, beside the scan settings, because that is where the type is
> chosen; this screen keeps **device management only**. A **per-device start scan is future work**,
> not part of the revamp. The `[Scan now]` references below are the built behaviour and are
> superseded by SCANS on that point. Everything else here — provisioning states, the network
> chooser, the command lifecycle — stands, restyled to [`FOUNDATIONS.md`](FOUNDATIONS.md).

**Epicenter** — *can I scan right now?* The device's live state and the network it targets
([`REFERENCE.md`](REFERENCE.md) §2). Everything else on this page is caption.

**Data:**
- `GET /api/v1/agents` → the row. **✅ C1 shipped (DMI-78).** One agent in the MVP; the list is how
  the frontend discovers `agent_id`.
- `GET /api/v1/agents/{agent_id}` → `AgentDetail`: `display_name`, `online`, `last_seen_at`,
  `active_command_id`, `available_subnets`, `target_subnet`. **Read on mount** — this is what lets a
  running scan's pill survive navigation and reload (B4). **✅ C2 shipped (DMI-78).**
- `PATCH /api/v1/agents/{agent_id}` → `AgentDetail`, admin only. Body `{ target_subnet }`, one of
  the CIDRs `available_subnets` reported. The response is the full detail, so the screen needs no
  refetch. `409 device_offline` if the Pi is reporting nothing; `422 subnet_not_reported` if the
  chosen network is not one it reported.
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
- **Expired.** The Pi **never took the command** — there was no open socket, or the one send
  attempt threw. Distinct from
  `failed` — the operator's next step is *check the box*, not *try again* — so it points at the Pi and
  offers `[Retry]` second.
- **Offline.** `online: false`. `[Scan now]` **stays visible and enabled** — see Open questions.
- **Viewer.** Sees the row, the status and the network. No `[Scan now]`, no network chooser —
  omitted, not disabled (absent, not disabled).
- **Error.** Page-level copy + `[Retry]`.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Devices" |
| Subtitle | "The Dmitri box on your network." |
| Row — online | "Online · last seen 2 min ago" |
| Row — offline | "Offline · last seen Tuesday 14:10" |
| Row — network | "Scanning: Ethernet · 192.168.0.0/24" · [Change] |
| Trigger | "Scan now" |
| Needs-network heading | "Which network should Dmitri scan?" |
| Needs-network body | "This box is connected to more than one network. Pick the one you want scanned — usually the office network, not the internet connection." |
| Needs-network options | "Ethernet · 192.168.0.0/24" / "Wi-Fi · 10.12.0.0/16 (internet connection)" — **derived** from reported `interface` by prefix (`eth*`/`en*` → Ethernet, `wl*` → Wi-Fi; unfamiliar names render raw) |
| Needs-network confirm | "Set this Network" |
| Pill — queued | "Queued" |
| Pill — delivered | "Sent to the Pi" |
| Pill — running | "Scanning…" |
| Pill — uploading | "Uploading results…" |
| Pill — done | "View scan" |
| Pill — failed | "Scan failed" pill + operator sentence from `scanFailureReason(error_code)` (not the raw code) · [Retry] |
| Pill — expired | "Not picked up" pill + "The Pi never picked up the scan. Check that it's powered on and connected to the network." · [Retry] |
| Hint under trigger | "A scan usually takes about 10 minutes." |
| Toast — 503 `device_offline` | "Pi seems to be offline." |
| Toast — 409 `device_busy` | "That Pi is already scanning. Showing the scan in progress." — only when the Pi's run is actually adopted |
| Toast — any other refused trigger | "Couldn't start the scan." — including a busy Pi that reports no run to adopt |
| Blank — heading | "No Pi connected yet." |
| Blank — body | "Dmitri scans your network from a small box installed on site. Your installer sets it up — once it's online, it shows up here and you can run your first scan." |
| Blank — viewer/admin line | "Contact whoever installed Dmitri if you were expecting to see one." |
| Error | "Couldn't load the agents." · [Retry] |

**Layout:**

Ready — admin:
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Network  Devices  Users  Settings      [Log out]     |
+==============================================================================+
|                                                                              |
|   DEVICES                                                                    |
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
|   |                                   [ Set this Network ]         |        |
|   +----------------------------------------------------------------+        |
```

Scanning:
```text
|   |  DMITRI-NSPI-01          Online · last seen 4 s ago             |        |
|   |  Scanning: Ethernet · 192.168.0.0/24                            |        |
|   |                                         [ ▓ Scanning… ]         |        |
```

**Open questions:**
1. ~~**Offline: keep `[Scan now]` or hide it?**~~ **✅ RESOLVED — keep visible and enabled** (shipped DMI-89). `online` is
   derived from the WebSocket registry and can be momentarily stale. The backend makes **one**
   delivery attempt and does not retry ([`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-)),
   which makes keeping the button live *more* important, not less: **the operator clicking again
   is the only retry the system has.** Hiding the button on a flag that might be wrong denies a
   scan that would have worked; the `503` toast is the designed, honest failure. **This is not the absent-not-disabled rule** — that rule is about what a *role*
   may do, not what is momentarily unavailable.
2. ~~**C12 — does a dead Pi produce `failed` or `expired`?**~~ **✅ RESOLVED 2026-07-13 — the split is
   `delivered_at`.** Never delivered → `expired`; delivered then broke → `failed`. The screen knows
   which it gets: **a Pi that dies mid-scan is `failed`** (it took the job), and `expired` is only
   *never picked up*. Pill copy updated accordingly.
3. Pill vs stepper for the five lifecycle states — pill chosen; stepper parked
   ([`IDEAS.md`](IDEAS.md) → Agents & Scan now).
4. ~~Blocked on **C1** and **C2**.~~ **✅ Unblocked and built** — DMI-78 (contract) + DMI-89 (SPA).

---

### USERS

**Route:** `/users` · **Shell:** inside · **Roles:** admin only · **Flow:** B2

*Re-specced 2026-09-02 against
[`mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html). Built 2026-08-21 (spec 034);
what follows is the approved shape, not a build plan.*

**Epicenter** — **the table is the page**: everyone with access, members and pending invites in
one list. Inviting is a function of the screen, not its focus.

**No count line and no helper copy.** The old *"Create a link that lets someone join your
organization."* subtitle and the per-role explanations under the role control are **deleted, not
reworded**.

**A viewer reaching `/users` directly gets the not-found page.** Two primitives, because hiding a
nav item and refusing a route are different jobs: `AdminOnly` renders `null` for viewers (it hides
the nav item), and `RequireAdmin` is an outlet guard that renders the existing `NotFound` page.
Not-found rather than access-denied, for the same reason the backend answers `404` and never `403`
for another org's resources. Neither primitive takes a `fallback` or `disabled` prop, so a
greyed-out admin control cannot be produced.

**Data:**
- `GET /api/v1/users` → `OrgMember[]` (`user_id`, `email`, `role`, `last_seen_at`) and
  `GET /api/v1/invites` → pending invites. **Two calls, one table.** Members first in the order
  the endpoint returns them (`last_seen_at` desc, nulls last), then pending invites,
  soonest-to-expire first. They are not interleaved: a pending row has no `last_seen_at` to sort
  by. **If either call fails the whole table shows its error state** — this table means *everyone
  with access*, and a member list silently missing its invites is a wrong answer, not a partial
  one.
- **There is no `status` field on the wire.** Status is derived from which endpoint the row came
  from.
- `POST /api/v1/invites` — body `{ email, role }` → `201 InviteCreatedResponse`
  `{ invite_token, expires_at }`. The backend emails the link; the screen also shows it.
- `PATCH /api/v1/users/{user_id}` — role change. Refuses to target the caller: **self-demotion is
  not possible.**
- `DELETE /api/v1/users/{user_id}` — admin-only **hard delete**
  ([`ADR-017`](../adr/ADR-017-account-removal.md)). It refuses to target the caller; `/users/me` is
  the self-service path and lives in SETTINGS. Between the two refusals an org can never reach
  zero admins.
- **Mutations refetch; they do not patch the cache by hand.** No optimistic update — these are
  admin writes on a small table where a wrong guess briefly shows a false membership fact.

**Layout:**

1. **Page title**, then the table. Fixed 56px rows.
2. **The role cell is an inline select** — shadcn `Select` with a **ghost, borderless trigger**,
   the text plus a small chevron close to it, **aligned with the column header**. It appears on
   other members' rows only; your own row and pending invite rows render the role as plain text.
3. **Every row carries a `Remove` action** — a **text link in the row plus a confirm dialog**,
   never a bare icon button. Admins may remove viewers **and other admins**; your own row carries
   none (leaving is done in Settings). Pending rows carry `Revoke` instead.
4. **`[Invite a user]` sits under the table at the right edge**, ~5% taller than the default
   control. It opens a dialog: the email + role form, replaced in place by the confirmation
   carrying the link and `[Copy link]`. A modal is the only layout the once-only link cannot
   scroll out of.

**Two weights of confirmation.** Removal makes the admin type the target's address
([`ADR-017`](../adr/ADR-017-account-removal.md) §5, `ConfirmByTyping`); a role change and a revoke
ask a plain question with a single confirm button. **Typing is reserved for what cannot be
undone** — a role set wrong is corrected in two clicks; an invite revoked is reissued in one.

**Three row actions raise a toast; the invite does not.** Role change, remove and revoke each take
effect in a table the admin is already looking at, and a row quietly changing is easy to miss. The
invite's dialog already *is* its confirmation.

**Email is the convenience; the link is the guarantee.** A security product's one-time login link
is structurally indistinguishable from phishing and will sometimes land in spam, so the admin gets
a recovery that does not depend on the thing that just failed. With no way to re-read a token, the
once-only nudge stays.

**Three states:**
- **Regular:** the table.
- **Blank:** never truly empty — the admin reading it is in it.
- **Error:** the table's own error state, both calls treated as one unit; the same goes for its
  loading skeleton.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Users" |
| Table columns | "Person · Role · Status · Last seen" |
| Active row | "Active" · "2 hours ago" · [Remove] |
| Active row, no last-seen value | "Not recorded yet" — **not** "Never", and not the pending row's `—` |
| Pending row | "Invited — expires in 2 days" · "—" · [Revoke] |
| Own row | No "you" marker, no Remove, no role control. The absent controls identify the row |
| Blank table | "You're the only person here." |
| Table — load error | "Couldn't load your organisation." · [Try again] |
| Role control | "Viewer" / "Admin" |
| Screen action | "Invite a user" |
| Invite fields | "Email" / "Role" |
| Invite button | "Create invite link" · in flight: "Creating…" |
| Created — heading | "Invite sent." |
| Created — body | "We emailed an invite to **name@example.com**. It works once, and expires **in 48 hours**." |
| Created — link label | "Or send them this link yourself:" |
| Created — nudge | "This is the only time you'll see this link. If they never get the email, copy it now." |
| Created — copy button | "Copy link" · after click: "Copied" |
| Created — again | "Invite someone else" |
| Created — dismiss | "Done" — closes the dialog and refetches the table |
| Error — bad email | "That doesn't look like an email address." |
| Error — already a member (`400 email_already_member`) | "That person is already in your organization." |
| Error — already invited (`409 invite_already_pending`) | "That address already has an invite waiting. Revoke it first if you need to send a new one." |
| Error — server | "Couldn't create the invite." · [Try again] |
| Role change — confirm heading | "Make **name@example.com** an admin?" · demoting: "Make **name@example.com** a viewer?" |
| Role change — confirm body (to admin) | "They'll be able to run scans and invite people." |
| Role change — confirm body (to viewer) | "They'll only be able to see scans and your network." |
| Role change — confirm button | "Change role" · in flight: "Changing…" |
| Role change — error | "Couldn't change that role." · [Try again] |
| Remove — confirm heading | "Remove name@example.com?" |
| Remove — confirm body | "They lose access immediately and their account is deleted. This can't be undone. You can invite them again later." |
| Remove — confirm prompt | "Type their email address to confirm." |
| Remove — confirm button | "Remove" · in flight: "Removing…" |
| Remove — error | "Couldn't remove that person." · [Try again] |
| Revoke — confirm heading | "Revoke the invite to **new@example.com**?" |
| Revoke — confirm body | "Their link stops working immediately. You can invite them again later." |
| Revoke — confirm button | "Revoke" · in flight: "Revoking…" |
| Revoke — error | "Couldn't revoke that invite." · [Try again] |
| Role change — success toast | "**sam@acme.com** is now an admin." · demoting: "**sam@acme.com** is now a viewer." |
| Remove — success toast | "**sam@acme.com** was removed." |
| Revoke — success toast | "The invite to **new@acme.com** was revoked." |

**"Added" was dropped, deliberately.** `last_seen_at` replaces it rather than joining it: accepting
an invite issues a session immediately, so a user's first activity timestamp *is* their join date.
For a pending row, "expires in 2 days" carries the only time fact worth having. Four columns, not
five.

**One null case does arise.** The migration that added `last_seen_at`
([`20260810_16`](../../backend/alembic/versions/20260810_16_user_activity_and_invite_revoke.py))
adds it nullable **with no backfill**, so accounts predating 2026-08-10 read `NULL` until that
person next signs in. Those rows say **"Not recorded yet"** — not "Never", which would assert a
falsehood, and not the pending row's `—`, which is what tells a member from an invite. `GET /users`
sorts these rows last.

**The route and the nav item stay `Users`.** *Users* names the domain, not today's actions. Nav
names were not commented in the DMI-131 review, so this one is unchanged.

**Open questions:**
1. Who may remove whom is a Users-issue question. The design system only fixes *destructive row
   action = text link + confirm dialog*.

---

### SETTINGS

**Route:** `/settings` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B5

> **Rebuilt by DMI-110, 2026-09-06.** Arrangement, hierarchy, grouping and density come from
> [`SETTINGS-RESEARCH.md`](SETTINGS-RESEARCH.md) §9 (owner decisions D1–D7); the look comes from
> [`FOUNDATIONS.md`](FOUNDATIONS.md). *Amended 2026-09-06 (DMI-110); this note previously read
> "Restyle only — DMI-110 owns this screen's content", parking the content for its own revamp
> (decided 2026-09-02, DMI-131). That hold is discharged.*

**Epicenter** — **who you are signed in as, and what you can do about it.** The screen opens on
your email and your role, read without interaction, and then offers the two things you can do to
that account: change its password, or leave the organization. *Who am I* comes before *change my
password*, always — a screen that opens with the cursor in a current-password field and never
names the account has asked for a secret before saying whose it is. *Amended 2026-08-18
(DMI-107); it previously read "change your own password".*

**Two groups on one scrolling page, separated by a hairline rule** — `Your account` first, then
`Leave this organisation` — and no card chrome around either: Settings is mostly text, and the
`Card` container earns its place on the dense data screens, not here. Both group titles are real
`<h2>`s. Density is `gap-8` between the groups, `gap-4` inside a group, `gap-2` from a label to its
value — three vertical steps, the rhythm rule's ceiling. The single page holds while Settings is
about the account and the way out of it; the two-level restructure waits for a second populated
section ([`SETTINGS-RESEARCH.md`](SETTINGS-RESEARCH.md) §10). *Added 2026-09-06 (DMI-110, D1/D5);
the screen was four bare sections at `gap-12`.*

Changing the password is still the most common reason anyone comes here, and it is still the
**only** change-password screen in the product — there is no forced rotation and no 403-triggered
flow ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced periodic rotation is rejected as
NIST-misaligned). It is reached through a `[Change password]` trigger that opens a modal, and the
trigger is a property row of the account group: the label `Password`, the button, and **nothing
between them**. No masked dots — there is no length to disclose and no "last changed" fact to show,
and the row takes one without a layout change if `password_last_changed_at` is ever added.
*Amended 2026-09-06 (DMI-110, D6); the page's regular state was "four short sections with air
between them" and the password section had its own `h2`.*

**The account group is read-only above its button** — email and role as text, no display name and
no `[Save]`. Open question **C3** stays open: there is no self-profile update operation, and an
input the user can type into but not submit is worse than text. The email is on the screen even
though the top bar also carries it: it is the screen's subject, and
[`ADR-017`](../adr/ADR-017-account-removal.md)'s typed confirmation asks the reader for that exact
string, which is worse to hunt for in the chrome. *Amended 2026-09-06 (DMI-110, D3/D7); `Your
details` and `Password` were two sections and are now one group titled `Your account`.*

**Leaving the organization also lives here** ([`ADR-017`](../adr/ADR-017-account-removal.md), added
2026-08-08), for **both roles**. A viewer never sees the USERS screen, so this is the only place
they can remove their own account — and an account nobody can leave is the wrong default for a
product holding this data. It sits at the bottom, visually separated, and is the last thing on the
page: it is not what anyone came here to do. Its title is an `<h2>`, like the account group's.
*Corrected 2026-09-06 (DMI-110); it shipped as a `<span className="text-title-sm">`, which left the
one section a screen-reader user most needs to find deliberately out of heading navigation.*

The copy does **not** name the organization. A signed-in member cannot read it — `UserProfileResponse` carries `user_id`, `email` and `role` only, and `org_name` exists solely on the
pre-session invite lookup. The wording is org-neutral rather than adding a request to discover a name
the heading has already supplied (spec 033).

**Activity is a privacy note inside the account group, not a section of its own** (spec 030). It
carries no control and no state, so it does not belong at the same level as the password and the
way out. It keeps its `Disclosure` — a caret and the label `What's recorded about me?` — and sits
under the account rows; activating it expands a persistent note and rotates the caret. The row is
the shared button primitive in its `link` variant and carries all five interactive states
([`FOUNDATIONS.md`](FOUNDATIONS.md) §Interaction states) — it is the worked example that section is written for. It names what
the organization can see, and states that no viewed/action detail is recorded. It is information,
not a toggle, and must work by keyboard and assistive technology: the trigger keeps focus when it
expands and stays linked to the note it reveals. *Amended 2026-09-06 (DMI-110, D2); it previously
had its own `Activity` heading and the label `What's recorded?`. The 2026-08-18 correction
(DMI-107), which moved the row off the heading's line, is superseded by the heading's removal.*

**Every password field carries a reveal toggle** — a real `<button type="button">` inside the
field and in the tab order, drawn as a hand-drawn inline SVG eye (no icon set, no glyph), whose
accessible name flips `Show password` ↔ `Hide password`. Fields start hidden, each toggles
independently, and the state never persists: closing the dialog resets it. The browsers' own
reveal controls are suppressed so no field shows two eyes. The same primitive carries the password
fields on LOGIN, RESET PASSWORD and ACCEPT INVITE — typing a new password blind, twice, is the
worst moment on those screens too. *Added 2026-09-06 (DMI-110, D4).*

**The scan target network is not here.** It is a property of the Pi, not of the user — one box
pointed at one network, identical for every admin in the org. It lives on DEVICES (B4).

**Data:**
- `POST /api/v1/auth/change-password` → **`204`**. Body: `{ current_password, new_password }`;
  `new_password` has `minLength: 12` in the contract. Errors: **`400`** for both a wrong current
  password (`wrong_current_password`) and a policy rejection (`password_policy_violation`); `401`
  on this route means the session itself failed, not the field. This split is deliberate — the
  SPA's refresh interceptor ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client) acts on
  every `401`, so returning one for a mistyped field would refresh-and-retry, then sign the user
  out over a typo. *Settled by contract ask C13.*
- Profile (display name, email) — **🔓 C3 update half.** `GET /users/me` exists, but there is no
  self-profile update operation and the model still has no display name.
- `DELETE /api/v1/users/me` → **`204`**. No body. Any role. **Hard delete** — the account and its
  sessions are gone, not disabled. One error worth designing for: **`409 last_admin`** when the
  caller is their org's only admin, because an org with no admins can invite nobody and manage
  nothing. The route does **not** clear the refresh cookie and does not need to: deleting the user
  cascades their refresh tokens, so the cookie is already inert.
- Activity disclosure — static product copy over the activity facts recorded by the backend; no
  request and no opt-out control.

**Password policy** ([`AUTH.md`](AUTH.md) → Passwords) — stated up front, not discovered by failing:
minimum 12 characters; no common or breached passwords; no obvious patterns (repeated characters,
simple suffixes); no names or birth dates.

**States:**
- **Regular:** the two groups, stacked, with the rule between them.
- **Loading:** the session profile has not arrived yet. The whole screen renders — both headings,
  the password row, the disclosure, the leaving copy — with the email and role values as skeleton
  bars and the `[Delete my account]` trigger disabled until the account it would delete is known,
  so the shape never changes under the reader. *Added 2026-09-06 (DMI-110); the screen previously
  rendered a half page while the profile loaded, because the details section returned nothing while
  the sections around it drew in full.*
- **Blank:** **not applicable, deliberately.** A settings form is never empty — it always has its
  own fields. Recording this so nobody invents an empty state to satisfy the three-states rule.
- **Error:** field-level inline errors (wrong current password, policy rejection). No toast for form
  validation — the error belongs next to the field that caused it.
- **Success:** inline confirmation, not a redirect. The user stays where they are.
- **Confirming removal:** a modal over the page. It states what is lost, and the confirm button is
  greyed out and disabled until the user has typed **their own email address**, enabling the
  instant it matches — deletion is irreversible and kills a live session, so a single click is not
  proportionate to it ([`ADR-017`](../adr/ADR-017-account-removal.md) §5, amended 2026-08-17). Same
  component as the USERS screen's Remove; two call sites is the bar §Shared components sets.
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
| Activity control | "What's recorded about me?" |
| Activity disclosure | "Everyone in your organization can see when you last signed in, and a log of changes to the organization: scans, machines that join the network, invitations, role changes, and members joining or leaving. We don't record what you viewed." *(the shipped string; the table carried the pre-spec-030 wording until 2026-09-06, DMI-110.)* |
| Section — account | "Your account" |
| Account rows | "Email" / "Role" / "Password" |
| Reveal toggle | "Show password" ↔ "Hide password" |
| Section — leaving | "Leave this organisation" |
| Leaving — body | "Your account is deleted and you lose access to this organisation's scans, network and vulnerabilities straight away. This can't be undone — an admin would have to invite you again." *(the shipped string; the table was one revision behind until 2026-09-06, DMI-110.)* |
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
| DMITRI    Home  Scans  Network  Devices  Users  Settings      [Log out]     |
+==============================================================================+
|                                                                              |
|   SETTINGS                                                                   |
|   ------------------------------------------------------------------        |
|                                                                              |
|   YOUR ACCOUNT                                                               |
|   Email  you@example.com                                                     |
|   Role  Admin                                                                |
|   Password  [ Change password ]                                              |
|                                                                              |
|   > What's recorded about me?                                                |
|   (expanded) Everyone in your organization can see when you last signed in,  |
|   and a log of changes to the organization: scans, machines that join the    |
|   network, invitations, role changes, and members joining or leaving. We     |
|   don't record what you viewed.                                 (muted)      |
|                                                                              |
|   ------------------------------------------------------------------        |
|                                                                              |
|   LEAVE THIS ORGANISATION                                                    |
|   Your account is deleted and you lose access to this organisation's         |
|   scans, network and vulnerabilities straight away. This can't be            |
|   undone — an admin would have to invite you again.              (muted)     |
|                                                                              |
|   [ Delete my account ]                                                      |
+------------------------------------------------------------------------------+
```

Confirming — a modal over the page; the confirm button is greyed out and disabled until the
address matches, shown here with parentheses in place of brackets (the convention `DESIGN.md` §2.2
uses for a greyed, non-clickable button; a live button keeps square brackets):
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
|            [ Cancel ]  ( Delete my account )     |
+--------------------------------------------------+
```

**Open questions:**
1. **C3** — no user resource. The profile section cannot be built.
2. Password strength meter — parked ([`IDEAS.md`](IDEAS.md) → Auth & admin). The policy hint is
   stated up front instead.
