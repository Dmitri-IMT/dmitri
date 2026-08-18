# ARCHITECTURE — Leave the organization from Settings

> Frontend only. Every path in this document is under `frontend/src/`. No `hardware-agent/` work,
> no `backend/` work, no contract change: `DELETE /api/v1/users/me` is already published and
> already generated into `src/types/openapi.d.ts` (`operations["deleteCurrentUser"]`, and the
> `LastAdminConflict` response with its pinned `code`). `npm run gen:types` must stay a clean
> diff — nothing here regenerates it.
>
> **No `INTEGRATION.md`.** Nothing crosses a layer boundary. The one contract involved was
> delivered by `specs/029-account-removal-api/` and is consumed here as published.
>
> **No `HUMAN_INFRA_REQUIRED`.** No new dependency either: `radix-ui@^1.6.4` is already in
> `frontend/package.json` and already used by `components/ui/label.tsx` and
> `components/ui/button.tsx`.
>
> Sources: `TRUTH.md` (this folder) · `docs/adr/ADR-017-account-removal.md` §§1, 3, 5, 6 ·
> `docs/ui/SCREENS.md` § SETTINGS, § LOGIN, §Shared components, §Consistency rules ·
> `.claude/skills/frontend-conventions/SKILL.md` · `.claude/docs/frontend/screens.md`.

---

## System context

Where this sits in the SPA, from the outside in:

```
main.tsx  →  QueryClientProvider  →  MemoryRouter/BrowserRouter  →  SessionProvider
                                                                        │
                            App.tsx route table ────────────────────────┤
                                                                        │
   /login  (public, AuthShell)  ←──── redirect on teardown ─────┐       │
                                                                │       │
   RequireSession → AppShell (TopBar + Outlet)                  │       │
        └── /settings → Settings.tsx                            │       │
                          └── ConfirmByTyping (Radix Dialog) ───┘       │
                                    │                                   │
                                    │ onConfirm                         │
                                    ▼                                   │
                        useSession().deleteAccount() ───────────────────┘
                                    │
                                    ├─ api/users.ts  deleteCurrentUser()
                                    │     └─ apiClient (business Axios, no credentials)
                                    │           DELETE /api/v1/users/me
                                    │
                                    ├─ 204 → clearSession()  (clearAccessToken + enabled=false
                                    │                          + removeQueries ['session'])
                                    │        navigate('/login', {replace, state:{accountDeleted:true}})
                                    │
                                    └─ throw → Settings renders the refusal; session untouched
```

**Route.** `/settings`, already registered in `src/App.tsx` inside `RequireSession` → `AppShell`.
No route is added, no route is changed. Both roles reach it — `TopBar` has no role branch
(`.claude/docs/frontend/screens.md`), and `DELETE /users/me` is `require_user`, any role
(ADR-017 §2). There is nothing role-conditional anywhere in this feature.

**Shell.** The leaving section renders inside the existing 720px prose column that `AppShell`
gives every inside-shell screen. It is the **last** child of `Settings`'s root flex column, after
the change-password form and the Activity disclosure. The confirmation is a Radix
`Dialog.Portal` — it renders into `document.body`, outside the shell, which is what a modal
should do and what Testing Library's `screen` queries already reach.

**Session lifecycle and the teardown path shared with `signOut`.** `SessionProvider` owns the
whole of it: the `['session']` query, the `enabled` flag that models "anonymous", the
`clearAccessToken()` call, and the effect that re-asserts `removeQueries({queryKey:['session']})`
on every render while `enabled` is false. `clearSession()` is a **closure over provider-local
state** — a page cannot reproduce it. A page that only called `clearAccessToken()` and navigated
would leave `enabled === true` and a cached `['session']` entry, so `status` would still read
`authenticated`, and `Login`'s `if (status === 'authenticated') return <Navigate to="/" replace/>`
would bounce the just-deleted user straight back to Home. **Account removal therefore gets its own
context method.** See the decision below.

**Which `signOut` step is deliberately *not* reused.** `signOut()` posts `/auth/logout` first.
`deleteAccount()` must not: ADR-017 §1 says the delete cascades `refresh_tokens`, so the session
is already gone server-side and a `logout` afterwards is a request against a session that no
longer exists. `deleteAccount()` shares only the *tail* of `signOut` — `clearSession()` then
`navigate('/login', { replace: true })` — plus the router state that carries the arrival note.

**The refresh cookie is not touched, by decision.** ADR-017 §6: the cookie is scoped to
`/api/v1/auth`, the cascade has already invalidated the token behind it, and its next use is a
`401`. Clearing it would mean sending credentials from the business client — see Constraint 1.

---

## Data model / contracts

### The call

`DELETE /api/v1/users/me` — `operations["deleteCurrentUser"]` in `src/types/openapi.d.ts`.

| | |
|---|---|
| Request body | **none** (`requestBody?: never`) |
| Query / path / header params | **none** |
| `204` | `content?: never` — empty body. The account, its `refresh_tokens` and its `password_reset_tokens` are gone. |
| `401` | `components["responses"]["Unauthorized"]` — not designed for; see below. |
| `409` | `components["responses"]["LastAdminConflict"]` — `ErrorResponse & { error: { code: "last_admin" } }`, the code **pinned** by the contract. |

