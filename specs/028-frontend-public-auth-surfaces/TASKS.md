# Tasks — Frontend public auth surfaces (`028-frontend-public-auth-surfaces`)

7 tasks. **Unblocked now: #1, #4, #6**

> **Frontend feature — do not spawn the Python agents.** The blast radius is `frontend/` only.
> Spawn **`frontend-test-engineer`** (Vitest + Testing Library + MSW) and
> **`frontend-code-reviewer`**, not `test-engineer` / `code-reviewer`. The gate for every task,
> run from `frontend/`, is:
>
> ```
> npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
> ```
>
> No repo-wide formatter, and no `uv run` anything. `ScanOrchestrator` / `ScanRunner` are untouched,
> so the CLAUDE.md threading rule does not apply.
>
> **`frontend/src/App.tsx`, `frontend/src/test/mswHandlers.ts`, and `frontend/src/api/auth.ts` are
> each edited by several tasks.** The orchestrator runs tasks one at a time, so this is safe — but a
> coder must **append** to these files and never rewrite them, or it will delete a prior task's work.
> Every task's route/handler/function additions are additive.
>
> Governing specs: `TRUTH.md` (business rules, acceptance criteria), `ARCHITECTURE.md` (naming table
> §3, constraints §4, testing §5), `DESIGN.md` (mockups, exact copy, states, `data-testid` values).
> Copy is **approved and verbatim** — implementations must not invent replacement strings.

---

## Task 1: Forgot password screen, route, and API function
- **Description**: Build the `/forgot-password` screen per `DESIGN.md` §Forgot password — idle,
  submitting, recoverable-failure, and confirmed states — and register its public route in
  `App.tsx` outside `RequireSession`. This is the feature's simplest form and establishes the four
  patterns every later form reuses: the real `<form>` + in-handler in-flight guard, the message
  lifetime rule (`DESIGN.md` §States — clear all messages at the top of the submit handler, never on
  typing), the recoverable service-error state, and the approved copy tables. The `204` confirmation
  **replaces** the form and is byte-for-byte identical for known and unknown addresses, interpolating
  only the address the user typed — this is the anti-enumeration boundary in `TRUTH.md`.
- **Absorbed**: `forgotPassword` in `api/auth.ts` (a thin typed wrapper on the bare `authClient` —
  no branching of its own, so it carries no test independently of the page that calls it); the
  `POST /auth/forgot-password` MSW handler (a fixture, tested through its first consumer).
