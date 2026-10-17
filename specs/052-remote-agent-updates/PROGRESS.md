# Progresso — atualização remota do agente

- Estado: TASK_1_COMPLETED; Tasks 2–14 PENDING.
- Autorização atual: comando explícito do usuário para fazer a Task 1.
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
