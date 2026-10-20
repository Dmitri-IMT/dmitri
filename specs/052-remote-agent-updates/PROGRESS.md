# Progresso — atualização remota do agente

## Preparação para uso real — 2026-10-20

- As Tasks 1–14 abaixo estão concluídas no código. A ativação operacional está em andamento
  e tem critérios próprios em [ROLLOUT.md](ROLLOUT.md); ainda não foi concluída em produção.
- O1: concluída e aprovada por revisão independente. O pacote ARM64 atual executou o `postinst`
  real sem rede, com uv 0.11.20/Python 3.12.15; instalação offline e smoke test passaram e os
  dados/lock do Raspberry permaneceram intactos. Os serviços da VM foram restaurados.
- O2: reparos de CI e fluxo protegido de release concluídos e aprovados por revisão independente.
- O usuário informou não ter acesso à Railway. Configuração, migrações e deploy de produção
  dependem de um responsável autorizado. Nenhum runtime de produção ou pacote do Raspberry
  foi alterado nesta preparação.

## Estado das tarefas de desenvolvimento

- Estado atual: Tasks 1–14 concluídas após revisão independente do produto e da documentação.
- Autorizações registradas: Tasks 8 e 9 concluídas nesta sequência, conforme comando explícito do usuário em 2026-10-19.
- Bypass autorizado pelo usuário para concluir os gates: usar PostgreSQL isolado em Docker,
  com banco `dmitri_test`, porta em loopback e armazenamento tmpfs, como exceção ao bootstrap
  Supabase. Não reparar nem reutilizar o banco local com schema divergente; não apagar volumes.
- Base do planejamento original: branch `feature/scan-adjusts-improve`, HEAD `b207a83`.
- Base conferida na decomposição e implementação: branch `feature/remote-agent-updates`, HEAD `a178aa6`.
- Fluxo: `feature-planning` e `consult-docs`; arquitetura Sol high, design/escrita Luna medium; execução sequencial coder → tester → reviewer.
- `TASKS.md` criado por autorização explícita de decomposição; isso não inicia implementação.

## Evidência inicial

- ADR-021 já define pacote Debian, repositório confiável, atualização externa ao processo e exclusão mútua com scans.
- Fonte atual contém `packaging/build-deb.sh`, `apt-upgrade-agent` e timer diário; estes não comprovam que existe repositório de releases assinado operacional.
- O `hello` contém versão em memória no registro de conexões; persistência e apresentação da versão precisam ser rastreadas na fonte.
- A unidade do agente já roda como root; o desenho deve reutilizar permissões e isolamento existentes sem criar um mecanismo de shell remoto genérico.
- O timer atual executa instalação automática quando houver atualização disponível no APT. A arquitetura deve resolver essa diferença com o requisito de instalação manual por padrão.
- O pipeline histórico em `.claude/docs/pipeline.md` ainda descreve camada única; as skills e perfis Codex atuais governam o fluxo entre múltiplas camadas.

## Próximo passo

Aguardar comando do usuário para a próxima tarefa; a ordem sugerida continua na Task 2
(catálogo verificado). Task 1 aprovada pelo reviewer após suíte completa verde. O banco
local original com schema divergente foi preservado; a validação usou outro container,
porta 55432 e banco chamado `dmitri_test`, com armazenamento temporário em memória.

## Decomposição autorizada — 2026-10-17

- Usadas `create-tasks` e `consult-docs` dos arquivos existentes em `.claude/skills/`;
  os espelhos `.agents/skills/` e `.codex/agents/` não têm os arquivos esperados nesta base.
- 14 tarefas com dependências, testes, critérios U01–U16, modelos e contador de rejeições.
  Sem dependência de código agora: #1, #3, #4, #6; execução sugerida começa em #1.
- Coder/tester Luna medium; revisão crítica Sol 6.1 high, UI/docs Sol 6.1 medium;
  orquestração futura Sol 6.1 medium. São seleções futuras, não mudança de modelo desta sessão.
- H1–H6 isolam hosting, assinatura, plataforma, bootstrap, canário e integração humana de CI.
  Publicador/pacotes têm validação local descartável; isso não comprova distribuição operacional.
- Head de migrações visível nesta base: `20260928_38`; parent da revisão proposta deve ser
  conferido ao implementar. Histórico de investigação abaixo continua referido a `b207a83`.