Because both directions are empty, **there is no request or response shape to alias** — Constraint 5
is satisfied by having nothing to hand-write, not by inventing a type. The client function is:

```ts
// src/api/users.ts
export async function deleteCurrentUser(): Promise<void> {
  await apiClient.delete('/users/me')
}
```

`apiClient` is the business instance from `src/api/client.ts` — request interceptor attaches the
bearer token, response interceptor owns the single-flight 401→refresh. No second client, no
bespoke fetch (frontend-conventions §Data and types).

### The error-code read path

`readApiError(err)` from `src/api/apiError.ts` returns `{ status, code }`, both possibly
`undefined` (a network failure is neither an Axios response nor an API envelope). The page
branches on the pair, exactly as `Settings.tsx` already does for `change-password`:

| Observed | Branch | Effect |
|---|---|---|
| resolves (`204`) | success | `clearSession()` + navigate to `/login` with the arrival note |
| `status === 409 && code === 'last_admin'` | last-admin refusal | modal stays open, session untouched, refusal message rendered |
| anything else (`5xx`, network, `401`, unexpected `409` code) | generic failure | modal stays open, session untouched, failure message rendered |

The `'last_admin'` literal is compared inline, matching the existing
`code === 'wrong_current_password'` compare in `Settings.tsx:56`. No `Record` map, no exported
constant — one code, one call site.

**`401` needs no special handling.** It falls into the generic branch. If the access token has
expired the `apiClient` response interceptor refreshes and retries first; if the refresh also
fails it emits `session-expired`, which `SessionProvider` already turns into a teardown and a
`/login` redirect. Nothing new is required.

**The removal is a plain `await` in an event handler, not a `useMutation`.** Every mutation in
this app is written that way (`signIn`, `acceptInvitation`, `signOut`, `changePassword`); TanStack
Query owns the *reads*. Do not introduce a mutation hook for one call.

### The router-state key carrying the arrival note

Reuses the pattern `ResetPassword.tsx:53` → `Login.tsx` already ships:

```ts
navigate('/login', { replace: true, state: { accountDeleted: true } })
```

| Key | Type | Set by | Read by |
|---|---|---|---|
| `passwordReset` | `true` | `pages/ResetPassword.tsx` (existing) | `pages/Login.tsx` |
| `accountDeleted` | `true` | `auth/SessionProvider.tsx` → `deleteAccount()` (**new**) | `pages/Login.tsx` |

Router state is the whole mechanism for "does not survive a reload" (TRUTH, and SCREENS § LOGIN):
`history.state` is not restored on a fresh document load, and `Login` additionally scrubs it with
`navigate(location.pathname, { replace: true })` inside the same effect that focuses the note.
The value is snapshotted once with `useState(() => …)` so the scrub does not erase the note it
just triggered. **No `sessionStorage`, no query parameter, no provider state** — each of those
would survive a reload and reintroduce the stale-message disclosure the rule exists to prevent.

### Session context contract change

`SessionContextValue` in `src/auth/SessionProvider.tsx` gains one member:

```ts
interface SessionContextValue {
  status: SessionStatus
  user: UserProfileResponse | null
  signIn: (credentials: LoginRequest) => Promise<void>
  signOut: () => Promise<void>
  acceptInvitation: (request: AcceptInviteRequest) => Promise<void>
  deleteAccount: () => Promise<void>   // NEW
}
```

```ts
async function deleteAccount(): Promise<void> {
  await deleteCurrentUser()                 // rejects on 409 / 5xx / network — deliberately unguarded
  clearSession()
  navigate('/login', { replace: true, state: { accountDeleted: true } })
}
```

**Decision — why a context method rather than driving it from the page.** Two forces:

1. *The teardown is not reachable from a page.* `clearSession()` closes over `setEnabled` and
   cooperates with the deliberately dependency-free `removeQueries` effect. Reproducing it in
   `Settings.tsx` means exporting provider internals or duplicating a subtlety whose comment in
   `SessionProvider.tsx` explains why it is fragile. `signOut` is the precedent: it is a context
   method for exactly this reason.
2. *The failure branch must stay in the page.* Copy, live regions and modal state are screen
   concerns. So `deleteAccount` **does not catch** — it is shaped like `signIn`, which awaits
   `login()`, lets a `401` propagate, and leaves `Login.tsx` to turn it into a message. It is
   explicitly **not** shaped like `signOut`, whose `try/catch/finally` swallows failure because a
   local logout must always succeed. Swallowing here would tear down a session whose account
   still exists.

The split is: **provider owns the session teardown and the redirect; page owns the request's
outcome copy.** Nothing about `last_admin` reaches `SessionProvider`.

### `UserProfileResponse` — the confirming address

`components['schemas']['UserProfileResponse']` is `{ user_id, email, role }` and nothing else.
`useSession().user!.email` is the value typed to confirm. There is **no organization name in it**,
which is why the leaving copy names the org generically and issues no extra request (TRUTH;
SCREENS § SETTINGS shows `**Acme**` as an illustration only — do not build a lookup for it).

