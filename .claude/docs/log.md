# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

## 2026-07-27

* **Update**: spec 019 (DMI-72) `GET /users/me` + global error envelope — `errors.py`
  (`ApiError`, `_DEFAULT_CODES_BY_STATUS`), global `StarletteHTTPException` + `Exception`
  handlers in `main.py`, WS denial envelope, C13 change-password codes, `routers/users.py`,
  `schemas/users.py`, contract + `openapi.d.ts` updates. Created `backend/errors.md`; updated
  `backend/api.md`, `routers.md`, `schemas.md`, `auth.md`, `index.md`.
  Pre-push follow-up: `http_exception_handler` now forwards `exc.headers` (the router's `405`
  had lost its RFC-required `Allow`); `validation_exception_handler` pulls `422` into the
  envelope and stops pydantic echoing the rejected password back via `input`; `errors.py` gained
  `error_envelope`/`field_path` and lost the underscore on `DEFAULT_CODES_BY_STATUS`; the four
  pinned-code responses in `openapi.yaml` gained `required:` so their `code` discriminator
  actually narrows in the generated TS.
* **Update**: spec 018 (DMI-62) agent WebSocket command channel — `routers/agents.py`
  (`connect_agent_commands`), `services/agent_connections.py` (in-process registry),
  `services/agent_ws.py` (frame dispatch), `schemas/agent_frames.py`, `require_agent_ws` adapter,
  `main.py` WS validation→403 handler, `websockets>=13` dependency. Updated
  `backend/routers.md`, `services.md`, `schemas.md`, `device-auth.md`, `api.md`, `index.md`.
  Device gate now mounted on WS; HTTP `require_agent` still unmounted; no command delivery yet.
