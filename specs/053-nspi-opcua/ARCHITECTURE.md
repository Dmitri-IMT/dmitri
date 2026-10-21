# Arquitetura — OPC UA no NSPi

Architecture approved 2026-10-20, base `971ba8d`. Task 1 implementation is complete and reviewer-approved; Tasks 2–9 remain pending.
Escopo e aceite: [TRUTH.md](TRUTH.md). Caminhos e testes: [INTEGRATION.md](INTEGRATION.md).
Fontes internas consultadas: `docs/README.md`, ADR-018 e ADR-019; code-map usado apenas
para localizar o código. O código atual prevalece sobre descrições antigas.

## Decisão

Acrescentar OPC UA Binary sobre TCP ao estágio industrial existente. `nspi`,
`inventory` padrão e `read_only_mapping` continuam os únicos caminhos executáveis.
Manter Nmap/NSE e Modbus; nenhum modo, comando remoto ou campo de credencial novo.

Inventário executa `GetEndpoints` sem sessão. Mapeamento abre **uma sessão anônima
em endpoint que anuncia explicitamente SecurityPolicy None + MessageSecurityMode None
e token Anonymous**, no mesmo alvo. Endpoints Sign/SignAndEncrypt são inventariados;
v1 não estabelece suas sessões, pois não possui provisionamento de certificado de
cliente nem confiança configurada. Registrar `security_configuration_required`.
Não aceitar certificados automaticamente, gerar confiança implícita, usar uma cadeia
anunciada como âncora ou tentar segurança mais fraca depois de uma recusa.
Selecionar None anunciado é política explícita desta versão, registrada na evidência;
não representa validação da segurança de endpoints protegidos. Este recorte é uma
decisão proposta para aprovação junto com o plano.

## Cliente e fronteira de operações

Usar helper first-party .NET 10 com OPC Foundation UA-.NETStandard 2.0.1 (NuGet
fixado no projeto helper), exposto ao agente por IPC JSON fechado. O wrapper Python
não expõe cliente SDK, Node, nem valores UA. A fixture pode usar `asyncua==2.1.0`
somente como dependência de desenvolvimento. Preservar o aviso MIT da OPC Foundation
em `helper/LICENSE.txt`; o helper é compilado fora do runtime Python e seu
empacotamento/instalação é responsabilidade da Task 9.

Adaptador específico `ot/opcua/client.py`, sem registro genérico de plugins. Expor
somente descobrir endpoints, abrir/fechar sessão anônima, Browse/BrowseNext e Read
com parâmetros construídos pelo coletor. Não devolver Client/UaClient/Node ao estágio.
Bloquear no envio o conjunto de serviços que não está na allowlist: GetEndpoints,
Browse, BrowseNext, Read; infraestrutura HEL, OpenSecureChannel, CreateSession,
ActivateSession, CloseSession, CloseSecureChannel. Proibir Write, Call,
HistoryRead/HistoryUpdate, RegisterServer, Add/DeleteNodes/References, subscriptions,
monitored items e Publish. Contar os tipos realmente enviados, inclusive tentativa
bloqueada; nunca preencher contador de escrita com constante.

Preferir `UaClient` e serviços tipados, com ciclo de vida explícito, em vez de
`Client.connect()` e helpers que iniciam tarefas adicionais. O código da tag mostra
auto reconnect, renovação e health reads no cliente de alto nível; estes não devem
escapar de pacing, orçamento ou contagem. Não chamar carregamento de tipos,
modelos XML ou decodificadores definidos pelo dispositivo.

## Execução e limites iniciais

`ScanRunner` é síncrono e roda em worker thread. O adaptador executa uma coroutine
por serviço com `asyncio.run()` nessa thread; um controlador registra loop/task e
transport ativo. `request_cancel()` chama `loop.call_soon_threadsafe()` para cancelar
a task e abortar o transport, inclusive durante connect/Read/BrowseNext. Evento de
cancelamento vence deadline. Não usar o wrapper sync da biblioteca com outra thread
invisível. Liberar task, loop, socket e registro em `finally`.

Manter os tetos existentes: estágio industrial 600 s, host 90 s, ambos limitados
pelo prazo global. Modbus e OPC UA são sequenciais e compartilham esses relógios.
Fazer inventário dos dois protocolos antes de mapear; ordem determinística por
host, protocolo e porta. Acrescentar orçamento comum de 64 requisições por host,
com teto de 32 para cada protocolo em host dual. Modbus mapping conserva o teto
local existente de 32, incluindo suas sondas de inventário. Propagar o orçamento
comum até os pontos de envio Modbus, também no inventário. Uma falha preserva os
resultados do outro protocolo. Serviços não iniciados ganham cobertura `skipped`.

