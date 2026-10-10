# INTEGRATION — Contrato e consumidores da evidência

Status: proposta para aprovação. Entrega A, 2026-10-10. Complementa `ARCHITECTURE.md` e
`DESIGN.md`; todos os nomes abaixo são decisões propostas para implementação posterior.

## Contrato aditivo

`contracts/openapi/openapi.yaml` continua fonte única. Backend espelha em Pydantic;
agente espelha o payload e limites; frontend gera tipos. Não adicionar `confidence` ao
ingest: esse campo continua calculado pelo backend. Modelos novos usam `extra="forbid"`.
Não flexibilizar o ingest antigo para aceitar campos arbitrários. [A10, A15]

### FindingEvidenceObservationPayload

Mesma estrutura nas observações de finding e nas observações sem finding do scan.

| Campo | Tipo/limite | Significado |
|---|---|---|
| `ip` | IPv4 ou null | Alvo observado; null só para registro de alcance global, que não confirma endpoint. |
| `port` | inteiro 1–65535 ou null | null preserva alcance host; não significa todas as portas. |
| `protocol` | tcp/udp ou null | Deve corresponder ao endpoint quando presente. |
| `unit_id` | inteiro 0–255 ou null | Unidade Modbus, sem propagar a outras unidades. |
| `condition_key` | string 1–256 | CVE canônica para verificação dessa CVE; `issue_key` existente para configuração/condição. |
| `method` | version_correlation/configuration_observation/specific_check/textual_reference/unknown | Forma de obtenção do registro; backend valida seu significado. |
| `result` | positive/negative/inconclusive | Resultado sobre a condição; positive de correlação significa associação, não falha no alvo. |
| `source` | string 1–64 | Produtor original; rótulo não autoriza confirmação. |
| `source_script` | string 1–64 ou null | Script/ferramenta original. |
| `rule_id` | string 1–128 | Regra de interpretação; exemplo `nse:smb-vuln-ms17-010`. |
| `rule_version` | string 1–64 | Versão dessa regra; versão desconhecida não confirma. |
| `evidence` | string 1–512 | Excerto sanitizado da observação; texto completo já existente conserva seu papel. |
| `facts` | objeto até 8 campos | Valores string até160 caracteres, inteiro ou booleano; chave até64. Sem objetos/listas aninhadas, floats, segredos ou blob arbitrário. |

`facts` tem chaves fechadas **por regra suportada**. O backend valida combinação de
method/result/condition_key/endpoint e fatos antes de confirmar. Uma regra desconhecida
pode conservar fatos limitados para revisão, com classificação inconclusiva; não obtém o
predicado de uma regra conhecida pelo simples uso do mesmo nome. String/fato fora dos
limites é rejeitado no ingest; produtor faz sanitização determinística antes da construção.
Truncamento semântico de fatos obrigatórios impede confirmação.

Predicados mínimos: correlação requer CVE e identidade/CPE observada; SMB signing exige
valor de signing observado; SMBv1 exige dialect observado; SSH/métodos HTTP/certificado/cifra
exigem primitive/configuration e valor correspondente; login/sessão/leitura exigem resultado
de resposta e escopo; MS17 exige estado estruturado positivo, CVE esperada e tabela/endpoint
do script. O corpus enumera os fatos aceitos por cada regra existente. Não aceitar título
ou referência CVE como substituto de resposta. Um registro de configuração com CVE associada
continua condição de configuração. [A04–A07]

Atualidade da observação é o timestamp do scan que a contém. Não adicionar data inventada,
não usar horário do job NVD como horário de observação e não transmitir uma porcentagem de
confiança. Escopo desconhecido é explícito, não curinga para reconciliar outro endpoint.

### Campos adicionados ao ingest/agente

| Modelo | Campo | Default/limite |
|---|---|---|
| `FindingPayload` | `evidence_observations` | lista vazia, máximo16; normalmente positivos e conflitos associados à finding |
| `FindingPayload` | `evidence_truncated` | false; limita a confiança quando perde testemunhas/fatos necessários |
| `ScanPayload` / `ScanIngestRequest` | `finding_evidence_policy_version` | string 1–64 ou null; versão inicial `1`; independente de assessment_policy_version |
| mesmos | `finding_observations` | lista vazia, máximo512; negativos/inconclusivos sem achado positivo correspondente |
| mesmos | `finding_observations_truncated` | false; lista é amostra limitada quando true, não total de verificações |

