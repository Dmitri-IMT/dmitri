# frontend

The React 19 + TypeScript SPA (Vite). Spec 014 built the scaffold — contract-typed API access and
the auth-client plumbing behind a stub UI; spec 020 replaced the stubs with the first real vertical
slice: routing, a session layer, and the login → Home screens. Spec 028 added the public auth
surfaces around that slice — password recovery, invite acceptance and a Settings screen. Source
lives at `frontend/src/`.

## Overview

* [Package overview](./overview.md) — The React 19 + TypeScript SPA — contract-typed API access, the auth-client plumbing, the session layer, and the first real screens (login → Home).

## API layer

* [api](./api.md) — The two Axios instances, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, and the three read resource modules.

## Session & routing

* [auth](./auth.md) — The SessionProvider (boot refresh modelled as a query), the shared post-authentication sequence, the useSession accessor, and the RequireSession route guard.
* [app](./app.md) — The React root's provider nest and App's route table — the four public auth routes, the guarded shell branch, and a catch-all that renders rather than redirects.

## Domain & screens

* [review](./review.md) — deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes the four reads into one discriminated union.
* [screens](./screens.md) — The login, home, password-recovery, settings (including activity disclosure) and invite screens, plus shells, navigation and shared components.
