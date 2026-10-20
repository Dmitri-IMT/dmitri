# Reavaliação estrutural — histórico das Tasks 4 e 11

## Sintoma

A Task 4 chegou à quarta rejeição e foi marcada `BLOCKED_STRUCTURAL`, conforme a
skill `feature-orchestrator`. Esta avaliação examina a decomposição, o contrato e
o diff atual; não é aprovação de código nem execução dos gates.

Histórico informado pelo orquestrador e confrontado com o código e as regressões:

| Rodada | Achados |
|---|---|
| 1 | Candidato antigo podia regredir o catálogo; `Packages` descartava Depends/Pre-Depends/Conflicts/Breaks; índices by-hash antigos não permaneciam na URI estável; candidate/suite permitiam caminhos fora da área gerenciada; refresh podia produzir Date no futuro. |
| 2 | Identidade de release divergente entre suites e symlink dentro do candidato permitiam efeitos fora da árvore gerenciada. |
| 3 | Symlinks em pais gerenciados (`.staging`, `pool`, `snapshots`, `dists` e `.publish.lock`) ainda permitiam escapes. |
| 4 | Somente `import sys` sem uso no Python embutido em `publish-apt.sh`. |

Os achados anteriores eram relevantes para integridade e confinamento de arquivos,
não simples questões de estilo. Foram corrigidos e receberam regressões. A última
rejeição não aponta falha funcional ou mudança de contrato.

## Causa raiz

A arquitetura já exige identidade imutável, snapshots e índices por conteúdo,
promoção atômica e retenção. A Task 4 já reúne preparação, assinatura separada e
promoção, com verificação em repositório descartável. Esses limites continuam
coerentes e testáveis sem infraestrutura externa.

As rejeições decorreram de implementação incompleta desses invariantes nas
fronteiras entre comandos e sistema de arquivos: validar apenas um candidato ou
uma fase não protegia todos os caminhos, a promoção precisava confrontar a base
atual e a retenção precisava preservar as URIs by-hash utilizadas pelos clientes.
A perda de campos de controle era defeito de geração do índice APT. Nenhum desses
casos requer outro protocolo, armazenamento ou decomposição da feature.

O código atual contém comandos `prepare`, `sign` e `promote`, mutex comum,
restrição à suite `stable`, validação dos pais e da árvore gerenciada, geração e
digest de base cobertos pela assinatura, controle completo do pacote, retenção
by-hash e troca atômica do ponteiro da suite. As regressões examinadas exercitam
essas fronteiras. O import remanescente é um defeito de limpeza após as correções;
o lint normal de arquivos Python não cobre automaticamente um heredoc em `.sh`.

## Plano revisado

1. Manter a arquitetura, a decomposição e os critérios atuais da Task 4.
2. Após a decisão do orquestrador sobre a retomada autorizada, um **coder novo**
   remove apenas o `import sys` sem uso no Python embutido. Não reabrir assinatura,
   promoção ou estrutura do repositório por essa correção.
3. Conferir estaticamente o Python extraído do heredoc além dos arquivos Python
   normais; revisão de scripts deve considerar o código efetivamente executado.
4. Submeter novamente ao reviewer independente. Preservar todas as regressões e
   evidências funcionais; repetir testes somente se o reviewer identificar risco
   residual ou mudança adicional que justifique a execução.
5. Registrar o resultado e somente marcar a task concluída após `[APPROVE]`.

**Não é necessária mudança de escopo.** Um coder novo pode remover o import sem
uso dentro do escopo já autorizado.

## Alterações de especificação necessárias

Nenhuma alteração de `TRUTH.md`, `ARCHITECTURE.md`, `INTEGRATION.md` ou dos critérios
de sucesso é necessária. Os reparos implementam os invariantes existentes. A
checagem do Python embutido é ajuste do procedimento de validação, sem ampliar
o produto ou o contrato público.

O orquestrador deve preservar o histórico das quatro rejeições neste registro ao
tratar a transição de `BLOCKED_STRUCTURAL` e eventual reinício do contador. Esta
avaliação não altera o ledger nem declara a tarefa aprovada.

## Implicações de teste e aprovação

