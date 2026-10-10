# ARCHITECTURE — Qualidade da evidência dos achados

Status: proposta para aprovação. Entrega A, 2026-10-10. Sem implementação ou `TASKS.md`.

## Contexto verificado

Leitura seletiva: `docs/implementation/SCAN-EVIDENCE-CORRECTIONS-2026-09-24.md` e
`docs/implementation/NSE-VULNERABILITY-PIPELINE.md`, seguida do mapa em `.claude/docs/`
e da fonte. O documento NSE tem informações históricas; a fonte atual define os caminhos.

O caminho atual é descoberta → portas → NSE/OT/avaliação direcionada →
`ScanRunner._build_payload()` → JSON/TUI/ingest → enriquecimento/risco/inventário →
leituras web/relatórios/IA. `cli.py` chama `headless.run_headless_scan()`; o daemon usa
a mesma função; `ScanProgressScreen` constrói `ScanRunner` diretamente. Não foi localizado
`ScanOrchestrator` ou `scanner/pipeline.py` neste checkout. Não criar outra camada de scan.

Problemas comprovados na fonte:

- `normalize/findings.py` aceita estados por substring. Um negativo pode passar como positivo.
- `_extract_generic_findings()` interpreta uma lista vazia como permissão para extrair todas
  as CVEs do texto. A rejeição estruturada precisa bloquear esse fallback.
- A tabela genérica exige descrição antes de examinar o estado. Resultados negativos nativos
  podem não ter descrição. O formato nativo também pode trazer `ids` como lista.
- A deduplicação do agente perde conteúdo da segunda evidência e depende da ordem em empates.
- `initial_confidence_for_finding()` usa apenas a presença de CVE; `_max_confidence()` conserva
  a maior confiança sem avaliar contradições. O enriquecimento altera confiança por origem.
- `_to_finding_read()` usa a confiança do snapshot de risco; sem snapshot ela desaparece.
- A origem real do produtor NVD é `nvd_enrichment`, mas `is_cve_correlation()` conhece somente
  `nmap_vulners` e `nvd`.
- A revisão Alembic atual é **`20261002_39`**, posterior à revisão 38 citada no mapa.

## Decisão e limites

Acrescentar observações tipadas aos modelos existentes e uma política determinística nos
helpers existentes. O backend decide a confiança; o agente conserva os fatos usados nessa
decisão. Não criar serviço de validação, barramento de observações ou novo mecanismo de scan.
O contrato detalhado está em `INTEGRATION.md`.

Manter `tentative`, `probable`, `confirmed` e ausência na leitura. Separar esses valores de
`detection_method` e `evidence_status`. `confirmed` para configuração significa somente que
a configuração foi observada. Confirmação de uma condição específica não significa que uma
exploração foi realizada. Fontes e referências permanecem como procedência. [A04–A06, A12]

Não adicionar scripts, argumentos Nmap, ferramentas, credenciais, coletores autenticados ou
modos. Saídas CLI continuam 0/10/20 e entrada inválida 2. `HUMAN_INFRA_REQUIRED`: nenhum
novo recurso; a implementação exigirá o banco de testes existente para gates backend.

## Interpretação de NSE

O parser retorna, internamente, **se a estrutura foi reconhecida**, os achados e as
observações sem achado. Lista vazia de achados não significa estrutura ausente. Reconhecer
tabela de resultado por seus campos de estado/identidade, antes de exigir título/descrição.
Visitar somente a unidade que possui o estado; referências e filhos não herdam positividade.

| Estado após trim, normalização de espaços e casefold | Resultado | Comportamento |
|---|---|---|
| `NOT VULNERABLE` | negative | Sem achado; registrar observação com alcance da condição. |
| `UNKNOWN (unable to test)`, `UNKNOWN`, ausente ou não suportado | inconclusive | Sem confirmação; registrar limite se houver unidade identificável. |
| `LIKELY VULNERABLE` | inconclusive | Pode conservar candidato de correlação quando há identidade/versão; nunca confirmação. |
| `VULNERABLE`, `VULNERABLE (DoS)`, `VULNERABLE (Exploitable)` | positive declarado pelo script | Conservar controle positivo; aplicar a política da regra, sem assumir exploração pelo rótulo. |

