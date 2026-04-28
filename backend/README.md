# Backend API (FastAPI)

Backend minimo responsavel por receber resultados de varredura do hardware-agent e validar o payload conforme os contratos em `../contracts/schemas`.

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

## Endpoints

- `GET /` -> responde `{"status": "ok"}`
- `GET /api/v1/health` -> responde `{"status": "ok"}`
- `POST /scans` -> recebe um JSON compativel com o contrato compartilhado
- `POST /api/v1/scans` -> alias versionado usado pelo agente

Resposta esperada de ingestao:

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

Ou usando o caminho versionado:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/scans \
  -H "Content-Type: application/json" \
  --data @contracts/examples/scan_result.example.json
```

Voce deve ver o mesmo `scan_id` do arquivo de exemplo e `devices_received` igual ao numero de dispositivos listados.
