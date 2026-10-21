# Tasks — OPC UA integrado ao NSPi (`053-nspi-opcua`)

9 sequential tasks. **Task 1 is complete and reviewer-approved.** Specs approved 2026-10-20. Base: `feature/nspi-scan-opcua` / `971ba8d`.

Cada tarefa segue coder Luna medium → test engineer Luna medium → reviewer Sol 6.1; Task 1 requer reviewer Sol 6.1 high. Só o reviewer registra aprovação. Nenhum commit, push, PR, publicação ou deploy está incluído.

---

## Task 1: Implementar cliente OPC UA limitado e laboratório local
- **Description**: Helper first-party .NET 10 com OPC Foundation UA-.NETStandard 2.0.1, IPC JSON fechado, allowlist na fronteira `ITransportChannel`, limites HEL/ACK e frame/message 128 KiB / 64 KiB / 16 chunks. `EndpointConfiguration.Create()` configura lifetime positivo; o smoke loopback conclui GetEndpoints com status Good. Guardas acumulam bytes/chunks por mensagem antes de entregar ao decoder. Resposta oversized (>128 KiB realmente recebidos) falha com `message_size_limit`, sem auto-aumento. Instalação/runtime self-contained Linux ARM64 é da Task 9. Governam `TRUTH.md` A07, A09, A14, A16 e `ARCHITECTURE.md`.
- **Dependencies**: —
- **Target Files**: `hardware-agent/src/agent/ot/opcua/{__init__.py,models.py,client.py,helper/opcua-bridge.csproj,helper/Program.cs,helper/LICENSE.txt}`, `hardware-agent/src/agent/ot/opcua/helper/.gitignore`, `hardware-agent/tests/fixtures/opcua_lab.py`, `hardware-agent/tests/unit/test_opcua_client.py`, `hardware-agent/tests/dotnet/opcua-bridge.tests/`. `asyncua==2.1.0` permanece somente dependência de desenvolvimento do fixture; não é produção.
- **Tests**: `hardware-agent/tests/dotnet/opcua-bridge.tests` valida diretamente allowlist/contador de bloqueios, HEL exato, ACK inválido, 16/17 chunks, reset por mensagem, limite cumulativo de bytes, array pré-alocação, cleanup cancelado sem CLO e sanitizer/JSON snake_case com sentinel secreto. `test_opcua_client.py` exercita fixture loopback, serviço recebido, endpoint preenchido via snake_case, oversized GetEndpoints, timeout e cancelamento externo. Segunda passagem independente: build sem warnings/erros, harness, pytest 6/6, Ruff e `git diff --check` passaram; reviewer repetiu 21 testes Python e aprovou. Execução end-to-end usa apphost publicado em Temp por causa do bloqueio ambiental WDAC na pasta OneDrive; não desativar WDAC. Build/execução ARM64 e PLC real ficam para Task 9.
- **Success Criteria**:
  - A dependência OPC UA escolhida está fixada no projeto/lock e é importável nas versões Python suportadas; seus termos de licença são compatíveis com distribuição do Dmitri.
  - GetEndpoints, Browse/BrowseNext, Read e lifecycle estritamente necessário podem ser enviados; serviços de escrita, método, histórico, registro e subscription são barrados na fronteira de transporte mesmo se a API pública for contornada.
  - Limites de mensagens/chunks/bytes são efetivos antes de alocação ou decodificação; limites pós-decode não contam como proteção. Não registrar corpo binário ou valor de processo.
  - Orçamento/pacing contam tentativas reais de envio. Cancelamento durante conexão ou I/O termina task e fecha/aborta socket sem envio de cleanup posterior.
  - Fixture só aceita conexão loopback em porta efêmera e mede solicitações efetivamente recebidas; nenhum listener é adicionado ao runtime.
  - Checks focais de pytest e Ruff passam; reviewer fornece evidência explícita para decode pre-allocation e cancelamento real.
- **Status**: COMPLETE
- **Review Rejections**: 1 (corrigida e aprovada na segunda revisão)

## Task 2: Inventariar endpoints e definir contrato do agente
- **Description**: Descobrir OPC UA em candidatos existentes, validar respostas e sanitizar identidade/endpoints/políticas anunciadas. Acrescentar o payload interno estrito sem mudar o membro Modbus legado; governam A02–A03, A08, A13–A14.
- **Dependencies**: Task 1
- **Target Files**: `hardware-agent/src/agent/ot/opcua/inventory.py`, `hardware-agent/src/agent/ot/opcua/models.py`, `hardware-agent/src/agent/ot/opcua/client.py`, `hardware-agent/src/agent/ot/opcua/helper/Program.cs`, `hardware-agent/src/agent/normalize/contracts.py`, `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`
- **Tests**: `hardware-agent/tests/unit/test_opcua_inventory.py`, `hardware-agent/tests/test_contract_models.py`, `hardware-agent/tests/dotnet/opcua-bridge.tests/`; atualizar fixtures/contratos legados aplicáveis.
- **Success Criteria**: resposta OPC UA semanticamente válida é necessária para confirmar protocolo; URLs são limitadas ao IP/porta descobertos; identidade anunciada, tipos de autenticação e impressão digital SHA-256 do certificado ficam limitados/sanitizados; respostas truncadas são parciais; modelos UA têm enums fechados e campos de fase requeridos; payload antigo Modbus permanece aceito; anúncio não gera finding.
- **Status**: COMPLETE
- **Review Rejections**: 3