`user` is typed `UserProfileResponse | null`. `Settings` is behind `RequireSession`, so it is
non-null whenever the screen is interactive, but the leaving section is rendered
`{user && <section …>}` rather than asserted with `!`. That keeps the type honest and matches
"absent, not disabled": during the single boot render the section is simply not there yet.

---

## New files and naming (mandatory)

Exhaustive. Every file an implementer creates or opens is listed. `frontend/src/` is the root of
every path.

| # | Area | Path | Exported / added symbols | Note |
|---|------|------|--------------------------|------|
| 1 | API | `frontend/src/api/users.ts` | `deleteCurrentUser(): Promise<void>` | **Touched.** Added beside the existing `getCurrentUser`. Name matches the generated `operationId`. Uses `apiClient` (already imported in this file). No new type alias — the call has no body either way. |
| 2 | Session | `frontend/src/auth/SessionProvider.tsx` | `SessionContextValue.deleteAccount`; local `async function deleteAccount()`; new import of `deleteCurrentUser` from `@/api/users`; `deleteAccount` added to the `value` object | **Touched.** Does not catch. Calls `clearSession()` then `navigate('/login', { replace: true, state: { accountDeleted: true } })`. Do not reuse `logout()`. |
| 3 | Shared component | `frontend/src/components/ConfirmByTyping.tsx` | default export `ConfirmByTyping`; module-local `type ConfirmByTypingProps`; module-local `function matchesExpected(typed, expected)` | **New.** Lives in `components/`, not `components/ui/` — `components/ui/` is the vendored shadcn layer (`button`, `input`, `label`); this is product behaviour. Built directly on `Dialog` from `radix-ui` (no vendored `ui/dialog.tsx`: one modal does not earn the shadcn surface). Props and inert mechanics are specified below and are binding. |
| 4 | Screen | `frontend/src/pages/Settings.tsx` | default export `Settings` (signature unchanged) | **Touched.** Adds `useSession()` for `user` + `deleteAccount`; state `isLeaveOpen: boolean` and `leaveError: string \| null`; a `handleLeave()` async callback passed as `onConfirm`; the trailing `<section data-testid="settings-leave">` with its heading, body and `data-testid="settings-leave-trigger"` button; and the `<ConfirmByTyping>` element. The change-password form and the Activity disclosure are **not** modified. |
| 5 | Screen | `frontend/src/pages/Login.tsx` | default export `Login` (signature unchanged) | **Touched.** Widens the snapshotted router-state read to an `arrival: 'passwordReset' \| 'accountDeleted' \| null` value and switches the copy of the **single existing** `role="status"` region on it. Keeps `data-testid="login-success"`. See "Login: one region, two notes". |
| 6 | Test fixtures | `frontend/src/test/mswHandlers.ts` | `handlers` array | **Touched.** One line: `http.delete(\`${baseURL}/users/me\`, () => new HttpResponse(null, { status: 204 }))`. Required — `setup.ts` runs `server.listen({ onUnhandledRequest: 'error' })`, so an unstubbed route fails the suite. No new exported fixture: `adminProfile` / `viewerProfile` already carry the emails the confirmation needs. |
| 7 | Test | `frontend/src/components/ConfirmByTyping.test.tsx` | — | **New.** Component-level, no MSW. Mirror `frontend/src/pages/home/FindingDeck.test.tsx` (nearest existing shared-interactive-component test: `userEvent`, keyboard, absent-not-disabled sweep). |
| 8 | Test | `frontend/src/pages/Settings.test.tsx` | — | **Touched.** Extends the file's own helpers (`signedInAs`, `renderSettings`, `LocationProbe`, `respond`) with a `captureDeleteRequests()` in the shape of the existing `captureChangeRequests()`. |
| 9 | Test | `frontend/src/pages/Login.test.tsx` | — | **Touched.** Mirror the existing `renderLoginApp({ passwordReset: true })` tests (`Login.test.tsx:205-235`) with `{ accountDeleted: true }`. |
| 10 | Test | `frontend/src/auth/SessionProvider.test.tsx` | — | **Touched.** Mirror the two existing `signOut` teardown tests (`SessionProvider.test.tsx:85` and `:109`) for `deleteAccount`. |

### Files deliberately **not** touched

The house integration rule is "trace every call site of the changed thing". `SessionContextValue`
is the changed contract; adding a member is additive, and every existing consumer destructures a
subset. Each was checked:

| Call site | Destructures | Verdict |
|---|---|---|
| `frontend/src/auth/RequireSession.tsx:5` | `{ status }` | unaffected |
| `frontend/src/components/TopBar.tsx:13` | `{ signOut }` | unaffected — `[Log out]` keeps calling `signOut`, not `deleteAccount` |
| `frontend/src/pages/Login.tsx:11` | `{ status, signIn }` | unaffected by the context change (touched for the arrival note only) |
| `frontend/src/pages/AcceptInvite.tsx:28` | `{ status, signOut, acceptInvitation }` | unaffected |
| `frontend/src/auth/useSession.ts` | returns the whole context | unaffected — no explicit return type to widen |
| `frontend/src/api/client.ts`, `instances.ts`, `apiError.ts` | — | unaffected; see Constraint 1 |
| `frontend/src/lib/copy.ts` | — | **unchanged**; see Constraint 6 |
| `frontend/src/App.tsx`, `components/AppShell.tsx` | — | unchanged; `/settings` is already routed inside the guard |
| `frontend/src/types/openapi.d.ts`, `contracts/openapi/openapi.yaml` | — | **never edited by hand**; the operation is already generated |

