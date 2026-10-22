# Tasks — OPC UA integrado ao NSPi (`053-nspi-opcua`)

11 sequential implementation units: original Tasks 1–9 plus migration M1/M2.
**Tasks 1–9, M1 and M2 are complete and reviewed.** Tasks 5–6 were committed and
synced as `fe182a0`. On 2026-10-22 the user authorized Tasks 7, 8 and 9 in sequence;
implementation must stop after Task 9. User authorized replacing the C#/.NET helper
entirely with Python. Specs originally approved 2026-10-20. Branch:
`feature/nspi-scan-opcua` / current base `fe182a0`.
Original completed entries and review history below remain unchanged. Their .NET
targets describe the old implementation; active migration targets supersede them.

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
- **Target Files**: `hardware-agent/src/agent/ot/opcua/mapper.py`, `hardware-agent/src/agent/ot/opcua/models.py`, `hardware-agent/src/agent/ot/opcua/client.py`, `hardware-agent/src/agent/ot/opcua/helper/Program.cs`, `hardware-agent/src/agent/normalize/contracts.py`, `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`
- **Tests**: `hardware-agent/tests/unit/test_opcua_mapper.py`, `hardware-agent/tests/unit/test_opcua_untrusted.py`, `hardware-agent/tests/unit/test_opcua_client.py`, `hardware-agent/tests/test_contract_models.py`, `hardware-agent/tests/fixtures/opcua_lab.py`, `hardware-agent/tests/dotnet/opcua-bridge.tests/Program.cs`.
- **Success Criteria**: nenhum downgrade/credencial; limites de profundidade, nós, referências, páginas e leituras são respeitados; referências externas e loops terminam deterministicamente; somente status/metadados permitidos saem; valor bruto e derivados não aparecem em JSON/logs/exceções; recusa/timeout não vira resultado negativo global.
- **Status**: COMPLETE (aprovada na quarta revisão)
- **Review Rejections**: 3

## Task 4: Integrar protocolos no estágio industrial e nos chamadores

- **User-added acceptance criterion**: identify the agent's own discovered host as `DMITRI` in scan output and reports that consume the host name. Determine self identity by matching the host IP to the agent's detected local scan IP; do not rename other hosts or change the `machine_type` taxonomy. Added at the user's request before implementation.
- **Description**: Integrar inventário e mapping UA ao estágio NSPi compartilhado, preservando Modbus, limites, progresso e cancelamento. Ajustar apenas compatibilidade mínima da TUI; o front continua interface principal. Governam A01, A10–A11, A15.
- **Dependencies**: Task 3
- **Target Files**: `hardware-agent/src/agent/ot/policy.py`, `hardware-agent/src/agent/ot/modbus/client.py`, `hardware-agent/src/agent/ot/modbus/inventory.py`, `hardware-agent/src/agent/ot/modbus/mapper.py`, `hardware-agent/src/agent/ot/opcua/client.py`, `hardware-agent/src/agent/ot/opcua/inventory.py`, `hardware-agent/src/agent/ot/opcua/mapper.py`, `hardware-agent/src/agent/ot/opcua/models.py`, `hardware-agent/src/agent/ot/opcua/helper/Program.cs`, `hardware-agent/src/agent/scanner/runner.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/models.py`, `hardware-agent/src/agent/scanner/progress.py`, `hardware-agent/src/agent/scanner/live_progress.py`, `hardware-agent/src/agent/daemon.py`, `hardware-agent/src/agent/normalize/contracts.py`, `hardware-agent/src/agent/normalize/coverage.py`, `hardware-agent/src/agent/tui/screens/device_detail.py`, `hardware-agent/src/agent/tui/screens/scan_progress.py`, `hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/src/agent/tui/screens/home.py`
- **Tests**: `hardware-agent/tests/unit/test_opcua_stage.py`, `test_modbus_stage.py`, `test_scan_runner_cancel.py`, `test_scan_runner_partial.py`, `test_scan_runner_timing.py`, `test_headless.py`, `test_daemon.py`, `test_scan_progress_screen.py`, `test_tui_device_detail.py`, `test_egress_only.py`.
- **Success Criteria**: inventory precedes mapping; OPC UA e Modbus compartilham relógio/orçamento sem sobrescrever resultados; falha isolada e `skipped` preservam cobertura; cancel funciona em CLI/headless/daemon/TUI; consumidor TUI não trata UA como Modbus nem quebra; novos contadores refletem envios reais.
- **Status**: COMPLETE
- **Review Rejections**: 1