- Apenas documentação alterada nesta etapa; sem código, testes de produto, SSH, deploy,
  varredura, commit/push ou provisionamento.
- Verificação documental: 14 blocos no formato canônico, todos PENDING/0; grafo sem ciclos,
  raízes #1/#3/#4/#6, caminhos declarados nas specs, testes por tarefa, cobertura U01–U16 e
  ausência de espaços ao fim de linha. Essa verificação não é revisão independente nem gate de produto.
- Início autorizado pelo usuário em 2026-10-17: Task 1, ciclo coder → tester → reviewer.
- Coder inicial concluiu o escopo. Tester obteve 8 testes aprovados e 1 erro de teardown ao
  executar o downgrade até base: uma FK de `deleted_scans` impede a remoção de `orgs` em uma
  migração existente. A conexão posterior confirmou o schema no head41 antes do teste; o estado
  final do banco após o teardown é incerto. Não executar mais comandos de banco até planejar a
  recuperação da fixture `dmitri_test`.
- Review round 1: `[REJECT]`; Ruff passou. Rejeição 1: grants/RLS para `dmitri_runtime` e
  revogação de roles, UUID do release fora do trigger imutável, cobertura insuficiente de
  invariantes/dados no upgrade-downgrade e INTEGER/BIGINT divergente no metadata.
- Novo coder iniciado para corrigir esses pontos sem acessar Postgres. Após handoff, rerodar
  somente verificações sem banco e pedir revisão independente. Gate de banco ainda não aprovado.
- Review round 2: `[REJECT]`; Ruff oficial passou. Rejeição 2: schemas AgentSummary/AgentDetail
  publicam versão antes da Task 7 e divergem do OpenAPI; testes não isolam singleton_id CHECK,
  domínio de error_code/FK e trigger de ID imutável. Novo coder iniciado sem acesso a banco.
  Reviewer confirmou as correções da rodada anterior por leitura. Gate de banco e fidelity tests pendentes.
- Review round 3: `[APPROVE]` restrito à revisão estática; `uv run ruff check src tests` passou.
  O teste focado de fidelidade OpenAPI para AgentSummary, AgentDetail e AgentListResponse passou
  (3 testes) usando URL local inalcançável com nome `dmitri_test`, sem conexão ao Postgres.
  Gates de persistência/migração e permissões no banco continuam pendentes; Task 1 permanece aberta.
- Após bypass: tester preparou PostgreSQL 17 isolado em tmpfs, sem mounts persistentes,
  em `127.0.0.1:55432/dmitri_test`. A rodada inicial de foco/migrações/contrato teve
  148 aprovados e uma falha de ordenação da fixture; novo coder passou a gravar Org antes
  dos dependentes. Retry dos dois arquivos Task 1: 13 aprovados.
- Primeira suíte completa isolada: 1511 aprovados, 3 falhas e 8 erros. Identificados head
  Alembic e colunas Agent desatualizados em testes, leitura cp1252 no Windows e fixtures
  SQLite incompatíveis com constraints PostgreSQL. Novo coder atualizou esses testes e
  migrou as fixtures de rotas afetadas para o PostgreSQL compartilhado, sem enfraquecer
  constraints. Ruff e diff-check passaram; tester e reviewer validam a nova rodada.
- Retry integrado dos sete arquivos afetados: 71 aprovados em 25,72 s. Reviewer confirmou
  preservação dos cenários/asserções e a cobertura das novas tabelas por RLS/grants nos
  testes de migração baseados no metadata. Suíte completa final em execução.
- Fechamento Task 1: tester independente confirmou `uv run pytest -q` com **1522 aprovados,
  520 warnings, sem falhas/erros (515,80 s)**, incluindo teardown. Foco final: 71 aprovados
  (25,72 s). Ruff `src tests` e diff-check aprovados. Reviewer Sol 6.1 high emitiu
  **[APPROVE] final**, sem achados nem gates pendentes. Task 1 marcada COMPLETED;
  duas rejeições históricas preservadas no ledger. Correções e testes por coders/tester
  Luna medium. Sem início da Task 2, commit/push, deploy, SSH ou scan.
- Ambiente de teste temporário encerrado: container `dmitri-task1-postgres-20261017`
  parado e removido sem remover volumes. Tester confirmou Supabase original saudável,
  com mesmo container, porta e volume; nenhum dado persistente original foi alterado
  nesta rodada isolada de validação.

## Handoff de arquitetura

