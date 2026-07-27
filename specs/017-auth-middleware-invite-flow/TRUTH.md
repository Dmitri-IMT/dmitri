# TRUTH — Auth middleware + invite flow (DMI-61)

## Narrative

DMI-60 gave Dmitri sessions: an operator can log in, refresh, and reset a password. But
nothing yet *uses* those sessions. The business routes shipped so far — hosts, scans,
findings — answer anyone who asks, with no token and no tenant boundary, and there is still
no way to bring a second person into an org. On the device side, the `agents` table can hold a
per-device credential, but no code verifies one, so the Pi has no way to prove who it is.

This feature closes AUTH.md Phase 1. It builds the two authentication gates the rest of the
product mounts rather than reinvents — a JWT gate that knows the role matrix, and a device gate
that verifies a per-device signature — and it lands the invite flow that lets an admin onboard a
teammate. After this, the command-channel work (WebSocket upgrade, scan ingest) attaches
ready-made gates instead of inventing auth twice, and an org admin can actually grow their team.

The device gate uses **asymmetric** signatures (Ed25519, per ADR-005 as amended 2026-07-24). The
Pi holds a private key and signs each request; the backend stores only that device's **public
key** and verifies with it. This matters beyond cryptographic taste: the backend never holds a
secret that could impersonate a device, so a database leak exposes nothing forgeable, and there
is nothing to encrypt at rest (this is why ADR-015 is retired). It also shrinks provisioning —
the private key is born on the device and never travels.

Two things the gates must get right, because they are the difference between a lock and a
decoration. First, a role check without a tenant check is a half-closed door: enforcing that a
`viewer` cannot mutate is worthless if that viewer can read another company's findings, so
every business read is scoped to the caller's org. Second, a valid signature without replay
protection is a reusable password: a captured request could be replayed forever, so every
device request carries a nonce that is remembered and refused the second time.

## Business rules

### Roles and the JWT gate

- Every business route requires a valid access token. Missing or invalid token → `401`.
- The role matrix from AUTH.md is authoritative and complete:

  | Role | Read (scans, hosts, agents) | Trigger scan | Invite users | Pi provisioning |
  |------|------------------------------|--------------|--------------|-----------------|
  | `viewer` | Yes | No | No | No |
  | `admin` | Yes | Yes | Yes | No (installer/vendor) |

- An authenticated caller whose role is insufficient for the operation → `403`, never `401`.
  `401` means "I don't know who you are"; `403` means "I know, and you may not."
- **Neither role provisions Pi devices.** No route in this product grants device provisioning
  to a logged-in user; that is an installer/vendor action outside the web app.
- **Tenant scoping**: every business read returns only records belonging to the caller's org.
  A record that exists but belongs to another org is indistinguishable from one that does not
  exist (`404`, not `403` — a `403` would confirm the record exists).

### Invites

- Only an `admin` may create an invite. A `viewer` attempting it gets `403`.
- An invite names an email and a role (`admin` or `viewer`) and belongs to the creating
  admin's org — the creator cannot invite into another org.
- Creation returns a single-use invite token and its expiry. The token is delivered to the
  invitee as a link; the raw token is never recoverable from storage afterwards.
- Invite links are **single-use** and **short-lived** (24–72 h per AUTH.md).
- Accepting an invite requires no prior authentication — the invitee has no account yet.
  Acceptance creates the user in the invite's org with the invite's role, consumes the invite,
  and signs the new user in immediately (access token + refresh cookie) so they land in the
  product rather than at a login screen.
- The password chosen at acceptance is subject to the **same policy** enforced everywhere else
  (DMI-60 / ADR-016: length, breach screening, pattern and personal-data rejection). A policy
  violation → `400`, and no account is created.
- An expired or already-consumed invite → `410`, deliberately distinct from `400`, so the
  frontend can say "this link is dead" rather than "your password is bad".
- **An email address identifies exactly one person in exactly one org, product-wide.** Sign-in
  asks only for an email and a password, so an address that existed in two orgs could not be
  resolved to a single account — the same credentials would land in an arbitrary tenant.
  Accepting an invite for an email that already has an account **anywhere** is therefore
  rejected, not just within the inviting org. This is coherent with invite-only onboarding: a
  person is brought into one company, and nobody self-registers into a second.
- A rejected acceptance does not consume the invite; the link still works for a corrected
  attempt.
- **Inviting someone who is already a member of your org is refused at creation**, so an admin
  learns immediately rather than handing out a link that was always going to fail. This check is
  scoped to the admin's **own org only**. It deliberately does *not* ask whether the address
  belongs to some other company: the global rule above still applies, but enforcing it at creation
  would turn the invite box into an oracle for discovering who works at another org — which is the
  same tenant boundary the rest of this feature exists to defend. An address belonging to another
  org therefore yields a normal invite that fails on acceptance.