## Task 5: Persistir observações UA e manter ingest/read compatíveis
- **Description**: Adicionar observação JSON tipada por serviço e atualização Alembic segura. Ingestão idempotente e leitura isolada por organização devem preservar scans antigos e resultados Modbus; governam A03, A11, A13–A14.
- **Dependencies**: Tasks 1, 4 and M2 (full Python migration reviewed)
- **Target Files**: `backend/src/api/models/persistence.py`, `backend/alembic/versions/20261020_44_opcua_observations.py`, `backend/src/api/schemas/industrial.py`, `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/read.py`, `backend/src/api/routers/scans.py`, `backend/src/api/services/persistence.py`, `backend/src/api/services/industrial.py`, `backend/src/api/services/read.py`, `backend/src/api/services/deletion.py`, `contracts/openapi/openapi.yaml`
- **Tests**: `backend/tests/test_opcua_observations_migration.py`, `test_industrial_persistence.py`, `test_industrial_observations_migration.py`, `test_ingest_scan.py`, `test_industrial_read_routes.py`, `test_contract_fidelity.py`.
- **Success Criteria**: upgrade/downgrade preserva dados; downgrade não apaga observações UA silenciosamente; upsert `(scan_host, protocol, port)` é idempotente; JSON corrompido degrada somente observação UA; isolamento org e membro Modbus não mudam.
- **Status**: COMPLETE (reviewer approved 2026-10-22; 1,802 full-suite passes plus the sole environment failure passed after installing the agent package; Ruff and diff check passed)
- **Review Rejections**: 2 (first: nullable mapping facts and legacy Modbus; second: read evidence-source length parity and stale migration-head tests; full Windows gate also lacks Linux release tools)

## Task 6: Exibir serviços OPC UA no front
- **Description**: Gerar tipos e fazer dispatch de protocolo nos detalhes de scan/equipamento e relatórios web, com estados anunciados separados de ações verificadas e cobertura limitada. Não criar UX de TUI detalhada; governam A03–A06, A09–A14.
- **Dependencies**: Task 5
- **Target Files**: `frontend/src/types/openapi.d.ts`, `frontend/src/api/scans.ts`, `frontend/src/api/hosts.ts`, `frontend/src/pages/hosts/IndustrialServices.tsx`, `frontend/src/pages/scans/ScanIndustrialServices.tsx`, `frontend/src/pages/HostDetail.tsx`, `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/scans/scanDetailView.ts`, `frontend/src/pages/scans/ScanReports.tsx`, `frontend/src/i18n/messages/en.ts`, `frontend/src/i18n/messages/pt-BR.ts`, `frontend/src/i18n/messages/ru.ts`
- **Tests**: `frontend/src/pages/hosts/IndustrialServices.test.tsx`, `pages/ScanDetail.test.tsx`, `pages/HostDetail.test.tsx`, `pages/scans/ScanReports.test.tsx`.
- **Success Criteria**: UA-only, dual, legado, partial/denied/corrupt são distinguíveis; strings não confiáveis são escapadas; labels existem nos três idiomas; download usa rotas atuais.
- **Status**: COMPLETE (reviewer approved; 97 final focused tests, prior full 789 tests/85 files, lint, format, typecheck, build, generated types and diff checks passed)
- **Review Rejections**: 2 (first: UTF-8, verified Value claim and inventory coverage; second: distinguish transport security from authentication and expose bounded endpoint security inventory)

## Task 7: Atualizar relatórios e contexto de IA
- **Description**: Acrescentar resumo industrial por protocolo nas exportações e informações agregadas no contexto de IA, sem NodeIds, URLs, valores de processo ou dados de certificado. Governam A11–A14.
- **Dependencies**: Task 6
- **Target Files**: `backend/src/api/schemas/reports.py`, `backend/src/api/services/reports.py`, `backend/src/api/services/report_education.py`, `backend/src/api/services/report_education_copy.py`, `backend/src/api/services/report_education_pdf.py`, `backend/src/api/services/report_pdf.py`, `backend/src/api/services/ai/context.py`, `backend/src/api/services/ai/analyzer.py`, `backend/src/api/services/ai/chat.py`, `backend/src/api/services/ai/groq.py`
- **Tests**: `backend/tests/test_reports.py`, `test_report_schema.py`, `test_report_education.py`, `test_ai_context.py`, `test_ai_analyzer.py`, `test_ai_chat.py`.
- **Success Criteria**: JSON/PDF distinguem protocolos e limitações; conteúdo de IA é agregado e livre de dado operacional sensível; findings Modbus/NSE continuam iguais; PDF renderizado é inspecionado.
- **Status**: COMPLETE (reviewer approved; 94 focused tests, Ruff and diff check passed; explained PDF rendered and visually inspected, with banner sentinel absent)
- **Review Rejections**: 2 (R1: PDF banner leak/A14 and Modbus discovery units counted as mapping/A11. R2: unbound/stale host address caused fallback crash and incomplete A14 redaction.)
- **Review decision after repeated A14 finding**: retained the approved contract and applied a host-scoped report-data boundary shared across explained output paths.

