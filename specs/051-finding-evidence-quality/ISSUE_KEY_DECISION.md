# Vínculo de configuração — decisão focal

2026-10-10. Opção A autorizada pela orquestração como clarificação necessária da
entrega A. Não é nova aprovação humana nem aprovação de código. Nenhum novo teste
ativo, coletor ou configuração de scan. Tarefas1–3 aprovadas; tarefa4 permanece
intermediária, com modelo/revisão40 ainda sem validação ou aprovação.

## Evidência na fonte

- `backend/src/api/schemas/scan.py`: `FindingPayload` tem `extra="forbid"` e não
  tem `issue_key`; `_validate_finding_evidence` verifica alcance, sem vínculo de
  condição. `hardware-agent/src/agent/normalize/contracts.py` tem a chave interna
  com `exclude=True`. Ela não chega ao backend nem ao arquivo local serializado.
- `backend/src/api/services/scan_evidence.py`: `validate_finding_evidence` e
  `reduce_finding_evidence` já recebem `issue_key`; `_matching_observations` usa
  `issue_key or cve_id`. Sem ambas, elimina todas as observações. `_rule_result`
  valida regras e fatos fechados. Esses helpers não estão integrados à persistência.
- `backend/src/api/services/persistence.py`: `finding_dedupe_key` usa
  IP/protocolo/porta/unidade + CVE ou título normalizado. `FindingRecord` tem
  unicidade scan/dedupe_key; `HostFindingRecord` usa host/dedupe_key. A chave interna
  do agente já participa de seu dedupe sem CVE; isso não define a identidade SQL.
- `normalize/findings.py::_finding_identity` usa heurísticas de título/texto quando
  não há chave; elas servem à identidade local existente e não autorizam confiança.
  Até alguns predicados atuais usam uma chave literal com prefixo `title:`; igualdade
  contra essa chave declarada continua exigindo os fatos reais da regra. Não derivá-la
  do título recebido. `coverage.issue_keys` não vincula uma observação à finding.

## Alternativas e decisão

| Opção | Forma e consequência |
|---|---|
| A, escolhida | Publicar chave opcional, validar vínculo e conservar metadado no registro. Explicita a condição pretendida pelo produtor e permite replay pelo backend. Não altera identidade SQL. |
| B | Usar somente observações aninhadas, aceitar uma condição estrutural única validada por regra/fatos/alcance e recusar promoção na ambiguidade. Evita campo novo, mas exige outra política de associação e não conserva a chave declarada após merges sem informação adicional. |

A é o menor vínculo explícito que atende a semântica aprovada e usa o parâmetro
existente do reducer. Chave, fonte, regra, método e `positive`, sozinhos, não confirmam.
O backend valida os fatos e o endpoint; a assinatura autentica o produtor, sem novo
teste do alvo. B não será fallback quando A estiver ausente ou inválida.

## Forma exata

- OpenAPI `FindingPayload.issue_key`: propriedade opcional `string | null`, default
  null, minLength1/maxLength256; string deve ter conteúdo após trim. Backend e agente
  espelham `constr(min_length=1, max_length=256, strip_whitespace=True) | None = None`.
  Extras continuam proibidos no contrato/backend. Não adicionar `confidence` ao ingest.
- Retirar `exclude=True` somente quando tarefa10 habilitar emissão. Até lá, modelos
  aceitam a chave e seu uso interno permanece; nenhum corpo novo é enviado.
- `FindingRecord.issue_key`: nullable String(256), metadado sem índice ou unicidade.
  `FindingRecord.issue_key_ambiguous`: boolean não null, default/server_default false,
  estado explícito para merge incompatível. Acrescentar ambos à revisão40 ainda não
  publicada; histórico recebe null/false, sem inferência nem backfill de chave.
- Sem coluna em `HostFindingRecord`, sem mudança de `finding_dedupe_key`, finding_id,
  constraints, contagem ou reconciliação. Downgrade remove os dois metadados novos.
  A chave e a flag não precisam ser acrescentadas a `FindingRead`/OpenAPI FindingRecord:
  a leitura já expõe `condition_key` nas observações e resultado da política.

