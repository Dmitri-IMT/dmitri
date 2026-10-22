# Design — OPC UA in NSPi

Status: approved for Tasks 5–6 by the user on 2026-10-22 after authorizing resolution of the approval gate. Reuse the existing industrial-services interface described below.

Proposal for `feature/nspi-scan-opcua` at `971ba8d`. Frontend is the primary interface, as clarified by the user on 2026-10-20. TUI work is limited to compatibility. Uses the existing NSPi `inventory` and `read_only_mapping` submodes; adds no mode, credential flow, finding, or severity.

## Reuse and source paths

Verified shipped UI paths:

- Host page shell/card: `frontend/src/pages/HostDetail.tsx` (industrial-services card).
- Shared renderer to extend with protocol dispatch: `frontend/src/pages/hosts/IndustrialServices.tsx` (currently assumes every service has `.units`).
- Scan summary reuse: `frontend/src/pages/scans/ScanIndustrialServices.tsx`, rendered by `frontend/src/pages/ScanDetail.tsx`.
- Expand/collapse interaction: `frontend/src/components/Disclosure.tsx` (Radix Collapsible + shared Button; keeps `aria-controls` while closed).
- Existing strings: `frontend/src/i18n/messages/en.ts`, `pt-BR.ts`, `ru.ts`; hook `frontend/src/i18n/useI18n.ts`.
- Request feedback: `frontend/src/hooks/useToast.ts` and existing toast provider; use it for request/action errors. Preserve `ReadDetailGate` page-level load handling.
- TUI detail and summary: `hardware-agent/src/agent/tui/screens/device_detail.py` (`_render_industrial`), `hardware-agent/src/agent/tui/screens/scan_view.py` (`_render_category_summary`, currently no Modbus summary), and `hardware-agent/src/agent/tui/screens/scan_progress.py` (stage labels/events).

Keep HostDetail's existing Industrial services Card and scan detail's existing Industrial services section. Reuse Card/CardContent, section headings, `IndustrialServices`, and `Disclosure`; don't add a tab, route, mode selector, or bespoke interactive element. The current renderer labels every row Modbus TCP and reads `.units`; protocol dispatch is the required seam. Existing i18n mixes hardcoded English inside this renderer; new and touched OPC UA copy must use the catalogs. Shipped implementation is light-only even though FOUNDATIONS now describes light and dark; avoid theme-specific styling and use existing semantic tokens/components.

## Screen shape

```text
Host detail
  ...existing sections...
  [Card: Industrial services]
    Modbus TCP · port 502                         [existing]
      ...units and ranges...
    OPC UA · port 4840 · Confirmed
      Endpoint security: None / Anonymous advertised
      Mapping: Anonymous session accepted
      Browse: Completed · sample only
      Nodes with successful anonymous Value reads: 3
      [Show observed details  v]
        Product / build identity: ...
        Endpoints: 2 (secure endpoints are inventoried)
        Coverage: partial · sample limit reached
        Observed nodes: Name | NodeId | Data type | Read result
```

Use `OPC UA` as the protocol title, port and confidence as existing compact metadata. Show only typed, bounded fields supplied by the observation. The disclosure includes sampled node metadata: bounded DisplayName/BrowseName, sanitized textual NodeId, data type and the status of the attempted read. Render these as escaped plain text, never links or markup; omit opaque identifiers as specified by the contract. Never render endpoint URLs, certificate material, raw process values, or raw error strings. Secure endpoints remain listed in endpoint inventory/coverage; disclose that v1 maps only an explicitly advertised `SecurityPolicy None` + `MessageSecurityMode None` + Anonymous endpoint. Do not offer credentials or certificates. An announced Anonymous token is configuration only. State session, Browse and Value results separately. A successful Value read proves only anonymous read capability for the observed node; it does not establish application meaning, sensitive content, unauthorized access, write capability, or a vulnerability. Metadata-only reads do not increase the count of successful Value reads.

## Flow and states

1. Open existing machine detail or scan detail; the existing section displays protocol-specific rows.
2. Read a row's summary. Expand `Show observed details` using shared Disclosure to review bounded observations and coverage.
3. A scan without OPC UA data (including a legacy scan) has unknown OPC UA status. Do not infer absence or render a negative OPC UA result. Existing empty industrial-services treatment remains when the whole list is empty.
4. UA-only: render OPC UA row. Mixed: render each Modbus and OPC UA row independently, preserving their own protocol-specific details.
5. Candidate/unconfirmed: show `OPC UA service not confirmed`; don't label it OPC UA confirmed based on open port alone.
6. Inventory complete, mapping not requested: show endpoint inventory and `Mapping not requested`.
7. Anonymous token/policy advertised: label `Anonymous access advertised`; never say anonymous access succeeded until session succeeds.
8. Session accepted: `Anonymous session accepted`. Browse and Value each retain independent status; do not imply one from the other. A null/unattempted Value status shows `Not tested`; it must not appear as a failed read or a confirmed negative result. Expanding details reveals only the bounded sample already collected, without triggering more reads of the device.
9. Denied: `Anonymous session denied` or `Access denied`; keep inventory and coverage. Do not call the whole service inaccessible.
10. Secure-only endpoints: `Secure endpoint advertised; mapping unavailable in this version`. Keep endpoint count/coverage and do not prompt for credentials.
11. Partial/truncated: show observed counts and `Partial sample`; communicate limit/coverage by a localized reason label, not raw exception text.
12. Corrupt/unreadable stored observation: retain the OPC UA row and other services; show `OPC UA details are unavailable`. Do not reinterpret as Modbus.
13. Request failures use the existing toast; page uses existing `ReadDetailGate`. No inline error panel.