Usar igualdade contra a lista fechada; nunca substring `vuln`, `exploit` ou `dos`.
Variantes não suportadas permanecem inconclusivas. Não presumir que descrição ausente
transforma resultado negativo em texto livre. Aceitar CVEs somente de `IDS`/`ids` estruturados,
tanto mapa quanto lista nativa; identificadores em referências não identificam outra falha.

Quando qualquer unidade estruturada foi reconhecida, o texto geral é apenas evidência da
resposta: não reextrair CVEs dele, mesmo que todas as unidades sejam negativas, desconhecidas
ou incompletas. Em resposta mista, cada unidade mantém seu resultado; negativo de outra
condição não remove o positivo. Estruturas parcialmente malformadas não liberam fallback.
Sem estrutura reconhecida, texto com CVE gera no máximo candidato `textual_reference`,
`tentative`, `inconclusive`; texto com negativo/erro explícito gera somente observação.
Nenhum texto genérico recebe `confirmed`, nem gravidade alta presumida pela mera CVE:
usar `low` quando não há gravidade demonstrada e conservar a limitação. [A01–A03, A07, A16]

A lista de estados e a forma nativa são verificáveis na fonte primária
[Nmap vulns.lua](https://github.com/nmap/nmap/blob/master/nselib/vulns.lua).
O script já configurado `smb-vuln-ms17-010` fornece estado positivo sem `check_results`;
requerer esse campo eliminaria um controle legítimo. O mesmo script pode produzir estado
negativo em caminhos de erro. Conservar essa limitação; negativo nunca encerra histórico
na entrega A. Fonte: [script Nmap](https://github.com/nmap/nmap/blob/master/scripts/smb-vuln-ms17-010.nse).
Estas fontes explicam o formato; fixtures devem registrar a versão de origem e validar a
versão suportada, sem aceitar mudanças futuras de esquema automaticamente.

## Política de evidência

Aplicar a mesma tabela semântica em `normalize/findings.py` e `services/scan_evidence.py`;
as camadas não importam os pacotes Python umas das outras. O contrato e fixtures comuns
verificam equivalência. Web, relatório e IA consomem o resultado backend, sem reclassificação.

| Observação válida | Método | Confiança máxima | Estado |
|---|---|---|---|
| Vulners/NVD associa identidade observada à CVE | version_correlation | probable | supported para a associação; aplicabilidade continua não verificada |
| Valor de configuração observado por regra suportada | configuration_observation | confirmed para essa configuração | supported |
| Resposta positiva de teste específico suportado, no alcance correto | specific_check | confirmed para a condição testada | supported |
| CVE em texto/referência, sem teste válido | textual_reference | tentative | inconclusive |
| Regra/fatos não suportados, sem metadados ou tentativa inconclusiva | unknown ou método declarado sem validação | tentative para nova ingestão | inconclusive/unknown |

`source`, `source_script`, `rule_id`, `rule_version` ou `result=positive` isolados não
autorizam promoção. Cada regra tem campos de `facts` permitidos e predicado fechado de
resultado/condição/endpoint; valores inconsistentes não confirmam. A assinatura de ingest
autentica o produtor, não verifica novamente a resposta do alvo. Essa limitação permanece
explícita: validação do backend é semântica e não executa novos testes. [A04–A07, A14]

Regras da entrega A, sobre coletores já existentes:

- Vulners/NVD: identidade/CPE ou versão realmente observada e CVE; existência de exploit,
  CVSS, KEV ou EPSS não modifica confiança. Incluir o alias real `nvd_enrichment`.
- SMB signing/SMBv1, autenticação SSH, métodos HTTP, certificado e cifras TLS: fatos de
  configuração já interpretados por extratores específicos, com nome e valor observados.
  Exemplo: `signing_required=false` ou `dialect=SMBv1`, não apenas título de achado.
- FTP anônimo, sessão SMB anônima e leitura Modbus: resposta já obtida e resultado explícito
  de login/sessão/leitura, com endpoint e unidade quando aplicável; configurar método
  `specific_check`, sem inferir escrita ou exploração de CVE.
- `smb-vuln-ms17-010`: estado estruturado positivo, identidade esperada `CVE-2017-0143`,
  tabela e endpoint correspondentes. Regra `nse:smb-vuln-ms17-010`, versão `1`.
  Confirma apenas o resultado do teste desse script; não presume exploração ou todas as CVEs
  do boletim. Não exige `check_results` ausente no positivo nativo.
- `testssl.sh`, `ssh-audit`, `enum4linux-ng`, `ffuf`, Nikto e checks de cleartext:
  anotar método por registro e regra existente. Resultado de configuração/HTTP observado
  pode confirmar a condição limitada quando seu esquema está suportado. CVE em mensagem,
  recomendação ou referência dessas ferramentas não vira confirmação de CVE. Nikto com
  identificação de teste e mensagem sem fatos suficientes permanece candidato inconclusivo.
- Tabela genérica positiva de script desconhecido conserva o candidato, mas não autoriza
  `confirmed`. O estado do script não substitui a revisão do significado de sua regra.

Não transformar a lista acima em confirmação automática por ferramenta. O corpus de cada
adaptador documenta as regras de resposta aceitas e seus fatos fechados antes de promovê-las.
Campos novos de `TargetedIssue` transportam método/fatos/rule_id/version por registro; uma
origem comum `targeted_service_assessment` não significa que os registros têm a mesma força.

## Consolidação, contradição e atualidade

Estender `finding_dedupe_key`, `_append_unique` e `upsert_finding` existentes. Não criar uma
segunda identidade persistente. A chave backend e `HostFindingRecord` continuam estáveis;
`condition_key` nas observações serve para delimitar o que foi testado, não substitui a
identidade de inventário. CVE associa por CVE + endpoint/unidade; configuração associa por
`issue_key` já usado pelo agente. Observação de configuração com CVE de referência conserva
chave da configuração: sua positividade não confirma automaticamente a CVE referenciada.

Unir observações por valor canônico, ordenar de modo estável e escolher texto/fonte principal
por qualidade da evidência validada, depois severidade e desempate lexical. Manter união de
referências e `source_labels_json`. Repetição não acrescenta peso. Fonte principal não é a
lista completa de procedência. Retirar texto gerado que sugere confirmação por repetição.

Para o mesmo endpoint, unidade e condição:

1. Comparar alcance e fatos válidos antes de confiança. Host inteiro não equivale a uma porta;
   negativo genérico e erro não refutam observação específica.
2. Correlação não refuta configuração nem teste positivo; catálogo tardio também não pode
   rebaixar teste válido por encontrar `nmap_vulners` na fonte principal.
3. Positivo e negativo de verificação direta comparáveis, no mesmo scan, conservam ambos;
   resultado `conflicting`, confiança no máximo `tentative`, sem fechar inventário.
4. Negativo específico contra correlação da mesma CVE gera `conflicting`, no máximo tentative;
   conserva associação e justificativa para revisão, sem descartar nem encerrar histórico.
5. Inconclusivo não refuta positivo independente. Se o próprio positivo carece de fatos,
   endpoint ou esquema suportado, ele continua inconclusivo.
6. Atualidade vem de `ScanRecord.timestamp` e da seleção existente de scan mais recente.
   Todos os registros de um payload têm a mesma atualidade; ordem de ingest/enriquecimento
   e `updated_at` não criam uma observação mais nova. Não combinar scans em confirmação.

Reduzir sobre a união completa antes dos limites. Retenção determinística prioriza testemunhas
da evidência válida mais forte e pares de contradição, depois ordem canônica. Se o limite não
permite conservar as testemunhas necessárias, marcar truncamento e `inconclusive` (ou manter
`conflicting` conhecido); confiança no máximo tentative. Truncamento é monotônico durante
merge: posterior ingest não apaga o limite. Sem estatística por número de fontes. [A08–A09]

`_max_confidence` deixa de decidir observações atuais. Calcular confiança com a política;
atualizar snapshot após cada mudança e usar `FindingRecord.confidence` na leitura, mesmo
quando o risco ainda não existe. Job por CVE só acrescenta contexto público; job por CPE
acrescenta observação de correlação explícita. Nenhum job substitui o conjunto de observações.

## Cobertura e histórico

Observações negativas/inconclusivas sem achado ficam em `ScanPayload.finding_observations`,
fora dos achados. Não alterar `CoverageObservationPayload`, que já representa superfície,
administração e identidade. Timeout/erro/not_run gerais continuam na cobertura existente;
não fabricar um negativo por CVE quando a ferramenta não testou essa CVE. Observação com
condição identificável pode descrever falha de teste; não precisa criar achado positivo.

Preservar os bloqueios atuais de reconciliação: resultado parcial, lacunas e completude
desconhecida não fecham achados ausentes. Acrescentar salvaguarda para truncamento e unidades
negativas/inconclusivas sem alcance validado. **Na entrega A, observação negativa não é uma
instrução de resolução.** Se a omissão de um candidato decorre de resultado desconhecido,
parsing incompleto ou regra não suportada, não marcar seu histórico como corrigido só porque
Nmap terminou com êxito. Conservar problemas anteriores quando falta prova de que a condição
foi efetivamente coberta. Completar uma etapa não comprova avaliação de toda vulnerabilidade.
Não remover o fechamento existente de ausências que permanecem comprovadamente no alcance
completo; seu gate precisa considerar essas lacunas semânticas. [A07, A11]

Sem novos metadados, manter JSON antigo aceito. Histórico não ganha observações reconstruídas,
regra de teste, data de observação nem confiança inventada. Leitura desconhecida usa método
`unknown`/estado `unknown`; origem reconhecida permite somente descrever correlação. Guardar
confiança histórica já armazenada, acompanhada do limite de procedência, e excluí-la da nova
contagem de condições demonstradas quando não existe evidência estruturada suportada. Nova
ingestão legada usa probable para associação CVE e tentative nos demais casos. [A10, A13]

Uma migração adiciona campos anuláveis de política/observações e flags de truncamento aos
modelos existentes, sem novas tabelas. Corrigir somente correlações históricas comprovadas
por `nmap_vulners`, `nvd`, `nvd_enrichment` indevidamente confirmadas e seus snapshots, como
extensão da correção anterior; não inferir testes a partir de texto ou migrar todo o histórico
por heurística. Detalhes, compatibilidade e consumidores em `INTEGRATION.md`. [A10, A15]

## Arquivos e nomes obrigatórios

As linhas com vários caminhos enumeram arquivos exatos; todos existem salvo os marcados Novo.
Nenhum arquivo de aplicação será modificado durante esta preparação.

| Estado | Caminho | Responsabilidade |
|---|---|---|
| Existente | `hardware-agent/src/agent/normalize/contracts.py` | `FindingEvidenceObservationPayload`, limites/enums; campos aditivos de finding/scan. |
| Existente | `hardware-agent/src/agent/normalize/findings.py` | Estados fechados, fallback bloqueado, observações, merge e reducer locais. |
| Existente | `hardware-agent/src/agent/targeted/models.py` | Método/fatos por `TargetedIssue`; não alterar planos de execução. |
| Existente | `hardware-agent/src/agent/targeted/tls.py`, `hardware-agent/src/agent/targeted/ssh.py`, `hardware-agent/src/agent/targeted/smb.py`, `hardware-agent/src/agent/targeted/web.py`, `hardware-agent/src/agent/targeted/cleartext.py` | Anotar somente evidências já obtidas; CVEs em referência não confirmam. |
| Existente | `hardware-agent/src/agent/scanner/runner.py` | `_build_payload` coleta achados e observações uma vez, também nos resultados parciais. |
| Existente, auditoria de chamada | `hardware-agent/src/agent/cli.py`, `hardware-agent/src/agent/headless.py`, `hardware-agent/src/agent/daemon.py`, `hardware-agent/src/agent/tui/screens/scan_progress.py` | Frentes verificadas do mesmo runner; nenhum novo argumento público é necessário. Se a implementação adicionar um, propagar em todos. |
| Existente, auditoria de transporte | `hardware-agent/src/agent/scanner/workspace.py`, `hardware-agent/src/agent/transport/ingest.py`, `hardware-agent/src/agent/transport/signing.py`, `hardware-agent/src/agent/normalize/coverage.py` | Confirmar preservação de campos na gravação/serialização e assinatura do corpo completo; independência da cobertura existente. |
| Existente | `hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/src/agent/tui/screens/device_detail.py` | Rótulos de método/limite no resultado local; contagens significam registros. |
| Existente | `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/read.py` | Ingest estrito, leitura de observações e resumo tipado. |
| Existente | `backend/src/api/models/persistence.py` | Campos JSON/política/truncamento existentes por scan/finding. |
| Novo | `backend/alembic/versions/20261010_40_finding_evidence_quality.py` | Revisão `20261010_40`, pai `20261002_39`; revalidar head antes da implementação. |
| Existente | `backend/src/api/services/scan_evidence.py` | Política backend, validação dos fatos e resumo comum. |
| Existente | `backend/src/api/services/persistence.py`, `backend/src/api/services/enrichment.py`, `backend/src/api/services/risk.py`, `backend/src/api/services/inventory.py` | Merge por evidência, contexto NVD, snapshots e salvaguardas de resolução. |
| Existente | `backend/src/api/services/read.py`, `backend/src/api/services/home.py` | Confiança da finding, todos os pontos que serializam FindingRead, agregação com filtros antes de paginação. |
| Existente | `backend/src/api/services/reports.py`, `backend/src/api/services/report_education.py`, `backend/src/api/services/report_education_pdf.py`, `backend/src/api/services/report_education_copy.py` | JSON técnico, educação versão 3, PDF e traduções. |
| Existente | `backend/src/api/services/ai/context.py`, `backend/src/api/services/ai/chat.py`, `backend/src/api/services/ai/groq.py` | Contexto versão 5, todos os escopos e limites do dado; sem envio de evidência bruta. |
| Existente | `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json` | Fonte única do contrato e exemplo atual; testar exemplo legado separado. |
| Existente, gerado | `frontend/src/types/openapi.d.ts` | `npm.cmd run gen:types`, nunca editar manualmente; schema frontend se chama `FindingRecord`, backend `FindingRead`. |
| Existente | `frontend/src/pages/scans/FindingPanel.tsx`, `frontend/src/pages/scans/FindingsTable.tsx`, `frontend/src/pages/scans/findingColumns.tsx`, `frontend/src/pages/scans/ServiceTargetedFindings.tsx` | Consumo de método/estado/procedência no painel e tabelas existentes. |
| Existente | `frontend/src/pages/ScanDetail.tsx`, `frontend/src/pages/hosts/HostFindings.tsx`, `frontend/src/pages/HostDetail.tsx`, `frontend/src/api/findings.ts` | Resumo API, limites/observações de scan e página de findings do host. |
| Existente | `frontend/src/i18n/messages/en.ts`, `frontend/src/i18n/messages/pt-BR.ts`, `frontend/src/i18n/messages/ru.ts`, `frontend/src/i18n/messages/catalog.types.ts` | Rótulos localizados, conforme DESIGN. |

## Testes e avaliação offline

| Arquivos exatos | Expectativa e aceite |
|---|---|
| `hardware-agent/tests/test_findings.py`, `hardware-agent/tests/test_contract_models.py` | Negativo sem descrição e com referência; IDs nativos; unknown; texto; mixed; positivo MS17; configuração; merge em todas as ordens; limites e legado. A01–A10, A16. Atualizar a expectativa antiga de fallback, sem apagar o controle. |
| `hardware-agent/tests/unit/test_targeted_tls.py`, `hardware-agent/tests/unit/test_targeted_ssh.py`, `hardware-agent/tests/unit/test_targeted_smb.py`, `hardware-agent/tests/unit/test_targeted_web.py`, `hardware-agent/tests/unit/test_targeted_cleartext.py` | Método por registro, CVE em referência, alvo errado, resultado parcial e fatos aceitos/rejeitados. A04–A09. |
| `hardware-agent/tests/unit/test_scan_runner_partial.py`, `hardware-agent/tests/unit/test_headless.py`, `hardware-agent/tests/unit/test_cli_agent.py`, `hardware-agent/tests/unit/test_daemon.py`, `hardware-agent/tests/unit/test_tui_scan_view.py`, `hardware-agent/tests/unit/test_tui_device_detail.py`, `hardware-agent/tests/unit/test_ingest_client.py` | Mesmo payload/significado, cancelamento, arquivo local e corpo assinado sem perda; UI local/legado. A07, A10–A12, A15. Sem rede real. |
| `backend/tests/test_ingest_schema.py`, `backend/tests/test_ingest_scan.py`, `backend/tests/test_scan_ingest_route.py`, `backend/tests/test_scan_evidence.py`, `backend/tests/test_contract_fidelity.py` | Legado aceito; campos extras rejeitados; validação cruzada/limites; source/rule_id/fatos arbitrários não confirmam; aliases NVD. A04–A10, A15. |
| `backend/tests/test_enrichment_retries.py`, `backend/tests/test_finding_risk_read.py`, `backend/tests/test_inventory_reconcile.py` | Ordem dos jobs e duplicatas; risco atualizado; positivo preservado; conflito; cobertura incompleta e lacuna semântica não resolvem histórico. A08–A11. |
| `backend/tests/test_read_findings.py`, `backend/tests/test_read_scans.py`, `backend/tests/test_read_hosts.py`, `backend/tests/test_home_snapshot.py` | Contrato uniforme, confiança sem snapshot, filtro/isolamento org, resumo anterior a LIMIT/OFFSET e >uma página. A10, A12–A13. |
| Novo `backend/tests/test_finding_evidence_quality_migration.py`; existente `backend/tests/test_migrations.py` | Upgrade/downgrade a partir de 39, null no legado, correção restrita de aliases/snapshots; nenhuma observação fabricada. A10, A15. |
| `backend/tests/test_reports.py`, `backend/tests/test_report_education.py`, `backend/tests/test_ai_context.py`, `backend/tests/test_ai_chat.py`, `backend/tests/test_ai_groq.py` | Mesma semântica e resumo; escopos IA/limites; JSON técnico/preview; negativo fora de contagem; linguagem de incerteza. A12–A14. |
| `frontend/src/pages/scans/FindingPanel.test.tsx`, `frontend/src/pages/scans/findingColumns.test.tsx`, `frontend/src/pages/ScanDetail.test.tsx`, `frontend/src/pages/HostDetail.test.tsx` | Configuração versus CVE, legado/ausente, conflito, resumo filtrado global, observações sem achados, idiomas. A05–A06, A10, A12–A13. |
| Novo `hardware-agent/tests/test_finding_evidence_quality.py`; novos `hardware-agent/tests/fixtures/finding_evidence_quality/development.json`, `hardware-agent/tests/fixtures/finding_evidence_quality/evaluation.json` | Corpus versionado, pequeno, offline; desenvolvimento separado da avaliação e controles positivos. A01–A09, A16. |

O corpus registra entrada reduzida, origem/versão, rótulo independente, condição e resultado
esperado. Rótulos avaliam a interpretação da resposta, não provam a situação do scan pessoal.
Medir TP/FP/FN, precisão e cobertura com denominadores; separar inconclusivos/não avaliáveis
e método. Só calcular taxa FP com negativos de referência suficientes. Comparar baseline e
entrega A sobre o mesmo corpus. Redução do número de alertas não basta; preservar controles
positivos e reportar limitações/amostra. Nenhum percentual de confiança de produto é derivado
de fixtures. A avaliação das entregas B/C permanece no roadmap.

Gates durante implementação: pytest/Ruff focais, depois gates obrigatórios da camada;
backend prepara `dmitri_test` via `database.ps1`/`database.sh`; Ruff sem formatador global.
Frontend: lint, format:check, typecheck, test, build e geração/verificação do contrato.
PDF alterado exige skill PDF, renderização e inspeção das páginas afetadas. Falhas anteriores
devem ser registradas; não relatar suíte verde sem banco. Esta preparação não executou
suítes de produto, scans, deploys ou commits, nem inferência via CLI para verificar o harness.
Os agentes usaram os modelos selecionados; consumo de quota não foi medido.
