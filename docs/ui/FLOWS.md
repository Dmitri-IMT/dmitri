# UI Flows — Breadboards

> **Status:** draft (2026-07-13) — **B3 and B4 clarified against the contract**; B5 (Settings) added;
> **B1 and B2 corrected against the contract** when the auth screens were specced (C7 resolved — accepting
> an invite *does* issue a session, so it lands on HOME, not LOGIN; invite expiry is `410`, not `400`).
> Fourteen open contract asks are recorded below; B4 cannot lock until C1 and C2 land. The flow layer of the UI docs ladder:
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
| HOME | inside | admin, viewer |
| SCAN LIST | inside | admin, viewer |
| SCAN DETAIL | inside | admin, viewer |
| HOST INVENTORY | inside | admin, viewer |
| HOST DETAIL | inside | admin, viewer |
| AGENTS | inside | admin, viewer (read-only) |
| USERS & INVITES | inside | admin only |
| SETTINGS | inside | admin, viewer |

**Single agent.** The MVP has exactly one Pi. AGENTS is still a list place (one row), and the
frontend discovers it via `GET /api/v1/agents` — **contract ask C1**; the agent id is the
provisioning `X-Device-Id` and cannot be derived client-side.

## B1 — Auth: login and its edges

```text
LOGIN
  [email] [password] [Log in]  ["Forgot password?"]
  [Log in] ok ................→ HOME
  [Log in] 401 ...............→ stay; inline error
  ["Forgot password?"] .......→ FORGOT PASSWORD

FORGOT PASSWORD
  [email] [Send reset link]
  always 204 .................→ stay; confirmation copy (no account enumeration)
  (email link) ...............→ RESET PASSWORD

RESET PASSWORD                     (?token=… — the token posts in the BODY, not the path)
  [new password] [confirm] [Set password]
  204 ........................→ LOGIN (success copy) — reset issues NO session, unlike accept-invite
  400 policy .................→ stay; inline error
  400 dead/used token ........→ form removed; [Request a new link] → FORGOT PASSWORD
                                ⚠️ both failures are the SAME 400 — contract ask C15

Session edges (from any authenticated place)
  access expired ..............→ silent refresh → retry (invisible to user)
  refresh expired/revoked .....→ LOGIN
  [Log out] (shell top bar) ...→ LOGIN
```

## B2 — Admin day one: invite → first scan

```text
(invite email link)
  → ACCEPT INVITE
      [email] [password] [confirm] [Create account]  POST /invites/accept  {token, email, password}
      201 .....................→ HOME (blank slate) — returns a LoginResponse; ✅ C7 resolved
      410 invalid_invite_token → form removed; "ask your admin for a new link"
      400 password_policy_violation → stay; inline error under the password field
      400 invite_email_mismatch ....→ stay; inline error under the email field
      400 email_already_registered .→ stay; offer LOGIN instead

HOME (blank slate: no scans yet)
      blank-slate CTA .........→ AGENTS               (the blank slate IS the onboarding)

AGENTS
      target_subnet == null ..→ [Choose which network to scan]   ← required before the first scan
                                (the Pi is dual-homed; see B4)
      network chosen .........→ [Scan now] becomes available → B4

(first scan done)
  → HOME with first real data / SCAN DETAIL via B4

USERS & INVITES                                        ⚠️ mostly blocked — contract ask C4
      [Invite user: email + role admin|viewer]                        POST /invites  ✅ exists
          201 → { invite_token, expires_at }
          → the BACKEND emails the link to the invitee (✅ C17 decided; provider TBD)
          → the SCREEN also shows the link, copyable — email can land in spam, and
            some admins would rather send it over Slack
          → shown ONCE: with no GET /invites, the admin cannot retrieve it again
      [change role] / [revoke invite] → row updates                   ❌ no endpoint
      (listing users and pending invites)                             ❌ no endpoint
      ⇒ v1 ships the invite form ALONE, at /users. The nav item stays "Users" — it names the
        domain, and more user-related surfaces land inside it as endpoints arrive.
```

## B3 — Daily read path

The viewer has **no** `[Scan now]` and no USERS & INVITES nav item — affordances are omitted,
not disabled (context over consistency, [`REFERENCE.md` §9](REFERENCE.md)). Admins walk this same
path; nothing below is viewer-specific except those two omissions.