| Limite OPC UA | Valor inicial obrigatório |
|---|---|
| Portas candidatas ativamente inspecionadas por host | 4; excedentes com `service_limit` |
| Requisições enviadas por host | 32, **incluindo** HEL, canais, sessões e cleanup |
| Reserva de encerramento dentro das 32 | 4; nenhum novo trabalho ao restarem apenas 4 |
| Sessões de mapeamento | 1 por serviço; sem retry ou reconexão automática |
| Pacing entre todos os envios, incluindo lifecycle | >=100 ms; política local só pode aumentar |
| Timeout de conexão/operação | 2 s ou prazo restante, o menor |
| Cleanup normal | <=1 s dentro do prazo; após cancel/deadline abortar socket sem novos pedidos |
| Endpoints / tokens por endpoint | 16 / 8 |
| Profundidade / nós únicos / referências conservadas por serviço | 4 / 128 / 512 |
| Browse page / total de páginas por serviço | 32 referências solicitadas / 16 páginas |
| BrowseNext por nó / continuation points ativos | 4 / 1 |
| Read batch | <=16 atributos; <=8 operações Value por serviço |
| UA chunk / mensagem reconstituída / chunks | 64 KiB / 128 KiB / 16 |
| Bytes recebidos totais por serviço | 4 MiB, antes da decodificação |
| Texto / NodeId ou URI sanitizada / certificado recebido | 128 caracteres / 256 caracteres / 64 KiB |
| Observação serializada por serviço | 128 KiB; redução determinística de listas com motivo |

Requisição é um envio UA/Modbus de aplicação ou lifecycle, não pacote TCP. Contar
tentativa entregue ao transport mesmo quando a resposta falha; impedir envio antes
do limite. Guardar separados requests por tipo, bytes enviados/recebidos e chunks
UA; **não chamar estes números de pacotes de rede**. Nmap continua com sua própria
contabilidade; PCAP de laboratório mede pacotes reais. Cleanup consome reserva;
se faltar tempo ou orçamento, abortar conexão. Continuação liberada usa BrowseNext
com release quando há reserva, tempo e nenhum cancelamento.

Configurar limites do SDK antes do tráfego: MaxMessageSize=128 KiB,
MaxBufferSize=64 KiB, MaxChunkCount=16, arrays <=1024, textos/bytes limitados e
nesting <=8. Uma guarda no transporte valida o tamanho declarado e real de cada
frame, soma bytes e chunks por mensagem antes de entregar o chunk ao decoder; HEL
local anuncia exatamente 64/64/128 KiB e 16 chunks, e ACK remoto zero/unbounded ou
acima desses caps é rejeitado. O teste harness cobre 16/17 chunks, reset por
mensagem, ACK e `BinaryDecoder.ReadVariant` com limite de array antes da alocação.
GetEndpoints não pagina: resposta maior que 128 KiB gera `message_size_limit`, sem
elevar o limite automaticamente. Não registrar corpo binário ou valor de processo.

## Alvos, grafo e dados

Candidato: porta TCP aberta 4840 ou serviço Nmap OPC UA reconhecido em outra porta
já descoberta. Conectar somente no IPv4 numérico e porta descobertos. Primeiro
GetEndpoints usa `opc.tcp://<ip>:<port>/`; não descobrir peers pela rede.
URI anunciada é dado: permitir somente `opc.tcp`, mesmo IP literal e mesma porta,
sem userinfo, query ou fragment; não resolver DNS ou aceitar outro host/porta.
Pode usar caminho anunciado validado (<=256 caracteres), mantendo conexão fixa no
socket original. Se servidor só funciona com hostname alternativo, registrar
`endpoint_target_mismatch`; nenhuma expansão automática. DiscoveryUrls e certificados
jamais provocam HTTP/DNS/LDAP/OCSP/AIA ou download de arquivos.

Browse BFS inicia em Objects (`ns=0;i=85`), referências hierárquicas forward,
somente Object/Variable; visited por NodeId canônico, antes de enfileirar. Ignorar
ServerIndex !=0, ExpandedNodeId externo e referência de destino não local, com
`external_reference` e contagem. Não seguir links de servidores nem métodos.
Continuation point repetido, página sem avanço, resultado acima do solicitado,
referência duplicada ou ciclo têm parada determinística; não multiplicar filas.
Guardar nós, parent local e referências limitadas; NodeId é identificador local,
sem promessa de estabilidade entre scans. Identificadores binários opacos não são
exportados; registrar que o nó foi omitido.

