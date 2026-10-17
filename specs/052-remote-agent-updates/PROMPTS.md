# Prompts — atualização remota do agente

Estado: `TASKS.md` preparado por solicitação do usuário; implementação aguarda seu comando.
Selecionar modelos e esforço no cliente/chamada real; não simular mudança de modelo em texto.
Contexto compacto: `TRUTH.md`, `PLAN.md`, a tarefa selecionada em `TASKS.md` e `PROGRESS.md`.
Se `.agents/skills/` ou `.codex/agents/` não contiverem arquivos na base em uso, ler as skills
e perfis existentes em `.claude/`; não restaurar/copiar o harness durante esta feature.

## 1. Retomar e revisar o planejamento

Modelo: GPT-6.1 Sol medium; high somente para decisão técnica crítica ainda aberta.

```text
Retome o planejamento de specs/052-remote-agent-updates. Leia AGENTS.md, PROGRESS.md e PLAN.md,
depois os trechos relevantes de TRUTH/ARCHITECTURE/INTEGRATION/DESIGN. Use consult-docs e o
mapa .claude/docs/index.md para localizar código. Verifique branch/HEAD e alterações existentes.
O usuário autorizou criar TASKS.md, já presente, e reservou desenvolvimento para seu comando.
Sem esse comando, mantenha somente planejamento; não regenere o ledger existente.
Confirme capacidades reais de pacote, APT, locks, timer, WS e permissões, sem SSH ou scans.
Não presuma repositório de releases assinado ou segredos de publicação já configurados.
Atualize somente as specs se houver drift factual e apresente as decisões materiais para aprovação.
```

## 2. Iniciar as tarefas ao comando do usuário

Modelo: GPT-6.1 Sol medium, papel orquestrador.

```text
Retome specs/052-remote-agent-updates a partir do TASKS.md existente. O usuário autorizou a
decomposição; inicie código somente quando ele mandar desenvolver. Não solicite nova confirmação
para uma tarefa que esse comando já autorize. Leia AGENTS.md, PROGRESS.md, PLAN.md e a tarefa
selecionada, depois feature-orchestrator e os perfis realmente disponíveis.
Não regenere TASKS.md nem zere progresso/rejeições. Confira a base efetiva: revisão original em
b207a83, decomposição em a178aa6 na branch feature/remote-agent-updates. Revalide símbolos,
chamadores e head Alembic antes da mudança; não faça pull/troca de branch automaticamente.
Comece pela Task 1, ou outra explicitamente escolhida com dependências satisfeitas.
H1–H6 são HUMAN_INFRA_REQUIRED. Não invente acesso a hosting/chaves; registre bloqueios e continue somente
trabalho independente que entregue uma parte completa, sem substitutos temporários.
Atualize PROGRESS.md e USAGE.md. Não implemente como orquestrador nem rode gates como reviewer.
Deixe commit, push, release, deploy e scan real para autorização específica.
```

## 3. Despachar uma tarefa de implementação

Modelo: GPT-6 Luna medium, contexto novo e somente uma tarefa.

```text
Papel: agent-developer. Implemente apenas a Task {N} de
specs/052-remote-agent-updates/TASKS.md. Leia AGENTS.md e os trechos das specs citados nessa tarefa.
Arquivos permitidos: {CAMINHOS}. Critérios: {CRITERIOS}. Decisões fechadas: {DECISOES}.
Confirme que as dependências da tarefa foram aprovadas e revalide seus caminhos na base atual.
Use as skills relevantes para a camada. Confira símbolos e chamadas reais antes de editar.
Reutilize auth, HTTP, WS, empacotamento e locks existentes. Não invente API de shell remoto,
URL arbitrária de pacote ou atualização do próprio agente dentro de seu processo.
Não altere estado de scans para permitir atualização. Preserve configuração, identidade e resultados.
Não amplie o escopo para resolver uma decisão aberta: relate o ponto específico ao orquestrador.
Rode as verificações focais exigidas pela tarefa e registre resultados reais.
Não marque a tarefa aprovada, publique pacote, instale no Pi, execute scan, faça commit ou push.
Entregue arquivos alterados, testes/verificações, riscos e handoff curto.
```

## 4. Engenharia de testes independente

Modelo: GPT-6 Luna medium, contexto separado do coder.

```text
Papel: test-engineer (ou frontend-test-engineer). Valide somente Task {N} e seus critérios aprovados.
Leia os caminhos das specs e o handoff em {HANDOFF}; não carregue a conversa inteira.
Arquivos de teste permitidos: {CAMINHOS}. Inspecione o diff e fortaleça testes de comportamento,
especialmente permissões, concorrência, reconexão, idempotência, falha e preservação de dados
quando pertinentes à tarefa. Use pacotes/serviços falsos em ambiente isolado.
Nunca use o Raspberry real, APT do host, chaves reais de release ou rede industrial como teste.
Para backend, siga database.ps1/database.sh e use somente dmitri_test; ausência do banco não é passe.
Não corrija produto fora do escopo. Entregue resultados, arquivos e bloqueios; aprovação é do reviewer.
```

## 5. Revisão da tarefa

Modelo: GPT-6.1 Sol high para confiança/privilégios/autorização/replay/locks/recuperação;
medium para UI/localização/documentação com decisões fechadas.

```text
Papel: reviewer independente. Revise somente Task {N} contra specs aprovadas, critérios, diff e
handoffs de coder/tester. Não edite arquivos. Primeira linha: [APPROVE] ou [REJECT].
Inspecione contratos entre camadas, chamadas e estados de falha relevantes. Rode gates focais
exigidos; gate indisponível ou falhando não conta como aprovado. Não rode scans reais ou installs
no host/dispositivo. Exija integridade/autenticidade, compatibilidade de legado, lock entre todas
as entradas de scan e update, estado durável e confirmação observada quando a tarefa os tocar.
Na rejeição, cite arquivo/critério e reproduza o problema de modo delimitado. Na aprovação, liste
verificações e limites. Não aprove apenas porque o coder afirmou conclusão.
```

## 6. Fechamento e documentação

Modelo: GPT-6 Luna medium para docs-sync; revisão material permanece com Sol.

```text
Na Task 14 de specs/052-remote-agent-updates, após aprovação das Tasks 1–13, execute docs-sync
uma única vez para o diff completo. Não repita se a execução já estiver registrada nessa tarefa.
Confira .claude/docs, ADR-021 e guias de instalação/recuperação sem copiar
alegações de planejamento para a seção de produto implementado. Registre infraestrutura e
bootstrap realmente executados versus pendentes, gates completos e limitações conhecidas.
Não declare atualização remota operacional só porque mocks passaram. Preserve PROGRESS/USAGE,
reporte drift contestado e não faça commit, push, release, deploy ou scan sem autorização.
```

## Regras para todos os despachos

- `fork_turns="none"` com modelo e esforço explícitos quando o cliente oferecer esse mecanismo.
- Uma tarefa por vez; fechar/liberar worker ou usar sessão separada que encerra, conforme a skill.
- Handoff e caminhos em vez de repetir documentos inteiros. Não lançar agentes exploratórios sem
  uma decisão/artefato concreto que justifique o custo.
- Rejeição pede coder novo; motivo repetido exige resolver arquitetura antes de reimplementar;
  quarta rejeição segue reavaliação estrutural e aprovação humana conforme a skill.
- Consumo indisponível deve ser declarado; não converter tokens em saldo/percentual do plano.