```text
LOGIN → HOME (the nav name is "Home"; its job is a judgment, not a metrics wall)
      verdict line (epicenter) — the product answers "is anything wrong since I last looked?"
      review items — rendered only when something warrants attention:
        critical/high finding
          (latest COMPLETED scan) ............→ SCAN DETAIL, that finding row open
        scan failed (latest scan) ............→ SCAN DETAIL (failure reason)
        coverage stale (Pi offline /
          no completed scan in N days) .......→ AGENTS                ⚠️ N undecided
        new device on the network ............→ HOST DETAIL           ⚠️ cut from v1 (#4)
      quiet context footer: last scan · Pi status — muted links, no metric cards
      nav: Scans ................→ SCAN LIST → row → SCAN DETAIL
      nav: Hosts ................→ HOST INVENTORY → row → HOST DETAIL

SCAN DETAIL
      host row ..................→ host panel (in place)
      finding row ...............→ finding detail (in place)

HOST DETAIL
      scan-history row ..........→ SCAN DETAIL
```

**Findings come from the latest *completed* scan, never simply the latest scan.** If the most
recent scan **failed**, it has no findings — so keying the review items to it would make Home fall
*silent about the critical findings from the last good scan*, showing the operator a calmer page at
the exact moment coverage degraded. The failed scan is an **additional** item, never a replacement.
Home therefore reads two scans: the latest (for the failure item and the footer) and the latest
completed (for the findings).

**Finding detail is rendered in place, not fetched.** `GET /findings?scan_id=…` already returns the
full `FindingRecord` — `title`, `description`, `recommendation`, `evidence`, `device_ip`, `port`,
`severity`. Scan detail holds every finding it needs the moment it loads, so opening one is local
state. **No `GET /findings/{id}` endpoint is needed** and none should be added ([`REFERENCE.md`
§12](REFERENCE.md) — don't solve a problem you don't have).

**The Home → finding deep link is routing, not data:** `/scans/:scanId?finding=:findingId`. Scan
detail loads its findings as it always does, matches the id locally, scrolls to that row and opens
its panel. If the param is absent or unmatched the page renders normally, so the link degrades
cleanly.

## B4 — "Scan now": command flow

Admin only. Contract: [`ADR-011`](../adr/ADR-011-pi-command-channel.md) +
[`BACKEND.md` B6](../roadmap/BACKEND.md).

```text
AGENTS  (one row — single-agent MVP; discovered via GET /agents, contract ask C1)
  agent row: name · online/offline · last seen · target network · [Scan now]

  on mount / return / reload:
     GET /agents/{agent_id} → active_command_id
     active_command_id != null ..→ resume polling; render the pill mid-flight
                                   (this is what makes the pill survive navigation)

  target_subnet == null .........→ [Choose which network to scan]   ← blocks [Scan now]
     lists AgentDetail.available_subnets, reported by the Pi over its WS channel
     shown as human labels, never a CIDR text field:
         ( ) Ethernet · 192.168.0.0/24
         ( ) Wi-Fi    · 10.12.0.0/16
     chosen ......................→ persisted on the agent (contract ask C2)

  [Scan now] ....................→ POST /agents/{agent_id}/commands
                                    { scan_mode: "quick", subnet: <agent.target_subnet> }
     201 ........................→ status pill on the row: queued
        poll GET /commands/{command_id}  every 5s while pending
        queued → delivered → running → uploading → done
        done ....................→ invalidate scans/agents/findings caches
                                    pill becomes [View scan] → SCAN DETAIL
        failed ..................→ error pill (CommandDetail.error_code) + [Retry]
     503 device_offline .........→ toast "Pi seems to be offline." + refresh agent status
     409 device_busy ............→ toast (copy TBD) + GET /agents/{id} → poll active_command_id
                                    (the Pi is mid-scan; adopt its command, don't start one)
```

**Why the network must be chosen, and chosen here.** The Pi is **deliberately dual-homed**
([field test](../tests/nspi-september/plan.md)): ethernet onto the target subnet with *no default
gateway*, wifi for internet so it can reach `vulners.com` while scanning. It therefore sees **two**
networks and has no basis for guessing which is the target — and scanning the wrong one (the host
site's own wifi) would be both useless and hostile. A human must choose, once.

That choice is a **property of the Pi, not a user preference**: one box, pointed at one network, the
same for every admin in the org. So it lives on the agent and is made on AGENTS — the place you are
already looking at the Pi and about to scan it ([`REFERENCE.md` §9](REFERENCE.md)) — not in SETTINGS.
`POST /commands` is unchanged: the frontend sends the stored `target_subnet`, and the admin never
sees a CIDR field.

**Scan mode is not a choice.** `ScanMode` has five values; the product surfaces one and picks
**`quick`** ([`REFERENCE.md` §8](REFERENCE.md) — the product decides). It is not exposed in the UI.

**The pill survives navigation.** `AgentDetail.active_command_id` already exists in the contract.
Without reading it on mount, the status pill would live only in React state and a ten-minute scan
would lose it the moment the operator visited Scans and came back — or reloaded. The same field is
the *only* way to implement the 409 branch, which must show the running state of a command the
frontend did not create and has no id for.

**`[View scan]` appears only at `done`,** deliberately. `CommandSummary` returns `scan_id` at `201`
— the scan row exists as a stub from the start — so the link is technically available immediately.
It is withheld because sending an operator to an empty scan is worse than making them wait.

## B5 — Settings

Both roles. Settings exists because **a logged-in user currently has nowhere to change their own
password**: voluntary self-service change-password is the only change-password flow the product
has ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced periodic rotation was rejected as
NIST-misaligned, so there is no forced flow for it to compete with).