### `ConfirmByTyping` — the exact props

These are binding. The second call site (Users screen, DMI-90 — **not built here**) must be able
to use this component with no change to it.

```ts
type ConfirmByTypingProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  heading: string
  body: string
  expectedValue: string
  confirmLabel: string
  confirmPendingLabel: string
  onConfirm: () => Promise<void>
  error?: string | null
}
```

| Prop | Why it exists | Settings (here) | Users / DMI-90 (later, unchanged component) |
|---|---|---|---|
| `open` / `onOpenChange` | Radix controlled `Dialog`. `onOpenChange(false)` is the **single** dismissal path — Cancel, `Esc` and overlay click all route through it. There is no separate `onCancel`. | `isLeaveOpen`, `setIsLeaveOpen` | its own row state |
| `heading` | `Dialog.Title` (Radix requires one). | `"Delete your account?"` | `"Remove ana@northwind.example?"` |
| `body` | `Dialog.Description` (satisfies Radix's `aria-describedby`). | what is lost, irreversible | same shape, other person |
| `expectedValue` | The address to type, **and** the address rendered in the prompt. The prompt line is the `<label htmlFor>` for the input, so one prop supplies the gate and its accessible name — there is no separate `inputLabel`. | `user.email` from `useSession()` | the target row's `email` |
| `confirmLabel` / `confirmPendingLabel` | SCREENS pins both per screen (`"Delete my account"` · `"Deleting…"`). | those two | `"Remove"` · `"Removing…"` |
| `onConfirm` | The whole action. Awaited by the component; **must not reject** — the caller handles its own errors and reports through `error`. | `handleLeave` | its own delete-by-id handler |
| `error` | Caller-supplied message rendered inside the modal, in a region that is **always mounted, empty when clean** (frontend-conventions: a live region must pre-exist to be announced). The component never invents, maps or interprets a message — and never suppresses one either. | `last_admin` refusal / generic failure | `last_admin` / `self_target` / generic |

**The caller MUST set `error` to `null` before awaiting its request.** This is part of the prop's
contract, not a courtesy, and DMI-90 inherits it:

```ts
async function handleLeave(): Promise<void> {
  setLeaveError(null)          // contract: empties the region before the attempt
  try {
    await deleteAccount()
  } catch (err) {
    const { status, code } = readApiError(err)
    setLeaveError(
      status === 409 && code === 'last_admin' ? LAST_ADMIN_COPY : GENERIC_COPY,
    )
  }
}
```

The empty→filled transition is the announcement mechanism. A `role="alert"` whose text content does
not change is not re-announced, and the component's focus effect — `useEffect(() => { if (error)
errorRef.current?.focus() }, [error])` — does not re-fire on an unchanged value. Without the null,
a retry that fails the same way (a second `409 last_admin` is the ordinary case, since nothing the
person can do inside the dialog changes the answer) would produce no announcement, no focus move,
and no visible change at all.

**The message does not clear when the field is edited.** An earlier draft of `DESIGN.md` said it
did; the component owns the typed value and there is no callback to the caller, so the caller cannot
see an edit, and the component may not decide that a caller's message has stopped being true. Both
documents now say: caller clears, on submit; the dialog's unmount clears the rest.

**There is no `disabled` prop and no `fallback` prop, and none may be added.** The full prop list
is unchanged — the nine entries above — because a caller was never meant to supply the disabled
state or a substitute rendering. The component derives its own disabled state internally, from the
match and from its own in-flight state; a caller cannot inject one. That remains true after this
amendment, and it is exactly why DMI-90 stays a zero-change second caller.

**How the confirm button's `disabled` state is derived (amended 2026-08-17 — ADR-017 §5, which
reverses the always-live design this section previously specified):**

- The input and the two buttons live inside a real `<form onSubmit={handleSubmit}>`. Confirm is
  `<button type="submit" disabled={!matchesExpected(typed, expectedValue) || isSubmitting}>`;
  Cancel is `<button type="button">` inside `Dialog.Close asChild`, absent while `isSubmitting`.
- **Confirm carries the real `disabled` attribute — not `aria-disabled`, not a muted style on an
  otherwise-live control — for as long as the typed value does not match `expectedValue`, and
  again while the request is in flight.** `disabled` removes it from the tab order; that is
  deliberate, and the accepted accessibility trade-off below. It enables the instant
  `matchesExpected(typed, expectedValue)` becomes true.
- The prompt element is both the field's `<label htmlFor>` and the confirm button's
  `aria-describedby` target — one element, one id, two references. `DESIGN.md` §5.3 depends on this:
  a screen reader reaching the button hears the condition it is gated on, with no second string to
  keep in sync.
- `matchesExpected` compares `typed.trim().toLowerCase() === expected.trim().toLowerCase()`.
  Case-folding is not a loosening: ADR-017 §1 records that the account's identity in this system
  *is* `lower(email)`, so two spellings differing only in case are the same account, and trimming
  defeats a trailing space from paste or autofill. Implementers must not improvise here — the
  input also carries `autoComplete="off"`, `autoCapitalize="none"`, `autoCorrect="off"`,
  `spellCheck={false}` so a mobile keyboard cannot silently defeat a correct entry.
- `handleSubmit` may keep an early return on `!matchesExpected(...)` as a belt-and-braces guard —
  a `disabled` `<button type="submit">` cannot be activated by a click or by `Enter` from the field
  in any evergreen browser, so the guard is defensive, not the mechanism. The stated mechanism is
  the `disabled` attribute, derived from the match.
- **In-flight state is owned internally**, not by a prop: `handleSubmit` sets a local
  `isSubmitting`, `await`s `onConfirm()`, and clears it in `finally`. While `isSubmitting` the
  confirm button reads `confirmPendingLabel` and carries `disabled` regardless of the match — the
  same attribute, a second reason to hold it. `Login.tsx:113` and `Settings.tsx:168` already carry
  `disabled` for their own in-flight state, so this is one more case of an existing pattern, not
  the product's sole exception any more. Owning it internally is what closes the hole: a `pending`
  prop would be a `disabled` prop wearing a different name, and it also guarantees the AC "the
  removal is requested **once**".
- Closing the dialog unmounts `Dialog.Content` (no `forceMount`), but **not** `ConfirmByTyping`
  itself: the component sits beside the trigger in its caller and stays mounted for the life of
  the screen, so its `typed` state outlives the dialog. The reset is therefore **explicit**:
  React's reset-on-prop-change pattern — a `wasOpen` state mirror compared during render, which
  clears `typed` on the false → true edge. Not a layout effect: `npm run lint` errors on
  `react-hooks` *"Calling setState synchronously within an effect can trigger cascading renders"*,
  and the field must be empty on the reopened dialog's **first** render, not one paint later.
  Without the reset a cancelled attempt reopens with the address still in the field and the
  destructive action already live, and the typing gate holds only on the first open. Assertion 9c
  pins it; do not remove the reset as redundant.

**Focus restore on close is suppressed when the opener is gone (added 2026-08-17).** Radix's focus
scope restores focus in a **deferred** cleanup — `setTimeout(…, 0)` in
`@radix-ui/react-focus-scope`, focusing `previouslyFocusedElement ?? document.body`. On the `204`
path the dialog is not closed before the navigation: `deleteAccount()` navigates, `Settings`
unmounts with `open === true`, and that timer fires *after* `Login` has focused its arrival note,
targeting a trigger that is no longer in the document. Focusing a detached node is a no-op, so
`document.activeElement` falls back to `<body>` and the arrival note silently loses focus. The
component prevents it:

```tsx
const openerRef = useRef<Element | null>(null)

