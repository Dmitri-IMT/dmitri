# Frontend UX audit and implementation architecture

> **Status:** Stage 1 complete (2026-09-19). This document turns the existing
> product and code review into the source plan for the professional UI work.
> It supplements [`FOUNDATIONS.md`](FOUNDATIONS.md), [`FLOWS.md`](FLOWS.md),
> and [`SCREENS.md`](SCREENS.md); it does not replace their authority.

## Scope and method

The review covered the authenticated shell, Home, scans, scan detail, network,
host detail, devices, Settings, the global assistant, reports, shared tables,
loading, blank, and error components. It used the implemented React routes,
shared components, tests, and design documentation as evidence.

The local API and frontend were running during the review. Browser automation was
not available in this session, so the visual acceptance checklist below must be
completed in a browser with a real account before Stage 2 is accepted.

## Product decisions

### Language

The user-facing application language is Brazilian Portuguese. Technical labels
that a specialist may need, such as CVE, IP, port, or service name, remain in
their standard form and receive a nearby plain-language explanation when needed.

This replaces the current mixed interface, where navigation, tables, errors, AI
cards, and reports use both Portuguese and English.

### Theme and visual identity

Light and dark themes are shipped product behaviour. The shared semantic tokens
in `frontend/src/index.css` own both themes. Purple `#600BB5` is the sole action
accent. Severity remains textual and neutral so colour is never the only way to
understand a security result.

### Responsive boundary

The product remains desktop first, but it must remain usable at widths from
1024px upward. The page shell never scrolls horizontally. Dense tables may scroll
inside their own frame. Navigation must collapse into a menu before it competes
with the account control or page content.

### Vocabulary

The navigation and page vocabulary must distinguish the network that was scanned
from the Dmitri hardware that performed the scan:

| Current term | Product term | Meaning |
| --- | --- | --- |
| Home | Início | The current security summary and next action. |
| Scans | Varreduras | Historical scan runs and their reports. |
| Network / Machines | Rede / Equipamentos encontrados | Devices detected on the selected network. |
| Devices / Dmitri boxes | Agentes Dmitri | Hardware that executes scans. |
| Users | Usuários | People allowed to use the organization. |
| Settings | Configurações | Account and organization preferences. |

## Findings and priorities

| Priority | Finding | Impact | Planned remedy |
| --- | --- | --- | --- |
| P0 | The shipped dark theme and purple accent conflict with `FOUNDATIONS.md`. | Teams cannot make consistent visual decisions. | Reconcile the foundation source now; Stage 2 applies its tokens consistently. |
| P0 | User-facing copy is mixed between Portuguese and English. | It weakens clarity for the non-technical target audience. | Create a shared PT-BR copy catalog and migrate by journey. |
| P0 | The top bar has six links plus a theme toggle and an email control in one row. | Long email addresses and narrower desktop widths can crowd navigation. | Add a compact navigation pattern and test it at 1024px and 1440px. |
| P1 | Home presents an attention count but the journey is spread across a table, side panels, and a separate AI card. | A first-time user can miss the recommended next action. | Shape Home around one current assessment, one primary action, and evidence below it. |
| P1 | Scan and host detail screens place technical inventory, findings, AI output, reports, and history in one vertical stream. | Readers must scan long pages to understand what to do first. | Create a clear summary layer with expandable technical sections. |
| P1 | Shared blank, error, and loading patterns exist, but their copy and retry labels remain English. | States feel inconsistent and less reassuring. | Localize and standardize all three states in the shared primitives. |
| P1 | The assistant is always reachable, but pages without a scan or host context only redirect to scan selection. | The assistant feels unavailable on much of the product. | Define page-aware starter questions and a deliberate no-context state. |
| P2 | Report preview is functional but needs browser visual verification for sizing, iframe readability, keyboard focus, and download confirmation. | A report may be hard to inspect before download. | Verify with explained and technical reports in both themes and at the responsive boundary. |
| P2 | AI usage is shown in Settings beside account actions. | It is useful operational data but competes with personal account tasks. | Decide in the screen specification whether it stays as an admin-only Settings section or becomes an organization diagnostics view. |

## Delivery architecture

```text
Foundations and copy
        |
        v
Shell, navigation, states, shared components
        |
        v
Home and scan journey
        |
        v
Network, host, agent, user, and settings journeys
        |
        v
Assistant, reports, accessibility, and visual acceptance
```

Every delivery slice must include its normal, blank, loading, and error states.
It must pass lint, typecheck, focused tests, and a browser review at 1024px and
1440px in light and dark themes.

## Staged implementation plan

### Stage 1 — audit and design contract

**Complete.** This audit records the product vocabulary, theme decision,
responsive boundary, priorities, implementation sequence, and visual acceptance
criteria. `FOUNDATIONS.md` now reflects the shipped theme and accent.

Recommended Codex model: **GPT-5.6 Terra, medium reasoning**. It offers the
right balance for decisions that cross code, content, and UI architecture.

### Stage 2 — shared visual system and application shell

Unify semantic tokens, button and control boundaries, text styles, cards,
dialogs, tables, status states, and navigation. Add the compact navigation
pattern and move product copy to PT-BR in shared surfaces first.

Recommended model: **GPT-5.6 Terra, medium reasoning** for component decisions;
**GPT-5.6 Luna, medium reasoning** for repetitive copy migration and mechanical
test updates.

### Stage 3 — Home and scan journey

Redesign the Home page around the current assessment and one next action. Then
make Scan Detail lead with the explanation, priority action, and report actions,
with findings and technical inventory below the summary layer.

Recommended model: **GPT-5.6 Terra, high reasoning** for the Home and Scan
information architecture; **Terra, medium** for bounded implementation slices.

### Stage 4 — network and operational journeys

Apply the same hierarchy to Network, Host Detail, Agents Dmitri, Users, and
Settings. Preserve technical detail while placing identity, status, and the
next useful action first.

Recommended model: **GPT-5.6 Terra, medium reasoning**. Use **Luna, medium**
for localized table labels, tests, and contract type updates.

### Stage 5 — assistant and reports

Give the global assistant explicit page-aware starter questions, helpful
empty-context guidance, consistent rate-limit feedback, and reviewed history
behaviour. Finish the report-preview experience with a visual and keyboard audit.

Recommended model: **GPT-5.6 Terra, medium reasoning**. Escalate only an
unresolved interaction or accessibility problem to **GPT-5.6 Sol, high**.

### Stage 6 — acceptance and polish

Run the browser acceptance checklist, keyboard-only paths, text-overflow cases,
theme contrast review, and data-rich scenarios. Fix only issues found by this
review; avoid a speculative final redesign.

Recommended model: **GPT-5.6 Luna, medium reasoning** for the checklist and
small fixes; **Terra, medium** when a defect changes a shared component or user
flow.

## Browser acceptance checklist

Run each check in light and dark themes at 1024px and 1440px:

1. Top navigation remains readable; no page-level horizontal scroll occurs.
2. A long email address does not hide navigation, the theme control, or logout.
3. Home answers what needs attention and presents a clear next action.
4. Scan Detail exposes the plain-language summary before technical tables.
5. Network and host tables preserve readable labels and scroll only inside the
   table frame.
6. The assistant provides useful guidance on Home, scan, host, and no-context
   pages.
7. Explained and technical report previews are legible, closable with Escape,
   and confirm the download.
8. Every action is reachable with keyboard navigation and has visible focus.
9. Blank, loading, and error states use PT-BR and tell the person what to do
   next.
