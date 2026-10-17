# Remote agent updates — design proposal

Status: proposal for review. No implementation is authorized by this file.

## Scope and placement

Add update status to the existing device detail page only. Do not add a fleet dashboard,
campaign view, or navigation destination. Show one device at a time. The section summarizes
installed and available versions, update readiness, release notes, and the current or latest
operation. Use only contract fields and names in `INTEGRATION.md`; generated OpenAPI types
remain the source of frontend API types.

On the existing page, place `AgentUpdateSection` after `AgentIdentity` and before the existing
scan controls/history. Keep it visible for an authorized device record regardless of scan
section visibility. A revoked device is read-only and cannot start an update. Do not couple
update handlers to `useScanCommand`; updating must never start or cancel a scan.

## Flow

1. Read availability and recent operation history. Display installed app/package version and
   observation time, catalogue availability, and device readiness as separate facts.
2. When a verified release is available and readiness is `ready`, an Admin opens the release
   notes and compares installed and target app/package versions.
3. Admin selects **Update device**. A confirmation dialog names this device, target version,
   and the manual action. Confirm sends only the selected release identity and expected
   observed version under the API's idempotency contract.
4. Show the operation returned by the server. Poll its operation state while active; refresh
   availability/history after mutation and on explicit **Refresh status**. Refresh is read-only.
5. Keep local phase/outcome separate from remote contact/confirmation. Close only as `succeeded`
   after the contract's local success and matching current-session confirmation evidence.

Never promise a start time or queue work for an offline device. Never show a made-up percentage.

## Compact mockups (pt-BR)

```text
[Detalhes do dispositivo]
Versão instalada       1.0.5 · pacote 1.0.5-1
Versão disponível      1.0.6 · pacote 1.0.6-1
Atualização            Pronta
Notas da versão        Correções e melhorias…
[Atualizar dispositivo]
```

```text
[Confirmar atualização]
Atualizar “Dmitri escritório” para 1.0.6?
A solicitação é manual. A varredura não será iniciada por esta ação.
[Voltar] [Atualizar dispositivo]
```

```text
[Atualização do dispositivo]
1.0.5 → 1.0.6     Instalando · contato atual
Preparando → Instalando → Verificando → Aguardando confirmação
Última evidência: pacote local 1.0.6-1
```

The scan sentence in the dialog is unnecessary if it reads as implementation detail; preferred
final dialog copy is simply the device, target version, and explicit confirmation. The update
section must remain visually distinct from scan controls through a shared Card and heading,
not a new color or bespoke status treatment. Use existing card, dialog, button, timestamp,
status, and toast components where present. Follow `docs/ui/FOUNDATIONS.md`: semantic tokens,
closed type scale, spacing scale, focus ring, plain ink status text, light theme, and no severity
colors. Do not add one-off native interactive controls.

## State and action matrix

| Contract state | Display | Admin action |
|---|---|---|
| `availability=available`, readiness `ready` | Installed vs available versions; notes | Confirm manually |
| `availability=up_to_date` | Installed version; “Up to date” | None |
| Availability `unknown` or installed version unknown | “Installed version unknown”; no comparison | None; refresh status |
| Availability `unavailable` | Catalogue unavailable/expired; last check time if supplied | Refresh status only |
| Readiness `offline` | Offline; no queued update | None; refresh status |
| `bootstrap_required` | “Assisted setup required before remote updates” | None; no fake setup link or remote bootstrap promise |
| `revoked` | Revoked/read-only state | None |
| `busy` | Existing operation/device busy | Follow operation; no second request |
| `requested` | Request accepted; awaiting device claim | No repeat action |
| `preparing`, `installing`, `verifying` | Current phase in text, no percentage | No cancel control |
| `awaiting_confirmation` | Local success; awaiting server confirmation; show contact separately | Refresh status |
| `succeeded` | Confirmed target version and evidence time | None |
| `recovering` | Recovery in progress | No action |
| `rolled_back` | Prior version restored; name observed version when available | None |
| `failed`, `expired` | Terminal operation outcome and safe next-step text | New attempt only if fresh availability allows it |
| `needs_intervention` | Assisted intervention required; scans/updates may remain blocked | No retry CTA; show no unsupported repair path |
| Contact `stale` / `unknown` | Label contact evidence separately from local outcome | Refresh status |

Role is authoritative from `/users/me` and server admission. Hide all update mutation controls
for Viewer. Do not rely on hidden buttons for authorization. A failed API request shows a localized
toast; it does not replace or erase the operation's persisted phase/outcome. Backend outage is
not local install failure. Never expose shell output, secrets, raw diagnostics, or internal IDs.

