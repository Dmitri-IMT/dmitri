# Plano de execução — OPC UA no NSPi

Status: Tasks 1–4, M1 and M2 complete and reviewer-approved. Python migration is complete.
The latest user instruction requires a new command before starting Task 5.
Sequence is M1 → M2 → user command → 5 → 6 → 7 → 8 → 9.
Completed task numbers and review history are retained.
Branch/base: `feature/nspi-scan-opcua`, `971ba8d`.

## Active Python migration

`PYTHON_MIGRATION.md` governs M1/M2 and supersedes the .NET SDK choice and stale
approval/status text in the historical planning record below. Use pinned runtime
`asyncua==2.1.0` in an isolated Python subprocess, worker-only bounded decoder
patches and a raw socket writer with actual-send accounting. Preserve all Task 1–4
security/functionality and the current uncommitted Task 4 changes.

| Task | Deliverable | Dependency | Gate |
|---|---|---|---|
| M1 | Stable decoder/transport guards and worker GetEndpoints, tested directly | Task 4 history | Real pinned decoder pre-allocation paths, HEL/ACK, allowlist, actual sends, budgets, pacing, cancellation and fixture isolation |
| M2 | Port complete anonymous mapping, switch facade to Python, remove .NET sources/build/test paths | M1 | Full existing client/mapping/stage parity, wire observations, metadata-only output, DMITRI identity and Modbus regression |
| 5 | Existing backend persistence/ingest/read scope | M2 | Live `dmitri_test`, migrations, compatibility, idempotence and org isolation |

Exact target files and acceptance criteria are in `TASKS.md`. No throwaway client
or temporary .NET fallback. Task 9 retains Linux ARM64/offline package validation;
runtime pin/lock and .NET removal belong to migration now. Each migration unit uses
Python coder/test engineer and critical transport reviewer under the existing
sequential harness. M1/M2 review gates passed; Task 5 waits for a new user command.

## Historical planning record

The remaining sections record the original nine-task planning and SDK assessment.
Their .NET implementation choice, "pending user command" statements and Task 1
preparation instructions are superseded by the active migration above.

## Resultado e decisões propostas

OPC UA participa do scan NSPi junto com Modbus. `inventory` descobre o servidor e
suas configurações anunciadas; `read_only_mapping` acrescenta navegação e verificação
de leitura anônima limitadas. O fluxo atual leva os resultados ao histórico, detalhes
do equipamento no front, exportações e relatórios.

Prioridade definida pelo usuário em 2026-10-20: o front é a interface principal.
A TUI teve função provisória pré-front. Nesta entrega, ela recebe apenas ajustes
de compatibilidade necessários para continuar usando o motor compartilhado sem
exceções, interpretação errada de protocolo ou exposição de dados. Detalhes de nós,
novos resumos e melhorias visuais da TUI ficam adiados e não bloqueiam a feature.

As informações OPC UA entram como observações de capacidade e cobertura. Acesso
anônimo permitido, isoladamente, não demonstra acesso indevido. Esta entrega não
cria findings ou severidades OPC UA; preserva os findings Modbus/NSE existentes.

A primeira entrega não inclui gerenciamento de credenciais ou certificados de cliente.
Servidores que exigem essa preparação conservam o inventário disponível e apresentam
o motivo da cobertura limitada. Esse recorte precisa fazer parte da aprovação do plano.
Não interpretar esse estado como ausência de vulnerabilidade.

`TRUTH.md` define o comportamento. `ARCHITECTURE.md` e `INTEGRATION.md` fecham as
decisões técnicas e os caminhos. `DESIGN.md` especifica a apresentação.
`PROMPTS.md` define os pacotes de contexto, papéis, evidências e gates.

## Distribuição de modelos

Os identificadores abaixo vêm dos perfis existentes em `.codex/agents/`. A seleção
precisa constar na ferramenta de criação do agente; escrever o nome no prompt não
seleciona modelo. Nenhuma estimativa de preço ou economia percentual foi presumida.

