# Roadmap Tecnico: Intelligence + IA + Authorized Assessment

## Objetivo

Definir a proxima linha de evolucao do projeto sem depender de OpenVAS e sem pular direto para um modo ofensivo solto.

O foco passa a ser:

- consolidar inteligencia de vulnerabilidade no backend
- enriquecer findings com fontes externas de priorizacao e, depois, fontes canonicas se necessario
- usar um agente LLM como analista assistivo
- introduzir um modo formal de assessment autorizado com guardrails

Este roadmap assume o estado atual do repositorio em maio de 2026:

- `hardware-agent` ja executa discovery, enumeracao TCP/UDP seletiva, service detection e NSE orientado por servico
- o backend ja persiste `scan`, `device`, `port`, `service`, `cpe`, `finding`, `artifact`, `enrichment_job` e cache NVD
- o enrichment NVD ainda roda inline no processo da API e precisa ser desacoplado

## Decisao de Prioridade

Neste recorte, o script `vulners` do Nmap continua como a principal fonte imediata de correlacao CVE no agente.

Isso significa:

- nao e obrigatorio adotar NVD CVE API e CPE API agora
- KEV e EPSS entram antes como camadas de priorizacao
- NVD fica como camada opcional posterior para canonicidade, normalizacao e maior rigor academico

Em termos praticos:

- agora: `vulners` + `KEV` + `EPSS`
- depois, se necessario: `NVD CVE API` + `NVD CPE API`

## Principio Central

O projeto nao deve evoluir para "um LLM rodando ferramentas de ataque".

O LLM deve entrar primeiro como:

- analista de contexto
- resumidor tecnico
- correlator de evidencias
- gerador de recomendacoes
- copiloto de triagem

Execucao ativa so entra sob:

- escopo explicito
- autorizacao formal
- modulos opt-in
- auditoria completa
- rate limiting
- kill switch

## Fase 3A: Vulnerability Intelligence

### Objetivo

Transformar o backend no centro real de inteligencia e priorizacao de risco.

### Entregas

- separar o worker de enrichment da API principal
- mover consumo de jobs para fila real em PostgreSQL com `FOR UPDATE SKIP LOCKED`
- ampliar enrichment a partir de `vulners` com fontes de priorizacao
- introduzir score composto de risco e explorabilidade
- manter CVE e CPE como identificadores centrais, sem exigir normalizacao profunda nesta etapa

### Fontes externas recomendadas

- CISA KEV catalog
- FIRST EPSS API
- opcionalmente NVD Vulnerabilities API
- opcionalmente NVD Products / CPE API
- opcionalmente CVE.org como referencia complementar de metadados

### Modelo de dados a adicionar

- `external_references`
  - `finding_id`
  - `source_name`
  - `reference_type`
  - `url`
- `kev_records`
  - `cve_id`
  - `known_ransomware`
  - `date_added`
  - `required_action`
- `epss_records`
  - `cve_id`
  - `epss_score`
  - `percentile`
  - `scored_at`
- `risk_snapshots`
  - `finding_id`
  - `confidence`
  - `exploitability`
  - `asset_criticality`
  - `risk_score`
  - `rationale`

Modelo opcional posterior, se NVD entrar:

- `cve_records`
  - `cve_id`
  - `description`
  - `cvss_v2`
  - `cvss_v3`
  - `cvss_v4`
  - `published_at`
  - `last_modified_at`
- `cpe_inventory`
  - `port_id`
  - `cpe`
  - `normalized_vendor`
  - `normalized_product`
  - `normalized_version`

### Logica de correlacao recomendada

1. usar findings e CPEs ja observados pelo `vulners` e pelo pipeline NSE
2. anexar KEV por `cve_id`
3. anexar EPSS por `cve_id`
4. calcular `confidence` e `risk_score`
5. opcionalmente, numa etapa posterior, validar ou enriquecer via NVD

### Scoring minimo recomendado

- `confidence`
  - `tentative`: banner fraco, heuristica, match parcial
  - `probable`: correlacao forte por `vulners` ou versao observada
  - `confirmed`: evidencia convergente entre `vulners`, fontes externas ou verificacao adicional
- `exploitability`
  - base em `epss_score`
  - boost se presente em `kev`
- `risk_score`
  - combinar `severity`, `confidence`, `epss`, `kev`, `service exposure`

### Endpoints novos

- `GET /api/v1/scans/{scan_id}/risk-summary`
- `GET /api/v1/findings/{finding_id}`
- `GET /api/v1/findings/{finding_id}/evidence`
- `GET /api/v1/cves/{cve_id}`
- `GET /api/v1/devices/{device_id}/timeline`
- `POST /api/v1/enrichment/reprocess/{scan_id}`

### Tarefas de implementacao

