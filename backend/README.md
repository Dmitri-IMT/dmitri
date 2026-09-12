# Backend API (FastAPI)

Backend responsavel por receber resultados do `hardware-agent`, persistir scans/dispositivos/portas/servicos/CPEs/findings, enfileirar jobs de enrichment e executar o enrichment em um worker dedicado.

O enrichment atual cruza `cve_id` com:

- NVD para validacao/correlacao complementar
- CISA KEV para exploracao conhecida
- FIRST EPSS para probabilidade de exploracao

Com isso, cada finding pode expor `kev`, `epss` e um `risk_score` inicial explicavel.

O ingest tambem preserva os snapshots de sistema operacional e dos servicos industriais
Modbus produzidos pelo `hardware-agent`.

## Requisitos

- Python 3.11+
- `uv` (gerencia dependencias e o lockfile `backend/uv.lock`)
- Postgres 17 acessivel (local via `supabase start`, ou hosted)

Instalacao local:

```bash
cd backend
uv sync --extra dev
```

## Migracao primeiro (obrigatorio antes de subir a API ou o worker)

O schema e propriedade exclusiva do Alembic; a aplicacao nunca cria tabelas no boot. Antes
de rodar a API ou o worker pela primeira vez contra um banco vazio, aplique a migracao
baseline com `DATABASE_URL_DIRECT` (variavel so de shell, nunca em `.env` ou no Railway):

```bash
cd backend
export DATABASE_URL_DIRECT=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres
uv run alembic upgrade head
unset DATABASE_URL_DIRECT
```

`DATABASE_URL_DIRECT` aceita `postgres://`, `postgresql://`, `postgresql+psycopg://` e
`postgresql+asyncpg://`, sempre normalizados para psycopg; nunca cai de volta para
`DATABASE_URL` (o pooler em modo transacao nao roda DDL). Ver
`../docs/cloud/supabase/SETUP.md` para o fluxo completo hosted (papel `dmitri_runtime`,
senha interativa, rollback).

## Variaveis de ambiente

Copie `.env.example` para `.env` e ajuste. `DATABASE_URL` e obrigatoria (`SecretStr`,
aceita os mesmos quatro prefixos Postgres de `DATABASE_URL_DIRECT`); as demais tem
default:

- `DATABASE_URL`
- `KEV_API_BASE_URL`, `KEV_CACHE_TTL_HOURS`
- `EPSS_API_BASE_URL`, `EPSS_CACHE_TTL_HOURS`
- `NVD_API_BASE_URL`, `NVD_API_KEY`, `NVD_CACHE_TTL_HOURS`,
  `NVD_MIN_REQUEST_INTERVAL_SECONDS`
- `ENRICHMENT_POLL_INTERVAL_SECONDS`, `ENRICHMENT_BATCH_SIZE`,
  `ENRICHMENT_MAX_ATTEMPTS`, `ENRICHMENT_RETRY_DELAY_SECONDS`,
  `ENRICHMENT_STALE_AFTER_SECONDS`

Sem banco Postgres configurado (ou com `DATABASE_URL` invalida/nao-Postgres), tanto a API
quanto o worker falham ao iniciar — nao ha fallback para SQLite.

`Settings` le `.env` automaticamente (`env_file=".env"`); um `.env` populado localmente tem
precedencia sobre variaveis exportadas no shell, inclusive durante os testes — remova ou
ajuste valores stale nesse arquivo se os testes falharem com configuracao inesperada.

## Como executar

API (usa o bind real que tambem roda no Railway):

```bash
cd backend
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

O servidor fica disponivel em `http://127.0.0.1:8000`.

Worker:

```bash
cd backend
uv run python -m api.worker_main
```

O worker faz polling na tabela `enrichment_jobs`, faz claim dos jobs `pending`, marca `running` durante a execucao e finaliza em `completed` ou `failed`. E um processo separado da API.

Consultas NVD sem cache sao espacadas por seis segundos por padrao. Respostas `429`,
falhas de transporte e erros `5xx` devolvem o job para `pending`, respeitam
`Retry-After` quando presente e usam tentativas limitadas. Jobs abandonados em `running`
tambem sao recuperados depois de `ENRICHMENT_STALE_AFTER_SECONDS`. Uma chave NVD permite
configurar um intervalo menor conforme a cota concedida ao projeto.

## Importar um scan JSON sem Raspberry

O importador local usa o mesmo servico de persistencia do endpoint de ingestao, mas exige
acesso direto ao banco e, por isso, deve ser usado apenas em desenvolvimento. O JSON e
validado integralmente antes de qualquer escrita. Informe um agente existente:

