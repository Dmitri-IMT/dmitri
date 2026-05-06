# Backend API (FastAPI)

Backend responsavel por receber resultados do `hardware-agent`, persistir scans/dispositivos/portas/servicos/CPEs/findings, enfileirar jobs de enrichment e correlacionar CVEs com a NVD.

## Requisitos

- Python 3.11+
- dependencias do `pyproject.toml`

Instalacao local:

```bash
cd backend
python -m pip install -e ".[dev]"
```

## Como executar

```bash
cd backend
python -m uvicorn api.main:app --reload --app-dir src
```

O servidor fica disponivel em `http://127.0.0.1:8000`.

Banco local default:

- se `DATABASE_URL` nao for definido, o backend usa `sqlite:///./scanner.db`
- em producao, configure `DATABASE_URL` para PostgreSQL

Variaveis relevantes:

- `DATABASE_URL`
- `NVD_API_BASE_URL`
- `NVD_API_KEY`
- `NVD_CACHE_TTL_HOURS`
- `PROCESS_ENRICHMENT_INLINE`

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
- `GET /findings` e `GET /api/v1/findings` -> lista findings persistidos com filtros simples

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
- cache local de consultas NVD
- correlacao CPE -> CVE e deduplicacao entre sinais do scan e enrichment
- score de confianca: `tentative`, `probable`, `confirmed`

## Testando com o payload de exemplo

Com o servidor rodando, execute a partir da raiz do monorepo:

```bash
curl -X POST http://127.0.0.1:8000/scans \
  -H "Content-Type: application/json" \
  --data @contracts/examples/scan_result.example.json
```

Ou usando o caminho versionado:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/scans \
  -H "Content-Type: application/json" \
  --data @contracts/examples/scan_result.example.json
```

Depois consulte:

```bash
curl http://127.0.0.1:8000/api/v1/scans
curl http://127.0.0.1:8000/api/v1/findings
```

Voce deve ver o mesmo `scan_id` do arquivo de exemplo, historico persistido e findings com `confidence` e `source_labels`.