- **Dependencies**: —
- **Target Files**: [`frontend/src/pages/ForgotPassword.tsx`,
  `frontend/src/pages/ForgotPassword.test.tsx`, `frontend/src/api/auth.ts`,
  `frontend/src/test/mswHandlers.ts`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`]
- **Tests**: `ForgotPassword.test.tsx` proves non-enumeration (a known and an unknown address produce
  identical confirmation structure and copy), that the request body is exactly `{ email }`, that the
  form is gone after `204`, that an in-flight request cannot be submitted twice, that network/`5xx`
  retains the email and restores the action, and that `Back to sign in` targets `/login`.
  `App.test.tsx` gains a proof that `/forgot-password` renders while anonymous.
- **Success Criteria**:
  - `/forgot-password` renders inside `AuthShell` with no nav or log-out control, for an anonymous
    visitor and after a failing boot refresh.
  - Both a known and an unknown address render the `forgot-success` container with identical wording
    apart from the interpolated address; `forgot-form` and `forgot-email` are absent afterward.
  - The captured request body is exactly `{ email }` — no extra properties.
  - `forgot-submit` reads `Sending…` and is disabled in flight; a second submit attempt issues no
    second request.
  - Network failure renders `forgot-error` with `Couldn't reach Dmitri. Try again in a moment.`,
    preserves the typed email, and re-enables the action.
  - `data-testid` values match `DESIGN.md` exactly: `forgot-idle`, `forgot-form`, `forgot-email`,
    `forgot-submit`, `forgot-error`, `forgot-success`, `forgot-back`.
  - `forgotPassword` uses the bare `authClient` from `./instances`; `auth.ts` still does not import
    `./client`.
  - Email is focused on mount; recoverable failure returns focus to Email; the confirmation heading
    takes programmatic focus.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Login forgot-password link and transient reset-success status
- **Description**: Add the `Forgot password?` link to `Login.tsx` targeting `/forgot-password`, and
  teach Login to capture the `{ passwordReset: true }` router-state marker into component state,
  clear it from the history entry, and render
  `Password set. Sign in with your new password.` as `role="status"` above the existing form
  (`ARCHITECTURE.md` §2.4, `DESIGN.md` §Success edge on Login). **`Login.tsx` early-returns on
  `authenticated` and `booting` at `Login.tsx:19-25` — the new `useState`/`useEffect` pair must be
  declared above those returns or React throws on changed hook order.** Because the message lives in
  component state, clearing history state cannot blank it, and a manual refresh correctly loses it.
  This task lands before Reset password so that screen has a real success destination to assert.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/src/pages/Login.tsx`, `frontend/src/pages/Login.test.tsx`]
- **Tests**: `Login.test.tsx` replaces its current `ships no forgot-password link` assertion
  (`Login.test.tsx:168-178`) with the real link expectation, and adds coverage that the reset marker
  renders the status, that it is transient, and that a normal Login visit never shows it. All
  existing login/session assertions stay green.
- **Success Criteria**:
  - A link reading `Forgot password?` is present and targets `/forgot-password`.
  - Rendering Login with router state `{ passwordReset: true }` shows `login-success` with the exact
    approved copy, using `role="status"` (not `role="alert"`).
  - Rendering Login with no router state shows no `login-success` element.
  - The success marker is history state, not a query string — the URL after navigation carries no
    success parameter.
  - The success region takes programmatic focus, after which Tab reaches the existing Login fields in
    their normal order.
  - No hook is declared below Login's existing early returns; `npm run lint` reports no
    rules-of-hooks violation.
  - Every pre-existing test in `Login.test.tsx` still passes.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: Reset password screen, route, and API function
- **Description**: Build the `/reset-password` screen per `DESIGN.md` §Reset password and register
  its public route. The screen reads `token` from the query string with `useSearchParams` and never
  renders it. There is **no pre-submit lookup contract for reset**, so an absent token is dead
  immediately while a present-but-dead token is discovered only when the request returns
  `410 invalid_reset_token` — both render the same terminal state with `Request a new link` pointing
  at `/forgot-password`. Success is the sharp edge: `204` must create **no session** — it must not
  call `setAccessToken`, `refresh`, `signIn`, or `acceptInvitation` — and navigates with
  `replace: true` to `/login` carrying the marker Task 2 consumes.
- **Absorbed**: `resetPassword` in `api/auth.ts` (thin typed wrapper on `authClient`, exercised
  end-to-end by this page's tests); the `POST /auth/reset-password` MSW handler.
- **Dependencies**: Task 1, Task 2
- **Target Files**: [`frontend/src/pages/ResetPassword.tsx`,
  `frontend/src/pages/ResetPassword.test.tsx`, `frontend/src/api/auth.ts`,
  `frontend/src/test/mswHandlers.ts`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`]
- **Tests**: `ResetPassword.test.tsx` covers the missing token, confirmation mismatch, policy `400`,
  dead-token `410`, service failure, duplicate-submit prevention, and the full `204` → Login journey
  including the assertion that no access token was created or mutated. `App.test.tsx` gains a proof
  that `/reset-password` renders while anonymous.
- **Success Criteria**:
  - `/reset-password` with no `?token=` renders `reset-dead` and issues **zero** network requests.
  - A confirmation mismatch renders `reset-confirm-error` and issues zero requests.
  - A successful request body is exactly `{ token, new_password }` — the confirmation value is never
    sent.
  - `400 password_policy_violation` renders `reset-password-error` beside New password and keeps
    `reset-form` mounted; `410 invalid_reset_token` removes `reset-form` and renders `reset-dead`
    with `reset-request` targeting `/forgot-password`.
  - After `204`: the access token in `tokenStore` is unchanged (still absent), the route is `/login`
    via `replace`, and `login-success` renders with the approved copy.
  - Network/`5xx` renders `reset-error`, preserves both entered values, and re-enables the action;
    an in-flight submit cannot be duplicated.
  - Messages persist while the user edits and clear only at the start of the next submit.
  - Both password inputs use `autocomplete="new-password"`; New password is focused on mount with a
    token; the dead-state heading takes focus when there is none.
  - `data-testid` values match `DESIGN.md` exactly.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Settings screen, change-password client, and guarded route
