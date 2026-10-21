# Integração — OPC UA no NSPi

Integration spec approved 2026-10-20, base `971ba8d`. Task 1 is complete and reviewer-approved; ARM64/real-device validation is assigned to Task 9.
Decisões e limites: [ARCHITECTURE.md](ARCHITECTURE.md). `N` marca arquivo proposto;
os demais caminhos foram localizados no source. Paths abaixo são relativos à raiz.

## Fluxos de entrada verificados

| Origem | Caminho real até o coletor |
|---|---|
| CLI | `hardware-agent/src/agent/cli.py` `_run_agent` → `headless.py` `run_headless_scan` → `scanner/runner.py` `ScanRunner.run_blocking` → `_run` → `stages.run_ot_inspection_stage` |
| API Python headless | `hardware-agent/src/agent/headless.py` valida modo/submodo e cria ScanRunner diretamente |
| Daemon remoto | `hardware-agent/src/agent/daemon.py` `_run_command` → callback `run_scan` (default run_headless_scan), passando `command.nspi_options.submode`; `_ScanStop` vincula cancelamento |
| TUI | `hardware-agent/src/agent/tui/screens/home.py` resultado de seleção → `ScanProgressScreen` em `tui/screens/scan_progress.py` → `ScanRunner.start` → worker `_run_locked` → `_run` |
| Contrato remoto | `backend/src/api/schemas/commands.py`, `backend/src/api/services/commands.py`, `hardware-agent/src/agent/transport/command_channel.py` conservam nspi_options/submode; seleção web existente em `frontend/src/pages/DeviceDetail.tsx` |

Só há dois construtores runtime de ScanRunner: headless e ScanProgressScreen.
Não há `ScanOrchestrator` no código atual; a referência em AGENTS/code-map é histórica.
Não introduzir outro pipeline. Controlador UA pertence a ScanRunner como controlador
Modbus; parâmetro de teste novo, se necessário, deve chegar por ambos construtores.
Submodo e defaults já percorrem todos os fluxos; testes comprovam que permanecem iguais.

## Arquivos e costuras obrigatórias

| Área | Caminhos verificados ou novos | Alteração necessária |
|---|---|---|
| Dependência/pacote | `hardware-agent/pyproject.toml`, `hardware-agent/uv.lock`, `hardware-agent/packaging/build-deb.sh`, `.github/workflows/agent-release.yml` | Pin UA, lock, licença e smoke wheelhouse arm64; runtime não contém servidores de teste |
| Coletor UA | N `hardware-agent/src/agent/ot/opcua/__init__.py`, `models.py`, `client.py`, `inventory.py`, `mapper.py` no mesmo diretório | Modelos só de metadados, adaptador limitado, inventário e BFS/read; sem engine genérico |
| Limites comuns | `hardware-agent/src/agent/ot/policy.py`, `ot/untrusted.py`, `ot/modbus/client.py`, `ot/modbus/inventory.py`, `ot/modbus/mapper.py` | Budget comum no envio, pacing, preservação dos limites Modbus; sanitização UA específica no cliente |
| Execução | `hardware-agent/src/agent/scanner/runner.py`, `stages.py`, `models.py` | União de serviços; controlador/cancel; candidatos ambos; append/merge por protocolo em vez de sobrescrever lista; inventários antes de mapping; cobertura por serviço |
| Eventos/progresso | `hardware-agent/src/agent/scanner/progress.py`, `live_progress.py`, `hardware-agent/src/agent/daemon.py` | Eventos industriais genéricos e labels de protocolo; contagem industrial soma ambos; manter evento legado se consumidor ainda depende |
| Normalização | `hardware-agent/src/agent/normalize/contracts.py`, `coverage.py`, `findings.py` | União tipada, fonte opcua_inspection, cobertura endpoint/tool; nenhum finding UA em v1; dispatch Modbus antes de .units |
| Modbus existente | `hardware-agent/src/agent/ot/modbus/fingerprints.py`, `models.py` | Guardas de tipo/protocolo; nenhum resultado UA passado ao correlator FC43 |
| Assessment | `hardware-agent/src/agent/assessment/profile.py`, `exposure.py` | Guardar loops .units; identidade anunciada; texto/role industrial reconhece UA sem chamar tudo de Modbus |
| Workspace/transporte | `hardware-agent/src/agent/scanner/workspace.py`, `hardware-agent/src/agent/transport/ingest.py` | Serialização e assinatura existentes; verificar ausência de valores e logs UA brutos em success/error/cancel |
| TUI — compatibilidade mínima | `hardware-agent/src/agent/tui/screens/device_detail.py`, `scan_progress.py`, `scan_view.py`, `hardware-agent/src/agent/tui/screens/home.py` | Ajustar somente consumidores/callers afetados: evitar acesso Modbus em UA, preservar scan/cancel e texto correto; header não atribui todo limite ao Modbus. Detalhes, tabelas e novos resumos ficam adiados |
| Contrato público | `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json` | Novos componentes/uniões/enums; exemplo dual limitado sem Value; manter exemplos legados em testes |
| Schemas backend | `backend/src/api/schemas/industrial.py`, `scan.py`, `read.py` | Ingest UA fechado; preservar componente read Modbus; union array; JSON corrompido com observation null/unreadable_fields |
| Banco | `backend/src/api/models/persistence.py`; N `backend/alembic/versions/20261020_44_opcua_observations.py` | JSON tipado UA nullable + protocol check; parent real 20261019_43, verificar novamente antes de codar |
| Ingest persistência | `backend/src/api/routers/scans.py`, `services/persistence.py`, `services/industrial.py` | `persist_scan`/persist_industrial_services faz dispatch, upsert idempotente por protocolo; mapa `(port,unit_id)` retorna apenas Modbus |
| Qualidade de evidência | `backend/src/api/services/scan_evidence.py` | Verificar que observações UA não viram finding, CVE ou auth bypass; preservar gates Modbus/NSE existentes |
| Leitura | `backend/src/api/services/read.py`, `services/industrial.py`, `routers/scans.py` | `_industrial_service_views` dispatch, valida JSON UA, preserva isolamento da organização e seleção de observação do host atual |
| Exclusão | `backend/src/api/services/deletion.py` | Conferir remoção industrial existente leva JSON UA; nenhum filho novo ou orphan |
| Relatórios/export | `backend/src/api/schemas/reports.py`, `services/reports.py`, `report_education.py`, `report_education_copy.py`, `report_education_pdf.py`, `report_pdf.py` | JSON técnico já usa ScanDetailResponse; PDF explicado precisa resumo UA explícito e limites; classificar opcua em family industrial |
| AI | `backend/src/api/services/ai/context.py`, `chat.py`, `groq.py` | `build_scan_ai_context`, `build_scan_chat_bundle`, `build_host_chat_bundle`: agregado por protocolo de serviços/cobertura/capacidade anônima; incrementar context version e instruções de evidência no prompt existente |
| Web tipo/API | `frontend/src/types/openapi.d.ts`, `frontend/src/api/scans.ts`, `frontend/src/api/hosts.ts` | `npm run gen:types`; arrays passam union sem casts Modbus; requests mantêm as mesmas rotas |
| Web resultados | `frontend/src/pages/hosts/IndustrialServices.tsx`, `pages/scans/ScanIndustrialServices.tsx`, `pages/HostDetail.tsx`, `pages/ScanDetail.tsx`, `pages/scans/scanDetailView.ts`, `pages/scans/ScanReports.tsx` | Dispatch protocol antes de units, títulos corretos, anúncio separado de operação verificada, limitações; download segue endpoints atuais |
| Web mensagens | `frontend/src/i18n/messages/en.ts`, `pt-BR.ts`, `ru.ts` | Labels industrial/UA e razões em todos idiomas existentes; erros via toast existente |

