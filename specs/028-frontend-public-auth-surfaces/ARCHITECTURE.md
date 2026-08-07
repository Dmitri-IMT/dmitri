# ARCHITECTURE — Frontend public auth surfaces (DMI-87)

> **Single frontend layer.** This feature consumes already-shipped auth and invite contracts. It
> changes no backend route, OpenAPI schema, database object, hardware-agent path, scan pipeline,
> `ScanPayload`, nmap flag, or exit code. The `ScanRunner` / `ScanProgressScreen` integration rule
> therefore does not apply. There is no `INTEGRATION.md`.
>
> `docs/ui/SCREENS.md` and `docs/ui/FLOWS.md` govern screen behaviour and copy. Where the Linear
> issue text is stale, the current OpenAPI contract governs transport: invite lookup is
> `POST /api/v1/invites/lookup` with `{ token }`; acceptance is
> `POST /api/v1/invites/accept` with `{ token, password }`; there is no email field in the
> acceptance form or request.

---

## 1. System context

```text
emailed invite ──> /invite?token=… ──> lookup ──> accept ──> SessionProvider ──> Home
                                               LoginResponse + refresh cookie

/login ──> /forgot-password ──> reset email ──> /reset-password?token=… ──> /login
                                                                        success state

authenticated Home ──> /settings ──> change password ──> remain on Settings
```

The React 19 SPA already has the required foundations:

- `frontend/src/api/instances.ts` creates `authClient` with `withCredentials: true` and
  `apiClient` without cookies;
- `frontend/src/api/client.ts` arms `apiClient` with the Bearer request interceptor and the
  single-flight `401 -> refresh -> retry` response interceptor;
- `frontend/src/api/auth.ts` owns refresh-cookie operations and stores access tokens in
  `frontend/src/api/tokenStore.ts`;
- `frontend/src/auth/SessionProvider.tsx` owns the `['session']` query, identity from
  `GET /users/me`, navigation on session expiry, and the login/logout actions;
- `frontend/src/App.tsx` owns the route table, with public routes outside `RequireSession` and
  authenticated routes inside `RequireSession` and `AppShell`.

This feature extends those seams rather than creating another auth store, router, Axios instance,
or form framework. Accept invite, Forgot password, and Reset password use the existing
`AuthShell`. Settings uses the existing guarded `AppShell`. Adding Settings is the second inside
navigation destination, so `TopBar` must end the temporary one-item centring and place `Home` and
`Settings` beside the wordmark, with Log out at the right.

No backend or contract work is blocked. Transactional email delivery is outside this frontend
feature; the frontend deliberately treats the forgot-password `204` as receipt of a request, not
proof that an account or delivered email exists.

---

## 2. Data model and contracts

### 2.1 Endpoints consumed

Path tails below are relative to the existing `${VITE_API_URL}/api/v1` base URL. Every request and
success body type aliases `components['schemas'][...]` from
`frontend/src/types/openapi.d.ts`; no handwritten API interface is permitted.

| Operation | Client | Generated request / response | Required UI branches |
|---|---|---|---|
| `POST /invites/lookup` | `authClient` | `InviteLookupRequest { token }` -> `200 InviteLookupResponse { email, role, org_name }` | `410 invalid_invite_token` -> terminal dead-invite state; network/unexpected failure -> recoverable lookup error and Retry. The read is non-consuming. |
| `POST /invites/accept` | `authClient` | `AcceptInviteRequest { token, password }` -> `201 LoginResponse` plus httpOnly refresh cookie | Store `access_token`, activate the existing session query, navigate `/`; `400 password_policy_violation` -> Password; `400 email_already_registered` -> form-level sign-in path; `410 invalid_invite_token` -> terminal dead state. **Never send lookup email.** |
| `POST /auth/forgot-password` | `authClient` | `ForgotPasswordRequest { email }` -> `204` | Every `204`, for known and unknown addresses alike, replaces the form with the same conditional confirmation; network/unexpected failure retains the form. |
| `POST /auth/reset-password` | `authClient` | `ResetPasswordRequest { token, new_password }` -> `204` | `400 password_policy_violation` -> New password; `410 invalid_reset_token` -> terminal dead-link state. Success creates no session and navigates to Login with transient success state. |
| `POST /auth/change-password` | intercepted `apiClient` | `ChangePasswordRequest { current_password, new_password }` -> `204` | `400 wrong_current_password` -> Current password; `400 password_policy_violation` -> New password; success stays on Settings. A genuine authorization `401` alone enters the existing refresh/retry/session-expiry pipeline. |