Inventário conserva ApplicationUri, ProductUri, ApplicationName, ApplicationType,
endpoint URL sanitizada, política, modo, token types, security level anunciado e
somente SHA-256 do certificado DER (identificador, **não prova de confiança**).
Não persistir DER, subjects, tokens ou mensagens de exceção brutas. Identidade de
fabricante/versão pode vir apenas de metadados padronizados de Server/BuildInfo no
mapeamento, identificada como anunciada; não ler o ServerStatus inteiro.

Mapeamento lê atributos NodeClass, BrowseName, DisplayName, DataType, ValueRank,
AccessLevel/UserAccessLevel. Estes bits são **metadados declarados**, não teste de
leitura. Nomes também são conteúdo não confiável, limitado e escapado; seu texto
não prova que um nó é dado de processo, estático, não sensível ou autorizado.
Testar Value em até oito Variables de namespace de aplicação (ns>0), sem namespace arbitrário
fornecido pelo operador. Conservar somente resultado UA/StatusCode e instante da
tentativa; Good de Value comprova somente aquela leitura. Descartar imediatamente
Variant, conteúdo, comprimento, estatísticas e timestamps do processo. Nenhum valor,
digest ou derivado de Value vai a modelos, JSON, logs, banco, UI, relatório ou AI.
Read de metadados não comprova leitura de processo; haver zero Value elegíveis gera
`no_eligible_variables`, sem finding. Não criar digest OPC UA nesta entrega.

## Estado, cobertura e evidência

Serviço contém confirmação `suspected|confirmed`, inventário e mapeamento separados.
GetEndpointsResponse válido com conteúdo semanticamente válido confirma protocolo;
ACK/TCP, timeout, erro UA genérico ou banner não confirmam inventário. Uma resposta
vazia válida registra inventário vazio, sem inventar endpoints ou identidade.
Mapeamento usa `not_requested|completed|partial|denied|unsupported_security|failed|timed_out|skipped`;
razões limitadas incluem request/page/node/depth/byte/decode limits, cancelamento,
host/stage/global deadline, authentication_required, anonymous_denied,
security_configuration_required, endpoint_target_mismatch e external_reference.
`completed` significa terminou a amostra planejada dentro dos limites; nunca afirma
que o address space inteiro foi lido. Qualquer truncamento torna a fase `partial`.

Emitir CoverageUnitPayload por endpoint descoberto com `stage=ot_inspection`,
`port`, `protocol=tcp`, `tool=opcua`, `evidence_source=opcua_inspection` (novo enum).
Manter cobertura Modbus anterior; agregar pior estado para evidência do scan.
Sessão recusada tem inventário preservado e cobertura parcial, não `completed`.
Limite atingido não é erro fatal do scan; razão e partial seguem reconciliação atual.
`_record_not_run` deve reconhecer candidatos de ambos e evitar deduplicação apenas
por nome do estágio quando faltam serviços de um protocolo.

| Fato observado | Significado e efeito permitido |
|---|---|
| Porta 4840 aberta | Candidato; nenhum finding |
| None/Anonymous em GetEndpoints | Configuração **anunciada**, nunca acesso comprovado |
| ActivateSession anônima Good | Sessão aceita, sem inferir Browse ou Read |
| Browse Good | Navegação da parte observada, sem inferir Value |
| AccessLevel/UserAccessLevel readable | Permissão declarada; não confirma Read |
| Read Value Good nessa sessão | Leitura anônima daquele nó comprovada, sem afirmar escrita |
| BadUserAccessDenied, timeout, falta de certificado | Limitação; nenhum resultado negativo global |
| ProductUri/BuildInfo | Identidade anunciada; nenhuma CVE confirmada |

**V1 acrescenta observações, sem novo finding OPC UA ou severidade.** Good de Value
em ns>0 demonstra capacidade de leitura anônima da amostra, não que o conteúdo era
processo sensível, que o acesso foi indevido ou que houve bypass de autenticação.
Read de ns=0/BuildInfo é metadado do servidor e nunca entra nessa contagem.
Conservar fatos tipados por endpoint `anonymous_session_activated`,
`browse_succeeded`, `application_value_read_succeeded`, `value_good_count`,
`security_mode` e `security_policy` com procedência e status UA; nunca derivar
esses fatos de AccessLevel, token anunciado, nomes ou texto de erro.
`services/scan_evidence.py` não recebe regra positiva UA nesta entrega: anúncio e
capacidade continuam observações sem CVE. Os findings Modbus/NSE existentes passam
pelo mesmo gate atual. Correlação NVD existente não deve promover identidade UA a
CVE confirmada; nenhum novo catálogo de fingerprints OPC UA é necessário.

