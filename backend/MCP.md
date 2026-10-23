# Read-only Dmitri MCP

The MCP endpoint reads uploaded scans from this backend's database. Production
therefore returns real retained production scans; a development backend returns
development data. Results stored only on a disconnected NSPi are unavailable.

## Enable locally

Install the backend dependencies with `uv sync --extra dev`. Apply Alembic through
the normal migration process before starting the API. Revision `20261022_45`
adds the MCP tables after `20261022_44`.

Set these values in `backend/.env` and restart the API:

```dotenv
MCP_PUBLIC_URL=http://127.0.0.1:8000/mcp
APP_BASE_URL=http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

Start the API and frontend using the normal local setup. The frontend must run
at `APP_BASE_URL` for browser sign-in and consent. Leave `MCP_PUBLIC_URL` empty
to disable the MCP endpoint and hide the Settings connection panel.

Codex setup:

```bash
codex mcp add dmitri --url http://127.0.0.1:8000/mcp
codex mcp login dmitri
```

Claude Code setup:

```bash
claude mcp add --transport http --scope user dmitri http://127.0.0.1:8000/mcp
```

Then open Claude Code, run `/mcp`, select Dmitri and authenticate. In either
client, the browser opens Dmitri. Sign in with an existing account, check the
organization and local client, and approve read access.

Try: "Show the machines and Modbus observations in my latest NSPi scan. Cite
the scan and state any evidence or coverage gaps."

When enabled, **Settings → MCP** shows a compact account control. **Turn on** opens
the setup modal with the configured endpoint in copyable Codex and Claude Code
commands, browser sign-in steps, example prompts, permissions, and the signed-in
user's connections. **Configure** reopens it while connected. The On/Off state
reflects actual active connections; access starts only after browser approval.
**Turn off** revokes all current connections for that account, with a retry if
some revocations fail. It does not disable the deployment endpoint or other users.

## Production activation

1. Deploy the backend and frontend changes together using the normal release
   process. Apply the migration with the existing direct migration credentials.
2. Set `MCP_PUBLIC_URL` on the API to its actual public HTTPS endpoint ending
   exactly in `/mcp`, for example `https://api.example.com/mcp`. Do not use the
   frontend hostname unless it routes to this API.
3. Keep `APP_BASE_URL` set to the deployed frontend origin and include that origin
   in `CORS_ALLOWED_ORIGINS`. Restart the API after configuration changes.
4. Check `/.well-known/oauth-authorization-server` and
   `/.well-known/oauth-protected-resource/mcp` on the API origin. An unauthenticated
   request to `/mcp` must return 401 with `WWW-Authenticate` metadata.
5. Add the production URL to each local client instead of the development URL.
   Each person authorizes their own Dmitri account. A public MCP directory
   listing is not needed for direct client configuration.
6. Verify a known production NSPi scan against the website, including its
   industrial observations. Check a second organization cannot read it. Revoke
   the connection in Settings and verify the client loses access.

There is no extra model API key, shared admin token, or new identity-provider
account to configure. Existing Dmitri accounts authorize individual connections.
The MCP does not invoke Dmitri's AI worker or contact devices.

## Access rules

- SDK-managed OAuth authorization-code flow with S256 PKCE and dynamic client
  registration. This release supports local public clients using
  `token_endpoint_auth_method=none` and HTTP loopback callbacks only.
  A later sign-in may change the loopback port; the host and path must still
  match registration, and token exchange must use the exact authorized URL.
- Access tokens last up to 15 minutes. Refresh tokens rotate within a fixed
  30-day connection. Reusing a refresh token revokes that connection.
- Credentials and authorization codes are stored as hashes. Connections are
  bound to the configured resource URL, user and organization. Moving the public
  URL requires users to connect again.
- Membership, connection expiry, revocation and password changes are checked on
  every authenticated request and again before executing reads. Removing a
  user removes their connections through foreign-key cascades.
- Viewers and admins get the same `dmitri:read` scope. MCP credentials are opaque
  and cannot authenticate to the existing JWT-based API, including write routes.
- Settings lists only the current user's connections. Disconnect revokes access
  and refresh credentials immediately; it cannot recall data already returned.
- Clients send requested results to their configured model provider. The consent
  page explains this. Client names are declared by clients, not independently
  verified identities.

## Tools and response limits

| Tool | Data |
|---|---|
| `get_account_context` | Account, organization and scope |
| `list_scans` | Newest first; mode, device, status and timezone-aware date filters |
| `get_scan` | Stored scan status, date, counts and coverage |
| `list_scan_machines` | Machine IDs and identities observed in that scan |
| `get_scan_machine` | Historical identity, ports or industrial services; optional port/unit filters |
| `list_machines` | Current inventory; separate active/quiet groups |
| `get_machine` | Current machine summary and website link |
| `list_findings` | Organization-scoped summaries with scan/machine/severity filters |
| `get_finding` | Confidence, evidence status and paged supporting evidence |

Lists accept 1–25 results per page and return `next_page`. Evidence text is
returned in 4,000-character chunks using `next_evidence_offset`. Responses flag
`truncated` and `truncated_fields` when nested content exceeds the response
budget; narrow the request or follow the source link. A truncated result is
never evidence that the omitted data is absent.

Machine inventory reflects the latest stored observation. Use scan-specific
tools when asking about an older scan. No tool can execute SQL, start or cancel
scans, generate AI analyses, update devices, delete records, or manage members.

Requests have a 16 KiB body limit. The API applies per-process, per-peer limits
of 120 MCP requests and 60 OAuth requests per minute. Read queries use a 10-second
Postgres statement timeout. The endpoint is stateless; authorization and tokens
are persisted, while rate counters reset when the API restarts. Shared ingress
limits are needed if the deployment later adds multiple API replicas.

## Verification

Run `./database.sh --test` from the repository root and the backend Ruff check.
`backend/tests/test_mcp.py` exercises the actual SDK HTTP routes against the
migrated `dmitri_test` database, including PKCE, refresh reuse, revocation,
organization isolation, historical evidence and industrial observations.

Frontend checks are lint, typecheck, tests and build. Consent and connection
panel tests cover sign-in continuation, disclosure, decisions, disconnect, retry
and toast errors. Production sign-in remains an activation smoke test.
