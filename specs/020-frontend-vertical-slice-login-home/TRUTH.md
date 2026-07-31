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

The second rule ships here as a *guarantee*, not yet as a demonstration: after this feature's
fences were drawn, nothing on either screen is admin-only. So this feature proves the first half —
the role is fetched from the server and available — and enforces the second structurally, by
ensuring nothing anywhere renders in a disabled state. The first admin-only affordance, and the
machinery that hides it, arrive with the screen that needs one.

> **✅ Unblocked (2026-07-28).** **DMI-82** landed: `GET /scans` and the `severity`/`scan_id`
> filters on `GET /findings` are implemented, tested and contract-verified. Home's verdict reads
> are all served. The one remaining gap is the agent's last-seen time (**DMI-78**), which costs
> only the Pi-status footer — not an acceptance criterion. See "Dependencies" below. This
> feature is buildable today.

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
- **The count states what is true, not what is shown.** When Home says how many things need
  review, that number counts everything that matched — never the number of items currently on
  screen. A screen that shows fewer than it counts is correct; a screen that counts only what it
  shows under-reports danger at exactly the moment it matters.
- **Serious findings are reviewed one at a time.** Home presents one finding, and the operator
  steps forward and back through the rest. Home never becomes an endless scroll, and stepping
  never waits on the network — everything the operator can step to is already loaded.
- **A failed scan and stale coverage are never stepped past.** They are not findings and are not
  part of that sequence; they stay in view so neither can go unseen.
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
3. As an operator with something to fix, I want each item stated in plain words — what it is,
   which machine it is on — so that I know what I am dealing with without opening anything else.
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
| 7 | Nothing is present-but-disabled | A signed-in operator of either role | Any screen in this feature renders | No element anywhere in the page is rendered in a disabled state, with one exception: the sign-in button while its request is in flight |
| 8 | The role comes from the server | A signed-in operator | The app determines whether they are an admin or a viewer | It uses the server's answer about who they are; it never decodes a token to find out |
| 9 | Home, all clear | A session, a recent successful scan, no critical or high findings | Home renders | The verdict states that nothing needs attention, with a context sentence naming when the last scan finished and what it covered. No review items are shown |
| 10 | Home, items pending | A session, a recent scan with at least one critical or high finding | Home renders | The verdict states how many things need review, and the first critical/high finding is shown in plain language naming what it is and which machine it is on |
| 11 | Home hides noise | A recent scan whose only findings are medium and low | Home renders | The verdict states nothing needs attention and no finding is listed |
| 12 | Home, failed scan | The most recent scan did not finish | Home renders | A review item states, in plain words, that the last scan did not finish |
| 13 | Home, stale coverage | The most recent successful scan finished more than 3 days ago | Home renders | A review item states, in plain words, how long it has been since a scan succeeded |
| 14 | Home, blank | A session and no scan has ever run | Home renders | First-run copy explains what a scan is and states where scanning is currently set up. No control for starting a scan is rendered, for either role |
| 15 | Home, error | A session and the data load fails | Home renders | Plain error copy and a retry are shown; no partial content pretends to be a verdict |
| 16 | Home, retry recovers | Home is in its error state and the backend recovers | The operator retries | The data loads and the appropriate regular or blank state renders |
| 17 | The count exceeds what is on screen | A scan with more critical and high findings than Home shows at once | Home renders | The verdict states the true number of things needing review — not the number visible |
| 18 | Stepping through findings | A session and a scan with several critical and high findings | The operator steps forward and back through them | One finding is shown at a time, most serious first, with its position in the sequence stated. Stepping never waits on the network, and the sequence stops at both ends rather than wrapping |
| 19 | Unknown address | A signed-in operator | They open an address the product does not have | A page states plainly that it does not exist and offers a way back to Home; they keep the shell they can navigate by. Signed out, the same address sends them to sign-in instead |
| 20 | Sign out | A signed-in operator | They sign out | The session ends on the server, in-memory state is cleared, and they are on sign-in. Going back does not restore protected content |
| 21 | Quality gates | The feature's branch | Lint, format check, typecheck, test, and build run | All pass on the touched scope |

## Out of scope (v1)

- Scans, Hosts, scan detail, host inventory, and host detail screens.
- **Any affordance that navigates off Home.** A review item states what is wrong; it does not
  carry a control that opens the thing it names, because the screens those controls point at do
  not exist yet. The product does not render a control that goes nowhere — the same reason this
  feature ships no "forgot password?" link. Each control arrives with the screen it points at.
- **Reaching beyond the first 100 critical or 100 high findings of a scan.** The sequence holds
  the first 100 of each; the verdict still states the true total, so the operator is told the real
  number even when they cannot step to every one. The screens that would list them all are out of
  scope below.
- **"Scan now", any command-status UI, and any control that starts a scan** — including on the
  first-run screen, where the operator is told in plain words where scanning lives instead.
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
| **Home's reads: the latest scan, and that scan's critical/high findings** | ✅ **DMI-82 — Done** (`specs/021-scan-list-and-finding-filters/`). `GET /scans` is mounted with `page`/`per_page`/`status`/`sort_by`/`sort_order`; `GET /findings` now takes `severity` and `scan_id` alongside the existing `host_id`. Shipped against the frozen contract with a fidelity test — no shape changed |
| The Pi's online state and last-seen time | ⛔ **DMI-78** (contract ask C1). The SPA has no way to learn an `agent_id`; there is no `/agents` collection in the contract. Costs the Home footer only — see `DESIGN.md` |

**Every acceptance criterion is now buildable.** DMI-78 costs the Pi-status footer, which is not
an acceptance criterion — criterion 13's staleness rule needs only a scan timestamp and survives
without it.

Two properties DMI-82 shipped that this feature must build against:

- **One severity per request.** `severity` takes a single value, not a list or a range. Home asks
  twice — once for critical, once for high.
- **Findings have no caller-chosen sort.** They come back in a fixed, stable-for-paging order.
  Home must not assume the response is ordered by severity, time, or anything else.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Screen layout, copy, states and colour: `DESIGN.md`
- Execution ledger: `POOP.md` (written during orchestration)
- Product brief: Linear DMI-81