The scan target network is **not** here — it is a property of the Pi, not of the user (see B4).

```text
SETTINGS
  Change password
      [current] [new] [confirm] [Change password]   POST /auth/change-password  ✅ exists
      ok ..........................→ stay; confirmation copy
      400 policy / wrong current ..→ stay; inline error

  Profile — display name, email                     ⚠️ blocked — contract ask C3
      no /users/me endpoint exists; LoginResponse returns only a token, no user object.
      Whether the user model even has a display_name is unknown.
```

## Not breadboarded (out of scope for September)

LLM explainer panel ([`AI.md`](../roadmap/AI.md)) · Pi provisioning/pairing (installer-only,
[`AUTH.md`](../roadmap/AUTH.md)) · notifications · scan scheduling · theme toggle (dark mode is a
later pass, [`SCREENS.md` §Theme](SCREENS.md#theme)).

## Contract asks

Raised against [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) on
2026-07-13. Each blocks a flow above; none are frontend-solvable.

| # | Ask | Blocks |
| --- | --- | --- |
| C1 | `GET /api/v1/agents` — list agents (an array of one in the MVP). Today only `GET /agents/{id}` exists, and `agent_id` is the provisioning `X-Device-Id`, so the frontend cannot discover it. | B4, AGENTS |
| C2 | `AgentDetail.available_subnets` (reported by the Pi over its WS channel) + `target_subnet`, and a way to set it. Without these, `POST /commands` demands a `subnet` CIDR from a non-technical admin. **◐ Half-closed 2026-07-13: the WS half is locked** — the Pi sends a **`hello` frame on connect** carrying `available_subnets` (`interface` + `cidr`), now in the contract ([`ADR-011` §3](../adr/ADR-011-pi-command-channel.md)). **Still open: the HTTP half** — exposing them on `AgentDetail`, and the endpoint an admin uses to pick `target_subnet`. | B2, B4 |
| C3 | A user resource: `GET /users/me` + a way to update it. There is **no `/users` path in the contract at all**, and `LoginResponse` returns only a token. | B5 profile |
| C4 | Users & invites: list users, list pending invites, change role, revoke invite. Only `POST /invites` exists — the USERS & INVITES place is **mostly unbuildable** as breadboarded in B2. | B2, USERS & INVITES |
| ~~C5~~ | ~~Forced password change: login with an expired password returns 403 without a token, but `POST /auth/change-password` requires Bearer.~~ **✅ VOID 2026-07-13 — [`ADR-016`](../adr/ADR-016-password-policy.md) drops forced rotation entirely (NIST SP 800-63B §5.1.1.2); the mechanism this ask was about no longer exists.** Login is `200`/`401` only; there is no forced password-change flow or screen. | — |
| ~~C6~~ | ~~`HostSummary.first_seen_at`, to power the "new device on your network" item on HOME.~~ **✅ RESOLVED — `first_seen_at` is a required property on `HostSummary`.** The HOME item is unblocked but still unbuilt; shipping it is a product call, not a contract gap. | — |
| ~~C7~~ | ~~Does accept-invite issue a session?~~ **✅ RESOLVED 2026-07-13** — **yes.** It returns `201` with a full `LoginResponse`, so the invitee lands on HOME, not LOGIN. B2 above said the opposite and was corrected. Expiry is **`410`**, not `400`. | — |
| ~~C8~~ | ~~Does `FindingRecord` carry a `cve_id`?~~ **✅ RESOLVED 2026-07-13** — it does, along with `cvss_score` and `references`. Home copy stands. | — |
| ~~C9~~ | ~~`DevicePayload` (the `devices` array on `ScanDetailResponse`) carries **no `host_id`** — so a host row on SCAN DETAIL cannot link to HOST DETAIL.~~ **✅ RESOLVED 2026-08-02 (DMI-85) — the array is `hosts: ScanHostView[]` and `host_id` is required on it.** The route to that machine's full history exists. | — |
| C10 | A **failed scan has no reason**. `ScanDetailResponse` has no error field; the reason must be fetched via `command_id` → `GET /commands/{id}.error_code` — and `error_code` is a *code*, not a sentence, so it needs a plain-language mapping. A failed scan with a null `command_id` has no reason at all. | SCAN DETAIL, B3 "scan failed → failure reason" |
| ~~C11~~ | ~~Does `GET /findings?device_id=…` accept the **`host_id`** UUID?~~ **✅ RESOLVED 2026-07-13 — it becomes `GET /findings?host_id=…`.** The ask existed only because the [B7](../roadmap/BACKEND.md#b7--openapi-contract-) rename stopped at the paths and left the field names behind. The read model is now `hosts[]` / `host_count` / `host_id` / `host_ip` throughout; **only the Pi's ingest payload keeps `devices`** ([`ADR-011` §5](../adr/ADR-011-pi-command-channel.md)). One identifier, one name — HOST DETAIL can show findings. | — |
| ~~C12~~ | ~~**Does a dead Pi produce `failed` or `expired`?**~~ **✅ DECIDED 2026-07-13 — the split is `delivered_at`, not the timeout.** The command **never reached the Pi** (delivery gave up after 2 retries) → **`expired`**, set at the same moment the trigger returns `503 device_offline`. The command **reached the Pi and then broke** — Pi error, ingest failure, WS drop mid-scan, stale `running` — → **`failed`**. So the pills keep their distinct words, but **a Pi that dies mid-scan is now `failed`, not `expired`**: it took the job. `expired` means *it never even answered*. [`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-) no longer contradicts itself. | — |
| ~~C13~~ | ~~Does a bad `current_password` on `POST /auth/change-password` return **400 or 401**?~~ **✅ RESOLVED — `400`.** Spec 019 (DMI-72) landed the envelope and pinned `wrong_current_password` / `password_policy_violation`; DMI-77 finished the wording by retitling the route's `401` to pin it to `Authorization`-header failures only. A body field is not a credential (RFC 9110 §11.6.2), so a mistyped `current_password` never trips the refresh interceptor. | B5, SETTINGS |
| C14 | **`GET /invites?token=…`** — read an invite before accepting it. Without it ACCEPT INVITE knows *nothing*: it cannot name the org or the role (the sentence that tells a stranger the link is real), and the invitee must **type their own email from memory** to match `AcceptInviteRequest.email`. A typo then fails identically to a dead link, so the product's very first screen has to word its error vaguely. ⚠️ **Not `{token}` in the path** — DMI-77 moved the token out of the accept route's path to keep a live credential out of access logs; this ask predates that and was reworded to match. | B2, ACCEPT INVITE |
| ~~C15~~ | ~~Distinct `error.code` values on `POST /auth/reset-password`'s `400`.~~ **✅ RESOLVED 2026-08-03 (DMI-77).** Split by *status*, not just code: a dead/used link is **`410 invalid_reset_token`**, a rejected password is **`400 password_policy_violation`**. Both enums are pinned in the contract and gated by `test_contract_fidelity.py`. The token is checked first, so a dead link with a weak password yields the `410`. Matches accept-invite, so both token screens share one pattern. | B1, RESET PASSWORD |
| ~~C17~~ | ~~Nothing in the product can send an email.~~ **✅ DECIDED 2026-07-13 — transactional email is in scope; provider TBD.** The backend emails invites *and* reset links. Invites additionally keep the copyable link in the UI (email is the convenience, the link is the guarantee — a one-time login link from a security product sometimes lands in spam). **Reset has no such fallback** — a locked-out user has nobody to hand-carry a link — so this is what makes FORGOT/RESET buildable. Remaining work is a sending domain with **SPF/DKIM/DMARC**, not code. | — |
| ~~C18~~ | ~~`POST /invites` documents **only a `201`** — no error responses at all.~~ **✅ RESOLVED 2026-08-03 (DMI-77).** An address already in the caller's org is **`400 email_already_member`**; one that already holds an unconsumed, unexpired invite is **`409 invite_already_pending`** (and mints no second token — the check sits behind an advisory lock). The member check runs first, so an address that is both yields `email_already_member`. A different org's address is still unreported and returns `201`, per the anti-probing design. | B2, USERS & INVITES |
| C16 | **The user's role is not in the contract.** `LoginResponse` carries only a token; there is no user object anywhere. [`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis says the role comes from **JWT claims**, but the contract documents no claims — so the frontend would decode an unspecified payload to decide what to render. **Every "absent, not disabled" decision depends on this** (SCREENS rule 3): the `Users` nav item, `[Scan now]`, the network chooser, the invite form. Specify the claims, or return the role (fold into C3's `/users/me`). | **all role-gated UI** |

## Open decisions

Design calls, not contract gaps — settle these in this doc or in SCREENS.md.

| # | Question | Owner |
| --- | --- | --- |
| 1 | Coverage-stale threshold: "no completed scan in **N** days". Pi `online: false` is immediate; N is not chosen. | product |
| 2 | 409 `device_busy` toast copy | copywriting pass in SCREENS.md |