| Papel | Modelo / esforço | Uso |
|---|---|---|
| Orquestração de desenvolvimento | `gpt-6.1-sol` / medium | Controlar dependências, contexto, handoffs e critérios. |
| Arquitetura | `gpt-6.1-sol` / high | Uma proposta compartilhada de protocolo, limites e integração. |
| Implementação | `gpt-6-luna` / medium | Uma tarefa delimitada por vez. |
| Testes Python e web | `gpt-6-luna` / medium | Verificar comportamento e fortalecer casos de falha. |
| Revisão usual | `gpt-6.1-sol` / medium | Contratos, persistência, apresentação e regressões. |
| Revisão crítica | `gpt-6.1-sol` / high | Transporte, leitura exclusiva, cancelamento e política de evidência. |
| Design e documentação | `gpt-6-luna` / medium | Fluxos e documentação com decisões técnicas já definidas. |

Luna é a primeira escolha de execução. Uma troca de modelo exige motivo concreto
registrado: tarefa sem decisão suficiente, falha repetida ou indisponibilidade real.
Antes de elevar esforço, reduzir o contexto e fechar a dúvida. Não repetir chamadas
falhas por quota nem substituir silenciosamente pelo modelo mais caro.

## Sequência de desenvolvimento proposta

Esta é a decomposição para revisão do plano. A skill `feature-planning` reserva
`TASKS.md` à fase seguinte, após aprovação das specs. Ao receber o comando para
implementar, `create-tasks` deve materializar este recorte com caminhos exatos do
manifesto arquitetural, testes, critérios, dependências e contadores de rejeição.

| # | Entrega verificável | Dependências | Coder / tester | Reviewer | Critérios |
|---|---|---|---|---|---|
| 1 | Cliente UA limitado e modelos internos, dependência fixada, guardas de transporte/decode e laboratório local mínimo. | Specs aprovadas | Luna medium | Sol 6.1 high | A02, A07–A10, A14, A16 |
| 2 | Inventário de endpoints e contrato aditivo agente/backend; identidade anunciada, segurança e compatibilidade Modbus. | 1 | Luna medium | Sol 6.1 medium | A01–A03, A06, A08, A13–A14 |
| 3 | Sessão anônima e mapeamento por navegação/leitura; ciclos, paginação, recusas e privacidade. | 2 | Luna medium | Sol 6.1 high | A04–A10, A14 |
| 4 | Integração na etapa industrial, cobertura, progresso, cancelamento e caminhos CLI/TUI/daemon. | 3 | Luna medium | Sol 6.1 high | A01, A10–A11, A15 |
| 5 | Persistência por scan, ingestão idempotente, leitura por organização e compatibilidade histórica. | 1, 4 | Luna medium | Sol 6.1 medium | A03, A11–A14 |
| 6 | Apresentação web, localização e distinção dos protocolos nos componentes existentes. | 4–5 | Luna medium | Sol 6.1 medium | A03–A06, A09–A14 |
| 7 | Relatórios, exportações e contexto de IA com cobertura e sem valores de processo. | 5–6 | Luna medium | Sol 6.1 medium | A11–A14 |
| 8 | Matriz integrada de evidência/falhas, auditoria das operações enviadas, regressão Modbus e contratos de ponta a ponta. | 2–7 | Luna medium | Sol 6.1 high | A01–A16 |
| 9 | Gates finais por camada, dependências/pacote Linux ARM64, documentação e checklist de validação real. | 8 | Luna medium | Sol 6.1 medium | A13–A16 |

Cada entrega inclui testes e revisão antes da próxima. O laboratório começa na tarefa 1;
a tarefa 8 amplia sua matriz e verifica o conjunto. São nove tarefas prioritárias.
Compatibilidade mínima da TUI integra a tarefa 4; apresentação detalhada na TUI fica
como melhoria futura, sem tarefa de implementação ou ciclo de agentes nesta entrega.