1. separar worker da API
2. criar claim de jobs com locking no PostgreSQL
3. adicionar clientes de KEV e EPSS
4. enriquecer findings ja existentes por `cve_id`
5. calcular `risk_score`
6. expor endpoints de consulta e historico
7. criar testes com fixtures offline para `vulners`-derived findings, KEV e EPSS

Tarefas opcionais posteriores:

1. adicionar cliente NVD CVE API
2. adicionar cliente NVD CPE API
3. persistir metadados canonicos de CVE
4. normalizar CPEs de forma mais rigorosa

### Criterio de pronto

- um finding consegue responder:
  - qual CVE foi correlacionado
  - por qual evidencia
  - com qual confianca
  - se ha exploracao conhecida
  - qual a prioridade relativa de remediacao

## Fase 3B: Copiloto LLM

### Objetivo

Adicionar um agente LLM como camada de interpretacao, priorizacao e explicacao.

### Papel do LLM

- resumir um scan inteiro
- explicar por que um finding e importante
- propor remediacao contextual
- apontar lacunas de evidencia
- sugerir proximo passo de verificacao
- gerar relatorio tecnico e resumo executivo

### Papel que o LLM nao deve ter nesta fase

- executar comandos ofensivos automaticamente
- alterar escopo de varredura
- inventar CVEs ou correlacoes sem evidencia
- atuar sem trilha de auditoria

### Arquitetura recomendada

- o backend continua como autoridade do estado
- o LLM consome dados estruturados do banco
- o LLM usa tools controladas pelo backend
- toda resposta do LLM deve citar os `finding_ids`, `device_ids` ou `scan_id` usados

### Ferramentas que o backend deve expor ao LLM

- `get_scan_summary(scan_id)`
- `get_device_profile(device_id)`
- `get_finding_detail(finding_id)`
- `get_cve_context(cve_id)`
- `search_findings(filters)`
- `list_assessment_modules(device_id)`
- `propose_assessment_plan(device_id, scope)`

### Funcionalidades de produto

- resumo tecnico por scan
- ranking de top riscos
- recomendacoes priorizadas por impacto
- resposta a perguntas do operador:
  - "quais hosts exigem atencao imediata?"
  - "quais findings sao conhecidos como explorados?"
  - "quais servicos expostos ainda nao tem evidencia suficiente?"

### Dados adicionais recomendados

- `llm_sessions`
  - `session_id`
  - `user_id`
  - `scan_id`
  - `started_at`
- `llm_messages`
  - `session_id`
  - `role`
  - `content`
  - `tool_calls_json`
- `llm_artifacts`
  - `session_id`
  - `artifact_type`
  - `path_or_payload`

### Guardrails obrigatorios

- respostas baseadas em dados persistidos
- proibido agir fora do escopo do scan selecionado
- proibido executar modulo intrusivo nesta fase
- logging de prompts, tool calls e IDs de evidencias
- templates de prompt com linguagem conservadora:
  - "evidencia observada"
  - "hipotese"
  - "recomendacao"
  - "nivel de confianca"

### Endpoints ou fluxos novos

- `POST /api/v1/ai/sessions`
- `POST /api/v1/ai/sessions/{session_id}/messages`
- `GET /api/v1/ai/sessions/{session_id}`
- `POST /api/v1/scans/{scan_id}/ai-summary`

### Tarefas de implementacao

1. definir tool surface minima
2. criar service de orchestracao LLM
3. persistir conversas e tool calls
4. montar prompts com evidencias estruturadas
5. criar testes de resposta com fixtures deterministicas

### Criterio de pronto

- o operador consegue abrir um scan e obter um resumo util e auditavel
- toda resposta do LLM consegue ser rastreada a evidencias persistidas

## Fase 3C: Authorized Assessment

### Objetivo

Criar um modo formal de avaliacao ativa controlada, sem transformar o projeto em um executor ofensivo generico.

### Modos operacionais formais

- `discovery`
- `vulnerability_assessment`
- `authorized_assessment`

### Regras

- `discovery`
  - somente observacao e enumeracao
- `vulnerability_assessment`
  - enrichment, correlacao, priorizacao, checagens seguras
- `authorized_assessment`
  - modulos ativos apenas com allowlist e aprovacao

### Modulos iniciais recomendados

- `http_surface_review`
  - cabecalhos, metodos, paginas previsiveis, tech fingerprint adicional
- `tls_posture_review`
  - cipher suites, expiracao, versoes, risco de configuracao
- `smb_posture_review`
  - signing, dialects, guest exposure
- `ssh_posture_review`
  - auth methods, algos fracos, exposicao externa
- `credential_policy_probe`
  - apenas se explicitamente autorizado e com lista controlada

### Modulos a evitar no recorte inicial

