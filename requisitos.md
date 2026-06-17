# Requisitos Funcionais — DMITRI (refinados)

> **Base normativa:** IEEE 830 / ISO/IEC/IEEE 29148 (requisitos atômicos, verificáveis,
> rastreáveis, sem Design) + EARS (Easy Approach to Requirements Syntax) para a forma
> da declaração (ubiquitous / event-driven / unwanted / state-driven / optional).
>
> **Escopo da análise:** validado contra `DMITRI_artigo.pdf` (§1.1, §3.1–§3.4), os 9 ADRs
> do repositório, `contracts/schemas/*.json`, e o código atual de `hardware-agent/` e `backend/`.

## Legenda de prioridade

| Código | MoSCoW | Fase | Status |
|--------|--------|------|--------|
| **MUST** | Must have | v1 | implementado no código atual |
| **SHOULD** | Should have | v2 | planejado (ADR), ainda não no código |
| **MAY** | May have | v3 | roadmap, não implementado |

## Legenda EARS

- **U** — Ubiquitous: *O <componente> deve <resposta>.*
- **E** — Event-driven: *Ao <gatilho>, o <componente> deve <resposta>.*
- **S** — State-driven: *Enquanto <estado>, o <componente> deve <resposta>.*
- **W** — Unwanted: *Se <falha|condição>, o <componente> deve <resposta>.*
- **O** — Optional: *Quando <recurso opcional>, o <componente> deve <resposta>.*

---

## v1 — MUST (implementado)

### Agente embarcado (`hardware-agent/`)

- **RF-001** *(U)* — O agente Dmitri deve descobrir hosts ativos na sub-rede configurada
  antes de qualquer enumeração de portas.
  - Origem: Artigo §1.1.2 (OE-1) + §3.2.
  - Verificação: scan em rede conhecida retorna ≥ 1 host por IP ativo.
  - Rastreabilidade: `discovery/network_discovery.py` (`nmap -sn -PE -T4`).

- **RF-002** *(E)* — Quando o operador seleciona um perfil de varredura, o agente deve
  aplicar somente o subconjunto de portas e scripts correspondente ao perfil escolhido,
  conforme a tabela: `quick` (-F, portas top), `standard` (NSE descoberta), `extensive`
  (top 10 000 + `vulners.mincvss=3.0`), `max` (`-p-` + `vulners.mincvss=1.0`), `nspi`
  (categoria dedicada ao laboratório NSPi).
  - Origem: Artigo §3.2 + ADR-004; README §"Modos de varredura".
  - Verificação: payload gerado contém `scan_mode` igual ao selecionado e flags Nmap
    coerentes (`nmap_arguments_summary`).
  - Rastreabilidade: `config.py::discovery_arguments`, `scanner/stages.py`.

- **RF-003** *(U)* — O agente deve identificar serviço e versão em cada porta aberta
  retornada pela enumeração.
  - Origem: Artigo §1.1.2 (OE-1) + §3.2.
  - Verificação: cada `PortPayload` tem `service` não-vazio; serviço conhecido (ex.: vsftpd)
    produz `version` compatível.
  - Rastreabilidade: `discovery/service_detection.py` (`-sV --version-intensity`).

- **RF-004** *(E)* — Ao detectar portas abertas com serviços versionados, o agente deve
  correlacionar cada par serviço×versão com identificadores CVE via script `vulners` NSE,
  respeitando o limiar `min_cvss` do perfil selecionado.
  - Origem: Artigo §1.1.2 (OE-1) + §3.2; ADR-002 / ADR-006.
  - Verificação: varredura em ambiente com serviço vulnerável conhecido produz `Finding`
    com `cve_id` válido (`^CVE-\d{4}-\d{4,}$`).
  - Rastreabilidade: `discovery/vulnerability_detection.py`, `normalize/findings.py`.

- **RF-005** *(S)* — Durante a varredura, o agente deve paralelizar a enumeração de portas
  e a inspeção NSE usando `ThreadPoolExecutor`, com `max_workers` e `host_batch_size`
  configuráveis.
  - Origem: ADR-004 + Artigo §3.2 (pipeline multi-estágio).
  - Verificação: log do executor contém fan-out por batch; tuning aplicado em testes.
  - Rastreabilidade: `scanner/stages.py::run_port_stage`, `run_deep_inspection_stage`.

