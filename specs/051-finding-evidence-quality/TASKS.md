# Tasks — Qualidade da evidência dos achados (`051-finding-evidence-quality`)

11 tarefas sequenciais. **#1–#4 concluídas. Execução encerrada por limite do usuário antes da #5.** Specs aprovadas em 2026-10-10; base `471739f`.

Ordem compatível: parser offline → contrato/backend → consumidores → agente. Nenhum novo envio ingest antes da tarefa10. Sem scans reais, deploy, SSH, commit, push ou PR.

Coder/tester: GPT-6 Luna medium. Reviewer GPT-6.1 Sol high para parser/contrato/política/persistência/reconciliação/adaptadores/integração/corpus; medium para apresentação/relatório/IA. Frontend usa perfis frontend. Seleção explícita nesta ferramenta; perfis TOML são referência. Gates focais por tarefa; completos quando a camada fecha (7,8,11). Só reviewer aprova.

## Task 1: Corrigir interpretação NSE offline
- **Description**: Estados fechados e reconhecimento independente de achados; bloquear fallback estruturado e preservar positivos nativos. Sem emitir campos novos no ingest neste passo. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: —
- **Target Files**: `hardware-agent/src/agent/normalize/findings.py`, `hardware-agent/tests/test_findings.py`
- **Tests**: `hardware-agent/tests/test_findings.py`; aceites A01,A02,A03,A07,A16.
- **Success Criteria**:
  - Negativo sem descrição, ids mapa/lista, desconhecido, malformado e mixed não criam falso positivo; MS17 positivo sem check_results permanece; referências textuais no máximo candidato low, nunca confirmação.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: COMPLETE
- **Review Rejections**: 1

## Task 2: Publicar contrato aditivo estrito
- **Description**: Implementar OpenAPI, schemas backend e modelos agente sem habilitar emissão. Atualizar exemplo atual e manter exemplo legado testado. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 1
- **Target Files**: `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`, `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/read.py`, `hardware-agent/src/agent/normalize/contracts.py`, `backend/tests/test_ingest_schema.py`, `backend/tests/test_contract_fidelity.py`, `hardware-agent/tests/test_contract_models.py`
- **Tests**: `backend/tests/test_ingest_schema.py`, `backend/tests/test_contract_fidelity.py`, `hardware-agent/tests/test_contract_models.py`; aceites A10,A15.
- **Success Criteria**:
  - Enums, limites16/512, facts planos e estritos, versão coerente, endpoints e standalone não positivo são validados; legado sem metadados aceita; extras rejeitam; ingest não recebe confidence.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: COMPLETE
- **Review Rejections**: 1

## Task 3: Implementar política e redução backend
- **Description**: Validar fatos fechados de regras sustentadas por corpus e reduzir união determinística antes de truncamento. Reusar scan_evidence e documentar predicados com fixtures de resposta verificadas. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 2
- **Target Files**: `backend/src/api/services/scan_evidence.py`, `backend/tests/test_scan_evidence.py`
- **Tests**: `backend/tests/test_scan_evidence.py`; aceites A04,A05,A06,A07,A08,A09,A10,A13.
- **Success Criteria**:
  - Nenhum nome/fonte/rule positivo isolado confirma; correlação maximum probable; direct válido confirma só condição; unknown degrada; conflitos comparáveis tentative; retenção testemunhas/truncamento monotônico; resumo separa legado/demonstrado.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: COMPLETE
- **Review Rejections**: 2