Versão null + listas vazias + flags false é legado. Versão null com metadados novos é
rejeitada por incoerência; versão futura pode ser armazenada dentro dos limites como
inconclusiva, sem promoção por regras da versão1. Agente atual produz versão1 também
quando não encontra achados. Endpoints de observações associadas devem corresponder ao
registro de finding; standalone deve pertencer ao scan/host e não se declarar positivo.
Observações podem conter mais de uma condição somente como registros separados.

Não renomear `evidence`, `source`, `source_script`, `references`, `coverage` nem
`assessment_policy_version`. Não mudar `CoverageObservationPayload` para alojar negativos
de CVE; seus tipos de superfície/identidade têm outro significado. Não exigir metadados
novos dos exemplos e arquivos históricos. [A01–A03, A10, A15]

Limites são de **observações distintas após deduplicação**, não de fontes ou chances de
confirmação. Produtor seleciona testemunhas de qualidade/conflito antes de cortar e marca
a flag. Backend rejeita payload acima do limite e aplica a mesma regra ao merge, com flag
monotônica; não descarta excedentes silenciosamente. A amostra standalone nunca prova
ausência de condições omitidas. Esses limites não truncam a lista de findings existente.

### Leitura

`FindingRead` no backend / `FindingRecord` no OpenAPI frontend acrescenta. Os nomes
`FindingListResponse` e `ScanDetailResponse` são iguais no OpenAPI e no backend:

| Campo | Tipo/default | Uso |
|---|---|---|
| `detection_method` | cinco valores de method; unknown no legado sem associação conhecida | Método da melhor observação validada; todas as outras permanecem na procedência. |
| `evidence_status` | supported/inconclusive/conflicting/unknown | supported significa suporte para o método limitado, inclusive associação de catálogo. |
| `evidence_observations` | lista, máximo16 | Observações positivas e negativas/inconclusivas comparáveis consolidadas. |
| `evidence_truncated` | boolean false | Limite visível, sem certeza fabricada. |

`confidence` continua tentative/probable/confirmed/null. A leitura usa o valor persistido na
finding, não depende de snapshot de risco existir. Histórico conserva o valor armazenado,
com estado unknown e aviso de procedência ausente; não é contado como condição demonstrada.
Correlação histórica identificável tem método version_correlation, mas estado unknown sem
observações estruturadas. `source_labels_json` continua armazenando a união; sua existência
não fabrica observações nem é requisito para promoção. [A04, A08, A10, A12]

`ScanDetailResponse` acrescenta finding_evidence_policy_version, finding_observations e
finding_observations_truncated, além de evidence_summary. `FindingListResponse` acrescenta
evidence_summary. Nas leituras, campos novos são aditivos e têm defaults para fixtures e
registros antigos; contrato de resposta documenta o que a API atual sempre emite.

### FindingEvidenceSummary

| Campo | Tipo | Definição |
|---|---|---|
| `scope` | scan/filtered_findings | ScanDetail usa scan; GET findings usa conjunto filtrado. |
| `total_records` | inteiro ≥0 | Quantidade de registros consolidados de findings no escopo. |
| `by_method` | objeto fechado com os cinco métodos, inteiros ≥0 | Cada registro entra uma vez no método principal; soma = total_records. |
| `by_confidence` | objeto tentative/probable/confirmed/unknown, inteiros ≥0 | Valores armazenados; null entra em unknown; soma = total_records. |
| `conflicting_records` | inteiro ≥0 | Registros evidence_status=conflicting. |
| `demonstrated_records` | inteiro ≥0 | Registros com observação positiva de configuração ou teste específico suportado, sem conflito/truncamento impeditivo. |

Histórico com confidence=confirmed e procedência ausente pode entrar nesse bucket de confiança
armazenada, mas nunca em demonstrated_records. Configuração demonstrada não equivale a CVE
explorada. Não chamar confirmed bucket de quantidade de falhas comprovadas. [A10, A13]

