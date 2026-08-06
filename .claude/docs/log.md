# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

## 2026-08-06

* **Creation**: `hardware-agent/daemon.md` and `hardware-agent/command-channel.md` — the Pi agent
  daemon (DMI-66, spec 026). Bare `dmitri agent` now starts `AgentDaemon`: it dials
  `GET /api/v1/agents/{device_id}/commands` over a signed WebSocket, sends a `hello` with its
  currently-enumerated subnets, executes one command at a time through the *existing*
  `run_headless_scan`, and uploads through the *existing* `ScanIngestClient` under the backend's
  `scan_id`. New modules: `transport/signing.py`, `transport/command_channel.py`, `daemon.py`.
* **Update**: **the device end of the link is wired** — `overview.md`, `index.md`,
  `contracts.md`, `MAINTAINING.md`, `hardware-agent/overview.md`, `hardware-agent/index.md`,
  `hardware-agent/transport.md`, `hardware-agent/cli.md`, `hardware-agent/utils.md`,
  `backend/schemas.md`. The long-standing "no Pi daemon posts results / no Pi client dials the WS
  channel (DMI-66)" caveat is **retired everywhere**; the remaining gap is physical (no Pi
  hardware, no service-manager packaging, no key provisioning), not code.

  Six facts worth not re-deriving:

  1. **The daemon is a third front door but not a third runner.** It calls `run_headless_scan`
     unchanged, in an `asyncio.to_thread` worker. No parameter was added to it or to `ScanRunner`,
     so the CLAUDE.md integration rule never fired.
  2. **Ed25519 envelope construction moved** out of `transport/ingest.py` into the shared
     `transport/signing.py`. The ingest `POST` and the WS `GET` upgrade now sign the same canonical
     string shape. Side effect: `ScanIngestClient.__init__` no longer builds the key object, so a
     hand-built bad `IngestConfig` raises on first `submit()` instead of at construction —
     unreachable in production because `load_ingest_config` already gates on 64 hex chars.
  3. **`AvailableSubnet.is_default_route` is now required** in OpenAPI, the backend Pydantic model
     and the generated frontend type. The model stays in Pydantic's **lax** mode like its
     neighbours, so `1` / `"true"` / `"yes"` coerce to bool and are accepted — only genuinely
     non-coercible values are rejected. That was a deliberate consistency call, not an oversight.
  4. **Hello is sent before the replay seam and before the first `recv()`**, on every reconnect,
     with a freshly enumerated list. That ordering is what makes the daemon's pending-status replay
     land after hello and before any newly delivered command.
  5. **The `>= 4000` close-code floor is a placeholder.** DMI-97 owns the concrete
     live-revocation close code; until then every 4xxx close parks. The only 4xxx the backend emits
     today is `4000/replaced`, so nothing over-parks in practice — but replace the floor when
     DMI-97 lands rather than leaving it.
  6. **`_check_nmap()` runs before the daemon module is imported**, so a missing scanner exits `20`
     without ever dialing. Exit `20` is now overloaded on that path (missing nmap *and* invalid
     ingest config), distinguishable only by stderr text.

  `websockets` is now a direct hardware-agent dependency.

## 2026-08-05

* **Creation**: `hardware-agent/transport.md` — the device-side ingest client (DMI-65, spec 025).
  New `agent.transport` package: `load_ingest_config` / `IngestConfig` / `IngestConfigError`,
  `ScanIngestClient`, `SubmissionOutcome`, `SubmissionResult`. It signs the same canonical string
  the backend's [device auth](./backend/device-auth.md) verifies, and is the opposite end of the
  wire from DMI-63's ingest route. Also updated `hardware-agent/overview.md`,
  `hardware-agent/index.md` (new "Upload" section) and `backend/device-auth.md`.
  Three facts worth not re-deriving: the client is **built but called by nothing** — no `src/agent/`
  module imports it, and wiring is DMI-66, so "no upload step yet" is now "no upload *caller* yet";
  the retry loop rebuilds the whole envelope per attempt because the backend burns a verified nonce
  *before* persisting, so reused headers would make a legitimate retry look like a replay `401`; and
  the client does **no file I/O**, taking an in-memory `ScanPayload` so the local artifact is
  untouched by success, failure, or a backend-assigned `scan_id` (applied to a `model_copy` only).
  `httpx` + `cryptography` are now direct hardware-agent dependencies.
