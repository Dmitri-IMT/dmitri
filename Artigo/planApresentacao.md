# Roteiro — Apresentação DMITRI (30 min)

## Context

O grupo precisa apresentar o projeto **DMITRI** (dispositivo embarcado para análise de
vulnerabilidades em redes locais) em 30 minutos. O artigo (`DMITRI_artigo.pdf`) já cobre
fundamentação teórica e justificativas; a apresentação deve **ir mais a fundo no código e na
arquitetura de software** do que o artigo. Entregável: **roteiro detalhado** (este arquivo) —
o grupo monta os slides depois. Ênfase **equilibrada (~50% técnico/código, ~50%
produto/processo)**. Apresentado por 5 pessoas (sem atribuição de falas neste roteiro).

**Ponto de atenção a resolver antes de apresentar:** há divergência de hardware entre as
fontes. O artigo e `docs/adr/ADR-001-hardware-selection.md` dizem **Raspberry Pi 4 (4 GB)**;
o slide de produto (`Dmitri_Analise_ConjunturaFinal.pptx`, slide 2) diz **Raspberry Pi 5**.
Padronizar para **Pi 4** (é o que está documentado e justificado por orçamento de R$ 1.250).

Material-fonte: artigo (21 págs.), `pptx` slide 2 (visão de produto/roadmap), código em
`hardware-agent/`, `backend/`, `contracts/`, `docs/adr/`, `specs/`, `.github/workflows/ci.yml`.

---

## Estrutura geral (30 min) — 11 blocos

Ordem pedida: **Arquitetura → Metodologia Ágil → Justificativa de tecnologias → Overview do
código**, com produto/problema na abertura e resultados/roadmap no fim.

| # | Bloco | Min | Tipo |
|---|-------|-----|------|
| 1 | Abertura + problema | 2 | Produto |
| 2 | Visão de produto e proposta de valor | 3 | Produto |
| 3 | Requisitos (funcionais e não funcionais) | 2 | Arquitetura |
| 4 | Arquitetura geral (5 componentes) | 3 | Arquitetura |
| 5 | Metodologia ágil (sprints, Kanban, specs) | 2 | Processo |
| 6 | Qualidade: TDD + CI (lint + testes) | 2 | Processo |
| 7 | Justificativa de tecnologias (ADRs, ferramentas, hardware) | 3 | Arquitetura |
| 8 | Overview do código: agente embarcado (pipeline) | 5 | Código |
| 9 | Overview do código: backend, enriquecimento e priorização | 5 | Código |
| 10 | Resultados (validação Metasploitable) | 2 | Resultado |
| 11 | Roadmap + encerramento | 1 | Produto |

Soma: ~30 min. Buffer de Q&A fora do tempo cronometrado.

---

## Bloco 1 — Abertura + problema (2 min)
- Quem somos, nome do projeto: **DMITRI — abordagem embarcada para segurança e análise de
  vulnerabilidades em redes**.
- Dor (do artigo, seção 1 e do `pptx` slide 3): Brasil concentra ~90% das tentativas de ataque
  da América Latina; 43% dos incidentes atingem pequenas empresas e só 14% estão preparadas;
  ferramentas existentes (Nmap, Nessus, OpenVAS) exigem especialista ou são caras.
- **Gancho central:** levar varredura + priorização de vulnerabilidades para quem **não tem
  equipe de segurança**, num appliance plug-and-play.

## Bloco 2 — Visão de produto e proposta de valor (3 min)
Fonte: `pptx` slide 2.
- **O que é:** appliance físico (Raspberry Pi 4) que conecta na rede local, roda sozinho e
  entrega resultados — sem instalação complexa e sem especialista.
- **Como funciona hoje (5 passos):** conecta na rede → roda Nmap + NSE (1–2x/dia ou sob
  demanda) → identifica hosts/portas/serviços → correlaciona com CVEs → apresenta na TUI.
- **Por que é diferente:** hardware+software plug-and-play; resultados acessíveis a gestores;
  **custo de hardware ~R$ 2.000 vs US$ 27.000+** das soluções enterprise.
- Posicionamento vs. concorrentes (artigo 2.5 + Tabela 1): mais barato/simples que
  Nessus/OpenVAS; vs. Vuls, o DMITRI faz **descoberta ativa de rede** + normalização +
  histórico + enriquecimento KEV/EPSS + (futuro) copiloto LLM.

