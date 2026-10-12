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

* [api](./api.md) — The two Axios instances, required VITE_API_URL base-URL construction, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, prefix-shaped query keys, and the read, account and org-administration resource modules.

## Engineering guardrails

* [frontend authored-source guardrails](./linting.md) — The local ESLint plugin that enforces named Tailwind tokens, spacing scale, shared interactive primitives, and bans raw hex in authored application source; no-dark-variant is exported but switched off.

## Session & routing

* [auth](./auth.md) — The SessionProvider (boot refresh modelled as a query), the shared post-authentication sequence, account deletion, the useSession accessor, and the RequireSession and RequireAdmin route guards.
* [i18n](./i18n.md) — LanguageProvider stores the chosen UI language (en, pt-BR, ru) in localStorage; useI18n returns it with a typed t(key) over one in-code message catalog; the same language is sent to the AI and report endpoints.
* [app](./app.md) — The React root's provider nest and App's route table — the four public auth routes, the guarded shell (Home, scans, network, devices, Settings), nested admin-only Users, and a catch-all that renders rather than redirects.

## Domain & screens

* [review](./review.md) — useHome() loads GET /home as one query and maps the snapshot to loading, error, blank, clear, or pending.
* [directory](./directory.md) — DirectoryRow — the merged member/invite display union — and useOrgDirectory(), which folds two list reads into one state union where error outranks loading.
* [scan-failure-reasons](./scan-failure-reasons.md) — SCAN_FAILURE_REASONS maps each published ScanErrorCode to one operator sentence; scanFailureReason() falls back to the unknown sentence.
* [scan-status](./scan-status.md) — scanStatusLabel maps every ScanStatus including cancelled and Stopped early; hidesCounts dashes count cells; bySeverityDesc is the only guaranteed worst-first order.
* [command-status](./command-status.md) — commandStatusLabel maps every CommandStatus including cancelled; isSettledCommand stops the device-detail command poll once no late results can land.
* [devices-screen](./devices-screen.md) — Devices shows Online, Offline or Revoked; DeviceDetail owns scanning (including Stop scan), plus admin revoke/restore and hides controls while revoked.
* [scan-partial-warning](./scan-partial-warning.md) — ScanPartialWarning shows a plain attention line beside scan duration when a scan is partial.
* [scan-ai](./scan-ai.md) — Scan Detail card that GETs analysis status in the UI language, offers Explain this scan once per language, polls only while pending or processing, and renders the Groq overview in collapsible sections when completed.
* [context-ai](./context-ai.md) — One-shot "Explain with AI" (finding, host) via ContextChat's presetQuestion mode against `/ai/chat`, askable once per mount. GlobalAssistant (the floating multi-turn assistant) was deleted.
* [home-ai-overview](./home-ai-overview.md) — Home teaser for the latest successful scan's analysis status.
* [ai-usage](./ai-usage.md) — Settings panel for org-wide provider usage totals and recent operations.
* [tables](./tables.md) — DataTable with rowAction, rowTone and collapsedGroup; ListSurface and ReadDetailGate; Pagination; EmptyState; SeverityWord; LoadingSkeleton.
* [host-detail](./host-detail.md) — readDetailState turns one detail query into loading/error/notFound/ready, ReadDetailGate renders the three non-ready states with back links, and each independent second read owns its own section states.
* [screens](./screens.md) — The public and guarded screens, scan-detail progress display, 70rem app frame, centred navigation, Settings with AI usage, and shared presentation and interaction components.