* **Update**: `backend/device-auth.md` had a caveat left over from before DMI-63 — it said the HTTP
  `require_agent` adapter was "built but still unmounted". It has been mounted on
  `POST /api/v1/scans` since DMI-63; corrected while adding the DMI-65 cross-link.
* **Update**: **ingest is wired** (DMI-63, spec 024) — `backend/routers.md`, `backend/api.md`,
  `backend/overview.md`, `backend/index.md`, `contracts.md`. `POST /api/v1/scans` is mounted as
  `ingestScan` behind the HTTP `require_agent` adapter, returning the contract's `202`
  `ScanIngestAcceptedResponse`. This retires the long-standing "ingest is contract-defined only"
  caveat that ran through five docs; the remaining gap is now purely the **device** end — no Pi
  daemon posts results yet (DMI-66) — so ingest is exercised by signed test requests. Auth resolves
  **before** body validation (a sub-`Depends` beats body parsing), so an unsigned request with an
  invalid payload is a `401`, not a `422`; the exception is a body that is not valid JSON, which
  fails at decode time and is a `422`.
* **Update**: the ingest schemas took the contract's vocabulary — `backend/schemas.md`,
  `contracts.md`. `ScanResult`→`ScanIngestRequest`, `Host`/`Port`/`Finding`→
  `HostPayload`/`PortPayload`/`FindingPayload`, `ScanIngestResponse`→`ScanIngestAcceptedResponse`
  (plus a required `status: "accepted"`). `extra="forbid"` now applies at **every** ingest depth, so
  a nested unknown field like `hosts[0].os` is refused instead of silently dropped. The rename is
  load-bearing, not cosmetic: `scan.py` deliberately keeps **no** class named `Port`, because the
  short-name collision with `read.Port` made FastAPI mangle a published component to
  `api__schemas__scan__Port`. The contract's correction was a *new* ingest-only `PortPayload`
  component (`Port` plus `cpes`) with `HostPayload.ports` re-pointed at it — `Port` itself stayed
  byte-identical, since the read responses still fingerprint through it.
* **Deletion**: the artifact concept is gone end to end — `backend/models.md`, `backend/schemas.md`,
  `backend/migrations.md`, `contracts.md`. `ArtifactRecord`/`artifacts`, `Artifact`, `ArtifactKind`,
  `ScanResult.artifacts`, `PersistedArtifact` and `PersistedScanDetail.artifacts` all removed; the
  agent never populated them. An `artifacts` key in an ingest body is now a `422`.
* **Update**: `persist_scan` was reworked into an authenticated, atomic ingest — `backend/services.md`.
  New `ingest_scan` owns the authorisation and lifecycle rules (fill a requested placeholder, create
  an unrequested scan, refuse a foreign or written-off one) and `persist_scan` took the keyword
  signature `(session, scan, *, org_id, agent_id, command, now)`. Idempotency **moved up** into
  `ingest_scan`, which now checks ownership *first* — a foreign agent replaying a known `scan_id`
  gets a `403`, where the old early-return made it a silent no-op. Every write is `flush()`ed to a
  single commit point, so ingest is genuinely all-or-nothing.
* **Creation**: revision `20260804_14` (`scan_ingest_rework`) — `backend/migrations.md`,
  `backend/models.md`. Adds nullable `scans.agent_id` (FK → `agents.id`, no backfill) and drops
  `artifacts` with its owned `artifacts_id_seq`; the downgrade recreates the table exactly as the
  baseline declared it. Recorded the trap it exposed: a migration test that seeds through an **ORM
  model** while pinned at an older revision breaks the moment a later migration adds a column —
  `agent_id` broke `test_finding_severity_migration.py` this way. Seed with explicit `sa.text()`
  INSERTs naming only the columns that exist at that revision.
