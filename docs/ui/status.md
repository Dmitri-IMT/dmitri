# UI status

Temporary, short overview. Details live in `REFERENCE.md`, `FLOWS.md`, `FOUNDATIONS.md`,
`SCREENS.md`, and `IDEAS.md`.
**`FOUNDATIONS.md` is the source of truth for the UI look** (binding, 2026-09-02); **`SCREENS.md`
is the source of truth for the screens.** When either disagrees with an ADR or roadmap doc, they
get reconciled to it.

## Goal

Build the desktop-first Dmitri web MVP: a simple security review UI plus admin-only **Scan now**.

The product should explain what needs attention. It is not a metrics dashboard.

## MVP screens

| Area | Screens | Status |
| --- | --- | --- |
| Auth | Login, accept invite, forgot/reset password, voluntary change password | B1/B2 **corrected against the contract**. Login still needs C16. **C14 resolved 2026-08-06 (DMI-86)** — accept invite has its lookup endpoint and no longer asks for an address; consuming it is DMI-87. **C15 resolved 2026-08-03 (DMI-77)** — reset password is unblocked. **Forced password change was dropped** — forced rotation is abandoned (ADR-015), so C5 is void and there is no forced-change screen. **Built 2026-08-07 (spec 028)** — login's forgot link, forgot/reset password, and accept invite (consuming the C14 lookup) all ship; delivery of the emails carrying those links still waits on the provider decision below. |
| Home | `/`; the work board — what needs review, plus events and activity | Re-specced 2026-09-02 against mockups v4 (DMI-131). |
| Read | Scans + scan settings, scan detail, Network list/detail | B3 clarified; **all four screen specs drafted 2026-07-13**. **C10 resolved 2026-08-13 (DMI-75)** — `ScanDetailResponse.error_code` is on the scan; the copy deck ships; consuming it on Scan Detail is DMI-88. **C9 resolved 2026-08-02** — `host_id` is required on `ScanHostView`. **C11 resolved** — the findings filter is `?host_id=`; the read model is `hosts` end to end, only ingest keeps `devices`. |
| Devices | Device status; network choice (the manual **Scan now** moved to Scans) | B4 clarified; **screen spec drafted 2026-07-13**. Blocked on C1, C2. **C12 resolved** — terminal state splits on `delivered_at` (never delivered → `expired`; delivered then broke → `failed`). |
| Admin | Users & invites | B2 and screen spec drafted. C4 backend contract is now complete (spec 030): member/pending-invite lists, role change, revoke, removal and last-seen exist. **Built 2026-08-21 (spec 034)** — the merged member/invite table, role change, removal by typing the target's address, invite revocation and the invite dialog with its copyable one-time link all ship, behind the product's first role-gated route. |
| Settings | Change password; profile | Change password, the layered Activity disclosure and the leaving section (self-removal, confirmed by typing your own address) are built. Profile update remains pending. |

## Chosen

- Two roles: admin and viewer. **Not renamed to "user"** — every member is a user, so the word cannot distinguish a role, and the screen listing them is itself called *Users*.
- **Members can be removed, and it is a hard delete** ([`ADR-017`](../adr/ADR-017-account-removal.md)): admins remove other people from Users; everyone removes themselves from Settings. Both surfaces confirm by making the operator type the target's email address.
- **An org can never reach zero admins.** Admins cannot delete or demote themselves from the Users screen, so the caller always survives; the only route that can remove the last admin is self-service removal in Settings, and it refuses with "You're the only admin."
- **Members show a "Last seen" time, not "Added."** It counts silent refresh, so it answers "is this account being used?" rather than "when did they last type a password."
- Both roles can read Home, scans, the network, and devices.
- Only admins can scan, invite users, or manage roles.
- Viewer-only UI omits unavailable actions; it does not show disabled controls.
- Home is the default screen. It gives a plain verdict, then only critical/high findings, failed scans, or stale coverage.
- Home has all-clear, needs-review, first-run, and error states. First-run sends admins to Scans to run the first scan.
- Scan now shows: queued → delivered → running → uploading → done. Done links to the scan.
- MVP excludes Pi setup, notifications, charts/metric cards, and the LLM explainer.
- Settings **is** in the MVP: change your own password (voluntary self-service — there is no forced rotation) and profile. The scan target network is **not** in Settings; it is a property of the Pi, chosen on Devices.
- Single agent: exactly one Pi. It is dual-homed, so a human picks which network to scan, once, on Devices. Scan type is chosen on the Scans page (Quick · Standard · Extensive · Max · NSPi).
- Visual direction: see [`FOUNDATIONS.md`](FOUNDATIONS.md) — binding since 2026-09-02 (DMI-131), implemented by DMI-132.
- App shell is a top bar, not a sidebar. ADR-008 was narrowed to match.
- Transactional email is in scope: the backend emails invite links and password-reset links (provider TBD). The Users screen **also** shows the invite link, copyable — email is the convenience, the link is the guarantee.
- **The nav names domains, not actions.** "Users" keeps its name even in v1, when the only thing inside it is the invite form; new user-related surfaces are added *inside* Users rather than beside it. Nav is muscle memory — items don't get renamed between releases.
- Nav names (2026-09-02, DMI-131): Home · Scans · **Network** (was Hosts) · **Devices** (was Agents) · Users · Settings. Routes are unchanged.
- Light theme only. No toggle, no `prefers-color-scheme` branch, no `dark:` variants. Dark mode is planned as a separate later pass.
- One family: Inter Variable for everything; Geist Mono for technical data only.
- Neutrals: canvas `#FCFCFC`, card `#FFFFFF`, ink `#0F172A`, muted `#475569`, rule `#E2E8F0`, edge `#64748B`.
- One accent, `#4F46E5` indigo, never a severity. Severity has no hue at all — a bold ink word.
- Desktop only (1440 target, 1280 min) but fluid within it: 1120px frame / 384px form are maximums, not fixed widths. No mobile or tablet layouts designed; nothing breaks below 1280 either.
- Building rules bind implementation: no magic numbers (everything is a token), components size to their container, long values never widen the page, the body never scrolls horizontally.
- Shared components earn their place by two or more screens. No MetricCard, no Breadcrumbs, no Sidebar, no Ornament.
- Nine cross-screen consistency rules, including three-states-always and absent-not-disabled for viewers.

## Still needed

- **Verify the Resend sending domain.** Provider code exists for invite and reset links; production
  delivery still needs SPF, DKIM, and DMARC. The built Forgot/Reset screens otherwise work.
- Remaining contract blockers include agent discovery/target-network persistence and self-profile update. C4 is closed: member and invite administration routes are published and implemented, and spec 034 consumed them — Users & Invites is built.
- One design call remains: the 409 busy-Pi copy. Stale coverage is already fixed at three days.
- **All screens are specced.** Home, public auth, and Settings (password, Activity disclosure and
  leaving the organization) are built; the remaining product screens/actions follow the roadmap.

## Later, not MVP

- LLM explainer on scan/finding detail.
- Search, breadcrumbs, filters, charts, richer agent history, password strength UI, theme toggle, and other ideas in `IDEAS.md`.