// Layout effect, so it runs before Radix's passive effect moves focus into the field.
useLayoutEffect(() => {
  if (open) openerRef.current = document.activeElement
}, [open])

<Dialog.Content
  onCloseAutoFocus={(event) => {
    if (!openerRef.current?.isConnected) event.preventDefault()
  }}
>
```

Outcome-agnostic on purpose: `Cancel`, `Esc` and a backdrop click leave the trigger mounted, so
Radix's restore runs untouched and focus returns to `Delete my account` (`DESIGN.md` §5.1). Only a
close caused by the opener's own page being replaced yields, and it yields to whatever the
replacing screen focused. **No prop is added** — Constraint 2 holds, and DMI-90 inherits the
behaviour, where a removed row's trigger is detached for the same reason.

**Accepted accessibility trade-off (ADR-017 §5).** While the typed value does not match, the
confirm button is out of the tab order. A sighted person sees it greyed and reads "not yet"; a
screen-reader user who mistypes the address tabs from the field, finds no confirm button, and has
no signal distinguishing a typo from a broken dialog. The operator was shown this cost and
accepted it — this is not an open question and is not re-argued here.

---

## Constraints

1. **`DELETE /users/me` goes over the business Axios instance, which sends no credentials — and
   that must not be widened.** `src/api/instances.ts` creates `apiClient` with no
   `withCredentials`; only `authClient` sets it, and `src/api/client.test.ts:93` asserts the
   split ("scopes credentials so the business client sends none and the auth client sends
   withCredentials"). ADR-017 §6 makes this deliberate: the refresh cookie is scoped to
   `/api/v1/auth`, the cascade has already invalidated the token behind it, so the residual cookie
   authenticates nothing. Do not add `withCredentials` to `apiClient`, to this one request, or to
   a new instance in order to clear it.
2. **`ConfirmByTyping` has no `disabled` prop and no `fallback` prop.** Its full prop list is the
   nine entries above, unchanged by this amendment. An unmatched value makes the confirm button
   carry the real `disabled` attribute, derived internally from `matchesExpected` and from the
   component's own `isSubmitting` state — never from a prop. Adding a `disabled`, `fallback`,
   `pending`, `inert`, `readOnly` or `variant="disabled"` prop is still a rejection at review: the
   component derives the state, and a caller cannot inject one.
3. **No `[disabled]` element may appear anywhere in the rendered tree at rest, with the modal
   closed.** This is the DMI-81 (spec `020-frontend-vertical-slice-login-home`, AC 7) invariant,
   and it is asserted today in **`frontend/src/pages/Settings.test.tsx:290`**
   (`'renders nothing disabled at idle'`), **`frontend/src/components/TopBar.test.tsx:25-41`**,
   **`frontend/src/pages/Home.test.tsx:304`** (`'AC 7 — every rendered control is enabled with no
   aria-disabled'`), plus `ForgotPassword.test.tsx:67`, `ResetPassword.test.tsx:107` and
   `home/FindingDeck.test.tsx:47`. Every one of these renders with the dialog closed — none of them
   opens `ConfirmByTyping` — so they are **unaffected by this amendment and must keep passing
   unmodified.** The sweep is always `queryAllByRole('button'|'link'|'textbox')` → `toBeEnabled()`
   + `not.toHaveAttribute('aria-disabled','true')`, **never**
   `container.querySelectorAll('[disabled]')` — that form misses `fieldset[disabled]` inheritance
   and `aria-disabled`, and breaks Testing Library's `no-container` / `no-node-access` lint rules
   (`.claude/docs/frontend/screens.md`).

   **Amended 2026-08-17 (ADR-017 §5):** the invariant no longer extends inside the open
   `ConfirmByTyping` dialog. The confirm button there is sanctioned `disabled` in two cases — while
   the typed value does not match `expectedValue`, and while a request is in flight. The second is
   the same sanctioned exception the product already has (a submit button while its own request is
   in flight); the first is new. No other element in the dialog, and nothing outside it, is ever
   `disabled`.
