# Backend API (FastAPI)

Backend mínimo responsável por receber resultados de varredura do agente embarcado e validar o payload conforme os contratos em `../contracts/schemas`.

## Requisitos

- Python 3.11+
- Dependências do `pyproject.toml` (instale com `pip install -e .[dev]` dentro de `backend/`)

## Como executar

```bash
cd backend
uvicorn api.main:app --reload --app-dir src
```

O servidor ficará disponível em `http://127.0.0.1:8000`.

## Endpoints

- `GET /` → responde `{"status": "ok"}`.
- `POST /scans` → recebe um JSON igual ao contrato `scan_result.schema.json` e retorna:

```json
{
  "message": "scan received successfully",
  "scan_id": "<uuid>",
  "devices_received": 2
}
```

## Testando com o payload de exemplo

Com o servidor rodando, execute a partir da raiz do monorepo:

```bash
curl -X POST http://127.0.0.1:8000/scans \
  -H "Content-Type: application/json" \
  --data @contracts/examples/scan_result.example.json
```

Você deve ver o mesmo `scan_id` do arquivo de exemplo e `devices_received` igual à quantidade de dispositivos listados.
