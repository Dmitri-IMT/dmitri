---
type: Module
title: MCP settings and browser consent
description: Compact MCP settings with a setup modal for Codex and Claude Code, copyable commands and prompts, and current-user connection controls.
resource: frontend/src/pages/settings/McpConnectionsPanel.tsx
tags: [frontend, settings, mcp, oauth, accessibility, i18n]
timestamp: 2026-10-23T00:00:00Z
---

## Purpose

Settings includes a compact MCP row when the backend enables its endpoint. Its
On/Off state reflects the current user's active connections. Turn on opens a
setup modal; approval in the local assistant's browser flow establishes access.
Configure reopens the modal while connected. Turn off revokes that user's active
connections through the existing disconnect API, then refreshes the true state.

## Key classes / functions

| Name | Responsibility | Ref |
|---|---|---|
| `McpConnectionsPanel` | Compact account control and shared wide dialog containing setup, usage, and connection management. Turn off waits for every revocation attempt and refreshes connections even after partial failure. | `frontend/src/pages/settings/McpConnectionsPanel.tsx` |
| `McpSetupGuide` | Shared Radix client tabs styled with `data-state=active` and a theme-aware gray selection, commands using the API's configured URL, sign-in instructions, padded stacked prompt buttons, and access disclosure. | `frontend/src/pages/settings/McpSetupGuide.tsx` |
| `McpAuthorize` | Validates the request token, continues through login when needed, displays server-provided consent details, and returns the authorization decision to the local assistant. | `frontend/src/pages/McpAuthorize.tsx` |
| `api/mcp` | Generated contract types through the shared authenticated HTTP client for endpoint information, consent, own connections, and disconnect. | `frontend/src/api/mcp.ts` |

## How it connects

- [Settings](./screens.md) mounts the compact row after AI usage. The shared
  `DialogShell` wide size bounds the setup modal to the viewport and scrolls long
  content. Escape and close restore focus to the opener when it remains mounted.
- [Session context](./auth.md) supplies the user id for connection query keys.
  The setup modal omits the organization/read-only banner; browser consent still
  shows the server-provided account and organization before approval.
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
- Turn off does not change the deployment-wide `MCP_PUBLIC_URL` or another user's
  connections. It disconnects current assistants; a user can authorize again.
  A partial failure shows a toast, refreshes remaining connections, and allows retry.
- `McpConnectionsPanel.test.tsx` verifies both client commands, all prompt copies,
  clipboard failure, viewer access, disabled MCP, request retry, and real
  connection removal or failure, plus modal close/focus and complete or partial
  account disconnection.