`Confirm password` / `Confirm new password` are client-only values. A mismatch prevents the HTTP
call. OpenAPI already marks the request objects `additionalProperties: false`, so confirmation and
lookup email must not be added to any body.

### 2.2 API module placement

Extend `frontend/src/api/auth.ts` with these generated-type functions:

- `lookupInvite(request: InviteLookupRequest): Promise<InviteLookupResponse>`;
- `acceptInvite(request: AcceptInviteRequest): Promise<LoginResponse>` — writes the returned
  `access_token` through `setAccessToken`, exactly like `login` and `refresh`;
- `forgotPassword(request: ForgotPasswordRequest): Promise<void>`;
- `resetPassword(request: ResetPasswordRequest): Promise<void>`.

All four use the bare `authClient` from `instances.ts`. That is intentional: invite acceptance
must receive the refresh cookie, and public auth requests must not enter the Bearer `401` retry
interceptor. `auth.ts` must continue not to import `client.ts`, because `client.ts` already imports
`refresh` from `auth.ts`; reversing that edge would create a real module cycle.

Create `frontend/src/api/passwords.ts` for
`changePassword(request: ChangePasswordRequest): Promise<void>`. It imports `apiClient` from
`./client`, never from `./instances`, so it receives both the Authorization header and the existing
single-flight refresh behaviour. This separate module is not optional: putting
`changePassword` in `auth.ts` either creates the cycle above or silently bypasses the interceptor.

Pages inspect failures with `isAxiosError<components['schemas']['ErrorResponse']>` and switch on
both HTTP status and the contract-pinned `error.code`. They do not display backend `message` text;
screen copy remains the approved copy in `SCREENS.md` / `DESIGN.md`. Unexpected statuses, `5xx`,
and network failures use the designed recoverable service state and never become false field
errors.

### 2.3 Session establishment

Extend `SessionContextValue` in `frontend/src/auth/SessionProvider.tsx` with:

```text
acceptInvitation(request: AcceptInviteRequest): Promise<void>
```

`acceptInvitation` calls the API-layer `acceptInvite`, then follows the same established sequence
as `signIn`: `setEnabled(true)`, invalidate `['session']`, and
`navigate('/', { replace: true })`. Factor that repeated post-authentication sequence into one
private provider helper; do not create a second context or duplicate token state. `GET /users/me`
remains the only identity and role source.

Invite acceptance must never navigate through Login. Reset-password success must never call
`setAccessToken`, `refresh`, `signIn`, or `acceptInvitation`.

### 2.4 Query and route state

`AcceptInvite` reads `token` with `useSearchParams` and owns one TanStack Query:

```text
key:       ['invite', 'lookup', token]
queryFn:   lookupInvite({ token })
enabled:   token is non-empty AND session status is 'anonymous'
retry:     false
```

TanStack Query supplies StrictMode-safe request deduplication for the on-mount lookup. A missing
token enters the dead state without a request. Lookup `410` enters the same dead state. A lookup
network/unexpected failure retains the query and calls its `refetch` from Retry. The password form
is not mounted until lookup succeeds. An acceptance `410` also replaces the form with that same
dead state; no automatic lookup is performed again.

Reset password performs no pre-submit token lookup because no such contract exists. It reads the
query token locally; an absent token is immediately dead, while an invalid/expired/used token is
known only when reset returns `410`.

Reset success navigates with `replace: true` to `/login` and a small router state marker such as
`{ passwordReset: true }`. `Login` captures that marker into component state, clears it from the
history entry, and renders the approved `role="status"` message for the lifetime of that Login
mount. It must not add a success token to the URL or a global notification store.

`Login.tsx` early-returns on `authenticated` and `booting` (`Login.tsx:19-25`). The capture-and-clear
`useState`/`useEffect` pair must be declared **above** those returns, or the hook order changes
between renders and React throws. The clear is a `navigate(location.pathname, { replace: true })`
that drops `state`; because the message already lives in component state, clearing history cannot
blank the visible message, and a manual refresh correctly loses it.

**Signed-in visitors.** `POST /invites/accept` returns a fresh `LoginResponse` and a new refresh
cookie, so an authenticated visitor who accepts an invite silently replaces their own identity —
including a demotion from admin to viewer with no explanation. `AcceptInvite` therefore reads
`status` from `useSession` and, when it is `authenticated`, renders the signed-in block from
`DESIGN.md` instead: the lookup query stays disabled, no request is made, and the invitation is not
touched. Its action calls the existing `signOut`, which already navigates to `/login`; the emailed
link still works on the next visit.