## Task 3: Implementar sessão anônima e mapeamento limitado
- **Description**: Sobre Task 2, abrir somente a sessão explicitamente permitida pela arquitetura e executar Browse/BrowseNext/Read limitados, com BFS, paginação, status e privacidade. Governam A04–A10 e A14.
- **Dependencies**: Task 2
- **Target Files**: `hardware-agent/src/agent/ot/opcua/mapper.py`, `hardware-agent/src/agent/ot/opcua/models.py`
- **Tests**: `hardware-agent/tests/unit/test_opcua_mapper.py`, `test_opcua_untrusted.py`, `test_opcua_client.py`.
- **Success Criteria**: nenhum downgrade/credencial; limites de profundidade, nós, referências, páginas e leituras são respeitados; referências externas e loops terminam deterministicamente; somente status/metadados permitidos saem; valor bruto e derivados não aparecem em JSON/logs/exceções; recusa/timeout não vira resultado negativo global.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 4: Integrar protocolos no estágio industrial e nos chamadores
- **Description**: Integrar inventário e mapping UA ao estágio NSPi compartilhado, preservando Modbus, limites, progresso e cancelamento. Ajustar apenas compatibilidade mínima da TUI; o front continua interface principal. Governam A01, A10–A11, A15.
- **Dependencies**: Task 3
- **Target Files**: `hardware-agent/src/agent/ot/policy.py`, `hardware-agent/src/agent/ot/modbus/client.py`, `hardware-agent/src/agent/ot/modbus/inventory.py`, `hardware-agent/src/agent/ot/modbus/mapper.py`, `hardware-agent/src/agent/scanner/runner.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/models.py`, `hardware-agent/src/agent/scanner/progress.py`, `hardware-agent/src/agent/scanner/live_progress.py`, `hardware-agent/src/agent/daemon.py`, `hardware-agent/src/agent/normalize/coverage.py`, `hardware-agent/src/agent/tui/screens/device_detail.py`, `hardware-agent/src/agent/tui/screens/scan_progress.py`, `hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/src/agent/tui/screens/home.py`
- **Tests**: `hardware-agent/tests/unit/test_opcua_stage.py`, `test_modbus_stage.py`, `test_scan_runner_cancel.py`, `test_scan_runner_partial.py`, `test_scan_runner_timing.py`, `test_headless.py`, `test_daemon.py`, `test_scan_progress_screen.py`, `test_tui_device_detail.py`, `test_egress_only.py`.
- **Success Criteria**: inventory precedes mapping; OPC UA e Modbus compartilham relógio/orçamento sem sobrescrever resultados; falha isolada e `skipped` preservam cobertura; cancel funciona em CLI/headless/daemon/TUI; consumidor TUI não trata UA como Modbus nem quebra; novos contadores refletem envios reais.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 5: Persistir observações UA e manter ingest/read compatíveis
- **Description**: Adicionar observação JSON tipada por serviço e atualização Alembic segura. Ingestão idempotente e leitura isolada por organização devem preservar scans antigos e resultados Modbus; governam A03, A11, A13–A14.
- **Dependencies**: Tasks 1, 4
- **Target Files**: `backend/src/api/models/persistence.py`, `backend/alembic/versions/20261020_44_opcua_observations.py`, `backend/src/api/schemas/industrial.py`, `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/read.py`, `backend/src/api/routers/scans.py`, `backend/src/api/services/persistence.py`, `backend/src/api/services/industrial.py`, `backend/src/api/services/read.py`, `backend/src/api/services/deletion.py`, `contracts/openapi/openapi.yaml`
- **Tests**: `backend/tests/test_opcua_observations_migration.py`, `test_industrial_persistence.py`, `test_industrial_observations_migration.py`, `test_ingest_scan.py`, `test_industrial_read_routes.py`, `test_contract_fidelity.py`.
- **Success Criteria**: upgrade/downgrade preserva dados; downgrade não apaga observações UA silenciosamente; upsert `(scan_host, protocol, port)` é idempotente; JSON corrompido degrada somente observação UA; isolamento org e membro Modbus não mudam.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 6: Exibir serviços OPC UA no front
- **Description**: Gerar tipos e fazer dispatch de protocolo nos detalhes de scan/equipamento e relatórios web, com estados anunciados separados de ações verificadas e cobertura limitada. Não criar UX de TUI detalhada; governam A03–A06, A09–A14.
- **Dependencies**: Task 5
- **Target Files**: `frontend/src/types/openapi.d.ts`, `frontend/src/api/scans.ts`, `frontend/src/api/hosts.ts`, `frontend/src/pages/hosts/IndustrialServices.tsx`, `frontend/src/pages/scans/ScanIndustrialServices.tsx`, `frontend/src/pages/HostDetail.tsx`, `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/scans/scanDetailView.ts`, `frontend/src/pages/scans/ScanReports.tsx`, `frontend/src/i18n/messages/en.ts`, `frontend/src/i18n/messages/pt-BR.ts`, `frontend/src/i18n/messages/ru.ts`
- **Tests**: `frontend/src/pages/hosts/IndustrialServices.test.tsx`, `pages/ScanDetail.test.tsx`, `pages/HostDetail.test.tsx`, `pages/scans/ScanReports.test.tsx`.
- **Success Criteria**: UA-only, dual, legado, partial/denied/corrupt são distinguíveis; strings não confiáveis são escapadas; labels existem nos três idiomas; download usa rotas atuais.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 7: Atualizar relatórios e contexto de IA
- **Description**: Acrescentar resumo industrial por protocolo nas exportações e informações agregadas no contexto de IA, sem NodeIds, URLs, valores de processo ou dados de certificado. Governam A11–A14.
- **Dependencies**: Task 6
- **Target Files**: `backend/src/api/schemas/reports.py`, `backend/src/api/services/reports.py`, `backend/src/api/services/report_education.py`, `backend/src/api/services/report_education_copy.py`, `backend/src/api/services/report_education_pdf.py`, `backend/src/api/services/report_pdf.py`, `backend/src/api/services/ai/context.py`, `backend/src/api/services/ai/chat.py`, `backend/src/api/services/ai/groq.py`
- **Tests**: `backend/tests/test_reports.py`, `test_report_schema.py`, `test_report_education.py`, `test_ai_context.py`, `test_ai_chat.py`.
- **Success Criteria**: JSON/PDF distinguem protocolos e limitações; conteúdo de IA é agregado e livre de dado operacional sensível; findings Modbus/NSE continuam iguais; PDF renderizado é inspecionado.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 8: Validar matriz ponta a ponta e regressões
- **Description**: Completar testes integrados do laboratório, fronteira read-only, evidência, banco, front e regressão Modbus em conjunto. Governam A01–A16.
- **Dependencies**: Tasks 2–7
- **Target Files**: `hardware-agent/tests/fixtures/opcua_lab.py`, `hardware-agent/tests/integration/test_opcua_lab.py`, `hardware-agent/tests/unit/test_opcua_client.py`, `test_opcua_inventory.py`, `test_opcua_mapper.py`, `test_opcua_untrusted.py`, `backend/tests/test_scan_evidence.py`, `backend/tests/test_industrial_persistence.py`, `backend/tests/test_ingest_scan.py`, `frontend/src/pages/hosts/IndustrialServices.test.tsx`
- **Tests**: matriz de sucesso, recusa, serviço hostil, limite, cancelamento, dual protocol, tráfego efetivamente observado, evidência sem finding e regressões existentes.
- **Success Criteria**: nenhum serviço proibido chega ao peer; os contadores batem com o wire; entrada malformada/hostil não ultrapassa limites nem vaza; resultados Modbus e legado permanecem estáveis; ambiente de laboratório permanece isolado.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 9: Validar empacotamento ARM64 e preparar uso real
- **Description**: Executar gates finais por camada, conferir lock/wheelhouse para Linux ARM64 Python 3.12, imports, CLI e smoke OPC UA loopback; documentar limites da validação e checklist de ensaio real. Governam A13–A16.
- **Dependencies**: Task 8
- **Target Files**: `hardware-agent/pyproject.toml`, `hardware-agent/uv.lock`, `hardware-agent/packaging/build-deb.sh`, `.github/workflows/agent-release.yml`, documentação de deployment/validação identificada pelo code-map durante a tarefa.
- **Tests**: gates do hardware-agent; smoke offline ARM64 Python 3.12 (import asyncua/cryptography, health CLI, inventário/mapping loopback); testes Python 3.11; gates backend/frontend já definidos na integração.
- **Success Criteria**: wheelhouse lockado resolve sem rede no dispositivo alvo; pacote e CLI importam/funcionam; lab comprova comportamento sem ser apresentado como validação de PLC comercial; checklist de produção especifica o ensaio posterior com equipamento autorizado.
- **Status**: PENDING
- **Review Rejections**: 0

---

## Dependency graph

```text
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
                  └─────────┘
5 também depende de 1 e 4
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Cliente limitado e laboratório local | COMPLETE |
| 2 | Inventário e contrato do agente | COMPLETE |
| 3 | Sessão anônima e mapeamento | PENDING |
| 4 | Integração do estágio e chamadores | PENDING |
| 5 | Persistência, ingest e read | PENDING |
| 6 | Interface web | PENDING |
| 7 | Relatórios e IA | PENDING |
| 8 | Matriz integrada e regressões | PENDING |
| 9 | Pacote ARM64 e prontidão para validação real | PENDING |