Summary de GET findings usa exatamente os filtros org/host/scan/severity aplicados ao
`total` existente, **antes** de offset/limit. HostFindings deve usar esse resumo mesmo que
só carregue a primeira página; seu escopo contém os registros históricos retornados por
essa API, sem deduplicar scans em silêncio. ScanDetail usa todas as findings embutidas.
Home continua contando itens de atenção/revisão e suas páginas; cada finding serializada
recebe a mesma política, sem reinterpretar review_count como vulnerabilidades confirmadas.
ScanSummary.finding_count e HostSummary.vulnerability_count mantêm seu significado atual de
registros/inventário aberto, rotulado de modo correspondente. Sem novo endpoint de métricas.

Standalone negativo/inconclusivo é apresentado na área de evidência/cobertura e no relatório,
fora dos registros positivos. Não entra em total_records/finding_count/demonstrated_records.
Sua lista limitada também não substitui incomplete_check_count nem o total de unidades da
cobertura. Resposta vazia com cobertura desconhecida não indica alvo seguro. [A07, A11–A13]

## Persistência e migração

Uma revisão nova: `20261010_40_finding_evidence_quality.py`, revision `20261010_40`,
down_revision `20261002_39`. Revalidar head antes de implementar para evitar bifurcação.

| Tabela/modelo | Colunas novas |
|---|---|
| `findings` / FindingRecord | `finding_evidence_policy_version` nullable string64; `evidence_observations_json` nullable JSON; `evidence_truncated` boolean não null default false |
| `scans` / ScanRecord | `finding_evidence_policy_version` nullable string64; `finding_observations_json` nullable JSON; `finding_observations_truncated` boolean não null default false |

Null no JSON de observações marca informação nunca registrada; lista vazia com versão1 marca
resultado novo sem observação. Não criar tabelas, índices de busca, enum SQL ou novo registro
de decisão manual. Enums de confiança atuais permanecem. Alterações JSON preservam isolamento,
grants e RLS das tabelas existentes. Downgrade remove somente campos novos; não pode restaurar
certeza antiga indevida nem fabricar dados descartados.

Migração de dados é restrita: fontes conhecidas de correlação indevidamente confirmadas são
rebaixadas a probable (inclui alias nvd_enrichment) e snapshots correspondentes recalculados
pela fórmula existente. Não promover histórico, não fabricar fatos nem inferir regra pela
evidência textual. Preservar descrição/evidência original e histórico de primeira/última
observação. Teste cobre alias, snapshot ausente e registro histórico sem fonte conhecida.

`upsert_finding` recebe o conjunto de observações relevante, inclusive negativos do mesmo
scan/condição/endpoint. Merge une antes de reduzir; ingest processa o lote de modo que a
posição de standalone no payload não altera o resultado. `_process_cpe_job` acrescenta
correlação estruturada; `_process_cve_job` acrescenta dados públicos e mantém a evidência
observada. `refresh_risk_snapshot` usa a confiança final; nenhuma alteração na fórmula ou
estimativa de risco pela quantidade de fontes. [A08–A10]

## Integração real do produtor

| Entrada | Caminho atual | Integração |
|---|---|---|
| CLI | cli.py → headless.run_headless_scan → ScanRunner | `_build_payload` normaliza uma vez; JSON e submit levam o mesmo corpo. |
| Daemon | daemon.py, run_scan default run_headless_scan → ScanRunner | Mesmas observações, cancelamento e partials; jobs remotos não criam interpretação separada. |
| TUI | ScanProgressScreen → ScanRunner; ScanView/DeviceDetail consomem ScanPayload | Mesma normalização; past scans sem versão seguem legíveis. |
| Targeted | TargetedUnitResult/TargetedIssue → normalize/findings.py | Método/fatos por issue; sucesso da unidade não confirma todos os registros. |
| OT | Industrial services/address_ranges → extrator Modbus existente | Só respostas readable reais, unidade correta; protocolo identificado não confirma CVE. |

`extract_findings` conserva a responsabilidade e o retorno existentes. Acrescentar coletor
opcional de observações sem finding como parâmetro interno nomeado, passado apenas por
`ScanRunner._build_payload`; extratores preservam suas observações mesmo quando não retornam
finding. Nenhum novo parâmetro de configuração de scan é necessário. Se a implementação
escolher um, CLI/headless/daemon/ScanRunner/ScanProgressScreen precisam recebê-lo e seus
construtores/call sites precisam ser verificados. Gravação em workspace e serialização em
`transport/ingest.py` devem conservar os novos campos: `submit` gera bytes UTF-8 do
`model_dump_json()` e `transport/signing.py` assina o hash desse corpo completo.

