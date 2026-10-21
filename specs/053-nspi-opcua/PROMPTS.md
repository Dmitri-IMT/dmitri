# Contextualização e harness dos subagentes — OPC UA

Status: execution authorized by user; Task 1 complete and reviewer-approved. Wait for the user's command before starting Task 2.
Planning is complete; follow the current task state in TASKS.md and stay within its target files.

Prioridade do usuário (2026-10-20): desenvolver para o front. Na TUI, limitar trabalho
à compatibilidade necessária com o motor/contrato compartilhado. Detalhes, resumos,
novas tabelas e melhorias visuais ficam adiados e não bloqueiam a entrega. Não criar
subagentes ou ciclos de implementação para apresentação detalhada na TUI.

## Fontes de contexto

| Contexto | Fonte mínima | Regra |
|---|---|---|
| Regras e base | `AGENTS.md`, branch/HEAD/status | Preservar alterações existentes. |
| Mapa | `.claude/docs/index.md` e mapas apontados pela tarefa | Ler seletivamente. |
| Produto | `specs/053-nspi-opcua/TRUTH.md` | Critérios A01–A16. |
| Técnica | `ARCHITECTURE.md` e a seção pertinente de `INTEGRATION.md` | Caminhos e contrato são vinculantes após aprovação. |
| UI | `DESIGN.md` | Carregar para apresentação/testes web; TUI somente no trecho de compatibilidade. |
| Tarefa | `TASKS.md`, seção da tarefa | Criado após aprovação; uma tarefa por execução. |
| Handoff | Arquivos, decisões, comandos e falhas da etapa anterior | Até 12 linhas; sem colar logs completos. |

Não ler todos os arquivos de `docs/`, os chats anteriores, as specs 051/052 completas
ou todos os testes antes de começar. Preferir `rg` e leitura dos trechos pertinentes.
Se faltar uma decisão, registrar a dúvida específica para o orquestrador.

## Skills por papel

- Planejamento: `.agents/skills/feature-planning/SKILL.md` e
  `.agents/skills/consult-docs/SKILL.md`.
- Criação de ledger: `.agents/skills/create-tasks/SKILL.md`, após aprovação.
- Orquestração: `.agents/skills/feature-orchestrator/SKILL.md`.
- Testes Python: `.agents/skills/tdd/SKILL.md`; usar interfaces existentes e testes de
  comportamento, sem criar casos que apenas repitam a implementação.
- Web e design: `.agents/skills/frontend-conventions/SKILL.md` e
  `.agents/skills/frontend-design-system/SKILL.md`.
- Verificação de contrato publicado: `.agents/skills/openapi-contract-sync/SKILL.md`,
  respeitando seu escopo de verificação e documentação. A implementação dos schemas
  continua sendo tarefa do coder.
- Documentação de fechamento: `.agents/skills/docs-sync/SKILL.md`, uma vez ao final.

## Envelope de despacho

Preencher este envelope com dados reais antes de criar o subagente. O perfil TOML
contém o modelo/esforço; usar a seleção real da ferramenta. Não alterar perfis globais.

```text
ROLE: <agent-developer | test-engineer | code-reviewer | ...>
MODEL / EFFORT: <selecionados na chamada>
WORKTREE: <caminho absoluto validado>
BRANCH / HEAD: <branch e commit conferidos nesta execução>
FEATURE: specs/053-nspi-opcua
TASK: <somente ID e seção correspondente de TASKS.md>
ACCEPTANCE: <IDs de TRUTH.md e critérios da tarefa>
READ: <specs/seções, skill e mapas mínimos necessários>
WRITE: <allowlist de caminhos exatos; vazia para reviewer>
PRIOR HANDOFF: <resumo verificável, até 12 linhas>
CHECKS: <comandos focais da tarefa; cwd explícito>
STOP: <artefato esperado e formato do handoff>
```