- **RF-006** *(U)* — O agente deve emitir ao final do scan um payload JSON conforme o
  contrato `ScanResult` em `contracts/schemas/scan_result.schema.json`, incluindo
  `scan_id` (UUID v4), `timestamp` ISO 8601, `subnet` CIDR, `scan_mode`, `devices[]`,
  `findings[]` e `metadata{}`.
  - Origem: Artigo §3.2 (payload JSON com metadados, devices, ports, services, artifacts,
  findings); `scan_result.schema.json`.
  - Verificação: payload passa no `jsonschema` validation em CI; testes de contrato.
  - Rastreabilidade: `normalize/contracts.py`, `hardware-agent/tests/`.

- **RF-007** *(W)* — Se o scan for interrompido (operador ou exceção), o agente deve
  produzir um payload marcado como `partial_result: true` indicando o estágio
  interrompido em `metadata.interrupted_stage`.
  - Origem: necessidade operacional; ADR-004.
  - Verificação: teste de interrupção em `hardware-agent/tests/` seta o flag.
  - Rastreabilidade: `scanner/stages.py::build_metadata`.

### Interface do operador (TUI Textual)

- **RF-008** *(U)* — A TUI Dmitri deve disponibilizar telas para Setup inicial, Home,
  Configuração de rede, Seleção de modo e categoria, Seleção de perfil de scan,
  Execução em curso, Visualização de resultado e Listagem de scans anteriores.
  - Origem: Artigo §1.1 (visualização) + §3.1 (Hardware Agent com uso pelo operador).
  - Verificação: smoke test da aplicação inicia cada tela sem erro.
  - Rastreabilidade: `tui/app.py` + `tui/screens/*.py`.

- **RF-009** *(S)* — Enquanto um scan estiver em curso, a TUI deve permitir que o
  operador o aborte; ao abortar, o resultado parcial deve ser gravado em disco.
  - Origem: requisitos operacionais do operador (escopo NSPi).
  - Verificação: atalho de abort durante scan grava arquivo com `partial_result=true`.
  - Rastreabilidade: `tui/app.py::action_quit_app`, `tui/screens/scan_progress.py`.

### Ingestão e persistência (Backend API)

- **RF-010** *(E)* — Ao receber um POST em `/api/v1/scans` com payload `ScanResult`
  válido, o Backend deve responder `202 Accepted` contendo `scan_id`, `devices_received`
  e mensagem de sucesso.
  - Origem: Artigo §3.1 (item 2) + §3.3; `main.py::ingest_scan_endpoint`.
  - Verificação: teste e2e em `backend/` (`smoke_test.py`) com payload válido.
  - Rastreabilidade: `main.py::ingest_scan_endpoint`.

- **RF-012** *(W)* — Se o `scan_id` recebido já existir no banco, o Backend deve
  retornar o registro existente sem criar duplicata (idempotência).
  - Origem: Artigo §3.3 (rastreabilidade, reprocessamento sem repetir coleta).
  - Verificação: dois POSTs com mesmo `scan_id` resultam em 1 `ScanRecord`.
  - Rastreabilidade: `services/persistence.py::persist_scan`.

### Persistência — modelo e dedupe

