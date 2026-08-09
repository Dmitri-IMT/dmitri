# TRUTH — Account removal: leaving an organisation, and being removed from one

Domain language and verifiable behaviour only. No file paths, no code.

Part of contract ask **C4**. Decided in [`ADR-017`](../../docs/adr/ADR-017-account-removal.md)
(2026-08-08), summarised in [`AUTH.md`](../../docs/roadmap/AUTH.md) § Account removal. Linear:
**DMI-102**, under epic DMI-70, milestone *MVP — Control*.

ADR-017 **reverses** the "no user deletion/deactivation" exclusion that DMI-76 and DMI-90 both
carried. This spec is the **backend half only**; the two screens that consume it are DMI-90
(Users) and DMI-103 (Settings).

## Narrative

Dmitri has a way in and no way out. An organisation invites someone, they choose a password,
and from that moment nothing in the product can remove them. There is no deletion, no
deactivation, no expiry — the account is permanent by omission rather than by decision.

The consequence is concrete. Someone leaves the company on a Friday and on Monday their
password still authenticates, their refresh token still rotates for up to a week, and they can
still read every scan, every host and every finding the organisation holds. For a product whose
entire subject is knowing who can reach what, a departed employee retaining full read access is
the wrong default.

A second, quieter gap sits beside it: a member who wants out has nobody to ask. A viewer never
sees the Users screen, so without a self-service route they are locked into an organisation
they may no longer belong to.

This was scheduled for Phase 2 and is pulled forward because it costs almost nothing to build —
no Pi, no hardware, no new contract machinery — and because the gap it leaves open is a
security gap in a security product.

**Removal is a hard delete, and that is the load-bearing decision.** The organisation's records
of what was scanned and found are not owned by the member and survive untouched; the only rows
that follow the member out are their live session and any password-reset tokens they hold.
Nothing is deactivated, nothing is tombstoned. ADR-017 rejects soft delete on a specific,
concrete ground rather than on taste: an address may hold only one account in the entire
product, so a retained tombstone would occupy that address forever and silently block the most
likely follow-up of all — re-inviting someone removed by mistake, or returning to the company.

**And one invariant is protected on the ordinary path: an organisation retains at least one
admin.** An organisation with none can invite nobody, promote nobody and manage nothing;
recovering it means a human editing the database by hand. The route that removes *someone else*
refuses to target the caller, so a single such request always leaves its admin caller behind.
Only the route by which a member removes *themselves* can reach zero on its own, and it is the
only place that counts admins. Concurrent admin removals are a known race deferred to DMI-105.

## Business rules

- **Removal is permanent and immediate.** There is no deactivated, suspended or disabled state
  anywhere in the product, no undo, and no grace period.
- Removing a member removes their live session with them — no separate revocation step. Their
  ability to *renew* that session dies immediately and cannot outlive the removal.
- **Known authorization bug (DMI-104):** their already-issued access credential is not revoked
  and remains usable for the remainder of its short lifetime. The existing authentication gates
  trust its identity and role claims without re-checking that the member still exists, so the
  credential can still authorize organisation reads and, for a removed admin, admin actions.
  Removal ends session renewal immediately and shortens the departed member's window from a week
  to minutes; it does not close that window. Closing it is separate follow-up work — see *Out of
  scope*.
- **A removed member's address becomes free again.** They can be invited back afterwards and
  the invitation succeeds exactly as it would for a stranger.
- Removal takes nothing else with it. The organisation's scans, hosts, findings and agents are
  the organisation's, not the member's, and are untouched.
- **Any member may remove their own account, whatever their role.** Leaving is not an
  administrative privilege.
- **Only an admin may remove somebody else**, and only within their own organisation.
- **An admin may not remove another account that is their own.** Removing themselves is a
  distinct, deliberate act with its own route; targeting your own account through the
  remove-someone-else route is refused as a **conflict of state**, distinctly identifiable and
  directing them to remove their account from Settings instead. It is deliberately *not*
  reported as not-found: the
  caller can see their own account listed, so denying its existence would be a lie the Users
  screen then has to word around.