Cada sessão usa `fork_turns="none"`. O modelo efetivo é registrado no ledger.
Handoff obrigatório: resultado, arquivos, decisões, verificações, falhas e limites.
Nenhum worker tem autorização implícita para commit, PR, deploy ou scan fora do harness.

## Coder — Luna medium

```text
Implemente somente a tarefa indicada no envelope e seus critérios aprovados.
Leia AGENTS.md, a skill aplicável e os caminhos/seções mínimos apontados.
Confira chamadores e reaproveite a etapa industrial atual. Não crie modo novo.
Preserve Modbus, a fronteira de somente leitura e a política de evidência.
Não amplie WRITE. Se o contrato impedir a tarefa, devolva a dúvida ao orquestrador.
Não implemente a tarefa seguinte nem altere unrelated code/formatting.
Execute os checks focais do envelope e devolva handoff de até 12 linhas.
```

## Tester — Luna medium

```text
Verifique os critérios observáveis da tarefa e o handoff do coder.
Trabalhe somente nos testes/fixtures autorizados. Não importe diretamente funções
internas da biblioteca se isso esconder o tráfego efetivo do coletor.
Inclua sucesso, recusa, limites, cancelamento e compatibilidade conforme o critério.
Use o laboratório loopback para provar os serviços enviados e a ausência de mutação.
Procure vazamento de valores de processo em JSON, logs, ingest, relatórios e IA.
Rode os testes focais; informe falhas, contadores e limites de validade da evidência.
```

## Reviewer — Sol 6.1 medium ou high

```text
Revise a tarefa contra seus critérios, specs, diff e resultados do tester.
Não edite arquivos. Execute os gates focais necessários; não aprove gates ausentes.
Confira TODOS os caminhos afetados: CLI/headless/daemon, ScanRunner/TUI,
serialização/ingest, persistência/leituras, relatórios e consumidores do contrato.
Nos checks críticos, confira alvo fixo, ausência de downgrade implícito,
orçamento compartilhado, cancelamento e evidência anunciada versus verificada.
Esta entrega produz observações UA; nenhum finding ou severidade UA é autorizado.
A primeira linha do handoff deve ser [APPROVE] ou [REJECT].
Em rejeição, cite arquivo/linha, critério violado e reprodução delimitada.
Em aprovação, informe verificações e limitações concretas, sem afirmar produção.
```

Usar high nas tarefas de transporte, mapeamento, cancelamento e matriz de evidências;
medium nas demais. O revisor não precisa reexecutar uma suíte completa já aprovada
para a mesma base, salvo mudança, gate obrigatório ou risco concreto restante.

## Evidências do harness

Para cada cenário do laboratório, conservar uma síntese dos pedidos recebidos,
status, cancelamento e contadores; não conservar valores de processo. Correlacionar
com o hash do checkout, versão da biblioteca e cenário executado.

Obrigatórios: discovery-only; sessão recusada; leitura recusada; leitura permitida;
endpoint externo; referências externas; ciclos/paginação; excesso de dados; timeout;
cancelamento durante I/O; coleta mista Modbus/OPC UA; contrato legado; ausência de
Write/Call/subscriptions; escape; nenhuma exposição de valores ou credenciais.

No fechamento, o reviewer de cada camada registra os gates exigidos por `AGENTS.md`.
Backend requer banco `dmitri_test` preparado com `database.sh`; ausência do banco não
é teste aprovado. OpenAPI e tipos são gerados pelos comandos existentes, sem edição
manual de artefatos. Formatação automática fica restrita aos arquivos autorizados.

## Retomada

O ledger futuro deve permitir continuar por tarefa sem reler o chat. Registrar:
status, dependências, decisões aprovadas, rejeições e evidência final de cada ciclo.
Status de implementação nunca deve ser COMPLETED sem aprovação do reviewer.
O chat permanece em execução enquanto houver worker ativo; o orquestrador comunica
conclusão ou bloqueio real antes de encerrar a resposta. O indicador visual é do cliente.