## Relatório, IA e apresentação

`reports.py` já monta JSON técnico e relatório explicado; o segundo já chama
`report_education._basis`. Reusar o fluxo. Educação muda versão2 → versão3 e recebe os
campos detection_method/evidence_status/confidence nas linhas do apêndice e nos grupos.
Grupos não misturam métodos/estados diferentes só porque compartilham serviço/CVE; um grupo
com limites distintos deve expô-los sem atribuir a todos a confiança da primeira linha.
Conservar os campos anteriores de educação para preview interno; evidence_counts antigo é
compatibilidade, evidence_summary define o resumo novo. Acrescentar standalone limitado
na seção de cobertura. PDF usa copy localizada e mesma política, com QA visual. JSON técnico
preserva as observações e nomes anteriores; exportar não dispara consultas de catálogo ou IA.
[A12–A14]

IA atual: context_version4, máximo15 findings no overview; chat usa máximo5 findings de scan,
10 do host, 20 linhas de máquinas e 10 mensagens de histórico. Não ampliar esses limites.
Contexto versão5 inclui detection_method, evidence_status, evidence_truncated e agregados
de evidence_summary em todos os builders: overview, scan chat, finding chat e host chat.
Conservar evidence_basis público como compatibilidade, ampliando com unknown quando não há
observação; deixar de usar target_observation como default para fonte desconhecida.

Não enviar ip, hostname, porta, serviço, CPE identificável, evidência bruta, facts, excerpts,
nomes locais, segredos ou mapa de endpoint. Preservar finding_N/machine_N e reinserção local
dos nomes já usada. Agregados refletem o conjunto completo; top_findings continua amostra.
Prompt diferencia configuração observada, associação e teste específico e proíbe transformar
inconclusivo/conflito/legado em confirmação, ou negativos/ausência em alvo seguro. Não chamar
IA para validar parser. Análises e chats já salvos permanecem intactos; a UI/relatório mostra
o limite de evidência atual ao lado, sem reescrever respostas históricas. [A10, A12, A14]

Frontend usa tipos gerados de OpenAPI e campos API em FindingPanel, tabelas, ScanDetail e
HostFindings. Rótulos, estados e mockups em DESIGN. TUI usa o reducer local sobre o mesmo
contrato e explicita que são resultados locais; não inventa enriquecimento/risco backend.
Todos os idiomas existentes recebem cópia consistente; falhas de leitura usam mecanismos
de erro existentes. Não apresentar percentuais de confiabilidade.

## Ordem de atualização e compatibilidade

1. Contrato/revisão/backend primeiro: aceitar payload antigo e novo; defaults no legado,
   persistência e política prontas. Atualizar API e worker juntos com a revisão aplicada.
2. Gerar tipos e atualizar web/relatórios/IA; ausência no histórico tem estado legível.
3. Atualizar agente depois de confirmar backend compatível, incluindo daemon e TUI.
   Só então ele pode emitir os novos campos para ingest. [A15]

Backend antigo usa extra=forbid e rejeita os campos novos; a ordem é um requisito real.
Não tentar reenviar automaticamente corpo sem metadados em erro422: isso perderia evidência
e alteraria o corpo assinado. Rollback do backend exige interromper envio por agentes novos
ou manter backend compatível; não fazer downgrade da persistência enquanto consumidores
dependem dos campos. Arquivo local novo permanece disponível se upload falhar. Não criar
negociação de capacidades ou dupla implementação provisória nesta entrega.

## Condições para aprovação

Aprovar limites16/512, fatos fechados, cinco métodos/quatro estados, fonte de confiança,
predicados das regras existentes, contagens e ordem backend → consumidores → agente.
Ausência de fixtures nativas para algum adaptador limita sua promoção a tentative, até haver
evidência suficiente; não justifica confirmação genérica. Avaliação de aplicabilidade NVD,
novos testes, patches/backports e decisões manuais ficam nas entregas futuras. A execução
deve cumprir os testes/gates mapeados em ARCHITECTURE antes de declarar A concluída.