A tarefa 1 é o gate de viabilidade da dependência proposta: comprovar guardas antes
da alocação/decodificação, bloqueio no envio e cancelamento real. Se a adaptação exigir
fork ou parser próprio amplo, rever a arquitetura antes de investir nas outras tarefas.
Não criar cliente provisório sem os limites. Evidência sem finding novo é verificada
nas tarefas 4/5 e consolidada na 8; não exige um ciclo de desenvolvimento separado.

## Preparação da Task 1

Pacote preparado em 2026-10-20 para iniciar após aprovação explícita das specs:

- **Meta:** demonstrar que o cliente OPC UA consegue limitar tamanho recebido antes
  de alocar/decodificar, aplicar allowlist no envio, impor pacing/orçamento, cancelar
  I/O e fechar transporte. Implementar somente os modelos internos que sustentam esse
  contrato e o servidor de laboratório loopback. Não iniciar inventário, navegação,
  ingestão ou UI nesta tarefa.
- **Arquivos de produção:** novos
  `hardware-agent/src/agent/ot/opcua/{__init__.py,models.py,client.py}`;
  helper .NET em `hardware-agent/src/agent/ot/opcua/helper/` com OPC Foundation
  UA-.NETStandard 2.0.1 e aviso MIT. O pin `asyncua==2.1.0` é apenas dependência de
  desenvolvimento da fixture; não é cliente de produção.
- **Harness permitido:** novos
  `hardware-agent/tests/fixtures/opcua_lab.py` e
  `hardware-agent/tests/unit/test_opcua_client.py` e
  `hardware-agent/tests/dotnet/opcua-bridge.tests/`. Apenas testes, bind loopback,
  porta efêmera; nenhum listener/runtime em `src/agent/`.
- **Critérios de saída:** A07 (serviços UA permitidos e bloqueio de mutações), A09
  (limites efetivos e cancelamento), A14 (entrada limitada/saneada e sem segredos),
  A16 (evidência de solicitações efetivamente recebidas pelo harness). Gates de
  egress e testes Modbus continuam passando.
- **Dependências de execução:** o agente declara `Python >=3.11,<3.13`; validar pin e
  lock com a toolchain local, depois import e protocolo nos Python suportados. O
  smoke ARM64 completo fica na Task 9.
- **Desenho:** coder `gpt-6-luna` medium → test engineer `gpt-6-luna` medium → reviewer
  `gpt-6.1-sol` high, um por vez, com os perfis e seleção reais do harness.
- **Checks focais:** `uv run pytest tests/unit/test_opcua_client.py
  tests/unit/test_opcua_untrusted.py tests/unit/test_egress_only.py` e
  `uv run ruff check src/agent/ot/opcua tests/unit/test_opcua_client.py
  tests/unit/test_opcua_untrusted.py`, executados de `hardware-agent/`. O reviewer
  repete checks focais e cobre tráfego/limites; não marca a tarefa aprovada se o gate
  de pré-decode ou cancelamento real não estiver provado.
- **Tempo de referência:** 45–90 minutos para coder, tester e revisão, conforme a
  estimativa atual. O limite superior é incerto até provar os hooks de framing/decode
  SDK escolhido UA-.NETStandard; limites de decode e framing usam APIs upstream
  comprovadas, sem fork ou parser paralelo.

Este pacote não é um ledger de execução nem uma autorização de implementação.
`TASKS.md` será criado pela skill `create-tasks` quando a etapa de specs for aprovada.

## Harness de execução e economia de contexto

- Uma tarefa por vez: coder → tester → reviewer. Respeitar as skills e perfis já
  existentes. Reaproveitar o harness do repositório, sem criar outro framework de agentes.
