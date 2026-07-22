# TRUTH — Frontend scaffold (DMI-20 / roadmap T9)

Domain language and verifiable behaviour only. No file paths, no code. Stack/tooling
decisions live in `ARCHITECTURE.md` and are already fixed by ADR-008.

## Narrative

The product has no `frontend/` yet. Every planned UI screen — login, Home, Scans, Hosts,
Agents, Users & invites — needs a foundation that already speaks to the backend safely
before any screen is worth building. This feature builds that foundation and **nothing
visible beyond a throwaway stub**: an SPA that (1) accesses the API through types
**generated from the frozen contract**, so the UI cannot silently drift from the API, and
(2) carries the full authentication plumbing — an in-memory access token, a login-only
refresh cookie, and automatic one-shot session recovery on expiry.

The scope rule that governs this whole feature: **if a test case touches it, it is built for
real; if it is a screen, it is a stub.** The client mechanics are real and tested. The login
page, route guards, and app shell are deferred to the first real-screens feature.

This is greenfield plumbing. It proves the chosen stack installs, builds, type-checks,
lints, tests, and enforces the contract in CI — so downstream UI work starts from a green,
trustworthy base. It is roadmap task **T9**, unblocked now that the contract is frozen
(DMI-53) and the frontend decisions are locked (DMI-54).

## Business rules

- **Contract is the source of truth.** API types are generated from the frozen backend
  contract, committed to the repo, and re-checked in CI. If the contract changes and the
  types are not regenerated, CI fails. Hand-written API types are forbidden.
- **Access token lives in memory only.** Never in `localStorage`/`sessionStorage`. A full
  page reload loses it and the app silently recovers the session via one refresh attempt
  before rendering protected content.
- **The refresh cookie rides only on auth requests.** Login, refresh, and logout requests
  carry credentials; every business request is pure Bearer and carries no cookie. This
  separation is structural, not a per-call opt-in that a developer can forget on the wrong
  side.
- **A 401 triggers exactly one refresh.** On an expired access token, the client attempts a
  single refresh and retries the original request once. Concurrent 401s share that one
  in-flight refresh — they do not each fire their own. If the refresh fails, in-memory auth
  state is cleared and the user is sent to login.
- **Visual surface is a stub.** Exactly one throwaway login form (enough to fire a real auth
  request) and one "signed in" placeholder. No real pages, guards, shell, or auth screens
  beyond that.
- **Tooling is CI-runnable.** Lint, format-check, type-check, test, type-generation, and
  build all run headless, non-interactively, and exit non-zero on failure.

## User stories

1. As a **downstream UI developer**, I want typed API access generated from the contract, so
   that a backend field rename becomes a compile error in my screen code instead of a runtime
   bug found by hand.
2. As a **downstream UI developer**, I want auth, refresh, and session-recovery already
   wired, so that I build screens without re-solving token storage or the 401 dance.
3. As a **security reviewer**, I want the refresh cookie structurally confined to auth
   requests, so that no business endpoint can ever receive it even if a future developer is
   careless.
4. As a **maintainer**, I want CI to fail when the committed API types drift from the
   contract, so that contract/UI divergence is caught in review, not in production.
5. As a **new contributor**, I want a clean checkout to install, build, type-check, and test
   with standard commands and a documented environment variable, so that onboarding is a
   matter of minutes.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Clean build | A fresh checkout | install + type-generation + build + type-check run | All succeed, and the app compiles against the **generated** API types (no hand-written contract types) |
| One refresh on 401 | A mocked API returning 401 for a business request, then a successful refresh | A business request fires and its access token is expired | Exactly **one** refresh request is made, the original request is retried once, and it succeeds |
| Refresh failure → login | A mocked API returning 401, and a refresh that also fails | A business request fires with an expired token | In-memory auth state is cleared and the app redirects to the login route; **no second refresh** is attempted |
| Concurrent 401s single-flight | A mocked API where several business requests are in flight and all receive 401 | The token expires and all responses arrive | Only **one** refresh request is made total; every queued request is retried after that single refresh resolves |
| Cookie scoping | The configured HTTP clients | A business request and an auth request are each issued | The business request sends **no** credentials/cookie; the auth request sends credentials |
| Contract drift caught | The committed API types and the frozen contract | Type-generation is re-run and the result is diffed in CI | A green diff passes; any difference fails the CI job |
| CI tooling gate | The frontend project | The CI job runs install → type-gen drift check → lint → type-check → test → build | Each step runs headless and the job fails if any step fails |
| Stub proves wiring | The stub login form rendered with the real UI stack | Valid credentials are submitted against a mocked login endpoint | A real auth request is issued through the auth client and the app transitions to the "signed in" placeholder |

## Out of scope (v1)

- No real pages (Home, Scans, Hosts, Agents, Users & invites) — post-T8 features.
- No route guards and no app shell / top bar — deferred to the first real-screens feature.
- No auth screens beyond the stub: no invite acceptance, forgot/reset password, or forced
  password-change flow. (The forced-change flow also has an unresolved contract question and
  cannot be built yet.)
- No deployment, hosting, containerization, or environment provisioning — belongs to the ops
  feature.
- No data-visualization/charting setup.
- No changes to the backend or the frozen contract.

## Related specs

- Implementation: `ARCHITECTURE.md` (DESIGN.md intentionally omitted — the only visual
  surface is a deferred stub; there are no real screens to design in this feature)
- Execution ledger: `POOP.md` (written during orchestration)

## Follow-ups surfaced (out of this feature's scope)

- **Backend:** confirm the refresh cookie is issued with a path scoped to the auth routes —
  that browser path-match is the authoritative guarantee the cookie never reaches business
  endpoints; the client-side confinement here is the second barrier, not the first.
- **Contract:** resolve the forced-password-change ambiguity (a 403 with no token vs. a
  restricted-scope login) before the forced-rotation screen is built.
