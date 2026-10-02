---
type: Entry Point
title: Backend management commands — bootstrap, provisioning, identity repair
description: Operator CLIs for org bootstrap, agent provisioning, and dry-run or applied repair of hosts with ambiguous shared MAC addresses.
resource: backend/src/api/management/bootstrap_org.py
tags: [backend, cli, operations, provisioning, invites, agents]
timestamp: 2026-09-30T00:00:00Z
---

# Backend management commands — bootstrap, provisioning, identity repair

## Purpose

Three `argparse` console scripts that solve the chicken-and-egg problems the HTTP
API cannot: creating the **first** org and its admin when no admin exists yet to authenticate, and
registering a device's **public key** before that device can authenticate. The third inspects and
repairs historical host identities when multiple IPs share a MAC in one scan. All are
operator-run out of band and expose **no HTTP routes**.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `bootstrap_org.main()` | Refuses a duplicate org name case- and whitespace-insensitively **before any insert**, then adds the `Org`, commits, then calls `create_invite(..., role="admin")`. Prints `invite_token=…` to stdout once. | `backend/src/api/management/bootstrap_org.py:29` |
| `_SilentMailer` | A local no-op satisfying the `Mailer` protocol, passed to `create_invite` so the bootstrap path emails nothing at all and the raw admin token never reaches a `logger` call. The command prints the token itself. | `backend/src/api/management/bootstrap_org.py:14` |
| `provision_agent.main()` | Validates the org and device public key, inserts the `Agent`, creates an org OT digest key if absent, and prints `agent_id` and `ot_digest_key` to stdout. Reuses the same key for later agents in that org. | `backend/src/api/management/provision_agent.py:33` |
| `_decode_public_key()` | Hex→32 raw bytes, or `None` for anything malformed. | `backend/src/api/management/provision_agent.py:22` |
| `repair_host_identities.main()` | Lists ambiguous MAC groups without writing by default; `--apply` relinks scan history, rebuilds host inventory, and commits. | `backend/src/api/management/repair_host_identities.py:10` |

## How it connects

- **Session** — both use the `for session in get_session():` idiom from
  [`services/worker.py`](/backend/services.md) and connect via `DATABASE_URL` (the `dmitri_runtime`
  role), **never** `DATABASE_URL_DIRECT`, which is migrations-only — see [config](/backend/api.md).
- **Downstream** — `bootstrap_org` calls `create_invite` in [invites](/backend/auth.md);
  `provision_agent` writes the `agents.public_key` that [device auth](/backend/device-auth.md)
  verifies against, and can mint a keypair via `device_sig.generate_keypair()`.
- **Console scripts** — `backend-bootstrap-org`, `backend-provision-agent`, and
  `backend-repair-host-identities` in
  `[project.scripts]` (`backend/pyproject.toml`), asserted structurally by a test.

## Notes / gotchas

- **Secrets go to stdout, never through `logging`.** The admin invite token is printed once; the
  org OT digest key is printed again when a later agent is provisioned into the same org. A logger
  would put the raw admin invite token into Railway's log stream. The original implementation
  passed the then-current `LogMailer` (whose `send_invite_link` logged the token) and was rejected in
  review for exactly that; a `caplog`-based test now pins the behavior, since a source-level "no
  logging import" check cannot catch a secret leaking through a collaborator.
- **`provision_agent` never receives a private key.** `--generate` may print one once for local
  testing behind a not-for-production banner, but no private key is ever persisted.
- **`main(argv=None) -> int`** returning `0`/`1` with one-line stderr messages — no tracebacks at an
  operator's terminal.
- **`_SilentMailer` is not redundant with `NullMailer`.** DMI-71 replaced `LogMailer` with a real
  provider, and nothing logs the token on the HTTP invite path any more — see
  [auth](/backend/auth.md). The two no-ops still mean different things: `NullMailer` means "email is
  not configured" and warns as much, while `_SilentMailer` means "this path deliberately does not
  email, the operator already has the token". Swapping it would print a misleading
  `RESEND_API_KEY is not set` warning on every bootstrap run.

# Citations

[1] [specs/017-auth-middleware-invite-flow](../../../specs/017-auth-middleware-invite-flow/TRUTH.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [docs/roadmap/AUTH.md](../../../docs/roadmap/AUTH.md)
