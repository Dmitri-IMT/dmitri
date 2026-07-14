# UI status

Temporary, short overview. Details live in `REFERENCE.md`, `FLOWS.md`, `SCREENS.md`, and `IDEAS.md`.
**`SCREENS.md` is the source of truth for the UI**; when it disagrees with an ADR or roadmap doc,
they get reconciled to it.

## Goal

Build the desktop-first Dmitri web MVP: a simple security review UI plus admin-only **Scan now**.

The product should explain what needs attention. It is not a metrics dashboard.

## MVP screens

| Area | Screens | Status |
| --- | --- | --- |
| Auth | Login, accept invite, forgot/reset password, forced password change | B1/B2 **corrected against the contract**; **all five screen specs drafted 2026-07-13**. Login needs C16, accept invite C14, reset password C15. **Forced password change is now specced** — C5's mechanism is decided (scoped `password_change_token` in the `403`); the contract must still say so (DMI-77). |
| Home | `/`; a verdict-led security review | Drafted. The only screen spec so far. |
| Read | Scan list/detail, host inventory/detail | B3 clarified; **all four screen specs drafted 2026-07-13**. Scan detail needs C9/C10. **C11 resolved** — the findings filter is `?host_id=`; the read model is `hosts` end to end, only ingest keeps `devices`. |
| Agents | Agent status; network choice; admin-only **Scan now** | B4 clarified; **screen spec drafted 2026-07-13**. Blocked on C1, C2. **C12 resolved** — terminal state splits on `delivered_at` (never delivered → `expired`; delivered then broke → `failed`). |
| Admin | Users & invites | B2 drafted; **screen spec drafted 2026-07-13**. Ships as **invite-only** — `POST /invites` is the sole endpoint (C4). Stays at `/users` under the "Users" nav item; the user table lands inside it when C4 arrives. |
| Settings | Change password; profile | B5 + **screen spec drafted 2026-07-13**. Password works; profile blocked (C3). |

## Chosen

- Two roles: admin and viewer.
- Both roles can read Home, scans, hosts, and agents.
- Only admins can scan, invite users, or manage roles.
- Viewer-only UI omits unavailable actions; it does not show disabled controls.
- Home is the default screen. It gives a plain verdict, then only critical/high findings, failed scans, or stale coverage.
- Home has all-clear, needs-review, first-run, and error states. First-run sends admins to Agents to run the first scan.
- Scan now shows: queued → delivered → running → uploading → done. Done links to the scan.
- MVP excludes Pi setup, notifications, charts/metric cards, and the LLM explainer.
- Settings **is** in the MVP: change your own password (otherwise homeless — B1 only covers *forced* rotation) and profile. The scan target network is **not** in Settings; it is a property of the Pi, chosen on Agents.
- Single agent: exactly one Pi. It is dual-homed, so a human picks which network to scan, once, on Agents. Scan mode is not a choice — the product picks `quick`.
- Visual direction: quiet paper/dark surfaces, deep purple accent, square components, engraving details, plain professional copy.
- App shell is a top bar, not a sidebar. ADR-008 was narrowed to match.
- Transactional email is in scope: the backend emails invite links and password-reset links (provider TBD). The Users screen **also** shows the invite link, copyable — email is the convenience, the link is the guarantee.
- **The nav names domains, not actions.** "Users" keeps its name even in v1, when the only thing inside it is the invite form; new user-related surfaces are added *inside* Users rather than beside it. Nav is muscle memory — items don't get renamed between releases.
- Light theme only. No toggle, no `prefers-color-scheme` branch, no `dark:` variants. Dark mode is planned as a separate later pass.
- Two fonts: IM Fell English for titles at every level (never below 16px), IBM Plex Mono for all non-title text including data. No third face.
- Neutrals locked: paper `#FAF8F4`, card `#FFFFFF`, ink `#1A1917`, muted `#6B6862`, rule `#E5E0D8`, edge `#8C8880`. All AA-verified.
- Purple is the brand accent and never a severity. Severity hues: critical red, high orange, medium amber, low blue.
- Desktop only (1440 target, 1280 min) but fluid within it: 720px prose / 1120px table columns are maximums, not fixed widths. No mobile or tablet layouts designed; nothing breaks below 1280 either.
- Building rules bind implementation: no magic numbers (everything is a token), components size to their container, long values never widen the page, the body never scrolls horizontally.
- Ten shared components, each earning its place by two or more screens. No MetricCard, no Breadcrumbs, no Sidebar.
- Nine cross-screen consistency rules, including three-states-always and absent-not-disabled for viewers.

## Still needed

- Pick the hexes for the deep purple and the four severities — **deferred on purpose** to when the frontend is being built, so the purple can be auditioned against real screens. Hues and rules are locked (purple is the accent and never a severity; severity is red/orange/amber/blue; AA on paper). Last unfilled values in Foundations; nothing is blocked on them.
- **Pick the email provider and the sending domain.** Transactional email is decided (C17 closed — the backend emails invites and reset links; invites also keep a copyable link in the UI as a spam fallback). The code is small; what's left is choosing Resend/Postmark/SES and standing up **SPF + DKIM + DMARC** on a domain you own. Forgot/Reset password stay unbuildable until that exists.
- **Fourteen contract asks + one doc contradiction** block the UI — see [`FLOWS.md` § Contract asks](FLOWS.md#contract-asks). The heavy ones: no `GET /agents` (C1), no way to set the Pi's target network (C2), and **no `/users` resource at all** (C3, C4, C16), which leaves Users & invites mostly unbuildable — and, via **C16**, leaves the frontend with no documented way to learn the user's **role**, which every "absent, not disabled" affordance in the product depends on. C8 resolved (`cve_id` exists); C7 resolved (accepting an invite **does** issue a session → lands on Home); C12 is a BACKEND.md self-contradiction, not a contract gap.
- One design call left: the stale-coverage threshold (N days). The 409 busy-Pi copy is now proposed in the Agents spec.
- Lock B3 and B4 (both clarified; B4 needs C1 + C2 landed). B1/B2 wait on C14, C15, C16.
- **All 13 screens are specced.** Home, the four B3 read screens, Agents, Settings, Users & invites, and the five auth screens including **forced password change** (2026-07-13, the last one).
- Build the first vertical slice: login → Home with live data.

## Later, not MVP

- LLM explainer on scan/finding detail.
- Search, breadcrumbs, filters, charts, richer agent history, password strength UI, theme toggle, and other ideas in `IDEAS.md`.
