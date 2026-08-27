# frontend

The React 19 + TypeScript SPA (Vite). Spec 014 built the scaffold — contract-typed API access and
the auth-client plumbing behind a stub UI; spec 020 replaced the stubs with the first real vertical
slice: routing, a session layer, and the login → Home screens. Spec 028 added the public auth
surfaces around that slice — password recovery, invite acceptance and a Settings screen. Spec 033
added the self-service exit from the organization, confirmed by typing your own address. Spec 034
added the admin users-and-invites surface — the product's first role-gated route and its first
table. Spec 035 added executable UI-foundation lint rules and aligned the shells, navigation and
Settings structure with the named design tokens. Spec 039 (DMI-88) added the scan and host read
surfaces, the shared `DataTable`, and a permanent one-state Agents page with no trigger. App source
lives at `frontend/src/`; the local lint plugin lives at `frontend/eslint-rules/`.

## Overview

* [Package overview](./overview.md) — The React 19 + TypeScript SPA — contract-typed API access, auth/session plumbing, public and guarded screens, local UI-foundation lint rules, and Railway static deployment.

## API layer

* [api](./api.md) — The two Axios instances, required VITE_API_URL base-URL construction, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, prefix-shaped query keys, and the read, account and org-administration resource modules.

## Engineering guardrails

* [frontend authored-source guardrails](./linting.md) — The local ESLint plugin that enforces named Tailwind width, type and spacing tokens and shared interactive primitives in authored application source.

## Session & routing

* [auth](./auth.md) — The SessionProvider (boot refresh modelled as a query), the shared post-authentication sequence, account deletion, the useSession accessor, and the RequireSession and RequireAdmin route guards.
* [app](./app.md) — The React root's provider nest and App's route table — the four public auth routes, the guarded shell (Home, scans, hosts, agents, Settings), nested admin-only Users, and a catch-all that renders rather than redirects.

## Domain & screens

* [review](./review.md) — deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes the four reads into one discriminated union.
* [directory](./directory.md) — DirectoryRow — the merged member/invite display union — and useOrgDirectory(), which folds two list reads into one state union where error outranks loading.
* [scan-failure-reasons](./scan-failure-reasons.md) — SCAN_FAILURE_REASONS maps each published ScanErrorCode to one operator sentence; scanFailureReason() falls back to the unknown sentence.
* [scan-status](./scan-status.md) — scanStatusPill maps every ScanStatus to tone and label; isUnfinished hides counts; bySeverityDesc is the only guaranteed worst-first order.
* [tables](./tables.md) — DataTable with a discriminated rowAction, stretched-link rows and compile-time sort keys, ListSurface holding the one list-page state machine, Pagination that greys edge controls, EmptyState with no CTA, outline StatusPill, and LoadingSkeleton bars on --border.
* [host-detail](./host-detail.md) — readDetailState turns one detail query into loading/error/notFound/ready for both detail screens; useHostDetail layers the host's findings read on top.
* [screens](./screens.md) — The public and guarded screens, 70rem app frame, 24rem auth shell, centred navigation, details-first Settings surface, and shared presentation and interaction components.