4. **`409 last_admin` is handled after the attempt, never predicted.** No pre-flight admin count,
   no `GET /users` from Settings, no hidden or greyed "you may be the last admin" state. The
   refusal is discovered by making the request and reading
   `status === 409 && code === 'last_admin'`. Any other failure — `5xx`, network, unexpected code
   — is a **distinct** message and the still-live confirm button is the retry (the modal stays
   open; do not add a second "Try again" control, and do not reuse one message for both).
5. **Types come from the generated `src/types/openapi.d.ts`.** No hand-written request or response
   interface. This call has no body in either direction, so nothing is aliased at all; the
   confirming email comes from `components['schemas']['UserProfileResponse']` via
   `useSession().user`. Never edit `contracts/openapi/openapi.yaml` or the generated file by hand.
6. **Copy placement follows the existing convention, per string.** `src/lib/copy.ts` holds only
   strings shared by *several* screens (its own header comment says so: the password-form copy).
   Every string this feature adds belongs to exactly one screen, so **`lib/copy.ts` is not
   modified**:

   | String | Home | Why |
   |---|---|---|
   | `"Your account has been deleted."` | inline in `pages/Login.tsx` | matches the sibling `"Password set. Sign in with your new password."`, which is inline in the same file |
   | Leaving section heading + body + `"Delete my account"` trigger | inline in `pages/Settings.tsx` | Settings-only, like `"Password changed."` and the Activity note already inline there |
   | Modal heading, body, `confirmLabel`, `confirmPendingLabel` | inline in `pages/Settings.tsx`, passed as props | the component holds no copy of its own — that is what makes DMI-90 a zero-change caller |
   | `"You're the only admin. Make someone else an admin first, then you can leave."` | inline in `pages/Settings.tsx` | one screen, one branch |
   | Generic failure (`"Couldn't delete your account."`) | inline in `pages/Settings.tsx` | screen-specific; do **not** substitute the shared `SERVICE_ERROR`, which says "Couldn't reach Dmitri" and would misdescribe a `5xx` that arrived fine |

   Final wording is `DESIGN.md`'s to fix against SCREENS § SETTINGS / § LOGIN; *where the string
   lives* is fixed here.
7. **No new dependency, no new vendored `ui/` component.** `Dialog` comes from the already-installed
   `radix-ui` unified package, imported the way `label.tsx` and `button.tsx` import their
   primitives. Do not run the shadcn CLI.
8. **The removal is not a `useMutation` and not an Effect.** Plain `await` in the event handler,
   matching every other mutation in this app. TanStack Query stays on the read path.
9. **The leaving section is last and visually separated**, for both roles, with no role branch
   anywhere in the code. There is no admin-only or viewer-only rendering in this feature.
10. **Login keeps exactly one `role="status"` region.** `Login.test.tsx:214` asserts
    `screen.getByRole('status')` resolves to *the* success region; a second status element would
    break it. See below.

### Login: one region, two notes

`Login.tsx` today snapshots `location.state.passwordReset` with `useState(() => …)`, focuses the
region and scrubs the state in one effect. Widen the snapshot, keep the single region:

