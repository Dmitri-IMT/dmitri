# API Planning Notes

This document captures the initial guidelines for the REST API that links the hardware agent, backend, and mobile client.

## Guiding Principles
- **Contract-first**: Every endpoint must be documented in `docs/api/openapi.yaml` before implementation.
- **Versioned APIs**: Use `/api/v1` as the initial prefix. Future breaking changes should roll out under `/api/v2`, etc.
- **Security**: All endpoints must require HTTPS, use token-based authentication, and validate payloads server-side.
- **Observability**: Include structured logging and tracing identifiers from the agent to the backend for correlation.

## Planned Endpoint Groups
1. **Ingestion**
   - `POST /api/v1/scans` Receives scan results produced by the hardware agent. Payload conforms to the scan ingest schema.
2. **Reporting**
   - `GET /api/v1/scans`  Paginated listing of scan metadata.
   - `GET /api/v1/scans/{scan_id}`  Detailed scan view, including normalized devices and findings.
   - `GET /api/v1/devices`  Host inventory list.
   - `GET /api/v1/devices/{device_id}`  Device detail with scan history.
   - `GET /api/v1/findings`  Filtered findings listing.
3. **Platform**
   - `GET /api/v1/health`  Basic readiness/liveness probe.

## Validation Strategy
- Pydantic models under `backend/src/api/schemas/` mirror the ingest contracts.
- JSON Schema tests will live in `contracts/tests` (to be created in later phases) to guard against regressions.
- The legacy copy at `contracts/openapi/openapi.yaml` is kept aligned with `docs/api/openapi.yaml` for compatibility with older references.

## Open Questions
- How will authentication keys be provisioned to each hardware device?
- Should ingestion be batched or streamed for larger networks?
- What retention policies apply to detailed port history data?

Review and approve the contract before implementing the routes.