* **Update**: documented `test_contract_fidelity.py`'s comparator — `contracts.md`. `SCHEMA_NAMES`
  gained the five ingest components (a name is only listable once a mounted route makes it reachable
  from `app.openapi()`), and `_property_shape` now treats `type: [X, "null"]` ≡
  `anyOf: [X, {type: null}]` and `const: v` ≡ `enum: [v]`. Noted the standing blind spot: it reads
  neither `minLength` nor `maxLength`, so a changed `constr(min_length=…)` goes uncaught.

## 2026-08-03

* **Update**: `read_hosts`'s paging defaults stopped being written twice — `backend/routers.md`,
  `backend/services.md`. `services/read.py` exports `DEFAULT_PAGE = 1` / `DEFAULT_PER_PAGE = 20` and
  `routers/hosts.py` imports them into its `Query(...)` declarations, so the route's advertised
  default and the service's fallback can no longer drift apart silently — a mismatch would page
  differently depending on whether the caller omitted the param or another caller invoked the
  service directly. Behaviour is unchanged (`1`/`20` either way); `read_scans`/`read_findings` keep
  their inline literals, since their services take no defaults. Also re-synced the five drifted
  `services/read.py` line refs in `backend/services.md` (`get_host_detail` and below were four
  lines stale before this change, seven after it).
* **Update**: `dmitri_runtime` now **converges** instead of merely existing — `backend/migrations.md`.
  The baseline's role statement gained an `ELSE ALTER ROLE dmitri_runtime WITH LOGIN BYPASSRLS`.
  Checking only `IF NOT EXISTS` meant a pre-existing role kept whatever attributes it had, and since
  RLS is `ENABLE`d on every application table with **no policy anywhere**, a role without
  `BYPASSRLS` is denied every read and write — so migrations reported success against a database the
  app could not write to. Surfaced as an order-dependent failure in
  `test_runtime_role_allows_engine_work_and_rejects_privilege_expansion` (the test before it creates
  the role bare), which is why it passed in isolation. The `ALTER` names only `LOGIN` and
  `BYPASSRLS`: naming `NOSUPERUSER` even to clear it requires the executor to be `SUPERUSER`, which
  the migration runner is not under Supabase. Pinned by an `rolbypassrls` assertion in
  `test_live_migration_tolerates_preexisting_runtime_role`. Backend suite: 665 passed, 0 skipped.
* **Update**: index listings for `backend/migrations` re-synced to its frontmatter description
  ("eleven revisions" → "thirteen") in `index.md` and `backend/index.md`.
* **Update**: auth + invite error codes pinned, and the invite token left the URL (DMI-77, spec
  023) — `backend/auth.md`, `backend/errors.md`, `backend/schemas.md` and `contracts.md`.
  **Codes:** reset-password, accept-invite and create-invite join change-password in raising
  `ApiError` with a pinned `error.code`; ten codes across seven `components/responses` entries,
  replacing the `bad_request` default that made *"your link is dead"* and *"your password is too
  weak"* indistinguishable to the SPA. **Statuses split:** a dead reset token is now `410` (was
  `400`), matching accept-invite; re-inviting an address that already holds a live invite is `409`.
  **Token relocated:** `POST /api/v1/invites/{token}/accept` → `POST /api/v1/invites/accept` with
  the token in the body — as a path parameter it was written to access logs by uvicorn's default
  logger and any edge proxy. `invite_link()` moved to the query form to match `reset_link()`.
  **New guard:** `test_contract_fidelity.py` now AST-extracts each route's `code=` literals and
  asserts exact set equality against the contract enums, so a typo can no longer ship green.
  **New concurrency guard:** `create_invite` takes a `pg_advisory_xact_lock` before its checks —
  `Invite.role` is per-row, so two racing invites with different roles let the invitee choose their
  own privilege. No migration and no partial index (the predicate is not IMMUTABLE and nothing
  sweeps expired invites).
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
  `RefreshToken`/`refresh_tokens`, `PasswordResetToken`/`password_reset_tokens`; auth no longer <!-- pragma: allowlist secret -->
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
