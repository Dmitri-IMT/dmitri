---
type: Entry Point
title: Backend management commands — org bootstrap, agent provisioning
description: The two operator CLIs — backend-bootstrap-org (first org + its admin invite) and backend-provision-agent (register a device public key) — which print secrets to stdout and never to a log.
resource: backend/src/api/management/bootstrap_org.py
tags: [backend, cli, operations, provisioning, invites, agents]
timestamp: 2026-07-27T00:00:00Z
---

# Backend management commands — org bootstrap, agent provisioning

## Purpose

Two `argparse` console scripts (spec 017 / DMI-61) that solve the chicken-and-egg problems the HTTP
API cannot: creating the **first** org and its admin when no admin exists yet to authenticate, and
registering a device's **public key** before that device can authenticate. Both are vendor-operated,
run out of band, and expose **no HTTP routes**.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `bootstrap_org.main()` | Refuses a duplicate org name case- and whitespace-insensitively **before any insert**, then adds the `Org`, commits, then calls `create_invite(..., role="admin")`. Prints `invite_token=…` to stdout once. | `backend/src/api/management/bootstrap_org.py:29` |
| `_SilentMailer` | A local no-op satisfying the `Mailer` protocol, passed to `create_invite` in place of `LogMailer` so the raw admin token never reaches a `logger` call. The command prints the token itself. | `backend/src/api/management/bootstrap_org.py:14` |
| `provision_agent.main()` | Validates the org and a 64-hex/32-byte public key, inserts the `Agent`, prints its `agent_id`. Returns `1` on a bad key length or unknown `--org-id` without raising. | `backend/src/api/management/provision_agent.py:32` |
| `_decode_public_key()` | Hex→32 raw bytes, or `None` for anything malformed. | `backend/src/api/management/provision_agent.py:22` |

## How it connects

- **Session** — both use the `for session in get_session():` idiom from
  [`services/worker.py`](/backend/services.md) and connect via `DATABASE_URL` (the `dmitri_runtime`
  role), **never** `DATABASE_URL_DIRECT`, which is migrations-only — see [config](/backend/api.md).
- **Downstream** — `bootstrap_org` calls `create_invite` in [invites](/backend/auth.md);
  `provision_agent` writes the `agents.public_key` that [device auth](/backend/device-auth.md)
  verifies against, and can mint a keypair via `device_sig.generate_keypair()`.
- **Console scripts** — `backend-bootstrap-org` and `backend-provision-agent` in
  `[project.scripts]` (`backend/pyproject.toml`), asserted structurally by a test.

## Notes / gotchas

- **Secrets go to stdout exactly once and never through `logging`.** This is not stylistic — a
  logger would put the raw admin invite token into Railway's log stream. The original implementation
  passed `LogMailer` (whose `send_invite_link` logs the token) and was rejected in review for exactly
  that; a `caplog`-based test now pins the behavior, since a source-level "no logging import" check
  cannot catch a secret leaking through a collaborator.
- **`provision_agent` never receives a private key.** `--generate` may print one once for local
  testing behind a not-for-production banner, but no private key is ever persisted.
- **`main(argv=None) -> int`** returning `0`/`1` with one-line stderr messages — no tracebacks at an
  operator's terminal.
- **`LogMailer` still logs the token on the HTTP invite path** (`POST /api/v1/invites`). That is
  Task 8's accepted dev stand-in until a real mail provider lands (DMI-71), not an oversight here.

# Citations

[1] [specs/017-auth-middleware-invite-flow](../../../specs/017-auth-middleware-invite-flow/TRUTH.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [docs/roadmap/AUTH.md](../../../docs/roadmap/AUTH.md)
