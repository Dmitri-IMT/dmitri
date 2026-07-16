# TRUTH — Backend app shell rebuild

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

## Narrative

The current backend was written by a prior contributor as a standalone scan-result scorer,
before the auth, frontend, Pi-command-channel, and contract decisions existed. Its
enrichment and scoring engine is real domain logic worth keeping; its application shell —
the web entrypoint, the SQLite-based session handling, the settings model — encodes a world
with no organizations, no auth, and no hosted database, and is discarded by decision B8.

This feature builds the replacement shell: a minimal web application that boots against the
hosted Postgres, a migration system that owns the database schema, and a settings model
read from the environment. Every later backend feature (identity schema, command channel,
scan ingest, read APIs) lands on this shell instead of building its own ground. It is the
gate for four downstream issues.

Who benefits: every subsequent backend builder — human or agent — starts from a booting,
migrated, configured application.

## Business rules

- The database schema is owned exclusively by migrations. No code path may create or alter
  tables outside the migration system.
- Database access posture is migration-owned too: every application table has row-level
  security enabled and grants to Supabase's `anon` and `authenticated` roles revoked. No RLS
  policies are introduced until the later identity/org-scoping feature.
- Runtime database access and migration database access use different connection targets:
  runtime uses a dedicated least-privilege login through the hosted connection pooler;
  migrations use the administrative direct connection. (Decision B4/B5: pooled transaction
  mode cannot run schema changes.)
- The hosted API and worker receive only the restricted runtime credential. The direct
  administrative credential is held by the operator for migrations and is never injected
  into either long-running Railway service.
- Application configuration comes from environment variables. Credentials never live in
  source code or the repository. Passwords, NVD API keys, and complete connection URLs never
  appear in settings representations, shell-generated validation/migration errors, health
  responses, or application logs. Credentials are unwrapped only at the connection or
  outbound-request boundary that consumes them.
- Configuration is introduced with code that consumes it; this shell does not reserve unused
  JWT or HMAC secret fields before authentication exists.
- Operator-facing setup guidance and environment templates describe the shell that actually
  ships; they must not direct maintainers back to SQLite, asyncpg, the administrative runtime
  login, obsolete migration-variable names, or discarded business routes.
- The kept enrichment/scoring engine is carried forward unchanged in behaviour: it must
  load and operate under the new shell exactly as it did before.
- The background worker remains a separately runnable process alongside the web application.
- Discarded shell pieces stay discarded: no auth-less business routes, no SQLite paths, no
  schema-on-boot behaviour, or standalone business-route smoke harness may be resurrected.
- The public shell exposes only its contracted health route. Framework-generated documentation
  and OpenAPI routes are disabled. The checked-in contract remains authoritative for the
  implemented GET path and response shapes; its end-state CORS preflight and response headers
  are intentionally deferred to the future middleware feature and do not block this shell.
- The deliverable runs against the hosted `nspi` environment; a local database may be used
  during development only.

## User stories

1. As a backend feature builder (the identity-schema, command-channel, and ingest issues),
   I want a booting, migrated, configured application, so that I add routes and tables
   instead of building infrastructure first.
2. As an operator, I want a health check that proves the application can reach its
   database, so that deployment problems surface immediately and unambiguously.
3. As a maintainer, I want the database schema to evolve only through reversible
   migrations, so that every environment's schema state is known and reproducible.
