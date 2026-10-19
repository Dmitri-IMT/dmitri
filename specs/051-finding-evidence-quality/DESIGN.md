# Design — Qualidade da evidência dos achados

Status: aprovado pelo usuário em 2026-10-10, ao solicitar avanço após revisar a proposta e a prévia · Entrega A

**Prévia visual:** [preview.html](preview.html) — página HTML estática para revisão no navegador, sem dependências de aplicação. [Captura desktop](preview-desktop.png) mostra o topo da página; os demais estados estão no HTML completo.

## Escopo da interface

Atualizar a área expandida de cada vulnerabilidade, que já aparece nas tabelas de scan e de equipamento, para explicar método, estado e confiança da evidência sem alterar as linhas, cartões, grupos de gravidade ou ações existentes. Estender a mesma distinção ao relatório explicado e ao resumo de contagens. A gravidade continua visível e independente da confiança e do método.

**Rotas e fluxo:** `/scans/:scanId` → expandir uma linha de vulnerabilidade → revisar evidência; `/hosts/:hostId` → expandir uma linha de vulnerabilidade → revisar evidência. O menu existente de relatório do scan → abrir prévia/baixar relatório explicado continua igual.

**Arquivos existentes conferidos:**

- `frontend/src/pages/scans/FindingPanel.tsx` — painel de detalhes compartilhado.
- `frontend/src/pages/scans/FindingsTable.tsx` — usa o painel nas variantes de scan e host.
- `frontend/src/pages/ScanDetail.tsx` — grupos e estado vazio do scan.
- `frontend/src/pages/scans/ScanReports.tsx` — prévia e download; falha de geração já usa toast.
- `backend/src/api/services/report_education.py`, `report_education_copy.py`, `report_education_pdf.py` — resumo explicado, idiomas e PDF.
- Catálogos de interface existentes: `frontend/src/i18n/messages/en.ts`, `pt-BR.ts`, `ru.ts`.

**Arquivo novo desta especificação:** `specs/051-finding-evidence-quality/DESIGN.md`. A mudança de produto proposta deve reutilizar os arquivos de interface e relatório acima; não criar uma tela ou fluxo separado.

## Contrato consumido

Usar somente os campos que a proposta de arquitetura aprova:

- `FindingRead.detection_method`: `version_correlation`, `configuration_observation`, `specific_check`, `textual_reference`, `unknown`.
- `FindingRead.evidence_status`: `supported`, `inconclusive`, `conflicting`, `unknown`.
- `FindingRead.confidence`: valores existentes `tentative`, `probable`, `confirmed` ou `null`.
- `FindingRead.evidence_observations`: observações tipadas e limitadas, com condição, método, resultado, procedência/regra, trecho de evidência e endpoint conforme a definição de arquitetura.
- `FindingRead.evidence_truncated`: indica que a lista limitada de evidências foi truncada. `ScanDetail.finding_observations` e `finding_observations_truncated`: observações negativas/inconclusivas sem linha positiva; cada observação tem resultado e origem, limite de 512 no scan. Exibir na área de cobertura/evidência existente do scan e do relatório, incluindo condição testada e indicador de truncamento. Não convertê-las em vulnerabilidades nem somá-las a `evidence_summary.total_records`, `finding_count` ou buckets de método/confiança.
- `ScanDetailResponse.evidence_summary` e `FindingListResponse.evidence_summary`: `total_records`, contagens `by_method`, `by_confidence`, `conflicting_records`, `demonstrated_records` e `scope` (`scan` ou `filtered_findings`). `demonstrated_records` conta somente resultados positivos sustentados de configuração ou verificação específica com procedência válida. O resumo de lista já considera filtros antes da paginação.
- Relatório explicado versão 3: os mesmos `detection_method`, `evidence_status`, `confidence` no apêndice/grupos e `evidence_summary`.

Dados sem observações registradas são legado: `evidence_status` permanece `unknown`, sem inferir estado de `source`, `cve_id`, gravidade ou texto. Para `detection_method`, aplicar somente a exceção aprovada pela arquitetura: reconhecer aliases seguros de correlação (`nmap_vulners`, `nvd`, `nvd_enrichment`); nos demais casos, exibir `unknown`. Manter a confiança histórica como recebida e mostrar o limite de procedência. `confirmed` é o valor de confiança fornecido pelo contrato; nunca converter uma associação de versão em vulnerabilidade explorada.

## Decisões de conteúdo