```ts
const [arrival] = useState(() => {
  const state = location.state as
    | { passwordReset?: boolean; accountDeleted?: boolean }
    | null
  if (state?.accountDeleted === true) return 'accountDeleted' as const
  if (state?.passwordReset === true) return 'passwordReset' as const
  return null
})
```

The effect's guard becomes `if (arrival !== null)` — the focus and the
`navigate(location.pathname, { replace: true })` scrub are unchanged. The region keeps
`data-testid="login-success"`, `role="status"`, `tabIndex={-1}` and its ref; only its text
switches on `arrival`. Renaming the test id is out of scope (surgical changes): the region is the
screen's arrival note and both notes are confirmations, not errors — SCREENS § LOGIN is explicit
that the deletion line "is a *confirmation*, not an error, and is styled as one".

---

## Testing expectations

Vitest + Testing Library + MSW, as configured by `frontend/src/test/setup.ts` (`server.listen`
with `onUnhandledRequest: 'error'`) and `renderWithProviders` (MemoryRouter + QueryClientProvider
+ SessionProvider). Gate: `npm run lint && npm run format:check && npm run typecheck &&
npm run test && npm run build` from `frontend/`.

### `frontend/src/components/ConfirmByTyping.test.tsx` (new)

**Mirror:** `frontend/src/pages/home/FindingDeck.test.tsx` — a shared interactive component,
rendered directly with `userEvent.setup()` and stub props, no MSW.