- **Description**: Build `/settings` per `DESIGN.md` §Settings — the voluntary change-password form
  only, **no profile section** — and register it inside the existing `RequireSession` + `AppShell`
  branch of `App.tsx`. Create `frontend/src/api/passwords.ts` exporting `changePassword`, importing
  `apiClient` from **`./client`** and never from `./instances`: `ARCHITECTURE.md` §2.2 explains this
  is not stylistic, because putting it in `auth.ts` either creates a real module cycle
  (`client.ts` already imports `refresh` from `auth.ts`) or silently bypasses the Bearer and
  refresh-retry interceptors. The session-safety rule is the point of this screen: a wrong current
  password is contractually `400 wrong_current_password`, so it must render as a field error and
  must never log the user out, trigger a refresh, or navigate.
- **Absorbed**: `api/passwords.ts` (a one-function module whose only observable behaviour — reaching
  the interceptors — is proved by the `authHeader.test.ts` case and the Settings suite); the
  `POST /auth/change-password` MSW handler.
- **Dependencies**: —
- **Target Files**: [`frontend/src/pages/Settings.tsx`, `frontend/src/pages/Settings.test.tsx`,
  `frontend/src/api/passwords.ts`, `frontend/src/api/authHeader.test.ts`,
  `frontend/src/test/mswHandlers.ts`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`]
- **Tests**: `Settings.test.tsx` covers both roles, the request payload, mismatch, wrong-current,
  policy, service failure, duplicate-submit, in-place success, message persistence, and a genuine
  `401` proving the existing interceptor still refreshes once and retries. `authHeader.test.ts` gains
  an isolated-module case for `passwords.ts`. `App.test.tsx` proves `/settings` is guarded.
- **Success Criteria**:
  - `/settings` redirects an anonymous visitor to `/login` and never flashes Settings while session
    status is `booting`; both the admin and viewer profiles open it and see the same form.
  - The request body contains exactly `current_password` and `new_password` — the confirmation value
    is never sent.
  - A client mismatch renders `settings-confirm-error` and issues zero requests.
  - `400 wrong_current_password` renders `settings-current-error`, performs **zero** refresh calls,
    leaves the access token and session intact, and leaves the route at `/settings`.
  - `400 password_policy_violation` renders `settings-new-error` and also stays on `/settings`.
  - `204` clears all three password fields, renders `settings-success` with `role="status"`, and
    stays on `/settings` with the session intact.
  - A settled message survives editing and is cleared only when the next submit begins.
  - Network/`5xx` renders `settings-error` and restores a usable form; an in-flight submit cannot be
    duplicated.
  - A genuine `401` still drives one refresh + retry; when refresh fails, the existing session-expiry
    event clears the session and navigates to Login.
  - `authHeader.test.ts` proves `passwords.ts`, imported in isolation after `vi.resetModules()`,
    sends `Authorization: Bearer …`. The existing `captureAuthorization` helper registers `http.get`
    only, so give it a method parameter or add a POST sibling — **do not convert the three existing
    GET cases**.
  - No profile fields, display name, or email input is rendered anywhere on the page.
  - `data-testid` values match `DESIGN.md` exactly.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: TopBar Settings link and two-item nav layout
- **Description**: Add a `Settings` `NavLink` to `TopBar.tsx` and end the transitional one-item
  centring. `docs/ui/SCREENS.md` §App shell states the centring is transitional and that "the feature
  that adds the second nav item reverts it"; `TopBar.tsx:8-13` carries the matching comment naming
  the exact change — drop the `grid-cols-[1fr_auto_1fr]` for `flex justify-between` and give the nav
  `flex-1` so `Home` and `Settings` sit beside the wordmark with Log out at the right. Settings is
  visible to **both** admin and viewer. **The bar has no `Users` link today and this feature does not
  add one.** Sequenced after Task 4 so the destination exists before the link to it does.
- **Dependencies**: Task 4
- **Target Files**: [`frontend/src/components/TopBar.tsx`,
  `frontend/src/components/TopBar.test.tsx`]
- **Tests**: `TopBar.test.tsx` asserts two enabled nav links for both roles, their exact hrefs,
  active indication on `/settings`, the absence of any disabled state, and that Log out still calls
  `signOut`.
- **Success Criteria**:
  - Exactly two nav links render — `Home` → `/` and `Settings` → `/settings` — for both the admin and
    the viewer profile.
  - `Settings` carries `data-testid="nav-settings"`.
  - Rendering at `/settings` gives the Settings link the active accent treatment and `Home` the muted
    one; rendering at `/` reverses it.
  - No nav item renders `aria-disabled` or a disabled attribute — absent, not disabled.
  - The stale centring comment at `TopBar.tsx:8-13` is removed along with the layout it describes.
  - Log out remains present, keyboard reachable, and still calls `signOut`.
  - No `Users` link is added.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Session establishment for invite acceptance
- **Description**: Extend `SessionContextValue` in `SessionProvider.tsx` with
  `acceptInvitation(request: AcceptInviteRequest): Promise<void>`, and add `acceptInvite` to
  `api/auth.ts` — it posts on the credentialed `authClient` so the httpOnly refresh cookie is
  received, and writes the returned `access_token` through `setAccessToken` exactly as `login` and
  `refresh` do. `acceptInvitation` then follows the same post-authentication sequence as `signIn`
  (`SessionProvider.tsx:69-74`): `setEnabled(true)`, invalidate `['session']`, and
  `navigate('/', { replace: true })`. **Factor that repeated sequence into one private provider
  helper shared by both** — do not duplicate it, and do not create a second context or a second
  token store. `GET /users/me` remains the only identity and role source, and an accepted invite must
  never route through Login.
- **Absorbed**: `acceptInvite` in `api/auth.ts` (its only real behaviour — storing the token and
  carrying credentials — is observable through the provider that calls it); the
  `POST /invites/accept` MSW handler.
- **Dependencies**: —
- **Target Files**: [`frontend/src/auth/SessionProvider.tsx`,
  `frontend/src/auth/SessionProvider.test.tsx`, `frontend/src/api/auth.ts`,
  `frontend/src/test/mswHandlers.ts`]
- **Tests**: `SessionProvider.test.tsx` proves invite acceptance stores the access token, refetches
  `/users/me`, exposes the new user with `status: 'authenticated'`, and navigates to `/` with
  `replace`. Every existing boot, login, and logout guarantee stays green.
- **Success Criteria**:
  - `useSession()` exposes `acceptInvitation` alongside `status`, `user`, `signIn`, and `signOut`.
  - Calling it with a valid request stores the returned `access_token`, drives a `GET /users/me`, and
    transitions status to `authenticated` with the returned profile.
  - Navigation lands on `/` with `replace: true` and Login is never rendered in between.
  - The post-authentication sequence exists **once** in the provider and is called by both `signIn`
    and `acceptInvitation`.
  - `acceptInvite` posts on `authClient` (so `withCredentials` carries the refresh cookie);
    `auth.ts` still does not import `./client`.
  - No second React context, token store, or Axios instance is introduced.
  - All pre-existing `SessionProvider.test.tsx` assertions still pass.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Accept invite screen, lookup, route, and signed-in guard
- **Description**: Build `/invite` per `DESIGN.md` §Accept invite and register its public route. The
  page owns one TanStack Query keyed `['invite', 'lookup', token]` with `retry: false`, enabled only
  when the token is non-empty **and** session status is `anonymous`. Four things carry real risk
  here. (1) **The lookup response's `email` is typed contract data that is neither rendered nor sent
  back** — `AcceptInviteRequest` is `additionalProperties: false` and the field was removed in spec
  027, so sending it now returns `422`. There is no email input on this screen. (2) The password form
  is **not mounted until lookup succeeds**, so a `410` never flashes a form. (3) All dead-token cases
  — absent token, lookup `410`, accept `410` — converge on one terminal state with **no retry
  action**, because only an administrator can issue a new invite; a network or `5xx` failure is a
  *different*, retryable state and must never be presented as a dead token. (4) An authenticated
  visitor gets the signed-in block instead: acceptance returns a fresh `LoginResponse` and refresh
  cookie, so letting it through would silently re-identify and possibly demote them. That block makes
  **no lookup request**, leaving the invitation untouched, and its action calls the existing
  `signOut`. The greeting reads `You've been invited to {org_name} with the {role} role.` — the
  article was dropped because `role` is the enum `admin | viewer` and "as a admin" is ungrammatical.
- **Absorbed**: `lookupInvite` in `api/auth.ts` (thin typed wrapper on `authClient`, exercised
  end-to-end by this page); the `POST /invites/lookup` MSW handler.
- **Dependencies**: Task 6
- **Target Files**: [`frontend/src/pages/AcceptInvite.tsx`,
  `frontend/src/pages/AcceptInvite.test.tsx`, `frontend/src/api/auth.ts`,
  `frontend/src/test/mswHandlers.ts`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`]
- **Tests**: `AcceptInvite.test.tsx` covers the missing token, the signed-in and booting branches,
  the live-invite greeting, StrictMode deduplication, both `410` paths, mismatch, both `400` codes,
  the `201` journey to Home, and service-failure retry. `App.test.tsx` gains a proof that `/invite`
  renders while anonymous.
- **Success Criteria**:
  - A missing token renders `invite-dead` and issues **zero** lookup requests.
  - An authenticated visitor with a live token renders `invite-signed-in`, issues **zero** lookup and
    **zero** accept requests, renders no password form, and its `invite-sign-out` action calls the
    existing `signOut`. A `booting` session renders `invite-loading` and issues no request.
  - A live token posts exactly `{ token }`, renders `org_name` and the role in the approved
    sentence, and renders **no email input and no email text anywhere in the DOM**.
  - A re-render under StrictMode performs one effective lookup; after a service failure,
    `invite-retry` is the only path back.
  - Lookup `410 invalid_invite_token` and accept `410` render the *same* `invite-dead` state with no
    retry control, and `invite-form` is absent from the DOM.
  - A confirmation mismatch issues zero accept calls and renders `invite-confirm-error`.
  - Acceptance posts exactly `{ token, password }` — the lookup response's email is never sent.
  - `400 password_policy_violation` renders `invite-password-error` and keeps the form;
    `400 email_already_registered` renders `invite-account-error` with `invite-sign-in` targeting
    `/login`, and keeps the form and entered values.
  - `201` stores the token, refreshes the profile, and navigates to `/` — Login is never rendered.
  - Network/`5xx` renders `invite-error` and restores a usable form with no false success; an
    in-flight submit cannot be duplicated.
  - Both password inputs use `autocomplete="new-password"`; Password is focused only after a
    successful lookup; dead and signed-in headings take programmatic focus via `tabindex="-1"`.
  - `data-testid` values match `DESIGN.md` exactly, including `invite-signed-in` and
    `invite-sign-out`.
  - The frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 Forgot password ──► #2 Login edges ──► #3 Reset password
#4 Settings ──► #5 TopBar nav
#6 Session acceptInvitation ──► #7 Accept invite
```

Three independent chains. #1, #4, and #6 are unblocked immediately; the orchestrator runs one task
at a time, so the shared edits to `App.tsx`, `api/auth.ts`, and `mswHandlers.ts` never collide —
provided each coder appends rather than rewrites.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Forgot password screen, route, and API function | COMPLETED |
| 2 | Login forgot-password link and transient reset-success status | COMPLETED |
| 3 | Reset password screen, route, and API function | COMPLETED |
| 4 | Settings screen, change-password client, and guarded route | COMPLETED |
| 5 | TopBar Settings link and two-item nav layout | COMPLETED |
| 6 | Session establishment for invite acceptance | COMPLETED |
| 7 | Accept invite screen, lookup, route, and signed-in guard | COMPLETED |

## Acceptance-criteria coverage

Every row in `TRUTH.md` §Acceptance criteria maps to at least one task.

| TRUTH scenario | Task |
|---|---|
| Live invite is identified | 7 |
| Invite lookup is non-consuming | 7 |
| Signed-in visitor cannot accept an invite | 7 |
| Invite acceptance signs in | 6, 7 |
| Dead invite is terminal | 7 |
| Invite password is rejected inline | 7 |
| Invite confirmation mismatch | 7 |
| Invited address already has an account | 7 |
| Forgot-password is non-enumerating | 1 |
| Reset succeeds without a session | 2, 3 |
| Dead reset link is terminal | 3 |
| Reset password is rejected inline | 3 |
| Wrong current password preserves session | 4 |
| Voluntary password change succeeds in place | 4 |
| Settings is available to both roles | 4, 5 |
| Settled messages survive editing | 1, 3, 4, 7 |
| Submitting state prevents duplicate work | 1, 3, 4, 7 |
| Network or server failure is recoverable | 1, 3, 4, 7 |
