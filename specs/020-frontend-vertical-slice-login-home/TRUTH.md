# TRUTH — Frontend vertical slice: login → Home with live data (DMI-81)

Domain language and verifiable behaviour only. No file paths, no code. Stack decisions live
in `ARCHITECTURE.md`; screen layout, copy and colour live in `DESIGN.md`. Both are already
constrained by ADR-008 and `docs/ui/SCREENS.md` §Foundations and do not get re-decided here.

## Narrative

The scaffold (DMI-20) proved the stack installs and the auth client works, but it ships a
throwaway login stub and a placeholder that says "signed in". Nobody can use the product.

This feature is the first real UI: an operator opens the app, logs in with their email and
password, and lands on a Home screen that tells them — in one plain sentence — whether their
network needs their attention. That is the whole product promise in one screen. Home is not a
dashboard: it interprets, and the operator reads a judgment rather than numbers. On a normal
day it is almost empty, and that emptiness is the design.

It is also the end-to-end proof of the stack: a browser form hits a real backend, gets a real
session, reads the signed-in user's identity and role, and renders real scan data. Everything
between the Pi and the pixel is exercised once.

Two things govern the scope. **The role is read from the server, never inferred** — every
"absent, not disabled" decision in the product depends on it. And **role-gated affordances are
omitted from the page, not greyed out**: a viewer never learns what they are missing.

> **⚠️ This feature is blocked.** Home's verdict needs the latest scan, that scan's
> critical/high findings, and the agent's last-seen time. All three are **defined in the frozen
> contract and unimplemented in the backend**. **DMI-82** must land first — implementation
> only, no contract change. See "Dependencies" below. The spec is written now so the build can
> start the day that blocker clears.

## Business rules

- **Identity and role come from the server.** After login the app asks the backend who the
  signed-in user is. The role is never decoded from a token client-side and never guessed.
- **Absent, not disabled.** An affordance a viewer cannot use is not rendered at all. There is
  no greyed-out control anywhere in this feature.
- **The verdict is a sentence, not a number.** Home's primary content is one plain-language
  statement of whether anything needs attention. Counts may appear inside that sentence; they
  never replace it.
- **Only actionable things reach Home.** Critical and high findings, failed scans, and stale
  coverage. Medium and low findings, and routine successful scans, never appear.
- **Coverage is stale after 3 days.** If the most recent successful scan finished more than
  3 days ago, Home says so. (Decided 2026-07-27; closes the FRONTEND.md open decision.)
- **Every screen ships three designed states.** Regular, blank, and error — none inherited by
  accident. A page-level failure states what failed in plain words and offers a retry. A
  skeleton never stands in for a verdict.
- **No session, no protected content.** Reaching any signed-in destination without a session
  sends the operator to login. Protected content is not rendered first and hidden after.
- **Login never reveals whether an account exists.** A failed sign-in names neither field and
  distinguishes no case; the operator stays on the page with the error in view.
- **Submitting is a state.** While a sign-in is in flight the button says so and cannot be
  pressed again. There is no bare spinner.
- **The contract is the source of truth.** No request or response shape is hand-written when
  the contract already defines it.

## User stories

1. As an operator, I want to sign in with my email and password and land on Home, so that I
   can use the product without touching an API client.
2. As an operator, I want a plain-language verdict on Home, so that I know my network's state
   at a glance without interpreting a chart.
3. As an operator with something to fix, I want each item stated in plain words with a way to
   go deal with it, so that I know what to do next.
4. As a viewer, I want never to see admin-only actions, so that the product does not tease me
   with things I cannot do.
5. As an operator returning to a browser tab, I want to be sent to sign-in rather than shown a
   broken page, so that an expired session is not a puzzle.
6. As an operator whose data fails to load, I want to be told and offered a retry, so that a
   failure is not an infinite spinner.
7. As an operator, I want to sign out and be certain I am signed out, so that I can leave a
   shared machine safely.