- brute force generico
- exploit automation
- payloads de RCE
- movement lateral
- agentes autonomos com shell irrestrito

### Modelo de dados a adicionar

- `assessment_policies`
  - `name`
  - `allowed_modes`
  - `rate_limit`
  - `requires_manual_approval`
- `assessment_scopes`
  - `scope_id`
  - `target_type`
  - `target_value`
  - `approved_by`
  - `approved_at`
  - `expires_at`
- `assessment_runs`
  - `run_id`
  - `scan_id`
  - `device_id`
  - `module_name`
  - `mode`
  - `status`
- `assessment_evidence`
  - `assessment_run_id`
  - `kind`
  - `payload_json`
  - `artifact_path`
- `audit_events`
  - `actor`
  - `action`
  - `target`
  - `timestamp`
  - `result`

### Guardrails obrigatorios

- scope explicito por host ou subnet
- aprovacao manual para modulos ativos
- trilha de auditoria completa
- rate limiting por modulo
- janela de execucao
- kill switch global
- dry-run mode

### Fluxo recomendado

1. operador seleciona scan ou device
2. sistema gera plano de assessment
3. operador aprova modulos permitidos
4. backend agenda jobs
5. hardware-agent ou worker executa apenas modulos allowlisted
6. backend persiste evidencias e findings derivados
7. LLM resume resultados e proximos passos

### Tarefas de implementacao

1. formalizar `mode` no contrato da API
2. criar `assessment_policies` e `assessment_scopes`
3. implementar um executor modular
4. criar `audit_events`
5. expor aprovacao manual via API
6. implementar `kill switch`

### Criterio de pronto

- nenhum modulo ativo executa sem escopo e aprovacao
- toda acao ativa gera evento de auditoria

## Roadmap de Implementacao no Repositorio

### Marco 1

Backend de enrichment desacoplado da API:

- criar worker dedicado em `backend/src/api/services/worker.py` ou pacote equivalente
- trocar processamento inline por claim de job
- ajustar `docker-compose` para API + worker

### Marco 2

Inteligencia de vulnerabilidade:

- adicionar clientes KEV e EPSS
- persistir `kev_records`, `epss_records` e snapshots de risco
- calcular `risk_score`
- adicionar endpoints de consulta historica

### Marco 2B

Canonicidade opcional posterior:

- adicionar NVD CVE API
- adicionar NVD CPE API
- persistir `cve_records`
- normalizar `cpe_inventory`

### Marco 3

Dashboard e consultas:

- endpoint de `risk-summary`
- timeline por device
- filtros por confidence, KEV e EPSS
- frontend com prioridade visual baseada em risco

### Marco 4

Copiloto LLM:

- service de IA no backend
- tool layer restrita
- persistencia de sessoes e mensagens
- resumo de scan e assistente de triagem

### Marco 5

Authorized Assessment:

- contratos de policy, scope e approval
- executor modular
- 1 ou 2 modulos seguros inicialmente
- auditoria, rate limit e kill switch

## Recorte Recomendado para o TCC

Se o objetivo e manter escopo viavel e ainda ter diferencial academico forte:

- agent robusto com enumeracao e NSE orientado por servico
- backend com persistencia e enrichment por `vulners`, KEV e EPSS
- score de risco explicavel
- copiloto LLM para triagem e relatorio
- authorized assessment limitado a 1 ou 2 modulos seguros

Opcional posterior:

- adicionar NVD como camada de validacao canonica e normalizacao de CPE

Evitar neste recorte:

- exploracao automatizada generica
- muitos modulos ativos ao mesmo tempo
- dependencia de scanners pesados externos
- autonomia ampla do LLM sobre execucao

## Perguntas de Pesquisa Alinhadas

- Como evoluir um scanner leve baseado em Nmap para uma plataforma de inteligencia de vulnerabilidade?
- Qual ganho real e obtido ao combinar CVE, CPE, KEV e EPSS sobre enumeracao bruta?
- Como um LLM pode aumentar a interpretabilidade dos findings sem comprometer rastreabilidade e controle?
- Como separar tecnicamente descoberta, enrichment, assessment autorizado e acao intrusiva?

## Ordem Pratica Recomendada

1. separar worker da API
2. integrar KEV e EPSS
3. calcular e expor `risk_score`
4. criar endpoints historicos por finding e device
5. integrar copiloto LLM com tools somente leitura
6. avaliar se NVD ainda e necessario
7. formalizar policies e scopes
8. implementar 1 modulo de authorized assessment
9. implementar auditoria e kill switch

## Fora de Escopo Imediato

- exploit frameworks
- movement lateral
- cred stuffing
- brute force generico
- agents com shell irrestrito
- escalacao automatica de agressividade por decisao do LLM