- Contexto novo por papel (`fork_turns="none"`), com diretório, base, task, critérios,
  arquivos permitidos, skills necessárias e handoff curto. Não enviar o histórico do chat.
- Coder e tester usam Luna. Reviewer recebe diff, critérios e evidências; não precisa
  repetir buscas exploratórias ou ler todas as specs de features anteriores.
- O orquestrador mantém o ledger e as decisões; não implementa nem aprova o próprio código.
- Registrar modelo efetivo, esforço, resultado, arquivos e comandos de cada ciclo.
  Capturar métricas de uso somente se a ferramenta as disponibilizar.
- Usar testes focais por entrega. Rodar os gates completos quando a camada estiver
  integrada e repetir somente se houver mudança ou risco concreto restante.
- Handoff de até 12 linhas; logs completos ficam em artefatos locais, fora de specs.
- Rejeição exige motivo com arquivo/linha e critério. Novo coder recebe o feedback;
  repetição do mesmo motivo pela segunda vez exige revisar a decisão antes de insistir.
  Quarta rejeição segue a reavaliação estrutural da skill de orquestração.
- Encerrar a execução do worker após o handoff. O cliente atual expõe estado final de
  subagente, sem ferramenta explícita para apagar threads. Não simular fechamento;
  verificar os slots disponíveis antes de cada criação. Se necessário, usar sessão
  efêmera sequencial com término verificável.

## Harness de validação

1. Testes determinísticos sem rede: política, limites, seleção de endpoint, estados,
   normalização, evidência, escape e contratos antigos/novos.
2. Servidor OPC UA de laboratório em loopback e porta efêmera: discovery, sessão,
   browse/read, recusas, timeout, cancelamento e contagem real dos serviços recebidos.
3. Servidor/peer controlado para violações de protocolo e limites: respostas grandes,
   páginas repetidas, referências externas e encerramento incompleto de conexão.
4. Integração do coletor real até JSON/ingest/PostgreSQL/leitura web/relatórios, com
   alvos Modbus e OPC UA na mesma execução e regressão dos consumidores legados.
5. Smoke do pacote ARM64, importações e dependências. Laboratório comprovado não
   deve ser apresentado como compatibilidade já validada com PLC comercial.

Os testes inspecionam requisições efetivamente recebidas pelo servidor. Nenhum `Write`,
`Call`, operação de mutação ou subscription pode atravessar o transporte. O ciclo de
canal/sessão é permitido e deve ser encerrado com prazo e contadores definidos.

O target é fixture de testes; não faz parte do runtime e não abre listener na appliance.
O `compose.nspi.yaml` atual se conecta ao backend configurado pelo operador; não deve
ser usado como substituto de um laboratório isolado. Docker adicional só é necessário
para um cenário que a fixture local e o harness existente não consigam comprovar.

## Execution status and next steps

Historical planning checkpoint (2026-10-20): implementation began after approval and the first review requested three fixes. The fixes passed the second independent test pass and reviewer approval. No commit, push, publication, or deployment is part of this task.

The initial asyncua assessment blocked on framing/decode limits. The later architecture decision selected OPC Foundation UA-.NETStandard with a .NET helper. Task 1 passed implementation, independent testing, and final review; only ARM64 packaging/real-device validation remain in Task 9.

### Resultado da avaliação de SDK alternativo (2026-10-20)

`o6\Python` (baseado em open62541) é o candidato mais próximo encontrado: a distribuição
PyPI documenta limites configuráveis de buffer/mensagem/chunks, Python 3.11+, wheels
Linux ARM64 e suporte sync/async. Porém, a wheel comercial opera em Script Mode por
10 minutos sem credencial; o código-fonte disponível separadamente é AGPL-3.0, enquanto
o Dmitri está sob MIT. Isso exige avaliação de licença antes de adoção. A wrapper
Python inspecionada expõe `localMaxMessageSize` e `localMaxChunkCount`, mas não uma
opção de decoder por cliente para impor 1.024 elementos antes de alocar. O decoder
open62541 limita arrays pela relação com os bytes restantes e depois aloca, limite que
não equivale ao teto rígido da spec. Portanto, o candidato ainda não passa o gate.