## Bloco 3 — Requisitos (2 min)
Fonte: `docs/architecture/ARCHITECTURE.md`, artigo 1.1.2 e 3.4.
- **Funcionais:** descoberta de hosts; enumeração de portas (perfis quick/standard/extensive/
  max/nspi); detecção de serviço/versão; correlação de CVEs (vulners); geração de payload JSON
  (contratos); ingestão/consulta via API; visualização (TUI agora, web depois).
- **Não funcionais (artigo 3.4):** baixo custo; modularidade; manutenibilidade; rastreabilidade/
  auditabilidade; viabilidade em hardware embarcado (Pi 4, ARM64, 4 GB); escopo ~1–2 scans/dia,
  /24, ~10 operadores; segurança do próprio dispositivo (headless, hardening, HMAC).

## Bloco 4 — Arquitetura geral (3 min)
Fonte: artigo 3.1 (Figura 1), `docs/architecture/ARCHITECTURE.md`.
- Desenhar o **diagrama de 5 componentes** + fluxo principal:
  1. **Hardware Agent** (Pi 4) — varre com Nmap/NSE, normaliza JSON, envia por HTTPS (assinado
     com HMAC).
  2. **Backend API** (FastAPI) — recebe payload, valida (schemas tipados), enfileira job.
  3. **Background Worker** — consome fila, faz enriquecimento e calcula risco, persiste.
  4. **Banco** — PostgreSQL (Supabase), histórico/auditoria.
  5. **Frontend Web** (React/TS) — dashboards (fase posterior).
- **Princípio-chave:** separação ingestão × enriquecimento → o Pi não carrega processamento
  pesado; fila baseada no próprio Postgres (sem RabbitMQ) mantém simplicidade.
- Diagrama de código a mostrar (árvore de módulos): `hardware-agent/src/agent/{scanner,
  discovery,normalize,tui}` e `backend/src/api/{models,services,db,core}`.