Paths agrupados na mesma célula usam o prefixo completo da primeira entrada.
Antes de implementar, confirmar símbolos locais com rg: nomes de serviços/routers
não devem ser deduzidos do code-map. Não é necessário alterar autenticação, endpoints
de comando ou gestão de credenciais para adicionar o coletor.

## Preservação de contrato

Backend novo deve aceitar scan antigo vazio, Modbus com/sem protocol legado e dados
Modbus anteriores que já toleram extras em units/ranges. Não endurecer esses campos
ao adicionar UA. UA usa extra=forbid e rejeita qualquer campo Value/process_data.
Não colocar `.units=[]` fictício em UA para fazer consumidores antigos passarem.
Atualizar cada consumidor listado com dispatch explícito; Modbus read view permanece
com o mesmo nome e campos, novo array referencia IndustrialServiceRead oneOf.

Metadata `modbus_*` conta somente Modbus. Acrescentar `opcua_candidates`,
`opcua_confirmed`, `opcua_requests_sent`, `opcua_anonymous_value_reads`,
`opcua_limited_services`, `industrial_requests_sent`; `nspi_policy_version`
passa para 2, sem mudar nspi_submode. Totais industriais de live progress somam
ambos; não somar número de nodes a número de Modbus units. Cobertura mantém protocolo
de transporte `tcp`; identificação UA fica em tool/evidence_source/industrial.protocol.

Acrescentar `industrial_stage_deadline_reached` e `industrial_stage_deadline_seconds`
para o teto compartilhado. Preservar leitura dos campos legados `modbus_stage_deadline_*`
em scans antigos; não emitir diagnóstico exclusivamente Modbus para um limite que
também afetou OPC UA. As novas observações informam o alcance por serviço.

## Matriz de verificação durante implementação