## Task 8: Validar matriz ponta a ponta e regressões
- **Description**: Completar testes integrados do laboratório, fronteira read-only, evidência, banco, front e regressão Modbus em conjunto. Governam A01–A16.
- **Dependencies**: Tasks 2–7
- **Target Files**: `hardware-agent/tests/fixtures/opcua_lab.py`, `hardware-agent/tests/integration/test_opcua_lab.py`, `hardware-agent/tests/unit/test_opcua_client.py`, `test_opcua_inventory.py`, `test_opcua_mapper.py`, `test_opcua_untrusted.py`, `backend/tests/test_scan_evidence.py`, `backend/tests/test_industrial_persistence.py`, `backend/tests/test_ingest_scan.py`, `frontend/src/pages/hosts/IndustrialServices.test.tsx`
- **Tests**: matriz de sucesso, recusa, serviço hostil, limite, cancelamento, dual protocol, tráfego efetivamente observado, evidência sem finding e regressões existentes.
- **Success Criteria**: nenhum serviço proibido chega ao peer; os contadores batem com o wire; entrada malformada/hostil não ultrapassa limites nem vaza; resultados Modbus e legado permanecem estáveis; ambiente de laboratório permanece isolado.
- **Status**: COMPLETE (reviewer approved; independent validation: 84 OPC UA unit tests, 20 UA/Modbus integration and stage tests, 90 backend tests on isolated `dmitri_test`, 13 frontend tests; focused Ruff and diff check passed)
- **Review Rejections**: 1 (blocking socketpair peer in two transport tests; fixed and independently revalidated)

## Task 9: Validar empacotamento ARM64 e preparar uso real
- **Description**: Executar gates finais por camada, conferir lock/wheelhouse para Linux ARM64 Python 3.12, imports, CLI e smoke OPC UA loopback; documentar limites da validação e checklist de ensaio real. Governam A13–A16.
- **Dependencies**: Task 8
- **Target Files**: `hardware-agent/pyproject.toml`, `hardware-agent/uv.lock`, `hardware-agent/packaging/build-deb.sh`, `.github/workflows/agent-release.yml`, documentação de deployment/validação identificada pelo code-map durante a tarefa.
- **Tests**: gates do hardware-agent; smoke offline ARM64 Python 3.12 (import asyncua/cryptography, health CLI, inventário/mapping loopback); testes Python 3.11; gates backend/frontend já definidos na integração.
- **Success Criteria**: wheelhouse lockado resolve sem rede no dispositivo alvo; pacote e CLI importam/funcionam; lab comprova comportamento sem ser apresentado como validação de PLC comercial; checklist de produção especifica o ensaio posterior com equipamento autorizado.
- **Status**: COMPLETE (final reviewer approved; native Raspberry Pi ARM64/Python 3.12 temporary offline venv passed imports, health CLI, and loopback inventory plus bounded mapping; Python 3.11 suite passed 1,698 tests with 27 skipped; independent final reviewer reran 17 release-workflow/client tests, Ruff and diff check passed)
- **Review Rejections**: 2 (R1: ARM64 package smoke and Python 3.11 evidence missing; R2: QEMU loopback inconclusive. Both findings addressed with native Pi validation and clarified documentation.)

---

