# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

## 2026-08-03

* **Update**: IPv4 narrowing threaded to the agent side — `hardware-agent/normalize.md`'s
  `HostPayload`/`FindingPayload` rows now read `IPv4Address` (was `IPvAnyAddress`) and note the
  nullable `mac`/`ip`. Both ends of the ingest contract agree again: the backend began rejecting
  IPv6 with a 422, so leaving the emitter on `IPvAnyAddress` would have turned an unreachable
  mismatch into a lost scan submission at HTTP time rather than a clean error at normalize time.
  Line refs shifted by one from the new `ipaddress` import.
* **Update**: read-path link fields + nullability landed (DMI-85) — `backend/schemas.md` records
  three changes to `schemas/read.py` and `schemas/scan.py`. **IPv4 only:** every address field is
  now `IPv4Address` rather than `IPvAnyAddress`, matching the contract's long-standing
  `format: ipv4` and the IPv4-only `SubnetCIDR` regex; ingest rejects an IPv6 host or finding with a
  422. **`mac` is required-but-nullable** on `ScanHostView`/`HostSummary`/`HostDetailResponse` — a
  routed host has no MAC, and the previous non-nullable `constr` meant any such host 500'd on
  `GET /hosts`. **Collection fields lost their `default_factory`** (`ports`, `scan_history`,
  `hosts`, `findings`): the service always passes them, and a default made FastAPI publish them as
  optional, which weakened the generated frontend types. `contracts.md` gains the matching
  `required`/nullability paragraph plus a note on what `test_contract_fidelity.py` does and does
  not guard — `/api/v1/hosts` query params stay unguarded until DMI-100 implements
  `sort_by`/`sort_order`. Line refs in both `read.py` and `scan.py` tables shifted by one from the
  new `ipaddress` import.

## 2026-08-02

* **Update**: `GET /hosts` paging landed (DMI-84) — `backend/routers.md`'s `read_hosts()` row now
  records the `page`/`per_page` query params, and the "`read_hosts` still ignores contract
  `page`/`per_page`" gotcha is **gone**: all three list routes now declare the same
  `Query(1, ge=1)` / `Query(20, ge=1, le=100)` constraints, so out-of-range paging is refused with a
  422 rather than clamped. `backend/services.md`'s `list_hosts()` row gains the `HostRecord.id`
  tie-breaker after `last_seen_at desc` (stable paging under tied timestamps, matching what
  `list_scans` already did). Also repaired drifted `path:line` refs in both tables — every
  `services/read.py` ref and the four router refs were stale by 1–22 lines.
* **Update**: transactional email landed (DMI-71) — `backend/auth.md`'s `Mailer` row rewritten: the
  `LogMailer` dev stand-in is **gone**, replaced by `ResendMailer` (plain-text POST to the Resend
  API, failures swallowed into a token-free `logger.error`), `NullMailer` for the unset-key case,
  `BackgroundMailer`, the `invite_link`/`reset_link` builders, and `get_mailer(tasks)`. Tokens still
  cross the service boundary raw; the mailer is now the one place a token becomes a URL, via
  `APP_BASE_URL`. Two new gotchas: the no-enumeration guarantee now covers **timing** (the send is a
  background task, so response latency no longer reveals whether mail went out, and the request's DB
  session is released before the provider is called), and email is best-effort — a Resend outage
  costs an email, never an invite.
* **Update**: `backend/api.md` — six new `Settings` fields (`RESEND_API_KEY`, `RESEND_API_BASE_URL`,
  `MAIL_FROM`, `MAIL_REPLY_TO`, `MAIL_TIMEOUT_SECONDS`, `APP_BASE_URL`), and an unset `RESEND_API_KEY`
  recorded as a supported production state rather than a boot failure.
* **Update**: `backend/management.md` — dropped the stale "`LogMailer` still logs the token on the
  HTTP invite path" risk, which DMI-71 resolved, and recorded why `_SilentMailer` is still not
  redundant with the new `NullMailer` (deliberate silence vs unconfigured).

## 2026-07-31