* **Creation**: `backend/device-auth.md` — the spec 017 (DMI-61) device gate: Ed25519 canonical-string
  signing (`services/device_sig.py`, the repo's only `cryptography` importer), insert-or-replay nonce
  handling (`services/nonces.py`), and the transport-agnostic `authenticate_agent` core with its thin
  `require_agent` HTTP adapter (`dependencies/agent_auth.py`). Records the 8-step order, the
  403-for-revoked / 401-for-everything-else split, and the accepted "a burned nonce is not rolled
  back" property that DMI-62/63 must build against.
* **Creation**: `backend/management.md` — the two operator CLIs (`backend-bootstrap-org`,
  `backend-provision-agent`), including why `bootstrap_org` passes a local `_SilentMailer` rather than
  `LogMailer` (the raw admin invite token must never reach a log stream).
* **Update**: `backend/auth.md` — `require_admin` + `ROLE_ADMIN`/`ROLE_VIEWER`, the extracted
  `issue_session` / `login_response` / `set_refresh_cookie` seams, `Mailer.send_invite_link`, the
  invite service and routes, the error→status map (400/410/403), and three new gotchas: why
  `refresh_session` cannot reuse `issue_session` (refresh-token family semantics), the asymmetric
  two-scope duplicate rule, and same-commit `consumed_at` atomicity.
* **Update**: `backend/routers.md` — the four read routes now carry `Depends(require_user)` and pass
  `org_id=caller.org_id`; foreign rows are 404 not 403; `host_id` is not a tenant escape.
* **Update**: `backend/services.md` — `read.py`'s four entry points take a required keyword-only
  `org_id`, both count and page queries are scoped, and a `NULL org_id` row is visible to nobody.
* **Update**: `backend/migrations.md` — revisions `20260724_09` (`agent_nonces`), `_10`
  (`ix_users_email`, global email uniqueness), `_11` (`agents.public_key` replacing the three secret
  columns). Corrected the standing "no `DELETE` grant" note: `agent_nonces` is the deliberate
  exception (`SELECT/INSERT/DELETE`, no `UPDATE`).
* **Update**: `backend/models.md` (`AgentNonce`, `Agent.public_key` replacing the secret columns,
  global user-email uniqueness, `Invite` no longer dormant), `backend/schemas.md` (`schemas/invites.py`
  and why `extra="forbid"` is load-bearing), `backend/api.md` (`DEVICE_SIG_MAX_SKEW_SECONDS`,
  `INVITE_TTL_HOURS`), `backend/overview.md` + `backend/index.md` ("read path + auth + invites wired").
* Standing fact updated: the `orgs`/`invites` half of the "identity dormant" note is now wired.
  Ingest remains unwired, and the device gate is built but mounted on no route.

## 2026-07-24

* **Creation**: `backend/auth.md` — the spec 016 (DMI-60) auth subsystem, now wired in `main.py`:
  the 6 auth routes (`routers/auth.py`, `dmitri_refresh` cookie), the auth services (`auth.py`
  orchestration, `tokens.py` JWT + rotating refresh families, `passwords.py` argon2 + policy +
  HIBP screen, `mailer.py` seam), the `require_user` dependency (`dependencies/auth.py`), and the
  app middleware (`middleware.py` — `RequestIdMiddleware`, `NoContentCorsMiddleware` 204 preflight).
* **Update**: threaded auth through the neighboring docs — `models.md` (new `session.py`:
  `RefreshToken`/`refresh_tokens`, `PasswordResetToken`/`password_reset_tokens`; auth no longer
  dormant), `migrations.md` (rev `20260722_07_auth_sessions`), `schemas.md` (`schemas/auth.py`
  request/response models), `api.md` (required `JWT_SIGNING_SECRET` + the seven auth `Settings`
  fields, middleware + auth-router wiring in `main.py`), `services.md`/`routers.md` cross-links,
  `overview.md` + `index.md` ("read path + auth wired"). Standing fact updated: the auth half of
  the "identity dormant" note is now wired; `orgs`/`invites` and the ingest route remain unwired.

## 2026-07-23

* **Update**: Documented spec 016's command-channel data model (DMI-59) — schema + lifecycle only,
  not yet wired. New `backend/src/api/models/command.py` (`Agent`→`agents` with the AES-256-GCM
  recoverable-secret columns `secret_ciphertext`/`secret_nonce`/`secret_key_version`, `revoked_at`
  tombstone, `last_seen_at`; `Command`→`commands` with the 1:1 `scan_id` UNIQUE FK, VARCHAR `status`,
  four timestamps) — added to `backend/models.md`. New pure `services/command_lifecycle.py`
  (`next_status`, `scan_status_for`, `InvalidCommandTransition`) — added to `backend/services.md`.
  New migration `20260723_07_command_channel.py` (agents + commands with the RLS/revoke/grant fence)
  — added to `backend/migrations.md` (now seven revisions); `env.py` now imports `command`/`identity`
  explicitly. Refreshed `backend/index.md` listings. Cites ADR-011, ADR-015.

## 2026-07-22

* **Update**: Documented spec 015's read path. Backend: three new routers (`hosts.py`, `scans.py`,
  `findings.py`) mounted in `main.py` alongside `GET /api/v1/health` (new `backend/routers.md`
  doc); `services/read.py` (`list_hosts`/`get_host_detail`/`get_scan_detail`/`list_findings`) and
  `schemas/read.py` (nine read-response models, incl. `ScanHostView` with required `host_id` and
  `HostSummary` with `first_seen_at`). Persistence: `DeviceRecord`/`devices` renamed to
  `ScanHostRecord`/`scan_hosts` (a per-scan host observation); new durable `HostRecord`/`hosts`
  table (cross-scan identity, resolved by `services/hosts.py::upsert_hosts_for_scan`, ADR-014);
  `FindingRecord` gained a `finding_id` UUID; `ScanRecord` moved from `target_mode`/`scan_profile`
  to `scan_mode` + `status`. Four chained Alembic migrations (`20260722_03`–`_06`) implement this.
  Updated `backend/models.md`, `backend/schemas.md`, `backend/services.md`, `backend/migrations.md`,
  `backend/api.md`, `backend/overview.md`, `backend/index.md`. Contracts/Pi: ADR-013 retires
  `device`/`Device`/`DevicePayload` from the wire — `ScanIngestRequest.devices`→`hosts`,
  `DevicePayload`→`HostPayload`, `devices_received`→`hosts_received`; the prior `scan_mode` vs
  `target_mode`/`scan_profile` contract divergence is resolved (both sides now use `scan_mode`).
  Updated `contracts.md`, `hardware-agent/normalize.md`, `hardware-agent/scanner/stages.md`,
  `hardware-agent/scanner/runner.md`, `hardware-agent/scanner/models.md`,
  `hardware-agent/scanner/index.md`, `hardware-agent/tui.md`, `hardware-agent/overview.md`, and
  `glossary.md` (new `ScanHost` term; `Device` now "retired" not "deprecated, ingest-only").
  Refreshed `index.md` and `overview.md` at the repo root and `backend/index.md`.
* **Creation**: Added the `frontend/**` code-map section (`overview`, `api`, `app`, `index`) for the
  greenfield SPA scaffold shipped by spec 014 (frontend/): the two-Axios-instance auth client with
  the single-flight 401→refresh interceptor, the in-memory token store, the contract-typed API
  layer, and the boot-refresh + stub login/placeholder UI. Linked from the root `index.md` under a
  new "Frontend (scaffold only)" section; noted the new `frontend` CI job in `.github/workflows/ci.yml`.

## 2026-07-21

* **Update**: Corrected the README scan-modes table (Quick is default top-1000 + `vulners`, not
  `-F`) to match `discovery_arguments()`; removed the now-resolved divergence note from `overview.md`.
* **Initialization**: Created the OKF code-map bundle mapping the whole repo — top-level
  `overview` / `glossary` / `contracts`, the `hardware-agent/**` set (overview, cli, discovery,
  normalize, utils, tui, and the split `scanner/` package), the `backend/**` set (overview, api,
  models, schemas, services, migrations), the `infra/**` set (supabase, deployment), plus
  `MAINTAINING.md` and per-directory `index.md` files.
* **Note**: Corrected the scan-modes table in `overview.md` to match `discovery_arguments()` —
  Quick/Standard use the default top-1000 port set (not `-F`, as the README's product table states).