| Costura | Testes existentes e novos necessários |
|---|---|
| Client + parser | N `hardware-agent/tests/unit/test_opcua_client.py`, `test_opcua_inventory.py`, `test_opcua_mapper.py`, `test_opcua_untrusted.py`: requests realmente transmitidos, timeout/cancel durante cada await, decoder lengths/depth/chunks, bytes, URL mismatch, segredo, escape, páginas repetidas, grafo cíclico, denied vs advertised |
| Limite read-only real | N `hardware-agent/tests/integration/test_opcua_lab.py` e `hardware-agent/tests/fixtures/opcua_lab.py`: servidor loopback instrumentado registra service type IDs de **todo** o fluxo; testes falham se Write/Call/subscription/History/alteração de grafo alcançar wire, mesmo com API do cliente adulterada; operação proibida não é respondida como read |
| Pacing/contadores | Fixture mede ordem e timestamps de envios, incluindo lifecycle; contadores comparados ao tráfego observado; timeout e bytes malformados ainda contam honestamente; PCAP sem valores de processo não é artefato de produção |
| Stage dual | `hardware-agent/tests/unit/test_modbus_stage.py`, N `test_opcua_stage.py`: host só UA, dual, dois serviços, ordem inventário/map, orçamento/time compartilhado, falha independente, skipped correto, partial sem overwrite |
| Runner/callers | `hardware-agent/tests/unit/test_scan_runner_cancel.py`, `test_scan_runner_partial.py`, `test_scan_runner_timing.py`, `test_headless.py`, `test_daemon.py`, `test_scan_progress_screen.py`: mesmo coletor/submodo/limites em CLI/headless/remote/TUI; cancel fecha UA antes de finalizar |
| Payload/evidence/assessment | `hardware-agent/tests/test_contract_models.py`, `hardware-agent/tests/unit/test_assessment_analyzer.py`, `test_modbus_fingerprints.py`, `test_ot_untrusted.py`: união dual, guardas .units, profile/exposure correto; raw Value sentinel ausente de payload, workspace, logs, exceções e digest |
| Runtime egress | `hardware-agent/tests/unit/test_egress_only.py`: coletor UA runtime não faz bind/listen; fixtures loopback ficam só no pacote de testes |
| Banco/ingest | `backend/tests/test_industrial_persistence.py`, `test_industrial_observations_migration.py`, N `test_opcua_observations_migration.py`, `backend/tests/test_ingest_scan.py`: upgrade com dados legados, upsert dual, protocolo constraint, replay, downgrade seguro, exclusão scan/host |
| Read/contrato | `backend/tests/test_industrial_read_routes.py`, `test_contract_fidelity.py`: scan e host dual, isolamento org, JSON corrompido só degrada UA, omissão legado, oneOf correto e componentes refletidos em generated types |
| Evidência | `backend/tests/test_scan_evidence.py`: anúncio, metadata Read, application Value, denied e timeout não geram finding/CVE/auth bypass; fatos de capacidade seguem tentativas reais, com null para não testado; regressão Modbus/NSE |
| Export/AI | `backend/tests/test_reports.py`, `test_report_schema.py`, `test_report_education.py`, `test_ai_context.py`, `test_ai_chat.py`: JSON/PDF mantém protocolos e cobertura; render PDF verificado; AI aggregate contém UA sem strings/NodeIds/URL/certificados/valores e não chama anúncio de acesso |
| Web | `frontend/src/pages/hosts/IndustrialServices.test.tsx`, `pages/ScanDetail.test.tsx`, `pages/HostDetail.test.tsx`, `pages/scans/ScanReports.test.tsx`: legado Modbus, UA-only, dual, denied/partial/corrupt, markup e rótulos |
| TUI — regressão mínima | `hardware-agent/tests/unit/test_tui_device_detail.py` e testes de callers acima: payload UA/dual não causa exceção, não é tratado como Modbus e não expõe dados; preservar resultados Modbus. Apresentação detalhada UA não é gate |
| Packaging | Smoke Linux arm64 Python3.12: locked offline wheelhouse install, import asyncua+cryptography, health CLI, loopback inventory/mapping; Python3.11 unit compatibility. Cross-download wheels sozinho não demonstra execução arm64 |

Servidor local novo deve ter cenários determinísticos: None anônimo permitido,
Anonymous anunciado/ActivateSession negado, Browse permitido/Value negado,
somente Username, somente SignAndEncrypt, endpoints externos, mensagens grandes,
paginação infinita, ciclo, socket lento e serviço não UA. Cenário dual usa também
`hardware-agent/tests/fixtures/modbus_lab.py` / `tests/integration/test_modbus_lab.py`.
Métodos e variáveis writable no servidor de teste provam que o scanner não os usa.
Bind apenas loopback; porta efêmera. Harness Compose isolado, se necessário, é novo;
`compose.nspi.yaml` existente aponta a backend já implantado e não atende isolamento.
Não enviar resultados de laboratório ao backend de produção. Evidência de lab deve
separar teste automatizado, smoke arm64 e ensaio posterior em equipamento real.

Gates na implementação: agente `uv run pytest` e lint scoped; backend iniciar
`./database.sh --test` e usar `dmitri_test` vivo, `uv run ruff check src tests` e
`uv run pytest`; frontend gen:types, lint, typecheck, test, build. Não rodar formatter
repo-wide. Planejamento atual valida referências e coerência; nenhum teste runtime
é declarado executado ou aprovado por estes documentos.