- Escritos `ARCHITECTURE.md` e `INTEGRATION.md`, ambos propostas sem aprovação humana.
- Decisões: releases imutáveis e APT com metadados assinados; pacote companheiro permanente para o atualizador; padrão manual/check-only no timer; estado durável; recuperação offline do pacote e virtualenv; versão persistida; protocolo condicionado a capacidade e sessão.
- Hospedagem, autoridade de assinatura, compatibilidade da appliance e bootstrap assistido permanecem `HUMAN_INFRA_REQUIRED`.
- Sessão encerrada com documentos e evento `turn.completed`. CLI retornou código 1 e avisou falha do hook local `legacy_notify` por caminho inexistente; o handoff e as métricas foram produzidos. Não se repetiu a arquitetura por causa desse hook.
- Nenhum código, `TASKS.md`, teste ou operação no dispositivo foi executado nesta fase.

## Fechamento do planejamento

- Design concluído por GPT-6 Luna medium em sessão nova; `DESIGN.md` cobre página do dispositivo, estados, confirmação, versões, recuperação, teclado/mobile e textos nos três idiomas existentes.
- Revisão independente GPT-6.1 Sol medium: `[APPROVE]` em `REVIEW.md`, exclusivamente aprovação técnica de proposta. Não substitui aprovação humana para implementar.
- `PLAN.md` registra seis entregas futuras e distribuição de modelos; `PROMPTS.md` prepara retomada, criação de tarefas, coder/tester/reviewer e docs-sync sem repetir a conversa inteira.
- `USAGE.md` registra os contadores reportados das sessões uma vez por papel; cache não é somado novamente e uso não é convertido em porcentagem do plano Codex.
- Somente esta pasta de specs foi criada no repositório. Sem desenvolvimento de produto, testes, publicação, commit/sync, SSH ou mudança de serviço.

## Implementação de produto

- Task 7 concluída após autorização do usuário em 2026-10-18. Backend negocia `scan_finalization_v1` por sessão, persiste versões observadas, rejeita frames de sockets substituídos e confirma estados terminais somente após commit; o probe assinado é restrito ao próprio agente e não anuncia capacidade de instalação.
- Validação focal em PostgreSQL 17 isolado `dmitri_test`: 243 casos passaram na suíte de seis arquivos; após corrigir os três mocks restantes, os mesmos três casos passaram individualmente (246 casos cobertos no total, sem uma única execução final all-green dos seis arquivos). Ruff 0.15.21 passou, OpenAPI gerou tipos byte-idênticos e `npm run typecheck` passou.
- Revisão independente: `[APPROVE]`, sem pendências. Task 8 permanece PENDING, aguardando novo comando do usuário. Nenhum commit/sync, deploy, SSH ou scan real nesta entrega.
- Task 8 iniciada após autorização do usuário em 2026-10-19; Task 9 também autorizada para execução sequencial após aprovação da Task 8. Nenhuma operação ou scan no Raspberry foi iniciada.
- Task 8 concluída após revisão independente `[APPROVE]` em 2026-10-19. Implementados checkpoint/replay duráveis de finalização, retry de ingest com backoff, single-flight compartilhado entre execução e recuperação, reconciliação de park/reconnect sem reexecutar scan, validação local de readiness e proteção de sessão/ACK. Testes focais Windows: 222 passed, 16 skipped; Linux: 238 passed no foco POSIX; suíte completa Linux: 1.523 passed, 16 skipped. Os 15 testes de `test_update_scripts.py` antes pulados por dependências passaram em execução separada (33 passed no arquivo); teste de recuperação isolada com Docker nested passou (1 passed). Ruff/format dos arquivos alterados aprovados. O Ruff global reporta 9 achados em testes não alterados; reservados para fechamento de camada/Task 14. Nenhum scan, SSH, deploy ou alteração do Raspberry.
- Task 9 iniciada em sequência após aprovação da Task 8, conforme autorização do usuário. Escopo: rotas de consulta e admissão manual, controle transacional de permissões/idempotência, exclusão mútua scan/update, envio único na sessão capturada e sincronização OpenAPI/tipos. Sem implementação de claim/eventos da Task 10.
- Task 9 concluída após duas rodadas de correção e revisão independente `[APPROVE]`. A API consulta disponibilidade/histórico/operação e admite atualização manual com autorização viva, idempotência, reserva compartilhada com scans, entrega única à sessão capturada, expiração de pedidos não reclamados e compatibilidade de versão Debian/protocolo/suite. O hello aceita a capability de update sem anunciá-la no agente, que permanece para a Task 12. OpenAPI e tipos foram sincronizados. Suíte focada independente: 220 passed; Ruff nos arquivos backend alterados, geração OpenAPI e typecheck passaram. Warning-only de depreciações Starlette/httpx e chave curta de fixture. Sem commit/sync, deploy, SSH ou scan real.
- Task 10 concluída após revisão independente `[APPROVE]`. Backend valida claims e eventos assinados, aplica sequência e digest idempotentes, mantém autorização sem estender deadline, aceita replay tardio de `installing` somente quando `occurred_at` comprova início antes do prazo, e reconcilia evento local de saúde com hello da sessão atual em qualquer ordem. Expiração só libera reserva antes da mutação; recuperação conserva sua causa, `rolled_back` exige saúde da versão anterior e `needs_intervention` mantém a reserva. Erros 409/410 estão documentados no OpenAPI e tipos sincronizados.
- Gates focais: `tests/test_agent_updates.py` 24 passed; `tests/test_agent_ws_channel.py` 26 passed; subconjunto de fidelidade de contrato 7 passed / 73 deselected; Ruff nos arquivos alterados, `compileall`, parse YAML, geração de tipos e `npm run typecheck` passaram. A suíte completa de `test_contract_fidelity.py` foi interrompida após 30 s (23 casos vistos), sem resultado final; não há pytest ativo.
- Testes executados somente no PostgreSQL descartável `dmitri-task10-postgres`, tmpfs, bind em `127.0.0.1:55432`; permanece ativo para a revisão independente. Uma tentativa inicial identificou que `127.0.0.1:54322/dmitri_test` é banco compartilhado incompatível com migrações; ele não foi mais usado nem alterado.


