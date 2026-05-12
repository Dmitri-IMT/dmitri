# Backend API (FastAPI)

Backend responsavel por receber resultados do `hardware-agent`, persistir scans/dispositivos/portas/servicos/CPEs/findings, enfileirar jobs de enrichment e executar o enrichment em um worker dedicado.

O enrichment atual cruza `cve_id` com:

- NVD para validacao/correlacao complementar
- CISA KEV para exploracao conhecida
- FIRST EPSS para probabilidade de exploracao

Com isso, cada finding pode expor `kev`, `epss` e um `risk_score` inicial explicavel.

## Requisitos

- Python 3.11+
- dependencias do `pyproject.toml`

Instalacao local:

```bash
cd backend
python -m pip install -e ".[dev]"
```

## Como executar

API:

```bash
cd backend
python -m uvicorn api.main:app --reload --app-dir src
```

O servidor fica disponivel em `http://127.0.0.1:8000`.

No `docker compose`, a API fica exposta por padrao em `http://127.0.0.1:18000` para evitar conflito com faixas reservadas do Windows. Se quiser outra porta, ajuste `BACKEND_HOST_PORT` no `.env`.

Worker:

```bash
cd backend
python -m api.worker_main
```

O worker faz polling na tabela `enrichment_jobs`, faz claim dos jobs `pending`, marca `running` durante a execucao e finaliza em `completed` ou `failed`.

Smoke test automatizado:

```bash
cd backend
python -m api.smoke_test
```

Esse comando:

- roda `ruff` e `pytest`
- sobe `postgres`, `backend` e `worker` com `docker compose`
- envia `contracts/examples/scan_result.example.json`
- valida que os jobs nascem em `pending` e depois terminam no worker

Opcoes uteis:

- `python -m api.smoke_test --skip-checks`
- `python -m api.smoke_test --keep-up`

Banco local default:

- se `DATABASE_URL` nao for definido, o backend usa `sqlite:///./scanner.db`
- em producao, configure `DATABASE_URL` para PostgreSQL

Variaveis relevantes:

- `DATABASE_URL`
- `BACKEND_HOST_PORT`
- `KEV_API_BASE_URL`
- `KEV_CACHE_TTL_HOURS`
- `EPSS_API_BASE_URL`
- `EPSS_CACHE_TTL_HOURS`
- `NVD_API_BASE_URL`
- `NVD_API_KEY`
- `NVD_CACHE_TTL_HOURS`
- `ENRICHMENT_POLL_INTERVAL_SECONDS`
- `ENRICHMENT_BATCH_SIZE`

Roadmap tecnico da proxima fase:

- `../docs/implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md`

Prioridade atual do roadmap:

- `vulners` continua como base imediata de CVE
- `KEV` e `EPSS` entram antes de `NVD`
- `NVD` fica como camada opcional posterior de canonicidade

## Endpoints

- `GET /` -> responde `{"status": "ok"}`
- `GET /api/v1/health` -> responde `{"status": "ok"}`
- `POST /scans` -> recebe e persiste um JSON compativel com o contrato compartilhado
- `POST /api/v1/scans` -> alias versionado usado pelo agente
- `GET /scans` e `GET /api/v1/scans` -> lista historico de scans persistidos
- `GET /scans/{scan_id}` e `GET /api/v1/scans/{scan_id}` -> detalhe completo de um scan
- `GET /scans/{scan_id}/risk-summary` e `GET /api/v1/scans/{scan_id}/risk-summary` -> resumo de risco do scan
- `GET /findings` e `GET /api/v1/findings` -> lista findings persistidos com filtros simples
- `GET /findings/{finding_id}` e `GET /api/v1/findings/{finding_id}` -> detalhe de um finding com enrichment e risco

Resposta esperada de ingestao:

```json
{
  "message": "scan received successfully",
  "scan_id": "<uuid>",
  "devices_received": 2
}
```

Com a Fase 2 implementada, a ingestao agora faz:

- persistencia idempotente por `scan_id`
- normalizacao relacional de `scan`, `device`, `port`, `service`, `cpe` e `finding`
- criacao de `enrichment_jobs`
- retorno imediato sem enrichment inline
- cache local de consultas NVD, KEV e EPSS
- correlacao CPE -> CVE e deduplicacao entre sinais do scan e enrichment
- enrichment por `cve_id` com KEV e EPSS
- score de confianca: `tentative`, `probable`, `confirmed`
- snapshot inicial de risco com `exploitability`, `risk_score` e `rationale`

## Regra inicial de risco

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

## Testando com o payload de exemplo

Com o servidor rodando, execute a partir da raiz do monorepo:

```bash
curl -X POST http://127.0.0.1:18000/scans \
  -H "Content-Type: application/json" \
  --data @contracts/examples/scan_result.example.json
```

Ou usando o caminho versionado:

```bash
curl -X POST http://127.0.0.1:18000/api/v1/scans \
  -H "Content-Type: application/json" \
  --data @contracts/examples/scan_result.example.json
```

Depois consulte:

```bash
curl http://127.0.0.1:18000/api/v1/scans
curl http://127.0.0.1:18000/api/v1/findings
curl http://127.0.0.1:18000/api/v1/findings/<finding_id>
curl http://127.0.0.1:18000/api/v1/scans/<scan_id>/risk-summary
```

Voce deve ver o mesmo `scan_id` do arquivo de exemplo e os `enrichment_jobs` em `pending` ate o worker consumir a fila. Depois que o worker rodar, os findings enriquecidos passam a refletir `confidence`, `source_labels`, `kev`, `epss` e `risk`.

## Testes locais

```bash
cd backend
python -m ruff check src tests
python -m pytest tests
```

Os testes usam `monkeypatch` e fixtures offline para NVD, KEV e EPSS. Nao dependem da rede real.