## Task 4: Persistir evidências e proteger reconciliação
- **Description**: Adicionar revisão40 pai39, integração ingest/upsert/enrichment/risk/inventory e salvaguardas semânticas. Inclui correção focal do vínculo issue_key opcional conforme ISSUE_KEY_DECISION.md, sem reabrir tarefas 2–3 aprovadas. Mantém identidade atual e restringe correção histórica aos aliases conhecidos. Governada por ARCHITECTURE.md e INTEGRATION.md.
- **Target Files (revisão focal autorizada)**: `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`, `backend/src/api/schemas/scan.py`, `hardware-agent/src/agent/normalize/contracts.py`, `backend/src/api/services/scan_evidence.py`, `backend/tests/test_ingest_schema.py`, `backend/tests/test_contract_fidelity.py`, `hardware-agent/tests/test_contract_models.py`, `backend/tests/test_scan_evidence.py`.
- **Tests (vínculo focal)**: Legado sem issue_key; string1–256/null; vínculo incoerente rejeitado; issue_key e issue_key_ambiguous persistidos sem alterar dedupe/HostFindingRecord; replay, reingest, truncamento e catálogo não apagam ambiguidade; CVE referenciada por configuração não confirma CVE.
- **Dependencies**: Task 3
- **Target Files**: `backend/src/api/models/persistence.py`, `backend/alembic/versions/20261010_40_finding_evidence_quality.py`, `backend/src/api/services/persistence.py`, `backend/src/api/services/enrichment.py`, `backend/src/api/services/risk.py`, `backend/src/api/services/inventory.py`, `backend/tests/test_ingest_scan.py`, `backend/tests/test_scan_ingest_route.py`, `backend/tests/test_enrichment_retries.py`, `backend/tests/test_finding_risk_read.py`, `backend/tests/test_inventory_reconcile.py`, `backend/tests/test_finding_evidence_quality_migration.py`, `backend/tests/test_migrations.py`
- **Tests**: `backend/tests/test_ingest_scan.py`, `backend/tests/test_scan_ingest_route.py`, `backend/tests/test_enrichment_retries.py`, `backend/tests/test_finding_risk_read.py`, `backend/tests/test_inventory_reconcile.py`, `backend/tests/test_finding_evidence_quality_migration.py`, `backend/tests/test_migrations.py`; aceites A08,A09,A10,A11,A15.
- **Success Criteria**:
  - Ordem ingest/standalone/jobs não muda resultado; snapshots finais; NVD CPE acrescenta correlação e CVE só contexto; parcial/inconclusivo/truncado não resolve histórico; negativo não instrução resolução; fechamento legítimo preservado; migração alias/snapshot ausente/null/downgrade testados em dmitri_test.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: COMPLETE
- **Review Rejections**: 3

## Task 5: Expor leitura e totais por escopo
- **Description**: Aplicar política em todos serializers FindingRead e usar confidence persistida, com summary filtrado antes da paginação e observações standalone fora dos totais. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 4
- **Target Files**: `backend/src/api/services/read.py`, `backend/src/api/services/home.py`, `backend/tests/test_read_findings.py`, `backend/tests/test_read_scans.py`, `backend/tests/test_read_hosts.py`, `backend/tests/test_home_snapshot.py`, `backend/tests/test_finding_risk_read.py`
- **Tests**: `backend/tests/test_read_findings.py`, `backend/tests/test_read_scans.py`, `backend/tests/test_read_hosts.py`, `backend/tests/test_home_snapshot.py`, `backend/tests/test_finding_risk_read.py`; aceites A10,A12,A13.
- **Success Criteria**:
  - Sem snapshot confidence permanece; isolamento org e filtros exatos; >uma página resumo global correto; legado confirmed não demonstrado; Home mantem itens de atenção; scan summary e limites uniformes.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: COMPLETE
- **Review Rejections**: 1

## Task 6: Atualizar relatórios e verificar PDF
- **Description**: Educação versão3, grupos separados por semântica, JSON técnico completo e copy localizada; renderizar e inspecionar PDF via skill PDF. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 5
- **Target Files**: `backend/src/api/services/reports.py`, `backend/src/api/services/report_education.py`, `backend/src/api/services/report_education_pdf.py`, `backend/src/api/services/report_education_copy.py`, `backend/tests/test_reports.py`, `backend/tests/test_report_education.py`
- **Tests**: `backend/tests/test_reports.py`, `backend/tests/test_report_education.py`; aceites A10,A12,A13,A14.
- **Success Criteria**:
  - Método/status/confidence/limites em grupos e apêndice equivalentes ao contrato; standalone na cobertura fora dos totais; compat evidence_counts; PDF renderizado e páginas afetadas inspecionadas sem clipping.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: COMPLETE
- **Review Rejections**: 3

## Task 7: Limitar explicação automatizada e fechar backend
- **Description**: Contexto versão5 para overview e todos chats; prompts respeitam evidência e contexto agregado completo, conservando limites de amostra e anonimização. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 6
- **Target Files**: `backend/src/api/services/ai/context.py`, `backend/src/api/services/ai/chat.py`, `backend/src/api/services/ai/groq.py`, `backend/tests/test_ai_context.py`, `backend/tests/test_ai_chat.py`, `backend/tests/test_ai_groq.py`
- **Tests**: `backend/tests/test_ai_context.py`, `backend/tests/test_ai_chat.py`, `backend/tests/test_ai_groq.py`; aceites A10,A12,A14,A15.
- **Success Criteria**:
  - Nenhum raw facts/evidence/endpoint/identidade enviado; unknown não target_observation default; conflito/inconclusivo/correlação nunca elevada; negativos não alvo seguro; análise salva intacta. Reviewer executa gate backend completo: database.ps1/sh --test em dmitri_test, ruff check src tests e pytest.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 8: Apresentar método, limites e resumo web
