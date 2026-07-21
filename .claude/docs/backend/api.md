---
type: Entry Point
title: Backend entry points & config
description: The FastAPI app (health-only), the worker process entry, settings, and the DB engine/session.
resource: backend/src/api/main.py
tags: [backend, entrypoint, fastapi, config, database]
timestamp: 2026-07-21T00:00:00Z
---

# Backend entry points & config

## Purpose

The four files that boot and configure the backend: the FastAPI **API** process (`main.py`), the
**worker** process (`worker_main.py`), the pydantic-settings configuration (`core/config.py`), and
the SQLAlchemy engine/session factory (`db/session.py`). Together they define how each process
starts, how it is configured from the environment, and how it reaches Postgres.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `app` | The `FastAPI` instance, title `"Dmitri Backend"`, version read from installed `backend-api` metadata. `docs_url`/`redoc_url`/`openapi_url` are **all `None`** — interactive docs and the generated schema are disabled because the published contract is the system of record. | `backend/src/api/main.py:18` |
| `get_settings()` (import-time call) | Called at module import so a missing/invalid `DATABASE_URL` **fails fast** at startup. | `backend/src/api/main.py:16` |
| `read_health()` | The **only** registered route, `GET /api/v1/health`. Runs a real `SELECT 1` through a `get_session` dependency; returns `{"status": "ok", "version": ...}`, or a `503` `database_unreachable` error envelope on `SQLAlchemyError`. | `backend/src/api/main.py:27` |
| `main()` | Worker process entry. Configures INFO logging, calls `run_worker_loop()`, returns `0`; run as `python -m api.worker_main` (or the `backend-worker` script). | `backend/src/api/worker_main.py:8` |
| `Settings` | pydantic-settings `BaseSettings` (env + `.env`, `extra="ignore"`). Fields: `database_url` (`SecretStr`, validated to a Postgres URL), the KEV/EPSS/NVD base URLs + cache TTLs, optional `nvd_api_key`, and `enrichment_poll_interval_seconds` (5.0) / `enrichment_batch_size` (10). | `backend/src/api/core/config.py:22` |
| `normalize_postgres_url()` | Rewrites any accepted Postgres scheme to `postgresql+psycopg://`; **rejects** unknown schemes (no SQLite). Used by both config validation and the engine. | `backend/src/api/core/config.py:16` |
| `get_settings()` | `lru_cache`d `Settings` accessor (singleton). | `backend/src/api/core/config.py:62` |
| `get_engine()` | `lru_cache`d engine from the normalized `DATABASE_URL`, with `pool_pre_ping=True` and `connect_args={"prepare_threshold": None, "connect_timeout": 10}` — required for the pgbouncer/Supabase pooler. | `backend/src/api/db/session.py:11` |
| `get_session()` | Generator yielding a `Session` in a context manager; the FastAPI dependency and the worker's session source. | `backend/src/api/db/session.py:22` |
| `reset_db_state()` | Test helper clearing the engine + settings caches. | `backend/src/api/db/session.py:27` |

## How it connects

- `read_health` depends on `get_session`, which yields sessions bound to the `get_engine` engine
  built from `Settings` — all four files in this doc form the boot chain.
- The worker entry delegates to `run_worker_loop()` in [services](/backend/services.md).
- `Settings` cache TTLs and the poll interval/batch size are consumed by the enrichment
  [services](/backend/services.md) (NVD/KEV/EPSS clients and the worker loop).
- `normalize_postgres_url` is reused by the Alembic env — see [migrations](/backend/migrations.md).

## Notes / gotchas

- **Not wired.** Only `GET /api/v1/health` is registered. The ingest (`POST /api/v1/scans`) and read
  routes described in [contracts](/contracts.md) are contract-defined but absent from `main.py`;
  `persist_scan` and the worker are driven by tests, not HTTP. This is a standing fact — do not "add"
  the routes when documenting.
- Disabling `openapi_url` means FastAPI serves **no** generated schema; the hand-authored
  `contracts/openapi/openapi.yaml` is authoritative.
- The worker uses `time.sleep`, not FastAPI — it never imports `app`.

# Citations

[1] [specs/013-backend-app-shell-rebuild](../../../specs/013-backend-app-shell-rebuild/TRUTH.md)
[2] [docs/adr/ADR-003-backend-stack.md](../../../docs/adr/ADR-003-backend-stack.md)
[3] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