| # | Assertion |
|---|---|
| 1 | Closed (`open={false}`) renders no dialog: `queryByRole('dialog')` is null. |
| 2 | Open renders `role="dialog"` with the accessible name from `heading` and the description from `body`; the prompt names `expectedValue`; the input's accessible name is the prompt (`getByLabelText`), and the confirm button's `aria-describedby` resolves to that **same** element (assert the id matches the prompt's, not that the attribute merely exists). |
| 3 | **Inert on empty** — submit with an empty input: `onConfirm` not called. |
| 4 | **Inert on partial and on a different address** — `it.each` over `'ana@'` and `'someone.else@northwind.example'`: `onConfirm` not called. |
| 5 | **Exact match releases it** — type `expectedValue`, confirm: `onConfirm` called exactly once. |
| 6 | Trailing/leading whitespace and a differently-cased spelling of the same address still confirm (pins `matchesExpected`). |
| 7 | **Disabled until the match, live at the match** — at empty input and at each `it.each` partial/different address, the confirm button `toBeDisabled()` and is out of the tab order; typing `expectedValue` makes it `toBeEnabled()`. It never carries `aria-disabled` — the mechanism is the real `disabled` attribute. Cancel and the input stay enabled throughout. This is the test that would fail if the match gate stopped deriving `disabled`. |
| 8 | **Pending** — `onConfirm` returns a deferred promise: the confirm button reads `confirmPendingLabel` and `toBeDisabled()` for the duration, regardless of the match; a second click while pending calls `onConfirm` only once; after resolution the label and the enabled state both return, since the matched value is still in the field. Use `msw`'s `delay` style or a hand-held promise, as `Settings.test.tsx` already does for the in-flight password test. |
| 9 | **Dismissal** — Cancel click, and `Esc`, each call `onOpenChange(false)` and never `onConfirm`. Focus returns to the element that opened the dialog, which is still mounted — the `onCloseAutoFocus` suppression must **not** fire on this path. |
| 9c | **Reopens clean** — from a harness with a real trigger: open, type `expectedValue` until the confirm button is enabled, Cancel, then open again. The field is empty and the confirm button is `disabled` on the second open, and `onConfirm` was never called. This is the test that would fail if the explicit `setTyped('')` reset were removed. |
| 9b | **Opener detached** — render the dialog open from a parent that then unmounts the trigger and the dialog together, and focus something else first: after timers flush (`await waitFor(...)`, which outlives Radix's `setTimeout(…, 0)`), focus is still on that other element and **not** on `document.body`. |
| 10 | **`error` region** — always in the document (with `error={null}`, empty); with a string, it renders that exact string in a `role="alert"` region, and focus moves to it (`tabIndex={-1}`, never a tab stop). The component adds no message of its own, and does not blank one when the field is edited: type into the field with `error` set and the message is still there. |
| 10b | **The same message twice** — rerender `error={null}` → `error="X"` → `error={null}` → `error="X"`: the region empties and refills each time, and focus lands on it on **both** fills. Pins the announcement mechanism the caller's null-before-request exists to serve. |
| 11 | **Second-caller shape** — one render with DMI-90-style props (`confirmLabel="Remove"`, a different `expectedValue`) proving no prop is Settings-specific. |

### `frontend/src/pages/Settings.tsx` → `frontend/src/pages/Settings.test.tsx` (extend)

**Mirror:** the file itself — `signedInAs(profile)`, `renderSettings()`, `LocationProbe`, and a
new `captureDeleteRequests()` built exactly like the existing `captureChangeRequests()` but on
`http.delete(\`${baseURL}/users/me\`)`. Roles are exercised with the existing
`it.each([['admin', adminProfile], ['viewer', viewerProfile]])`.

| # | AC covered | Assertion |
|---|---|---|
| 1 | viewer sees the exit / admin sees the same exit | `it.each` over both profiles: `settings-leave` present, its trigger reads `Delete my account`, and it is the **last** section — assert ordering against `settings-form` and `settings-activity` rather than by index alone. |
| 2 | typing gates the action | Open the modal, submit with empty / partial / a different address: `captureDeleteRequests()` stays `[]`. |
| 3 | exact match | Type the profile's own `email` (`adminProfile.email`, from `mswHandlers`), confirm: exactly one DELETE recorded. |
| 4 | successful removal | `204`: `getAccessToken()` is `null` and `location-probe` reads `/login` (the `login-route` stub is already registered by `renderSettings`). Reuse the existing token/route assertion style from the change-password tests. |
| 4b | focus survives the navigation | Same `204`, driven from the open dialog: after the route settles **and Radix's deferred restore has had its tick** — assert inside `waitFor`, never synchronously after the response — `document.activeElement` is the arrival note and not `document.body`. This pins the focus outcome, but it does **not** guard the `onCloseAutoFocus` suppression: verified by mutation, it still passes with that handler deleted, because jsdom does not reproduce Radix's deferred restore against a detached opener. No Vitest test discriminates the suppression — it is unguarded by the suite and only a real-browser run would catch its removal. The `Login.test.tsx` mirrors cannot catch it either, because they never mount a dialog. |
| 5 | only admin refused | MSW returns `409 { error: { code: 'last_admin', … } }`: the refusal string is rendered, `getAccessToken()` is **unchanged**, `location-probe` still reads `/settings`, and no `/auth/refresh` fires — reuse the existing `countRefreshes()` helper, which exists for exactly this class of assertion. |
| 6 | server failure | `500`, and separately a network error (`HttpResponse.error()`): the **generic** message renders, distinct from the last-admin string; session and route intact; the confirm button is still live so a second attempt is possible. |
| 6b | retry after a refusal | Two consecutive `409 last_admin` responses: two DELETE requests are recorded, and the refusal is announced and focused after the second as after the first — `handleLeave` nulls `leaveError` before each attempt. |
| 7 | cancelling | Open, type the correct address, then Cancel: zero DELETE requests, `settings-form` and `settings-activity` unchanged. |
| 8 | confirm button gated by the match | Keep the existing `'renders nothing disabled at idle'` test **untouched** — the modal is closed there, so the DMI-81 invariant still holds. Add a new test, modal open: the confirm button `toBeDisabled()` at empty/partial/different input and `toBeEnabled()` at the profile's own `email`; Cancel and the input stay enabled throughout. |
| 9 | regression | The existing change-password and activity-disclosure tests must pass **unmodified**. |

### `frontend/src/pages/Login.tsx` → `frontend/src/pages/Login.test.tsx` (extend)

**Mirror:** `Login.test.tsx:205-235` — the two `renderLoginApp({ passwordReset: true })` tests —
re-run with `{ accountDeleted: true }`.

| # | Assertion |
|---|---|
| 1 | With `state.accountDeleted`, `login-success` renders `"Your account has been deleted."`, has `role="status"`, and is the **only** `role="status"` element (`getByRole('status')` must not throw). |
| 2 | The router state is scrubbed: `location-state` reads `null`, `location-url` stays `/login`, and the note **remains** on screen after the scrub. |
| 3 | The note takes focus, and `Tab` reaches Email then Password — mirror `'gives the reset-success status focus…'`. |
| 4 | Transience: `renderLoginApp()` with **no** state renders no `login-success` region — this is the reload proxy, since a remount without router state is exactly what a reload produces. |
| 5 | The two notes do not collide: with `{ passwordReset: true }` the existing copy still renders (existing test, unmodified). |

### `frontend/src/auth/SessionProvider.tsx` → `frontend/src/auth/SessionProvider.test.tsx` (extend)

**Mirror:** `SessionProvider.test.tsx:85` and `:109` — the two `signOut` teardown tests — for
their assertion shape (token cleared, cache emptied, `/login` with `replace`).

| # | Assertion |
|---|---|
| 1 | On `204`: `deleteAccount()` clears the access token, empties the `['session']` cache entry, and navigates to `/login` with `replace`, carrying `state.accountDeleted === true`. |
| 2 | It fires **`DELETE /users/me` and no `POST /auth/logout`** — the explicit difference from `signOut`. |
| 3 | On `409`: the promise **rejects**, the token is still present, the `['session']` entry is still populated, `status` is still `authenticated`, and no navigation happened. This is the test that would catch someone copying `signOut`'s `try/catch/finally`. |
| 4 | `useSession()` exposes `deleteAccount` as a function (extends the existing context-shape test). |

### `frontend/src/test/mswHandlers.ts`

No test of its own. The added default `http.delete(\`${baseURL}/users/me\`)` → `204` keeps
`onUnhandledRequest: 'error'` satisfied for any test that reaches the request without its own
override.

### Not tested here

- `DELETE /api/v1/users/{user_id}` and the Users screen — DMI-90. `ConfirmByTyping` test #11 is
  the only forward-looking assertion, and it exercises props, not that route.
- The backend's own last-admin behaviour — covered by `specs/029-account-removal-api/`.
