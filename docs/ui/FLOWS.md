# UI Flows — Breadboards

> **Status:** draft (2026-07-10). The flow layer of the UI docs ladder:
> [`REFERENCE.md`](REFERENCE.md) (principles) → **FLOWS.md** (breadboards) → [`SCREENS.md`](SCREENS.md)
> (layouts, states, copy). Breadboards fix **places, affordances and connections**
> and deliberately fix **no layout** ([`REFERENCE.md` §5](REFERENCE.md)) — argue and lock the
> flows here before any wireframe exists.

Notation: **PLACE** in caps · `[affordance]` for buttons/inputs/links · `→` a connection with
its trigger. API references are to
[`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml); roles and auth policy
per [`AUTH.md`](../roadmap/AUTH.md); client mechanics per
[`ADR-008`](../adr/ADR-008-frontend-stack.md).

## Places inventory

Matches the screen inventory in ADR-008. The LLM explainer panel is deferred and has no place yet.

| Place | Shell | Roles |
| --- | --- | --- |
| LOGIN | outside | public |
| ACCEPT INVITE | outside (email link) | public |
| FORGOT PASSWORD | outside | public |
| RESET PASSWORD | outside (email link) | public |
| FORCED PASSWORD CHANGE | outside | public (post-403) |
| DASHBOARD | inside | admin, viewer |
| SCAN LIST | inside | admin, viewer |
| SCAN DETAIL | inside | admin, viewer |
| HOST INVENTORY | inside | admin, viewer |
| HOST DETAIL | inside | admin, viewer |
| AGENTS | inside | admin, viewer (read-only) |
| USERS & INVITES | inside | admin only |

## B1 — Auth: login and its edges

```text
LOGIN
  [email] [password] [Log in]  ["Forgot password?"]
  [Log in] ok ................→ DASHBOARD
  [Log in] 401 ...............→ stay; inline error
  [Log in] 403 pw-expired ....→ FORCED PASSWORD CHANGE
  ["Forgot password?"] .......→ FORGOT PASSWORD

FORGOT PASSWORD
  [email] [Send reset link]
  always 204 .................→ stay; confirmation copy (no account enumeration)
  (email link) ...............→ RESET PASSWORD

RESET PASSWORD
  [new password] [confirm] [Set password]
  ok .........................→ LOGIN
  400 policy / expired token .→ stay; inline error

FORCED PASSWORD CHANGE
  [current] [new] [confirm] [Change password]
  ok .........................→ DASHBOARD

Session edges (from any authenticated place)
  access expired ..............→ silent refresh → retry (invisible to user)
  refresh expired/revoked .....→ LOGIN
  [Log out] (shell top bar) ...→ LOGIN
```

⚠️ FORCED PASSWORD CHANGE is **blocked on the contract gap** recorded in ADR-008 (§Auth Client):
expired-password login returns 403 with no token, but `change-password` requires Bearer. Resolve
in contract + AUTH.md before this flow reaches SCREENS.md.

## B2 — Admin day one: invite → first scan

```text
(invite email link)
  → ACCEPT INVITE
      [set password] [confirm] [Create account]      POST /invites/{token}/accept
      ok ......................→ LOGIN (success copy)          [open: auto-login? see below]
      400 expired/used token ..→ stay; error copy + "ask your admin to re-invite"

LOGIN → DASHBOARD (blank slate: no scans yet)
      blank-slate CTA .........→ AGENTS               (the blank slate IS the onboarding)

AGENTS
      agent row online .. [Scan now] → B4

(first scan done)
  → DASHBOARD with first real data / SCAN DETAIL via B4

USERS & INVITES
      [Invite user: email + role admin|viewer] → pending-invite row   POST /invites
      [change role] / [revoke invite] → row updates
```

## B3 — Viewer daily: read path

The viewer has **no** `[Scan now]` and no USERS & INVITES nav item — affordances are omitted,
not disabled (context over consistency, [`REFERENCE.md` §9](REFERENCE.md)).

```text
LOGIN → DASHBOARD ("Review" in the nav — a judgment, not a metrics wall)
      verdict line (epicenter) — the product answers "is anything wrong since I last looked?"
      review items — rendered only when something warrants attention:
        critical/high finding (latest scan) ..→ SCAN DETAIL (finding row)
        scan failed ..........................→ SCAN DETAIL (failure reason)
        coverage stale (Pi offline /
          no recent completed scan) ..........→ AGENTS
        new device on the network ............→ HOST DETAIL      ⚠️ open decision #4
      quiet context footer: last scan · Pi status — muted links, no metric cards
      nav: Scans ................→ SCAN LIST → row → SCAN DETAIL
      nav: Hosts ................→ HOST INVENTORY → row → HOST DETAIL

SCAN DETAIL
      host row ..................→ host panel (in place)
      finding row ...............→ finding detail (in place)

HOST DETAIL
      scan-history row ..........→ SCAN DETAIL
```

## B4 — "Scan now": command flow

Admin only. Contract: [`ADR-011`](../adr/ADR-011-pi-command-channel.md) +
[`BACKEND.md` B6](../roadmap/BACKEND.md).

```text
AGENTS
  agent row: name · online/offline · last seen · [Scan now]
  [Scan now] ....................→ POST /agents/{agent_id}/commands
     accepted ...................→ status pill on the row: queued
        poll GET /commands/{command_id}
        queued → delivered → running → uploading → done
        done ....................→ invalidate scans/agents/findings caches
                                    pill becomes [View scan] → SCAN DETAIL
        command failure state ...→ error pill + [Retry]
     503 device_offline .........→ toast "Pi seems to be offline." + refresh agent status
     409 device_busy ............→ toast (copy TBD — IDEAS.md) + show running state
```

## Not breadboarded (out of scope for September)

LLM explainer panel ([`AI.md`](../roadmap/AI.md)) · Pi provisioning/pairing (installer-only,
[`AUTH.md`](../roadmap/AUTH.md)) · settings/preferences (none in MVP) · notifications.

## Open decisions

| # | Question | Blocked on |
| --- | --- | --- |
| 1 | ACCEPT INVITE: auto-login into DASHBOARD instead of bouncing to LOGIN? | contract — does `/invites/{token}/accept` issue a session? |
| 2 | FORCED PASSWORD CHANGE flow | contract gap (ADR-008 §Auth Client) |
| 3 | 409 `device_busy` toast copy | copywriting pass in SCREENS.md |
| 4 | "New device" review item on DASHBOARD: `HostSummary` has no `first_seen_at` | contract — add the field to `GET /hosts`, or cut the item from v1 |