This guard belongs to `AcceptInvite` alone, not to a shared anonymous-only route element. `/invite`,
`/forgot-password`, and `/reset-password` all stay public in the route table. Forgot and reset
cannot swap a session — reset issues no token at all — and a signed-in user on a second device is a
legitimate reset case, so neither screen gains a status branch. `Login` retains its existing
authenticated redirect.

While `status` is `booting`, `AcceptInvite` renders its lookup-loading card and issues no request,
so the form can never flash before the session resolves.

### 2.5 Route table and interceptor behaviour

`frontend/src/App.tsx` gains these exact entries:

```text
/invite                 public, AuthShell inside AcceptInvite
/forgot-password        public, AuthShell inside ForgotPassword
/reset-password         public, AuthShell inside ResetPassword
/settings               inside RequireSession -> AppShell
```

The existing `/login`, `/`, and protected catch-all semantics remain unchanged. In particular, do
not move `*` outside the protected branch and do not add redirects that rewrite unknown URLs.

The response interceptor in `frontend/src/api/client.ts` needs no route exception or code change:

- wrong current password is contractually `400`, so it never enters the interceptor and cannot
  trigger refresh, `emitSessionExpired`, cache clearing, or `/login` navigation;
- an actual `401` from change-password is an Authorization-header/session failure, so the existing
  one-refresh retry is correct;
- lookup, accept, forgot, and reset use `authClient`, which intentionally has no interceptors.

### 2.6 Constants and environment

No new environment variable, storage key, password-policy constant, color token, or runtime
dependency is introduced. The minimum of 12 is already in OpenAPI and is also represented by
native input validation; server policy remains authoritative. Query keys and router-state markers
are colocated with the page/provider that owns them.

---

## 3. New files and naming (mandatory)

Every implementation touch is listed. Paths not listed here are out of scope.

| Path | New / edit | Exact names and responsibility |
|---|---|---|
| `frontend/src/api/auth.ts` | edit | Add `lookupInvite`, `acceptInvite`, `forgotPassword`, `resetPassword` using generated schemas and `authClient`; only `acceptInvite` stores a returned access token. Keep the `auth.ts -> instances.ts` import direction. |
| `frontend/src/api/passwords.ts` | **new** | Export `changePassword`; type with `ChangePasswordRequest`; import intercepted `apiClient` from `./client`. |
| `frontend/src/auth/SessionProvider.tsx` | edit | Extend `SessionContextValue` with `acceptInvitation`; share the existing post-auth session activation between `signIn` and `acceptInvitation`; navigate accepted invite directly to `/`. |
| `frontend/src/auth/SessionProvider.test.tsx` | edit | Prove invite acceptance stores the token, refetches `/users/me`, exposes the new user, and replaces navigation with Home; existing boot/login/logout guarantees remain green. |
| `frontend/src/App.tsx` | edit | Register public `/invite`, `/forgot-password`, `/reset-password`; register protected `/settings` under the existing `RequireSession` + `AppShell` branch. |
| `frontend/src/App.test.tsx` | edit | Route-level proofs for all three public routes while anonymous, Settings protection, and authenticated Settings access; preserve existing catch-all tests. |
| `frontend/src/pages/AcceptInvite.tsx` | **new** | Default `AcceptInvite`; query token parsing; `['invite','lookup',token]` query; loading/ready/dead/retry states; fully typed lookup response with email kept out of the UI; form validation; `acceptInvitation` call; signed-in block that disables the lookup and offers `signOut`. |
| `frontend/src/pages/AcceptInvite.test.tsx` | **new** | Full lookup and acceptance state/contract coverage listed in section 5. |
| `frontend/src/pages/ForgotPassword.tsx` | **new** | Default `ForgotPassword`; idle/submitting/recoverable/confirmed states; retain submitted email for identical conditional confirmation. |
| `frontend/src/pages/ForgotPassword.test.tsx` | **new** | Non-enumeration, duplicate-submit, failure recovery, and navigation tests. |
| `frontend/src/pages/ResetPassword.tsx` | **new** | Default `ResetPassword`; query token parsing; mismatch/policy/dead/service states; `204` navigation state to Login without session creation. |
| `frontend/src/pages/ResetPassword.test.tsx` | **new** | Missing/invalid token, request body, mismatch, policy, service failure, and reset-to-Login coverage. |
| `frontend/src/pages/Settings.tsx` | **new** | Default `Settings`; change-password form only; exact `400` code-to-field mapping; in-place `204` success; no profile UI. |
| `frontend/src/pages/Settings.test.tsx` | **new** | Both roles, payload, mismatch, wrong-current, policy, real session failure, service failure, duplicate-submit, and in-place success. |
| `frontend/src/pages/Login.tsx` | edit | Add the `/forgot-password` link; capture/reset the password-reset router state and render the approved success status above the existing form. |
| `frontend/src/pages/Login.test.tsx` | edit | Replace the current “no forgot-password link” assertion with the real link/route expectation; add transient reset-success coverage; retain all login session tests. |
| `frontend/src/components/TopBar.tsx` | edit | Add `NavLink` to `/settings` with `data-testid="nav-settings"`; change the temporary three-track centred layout to the Foundations two-item left-adjacent layout. Settings is present for admin and viewer; do not add Users. |
| `frontend/src/components/TopBar.test.tsx` | edit | Assert Home + Settings for both roles, Settings active state/navigation, no disabled controls, and unchanged logout behaviour. |
| `frontend/src/api/authHeader.test.ts` | edit | Add an isolated-module proof that `passwords.ts` sends Bearer on change-password. This guards the required `./client` import. The existing `captureAuthorization` helper registers `http.get` only; change-password is a `POST`, so the helper needs a method parameter or a POST sibling. Do not convert the existing three GET cases. |
| `frontend/src/test/mswHandlers.ts` | edit | Add generated-type fixtures and default successful handlers for invite lookup/accept, forgot/reset, and change-password. Individual page tests override statuses/codes. |