- **Gravidade** responde “qual o impacto potencial?” e mantém o rótulo atual Critical/High/Medium/Low. **Confiança** responde “quão forte é a evidência registrada?”. **Método** responde “como o alerta foi produzido?”. Apresentar em linhas separadas, sem escala ou cor compartilhada.
- Associação de versão com catálogo: “Versão associada a uma vulnerabilidade conhecida. A presença dessa falha neste equipamento ainda precisa ser validada.” Não dizer que a falha está instalada, foi explorada ou foi comprovada.
- Configuração observada: nomear a condição que foi observada; não chamar isso de exploração comprovada de CVE.
- Verificação específica positiva: nomear a condição testada e o endpoint/alcance que a evidência demonstra. Não generalizar para o equipamento inteiro.
- Menção textual: informar que a referência foi encontrada no texto, sem resultado verificável. Não promover a vulnerabilidade a positiva.
- Estado negativo, inconclusivo, conflitante ou desconhecido sempre descreve só a verificação/evidência registrada. Não usar “seguro”, “corrigido” ou “sem vulnerabilidades” como conclusão geral.
- Repetições de evidência não elevam a confiança. Manter a procedência visível em cada observação.
- Contagens dizem **registros** quando contam linhas/achados; dizem **confiança confirmada** quando usam esse recorte. Não somar linhas da página atual para exibir um total de scan/lista. Mostrar o escopo `scan` ou `filtered_findings` junto ao resumo.
- Exibir observações negativas/inconclusivas como resultado da verificação no scan, separado das linhas positivas; incluir condição, método, endpoint quando houver, fonte/regra e trecho registrado. Não inventar data da observação: a atualidade herdada é a data do scan.
- Preservar o conteúdo e as ações atuais de cada linha/cartão. A nova área é informação explicativa dentro do painel expandido.

## Estados e mockups

O alvo visual segue `docs/ui/FOUNDATIONS.md`: canvas claro, cartões brancos, severidade em palavra de tinta sem matiz, escala tipográfica nomeada, espaços da escala de 4 px, largura de leitura existente e sem sidebar. Mockups são estruturais; usar passos 6 entre itens, 8 entre grupos e 12 entre seções. O painel não ganha margem externa própria.

### Regular — evidência completa e explicável

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [linha atual da vulnerabilidade: gravidade · título · máquina]               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Gravidade: High                     Confiança: Provável                     │
│ Método: Associação de versão                                                │
│ Estado da evidência: Sustentada para a associação de versão                 │
│                                                                              │
│ Versão associada a uma vulnerabilidade conhecida. A presença desta falha   │
│ neste equipamento ainda precisa ser validada.                                │
│                                                                              │
│ Evidência registrada                                                       │
│ CVE-2024-0001 · Serviço 443/tcp · versão observada 2.4.1                    │
│ Fonte: nvd_enrichment · Regra: cpe-match v1                                 │
│                                                                              │
│ Risco / O que é / O que fazer / Evidência / Referências [conteúdo atual]    │
│ [Explicação da IA atual]                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

Severity, confidence, detection method and evidence status occupy distinct labeled fields. Existing risk score and explanation content remain available below. The evidence row may show a neutral monospace identifier/endpoint, but severity has no hue.

### Legado — campos novos ausentes

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [linha atual da vulnerabilidade: gravidade · título · máquina]               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Gravidade: Medium                    Confiança: Não informada                │
│ Método: Desconhecido                  Estado da evidência: Desconhecido       │
│                                                                              │
│ Este registro é anterior ao detalhamento da evidência. Os dados disponíveis │
│ não permitem identificar como o alerta foi produzido ou validar a falha.   │
│                                                                              │
│ [detalhes já existentes continuam abaixo]                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

Do not synthesize provenance from the legacy `source` or infer confirmation from confidence being absent. Keep existing evidence text and references intact.