## Contrato e persistência

`industrial_services` vira união por `protocol`: membro Modbus existente preservado;
novo `OpcUaTcpServicePayload` (`protocol=opcua_tcp`, port, confidence,
evidence_sources, write_requests_sent medido, `observation`). A observação versionada
(`schema_version=1`) contém identity, endpoints[], selected_endpoint_index opcional,
session/browse/value-read estados, nodes[], references[], phase coverage e contadores.
Cada fase tem `status`, `reason_codes[]`, `truncated` e `observed_at`; inventário
usa completed/partial/failed/timed_out/skipped, mapeamento usa os estados acima.
Session/browse/read facts começam null (não testado); false somente após tentativa
com resultado válido negativo, nunca após timeout. Endpoints não selecionados não
ganham resultado de acesso. Nós guardam somente atributos permitidos e status de Value. Modelos UA têm
`extra=forbid`, enums fechados, mesmos limites no agente/backend/OpenAPI.

Conservar `IndustrialServiceView` como componente Modbus atual. Novo
`OpcUaServiceView` conserva campos comuns e `observation` **required nullable**;
o array de leitura usa novo `IndustrialServiceRead` oneOf dos dois. JSON inválido
armazenado degrada somente observation para null e acrescenta unreadable_fields;
não reclassificar como Modbus nem apagar outros serviços. OPC UA ausente em scan
antigo significa desconhecido. Ingest legado que omite protocol no membro Modbus
continua aceito por normalização restrita à forma Modbus antes de discriminar;
outros membros sem protocol são inválidos.

Reutilizar `industrial_services`, unique `(scan_host_id,protocol,port)`. Adicionar
`opcua_observation_json` nullable JSON; ampliar check protocol para modbus_tcp e
opcua_tcp; JSON UA só permitido em membro UA. Evitar tabela genérica de nós para
amostra limitada sem consultas globais. Modbus units/findings e retornos de mapas
de Unit IDs continuam exclusivos de Modbus. Persistência faz upsert por protocolo,
sem percorrer `.units` de UA; leitura valida JSON tipado com degradação existente.
Exclusão de scans/hosts remove o JSON junto da linha industrial, sem nova FK.

Grafo real Alembic verificado: `20261018_42` junta `20261010_40`, `20261012_40`,
`20261017_41`; `20261019_43` depende desse merge e é head único observado.
Nome proposto: `20261020_44_opcua_observations.py`, revision `20261020_44`,
down_revision `20261019_43`. Revalidar head antes de implementar; code-map que cita
`20261012_40` está desatualizado. Downgrade deve recusar dados UA existentes ou
exigir limpeza explícita; não apagar evidência silenciosamente.

Todo consumidor de `industrial_services` deve fazer dispatch antes de acessar
`.units`: normalização/findings, fingerprints, profile, exposure, TUI, persistência,
read e web. Profile pode conservar identidade UA como autodeclaração limitada;
não usar para ampliar sondas. Exposure precisa dizer “OPC UA”, pois hoje seu texto
de protocolo industrial é fixo em Modbus. Modbus mantém labels, unidades, ranges,
digest e findings existentes.

O front é a interface prioritária, conforme orientação do usuário em 2026-10-20.
Na TUI, fazer somente guardas/dispatch necessários para dados UA não serem tratados
como Modbus, preservar execução/cancelamento e manter texto existente correto.
Omitir detalhes UA ainda não suportados é permitido; não apresentar ausência de
detalhes como ausência de serviço. Novos painéis, tabelas de nós e resumos TUI ficam
adiados e não são requisito de conclusão desta feature.

## Entrega e pendências verificáveis

Publicar contrato/backend antes de agentes que enviam UA; frontend com dispatch
de ambos antes de habilitar novos resultados. Backend antigo não aceita UA, portanto
compatibilidade é com payload/scan antigo, não promessa de aceitar novo payload em
servidor antigo. JSON técnico carrega detalhe tipado; PDF explicado ganha resumo
industrial por protocolo e limitações, sem despejar grafo. AI recebe apenas contagens
e estados agregados, sem URLs, NodeIds, labels ou strings do equipamento.

Os testes focais atuais exercitam o helper e o wrapper com fixture OPC UA loopback;
o oversized GetEndpoints comprova rejeição pré-decode após tráfego >128 KiB recebido.
Build/test foram validados localmente em Windows; ainda não foi validado build,
empacotamento ou execução Linux ARM64, nem servidor PLC real. A fixture não substitui
essa validação.