- **An admin may remove another admin**, provided the invariant below still holds afterwards.
  Admins are mutually trusted by design and a departing admin must be removable without a
  second ceremony. Decided 2026-08-08 rather than left true by silence. Note the consequence:
  one admin may remove all the others and be left in sole control, and because removal is
  deliberately unrecorded and unannounced, nothing surfaces that afterwards until the Phase 2
  audit trail exists.
- **An organisation retains at least one admin through every ordinary removal flow** — one, not
  two. In a two-admin organisation either admin may remove the other, leaving the survivor as
  sole admin. A member who is their organisation's only admin cannot remove themselves. This is
  reported as a *conflict of state*, not as a denial of permission — they hold every permission
  the action requires; it is the organisation's condition that refuses. Once a second admin
  exists the same request succeeds.
- The invariant is about admins alone. Removing the last **viewer** — even the last member who
  is not an admin — is ordinary and allowed.
- **Known concurrency race:** v1 does not serialize admin removals. Two admins removing
  themselves simultaneously, or concurrently targeting each other, can both pass their ordinary
  checks and leave the organisation with no admin. Hardening both routes together is deferred to
  DMI-105 rather than partially solved here.
- **A member of another organisation is reported as not existing.** An admin who names an
  account outside their own organisation learns nothing about whether it exists, in keeping
  with the rule the product already applies to every business read. That member is unaffected.
- **The removed person is told nothing.** No email is sent. Requests through row-backed identity
  routes and the next attempt to renew the session fail as unauthenticated; the known DMI-104
  bearer-token authorization bug remains until the credential expires.
- **Removal leaves no record of itself.** By ADR-017 this is deliberate: there is nowhere
  append-only to write such a record today, and a trail that can be edited is worse than none.
  The audit trail is Phase 2 work with its own store.

## User stories

1. As an admin, I want to remove someone who has left the company, so that their account and
   ability to renew its session end immediately rather than remaining usable for a week.
2. As any member, whatever my role, I want to leave an organisation I no longer belong to
   without having to ask anyone's permission, so that I am never locked into it.
3. As the only admin of my organisation, I want to be stopped from removing myself, so that I
   cannot accidentally leave the organisation with nobody able to manage it.
4. As an admin who removed the wrong person, I want to invite them straight back, so that an
   honest mistake costs an invitation rather than a support request.
5. As a member of one organisation, I want an admin of another to be unable to learn that my
   account exists, let alone remove it.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Admin removes a member | An admin and another member of the same organisation | The admin removes that member | The request succeeds with no content; the member's account no longer exists |