## Bloco 5 — Metodologia ágil (2 min)
Fonte: `specs/`, GitHub Project, `CONTRIBUTING.md`.
- **Kanban no GitHub Projects** + issues (ex.: #56 extensive, #57 max, #58 nspi, #64 dead code,
  #67/#68 duração) organizadas em sprints.
- **Spec-driven development:** diretório `specs/NNN-feature-slug/` versionado (000-agent-tui →
  008-max-scan-mode), cada um com `ui/ interaction/ architecture/ contracts/ decisions/
  testing/ checklists/`. Contratos e critérios de aceite **antes** do código.
- **Conventional Commits** + branches `feature/*`/`fix/*` + PR com review obrigatório.

## Bloco 6 — Qualidade: TDD + CI (2 min)
Fonte: `.github/workflows/ci.yml`, `lint.sh`, `.pre-commit-config.yaml`, `hardware-agent/tests/`.
- **CI no GitHub Actions** (push/PR em main), 3 jobs:
  1. **validate** — `compileall` + validação dos JSON Schemas de `contracts/schemas/`.
  2. **lint** — `ruff check` + `black --check`.
  3. **tests** — `pytest hardware-agent/tests`.
- **TDD:** ~20 arquivos de teste (unit + integração e2e: `test_extensive_e2e.py`,
  `test_tui_flows.py`), incluindo testes de contrato (`test_contract_models.py`) que travam o
  schema Pydantic contra os JSON em `contracts/`.
- **Pre-commit** local: black, ruff, detect-secrets, pytest no pre-push.

## Bloco 7 — Justificativa de tecnologias: ADRs e ferramentas (3 min)
Fonte: `docs/adr/ADR-001..009`.
- Explicar **o que é um ADR** e que cada decisão foi avaliada por 3 critérios (artigo 1.4):
  valor técnico diferencial, adequação ética/legal, viabilidade no hardware embarcado.
- Tour rápido pelos 9 ADRs (1 frase cada):
  - **001 Hardware:** Pi 4 4 GB (Pi 5 estourava orçamento; BOM ~R$ 1.250) + adaptador
    AWUS036ACM (MT7612U) para modo monitor.
  - **002 Ferramentas de scan:** Nmap + NSE + **vulners**; descartados masscan, Metasploit,
    OpenVAS (pesado), CrackMapExec (ofensivo).
  - **003 Backend:** FastAPI (async, OpenAPI automático, validação Pydantic).
  - **004 Metodologia de scan:** pipeline multi-estágio + perfis quick/standard/extensive/max/nspi.
  - **005 Segurança:** HMAC-SHA256 agente→API; JWT frontend→API; HTTPS; CORS fechado.
  - **006 Ferramentas adicionais:** v2 enum4linux-ng/testssl.sh; exclusões justificadas
    (Hydra, LinPEAS, OpenVAS, reverse shells — ético/legal/recursos).
  - **007 Deploy:** nuvem (Render/Railway) vs LAN-only/VPN/local.
  - **008 Frontend:** React 19 + TypeScript + Vite + TanStack Query + shadcn/ui + Recharts.
  - **009 Banco:** PostgreSQL via Supabase, SQLModel, asyncpg, Alembic, fila no próprio Postgres.
- **Justificativa do hardware (destacar):** orçamento R$ 1.250; ARM64; Pi OS Lite headless;
  OpenVAS/Greenbone exigem ≥4 GB só para o feed → inviável → reforça a escolha Nmap+NSE leve.

## Bloco 8 — Overview do código: agente embarcado (5 min) — CÓDIGO
Fonte: `hardware-agent/src/agent/`.
- **Pipeline multi-estágio** (artigo 3.2; `scanner/stages.py`), inspirado em Lyon (2009):
  1. Descoberta de hosts — `discovery/network_discovery.py` (`nmap -sn -PE -T4`).
  2. Enumeração de portas — `run_port_stage()` em `scanner/stages.py`
     (`-Pn -sV --top-ports N`, ou `-p-` no modo max), com `ThreadPoolExecutor`
     (`max_workers`, `host_batch_size`).
  3. Detecção de serviço/versão — `discovery/service_detection.py` (`-sV --version-intensity 5`).
  4. NSE / vulnerabilidades — `run_deep_inspection_stage()` →
     `--script vulners --script-args vulners.mincvss={min_cvss}` + scripts por protocolo
     (smb-*, ssh-*, http-*, ssl-enum-ciphers).
  5. Normalização — `normalize/findings.py` (`extract_findings()`), regex `CVE-\d{4}-\d{4,}`,
     extratores por script → `FindingPayload`.
- **Wrapper do Nmap:** `scanner/nmap.py` — `NmapRunner.run_xml()` (`-oX -` + ElementTree);
  `LoggedNmapRunner` rastreia estágio/progresso para a TUI.
- **Contratos de saída:** `normalize/contracts.py` — `ScanPayload`, `DevicePayload`,
  `FindingPayload` (Pydantic). Mostrar um trecho do JSON gerado.
- **Regra de integração crítica (CLAUDE.md):** a TUI tem seu próprio runner
  (`scanner/runner.py::ScanRunner`) que chama as funções de discovery diretamente, **fora** do
  `ScanOrchestrator`. Bom ponto para falar de manutenção/armadilhas de arquitetura.
- **TUI (Textual):** `tui/app.py` (`DmitriApp`) + telas em `tui/screens/` (home, network,
  scan_mode, scan_progress, scan_view, past_scans). Mostrar 1 screenshot da TUI rodando.

## Bloco 9 — Overview do código: backend, enriquecimento e priorização (5 min) — CÓDIGO
Fonte: `backend/src/api/`.
- **Ingestão:** `POST /api/v1/scans` em `main.py` → `services/persistence.py::persist_scan()`
  grava `ScanRecord/DeviceRecord/PortRecord/FindingRecord` e **enfileira jobs** de
  enriquecimento (`EnrichmentJobRecord`: nvd_cpe, nvd_cve, kev_cve, epss_cve).
- **Modelo de dados:** `models/persistence.py` (entidades scan, device, port, service, finding,
  artifact, job, kev, epss, nvd_cache, risk_snapshot).
- **Fila lock-free no Postgres:** `services/enrichment.py::claim_pending_enrichment_jobs()` usa
  `FOR UPDATE SKIP LOCKED` — destacar como decisão de simplicidade (sem broker externo).
- **Metodologia de identificação de vulnerabilidades (2 camadas):**
  1. No dispositivo: **vulners NSE** (passivo, sem autenticação nem RCE) correlaciona
     serviço/versão → CVEs.
  2. No backend: enriquecimento com **NVD** (`services/nvd.py`, CPE→CVE, CVSS),
     **CISA KEV** (`services/kev.py`, exploração observada + flag ransomware) e
     **EPSS** (`services/epss.py`, probabilidade de exploração), com cache (TTLs em
     `core/config.py`).
- **Priorização / score de risco** — `services/risk.py::refresh_risk_snapshot()` (mostrar o
  código real):
  - `exploitability = min(1.0, epss*0.7 + kev_boost(0.3) + ransomware_boost(0.1))`
  - `risk_score = severity*45 + exploitability*35 + confidence*15 + exposed_service(0.05)*100`,
    saturado em 100.
  - Pesos: severidade {low .25 … critical 1.0}; confiança {tentative .5, probable .75,
    confirmed 1.0}. Gera `rationale` legível (`severity=…, epss=…, kev=yes`).
  - **Mensagem-chave (artigo 2.3):** severidade isolada (CVSS) não basta; combinar CVSS + EPSS +
    KEV produz priorização acionável.
- **Camada LLM (futuro, artigo 2.4/3.4):** copiloto **assistivo** (sumariza/explica/prioriza
  sobre dados já persistidos), nunca executor autônomo na rede — alinhado ao NIST AI RMF.
  Deixar claro que **ainda não está implementado** (é roadmap).

## Bloco 10 — Resultados (2 min)
Fonte: artigo 4.1 e Gráfico 1.
- Teste com **Metasploitable** na sub-rede 192.168.56.0/24, modo **extensive**:
  **3 hosts, 322 findings, 389,24 s**.
- Achados concretos: CVE em **vsftpd 2.3.4** (porta 21), login FTP anônimo, SSH por senha,
  caminhos web sensíveis (/admin, /manager), sessões SMB anônimas.
- Mostrar **Gráfico 1** (distribuição de findings por severidade).
- **Limitação honesta (artigo 4.2):** validado em PC de desenvolvimento; ainda **falta medir no
  Pi 4** → vira item de roadmap.

## Bloco 11 — Roadmap + encerramento (1 min)
Fonte: `pptx` slide 2, README, artigo 5.
- **v1:** scanner embarcado + TUI (atual).
- **v2:** frontend web com dashboard; ferramentas adicionais (enum4linux-ng, testssl.sh).
- **v3:** alertas críticos, copiloto LLM para triagem, pentest assistido, ferramentas com
  credenciais (com autorização explícita).
- Próximo passo imediato: **validação embarcada no Pi 4** e medição de desempenho.
- Fechamento: dados brutos → inteligência acionável, acessível a quem não é especialista.

---

## Slides sugeridos (para montar depois) — ~18–20 slides
1. Capa  2. Problema/cenário  3. Visão de produto (o que é / como funciona)
4. Proposta de valor + comparativo de custo  5. Requisitos F/NF
6. Diagrama de arquitetura (5 componentes + fluxo)  7. Diagrama de código (árvore de módulos)
8. Pipeline do agente (5 estágios)  9. Trecho de código do agente + JSON de saída
10. TUI (screenshot)  11. Backend: ingestão + fila Postgres
12. Metodologia de identificação (vulners + NVD/KEV/EPSS)  13. Fórmula de score de risco (`risk.py`)
14. ADRs (tabela resumo)  15. Justificativa de hardware  16. Metodologia ágil (Kanban/specs)
17. TDD + CI (pipeline)  18. Resultados (Metasploitable + gráfico)  19. Roadmap  20. Encerramento/Q&A

---

## Verificação (como conferir que o roteiro está fiel ao código)
Antes de fechar os slides, validar cada afirmação técnica abrindo o arquivo citado:
- Fórmula de risco: `backend/src/api/services/risk.py` (linhas 42–66) — confirmado.
- Jobs de CI: `.github/workflows/ci.yml` (validate/lint/tests) — confirmado.
- ADRs existentes: `docs/adr/ADR-001..009` — confirmado (9 arquivos).
- Specs/sprints: `specs/000..008` — confirmado (9 diretórios).
- Estágios do pipeline: `hardware-agent/src/agent/scanner/stages.py` e `discovery/`.
- Contratos: `contracts/schemas/*.json` + `normalize/contracts.py`.
- **Resolver a divergência Pi 4 vs Pi 5** antes de apresentar (usar Pi 4).
- Números dos resultados (3 hosts / 322 findings / 389,24 s) conferem com artigo 4.1.