Segundo o handoff do orquestrador, a rodada mais recente passou **24 testes focais
em Linux**, incluindo as regressões de segurança do repositório, e uma prova APT
isolada com `apt-get update` e `apt-cache show`. Esses resultados são evidência
reportada por tester/reviewer; não foram executados novamente nesta avaliação.
Não comprovam publicação externa, instalação no Raspberry ou prontidão operacional.

A skill exige reavaliação estrutural e aprovação humana antes de mais código na
quarta rejeição. O usuário já autorizou explicitamente desenvolver as Tasks 3 e 4
em sequência, com bypass para superar bloqueios. Como não há alteração de escopo
ou decisão arquitetural nova, esta avaliação recomenda que o orquestrador use
essa autorização para a correção delimitada e nova revisão, sem criar uma nova
etapa de confirmação. O bypass não substitui o `[APPROVE]` do reviewer.

H1/H2/H6 continuam pendentes para publicação operacional. Nenhuma chave de
produção, repositório externo, workflow, instalação APT no host, operação no Pi,
scan ou commit está incluído na retomada proposta.

## Task 11 — aprovada após cinco rejeições

### Reavaliação

As rejeições identificaram fronteiras concretas entre o estado local do companion
e o contrato já definido pelo backend: resultado local inválido em expiração,
classificação de falha real do `dpkg`, e reporte remoto de uma solicitação que
expirou antes do claim. Também foi corrigida a precedência de `metadata_expired`
no classificador de erros. A decomposição e o protocolo público permanecem
adequados; nenhum endpoint, enum ou migração adicional foi necessário.

### Reparos e evidência

- Expiração pré-claim agora cria tombstone local idempotente, sem outbox HTTP; o
  worker do backend continua encerrando solicitações não reclamadas. Teste cobre
  expiração durante preflight, ausência de evento/dpkg e replay depois de restart.
- Falha real de execução do `dpkg` é classificada como `install_failed`; teste
  integrado executa `dpkg --install` sobre pacote ausente em container isolado e
  confirma recuperação real/rollback reportado.
- `metadata_expired` preserva seu código específico; fixtures APT distinguem
  precisamente stable de unstable e validam fonte root-owned sem keyring.
- Reteste independente WSL/Linux: 62 testes focados passaram, incluindo fixtures
  Docker; Ruff e whitespace passaram. Revisão independente final: `[APPROVE]`.

As cinco rejeições e a reavaliação não alteraram escopo nem justificaram uma nova
aprovação arquitetural. Os limites de rollout real/systemd permanecem para a
validação operacional futura, sem bloquear o handoff da Task 12.

## Task 13 — erros dos três GETs da seção de atualização

### Achado estrutural

Duas revisões independentes rejeitaram o tratamento incompleto de erros de leitura.
Na primeira rodada, disponibilidade e histórico eram exibidos como erros inline e
o POST também precisava de toast; esses caminhos passaram a usar toast. Na segunda,
o GET da operação ativa (`/agent-updates/{id}`), inclusive seu polling, continuou
sem notificação. `AgentUpdateSection` observa `availability.isError` e
`history.isError`, mas não `operation.isError`. O botão de atualização manual também
exibe `updates.refreshFailed` além dos toasts dos GETs que falharem.

O limite de responsabilidade é o conjunto das três queries de leitura de
`useAgentUpdate`: disponibilidade, histórico e operação. TanStack Query v5 não
oferece `onError` por query; a seção que consome as três queries deve observar seus
resultados. O estado `isError` sozinho não identifica uma nova falha: ele permanece
verdadeiro durante renders e novas tentativas de polling. No pacote v5 instalado,
`errorUpdateCount` cresce quando a busca termina em erro, depois dos retries, e
um sucesso limpa `error`/`isError` sem apagar `data` em uma falha anterior. Um efeito
que chama `show` sempre que `isError` é verdadeiro pode repetir toasts; um efeito
que observa apenas a borda `false → true` perde a distinção entre operações ao
trocar a query key.

### Decisão e handoff de implementação