### Task 10 - coder round 2 apos rejeicao

- Regras de tempo: o inicio autorizado e `occurred_at` do primeiro evento `installing`,
  vinculado a `claimed_at`, a sessao persistida e a `authorization_deadline` imutavel.
  Eventos sao monot?nicos por sequencia e aceitam no maximo dois minutos de avanco de relogio.
  Um evento assinado que chega apos o deadline e aceito se ocorreu dentro da janela; isso nao
  move nem prolonga o deadline. Timestamp invalido e rejeitado sem expirar a operacao nem
  liberar a reserva, pois a mutacao pode ter comecado localmente.
- Validacao fase/outcome/evidencia: falha exige outcome `failed` e codigo de erro; sucesso local
  exige outcome `succeeded` e prova de saude; rollback exige versao/pacote anteriores,
  invocation e prova de pacote configurado, servico ativo e health check aprovado;
  `needs_intervention` exige erro e mantem a fase que reserva o dispositivo. Combinacoes
  incoerentes sao rejeitadas antes de persistencia.
- OpenAPI: rotas assinadas de claim e eventos agora publicam o envelope real de erro nos
  status 409/410, com codigos enumerados; tipos TypeScript regenerados.
- Regressoes adicionadas para replay de evento tardio, timestamp apos deadline, falha com
  outcome de sucesso, rollback sem saude e retencao de reserva em `needs_intervention`.
- Validacao local: `test_agent_updates.py` 27 passed; fidelidade OpenAPI selecionada
  82 passed, 68 deselected; Ruff nos arquivos backend alterados passou; geracao de tipos
  OpenAPI e `npm run typecheck` passaram. PostgreSQL 17 descartavel usa tmpfs e bind
  `127.0.0.1:55433`, banco `dmitri_test`; nenhum teste usou a porta compartilhada 54322.
  O ambiente Python tambem foi criado em pasta temporaria fora dos venvs ligados do checkout.
- Sem commit/sync/deploy, SSH, scan ou alteracao da Task 11/hardware-agent. Task 10 aguarda
  revisao independente.

### Task 10 - coder round 3 após segunda rejeição

- Corrigido o estado `preparing -> expired`: só aceita evento `request_expired` após o
  authorization deadline, com `occurred_at` no deadline ou depois e sem mutação iniciada;
  grava evento, outcome nulo e fase terminal, liberando a reserva.
- Recuperação agora exige mutação previamente registrada e causa `install_failed` ou
  `local_health_failed`; não há transição para recuperação a partir de
  `awaiting_confirmation`. A causa permanece no registro durante progresso e rollback;
  rollback exige versões anteriores, invocation e prova completa de saúde. Falha de
  recuperação pode ser auditada no evento de `needs_intervention` sem apagar a causa.