- **Bootstrap**: the very first admin of a new org arrives through this same acceptance flow.
  The org and its first invite are created by a vendor-run management command, not by an HTTP
  endpoint — there is no public path to creating an org.

### The device (Ed25519) gate

- A device authenticates by signing a canonical request string with its own **private key**
  (Ed25519, per ADR-005 as amended 2026-07-24). It sends its `agent_id`, a timestamp, a nonce, a
  body hash, and the signature. The canonical string, the five headers, the skew window, and the
  nonce rule are all unchanged from the original ADR-005 envelope — only the signature algorithm
  and the verification step differ.
- The backend **verifies** the signature against the **public key** it stores for that device.
  There is no shared secret and nothing to recompute. A bad signature, a missing header, a
  malformed header, or an unknown device → `401`.
- The backend stores only the device's public key. A public key is not a secret: it is held in
  the clear, and a full database read leaks nothing that can forge a device's requests.
- **Clock skew**: a timestamp more than 5 minutes from server time → `401`.
- **Replay**: a nonce already seen for that device inside the validity window → `401`. Nonces
  are remembered for at least the skew window; expired nonce records are prunable.
- A **revoked** device → `403` (we know the device; it is no longer allowed), distinct from the
  `401` of a bad signature.
- The device never states which org it belongs to. Tenant is resolved from the device record
  server-side; an `org_id` supplied by a device is ignored.
- **Provisioning**: a device is registered by recording its `agent_id`, `org_id`, and **public
  key** — the private key is generated on the device and never leaves it, so no secret is ever
  transmitted to or stored by the backend. Registration is a vendor-run management command, not
  an HTTP endpoint (same audience and posture as org bootstrap).
- The gate is verification only. No route is required to mount it in this feature — the
  command channel and scan ingest mount it later.

## User stories

1. As an org admin, I want to generate an invite link so a teammate can join my org as `admin`
   or `viewer` without me handling their password.
2. As an invitee, I want to open a link, choose my own password, and be signed in immediately,
   so onboarding is one step.
3. As an operator, I want business routes to reject callers without a valid session, so our
   scan data isn't public.
4. As an org admin, I want to be certain another company cannot read my hosts and findings,
   so tenancy is a real boundary and not a convention.
5. As a `viewer`, I want to be prevented from actions I'm not entitled to, so least privilege
   is enforced by the API rather than by the UI hiding buttons.
6. As the command-channel and ingest work, I want ready-made JWT and device-signature gates to
   mount, so auth is written and reviewed once.
7. As the vendor, I want to stand up a new customer's org and first admin from a management
   command, so onboarding a company needs no seeded password and no public signup.
8. As an installer, I want to register a Pi by handing the backend its **public** key, so no
   device secret is ever transmitted over the provisioning channel.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Anonymous is refused | no token | I call any business read route | `401` |
