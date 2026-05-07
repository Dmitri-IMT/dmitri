# Setup de desenvolvimento (em **menos de 15 minutos**)

## Prerequisites

- Docker + Docker Compose
- Node.js 20+ (recomendado via nvm)
- npm
- Git

## Backend Setup

```bash
# 1. Clone o repositório
git clone https://github.com/Dmitri-IMT/vulnerability-scanner-device
cd vulnerability-scanner-device/backend

# 2. Copie o exemplo de env
cp .env.example .env

# 3. Suba os serviços
docker compose up -d

# 4. Verifique se está rodando
curl http://localhost:18000/api/v1/health
# Deve retornar {"status": "ok"}

# 5. Fazer Rebuild, quando necessário
docker compose up --build

```

## Frontend Setup
(Em outro terminal)
```bash
cd frontend
npm install
npm run dev
Frontend estará em http://localhost:5173
Importante: Se o backend estiver rodando via `docker compose`, use http://localhost:18000. Se estiver rodando direto com `uvicorn`, a porta continua `8000`.
```

## Ambiente de Desenvolvimento
### (Nunca commite credenciais reais)
Atualize, caso necessário, as credenciais nos arquivos `.env` do backend e do frontend

## Pre-commit Hooks

Para garantir qualidade de código automaticamente antes de cada commit:

```bash
pip install pre-commit
pre-commit install
```
Após a instalação, o primeiro commit pode demorar alguns minutos por conta da inicialização do ambiente.
