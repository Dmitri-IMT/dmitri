# API Planning Notes

This document captures the initial guidelines for the REST API that links the hardware agent, backend, and mobile client. No routes are implemented yet.

## Guiding Principles
- **Contract-first**: Every endpoint must be documented in `contracts/openapi/openapi.yaml` and covered by JSON Schemas before implementation.
- **Versioned APIs**: Use `/api/v1` as the initial prefix. Future breaking changes should roll out under `/api/v2`, etc.
- **Security**: All endpoints must require HTTPS, use token-based authentication, and validate payloads server-side.
- **Observability**: Include structured logging and tracing identifiers from the agent to the backend for correlation.

## Planned Endpoint Groups
1. **Ingestion**
   - `POST /api/v1/scans` — Receives scan results produced by the hardware agent. Payload conforms to `scan_result.schema.json`.
   - `POST /api/v1/devices/{device_id}/findings` — Placeholder for future manual finding submissions.
2. **Reporting**
   - `GET /api/v1/scans` — Paginated listing of scan metadata.
   - `GET /api/v1/scans/{scan_id}` — Detailed scan view, including normalized devices and findings.
   - `GET /api/v1/devices/{device_id}` — Device timeline with open ports and severity trends.
3. **Control Plane (Future)**
   - `POST /api/v1/scans/requests` — Allows mobile clients to request the backend to schedule a scan with the agent.
   - `GET /api/v1/health` — Basic readiness/liveness probes.

## Validation Strategy
- Pydantic models under `backend/src/api/schemas/` mirror data contracts.
- JSON Schema tests will live in `contracts/tests` (to be created in later phases) to guard against regressions.

## Open Questions
- How will authentication keys be provisioned to each hardware device?
- Should ingestion be batched or streamed for larger networks?
- What retention policies apply to detailed port history data?

Document decisions here before implementing any API routes.