## Acceptance criteria (verifiable)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| 1 | Sign in succeeds | Valid credentials, no session | The operator submits the sign-in form | A session is established and Home is shown |
| 2 | Sign in fails | Credentials the backend rejects | The operator submits the sign-in form | An error appears in the form, the operator stays on sign-in, and no session exists |
| 3 | Sign-in is in flight | The form has been submitted and no answer has arrived | The operator looks at the button | The button states that signing in is in progress and cannot be submitted again |
| 4 | Network is down at sign-in | The backend is unreachable | The operator submits the sign-in form | An error distinguishable from "wrong credentials" appears in the form, and the operator stays on sign-in |
| 5 | Protected route without a session | No session | The operator opens Home's address | They are sent to sign-in and no protected content is rendered |
| 6 | Session recovery on reload | A valid long-lived session, the page is reloaded | The app boots | The operator stays signed in and is not shown sign-in |
| 7 | Viewer role gating | A signed-in viewer | Home and the shell render | No admin-only affordance is present anywhere in the page — not present and disabled, but absent |
| 8 | Admin role gating | A signed-in admin | Home and the shell render | The admin-only affordances are present |
| 9 | Home, all clear | A session, a recent successful scan, no critical or high findings | Home renders | The verdict states that nothing needs attention, with a context sentence naming when the last scan finished and what it covered. No review items are shown |
| 10 | Home, items pending | A session, a recent scan with at least one critical or high finding | Home renders | The verdict states how many things need review, and each critical/high finding is listed in plain language with a way to go deal with it |
| 11 | Home hides noise | A recent scan whose only findings are medium and low | Home renders | The verdict states nothing needs attention and no finding is listed |
| 12 | Home, failed scan | The most recent scan did not finish | Home renders | A review item states that the last scan did not finish, with a way to see why |
| 13 | Home, stale coverage | The most recent successful scan finished more than 3 days ago | Home renders | A review item states that coverage is stale, with a way to go deal with it |
| 14 | Home, blank | A session and no scan has ever run | Home renders | First-run copy explains what a scan is; an admin is offered a way to run the first scan, a viewer is told to ask their admin and is offered no such affordance |
| 15 | Home, error | A session and the data load fails | Home renders | Plain error copy and a retry are shown; no partial content pretends to be a verdict |
| 16 | Home, retry recovers | Home is in its error state and the backend recovers | The operator retries | The data loads and the appropriate regular or blank state renders |
| 17 | Sign out | A signed-in operator | They sign out | The session ends on the server, in-memory state is cleared, and they are on sign-in. Going back does not restore protected content |
| 18 | Quality gates | The feature's branch | Lint, format check, typecheck, test, and build run | All pass on the touched scope |

## Out of scope (v1)

- Scans, Hosts, scan detail, host inventory, and host detail screens.
- "Scan now" and any command-status UI.
- The Users & invites admin surface, invite acceptance, forgot password, reset password, and
  the Settings screen.
- Charts, metric cards, and any numeric dashboard on Home — excluded by decision, not by
  omission.
- The LLM explainer.
- Polling, websockets, or any real-time refresh. Home is a plain read.
- A "new device seen" review item on Home.
- Dark mode. One theme ships; no toggle, no detection, no half-built second palette.
- Tablet and mobile layouts.
- Any backend, contract, or Pi-agent change. Those belong to the blocking feature below.

## Dependencies

| Depends on | State |
|---|---|
| Sign-in, refresh, sign-out, and session machinery (DMI-60) | ✅ Done |
| Signed-in user's identity and role (DMI-72) | ✅ Done |
| The scaffold: typed API access and auth plumbing (DMI-20) | ✅ Done |
| **Home's reads: the latest scan, and that scan's critical/high findings** | ⛔ **DMI-82** — `GET /scans` (list) and the `severity`/`scan_id` filters on `GET /findings`. Both frozen in the contract, neither implemented; the residue DMI-74 deferred. Implementation only, no contract change |
| The Pi's online state and last-seen time | ⛔ **DMI-78** (contract ask C1). The SPA has no way to learn an `agent_id`; there is no `/agents` collection in the contract. Costs the Home footer only — see `DESIGN.md` |

Acceptance criteria 9–13, 15 and 16 cannot be met until the first blocker lands. Criteria 1–8,
14, 17 and 18 are buildable against what exists today. DMI-78 costs the Pi-status footer, which
is not an acceptance criterion — the 3-day staleness rule (criterion 13) needs only the scan
timestamp and survives without it.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Screen layout, copy, states and colour: `DESIGN.md`
- Execution ledger: `POOP.md` (written during orchestration)
- Product brief: Linear DMI-81