No new shared password-field component is required. The three forms share primitives but differ in
labels, autocomplete, field count, focus destination, error routing, and terminal behaviour; a
configurable universal auth form would hide those differences. Reuse `AuthShell`, `Ornament`,
`Button`, `Input`, and `Label` unchanged. `frontend/src/types/openapi.d.ts` already contains every
required current schema and operation; consume it but do not hand-edit or regenerate it as part of
this no-contract-change feature.

All constructor and call sites of the changed session/provider route are accounted for:
`main.tsx`, `renderWithProviders.tsx`, `App.test.tsx`, `Login.test.tsx`, and
`SessionProvider.test.tsx` continue constructing `SessionProvider` without a new prop; consumers
continue using `useSession`, with `AcceptInvite` as the only new caller of `acceptInvitation`.

---

## 4. Constraints

- **Contract authority:** request and response types come only from generated OpenAPI types.
  Never restore the stale `AcceptInviteRequest.email` field.
- **Token handling:** route tokens are read from the browser query string, sent in JSON bodies,
  never copied into API paths, logs, visible UI, local storage, or session storage.
- **Session handling:** access token remains memory-only; refresh token remains httpOnly and is
  received only through credentialed auth calls. No JWT decoding.
- **Anti-enumeration:** forgotten-password confirmation is byte-for-byte equivalent in structure
  and wording for any submitted address. Invite/reset unknown, expired, and used tokens share their
  respective terminal states.
- **Error ownership:** client mismatch makes no request; pinned `400` codes target fields; token
  `410`s remove forms; unexpected failures leave a retryable form/page. Never show raw backend
  messages.
- **Message lifetime:** every submit handler clears all field errors, the form error, and any
  success message as its first action, before the in-flight guard and the request. No `onChange`
  handler clears a message. See `DESIGN.md` §States.
- **Duplicate prevention:** each form uses a real `<form>`, an in-handler in-flight guard, and a
  disabled progress button until the request settles.
- **Settings session safety:** `wrong_current_password` is handled only as `400`; no client-side
  exception converts it to `401`, logs out, or navigates. A genuine failed refresh retains the
  existing session-expiry behaviour.
- **Single feature, not a split:** four screens is large for one slice, and a split was considered
  and rejected 2026-08-06. The five operations share one contract review and one `mswHandlers.ts`
  fixture pass, and both halves would edit `App.tsx`, `Login.tsx`, and `mswHandlers.ts` — splitting
  buys smaller reviews at the cost of merge friction on the same three files. Ship 028 whole.
- **Scope fence:** no profile fields, Users/invite administration, MFA, password meter, forced
  rotation, session management, backend endpoint, contract edit, alternate API type, new package,
  new theme/token, or mobile layout.
- **Surgical styling:** use existing tokens and components. Copy, stable ids, focus behaviour, and
  materially different visual states are owned by `DESIGN.md`; implementation does not invent
  alternatives.
- **Infrastructure:** `HUMAN_INFRA_REQUIRED` is not set. This frontend work requires no new
  hardware, daemon, provider, or external tool.

---

## 5. Testing expectations