- Regressões focais cobrem expiração e liberação de reserva, bloqueio após mutação,
  preservação da causa no rollback e ausência de recuperação após confirmação local.
- PostgreSQL 17 descartável em tmpfs, porta `127.0.0.1:55434`, banco `dmitri_test`.
  `test_agent_updates.py`: 30 passed; fidelidade OpenAPI focada: 2 passed;
  Ruff dos arquivos de serviço/teste e `npm run typecheck` passaram. Nenhuma mudança
  de enum/migração ou OpenAPI/tipos foi necessária. Sem commit/sync/deploy, SSH, scan,
  ou alterações da Task 11/hardware-agent.
- Validação independente final em PostgreSQL 17 descartável tmpfs (`127.0.0.1:55434/dmitri_test`): sete arquivos, **287 passed**, 12 warnings; probe de recuperação/intervenção/rollback: **1 passed**. Ruff e `git diff --check` passaram; OpenAPI gerou tipos byte-equivalentes e typecheck teve zero diagnostics. Review round 3: `[APPROVE]`. Sem commit/sync/deploy, SSH, scan ou alteração da Task 11.

### Task 11 — concluída após reavaliação estrutural e revisão independente

- O companion faz preflight, claim idempotente, instalação offline pelo APT previamente provisionado, verificação local, rollback limitado e reporte durável independente. A recuperação preserva gate e evidências quando exige intervenção.
- A revisão encontrou e corrigiu: evento de expiração incompatível antes do claim (agora tombstone local; o worker expira pedidos não reclamados), falha real do `dpkg` reportada com código aceito durante recuperação, e ordem de classificação de `metadata_expired`. Fixtures corrigidas para isolar suite APT `stable` e exercitar keyring ausente com fonte root-owned.
- Validação independente final em WSL/Linux: **62 passed** em `test_updater.py` e `test_update_recovery.py`, incluindo APT HTTPS assinado e rollback Docker com falha real do `dpkg`; Ruff e whitespace scoped passaram. Backend update/migration/contract havia passado **185 testes** em PostgreSQL descartável; geração de tipos OpenAPI e typecheck passaram sem diff.
- Revisão independente final: `[APPROVE]`. Limites: não comprova rollout no Raspberry nem systemd real; conexão daemon → companion e capability são Task 12, integração completa é Task 14. Sem commit/sync/deploy, SSH ou scan real.

### Task 12 — iniciada conforme comando explícito do usuário

- Escopo: fechar WS → daemon → socket companion, reconciliar contexto no hello e anunciar `agent_update_v1` somente quando suporte negociado, instalação preparada e supervisor estiverem prontos. O fluxo de update não inicia nem cancela scans.
- Task 12 concluída após correções e revisão independente final `[APPROVE]`. O probe backend e o agente negociam `agent_update_v1`; o daemon encaminha frames fechados ao companion, e o hello relata contexto durável para reconciliação. Durante `verifying`/`awaiting_confirmation`, a invocation observada pelo handshake preenche contexto ausente do journal somente se a versão do pacote corresponder. Estado `blocked` suprime a capability para novos pedidos, mas ainda permite reconciliar a operação atual; falhas de subprocesso na inspeção degradam a capability sem derrubar o canal de scan.
- Validação independente final: 184 testes focais do hardware agent e 40 testes backend passaram em PostgreSQL 17 descartável; Ruff passou, geração OpenAPI coincidiu com os tipos TypeScript, e `npm run typecheck` passou. Revisão Sol high: `[APPROVE]`. A integração ponta a ponta e o deploy no Raspberry permanecem para Task 14; nenhum scan real, SSH, deploy ou commit/sync foi feito nesta tarefa.

### Task 13 — concluída após revisão independente