4. As the scoring engine (kept domain logic), I want the same database session behaviour I
   was written against, so that enrichment and scoring keep working without a rewrite.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Clean migrate up/down | A fresh, empty Postgres database | Migrations are applied to the newest version, then rolled all the way back | Both directions complete without error; after rollback no application tables remain (the migration system's own bookkeeping table may persist) |
| Hosted rollback is quiescent | The hosted API and worker are using the pooled runtime login | An operator rolls the baseline back | Both services are stopped and their pooled sessions drained before downgrade; afterward the application tables and feature-owned runtime role are absent, and neither service restarts without a compatible schema |
| Baseline access closed | The baseline migration has been applied | Application-object security is inspected | Every application table has row-level security enabled and neither `anon` nor `authenticated` has privileges on application tables or sequences; the API and worker remain able to use the configured runtime role |
| Runtime role constrained | The baseline migration has been applied and the runtime role password provisioned outside source control | The API and worker connect through the pooler | They connect as the dedicated runtime role, which behaviorally can perform the health query and kept-engine reads/writes but cannot own or alter the schema, create database objects, delete/truncate application data, assume Supabase API roles, or access their protected data |
| Boot and health | The application booted with environment settings pointing at a reachable Postgres | The health endpoint is called | It reports OK, in the shape the published API contract promises, and only after a live database round-trip succeeded (a static always-OK reply is a failure) |
| Health identifies the release | Backend release 0.1.0 is installed | The health endpoint is called | Its version field is 0.1.0 from the installed backend package metadata, matching the published contract example rather than a second independently maintained value |
| Health degrades honestly | The application booted, then its database becomes unreachable | The health endpoint is called | It reports failure and names the database as the cause, without exposing internal connection detail — it never claims OK without a live round-trip |
| Settings from environment | Required settings present in the environment | The API or worker starts | It validates and uses those values before serving or polling, without opening a startup DB connection; missing or non-Postgres runtime configuration prevents process startup, while migrations independently require a valid direct target |
| Connection secrets redacted | Runtime or migration configuration contains credential-bearing URLs, including an invalid URL | Settings are represented or shell-generated validation/startup errors are emitted | The variable name and a safe reason may appear, but passwords and complete URL values do not |
| Administrative secret isolated | Railway variables for the hosted API and worker are inspected | The services are deployed or running | Both receive the restricted runtime URL and neither can read or reference the direct administrative URL |
| Runtime password provisioned safely | The migration-created runtime login needs its generated password | The operator assigns and deploys the credential | Password entry is interactive, the pooler URL contains the correctly URL-encoded value, Railway stores it sealed, and no password-bearing SQL command or history entry is created |
| NVD key remains secret | An optional NVD API key is configured | Settings are represented and the retained NVD client sends a request | The key is absent from representations and logs but is supplied to NVD in the required request header |
| Engine intact | The new shell in place | The kept enrichment/scoring engine modules are loaded | They import and construct cleanly, with no references to discarded shell pieces |
| Worker still runs | The new shell in place and a migrated database | The background worker entry point is invoked | It loads through the new settings/session stack and completes one empty polling iteration without error |
| No schema-on-boot | A fresh, empty Postgres database | The application boots without migrations having run | It creates no tables; schema creation happens only via migrations |
| Health-only route surface | The application is running | Its registered and reachable HTTP routes are inspected | Only `GET /api/v1/health` is exposed; `/`, `/docs`, `/redoc`, `/openapi.json`, and discarded business routes are absent |
| Obsolete smoke shell removed | The health-only shell replaces the standalone scorer application | Installed commands and source modules are inspected | No business-route smoke-test module or `backend-smoke-test` console command remains |
| Hosted service wiring | The API and worker Railway services use the repository configuration | Each service is deployed | Neither start command contains a placeholder; the API starts through its real entry point and Railway probes `/api/v1/health`; the worker starts through its real entry point |
| Operator guidance aligned | A maintainer follows the checked-in backend, Supabase, Railway, and requirements guidance | They configure, start, or trace verification for the new shell | The documented commands, role names, connection drivers, environment variables, migration order, health path, route surface, and verification owners match the delivered application; no active instruction describes a discarded shell path or deleted test harness |
| Backend CI gate | A clean CI runner | The backend job runs | A disposable Postgres 17 service is migrated up/down, all backend tests run with database coverage enabled and no database-test skips, and backend lint passes |
| Destructive tests are isolated | A database-test URL is supplied | The test harness prepares migrations, roles, truncation, or cleanup | It proceeds only when both the URL and connected server identify the dedicated `dmitri_test` database; otherwise it fails before mutation, and teardown removes only schema and stand-in roles owned by the harness |
| Incremental quality gate | A task changes one owned part of the shell while a documented pre-existing failure belongs to a later dependency | The task is reviewed | Its task-scoped tests and lint pass, the known failure is neither masked nor expanded, and the assigned compatibility owner must restore the complete suite before later backend work proceeds |
| Quality gate | The changed scope | Project tests and lint run locally or in CI as specified | Task approval passes the tests for its owned behaviour; feature approval still includes the complete Postgres-backed CI result with no database-test skips, not only a focused or locally skipped suite |

## Out of scope (v1)

- Business routes of any kind (scan ingest, read APIs, risk summaries) — later issues.
- Authentication, JWT/HMAC configuration or verification logic, and org scoping — Auth
  Phase 1 epic.
- Command-channel tables and lifecycle — command-channel epic.
- Rework of the scan persistence path (`org_id`, hosts rename, commit strategy) — ingest
  issue.
- New infrastructure and broader hosting configuration beyond wiring the existing Railway API
  and worker definitions to this shell — ops issue.
- Any change to the enrichment/scoring engine's algorithms or external API clients.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Execution ledger: `POOP.md` (written during orchestration)
