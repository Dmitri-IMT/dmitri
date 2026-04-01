# API Notes

## Fonte de verdade

- Contrato OpenAPI: `docs/api/openapi.yaml`
- Copia sincronizada: `contracts/openapi/openapi.yaml`
- Decisao arquitetural de seguranca: `docs/adr/ADR-005-security-model.md`

## Seguranca v1

- `POST /api/v1/scans`: autenticacao do agente via HMAC-SHA256 por device
- endpoints consumidos pelo frontend: JWT Bearer
- cookie de refresh fica fora do contrato atual de negocio e sera modelado em endpoints de auth futuros
- producao usa HTTPS; HTTP fica restrito ao desenvolvimento local
- CORS permitido apenas para `http://localhost:5173` e `https://app.vscanner.example.com`
