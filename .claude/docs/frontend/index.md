# frontend

The React 19 + TypeScript SPA (Vite). Spec 014 built the scaffold — contract-typed API access and
the auth-client plumbing behind a stub UI; spec 020 replaced the stubs with the first real vertical
slice: routing, a session layer, and the login → Home screens. Spec 028 added the public auth
surfaces around that slice — password recovery, invite acceptance and a Settings screen. Spec 033
added the self-service exit from the organization, confirmed by typing your own address. Spec 034
added the admin users-and-invites surface — the product's first role-gated route and its first
table. Source lives at `frontend/src/`.

## Overview

* [Package overview](./overview.md) — The React 19 + TypeScript SPA — contract-typed API access, the auth-client plumbing, the session layer, the screens from login and Home through password recovery, settings, the admin users-and-invites surface and invite acceptance, and the Railway static deployment.

## API layer

* [api](./api.md) — The two Axios instances, required VITE_API_URL base-URL construction, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, and the read, account and org-administration resource modules.

## Session & routing

* [auth](./auth.md) — The SessionProvider (boot refresh modelled as a query), the shared post-authentication sequence, account deletion, the useSession accessor, and the RequireSession and RequireAdmin route guards.
* [app](./app.md) — The React root's provider nest and App's route table — the four public auth routes, the guarded shell branch with its nested admin-only segment, and a catch-all that renders rather than redirects.

## Domain & screens

* [review](./review.md) — deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes the four reads into one discriminated union.
* [directory](./directory.md) — DirectoryRow — the merged member/invite display union — and useOrgDirectory(), which folds two list reads into one state union where error outranks loading.
* [scan-failure-reasons](./scan-failure-reasons.md) — SCAN_FAILURE_REASONS maps each published ScanErrorCode to one operator sentence; scanFailureReason() falls back to the unknown sentence.
* [screens](./screens.md) — The login, home, password-recovery, settings, users-and-invites and invite screens, plus shells, navigation, the role gate, the toast and shared components.