- Página do dispositivo agora exibe disponibilidade, readiness, versões observadas, operação atual e histórico. Admin pode solicitar atualização manual com confirmação e chave de idempotência estável; Viewer, dispositivo revogado, offline, busy, legado e demais estados não elegíveis não recebem ação de mutação. Fluxo de atualização permanece separado dos controles de scan.
- Estados de progresso, sucesso local aguardando confirmação remota e resultado confirmado são distintos; sem percentual fabricado. Interface e erros estão localizados em en/pt-BR/ru, com diálogo acessível e anúncios de fase.
- Uma reavaliação estrutural em `STRUCTURAL_REEVAL.md` definiu notificação localizada, deduplicada por episódio para erros dos GETs de disponibilidade/histórico/operação, retenção de dados persistidos durante falha e polling de recuperação para operação ativa.
- Validação independente final: quatro suítes focadas (update, DeviceDetail, comando e cancelamento) **76 passed**; lint, format check, typecheck, build e diff-check passaram. Lint reportou duas advertências preexistentes de Fast Refresh em `LanguageProvider.tsx`; build reportou chunk grande. A execução integral concorrente inicial teve 754/762 aprovados e oito falhas em quatro suítes (`Users.removeMember`, `ResetPassword`, `eslint-rules/no-dark-variant`, `PasswordDialog`); na Task 14, o gate integral serial passou **779/779**, e essas falhas anteriores não se reproduziram. Não restaram falhas frontend pendentes.
- Revisão independente final: `[APPROVE]` após duas rejeições e reavaliação arquitetural. Sem alterações de contrato/tipos, deploy, scan real, SSH ou commit/sync.

### Task 14 — iniciada conforme autorização sequencial do usuário

- Escopo: executar integração/gates completos por camada e Linux compatível, fechar matriz de falhas U01–U16, revisar documentação factual e registrar dependências de rollout. Nenhuma publicação ou instalação real será efetuada.

### Task 14 — validação integrada e documentação (concluída)

- Backend: suíte integral independente **1.773 passed, 0 failed** em PostgreSQL 17 descartável;
  a rodada focal adicional após o último patch cobriu **9/9** casos de atualização. A execução
  separada de `test_contract_fidelity.py` concluiu **150/150 passed**. Ruff passou. Os números
  são execuções separadas: os 9 casos novos não fazem parte da suíte integral independente acima.
- Hardware agent em Linux/WSL: **1.597 passed** na suíte integral; `test_updater.py` passou
  **62** testes e, em arquivo/execução separada, `test_update_recovery.py` passou **4** testes de
  recuperação com Docker. Os 4 testes Docker não estão incluídos nos 62. Ruff passou. O teste
  de evento com ACK perdido/restart confirma replay do mesmo evento persistido, sem duplicar o journal.
- Frontend: suíte serial **779/779 passed** (serializada após timeouts/falhas intermitentes sob
  concorrência). Lint, Prettier, typecheck e build passaram; tipos OpenAPI gerados coincidem
  byte a byte com `frontend/src/types/openapi.d.ts`. Permanecem avisos de lint Fast Refresh já
  conhecidos e aviso de chunk grande no build.
- Integração/documentação: cobertura representativa rastreada na matriz abaixo. Todos os casos
  usam fixtures, sockets, banco e pacote de teste; não houve publicação, deploy, instalação no
  Raspberry, execução de systemd real ou scan real. **H1–H6 permanecem pendentes**, portanto
  estes gates demonstram validação do código, não prontidão operacional.
- Docs-sync executado uma vez para o diff desta feature: code-map atualizado para companion,
  daemon/canal e UI/API; `TASKS.md` agora reflete Tasks 11–13 como concluídas. ADRs e runbooks
  não foram reescritos: veja a decisão documental no fim desta seção. Task 14 segue IN_PROGRESS
  até aprovação independente desta documentação.

