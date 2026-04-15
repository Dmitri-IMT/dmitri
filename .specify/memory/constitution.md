<!--
Sync Impact Report
- Version change: template → 1.0.0
- Modified principles: N/A (initial adoption; placeholders replaced)
- Added sections: Core Principles (5); Technology & Platform Constraints; Development Workflow & Quality Gates; Governance
- Removed sections: none
- Templates requiring updates:
  - .specify/templates/plan-template.md — ✅ updated (Constitution Check gates)
  - .specify/templates/spec-template.md — ✅ updated (TDD / constitution reference)
  - .specify/templates/tasks-template.md — ✅ updated (tests default mandatory per TDD)
- Follow-up TODOs: none
-->

# Vulnerability Scanner Device Constitution

## Core Principles

### I. Test-Driven Development (NON-NEGOTIABLE)

New behavior is delivered using **Test-Driven Development**: express intent as a failing automated test first, confirm the test fails for the right reason, then implement the minimum code to pass, then refactor. The Red–Green–Refactor cycle applies to application code, API contracts, and critical data transforms. Skipping tests-before-implementation requires a written exception in the feature spec with stakeholder rationale (e.g., spike, third-party-only glue).

**Rationale**: TDD locks in expected behavior, prevents regressions on the embedded agent and cloud API boundary, and keeps the codebase safe to change under thesis timelines.

### II. Contract-First Integration

The **OpenAPI specification** and **shared JSON Schemas** under `contracts/` are the source of truth for payloads between the hardware agent, backend, and frontend. Changes to externally visible behavior MUST update schemas and examples before or alongside code. Generated or hand-maintained client types (e.g., TypeScript from OpenAPI) MUST stay aligned with the published contract.

**Rationale**: The system is distributed (Pi, cloud API, SPA); contract drift causes production failures that unit tests alone will not catch.

### III. Authorized, Passive-First Scanning

The product performs **network scanning from outside targets** on **authorized** networks only. The v1 scanning pipeline is **passive / observation-first**: discovery, port scan, service detection, and CVE correlation (e.g., Nmap, NSE, vulners NSE) without exploitation, credential brute force, or post-exploitation tooling. Tools and techniques that are **excluded or deferred** in `docs/adr/` (e.g., Metasploit, OpenVAS on-device, masscan as default) MUST NOT be introduced without a new ADR and explicit approval.

**Rationale**: Matches documented ethics, legal, and hardware constraints and keeps the device deployable as an audit tool rather than an offensive weapon.

### IV. Security Model & Transport

**Agent → API (v1)**: request authentication uses **HMAC-SHA256 per device** with the canonical headers and rules defined in ADR-005 (`X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Body-SHA256`, `X-Signature`). Simple `X-API-Key` alone is not v1. **Frontend → API (v1)**: **`Authorization: Bearer <JWT>`** on documented endpoints; session-cookie-only auth is not v1. **CORS** MUST follow the closed allowlist (dev localhost + production app origin); no wildcard origins. **Production** MUST use **HTTPS**; HTTP is for local development only. Device secrets MUST NOT be committed; they live in secure provisioning and environment configuration.

**Rationale**: A single, explicit security model avoids drift between OpenAPI docs and implementation and protects sensitive scan data in transit and at the boundary.

### V. Aligned Technology Stack

Implementation MUST follow the **Architecture Decision Records** in `docs/adr/`, including: **Raspberry Pi 4 Model B (4 GB)** as the reference hardware agent platform; **FastAPI** backend; **PostgreSQL** (e.g., **Supabase**) with **SQLModel**, **asyncpg**, **Alembic** for migrations; **React + Vite + TypeScript** frontend with **React Router v6**, **TanStack Query**, **shadcn/ui**, **Recharts** as decided; **cloud-hosted** deployment with **Docker + Nginx** reverse proxy pattern for production (backend not on the Pi). Deviations require an ADR or constitution amendment before merge.

**Rationale**: Stack choices are already analyzed for performance, team skills, and Pi constraints; ad hoc substitutions recreate risk the ADRs already eliminated.

## Technology & Platform Constraints

- **Agent**: Runs on Raspberry Pi OS–class Linux; scanning uses **Nmap + NSE + vulners NSE** for v1; optional v2 tools (e.g., enum4linux-ng, testssl.sh) only when ADR-gated and scope conditions are met.
- **Backend**: FastAPI async stack; database access uses async drivers; migrations use direct PostgreSQL connection (not transaction-pooler port) for DDL per ADR-009.
- **Data**: Bulk ingest pattern for scan completion; idempotency and retention assumptions follow ADR-009 unless superseded by a newer ADR.
- **Frontend**: SPA consumes only the documented API; no duplicate ad hoc contract definitions outside generated/shared types.

## Development Workflow & Quality Gates

- **ADRs**: Material architecture or security changes go through **`docs/adr/`** with context, decision, and consequences before broad implementation.
- **TDD**: Features and fixes include tests written first per Principle I; CI MUST run the automated test suite on change.
- **Reviews**: Pull requests verify constitution compliance (contracts, security headers, scanning scope, stack).
- **Documentation**: User-facing security and responsible-disclosure expectations align with ADR-005 and scanning ADRs.

## Governance

This constitution supersedes informal conventions when they conflict. **Amendments** require: (1) a pull request that updates `.specify/memory/constitution.md` with version bump and Sync Impact Report; (2) propagation to dependent templates when principles change; (3) team review. **Versioning**: MAJOR for incompatible principle removals or redefinitions; MINOR for new principles or materially expanded guidance; PATCH for clarifications and non-semantic edits. **Compliance**: At least one reviewer per change MUST confirm gates under Development Workflow; periodic reviews align specs and ADRs with the constitution.

**Version**: 1.0.0 | **Ratified**: 2026-04-15 | **Last Amended**: 2026-04-15