## Main control copy (en / pt-BR / ru)

| Key / use | English | Português (Brasil) | Русский |
|---|---|---|---|
| Section | Agent update | Atualização do agente | Обновление агента |
| Installed | Installed version | Versão instalada | Установленная версия |
| Available | Available version | Versão disponível | Доступная версия |
| Ready | Ready to update | Pronto para atualizar | Готово к обновлению |
| Confirm action | Update device | Atualizar dispositivo | Обновить устройство |
| Confirm title | Update this device? | Atualizar este dispositivo? | Обновить это устройство? |
| Confirm submit | Update device | Atualizar dispositivo | Обновить устройство |
| Cancel dialog | Back | Voltar | Назад |
| Refresh | Refresh status | Atualizar status | Обновить статус |
| Up to date | Up to date | Atualizado | Обновлено |
| Await confirmation | Awaiting confirmation | Aguardando confirmação | Ожидание подтверждения |
| Recovered | Previous version restored | Versão anterior restaurada | Предыдущая версия восстановлена |
| Intervention | Assisted intervention required | É necessária intervenção assistida | Требуется помощь специалиста |
| Bootstrap | Assisted setup required before remote updates | É necessária preparação assistida antes de atualizações remotas | Перед удалёнными обновлениями требуется подготовка специалистом |

All visible labels, phases, release metadata, next-step messages, dialog text, toast errors,
accessible names, and live announcements need entries in all three catalogs. Do not hard-code
English fallbacks. Release notes are bounded plain text supplied by the release contract; render
as text, not HTML.

## Accessibility and responsive behavior

Use the shared Dialog primitive. On open, move focus into it; keep Tab/Shift+Tab inside; Escape
and the back action close without submitting; return focus to **Update device**. The submit
button has an explicit accessible name including the target version. While submitting, expose
busy state and prevent duplicate submission; do not remove the focused control unexpectedly.

Expose operation phase changes through a polite `aria-live="polite"` status region. Announce
meaningful phase/outcome changes, not every poll or timestamp. Use `role="status"` for ordinary
progress; reserve alert semantics for toast notifications. Status must be written in text and
not conveyed by color or icon alone. Keyboard users can reach every action in visual order; all
controls have visible focus and no focus trap outside the dialog. Respect reduced-motion.

At narrow widths, stack version labels and values, wrap release notes, and make dialog actions
full-width and vertically stacked when needed. Keep the page free of horizontal scrolling. Do
not introduce mobile-only actions or hide readiness and recovery state.

## Paths and verification handoff

Existing paths to compose/extend (E):
- `frontend/src/pages/DeviceDetail.tsx` — section placement; preserve active/revoked branches.
- `frontend/src/pages/agents/ScanControl.tsx` — adjacent scan behavior; no update coupling.
- `frontend/src/pages/agents/AgentIdentity.tsx` — existing device identity.
- `frontend/src/api/agents.ts`, `frontend/src/hooks/useToast.ts` — existing API/toast patterns.
- `frontend/src/i18n/messages/{en,pt-BR,ru}.ts` — translations.

Proposed new paths (N), as named in `INTEGRATION.md`:
- `frontend/src/api/agentUpdates.ts`
- `frontend/src/hooks/useAgentUpdate.ts`
- `frontend/src/pages/agents/AgentUpdateSection.tsx`
- `frontend/src/pages/DeviceDetail.updates.test.tsx`

Existing test paths (E): `frontend/src/pages/DeviceDetail.test.tsx`,
`frontend/src/pages/DeviceDetail.command.test.tsx`, `frontend/src/test/agentsHarness.ts`.
The new test path above is proposed, not present. Verify viewer action absence; confirmation and
idempotent submission; each readiness/availability state; local success versus remote
confirmation; rollback/intervention; toast versus operation history; translations, keyboard and
live-region behavior; and that update actions do not trigger scan start/cancel. No tests were run
for this design proposal.

## Open uncertainties

- The architecture does not settle the final owner-facing wording for “contact” freshness or
  the safe next-step copy for individual terminal error codes. Use localized, sanitized messages
  from the closed contract; do not invent diagnostic details.
- A `refresh status` control is optional in the integration spec. Include it only if the existing
  query pattern can refetch read-only GETs without suggesting device wake-up or install.
- The exact app-version/package-version layout can follow actual generated response fields; show
  both when available and preserve unknown as unknown rather than infer from source version.
