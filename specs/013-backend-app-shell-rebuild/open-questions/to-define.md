# Open questions — 013 backend app shell rebuild

Deferred items surfaced during refine-specs (2026-07-15). None block the approval gate.
All four are now tracked in Linear (triaged 2026-07-15); this file is a pointer, not a backlog.

- **Health CORS preflight + response headers** → tracked in **DMI-60** (Sessions + auth
  routes). The audited contract documents `OPTIONS /api/v1/health`, `Access-Control-Allow-*`
  and `X-Request-Id` headers. Deliberately not implemented by this shell (no browser consumer
  yet); DMI-60's Expected section now carries the CORS/middleware work since it delivers the
  first browser-facing routes. Deferral reconfirmed during grill-me on 2026-07-15; their
  absence is not a DMI-56 acceptance failure.
- **Hosted `BYPASSRLS` verification** → tracked as an open-checkpoint comment on **DMI-56**.
  Whether Supabase's `postgres` role (non-superuser, `supautils`-gated role DDL) can execute
  `CREATE ROLE dmitri_runtime ... BYPASSRLS` on the PG17 `nspi` instance is only decidable at
  the human apply step. Pre-flight check and the permissive-policies fallback are specced in
  ARCHITECTURE.md `HUMAN_INFRA_REQUIRED`. Record the outcome in the DMI-56 comment thread.
- **ADR-009 supersession** → tracked in **DMI-79** (Update ADR-009 for sync-everywhere,
  psycopg3; blocked by DMI-56). Run `architecture-adr-sync` after the feature lands
  (per decision recorded 2026-07-14).
- **Worker shutdown and interrupted-job recovery** → tracked in **DMI-80** (Worker
  reliability: SIGTERM shutdown + interrupted-job requeue; blocked by DMI-56, related to
  DMI-63). DMI-56 proves the worker entry point and one empty poll only.