### Método ou estado desconhecido em registro novo

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Gravidade: High                     Confiança: Preliminar                     │
│ Método: Desconhecido                  Estado da evidência: Inconclusivo        │
│                                                                              │
│ Não foi possível determinar o resultado desta verificação. Isso não        │
│ confirma nem descarta a vulnerabilidade.                                    │
│                                                                              │
│ Evidência registrada                                                       │
│ [trecho disponível ou “Nenhum trecho de evidência foi registrado.”]          │
└──────────────────────────────────────────────────────────────────────────────┘
```

Use the received enum values. Do not replace a known status with “unknown” just because the method is unknown. For `conflicting`, state that records disagree and retain source labels; do not collapse them to a single positive or negative.

Negative and inconclusive scan observations have their own section outside the vulnerability rows. Label the result and tested condition; they never create a positive row or increase the finding-record count. The UI and explained report use scan-level scope for those observations.

### Em branco — nenhum registro no scan

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Vulnerabilidades: 0                                                        │
│ Nenhum registro de vulnerabilidade neste scan.                              │
│                                                                              │
│ Resumo da evidência                                                        │
│ Registros: 0 · Demonstrados: 0 · Escopo: scan                              │
│ Verificações sem achado: 3 · Negativas: 3                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Preserve existing no-findings sentence and scan-completeness branch; do not imply the machine is safe. Do not render an empty finding panel. The empty summary is only shown when the API provides it and its scope is explicit.

### Erro

There is no new request for the expanded panel itself. If loading scan/finding data fails, retain the existing detail-level failure handling; any newly introduced retry/action failure uses the shared toast. If explained PDF preparation fails, the existing toast remains the pattern.

```text
Toast: Não foi possível preparar o relatório. Tente novamente.
```

Never put a new static error paragraph or error card inside the page. No error state should replace usable existing finding content.

## Relatório explicado — trecho do PDF

The report keeps its existing dashboard, severity scale, device summaries and appendix. Add evidence method/status/confidence at each appendix record and a scoped summary in the evidence section; preserve existing education copy and translated report generation. Page breaks may split records only between records, not between a record’s label and its value.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Evidência dos registros                         Escopo: scan                │
│ Registros: 12 · Demonstrados: 2 · Associação de versão: 7                  │
│ Configuração observada: 3 · Verificação específica: 2                       │
│ Referência textual: 0 · Conflitantes: 1                                   │
│ Confiança: Confirmada 2 · Provável 6 · Preliminar 3 · Não informada 1       │
│ Contagens representam registros de vulnerabilidade, não falhas demonstradas.│
│ Verificações sem achado: 3 · Negativas: 2 · Inconclusivas: 1               │
│ Condição: SMBv1 disponível · Resultado: negativo · Endpoint: 445/tcp                         │
│ Fonte: smb-protocols · Evidência: “SMBv1: not offered”               │
├──────────────────────────────────────────────────────────────────────────────┤
│ CVE-2024-0001 | app.exemplo.org | High                                     │
│ Método: Associação de versão   Estado: Sustentada para a associação                 │
│ Confiança: Provável                                                        │
│ Limite: A versão está associada a uma vulnerabilidade conhecida; a presença│
│ da falha neste equipamento não foi validada.                               │
│ Fonte: nvd_enrichment · Regra: cpe-match v1 · Endpoint: 443/tcp                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

Counts above are illustrative only; production values come from version 3 `evidence_summary`, never page row counts. In the API, machine-readable identifiers remain unchanged. In the PDF, translate the display labels using the report’s selected `en`, `pt-BR` or `ru` language. Technical JSON remains technical and keeps contract enum values.

## Copy final (en / pt-BR / ru)

All three languages are supported by the current UI and report catalogs. Exact display strings for this addition:

| Key / meaning | English | Português (Brasil) | Русский |
|---|---|---|---|
| Severity | Severity | Gravidade | Серьёзность |
| Confidence | Evidence confidence | Confiança da evidência | Уверенность в доказательствах |
| Method | Detection method | Método de detecção | Метод обнаружения |
| Status | Evidence status | Estado da evidência | Статус доказательств |
| Version correlation | Version association | Associação de versão | Связь с версией |
| Configuration observation | Observed configuration | Configuração observada | Наблюдаемая конфигурация |
| Specific check | Specific check | Verificação específica | Специальная проверка |
| Textual reference | Text reference only | Apenas referência textual | Только текстовое упоминание |
| Unknown | Unknown | Desconhecido | Неизвестно |
| Supported | Supported for the recorded method | Sustentada para o método registrado | Подтверждается для указанного метода |
| Version-correlation status | Supported for the version association | Sustentada para a associação de versão | Подтверждается для связи с версией |
| Inconclusive | Inconclusive | Inconclusivo | Неубедительно |
| Conflicting | Conflicting evidence | Evidências conflitantes | Противоречивые данные |
| Tentative | Tentative | Preliminar | Предварительная |
| Probable | Probable | Provável | Вероятная |
| Confirmed | Confirmed | Confirmada | Подтверждённая |
| Unreported confidence | Not reported | Não informada | Не указана |
| Correlation explanation | A version is associated with a known vulnerability. Its presence on this machine still needs validation. | Uma versão está associada a uma vulnerabilidade conhecida. A presença dela neste equipamento ainda precisa ser validada. | Версия связана с известной уязвимостью. Её наличие на этом устройстве ещё нужно проверить. |
| Observation explanation | This configuration was observed. This does not show that a known vulnerability was exploited. | Esta configuração foi observada. Isso não demonstra a exploração de uma vulnerabilidade conhecida. | Эта конфигурация была обнаружена. Это не доказывает эксплуатацию известной уязвимости. |
| Specific positive | The check found the stated condition on the recorded endpoint. It does not describe the whole machine. | A verificação encontrou a condição indicada no endpoint registrado. Isso não descreve o equipamento inteiro. | Проверка выявила указанное состояние на записанном узле. Это не описывает устройство целиком. |
| Text reference explanation | A vulnerability reference appeared in the text, but no verifiable positive result was recorded. | Uma referência a vulnerabilidade apareceu no texto, mas nenhum resultado positivo verificável foi registrado. | В тексте встретилось упоминание уязвимости, но проверяемый положительный результат не записан. |
| Inconclusive explanation | The check did not produce a conclusive result. This neither confirms nor rules out the vulnerability. | A verificação não chegou a um resultado conclusivo. Isso não confirma nem descarta a vulnerabilidade. | Проверка не дала однозначного результата. Это не подтверждает и не исключает уязвимость. |
| Legacy explanation | This record predates evidence details. The available data do not show how the alert was produced or validate the vulnerability. | Este registro é anterior ao detalhamento da evidência. Os dados disponíveis não mostram como o alerta foi produzido nem validam a vulnerabilidade. | Эта запись создана до появления подробных данных о доказательствах. Имеющиеся данные не показывают, как возникло предупреждение, и не подтверждают уязвимость. |
| Empty | No confirmed vulnerabilities in accepted evidence for this scan. | Nenhuma vulnerabilidade confirmada nas evidências aceitas deste scan. | В принятых данных этого сканирования нет подтверждённых уязвимостей. |
| Count note | Counts are vulnerability records, not proven failures. | As contagens são registros de vulnerabilidade, não falhas comprovadas. | Числа обозначают записи об уязвимостях, а не доказанные сбои. |
| Report error toast | Couldn't prepare the report. Try again. | Não foi possível preparar o relatório. Tente novamente. | Не удалось подготовить отчет. Попробуйте снова. |

`Confidence` labels are categorical, not percentages. “Confirmed” describes the contract’s confidence classification and does not imply exploitation. For negative observations, use a check-level sentence (“This check did not find…”) and never a machine-wide safety claim.

## Teclado, foco e acessibilidade

- The existing table row expander remains the only control to open/close the panel. Keep its current accessible name and keyboard behavior; do not add a second click target inside the panel.
- Static evidence fields are read in normal document order after severity and before the existing risk/evidence details. Do not add tab stops to labels or values.
- Keep each value adjacent to a visible label and expose the group as a definition list or equivalent name/value semantics. Method/status/confidence must not rely on color or icon alone.
- Evidence excerpts remain selectable text and wrap/scroll within the existing evidence area. CVE/endpoint identifiers use the existing monospace treatment.
- Existing AI action remains after the evidence summary; any request failure is announced through the shared toast. Preserve visible keyboard focus on existing controls.

## Test selectors e verificações de aceitação

Keep the existing `finding-panel-{finding_id}` root stable. Add stable IDs for the new panel state/fields and count summary; derive from the finding ID for per-record fields and use a named scan/host summary root. No selector may depend on translated text.

| Selector requirement | Element |
|---|---|
| `finding-evidence-{finding_id}` | evidence section/state container |
| `finding-method-{finding_id}` | method label/value |
| `finding-status-{finding_id}` | status label/value |
| `finding-confidence-{finding_id}` | confidence label/value |
| `evidence-summary-scan` / `evidence-summary-filtered` | scoped count summary container |
| existing `finding-panel-{finding_id}` | panel root, retained |

Selectors above are design recommendations for stable assertions, not contract fields. Accessible assertions should locate visible labels and values by role/name, assert each distinct dimension independently, and verify keyboard expansion. Check all three language catalogs. Report verification should assert the explained PDF labels and that technical JSON preserves enum values.

Acceptance mapping: **A01–A03** negative/reference/mixed results; **A04–A06** correlation, observed configuration and specific check; **A07–A09** inconclusive, repetition and conflict; **A10** legacy; **A11** partial coverage language; **A12** UI/PDF semantic parity; **A13** scoped summary and no page-local global count; **A14** AI explanation respects recorded limits; **A16** legitimate positive controls remain representable. **A15** is a compatibility/integration gate, not a visual change.

## Fora de escopo e aprovação visual

- No new active test, manual false-positive workflow, confidence percentage, chart, filter or new screen.
- Preserve existing severity grouping, details, AI control, report menu and technical JSON flow.
- Architecture field details remain subject to the approved `ARCHITECTURE.md` / `INTEGRATION.md`; if those documents change enum or summary names, update this spec before implementation.
- The preview is a local, renderizable HTML file using the real Inter Variable and Geist Mono Variable font assets from `frontend/node_modules`. It is a static browser preview rather than a published Artifact. It is optimized for the 1440px desktop target; mobile is not a product requirement. Human visual approval remains pending.