| Critério | Evidência automatizada representativa | Resultado nesta rodada |
|---|---|---|
| U01 versão/procedência | `backend/tests/test_agent_updates.py`; `backend/tests/test_agent_ws_channel.py`; `hardware-agent/tests/unit/test_updater.py`; `frontend/src/pages/DeviceDetail.updates.test.tsx` | backend/contrato/UI passaram; pacote e versão local verificados em Linux |
| U02 publicação disponível | `backend/tests/test_release_catalog.py`; `backend/tests/test_agent_updates.py`; `frontend/src/pages/DeviceDetail.updates.test.tsx` | catálogo e projeção de disponibilidade cobertos; sem publicação hospedada |
| U03 permissões | `backend/tests/test_agent_updates.py`; `frontend/src/pages/DeviceDetail.updates.test.tsx` | autorização backend e ocultação/bloqueio UI passaram |
| U04 confirmação manual | `frontend/src/pages/DeviceDetail.updates.test.tsx`; `backend/tests/test_agent_updates.py` | confirmação e admissão manual cobertas |
| U05 scan/upload/finalização concorrente | `hardware-agent/tests/unit/test_scan_lock.py`; `hardware-agent/tests/unit/test_daemon.py`; `hardware-agent/tests/unit/test_updater.py` | bloqueio compartilhado validado em Linux; nenhum scan real |
| U06 exclusão mútua local/remota | `hardware-agent/tests/unit/test_scan_lock.py`; `hardware-agent/tests/unit/test_updater.py`; `backend/tests/test_agent_updates.py` | testes de lock/reserva e concorrência passaram |
| U07 offline ou agente legado | `backend/tests/test_agent_ws_channel.py`; `hardware-agent/tests/unit/test_daemon.py`; `frontend/src/pages/DeviceDetail.updates.test.tsx` | capability/readiness degradada e estados não elegíveis cobertos |
| U08 idempotência/reconexão | `backend/tests/test_agent_updates.py`; `backend/tests/test_agent_ws_channel.py`; `hardware-agent/tests/unit/test_updater.py` | replay e contexto de sessão cobertos; ACK perdido/restart reenvia mesmo evento |
| U09 catálogo/publicação inválida | `backend/tests/test_release_catalog.py`; `hardware-agent/tests/unit/test_updater.py` | assinatura, validade, origem/suite, hash e colisão rejeitados nas fixtures |
| U10 reinício previsto | `hardware-agent/tests/unit/test_updater.py`; `hardware-agent/tests/integration/test_update_recovery.py`; `backend/tests/test_agent_ws_channel.py` | recuperação/reconciliação simuladas passaram; sem systemd real |
| U11 falha/rollback/intervenção | `hardware-agent/tests/unit/test_updater.py`; `hardware-agent/tests/integration/test_update_recovery.py`; `backend/tests/test_agent_updates.py` | `test_updater.py`: 62 passed; em arquivo/execução separada, `test_update_recovery.py`: 4 Docker passed (não incluídos nos 62) |
| U12 interrupção de rede/energia | `hardware-agent/tests/unit/test_updater.py`; `hardware-agent/tests/integration/test_update_recovery.py` | journal persistente, retry e reinício testados em Linux descartável |
| U13 backend indisponível | `hardware-agent/tests/unit/test_updater.py`; `backend/tests/test_agent_updates.py` | eventos pendentes são mantidos/retry; fluxo focal backend 9/9 passou |
| U14 histórico/privacidade | `backend/tests/test_agent_updates.py`; `frontend/src/pages/DeviceDetail.updates.test.tsx` | snapshots de auditoria e apresentação sem segredos cobertos |
| U15 localizado/acessível | `frontend/src/pages/DeviceDetail.updates.test.tsx`; `frontend/src/i18n/messages/{en,pt-BR,ru}.ts` | teclado/foco, anúncio e cópias nos três idiomas passaram nos testes e typecheck |
| U16 preparação/distribuição | `backend/tests/test_release_catalog.py`; `hardware-agent/tests/unit/test_updater.py`; `hardware-agent/tests/integration/test_update_recovery.py` | cadeia local de teste validada; H1–H6 seguem pendentes para uso operacional |

#### Limites e decisões documentais

- Não foi executada atualização ou bootstrap de dispositivo real; não se afirma que o Raspberry
  possua companion, timer ou repositório configurado. Evidência de pacote/recovery é descartável.
- `docs/DEV-SETUP.md`, `docs/PI-INSTALLER.md` e `docs/PI-RECOVERY.md` não receberam mudança
  de comando ou ambiente neste diff que exigisse ajuste factual adicional. ADR-011 e ADR-021
  registram decisões aceitas; a skill `architecture-adr-sync` não está disponível nesta sessão,
  então decisões/claims alvo não foram reescritos. Uma revisão arquitetural humana pode decidir
  se a nota histórica de ADR-021 sobre UI e versão persistida deve receber adendo de implementação.
- A checagem ampla do code-map encontrou links antigos quebrados em conceitos não alterados,
  apontando para specs históricos ausentes neste checkout; e `MAINTAINING.md` contém o link
  `./concept.md` apenas como exemplo de formato. Os links novos e os índices afetados foram
  verificados e resolvem. Os links históricos fora do diff não foram reescritos nesta rodada.
- Revisão integrada de produto: `[APPROVE]`; revisão documental após correções factuais: `[APPROVE]` em 2026-10-20. Tasks 1–14 concluídas. Sem commit/push, publicação, deploy ou operação no Raspberry.