* **Update**: post-DMI-64 cleanup — `MAINTAINING.md`'s "current vs target state" standing fact
  rewritten (the backend is no longer "working code but nothing calls it"; ingest and the Pi daemon
  are the two remaining gaps), `backend/api.md` (`command_running_timeout_seconds` deleted from
  `Settings` — it had no consumer), `backend/services.md` (`apply_status` gains an
  `AND scan_id IS NOT NULL` predicate and `deliver` a zero-rowcount rollback, closing both races in
  the delivery `await` window; recorded that D9's "rank resolves the early-`running` race" claim is
  inaccurate once D1's CHECK exists).
* **Update**: backend command channel wired end to end (spec 022 / DMI-64) — `backend/services.md`
  (new `commands.py` rows for `enqueue`/`active_command_for`/`apply_status`/`sweep_stale_commands`/
  `deliver`, new `agent_presence.py` rows, `command_lifecycle`'s pairwise `_LEGAL_EDGES` replaced by
  `status_rank`/`is_terminal`, `agent_ws` now takes a session **factory** and opens one session per
  frame in a threadpool, `run_worker_once` sweeps before enriching; the "schema-only / not-yet-wired"
  notes are gone and are replaced by notes on owner-split transitions, silent zero-rowcount,
  written-not-derived staleness, and connection-loss rather than elapsed-time timeouts),
  `backend/routers.md` (`POST /agents/{id}/commands`, `GET /commands/{id}`, presence calls on the WS
  handler; 403-not-404 and the shared 409 body), `backend/models.md` (`commands.scan_id` nullable
  under `CHECK (scan_id IS NOT NULL OR status IN ('queued','expired'))`, the partial unique index,
  `agents.connected_at`), `backend/migrations.md` (rev `20260731_13`; the baseline's `CREATE ROLE`
  guard and why cluster-scoped roles vs database-scoped migrations made the whole DB suite skip),
  `backend/schemas.md` (new `schemas/commands.py` section; optional `scan_id`), `backend/api.md`
  (startup `reconcile_all`, the commands router, the two new settings — and that
  `command_running_timeout_seconds` has no consumer), `backend/index.md` and `contracts.md`. `apiClient`/
  `authClient` were documented at `client.ts:7`/`:9`; they are created in `instances.ts`, which the
  doc did not mention at all. The recorded "deliberate lazy circular import" between `client.ts` and
  `auth.ts` no longer exists. Both errors sat over a **live bug**: `users`/`scans`/`findings`
  imported `apiClient` from `instances.ts`, so nothing in the app imported `client.ts`, the
  interceptors were never attached, and every authenticated request in the browser 401'd while the
  suite stayed green (the only importer of `./client` was its own test). Fixed in code; the import
  direction and the isolation the guard test needs are now both recorded.
* **Update**: `frontend/overview.md` (`src/api/` layout row split `instances.ts` from `client.ts`;
  `agents.ts` + its MSW handler deleted as unused), `frontend/review.md` (`useQueries` over
  `HOME_SEVERITIES`; `skipToken` replaces `enabled` + the `scanId as string` cast),
  `frontend/screens.md` (`TopBar` three-track grid centring its lone nav item — transitional, see
  SCREENS.md §App shell; `cursor-pointer` added to the vendored shadcn button base because Tailwind
  v4 preflight sets `cursor: default`).
* **Update**: `backend/api.md`, `backend/schemas.md`, `backend/models.md` — `Severity` and
  `SEVERITY_ORDER` moved from `schemas/read.py` to a new dependency-free `core/severity.py`, so the
  model layer spells the `ck_findings_severity` constraint without importing the schema layer above
  it. Importers updated in `models/persistence.py`, `services/read.py`, `services/hosts.py`,
  `routers/findings.py`.

## 2026-07-29

* **Creation**: `frontend/auth.md` (SessionProvider / useSession / RequireSession),
  `frontend/review.md` (`deriveReview` + `useHomeReview`), `frontend/screens.md` (Login, Home,
  NotFound, the two shells, top bar, shared components).
* **Update**: spec 020 frontend vertical slice login → Home — the SPA is no longer stub-only.
  `frontend/overview.md` (real screens, light-only token layer, the blocked `GET /agents/{id}`
  read), `frontend/api.md` (`authEvents` replaces the hard `window.location` redirect; new
  `users`/`scans`/`findings`/`agents` read modules), `frontend/app.md` (rewritten: provider nest +
  route table only, no session state), `frontend/index.md`. Notable seams recorded: the boot
  refresh is a query, not an Effect (StrictMode × rotating refresh token); sign-out cannot use a
  bare `queryClient.clear()` while the `['session']` observer is live; end-stop deck arrows are
  absent rather than disabled.

## 2026-07-27

* **Update**: spec 021 (DMI-82) scan list + finding filters — `GET /api/v1/scans`
  (`list_scans`, `ScanSummary`/`ScanListResponse`), widened `GET /api/v1/findings`
  (`severity`/`scan_id` filters, stable `FindingRecord.id` paging), `ck_findings_severity`
  migration, `SEVERITY_ORDER` promotion, `test_contract_fidelity.py`. Updated
  `backend/routers.md`, `services.md`, `schemas.md`, `models.md`, `migrations.md`, `log.md`.
  Pre-push follow-up (nuke): `SEVERITY_ORDER` moved from `services/hosts.py` to
  `schemas/read.py`, derived from the `Severity` literal — `models/persistence.py` had been
  importing a *service* to build its check constraint, whose import cycle forced deferred
  model imports and an untyped `scan_record` param in `hosts.py`; both reverted. Migration
  `20260727_12` no longer imports `api.*` (a revision is frozen history), with a drift test
  in `test_finding_severity_migration.py`. `list_scans`/`list_findings` now take
  `ScanStatus`/`Severity` instead of `str`. `test_read_service.py` split — scan-list cases to
  `test_read_service_scans.py`, shared builders to `tests/read_factories.py`.
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
