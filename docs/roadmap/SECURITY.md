# Roadmap — Security (cross-cutting)

> Security spans agent auth, frontend auth, Pi command channel, secrets, and data sensitivity.
> **Authentication roadmap (phased):** [`AUTH.md`](AUTH.md) — September → product-ready → enterprise.
> This file tracks cross-cutting posture and implementation gaps, not detailed auth product decisions.
>
> **Sources:** [`ADR-005`](../adr/ADR-005-security-model.md) (v1 baseline; §1 amended by ADR-011),
> [`ADR-011`](../adr/ADR-011-pi-command-channel.md), [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml).

---

## Authority map — who owns which security decision

Decided in roadmap, **not yet built in code**. Source of truth per area:

- **Agent HMAC + CORS/transport baseline** — [`ADR-005`](../adr/ADR-005-security-model.md) (v1
  baseline; §1 agent directionality amended by [`ADR-011`](../adr/ADR-011-pi-command-channel.md)).
- **Pi command channel** (bidirectional agent, WSS HMAC upgrade) —
  [`ADR-011`](../adr/ADR-011-pi-command-channel.md), reusing ADR-005's HMAC rules.
- **Identity** (login, sessions, invites, roles, password policy) — [`AUTH.md`](AUTH.md) **Phase 1 ✅**
  (roadmap); the detailed authority over ADR-005's frontend-auth sketch.

"Decided" ≠ "built" — none of the above exists in code yet (see [Built vs. gap](#built-vs-gap)).

---

## Built vs. gap

| Control | State |
|---------|--------|
| Agent HMAC | **Decided** (September); **not built** |
| Frontend JWT / login | **Decided**; **not built** |
| Authorization (roles) | **`admin` / `viewer`** — [`AUTH.md`](AUTH.md); **not built** |
| Device secrets | **✅** B2B installer provisioning — [`AUTH.md`](AUTH.md); rotation Phase 2 |
| Secrets management (prod) | Ad hoc `.env`; Phase 2 in AUTH |
| Pi command-channel auth | WSS HMAC upgrade per [`ADR-011`](../adr/ADR-011-pi-command-channel.md) |

---

## Phased milestones (mirror AUTH.md)

| Phase | When | Security focus |
|-------|------|----------------|
| **1 — NSPi / September** | ~September | AUTH Phase 1 + HMAC ingest + **WebSocket** command channel (B10 Control) |
| **2 — Product-ready** | End of year | Full login model, HMAC, roles, prod secrets, audit baseline |
| **3 — Enterprise** | Deal-driven | SSO, customer IdP, BYOC hardening |

---

## Data sensitivity

Scans carry sensitive recon data. Track: HTTPS in transit, encryption at rest (DB provider),
least-privilege once auth exists, audit for scan triggers and (later) LLM/assessment actions.

---

## Open (non-auth)

- **LLM data-access scope** — [`AI.md`](AI.md): read-only, scan-scoped, audit logging
- **Pi command channel** — outbound **WebSocket** v1 ([`ADR-011`](../adr/ADR-011-pi-command-channel.md))

---

## Ripple

Auth phase changes → [`AUTH.md`](AUTH.md), [`BACKEND.md`](BACKEND.md), [`FRONTEND.md`](FRONTEND.md), [`PI.md`](PI.md).