- **RF-013** *(U)* — O Backend deve manter entidades persistidas para Scan, Device,
  Port, Service, CPE, Finding, Artifact, EnrichmentJob, KevRecord, EpssRecord e
  RiskSnapshot, conforme definido em `models/persistence.py`.
  - Origem: Artigo §3.3 ("scan, device, port, service, finding, artifact e job de
  enriquecimento"); `ARCHITECTURE.md` §2.6.
  - Verificação: `Alembic` gera migrations cobrindo todas as tabelas; smoke test.
  - Rastreabilidade: `models/persistence.py`.

- **RF-014** *(E)* — Ao persistir um Finding, o Backend deve deduplicá-lo pela chave
  `(scan_id, ip, port, protocol, cve_id, title)`; entradas repetidas devem ser mescladas
  com `max(severity)`, `max(confidence)` e união de `references`.
  - Origem: integridade referencial; Artigo §3.3.
  - Verificação: dois findings idênticos no payload → um `FindingRecord` com severidade
  máxima.
  - Rastreabilidade: `services/persistence.py::upsert_finding`,
  `_max_severity`, `_max_confidence`.

### Enriquecimento assíncrono

- **RF-015** *(U)* — O Backend deve enfileirar jobs de enriquecimento em uma tabela do
  próprio PostgreSQL, consumidos por worker com `FOR UPDATE SKIP LOCKED` para garantir
  concorrência sem broker externo.
  - Origem: Artigo §3.3 ("fila baseada no próprio PostgreSQL … preserva simplicidade
  arquitetural"); ADR-009.
  - Verificação: dois workers concorrentes não processam o mesmo job.
  - Rastreabilidade: `services/enrichment.py::claim_pending_enrichment_jobs`.

- **RF-016** *(E)* — Ao persistir um scan, o Backend deve enfileirar jobs do tipo
  `nvd_cpe` (para cada CPE), `nvd_cve` (para cada CVE em finding),
  `kev_cve` e `epss_cve` (para cada CVE em finding).
  - Origem: Artigo §3.3 (worker enriquece); ADR-002 (vulners + NVD + KEV + EPSS).
  - Verificação: scan de teste gera ≥ 1 job de cada tipo quando aplicável.
  - Rastreabilidade: `services/persistence.py::_enqueue_enrichment_jobs`.

- **RF-017** *(S)* — Enquanto o feed estiver cacheado e dentro do TTL configurado, o
  worker deve usar o valor em cache para NVD, KEV e EPSS sem nova requisição externa.
  - Origem: Artigo §3.3 ("aderência ao porte do projeto"); ADR-009.
  - Verificação: dois enriquecimentos consecutivos do mesmo CVE geram 1 requisição HTTP.
  - Rastreabilidade: `services/{nvd,kev,epss}.py`, `core/config.py` (TTLs).

### Cálculo de risco e priorização

- **RF-018** *(E)* — Ao final do enriquecimento de cada Finding com CVE, o worker deve
  calcular `risk_score ∈ [0, 100]` conforme
  `risk = severity·45 + exploitability·35 + confidence·15 + exposed_service·5`,
  onde `exploitability = min(1, epss·0.7 + 0.3·kev_present + 0.1·ransomware)`,
  e gravar o resultado com `rationale` legível.
  - Origem: Artigo §2.3 (combinar CVSS + EPSS + KEV); `services/risk.py`.
  - Verificação: teste unitário em `services/risk.py` valida casos conhecidos;
  varredura em Metasploitable produz score alto para vsftpd 2.3.4 com CVE conhecido.
  - Rastreabilidade: `services/risk.py::refresh_risk_snapshot`.

### Consulta REST

- **RF-019** *(E)* — Ao receber `GET /api/v1/scans`, o Backend deve retornar a lista de
  scans ordenada por timestamp decrescente, com `device_count` e `finding_count`.
  - Origem: Artigo §3.3 (consultas históricas); OE-2.
  - Verificação: teste de listagem com 3 scans ordenados.
  - Rastreabilidade: `main.py::list_scans`.

- **RF-020** *(E)* — Ao receber `GET /api/v1/findings` com filtros opcionais
  `severity`, `scan_id`, `device_ip`, o Backend deve retornar apenas os findings que
  satisfazem todos os filtros fornecidos.
  - Origem: Artigo §3.3 (detalhamento por ativo).
  - Verificação: combinação de filtros produz intersecção correta.
  - Rastreabilidade: `main.py::list_findings`.

- **RF-021** *(E)* — Ao receber `GET /api/v1/scans/{id}/risk-summary`, o Backend deve
  retornar agregados do scan: total de findings, findings com KEV, findings com
  confidence=confirmed, `average_risk_score`, `max_risk_score` e top-5 findings por
  `risk_score`.
  - Origem: Artigo §2.3 (priorização acionável); §3.1 (recomendações de priorização).
  - Verificação: teste com scan conhecido reproduz os números esperados.
  - Rastreabilidade: `main.py::get_scan_risk_summary`.

- **RF-022** *(U)* — O Backend deve publicar a especificação OpenAPI 3.x gerada pelo
  FastAPI nos caminhos `/docs` (Swagger UI) e `/openapi.json`.
  - Origem: Artigo §1.2 (geração automática de contratos OpenAPI); ADR-003.
  - Verificação: `GET /openapi.json` retorna schema válido.
  - Rastreabilidade: `main.py` (`FastAPI(title=…)`).

### Operação (escopo e premissas)

- **RF-023** *(S)* — Enquanto em operação normal, o sistema deve suportar até
  1–2 varreduras por dia em sub-rede `/24`, com até ~10 operadores/visualizadores
  concorrentes.
  - Origem: Artigo §1.2 (escopo); README §"Escopo e premissas".
  - Verificação: smoke test com 2 scans/dia simulados não extrapola recursos.
  - Rastreabilidade: ADR-001 (sizing) + `core/config.py`.

---

## v2 — SHOULD (planejado, ADR-definido, ainda não no código)

- **RF-201** *(O)* — Quando portas SMB (445), TLS (443) ou HTTP (80/8080) forem
  detectadas, o agente deve opcionalmente executar `enum4linux-ng`, `testssl.sh` ou
  `Nikto`, respectivamente, em modo de varredura estendida.
  - Origem: Artigo §1.2 (v2 inclui ferramentas complementares); ADR-006.
  - Verificação: scan com perfil `v2` em host que expõe SMB dispara enum4linux-ng.
  - Rastreabilidade: a definir em `#issue` (v2).

- **RF-202** *(U)* — A camada de apresentação deve disponibilizar um Frontend Web
  (React + TypeScript) com dashboards de histórico de scans, inventário de dispositivos,
  detalhe de findings e recomendações priorizadas.
  - Origem: Artigo §1.1.2 (OE-4) + §3.1 (Frontend Web).
  - Verificação: build do SPA + smoke test das rotas principais.
  - Rastreabilidade: a provisionar (`frontend/`).

- **RF-203** *(U)* — O Backend deve autenticar usuários do Frontend via JWT (access
  short-lived + refresh em httpOnly cookie), com endpoints de login, registro e
  redefinição de senha.
  - Origem: ADR-005 (autenticação Frontend→API); OE-3 (usuários).
  - Verificação: fluxo login → access token → chamada autenticada → refresh.
  - Rastreabilidade: a definir (rotas `/auth/*`).

- **RF-204** *(U)* — O Backend deve manter entidades `User`, `Role` e `Permission` com
  controle de acesso aos endpoints de consulta.
  - Origem: Artigo §1.1.2 (OE-3: "usuários, permissões").
  - Verificação: usuário sem role não acessa `/scans`.
  - Rastreabilidade: a definir em `models/persistence.py` (v2).

- **RF-011** *(S)* — *(Reclassificado de v1 → v2: a verificação de assinatura
  agente→API ainda não existe em `backend/src/api/`; o ID original é preservado.)*
  Ao receber um POST em `/api/v1/scans`, o Backend deve validar a assinatura
  HMAC-SHA256 no header da requisição e rejeitar payloads com assinatura inválida
  ou ausente.
  - Origem: ADR-005; Artigo §3.1 ("envia de forma segura"); ver NFR-S-01.
  - Verificação: teste com HMAC correto retorna 202; HMAC incorreto/ausente retorna 401.
  - Rastreabilidade: a definir (middleware HMAC, conforme ADR-005).

---

## v3 — MAY (roadmap, LLM copiloto)

- **RF-301** *(O)* — Quando o módulo copiloto estiver habilitado, o Backend deve
  expor endpoints que sintetizam findings priorizados, explicam por que um item merece
  atenção e sugerem ordem de remediação, **somente sobre dados já persistidos**.
  - Origem: Artigo §3.4 (camada assistiva).
  - Verificação: explicação gerada cita `finding_id` real do banco; sem alucinação
  sobre findings inexistentes.
  - Rastreabilidade: a definir (v3).

- **RF-302** *(U)* — O Backend deve persistir sessões, mensagens e chamadas de
  ferramentas do copiloto para fins de auditoria.
  - Origem: Artigo §3.4 ("sessões, mensagens e chamadas de ferramentas devem ser
  armazenadas para auditoria").
  - Verificação: cada chamada de ferramenta do LLM gera registro em `llm_call_log`.
  - Rastreabilidade: a definir (v3).

- **RF-303** *(O)* — Quando autorizado explicitamente por configuração, o agente deve
  executar ferramentas com credenciais corporativas (ex.: tentativas controladas de
  autenticação) e revalidação de versões/patches de SO.
  - Origem: Artigo §1.1 (objetivo geral — "suporte à atualização de versões");
  ADR-006 (v3 — ferramentas com credenciais).
  - Verificação: ferramenta só roda se flag de autorização estiver ativa.
  - Rastreabilidade: a definir (v3, depende de revisão ética).

---

## Requisitos Não Funcionais (RNF)

> **Base normativa:** ISO/IEC 25010 (atributos de qualidade) para a categorização e
> ISO/IEC/IEEE 29148 (requisitos verificáveis e mensuráveis) para a forma. Cada RNF
> referencia, em "Rastreabilidade", a restrição de Design correspondente na tabela
> de Restrições abaixo (NFR-x) e/ou o ADR de origem.

### Segurança

- **RNF-001** — Toda comunicação agente→API e frontend→API deve ocorrer sobre HTTPS/TLS;
  requisições em HTTP simples devem ser recusadas ou redirecionadas.
  - Origem: ADR-005; Artigo §3.1 ("envia de forma segura").
  - Verificação: requisição HTTP em texto claro não é aceita (301/426 ou recusa de conexão).
  - Rastreabilidade: NFR-S-01.

- **RNF-002** — A API deve restringir CORS a uma allowlist explícita de origens, sem
  uso de `*` quando `allow_credentials=True`.
  - Origem: ARCHITECTURE.md §8.
  - Verificação: origem fora da allowlist não recebe headers `Access-Control-Allow-*`.
  - Rastreabilidade: NFR-S-02; `core/config.py` (CORS origins).

- **RNF-003** — Segredos (chave HMAC, segredo JWT, credenciais de banco) devem ser lidos
  de variáveis de ambiente e nunca versionados no repositório.
  - Origem: ADR-005; `backend/.env.example`.
  - Verificação: varredura do repositório não encontra segredo literal commitado.
  - Rastreabilidade: NFR-S-01.

### Desempenho e eficiência

- **RNF-010** — Uma varredura `standard` de sub-rede `/24` deve concluir em tempo
  compatível com o baseline do artigo (§4.1: 3 hosts, 322 findings, ≈ 389,24 s).
  - Origem: Artigo §4.1 (validação em Metasploitable).
  - Verificação: scan de laboratório dentro de margem do baseline reportado.
  - Rastreabilidade: cruza RF-001..006.

- **RNF-011** — O worker de enriquecimento deve reaproveitar feeds em cache dentro do TTL,
  limitando requisições externas a NVD/KEV/EPSS a uma por CVE/CPE por janela de TTL.
  - Origem: Artigo §3.3 ("aderência ao porte"); ADR-009.
  - Verificação: dois enriquecimentos consecutivos do mesmo CVE geram 1 requisição HTTP.
  - Rastreabilidade: cruza RF-017; `services/{nvd,kev,epss}.py`.

- **RNF-012** — O agente deve operar dentro dos limites de memória do Raspberry Pi (4 GB)
  durante uma varredura `/24`, sem esgotar RAM.
  - Origem: ADR-001 (sizing).
  - Verificação: monitoramento de RAM durante scan `/24` permanece abaixo do limite.
  - Rastreabilidade: NFR-S-03; ADR-001.

### Confiabilidade

- **RNF-020** — A ingestão de scans deve ser idempotente: reprocessar o mesmo `scan_id`
  não cria registros duplicados.
  - Origem: Artigo §3.3.
  - Verificação: dois POSTs com mesmo `scan_id` resultam em 1 `ScanRecord`.
  - Rastreabilidade: cruza RF-012; `services/persistence.py::persist_scan`.

- **RNF-021** — Jobs de enriquecimento não concluídos devem permanecer reentregáveis;
  a falha de um worker não pode deixar um job preso indefinidamente.
  - Origem: ADR-009; Artigo §3.3.
  - Verificação: job interrompido por queda de worker é reclamado por outro worker.
  - Rastreabilidade: cruza RF-015; `services/enrichment.py::claim_pending_enrichment_jobs`.

- **RNF-022** — Uma varredura interrompida deve produzir um resultado parcial recuperável
  e gravado, sem corromper o histórico existente.
  - Origem: necessidade operacional; ADR-004.
  - Verificação: abort durante scan grava payload com `partial_result=true`.
  - Rastreabilidade: cruza RF-007, RF-009.

### Manutenibilidade

- **RNF-030** — Os contratos de dados devem ser versionados em `contracts/schemas/*.json`
  e validados em CI; alterações de contrato sem atualização de schema devem falhar o build.
  - Origem: Artigo §3.3.
  - Verificação: payload fora do schema reprova na etapa de validação de contrato em CI.
  - Rastreabilidade: NFR-M-01.

- **RNF-031** — O código deve passar `ruff`, `black` e a suíte `pytest` (unit + e2e +
  contrato) no CI antes de qualquer merge.
  - Origem: ADR-005 / pipeline de CI.
  - Verificação: pipeline de CI bloqueia merge com lint/format/test falhando.
  - Rastreabilidade: NFR-Q-01.

- **RNF-032** — Toda alteração de esquema de banco deve ser aplicada via migração Alembic,
  sem modificação manual do schema em produção.
  - Origem: ADR-009.
  - Verificação: `alembic upgrade head` reproduz o schema a partir do zero.
  - Rastreabilidade: NFR-P-02; `models/persistence.py`.

### Portabilidade e plataforma

- **RNF-040** — O agente deve executar de forma headless em Raspberry Pi OS Lite
  (ARM64), sem dependência de ambiente gráfico.
  - Origem: ADR-001.
  - Verificação: instalação via `install.sh` e execução da TUI em ARM64 sem GUI.
  - Rastreabilidade: NFR-S-03.

- **RNF-041** — O Backend deve ser implantável via Docker Compose + Nginx, compatível
  com Railway (free-tier) e Supabase (Postgres).
  - Origem: ADR-007.
  - Verificação: `docker compose up` sobe API + worker + proxy funcionais.
  - Rastreabilidade: NFR-P-01.

### Escalabilidade e capacidade

- **RNF-050** — O sistema deve suportar 1–2 varreduras por dia em sub-rede `/24` e
  até ~10 operadores/visualizadores concorrentes sem degradação perceptível.
  - Origem: Artigo §1.2; README §"Escopo e premissas".
  - Verificação: smoke test com 2 scans/dia e 10 sessões simuladas não extrapola recursos.
  - Rastreabilidade: cruza RF-023; ADR-001.

### Custo

- **RNF-060** — O custo de hardware do agente deve ser ≤ R$ 1.250, sem licenciamento
  por dispositivo.
  - Origem: Artigo §1.2; ADR-001.
  - Verificação: BOM do dispositivo dentro do teto; software sem licença por unidade.
  - Rastreabilidade: NFR-C-01.

### Auditabilidade

- **RNF-070** — O sistema deve preservar histórico completo e consultável de scans,
  findings e `enrichment_jobs`, sem descarte automático de registros.
  - Origem: Artigo §3.3.
  - Verificação: registros de scans anteriores permanecem consultáveis após novos scans.
  - Rastreabilidade: NFR-A-01.

### Usabilidade

- **RNF-080** — A TUI deve ser totalmente operável por teclado, sem dependência de
  mouse ou ambiente gráfico, com cada tela acessível por navegação.
  - Origem: Artigo §3.1 (uso pelo operador).
  - Verificação: fluxo completo (setup → scan → resultado) concluído apenas com teclado.
  - Rastreabilidade: cruza RF-008.

---

## Restrições e NFRs (Design/Plataforma — IEEE 830 §5)

Os itens abaixo são as **restrições de Design/Plataforma** que fundamentam os RNF acima.
Cada RNF referencia o `NFR-x` correspondente em sua "Rastreabilidade":

| ID | Tipo | Descrição | Origem |
|----|------|-----------|--------|
| NFR-S-01 | Segurança | HMAC-SHA256 (agente→API) + JWT (frontend→API) + HTTPS obrigatório | ADR-005 |
| NFR-S-02 | Segurança | CORS allowlist (sem wildcard com `allow_credentials=True`) | ARCHITECTURE.md §8 |
| NFR-S-03 | Portabilidade | Operação headless em Raspberry Pi OS Lite (ARM64, 4 GB) | ADR-001 |
| NFR-P-01 | Plataforma | Deploy em Docker Compose + Nginx + Railway free-tier + Supabase | ADR-007 |
| NFR-P-02 | Plataforma | Migrações via Alembic contra Postgres (pooler 6543 / direta 5432) | ADR-009 |
| NFR-M-01 | Manutenibilidade | Contratos versionados em `contracts/schemas/*.json` validados em CI | Artigo §3.3 |
| NFR-Q-01 | Qualidade | Cobertura por testes unitários + e2e + contrato (`pytest` + `ruff` + `black`) | ADR-005 / CI |
| NFR-C-01 | Custo | Hardware ≤ R$ 1.250; sem licenciamento por dispositivo | Artigo §1.2; ADR-001 |
| NFR-A-01 | Auditabilidade | Histórico completo de scans, findings e enrichment_jobs | Artigo §3.3 |

---

## Validação: artigo × código × RF

| Claim do artigo | Onde aparece | RF correspondente | Status |
|-----------------|--------------|-------------------|--------|
| §1.1.2 OE-1: agente para descoberta/portas/serviços/NSE | código + artigo | RF-001..005 | ✅ MUST |
| §1.1.2 OE-2: backend REST API (recebimento, validação, persistência, consulta) | código + artigo | RF-010, RF-013, RF-019..021 | ✅ MUST |
| §1.1.2 OE-3: banco relacional com histórico, vulns, inventário, **usuários, permissões** | **gap**: sem User/Role | RF-013 (parcial); RF-203/204 | ⚠️ parcial → v2 |
| §1.1.2 OE-4: interface web "simples, não técnica" | **gap**: `frontend/` vazio | RF-202 | ⚠️ → v2 |
| §1.1.2 OE-5: validação em ambiente controlado | artigo §4.1 (Metasploitable) | validado em laboratório | ✅ |
| §1.1 (geral): "suporte à atualização de versões" | apenas texto em `recommendation` | RF-303 | ⚠️ → v3 |
| §3.1 Hardware Agent envia seguro | **gap**: HMAC só nos docs (ADR-005), não em `backend/src/api/` | RF-011 + NFR-S-01 | ⚠️ planejado → v2 |
| §3.1 Backend enfileira job | código (`_enqueue_enrichment_jobs`) | RF-015, RF-016 | ✅ MUST |
| §3.1 Worker enriquece + risco + persiste | código (`services/{enrichment,risk,persistence}.py`) | RF-016, RF-018 | ✅ MUST |
| §3.2 pipeline 4 estágios | código (`stages.py`) | RF-001..005 | ✅ MUST |
| §3.3 schemas tipados, entidades, fila Postgres | código | RF-013..015 | ✅ MUST |
| §3.4 camada LLM assistiva + auditoria | **gap**: não implementado | RF-301, RF-302 | ⚠️ → v3 |
| Resultado §4.1: Metasploitable, 3 hosts, 322 findings, 389,24 s | artigo | coberto por RF-001..006, RF-018 | ✅ validado |

---

## Como validar a apresentação

Cada RF acima pode ser cruzado com:
1. **Código-fonte** (arquivo e linha indicados em "Rastreabilidade").
2. **Teste** correspondente em `hardware-agent/tests/` e `backend/src/api/smoke_test.py`.
3. **Schema** em `contracts/schemas/*.json` (para RFs de contrato).
4. **ADR** correspondente (citado em "Origem").

Para o slide, sugerir usar apenas os MUST (RF-001 a RF-023) e indicar SHOULD/MAY como
faixas do roadmap, sem numerar todos.