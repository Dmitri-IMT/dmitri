# Roadmap — Security (cross-cutting)

> Security spans agent auth, frontend auth, Pi command channel, secrets, and data sensitivity.
> **Authentication roadmap (phased):** [`AUTH.md`](AUTH.md) — September → product-ready → enterprise.
> This file tracks cross-cutting posture and implementation gaps, not detailed auth product decisions.
>
> **Sources:** [`ADR-005`](../adr/ADR-005-security-model.md) (v1 baseline; §1 amended by ADR-011),
> [`ADR-011`](../adr/ADR-011-pi-command-channel.md), [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml).

---

## Authority map — who owns which security decision

Decisions and implementation status are separate; authority remains:

- **Agent Ed25519 signature + CORS/transport baseline** — [`ADR-005`](../adr/ADR-005-security-model.md)
  as amended by [`ADR-011`](../adr/ADR-011-pi-command-channel.md).
- **Pi command channel** — [`ADR-011`](../adr/ADR-011-pi-command-channel.md).
- **Identity** — [`AUTH.md`](AUTH.md) Phase 1.

The browser and agent gates, command/ingest transports, account removal, member administration, and
activity recording are now implemented in software. Physical Pi provisioning and later hardening
remain gaps; see [Built vs. gap](#built-vs-gap).

---

## Built vs. gap

| Control | State |
|---------|--------|
| Agent Ed25519 signature | **Built** on backend and Pi software; real hardware/key provisioning remains |
| Frontend JWT / login | **Built** — in-memory token, single-flight refresh, route guard |
| Authorization (roles) | **Built server-side**; admin member/invite operations are role-gated and org-scoped. The Users screen ships (spec 034) and adds the client-side gate — `AdminOnly` hides the nav item, `RequireAdmin` renders not-found in place of the route. Both fail closed, and both are a courtesy over the server checks, never a substitute |
| Account removal | **Built** (DMI-102/spec 029): hard delete with session-table cascade and last-admin refusal |
| Member activity | **Built** (DMI-76/spec 030): `last_login_at` + `last_seen_at`, admin list exposes only last-seen, Settings discloses both recorded facts |
| Device keys | **Built in software** for installer provisioning; physical provisioning and rotation remain |
| Secrets management (prod) | Ad hoc `.env`; Phase 2 in AUTH. Backend stores device public keys only |
| Pi command-channel auth | **Built**: Ed25519-signed WSS upgrade on backend and Pi daemon |

---

## Phased milestones (mirror AUTH.md)

| Phase | When | Security focus |
|-------|------|----------------|
| **1 — NSPi / September** | ~September | AUTH Phase 1 + Ed25519-signed ingest + **WebSocket** command channel (B10 Control) |
| **2 — Product-ready** | End of year | Full login model, device signatures, roles, prod secrets, audit baseline |
| **3 — Enterprise** | Deal-driven | SSO, customer IdP, BYOC hardening |

---

## Data sensitivity

Scans carry sensitive recon data. Track: HTTPS in transit, encryption at rest (DB provider),
least-privilege once auth exists, audit for scan triggers and (later) LLM/assessment actions.

**Member activity is personal data about employees, not recon data.** Showing an org admin when a
colleague was last active needs a documented lawful basis (legitimate interests — consent is not
freely given in an employment relationship) and transparency toward the people monitored. ICO
guidance places logon-time monitoring at the low-intrusion end and no DPIA is required here, but
the decision not to run one is recorded rather than assumed. Store precise, render coarse. See
[`AUTH.md` § Member activity](AUTH.md) and
[`user-last-seen-tracking.md`](../research/user-last-seen-tracking.md).

---

## Open (non-auth)

- **LLM data-access scope** — [`AI.md`](AI.md): read-only, scan-scoped, audit logging
- **Pi command channel** — outbound **WebSocket** v1 ([`ADR-011`](../adr/ADR-011-pi-command-channel.md))

---

## Ripple

Auth phase changes → [`AUTH.md`](AUTH.md), [`BACKEND.md`](BACKEND.md), [`FRONTEND.md`](FRONTEND.md), [`PI.md`](PI.md).
