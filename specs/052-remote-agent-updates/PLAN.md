# Plano de execução — atualização remota

Status: tarefas detalhadas a pedido do usuário; desenvolvimento aguarda seu comando.

## Resultado esperado

Um administrador atualiza o agente pelo navegador depois da preparação inicial do dispositivo.
O sistema mostra versões, publicação disponível, andamento e resultado observado. Preserva dados
e impede atualização durante scan. Instalação continua fora do processo que será substituído.

As regras estão em `TRUTH.md`; decisões técnicas em `ARCHITECTURE.md` e `INTEGRATION.md`; experiência
web em `DESIGN.md`. Nenhum documento deve ser tratado como comprovação de implementação.

## Etapas futuras propostas

As seis entregas abaixo foram decompostas em **14 tarefas** em `TASKS.md`, com caminhos,
testes, dependências, critérios U01–U16 e modelos por papel. A autorização atual cobre a
decomposição; nenhuma implementação foi iniciada.

| Ordem | Entrega | Dependência principal |
|---|---|---|
| 1 | Fechar identidade de releases, confiança, distribuição e preparação inicial | Decisões de hosting/chave e responsáveis explicitados |
| 2 | Atualizador local durável, exclusão mútua e recuperação | Pacote verificável e versão anterior recuperável |
| 3 | Estado persistido e API com permissão por organização | Contratos e ciclo de vida aprovados |
| 4 | Capacidades, entrega e reconciliação entre backend, agente e atualizador | Estado persistido e protocolo compatível com legado |
| 5 | Versões, confirmação, andamento e histórico na página do dispositivo | API/protocolo estabilizados e tipos gerados |
| 6 | Fechamento de regressões, falhas, documentação e rollout | Critérios por camada aprovados; infraestrutura validada separadamente |

Cada tarefa de implementação inclui seus testes de comportamento e revisão antes da próxima.
A última etapa fecha gates e integração; não adia todos os testes para o final.

Correspondência: distribuição/confiança → Tasks 2/4/5 e H1–H6; atualizador/locks/recuperação →
3/6/8/11; persistência/API → 1/9/10; protocolo/reconciliação → 7/8/10/12; frontend → 13;
fechamento → 14. As dependências em `TASKS.md` governam a ordem real, não a numeração das
entregas macro. Primeira tarefa sugerida: **Task 1**.

## Modelos e papéis

| Papel | Seleção preferida | Uso e limite |
|---|---|---|
| Orquestração futura | GPT-6.1 Sol medium | Ledger, escopo, handoffs e triagem; sem implementar ou aprovar o próprio trabalho |
| Arquitetura | GPT-6.1 Sol high | Confiança de pacotes, privilégios, concorrência, reinício e recuperação; uma decisão compartilhada |
| Desenvolvimento | GPT-6 Luna medium | Uma tarefa fechada com caminhos e critérios definidos |
| Engenharia de testes | GPT-6 Luna medium | Contexto independente; fortalecer comportamento e casos de falha da tarefa |
| Revisão crítica | GPT-6.1 Sol high | Publicação confiável, instalador privilegiado, autorização, replay, locks e recuperação |
| Revisão delimitada | GPT-6.1 Sol medium | UI, localização e documentação quando o contrato já estiver fechado |
| Design e docs-sync | GPT-6 Luna medium | Conteúdo e integração visual com decisões já definidas |

Selecionar modelo e esforço na chamada real. Um nome dentro do prompt não altera o modelo.
Se a seleção falhar, registrar a indisponibilidade antes de substituir qualquer modelo.

## Economia de contexto e limites de gasto

- Contexto novo por papel, com caminhos e critérios; não herdar toda a conversa.
- Um coder por vez: coder → tester → reviewer. Não criar vários agentes para a mesma busca simples.
- Ler mapa e trechos relevantes; não copiar diretórios inteiros de documentação para prompts.
- Handoff curto: arquivos alterados, decisões, verificações e dúvidas concretas. Logs completos
  ficam em artefatos locais; resumos bastam na conversa.
- Gates focais por tarefa; gates completos no fechamento da camada. Repetir somente quando houver
  mudança, falha ou risco ainda não resolvido.
- Registrar uso disponibilizado pela ferramenta sem somar acumulados duas vezes. Tokens de API
  ou de sessões não devem ser convertidos em porcentagem do limite do plano Codex sem dados reais.
- Não estimar economia percentual nem custo monetário sem métrica comparável. Medir o primeiro
  ciclo completo antes de ajustar a seleção de modelos nas tarefas seguintes.
- Preservar os quatro passos de rejeição/reavaliação da skill; não insistir com novos coders sem
  resolver primeiro uma decisão arquitetural repetidamente ambígua.

## Sessões e infraestrutura

O planejamento original usou os perfis em `.codex/agents/`. Na base `a178aa6`, os diretórios
Codex/skills espelhados estão sem os arquivos esperados; consultar os arquivos existentes em
`.claude/skills/` e os perfis reais disponíveis antes de despachar. Não recriar o harness como
parte da feature. Onde o cliente não expõe fechamento de threads, usar sessões separadas e sequenciais,
com encerramento verificável, conforme as skills; não fingir uma ação de fechamento inexistente.

O planejamento atual usa sessões CLI efêmeras com modelo/esforço explícitos. Elas só podem
escrever os documentos designados e encerram ao concluir o handoff. A configuração da sessão
coordenadora não é alterada nem apresentada como um modelo diferente.

Infraestrutura de publicação e confiança precisa ser preparada e validada antes do rollout real.
Preparar código ou mocks não comprova distribuição operacional. Não provisionar hosting, chaves,
segredos de CI ou dispositivos como consequência automática da aprovação das specs.

## Gate para começar

As tarefas estão preparadas. Quando o usuário mandar iniciar o desenvolvimento, usar
`PROMPTS.md` para executar a primeira tarefa com dependências satisfeitas em `TASKS.md`.
Conferir drift da base antes de implementar, pois a revisão original das specs usou `b207a83`
e a decomposição usa `a178aa6`. Decisões de infraestrutura abertas continuam H1–H6.

Não executar scan real, cancelamento, deploy no Raspberry, commit/push ou publicação de releases
como parte da execução de tarefas sem autorização específica para essas operações.