```powershell
cd backend
uv run backend-import-scan --file C:\caminho\scan.json --agent-id <UUID_DO_AGENTE>
```

Ou informe uma organizacao existente para criar/reutilizar um agente dedicado, sem gerar
nem imprimir chave privada:

```powershell
uv run backend-import-scan --file C:\caminho\scan.json --org-id <UUID_DA_ORG>
```

O comando imprime `scan_id`, `agent_id` e as quantidades recebidas. Repetir o mesmo arquivo
com o mesmo agente e idempotente. O worker deve permanecer em execucao para concluir o
enrichment e a analise por IA.

## Endpoints

As rotas registradas cobrem:

- health check em `GET /api/v1/health`
- ingest autenticado do agente em `POST /api/v1/scans`
- leitura de scans, hosts, findings e home
- detalhe de finding em `GET /api/v1/findings/{finding_id}`
- resumo de risco limitado e rastreavel em
  `GET /api/v1/scans/{scan_id}/risk-summary`
- autenticacao, usuarios e convites
- cadastro/leitura dos agentes, criacao e acompanhamento de comandos
- canal WebSocket do agente em `/api/v1/agents/{agent_id}/commands`

`/docs`, `/redoc` e `/openapi.json` estao desabilitados. O contrato publicado e
`../contracts/openapi/openapi.yaml`.

## Regra inicial de risco (engine mantido, sem mudanca de comportamento)

Os findings retornados pela lista, pelo detalhe de scan e pela home incluem
`risk_score` (0-100), `exploitability` (0-1), `confidence` e `risk_rationale`.
Esses campos refletem o snapshot persistido; ficam nulos quando ele nao existe.
As leituras nao recalculam risco nem consultam fontes externas. O painel de detalhe
do finding no frontend mostra o score e sua justificativa.

O `risk_score` atual e intencionalmente simples e deterministico:

- usa `severity` como base principal
- aumenta `exploitability` com `epss_score`
- aplica boost se o CVE estiver no catalogo KEV
- aplica pequeno peso para `confidence` e servico exposto

O resultado persistido em `risk_snapshots` inclui:

- `confidence`
- `exploitability`
- `risk_score`
- `rationale`

As duas consultas detalhadas acima formam a primeira superficie somente leitura
para a futura integracao LLM. Ambas aplicam o escopo da organizacao autenticada;
o resumo retorna no maximo dez findings, sempre com seus IDs e evidencias, para
limitar contexto e permitir rastreabilidade.

A analise assistida por IA tem uma superficie inicial somente leitura:

- `GET /api/v1/scans/{scan_id}/analysis`
- `AI_ENABLED=false` (padrao), ou a ausencia de `AI_API_KEY`, retorna
  `unavailable` sem afetar as demais APIs
- com IA habilitada, a resposta informa `pending`, `processing`, `completed` ou
  `failed`; somente `completed` inclui o JSON estruturado da analise
- a leitura nao chama um provedor nem dispara geracao

O resultado fica versionado e persistido em `ai_scan_analyses`, separado dos fatos
deterministicos do scan. A migracao deve ser aplicada antes de habilitar a feature.
O worker reutiliza o ciclo de polling existente: conclui o lote de enrichment,
seleciona apenas scans sem jobs de enrichment ativos e cria um unico job por scan.
Timeouts, rate limits e indisponibilidade usam retries limitados; jobs abandonados em
`processing` sao recuperados, e nenhuma chave ou mensagem de erro bruta do provedor e
persistida.

Configuracao inicial:

```env
AI_ENABLED=true
AI_PROVIDER=groq
AI_MODEL=openai/gpt-oss-120b
AI_API_KEY=<chave da Groq>
AI_MAX_FINDINGS=10
AI_TIMEOUT_SECONDS=30
AI_MAX_OUTPUT_TOKENS=4096
AI_REASONING_EFFORT=low
AI_MAX_ATTEMPTS=2
AI_RETRY_DELAY_SECONDS=30
```

Roadmap tecnico da proxima fase:

- `../docs/implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`

Prioridade atual do roadmap:

- `vulners` continua como base imediata de CVE
- `KEV` e `EPSS` entram antes de `NVD`
- `NVD` fica como camada opcional posterior de canonicidade

## Testes locais

```bash
cd backend
uv run ruff check .
uv run pytest
```

Sem `DATABASE_URL_TEST` definida, os testes que tocam banco pulam (o resto roda normal).
Com um Postgres 17 disponivel (por exemplo `supabase start`, banco dedicado
`dmitri_test`), rode a suite completa sem skips:

```bash
cd backend
DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest
```

Os testes de enrichment usam `monkeypatch` e fixtures offline para NVD, KEV e EPSS. Nao dependem da rede real.