| Invalid token refused | a malformed or expired access token | I call a business read route | `401` |
| Viewer may read | a `viewer` token | I call a business read route | `200` with that org's data |
| Admin may read | an `admin` token | I call a business read route | `200` with that org's data |
| Viewer may not mutate | a `viewer` token | I call an admin-only route | `403` (not `401`) |
| Cross-org read is invisible | an `admin` token for org A | I request a record belonging to org B by id | `404` |
| Cross-org list is filtered | data in orgs A and B | a caller in org A lists hosts / findings | only org A records appear |
| Admin creates invite | an `admin` token | I `POST` an invite for an email + role | `201` with a single-use token and an expiry |
| Viewer cannot invite | a `viewer` token | I `POST` an invite | `403`, no invite created |
| Inviting an existing member fails fast | an `admin` in org A, and an email already a user in org A | I `POST` an invite for it | `400`, no invite created |
| Inviting another org's user is not an oracle | an `admin` in org A, and an email already a user in org B | I `POST` an invite for it | `201` — creation is indistinguishable from inviting an unknown address; the acceptance is what fails |
| Invite is org-bound | an `admin` in org A | the invite is accepted | the new user is created in org A with the invited role |
| Acceptance signs in | a valid unexpired invite | I accept with a policy-valid password | `201` with an access token and a refresh cookie; the user can immediately call a business route |
| Single use | an invite already accepted | I accept it again | `410`, no second account |
| Expired invite | an invite past its TTL | I accept it | `410` |
| Unknown token | an invite token that never existed | I accept it | `410` |
| Weak password at acceptance | a valid invite | I accept with a policy-violating password | `400`, no account created, invite still unconsumed |
| Breached password at acceptance | a valid invite | I accept with a known-breached password | `400`, no account created |
| Duplicate email, same org | an email already registered in that org | I accept an invite for it | rejected, invite not consumed |
| Duplicate email, other org | an email already registered in a **different** org | I accept an invite for it | rejected, invite not consumed |
| Email resolves one account | any email in the system | sign-in looks it up | at most one account matches, guaranteed by storage, not by convention |
| Valid signature passes | a device whose public key is registered | it signs a request with its private key | the gate verifies it and resolves the device and its org |
| Bad signature refused | a request signed with a private key not matching the stored public key | the gate runs | `401` |
| Tampered body refused | a valid signature but a modified body | the gate runs | `401` |
| Unknown device refused | a signature for an `agent_id` with no record | the gate runs | `401` |
| Stale timestamp refused | a request timestamped 6+ minutes off | the gate runs | `401` |
| Replay refused | a request that already succeeded | it is sent again verbatim | `401` |
| Same nonce, different device | two devices using the same nonce value | both send valid requests | both pass — nonce uniqueness is per device |
| Revoked device refused | a device with a revocation date | it sends a perfectly valid signature | `403` (not `401`) |
| No secret stored at rest | the stored device row | it is read directly | it holds only a public key; there is no secret, encrypted or otherwise, to leak |
| Device cannot claim an org | a device request asserting a different org | the gate runs | the org from the device record wins |
| Provisioning registers a public key | a device keypair generated off-backend | the vendor registers the device with its public key | an `agents` row exists with that public key, `org_id`, and `agent_id`; the device can then authenticate, and no private key ever reached the backend |
| Bootstrap creates an org | a fresh database | the vendor runs the bootstrap command | an org and a single-use admin invite exist, and accepting it produces a working admin |
| Suite green | the touched scope | I run `uv run pytest` and `uv run ruff check` | both pass |

## Out of scope (v1)

- **No agent or command routes.** The WebSocket upgrade (DMI-62) and the scan ingest endpoint
  (DMI-63) mount the device gate; this feature only builds it. No route mounts it here.
- **No admin UI.** API only; the users & invites screens are frontend work.
- **No users & invites admin API** beyond the two contracted invite endpoints — listing,
  revoking, or resending invites and managing users is DMI-76.
- **No device-key rotation and no self-service pairing** (Phase 2). Device provisioning exists
  only as the vendor-run CLI that registers a public key; there is no HTTP provisioning endpoint
  and no admin-UI pairing flow.
- **No on-device keypair generation.** The Pi generating and storing its Ed25519 private key and
  signing requests is Pi-side work (DMI-57 / DMI-65). This feature only records the public key and
  verifies signatures; tests generate throwaway keypairs to exercise the gate.
- **No real invite email delivery** — DMI-71 owns the mailer and sending domain. Invites use the
  existing mail seam; console logging is not a shippable delivery path.
- **No invite-link construction.** Creation returns the invite **token**, not a URL. Whoever needs
  a clickable link builds it: the admin screen (DMI-76) composes one from the browser's own origin,
  and the invite email (DMI-71) composes one from a base-URL setting that DMI-71 introduces when it
  actually sends mail. This feature adds no such setting — there is nothing here for it to
  configure.
- No MFA, no logout-everywhere, no idle timeout, no session cap (Phase 2).
- No finer-grained permission matrix (Phase 2).

## Related specs

- Implementation: `ARCHITECTURE.md`
- Predecessor: `specs/016-sessions-auth-routes/` (sessions, tokens, password policy — reused)
- Data model: `specs/016-command-channel-data-model/` (the `agents` table this gate reads; its
  three encrypted-secret columns are replaced here by a `public_key` column)
- Product decisions: `docs/roadmap/AUTH.md` (Phase 1 role matrix, invites, bootstrap E2,
  Ed25519 provisioning flow)
- Architecture decisions: `docs/adr/ADR-005-security-model.md` (device-signature rules, canonical
  string, skew, replay — **amended 2026-07-24 to Ed25519**),
  `docs/adr/ADR-015-agent-secret-storage-at-rest.md` (**retired** by that amendment — no secret to
  store), `docs/adr/ADR-011-pi-command-channel.md` (same signature rules on the WS upgrade),
  `docs/adr/ADR-016-password-policy.md` (policy at invite acceptance)
- Decision record: `docs/research/device-auth-hmac-vs-asymmetric.md` (why Ed25519 over HMAC)
- Frozen contract: `contracts/openapi/openapi.yaml` (`/api/v1/invites`,
  `/api/v1/invites/{token}/accept`, `AgentSignatureAuth`, `FrontendBearerAuth`)
- Execution ledger: `POOP.md` (written during orchestration)
