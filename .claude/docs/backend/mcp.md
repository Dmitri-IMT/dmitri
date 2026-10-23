---
type: Module
title: Read-only MCP
description: Optional Streamable HTTP MCP with browser consent, persistent per-user OAuth connections and organization-scoped scan evidence reads.
resource: backend/src/api/mcp_server.py
tags: [backend, mcp, oauth, auth, reads]
timestamp: 2026-10-22T00:00:00Z
---

## Purpose

Local Codex and Claude Code connect to the deployed backend to read uploaded
scans. `MCP_PUBLIC_URL` enables the endpoint at startup. Browser consent uses
the existing user session and frontend at `APP_BASE_URL`.

## Key classes / functions

| Name | Responsibility |
|---|---|
| `create_mcp_server` | Official SDK transport, nine read tools, OAuth metadata and registration |
| `McpBoundaryMiddleware` | Body and request limits, resource validation, no-store responses |
| `DmitriOAuthProvider` | SDK provider adapter; DB work runs in the thread pool |
| `active_connection` | Current user, organization, resource, password, expiry and revocation checks |
| `execute_read` | Organization-scoped service calls and historical observations |
| `bounded_result` | Nested response limits with explicit truncation fields |

## How it connects

- `main.py` mounts the optional SDK app after normal FastAPI routes and runs its
  session manager in the API lifespan.
- `routers/mcp.py` exposes authenticated info, authorization preview/decision,
  own connection list and disconnect under `/api/v1/mcp`.
- `models/mcp.py` persists clients, authorization requests, connections and hashed
  credentials. Migration `20261022_45` adds the tables, runtime grants and RLS.
- `services/mcp_reads.py` reuses read serializers and SQL organization gates.
  `read.list_scans` additionally accepts mode and date filters for MCP callers;
  existing HTTP and Home callers keep their defaults.
- Frontend `McpAuthorize.tsx` and `settings/McpConnectionsPanel.tsx` use generated
  API types and the existing HTTP clients. Login preserves a validated MCP request.

## Notes / gotchas

- Opaque MCP credentials cannot authenticate to existing JWT routes. Admin MCP
  connections have no additional operational permissions.
- Only public local clients and loopback callbacks are supported. Access lasts
  15 minutes, with rotating refresh credentials for a fixed 30-day connection.
- Current inventory and historical scan observations are distinct. Industrial
  observations come from stored scan data, never a live device request.
- See [setup and activation](../../../backend/MCP.md) for environment, client
  commands, limits, and production smoke tests.