Historical o6 assessment: no production code was changed at that checkpoint. o6 was not selected; current implementation uses the .NET SDK.

### Avaliação do OPC Foundation UA-.NETStandard 2.0.1 (2026-10-20)

Este é o primeiro candidato com evidência de código para as guardas de decode:
`BinaryDecoder.ReadArrayLength` aplica `MaxArrayLength` antes da alocação e compara
comprimentos mínimos com os bytes restantes; `ReadString`/`ReadByteString` aplicam
suas quotas antes de alocar; nesting é contado. `TcpByteTransport.ReceiveChunkAsync`
lê o cabeçalho de 8 bytes e recusa tamanho acima do buffer antes de reservar o corpo.
A correção upstream #3910 está merged e limita arrays de operações aos quotas
efetivos. A biblioteca é publicada sob licença MIT da OPC Foundation e a versão 2.0.1
oferece alvos .NET 8, 9 e 10.

Prova temporária fora do repositório: restore do pacote NuGet 2.0.1 e publicação
self-contained `linux-arm64` concluíram com SDK 10.0.402; os arquivos totalizaram
aprox. 111 MB. A publicação NativeAOT cross-OS a partir de Windows falhou como
esperado; deve ser validada num runner Linux ARM64. Isso confirma possibilidade de
build self-contained, mas o tamanho ainda é alto e o executável não foi testado no Pi.

A Task 1 usa helper first-party .NET 10 com OPC Foundation UA-.NETStandard 2.0.1,
canal `ITransportChannel` allowlisted, IPC JSON fechado e fixture asyncua apenas em
loopback/porta efêmera. `EndpointConfiguration.Create()` fornece defaults válidos
de token; o smoke real conclui GetEndpoints com status Good e o fixture observa o
serviço efetivamente recebido. HEL anuncia exatamente ReceiveBuffer=64 KiB,
SendBuffer=64 KiB, MaxMessageSize=128 KiB e MaxChunkCount=16. ACK zero/unbounded ou
acima dos limites locais é rejeitado. A guarda conta bytes de frame incluindo header,
acumula por mensagem e rejeita chunks antes do decoder; há teste direto de 16/17
chunks, reset entre mensagens e limite de array no `BinaryDecoder` do SDK antes da
alocação. O fixture oversized entrega >128 KiB e a resposta é classificada como
`message_size_limit`, sem elevar os limites.

The wrapper and helper implement timeout/cancellation, service allowlist, blocked-attempt accounting, sanitized closed IPC, and no process values. Independent second pass passed the helper harness, .NET build (0 warnings/errors), Ruff, diff-check, and pytest 6/6. Reviewer final gate repeated 21 Python tests plus harness/Ruff/diff-check and approved. The helper apphost ran from Temp because WDAC blocks execution from OneDrive.
Packaging/runtime and Linux ARM64 validation belong to Task 9; no real PLC was validated. Task 1 is complete. Do not start Tasks 2-9 until the user gives the next command.

Reviewer rework findings: pass the bounded deadline token to CloseAsync and abort without CLO if it has expired; reject endpoint URL userinfo/query/fragment and off-target targets before IPC, preserve only same-target simple paths up to 256 chars; serialize JSON property names as snake_case to match the Python wrapper. Regression coverage is in the .NET guard harness and Python fixture test.
Rework verification and approval: .NET harness/build passed with 0 warnings/errors, independent pytest passed 6/6, Ruff and `git diff --check` passed; final reviewer repeated 21 Python tests and approved. The integration test uses the updated apphost published outside OneDrive because WDAC blocks helper execution from the workspace. ARM64 and real PLC validation remain in Task 9.
