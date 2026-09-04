# frontend

The React 19 + TypeScript SPA (Vite). Spec 014 built the scaffold — contract-typed API access and
the auth-client plumbing behind a stub UI; spec 020 replaced the stubs with the first real vertical
slice: routing, a session layer, and the login → Home screens. Spec 028 added the public auth
surfaces around that slice — password recovery, invite acceptance and a Settings screen. Spec 033
added the self-service exit from the organization, confirmed by typing your own address. Spec 034
added the admin users-and-invites surface — the product's first role-gated route and its first
table. Spec 035 added executable UI-foundation lint rules and aligned the shells, navigation and
Settings structure with the named design tokens. Spec 039 (DMI-88) added the scan and host read
surfaces, the shared `DataTable`, and the Agents scan trigger (DMI-89). Spec 042 (DMI-131) restyled
the SPA — design-system v2, `/network` and `/devices` IA, six ESLint rules, and the Home attention
table. App source lives at `frontend/src/`; the local lint plugin lives at `frontend/eslint-rules/`.

## Overview

* [Package overview](./overview.md) — The React 19 + TypeScript SPA — contract-typed API access, auth/session plumbing, public and guarded screens, local UI-foundation lint rules, and Railway static deployment.

## API layer

* [api](./api.md) — The two Axios instances, required VITE_API_URL base-URL construction, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, prefix-shaped query keys with invalidation on command completion, and the read, agent, command, account and org-administration resource modules.

## Engineering guardrails

* [frontend authored-source guardrails](./linting.md) — The local ESLint plugin that enforces named Tailwind tokens, spacing scale, shared interactive primitives, and bans raw hex and dark variants in authored application source.

## Session & routing

* [auth](./auth.md) — The SessionProvider (boot refresh modelled as a query), the shared post-authentication sequence, account deletion, the useSession accessor, and the RequireSession and RequireAdmin route guards.
* [app](./app.md) — The React root's provider nest and App's route table — the four public auth routes, the guarded shell (Home, scans, network, devices, Settings), nested admin-only Users, and a catch-all that renders rather than redirects.

## Domain & screens

* [review](./review.md) — deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes four reads into one discriminated union.
* [directory](./directory.md) — DirectoryRow — the merged member/invite display union — and useOrgDirectory(), which folds two list reads into one state union where error outranks loading.
* [scan-failure-reasons](./scan-failure-reasons.md) — SCAN_FAILURE_REASONS maps each published ScanErrorCode to one operator sentence; scanFailureReason() falls back to the unknown sentence.
* [scan-status](./scan-status.md) — scanStatusLabel maps every ScanStatus to a label; hidesCounts dashes count cells; bySeverityDesc is the only guaranteed worst-first order.
* [command-status](./command-status.md) — commandStatusLabel maps every CommandStatus to a label; isTerminalCommandStatus stops the device-detail command poll.
* [devices-screen](./devices-screen.md) — Devices lists every box; DeviceDetail owns subnet choice, scan-type tabs and useScanCommand; trigger() posts the selected ScanMode and invalidates read caches on done.
* [tables](./tables.md) — DataTable with rowAction, rowTone and collapsedGroup; ListSurface and ReadDetailGate; Pagination; EmptyState; SeverityWord; LoadingSkeleton.
* [host-detail](./host-detail.md) — readDetailState turns one detail query into loading/error/notFound/ready, ReadDetailGate renders the three non-ready states with back links, and each independent second read owns its own section states.
* [screens](./screens.md) — The public and guarded screens, 70rem app frame, 24rem auth shell, centred navigation, details-first Settings surface, and shared presentation and interaction components.
