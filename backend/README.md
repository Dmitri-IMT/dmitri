# Backend API (FastAPI)

Backend responsavel por receber resultados do `hardware-agent`, persistir scans/dispositivos/portas/servicos/CPEs/findings, enfileirar jobs de enrichment e executar o enrichment em um worker dedicado.

O enrichment atual cruza `cve_id` com:

- NVD para validacao/correlacao complementar
- CISA KEV para exploracao conhecida
- FIRST EPSS para probabilidade de exploracao

Com isso, cada finding pode expor `kev`, `epss` e um `risk_score` inicial explicavel.

Este README cobre apenas o shell atual (boot, config, migracao, health). Rotas de negocio
(`/scans`, `/findings`, etc.) ainda nao existem neste shell — chegam em issues futuras.

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
- `NVD_API_BASE_URL`, `NVD_API_KEY`, `NVD_CACHE_TTL_HOURS`
- `ENRICHMENT_POLL_INTERVAL_SECONDS`, `ENRICHMENT_BATCH_SIZE`

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

## Endpoint

Esta versao do shell expoe apenas o health check contratado:

- `GET /api/v1/health` -> `{"status": "ok", "version": "<versao instalada de backend-api>"}` somente apos um round-trip real ao banco (`SELECT 1`); `503` com um envelope de erro estatico se o banco estiver inacessivel.

`/docs`, `/redoc` e `/openapi.json` estao desabilitados; o contrato publicado e
`../contracts/openapi/openapi.yaml`. Nenhuma outra rota (incluindo as antigas rotas de
negocio de scans/findings) esta registrada neste shell.

## Regra inicial de risco (engine mantido, sem mudanca de comportamento)

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
