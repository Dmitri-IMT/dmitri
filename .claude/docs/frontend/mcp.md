---
type: Module
title: MCP settings and browser consent
description: Inline MCP setup for Codex and Claude Code, copyable commands and prompts, browser consent, and current-user connection management.
resource: frontend/src/pages/settings/McpConnectionsPanel.tsx
tags: [frontend, settings, mcp, oauth, accessibility, i18n]
timestamp: 2026-10-23T00:00:00Z
---

## Purpose

Settings includes an MCP section when the backend enables its endpoint. It shows
the signed-in user's organization, guides local assistant setup, explains the
read boundary, and lists that user's live connections. Browser authorization
uses the existing Dmitri account and organization.

## Key classes / functions

| Name | Responsibility | Ref |
|---|---|---|
| `McpConnectionsPanel` | Reads endpoint information and user-scoped connections, hides disabled MCP, displays organization scope, and revokes individual connections. | `frontend/src/pages/settings/McpConnectionsPanel.tsx` |
| `McpSetupGuide` | Shared Radix client tabs, commands using the API's configured URL, browser sign-in instructions, copyable evidence-aware prompts, and access disclosure. | `frontend/src/pages/settings/McpSetupGuide.tsx` |
| `McpAuthorize` | Validates the request token, continues through login when needed, displays server-provided consent details, and returns the authorization decision to the local assistant. | `frontend/src/pages/McpAuthorize.tsx` |
| `api/mcp` | Generated contract types through the shared authenticated HTTP client for endpoint information, consent, own connections, and disconnect. | `frontend/src/api/mcp.ts` |

## How it connects

- [Settings](./screens.md) mounts the panel after AI usage. Setup is an inline
  section, with no new Settings route or navigation tab.
- [Session context](./auth.md) supplies the organization name and user id.
  Connection query keys include the current user id.
- The [backend MCP](../backend/mcp.md) publishes the configured endpoint through
  `GET /api/v1/mcp/info`. Setup never derives it from the frontend hostname or
  substitutes a sample endpoint.
- Commands start authorization in the local CLI. The Settings page does not
  manufacture a consent request or simulate an approved connection.
- English, Brazilian Portuguese, and Russian catalogs cover setup, prompts,
  permissions, and clipboard feedback. Clipboard and request failures use the
  shared toast; failed copies leave their source text available.

## Notes / gotchas

- The guide describes uploaded scans, machine observations, findings, evidence,
  current organization membership, and the assistant's model-provider boundary.
  It does not imply live access to an NSPi or permission to change data.
- Returning focus to Settings lets TanStack Query refresh the connection list
  after browser approval. Disconnect invalidates that user's list.
- `McpConnectionsPanel.test.tsx` verifies both client commands, all prompt copies,
  clipboard failure, viewer access, disabled MCP, request retry, and real
  connection removal or failure.
