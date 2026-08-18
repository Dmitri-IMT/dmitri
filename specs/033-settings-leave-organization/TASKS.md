# TASKS — Leave the organization from Settings (DMI-103)

Specs: `TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md` (this directory).
Layer: `frontend/` only. Agents per task: `agent-developer` → `frontend-test-engineer` →
`frontend-code-reviewer` (gate: `npm run lint && npm run format:check && npm run typecheck &&
npm run test && npm run build`).

## Dependency graph

```
Task 1 (API + session) ─┐
Task 2 (ConfirmByTyping)─┴─> Task 3 (Settings section) 
Task 4 (Login arrival note) — independent
```

## Task 1: Delete-account API call and session teardown
- **Description**: Add `deleteCurrentUser()` to the users API module and a `deleteAccount()`
  member on the session context that calls it, then clears the session and navigates to
  `/login` with the `accountDeleted` router state. Add the MSW handler for `DELETE /users/me`
  so the suite does not fail on an unstubbed route. Follow ARCHITECTURE.md rows 1, 2, 6 and the
  "System context" / "Data model / contracts" sections exactly: `deleteAccount()` does **not**
  catch, does **not** reuse `logout()`, and uses `clearSession()` + `navigate('/login',
  { replace: true, state: { accountDeleted: true } })`.
- **Dependencies**: —
- **Target Files**: [`frontend/src/api/users.ts`, `frontend/src/auth/SessionProvider.tsx`,
  `frontend/src/test/mswHandlers.ts`, `frontend/src/auth/SessionProvider.test.tsx`]
- **Success Criteria**:
  - `deleteCurrentUser(): Promise<void>` is exported from `@/api/users`, uses `apiClient`, and
    hits the generated `DELETE /users/me` operation. No hand-edited `openapi.d.ts`.
  - `SessionContextValue` gains `deleteAccount`, provided in the context `value` object.
  - On resolve, the in-memory access token is discarded and the `['session']` query cache entry
    is cleared via `clearSession()` — not by a bare `clearAccessToken()` — so `status` no longer
    reads `authenticated`.
  - A rejection propagates to the caller untouched; the session is left intact.
  - Every existing `useSession()` consumer still compiles (additive context change).
  - Tests mirror the two existing `signOut` teardown tests in `SessionProvider.test.tsx`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: `ConfirmByTyping` shared confirmation component
- **Description**: Build the shared type-to-confirm modal per ARCHITECTURE.md row 3 and its
  binding "`ConfirmByTyping` — the exact props" section, and per DESIGN.md §2, §4, §5, §6, §8.
  Built directly on `Dialog` from `radix-ui`, placed in `frontend/src/components/`, not
  `components/ui/`. The confirming action's greyed state is decided by the component itself from
  the typed value and the outstanding-request flag — it is never a caller-supplied variant.
- **Dependencies**: —
- **Target Files**: [`frontend/src/components/ConfirmByTyping.tsx`,
  `frontend/src/components/ConfirmByTyping.test.tsx`]
- **Success Criteria**:
  - Props match the ARCHITECTURE.md prop table exactly, including `expectedValue` serving both
    as the gate and as the `<label htmlFor>` accessible name — no separate `inputLabel` prop.
  - `matchesExpected(typed, expected)` is module-local; the confirming action is greyed out and
    not clickable while the typed value is empty, partial, or different, and live the instant it
    matches exactly.
  - The confirming action is greyed out and not clickable again while a request is outstanding.
  - Every other element in the dialog is live at all times (absent-not-disabled sweep).
  - Cancel / dismiss requests nothing.
  - Keyboard and focus behaviour follow DESIGN.md §5; copy follows §6; `data-testid` values
    follow §8.
  - Test file is component-level with no MSW, mirroring `frontend/src/pages/home/FindingDeck.test.tsx`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: Settings leaving section
- **Description**: Add the trailing leaving section to Settings and wire it to
  `ConfirmByTyping` and `deleteAccount()`, including the last-admin refusal and the generic
  failure message. Per ARCHITECTURE.md row 4, its error-mapping table, and DESIGN.md §1–§6, §8.
  Do not modify the change-password form or the Activity disclosure.
- **Dependencies**: 1, 2
- **Target Files**: [`frontend/src/pages/Settings.tsx`, `frontend/src/pages/Settings.test.tsx`]
- **Success Criteria**:
  - The section is last on the page, visually separated, rendered `{user && …}` (no `!`), and
    identical for admin and viewer.
  - `data-testid="settings-leave"` and `data-testid="settings-leave-trigger"` are present.
  - The expected value typed to confirm is `useSession().user!.email`; no request is made to
    discover an organization name, and the copy names the organization generically.
  - Success: the removal is requested exactly once, and the person lands on `/login` showing the
    deletion note.
  - `status === 409 && code === 'last_admin'` (read via `readApiError`) keeps the modal open and
    the session intact, and renders "You're the only admin. Make someone else an admin first,
    then you can leave."
  - Any other failure keeps the person on Settings with a message that offers another attempt.
  - At rest, no element on the page is greyed out or announced as unavailable.
  - Tests extend the file's existing helpers with a `captureDeleteRequests()` shaped like the
    existing `captureChangeRequests()`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Login arrival note for a deleted account
- **Description**: Widen `Login`'s snapshotted router-state read to an
  `arrival: 'passwordReset' | 'accountDeleted' | null` value and switch the copy of the single
  existing `role="status"` region on it. Per ARCHITECTURE.md row 5 and its "Login: one region,
  two notes" section, Constraint 10, and DESIGN.md §6.
- **Dependencies**: —
- **Target Files**: [`frontend/src/pages/Login.tsx`, `frontend/src/pages/Login.test.tsx`]
- **Success Criteria**:
  - Exactly one `role="status"` region remains — `screen.getByRole('status')` stays unambiguous.
  - `data-testid="login-success"` is kept.
  - Arriving with `state: { accountDeleted: true }` shows "Your account has been deleted." as a
    confirmation, not an error.
  - The note does not survive a reload: the existing
    `navigate(location.pathname, { replace: true })` scrub still runs in the same effect that
    focuses the note, and is unchanged in behaviour.
  - The existing password-reset note is unchanged.
  - Tests mirror the existing `renderLoginApp({ passwordReset: true })` tests with
    `{ accountDeleted: true }`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Status table

| Task | Name | Status | Rejections |
|------|------|--------|-----------|
| 1 | Delete-account API call and session teardown | COMPLETED | 0 |
| 2 | `ConfirmByTyping` shared confirmation component | COMPLETED | 1 |
| 3 | Settings leaving section | COMPLETED | 0 |
| 4 | Login arrival note for a deleted account | COMPLETED | 1 |