- **Description**: Gerar tipos OpenAPI e atualizar painéis/tabelas/scans/host e três catálogos conforme DESIGN. Consumir resumo API para host paginado. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 7
- **Target Files**: `frontend/src/types/openapi.d.ts`, `frontend/src/pages/scans/FindingPanel.tsx`, `frontend/src/pages/scans/FindingsTable.tsx`, `frontend/src/pages/scans/findingColumns.tsx`, `frontend/src/pages/scans/ServiceTargetedFindings.tsx`, `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/hosts/HostFindings.tsx`, `frontend/src/pages/HostDetail.tsx`, `frontend/src/api/findings.ts`, `frontend/src/i18n/messages/en.ts`, `frontend/src/i18n/messages/pt-BR.ts`, `frontend/src/i18n/messages/ru.ts`, `frontend/src/i18n/messages/catalog.types.ts`, `frontend/src/pages/scans/FindingPanel.test.tsx`, `frontend/src/pages/scans/findingColumns.test.tsx`, `frontend/src/pages/ScanDetail.test.tsx`, `frontend/src/pages/HostDetail.test.tsx`
- **Tests**: `frontend/src/pages/scans/FindingPanel.test.tsx`, `frontend/src/pages/scans/findingColumns.test.tsx`, `frontend/src/pages/ScanDetail.test.tsx`, `frontend/src/pages/HostDetail.test.tsx`; aceites A05,A06,A07,A10,A12,A13,A15.
- **Success Criteria**:
  - Severity/method/confidence/status independentes; labels e seletores DESIGN, expansion keyboard, legacy/conflict/truncation e standalone; contagem filtrada API. npm.cmd gen:types, lint, format:check, typecheck, test, build pelo reviewer frontend.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 9: Anotar adaptadores e reduzir evidência local
- **Description**: Adicionar metadados por TargetedIssue e todos extratores existentes NSE/OT/targeted; implementar policy/merge local equivalente backend sem novos scans ou confirmação por nome ferramenta. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 8
- **Target Files**: `hardware-agent/src/agent/targeted/models.py`, `hardware-agent/src/agent/targeted/tls.py`, `hardware-agent/src/agent/targeted/ssh.py`, `hardware-agent/src/agent/targeted/smb.py`, `hardware-agent/src/agent/targeted/web.py`, `hardware-agent/src/agent/targeted/cleartext.py`, `hardware-agent/src/agent/normalize/findings.py`, `hardware-agent/tests/test_findings.py`, `hardware-agent/tests/unit/test_targeted_tls.py`, `hardware-agent/tests/unit/test_targeted_ssh.py`, `hardware-agent/tests/unit/test_targeted_smb.py`, `hardware-agent/tests/unit/test_targeted_web.py`, `hardware-agent/tests/unit/test_targeted_cleartext.py`
- **Tests**: `hardware-agent/tests/test_findings.py`, `hardware-agent/tests/unit/test_targeted_tls.py`, `hardware-agent/tests/unit/test_targeted_ssh.py`, `hardware-agent/tests/unit/test_targeted_smb.py`, `hardware-agent/tests/unit/test_targeted_web.py`, `hardware-agent/tests/unit/test_targeted_cleartext.py`; aceites A04,A05,A06,A07,A08,A09,A16.
- **Success Criteria**:
  - Regras fechadas com fatos reais/endpoint/unidade; unsupported fica tentative; Modbus read não write/CVE; MS17 limitado; CVE referenciada em configuração não confirma CVE; duplicatas/contradições e truncamento em permutações equivalentes backend.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 10: Integrar emissão e preservar todos caminhos