## Task M1: Implement bounded Python worker inventory and stable protocol guards
- **Description**: Build the final decoder and socket transport primitives specified in `PYTHON_MIGRATION.md`, reuse pinned `asyncua==2.1.0`, and expose bounded GetEndpoints through the worker entry tested directly. Keep the existing facade until M2 completes mapping; no fake mapper or runtime fallback. Govern A02, A07–A10, A14, A16.
- **Absorbed**: Runtime dependency promotion, lock and license attribution are verified through the actual worker rather than separate config-only tasks.
- **Dependencies**: Task 4 (completed baseline)
- **Target Files**: `hardware-agent/src/agent/ot/opcua/worker.py`, `hardware-agent/src/agent/ot/opcua/bounded_decode.py`, `hardware-agent/src/agent/ot/opcua/guarded_transport.py`, `hardware-agent/src/agent/ot/opcua/THIRD_PARTY_NOTICES.txt`, `hardware-agent/pyproject.toml`, `hardware-agent/uv.lock`, `hardware-agent/tests/unit/test_opcua_decode.py`, `hardware-agent/tests/unit/test_opcua_transport.py`, `hardware-agent/tests/unit/test_opcua_worker.py`, `hardware-agent/tests/fixtures/opcua_lab.py`.
- **Tests**: Real pinned decoder generic/Variant arrays, byte/string/ExtensionObject lengths, recursive/cached factories and dimensions reject before allocation/element decode. Raw loopback peers prove exact HEL, ACK validation, header-only rejection, 16/17 chunks, byte totals and reset. Socket writer tests prove single admission/pacing, pre-send failure versus response timeout, partial-send unknown counts, independent one-shot cleanup reservations, direct forbidden request block, cancellation/abort and unchanged parent fixture decoder.
- **Success Criteria**: Worker inventory returns existing sanitized bounded IPC schema; <=32 budget and >=100 ms pacing include lifecycle; only allowed exact request classes/TypeIds receive one-use send permits; counts follow actual socket-send completion; malformed/oversized data cannot reach unbounded allocation; patches exist only in worker memory; runtime pin/lock and attribution present; focused pytest/Ruff and independent critical Python review pass. No .NET implementation changes in this unit.
- **Status**: COMPLETE
- **Review Rejections**: 2

## Task M2: Complete Python mapping, replace facade launch and remove .NET
- **Description**: Port completed C# mapping and review fixes into `worker_mapping.py`, preserve all Task 1–4 behavior, switch the facade to Python worker, and delete C# source/projects/harness and obsolete executable/build configuration. Govern A01–A16 and Task 4 DMITRI acceptance criterion; `PYTHON_MIGRATION.md` names seams/removal paths.
- **Dependencies**: M1
- **Target Files**: `hardware-agent/src/agent/ot/opcua/{worker.py,worker_mapping.py,guarded_transport.py,client.py,models.py,inventory.py,mapper.py}`; remove `hardware-agent/src/agent/ot/opcua/helper/{Program.cs,opcua-bridge.csproj,LICENSE.txt,.gitignore}` and `hardware-agent/tests/dotnet/opcua-bridge.tests/{Program.cs,opcua-bridge.tests.csproj}`; `hardware-agent/tests/unit/{test_opcua_client.py,test_opcua_mapper.py,test_opcua_inventory.py,test_opcua_untrusted.py,test_opcua_worker.py,test_opcua_transport.py,test_opcua_stage.py}`, `hardware-agent/tests/fixtures/opcua_lab.py`.
- **Tests**: Port .NET guard-harness assertions into Python; client/mapper fixtures launch Python without SDK builds/skips. Verify actual worker session/BFS/pagination/metadata/Value-status parity, cleanup cutoff/duplicates, no cleanup after cancel/deadline, secrets/process sentinels absent from output/logs/models, bounded parent stdout reads, actual peer counts/pacing and no forbidden requests. Repeat relevant stage/Modbus/runner/headless/daemon/TUI/egress/contract tests including DMITRI self-name.
- **Success Criteria**: Python performs inventory and anonymous mapping with unchanged external contract, 32/64 shared budgets and cancellation semantics. No C# source, .NET project/build/test requirement, `DMITRI_OPCUA_BRIDGE` or DOTNET launch path remains in active production/tests; historical specs retain audit references. Parent/fixture asyncua remain unpatched; no process values/derivatives cross IPC. Focused gates and independent critical Python review pass. Audit packaging scripts/CI for .NET requirements; ARM64 offline execution remains Task 9. Task 5 requires a new user command after M2 review.
- **Status**: COMPLETE
- **Review Rejections**: 2

## Dependency graph

```text
1 → 2 → 3 → 4 → M1 → M2 → 5 → 6 → 7 → 8 → 9
Task 5 also depends on the completed Task 1 and Task 4 contracts.
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Cliente limitado e laboratório local | COMPLETE |
| 2 | Inventário e contrato do agente | COMPLETE |
| 3 | Sessão anônima e mapeamento | COMPLETE |
| 4 | Integração do estágio e chamadores | COMPLETE |
| M1 | Python worker inventory, bounded decoder and transport | COMPLETE |
| M2 | Python mapping, facade switch and .NET removal | COMPLETE |
| 5 | Persistência, ingest e read | COMPLETE |
| 6 | Interface web | COMPLETE |
| 7 | Relatórios e IA | PENDING |
| 8 | Matriz integrada e regressões | PENDING |
| 9 | Pacote ARM64 e prontidão para validação real | PENDING |