1. Centralizar a notificação dos três GETs em `AgentUpdateSection`, usando o mesmo
   pequeno mecanismo para os três resultados, sem `onError` de query e sem
   tratamento de erro dentro de `queryFn`. Associar cada resultado à identidade
   efetiva da query: tipo + `agentId` para disponibilidade/histórico, e tipo +
   `update_id` para operação. Ignorar a query de operação enquanto não houver
   `update_id` e ela estiver desabilitada.
2. Manter, em `useRef`, um registro de episódio de falha por identidade. Ao observar
   `isError` com `errorUpdateCount > 0`, emitir **um** toast localizado se ainda
   não houve notificação nesse episódio; marcar o episódio antes de chamar `show`.
   Enquanto continuar em erro, novos `errorUpdateCount` do polling, retries de
   refetch, renders e mudanças de função de tradução não emitem outro toast. Um
   resultado `isSuccess` encerra o episódio; a próxima falha pode gerar um novo
   toast. A mudança de agente ou operação usa uma identidade nova, sem herdar o
   bloqueio da anterior. Não usar apenas `errorUpdatedAt` como deduplicador: cada
   falha subsequente de polling tem um timestamp novo.
3. Usar `updates.readFailed` para disponibilidade e `updates.historyFailed` para
   histórico. Acrescentar uma chave própria para falha de leitura da operação,
   com texto em en, pt-BR e ru. O texto deve indicar impossibilidade de atualizar
   o **status remoto**, sem afirmar falha de instalação, rollback ou perda do
   resultado persistido. Não exibir mensagem bruta da API.
4. O botão **Atualizar status** deve chamar os refetches existentes e tratar a
   rejeição da Promise, mas não emitir o toast genérico `updates.refreshFailed`.
   Cada GET malsucedido passa pelo mesmo notificador; uma falha já notificada e
   ainda não recuperada pertence ao mesmo episódio. Assim, um clique não duplica
   o toast da query e não cria uma segunda mensagem genérica para a mesma falha.
   O POST mantém seu toast próprio, separado dos erros de leitura gerados pelas
   invalidações posteriores a um aceite bem-sucedido.
5. Preservar `operation.data ?? history.data?.data[0]` e os dados de histórico
   durante falhas de refetch. O toast sinaliza falha de comunicação, não substitui
   fase, resultado local ou evidência já persistida. Para uma operação ativa cujo
   primeiro GET falhou, usar a fase do item correspondente no histórico como base
   do intervalo de polling até existir `operation.data`; assim o GET continua
   tentando a cada 5 segundos e pode recuperar sem exigir clique. Fase terminal
   encerra o polling como antes. Não alterar endpoints nem o contrato do backend.

### Critérios focais para coder, tester e reviewer

- Falha inicial de cada um dos três GETs gera seu toast correto e localizado; a
  falha da operação é testada com histórico carregado e `update_id` ativo. Nenhum
  erro de GET aparece como texto inline ou substitui o estado da operação.
- Com timers controlados, vários ciclos de 5 segundos retornando erro para a
  mesma operação geram apenas um toast no episódio, inclusive após os retries
  internos; renders e troca de idioma não repetem a notificação. Um GET bem-sucedido
  rearma a notificação e uma falha posterior gera um novo toast.
- Um primeiro GET da operação que falha continua elegível a polling enquanto a
  fase do histórico estiver ativa; após recuperação, o detalhe atualizado aparece.
  Durante falhas de polling/refetch, a última operação e o histórico continuam
  visíveis com seus fatos persistidos.
- Falha de um ou mais GETs no refresh manual não produz `refreshFailed` além dos
  toasts específicos. Se a query já estiver no mesmo episódio de erro, o clique
  não repete o aviso; após sucesso intermediário, nova falha é avisada. Confirmar
  que rejeições de Promise do refresh são tratadas, sem erro não observado.
- A falha do POST continua produzindo somente seu toast de solicitação; um POST
  aceito não vira falha visual da operação quando uma invalidação de leitura falha.
  Confirmar a chave nova em en, pt-BR e ru e ausência de `onError` de query.

Esta reavaliação não amplia o escopo da Task 13, não aprova código nem altera o
ledger. A correção deve passar por nova revisão independente após os testes focais.