- **Description**: Somente após backend e consumidores aprovados, runner coleta uma vez observações/achados e produz versão1; transporte, arquivo local, assinatura e parcial preservam contrato. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 9
- **Target Files**: `hardware-agent/src/agent/scanner/runner.py`, `hardware-agent/src/agent/cli.py`, `hardware-agent/src/agent/headless.py`, `hardware-agent/src/agent/daemon.py`, `hardware-agent/src/agent/tui/screens/scan_progress.py`, `hardware-agent/src/agent/scanner/workspace.py`, `hardware-agent/src/agent/transport/ingest.py`, `hardware-agent/src/agent/transport/signing.py`, `hardware-agent/src/agent/normalize/coverage.py`, `hardware-agent/tests/unit/test_scan_runner_partial.py`, `hardware-agent/tests/unit/test_headless.py`, `hardware-agent/tests/unit/test_cli_agent.py`, `hardware-agent/tests/unit/test_daemon.py`, `hardware-agent/tests/unit/test_ingest_client.py`
- **Tests**: `hardware-agent/tests/unit/test_scan_runner_partial.py`, `hardware-agent/tests/unit/test_headless.py`, `hardware-agent/tests/unit/test_cli_agent.py`, `hardware-agent/tests/unit/test_daemon.py`, `hardware-agent/tests/unit/test_ingest_client.py`; aceites A07,A10,A11,A12,A15.
- **Success Criteria**:
  - CLI/headless/daemon/TUI mesmos campos, partial/cancel persistem; audit constructors/calls; bytes completos assinados; upload falho conserva arquivo sem fallback422; coverage independente; exit0/10/20 e inválido2 mantidos.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 11: Apresentar TUI e avaliar corpus offline
- **Description**: Atualizar telas locais/legado e avaliar corpus desenvolvimento/evaluation versionado independente, baseline versus corrigido; fechar gate hardware-agent. Governada por ARCHITECTURE.md, INTEGRATION.md e DESIGN.md quando visual.
- **Dependencies**: Task 10
- **Target Files**: `hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/src/agent/tui/screens/device_detail.py`, `hardware-agent/tests/fixtures/finding_evidence_quality/development.json`, `hardware-agent/tests/fixtures/finding_evidence_quality/evaluation.json`, `hardware-agent/tests/unit/test_tui_scan_view.py`, `hardware-agent/tests/unit/test_tui_device_detail.py`, `hardware-agent/tests/test_finding_evidence_quality.py`
- **Tests**: `hardware-agent/tests/unit/test_tui_scan_view.py`, `hardware-agent/tests/unit/test_tui_device_detail.py`, `hardware-agent/tests/test_finding_evidence_quality.py`; aceites A01,A02,A03,A04,A05,A06,A07,A08,A09,A10,A11,A12,A13,A15,A16.
- **Success Criteria**:
  - TUI explicita local/método/limite e contagens registros; corpus origem/versão/condição/rótulo, positivos reais preservados; TP/FP/FN/precisão/cobertura denominadores e inconclusivos separados sem confiança percentual produto. Reviewer executa pytest completo hardware-agent e black/ruff escopados gates da camada.
  - Todos os critérios implementados e testes focais aprovados por reviewer independente; nenhuma alteração fora do escopo.
- **Status**: PENDING
- **Review Rejections**: 0

## Acceptance mapping

| Aceite | Tarefas |
|---|---|
| A01 | 1, 11 |
| A02 | 1, 11 |
| A03 | 1, 11 |
| A04 | 3, 9, 11 |
| A05 | 3, 8, 9, 11 |
| A06 | 3, 8, 9, 11 |
| A07 | 1, 3, 8, 9, 10, 11 |
| A08 | 3, 4, 9, 11 |
| A09 | 3, 4, 9, 11 |
| A10 | 2, 3, 4, 5, 6, 7, 8, 10, 11 |
| A11 | 4, 10, 11 |
| A12 | 5, 6, 7, 8, 10, 11 |
| A13 | 3, 5, 6, 8, 11 |
| A14 | 6, 7 |
| A15 | 2, 4, 7, 8, 10, 11 |
| A16 | 1, 9, 11 |

## Dependency graph

```text
#1 → #2 → #3 → #4 → #5 → #6 → #7 → #8 → #9 → #10 → #11 → docs-sync
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Corrigir interpretação NSE offline | COMPLETE |
| 2 | Publicar contrato aditivo estrito | COMPLETE |
| 3 | Implementar política e redução backend | COMPLETE |
| 4 | Persistir evidências e proteger reconciliação | COMPLETE |
| 5 | Expor leitura e totais por escopo | PENDING |
| 6 | Atualizar relatórios e verificar PDF | PENDING |
| 7 | Limitar explicação automatizada e fechar backend | PENDING |
| 8 | Apresentar método, limites e resumo web | PENDING |
| 9 | Anotar adaptadores e reduzir evidência local | PENDING |
| 10 | Integrar emissão e preservar todos caminhos | PENDING |
| 11 | Apresentar TUI e avaliar corpus offline | PENDING |