| Admin retries a completed removal | An admin has removed another member, but did not receive the successful response | The admin retries the same removal | It is reported as not found because the target no longer exists |
| Member retries completed self-removal | A member has removed themselves, but did not receive the successful response | Their old access credential retries self-removal | It is refused as unauthenticated because the caller no longer exists |
| Removal ends the session | A member with a live session that has been refreshing normally | An admin removes them | Their existing session can no longer be refreshed; the attempt fails as unauthenticated |
| Removed credentials cannot log in | A removed member knows the password they used before removal | They try to log in with the removed address and password | Authentication fails with the same invalid-credentials response as an unknown account |
| Removal is felt on identity routes | A removed member still holding an unexpired access credential | They call a route that resolves the caller against stored state | It fails as unauthenticated |
| Admin removes a peer admin | An organisation with two admins | One removes the other | It succeeds; the survivor is the sole admin |
| Any role may leave | A member whose role is **viewer**, in an organisation that has an admin | They remove their own account | It succeeds; the route is deliberately not restricted to admins |
| An admin may leave too | An organisation with two admins | One of them removes their own account | It succeeds |
| A viewer cannot remove others | A viewer and another member of the same organisation | The viewer tries to remove that member | It is refused as forbidden; the other member still exists |
| Self-targeting the other route is refused | An admin | The admin names **their own account** on the remove-someone-else route | It is refused as a **conflict of state**, distinctly identifiable as the self-target condition and distinguishable from both not-found and forbidden; the admin still exists |
| Sole admin cannot leave | An organisation whose only admin is the caller | That admin removes their own account | It is refused as a **conflict of state**, distinctly identifiable as the last-admin condition; the account still exists |
| A second admin unblocks it | The same organisation, after a second admin exists | The first admin removes their own account | It succeeds |
| Viewers are not load-bearing | An organisation with one admin and one viewer | The admin removes the viewer | It succeeds; only admins protect the invariant |
| Foreign member is unknown | An admin of one organisation and a member of another | The admin tries to remove that foreign member | It is reported as not found — never as forbidden — and that member still exists |
| A removed address is reusable | A member has been removed | Their address is invited to the organisation again | The invitation is created and can be accepted, producing a working account |
| Organisation data survives | An organisation with scans, hosts and findings, and a member | That member is removed | Every scan, host, finding and agent is unchanged and still readable by the remaining members |
| Reset tokens go too | A member who has an outstanding password-reset token | They are removed | That token no longer resolves to anybody and cannot be used |
| Removal is unauthenticated-proof | No session at all | Either removal is attempted | It is refused as unauthenticated; nothing is removed |
| The cookie is left alone | A member with a refresh cookie in their browser | They remove their own account | The response does not clear the cookie; the cookie's next use fails as unauthenticated because the session behind it is gone |
| Contract is published | The feature is implemented | The published API contract is inspected | Both removals appear with their success and failure shapes, the last-admin failure code is present in the pinned failure vocabulary, and the contract-fidelity check passes |
| Gates are green | The feature is implemented | The backend lint and test gates are run against a live test database | Both pass with **zero skipped tests** |

## Out of scope (v1)

- **Any form of soft delete** — no deactivation, no suspension, no tombstone, no undo, no
  grace period, no restore.
- **Notifying the removed person.** No email, no in-product notice.
- **An audit record of the removal.** Deliberate per ADR-017; the append-only trail is Phase 2
  and needs its own store.
- **Bulk removal** and **organisation deletion**.
- **Serializing concurrent admin removal.** Both simultaneous self-removal and simultaneous
  peer cross-removal are known races. DMI-105 owns one complete solution across both routes;
  this feature adds no partial concurrency mechanism.
- **The last member of an organisation cannot leave it.** They are necessarily its only admin,
  so the invariant refuses them, and there is no other door. Accepted deliberately on
  2026-08-08: their departure would orphan every scan, host and finding with nobody able to
  reach or remove them, and the honest fix is organisation deletion, which is not scheduled.
  Until then a sole member invites an admin first, or asks support. Every organisation passes
  through this state, since `bootstrap_org` creates exactly one member.
- **Closing the known authorization bug described above.** Claims-only gates do not re-check that
  the caller still exists, so a removed member retains organisation reads and a removed admin can
  retain admin actions until the credential expires. Those gates predate this feature and are
  shared across existing routes, so changing them belongs to **DMI-104**, not this feature.
- **Role changes of any kind**, including the self-demotion refusal that ADR-017 § 4 decides.
  That rule belongs to the role-change route and ships with DMI-76.
- **Member activity** (`last_login_at` / `last_seen_at`), decided the same day in
  [`AUTH.md`](../../docs/roadmap/AUTH.md) § Member activity. Same ADR session, different
  feature; not this spec.
- **All frontend work**, including the confirm-by-typing-the-address component that ADR-017
  § 5 requires of both removal surfaces. That is DMI-90 and DMI-103, which this unblocks.
- Rate limiting. There is none in the service today and this adds none.

## Related specs

- Implementation: `ARCHITECTURE.md`
- No `DESIGN.md` — this feature changes no screen. The screens that consume it are DMI-90
  (Users) and DMI-103 (Settings).
- Decision of record: [`ADR-017`](../../docs/adr/ADR-017-account-removal.md)
- Prior art: `specs/017-auth-middleware-invite-flow/` (`require_user` / `require_admin`,
  org-scoping → 404), `specs/019-users-me-and-error-envelope/` (the `/users/me` precedent and
  the error envelope), `specs/023-auth-invite-contract-edges/` (contract fidelity)