## Exact new i18n keys and copy

Catalog paths below are `industrial.opcua.*`. Values are exact owner-facing copy; interpolate `{port}`, `{count}`, `{reason}` only from safe typed/localized values.

| Key | en | pt-BR | ru |
|---|---|---|---|
| title | OPC UA · port {port} | OPC UA · porta {port} | OPC UA · порт {port} |
| confirmed | Confirmed | Confirmado | Подтверждён |
| unconfirmed | OPC UA service not confirmed | Serviço OPC UA não confirmado | Служба OPC UA не подтверждена |
| advertised | Anonymous access advertised | Acesso anônimo anunciado | Анонимный доступ объявлен |
| session_ok | Anonymous session accepted | Sessão anônima aceita | Анонимный сеанс принят |
| session_denied | Anonymous session denied | Sessão anônima recusada | В анонимном сеансе отказано |
| browse_ok | Browse completed · sample only | Navegação concluída · somente amostra | Обзор завершён · только выборка |
| values_label | Nodes with successful anonymous Value reads | Nós com leitura anônima de valor confirmada | Узлы с успешным анонимным чтением Value |
| nodes_label | Observed nodes | Nós observados | Наблюдаемые узлы |
| node_name | Name | Nome | Имя |
| node_id | NodeId | NodeId | NodeId |
| data_type | Data type | Tipo de dado | Тип данных |
| read_result | Read result | Resultado da leitura | Результат чтения |
| not_tested | Not tested | Não testado | Не проверено |
| secure_only | Secure endpoint advertised; mapping unavailable in this version | Endpoint seguro anunciado; mapeamento indisponível nesta versão | Объявлена защищённая конечная точка; сопоставление недоступно в этой версии |
| not_requested | Mapping not requested | Mapeamento não solicitado | Сопоставление не запрашивалось |
| partial | Partial sample | Amostra parcial | Частичная выборка |
| details | Show observed details | Mostrar detalhes observados | Показать наблюдения |
| details_hide | Hide observed details | Ocultar detalhes observados | Скрыть наблюдения |
| details_unavailable | OPC UA details are unavailable | Detalhes de OPC UA indisponíveis | Данные OPC UA недоступны |
| secure_inventory | Secure endpoints are included in inventory | Endpoints seguros estão incluídos no inventário | Защищённые конечные точки включены в инвентаризацию |
| sample_limit | The observed sample reached a limit: {reason} | A amostra observada atingiu um limite: {reason} | Для наблюдаемой выборки достигнут предел: {reason} |
| sample_read_note | This confirms anonymous read capability for the observed sample only. | Isso confirma apenas a capacidade de leitura anônima da amostra observada. | Это подтверждает только возможность анонимного чтения наблюдаемой выборки. |
| read_failed | Could not load industrial service details. | Não foi possível carregar os detalhes do serviço industrial. | Не удалось загрузить сведения о промышленной службе. |

Map enum reason codes to localized fixed labels; never interpolate server exception text. Add all keys to all three catalogs, keeping key parity. Existing `common.industrialServices` remains the section title.

## Accessibility and interaction

Use `Disclosure` with a descriptive trigger name (`Show observed details` / `Hide observed details`), its persistent `aria-controls`, and native Radix keyboard behavior: Tab to trigger, Enter/Space toggles, focus stays on trigger, expanded/collapsed state announced. Preserve shared Button focus-visible ring, hover, active, and pointer states. Keep semantic headings and `<dl>` label/value pairs; counts and statuses include text and never rely on color or icon alone. Hide decorative icons from assistive technology. Do not make the whole card an interactive target.

The disclosure starts closed (`defaultOpen=false`). Proposed UA-only test IDs:
`industrial-opcua-{port}`, `opcua-details-{port}`, `opcua-details-caret-{port}`,
`opcua-observed-nodes-{port}`. Scope them to the existing host container on scan pages;
keep existing Modbus test IDs. Prefer accessible roles/names in tests; use IDs when
disambiguating protocols and hosts. The node sample is a semantic table with a caption.

## TUI compatibility only; detailed presentation deferred

Detailed OPC UA rendering, node tables and new TUI summaries are deferred. The frontend owns the full presentation in this delivery. Existing TUI consumers must handle the new service union without exceptions or interpreting OPC UA as Modbus. Preserve scan execution, cancellation, existing Modbus rendering and escaping. Unsupported UA detail may be omitted without claiming the service is absent.

Change existing stage labels or event handling only when needed to keep the shared-stage behavior correct. No dedicated TUI implementation task or design expansion is required to finish this feature.

The existing `_render_header` also has `Time limit reached during Modbus inventory`.
For the new shared-stage deadline, show `Time limit reached during industrial inspection`
and retain legacy metadata fallback only for old scans. Do not attribute an OPC UA
limit to Modbus. Process timestamps/values remain excluded from all these views.

## Scope and consistency

This design is observation-only and adds no OPC UA finding, vulnerability count, severity, safety claim, or AI detail. AI-safe aggregates remain outside this screen. Contract/browser types must be generated from OpenAPI; this design does not define API types. No app code, skill, contract, or other spec changes are part of this document.