Use Vitest + Testing Library + MSW through the existing real Axios instances. Mirror
`Login.test.tsx` for form behaviour, `SessionProvider.test.tsx` for session transitions,
`App.test.tsx` for router edges, and `authHeader.test.ts` for isolated interceptor-import proof.
Tests assert accessible roles/labels and the stable ids from `DESIGN.md`; they do not inspect React
implementation state.

### Accept invite

- Missing token renders the dead-invite state and makes no lookup request.
- An authenticated visitor with a live token renders the signed-in block, makes zero lookup and zero
  accept requests, renders no password form, and its action calls the existing `signOut`. A
  `booting` session renders the loading card and makes no lookup request.
- A live token posts exactly `{ token }`, renders `org_name` and `role`, keeps the typed response's
  email out of the UI, and renders no email input.
- Re-render/StrictMode performs one effective lookup; manual Retry is the only retry after a
  service failure.
- Lookup `410 invalid_invite_token` renders the same terminal state as accept `410` and removes the
  password form.
- Confirmation mismatch makes zero accept calls and targets Confirm password.
- Acceptance posts exactly `{ token, password }`; the lookup response's email is never sent.
- `400 password_policy_violation` stays on the form and targets Password;
  `400 email_already_registered` keeps the form and offers Login.
- `201 LoginResponse` stores the access token, refreshes the session profile, navigates directly
  to `/`, and never renders Login.
- In-flight acceptance cannot be submitted twice; network/`5xx` restores a usable form with no
  false success.

### Forgot password

- Known-address and unknown-address `204` runs produce identical confirmation structure/copy apart
  from echoing the submitted address; neither handler test depends on account existence.
- The form is replaced on success; email and button are absent afterward.
- Request body is exactly `{ email }`; in-flight state prevents duplicate calls.
- Network/`5xx` retains the email/form and approved error; Back to sign in routes to `/login`.

### Reset password and Login edge

- Missing token is immediately terminal and makes no reset request.
- Mismatch makes no request; policy `400` stays on form; `410 invalid_reset_token` removes it and
  links to `/forgot-password`.
- Successful request body is exactly `{ token, new_password }`, never confirmation.
- `204` does not create or mutate an access token, navigates with replace to `/login`, and displays
  the approved `Password set...` status with the Login form.
- The Login success marker is transient history state, not a query string; normal Login visits do
  not show it. Login's new Forgot password link targets `/forgot-password`.
- In-flight and network/`5xx` behaviour preserve the same duplicate-prevention and recovery rules.

### Settings and interceptor integration

- `/settings` redirects an anonymous visitor to `/login`; both admin and viewer profiles can open
  it and see the same change-password form.
- Mismatch makes no request. A valid request contains only `current_password` and `new_password`.
- A settled message survives typing: after `400 wrong_current_password`, editing Current password
  leaves the error rendered, and it disappears only once the next submit starts. Assert the same
  rule for the Settings success line.
- `400 wrong_current_password` targets Current password, performs zero refresh calls, preserves the
  access token/session, and leaves the route at `/settings`.
- `400 password_policy_violation` targets New password and also stays on Settings.
- `204` clears password fields, shows inline success, and stays on Settings.
- Network/`5xx` retains a usable form; an in-flight request cannot duplicate.
- A genuine `401` proves the existing interceptor refreshes once and retries. If refresh fails,
  the existing event clears session and navigates to Login.
- The isolated `authHeader.test.ts` case dynamically imports only `passwords.ts` and proves it
  sends `Authorization: Bearer ...`, preventing a silent import from bare `instances.ts`.

### Routing and chrome

- `App.test.tsx` proves all three public auth routes render after a failing boot refresh and that
  Settings never flashes while session status is booting/anonymous.
- Existing protected catch-all URL-preservation behaviour remains green.
- `TopBar.test.tsx` asserts two enabled links for both roles, exact `/` and `/settings` hrefs,
  correct active indication, no `aria-disabled`, and Log out still calls `signOut`.

### Gates

Run from `frontend/`:

```text
npm run lint
npm run typecheck
npm test
npm run build
```

No repo-wide formatter is run.

---

## 6. Sources consulted

- `docs/ui/SCREENS.md` — Foundations and the Login, Accept invite, Forgot password, Reset password,
  and Settings screen contracts.
- `docs/ui/FLOWS.md` — B1, B2, and B5 connections and the resolved C13/C14/C15 decisions.
- `.claude/docs/frontend/{api,auth,app,screens}.md` — current code map and load-bearing import,
  session, routing, and chrome seams.
- `contracts/openapi/openapi.yaml` and `frontend/src/types/openapi.d.ts` — current transport and
  generated type authority.