## Validação, merge e replay

Payload legado pode omitir `issue_key`, inclusive sem versão de evidência. A chave
isolada não é fato nem metadado suficiente para promover. Observação de configuração
ou teste não CVE deve ter `condition_key == finding.issue_key`; correlação/verificação
de CVE deve ter `condition_key == finding.cve_id`. CVE apenas referenciada em configuração
não substitui a chave da configuração. Backend e agente rejeitam vínculo incoerente
no schema do scan; não escolhem a primeira observação nem consultam título/coverage.

Alcance válido exige correspondência exata de IP/porta/protocolo/unidade para promoção;
null significa alcance ausente/host, nunca curinga. Regra desconhecida, fatos ausentes,
incorretos ou endpoint insuficiente conservam observação limitada e classificação
inconclusiva/tentative. Versões e limites16/512 continuam os existentes.

Quando há chave de configuração e CVE referenciada, separar as condições no reducer:
validar cada observação no vínculo permitido antes de reduzir a união. Nunca usar a
chave para promover automaticamente a CVE. Conflitos só comparam mesma condição e
alcance; usar o conjunto completo antes do limite, em ordem determinística.

Persistir a chave com as observações e reutilizá-la em ingest repetido, leitura,
enriquecimento e redução. Ausência de chave em job de catálogo não apaga chave válida.
Chaves explícitas distintas que colidem pela identidade SQL atual preservam todas as
observações, deixam `issue_key=null` e fixam `issue_key_ambiguous=true`. Essa flag é
absorvente no mesmo registro: merge posterior, catálogo, null ou truncamento não a
limpam. Registro ambíguo permanece inconclusive/tentative, ou conflicting quando há
contradição validada; não entra em demonstrated_records. Não separar registros nem
escolher chave/título para fabricar identidade ou restaurar confirmação.

## Ordem de implementação e gates focais

1. Correção focal da tarefa2: OpenAPI, schemas backend/agente e exemplos/testes de
   contrato; legado sem chave, limites, extras e vínculos incoerentes. Manter tarefa2
   aprovada e registrar a revisão focal no fluxo supervisionado.
2. Correção focal da tarefa3: reducer com vínculos explícitos, condições separadas,
   fatos inválidos, CVE associada e ambiguidades; preservar permutações/conflitos.
3. Pré-requisito da tarefa4: modelo/revisão40, persist_scan/upsert_finding, jobs de
   `backend/src/api/services/enrichment.py` e risco. Testar replay, chaves incompatíveis,
   flag absorvente após truncamento e invariância de FindingRecord/HostFindingRecord.
   Gates focais incluem `test_ingest_schema.py`, `test_contract_fidelity.py`,
   `test_scan_evidence.py`, `test_ingest_scan.py`, `test_enrichment_retries.py`,
   `test_inventory_reconcile.py` e testes da migração40, em dmitri_test preparado.
4. Tarefa9: adaptadores/extratores atribuem chave por condição e fatos reais;
   reducer local conserva a mesma semântica. Não aproveitar heurística de título
   como fato. Tarefa10 habilita serialização em runner/CLI/headless/daemon/TUI,
   `scanner/workspace.py` e `transport/ingest.py`, incluindo partial/cancel.
5. Gerar `frontend/src/types/openapi.d.ts` por `npm.cmd run gen:types` na tarefa8;
   FindingPayload gerado recebe o campo mesmo sem usá-lo no painel. Leituras,
   relatórios e IA continuam consumindo a decisão backend.

Backend/API/worker/revisão compatíveis devem estar liberados antes do agente emissor.
`transport/ingest.py` assina bytes de `model_dump_json()`; workspace usa
`model_dump(mode="json")`. Testes verificam chave no corpo completo/arquivo e legado
legível. Sem negociação temporária nem reenvio sem metadados após422. Esta decisão
foi verificada por leitura da fonte; não foram executados testes de produto aqui.
