# TRUTH — Users and invites admin API (DMI-76, contract ask C4)

## Narrative

Dmitri is multi-user and single-org: people join by invitation and hold one of two roles,
admin or viewer. An admin can already *create* an invitation and can now *remove* a member,
but there is no way to **see** the org — no list of members, no list of pending invitations —
and no way to correct the two mistakes that follow from inviting people: the wrong role, and
the wrong person. The USERS & INVITES screen therefore ships invite-only; it cannot show a
team it has no way to read.

This feature closes that gap with the admin read/manage surface: list members, list pending
invitations, change a member's role, revoke a pending invitation. Alongside it, members carry
an activity fact — when each person was last active — so an admin looking at the team can tell
a working account from a dormant one. Two activity facts are recorded, and they are different
things: when someone last *logged in* (proved their password) and when they were last *seen*
(their session was still alive). Only "last seen" is shown; login history is recorded now
because it cannot be reconstructed later, and is read when the audit surface lands.

Every write on this surface must preserve the org's standing invariant: **an organisation
always has at least one admin.** Removal already refuses to strip the last one. Role change is
the other door to the same room, and it must be shut with the same force — including when two
admins act at the same instant.

## Business rules

- Only an admin may read the member list or the pending-invitation list, change a role, or
  revoke an invitation. A viewer attempting any of them is refused as forbidden.
- All four operations are scoped to the caller's own organisation. A member or invitation of
  another organisation is indistinguishable from one that does not exist.
- **An admin may not change their own role.** Self-demotion is refused, mirroring the existing
  refusal to remove one's own account through the admin route.
- **An organisation always retains at least one admin.** A role change that would leave zero
  admins is refused — and that refusal holds under concurrency: two admins demoting each other
  simultaneously must end with exactly one admin remaining, never zero.
- Concurrency protection is one organisation-scoped, transaction-scoped serialization
  mechanism, shared in shape by every admin-reducing write, so that the removal routes can
  later adopt the same mechanism without two partial, incompatible locks colliding.
- Revoking a pending invitation makes its token immediately unusable. Only pending invitations
  can be revoked; an already-accepted or expired invitation is not a pending invitation.
- Members and invitations are two separate resources. They are read separately and joined for
  display by whoever renders them.
- A member's row carries: who they are (email), the role they hold, and when they were last seen.
  A member who has never been seen reports no last-seen value rather than a fabricated one.
- The member list carries **no status field**. Every member is an accepted, active member — the
  product has no suspended, disabled or deactivated account state, and a field that can only hold
  one value is not a fact worth publishing. A reader knows a row is an active member because it
  came from the member list; pending-ness is the invitation list's business.
- "Added at" is deliberately not carried: accepting an invitation starts a session immediately,
  so a member's first activity timestamp *is* their join date.
- **Last login** is stamped when a person authenticates with their password. **Last seen** is
  stamped both then and whenever their session is renewed. Renewing a session therefore advances
  last-seen but never last-login.
- Last login is never exposed by the member list.
- **Because the product now records when each person was last active and last signed in, and shows
  the first of those to their admins, every member must be able to find that out from the product
  itself.** The disclosure is shown on the account screen both roles can reach, not on the admin-only
  member screen — viewers are recorded too. It names both recorded times and states the limit: only
  those times, not what the person viewed or did. It is layered — a visible subject label, with the
  wording behind a control the member opens if they want it — so the screen stays a place to change
  a password rather than a notice board.
- The disclosure states a fact; it is not a setting. There is no way to switch the recording off,
  and offering one would misdescribe why the recording is lawful.
- The member opens the disclosure deliberately and it stays open until they close it. It does not
  appear and vanish as the pointer passes, because a person on a phone has no pointer to pass, and
  a notice nobody can hold still is not a notice.

## User stories

1. As an admin, I want to see everyone in my organisation and the role they hold, so that I can
   manage the team.
2. As an admin, I want to see which invitations are still outstanding, so that I know who has
   not joined yet.
3. As an admin, I want to correct a role I set wrong, so that access matches the person's job.
4. As an admin, I want to revoke an invitation I sent by mistake, so that it can never be used.
5. As an admin, I want to see when each member was last active, so that I can spot accounts
   nobody is using.
6. As an admin, I want the system to stop me from demoting myself or emptying the organisation
   of admins, so that I cannot lock everyone out.
7. As any member, admin or viewer, I want to find out what Dmitri records about my use of it and
   who can see it, without having to ask a colleague.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| List members | an admin in an org with several members | they read the member list | every member of that org is returned with email, role and last-seen |
| Member list omits login history | an admin | they read the member list | no last-login value appears anywhere in the response |
| Member list carries no status | an admin | they read the member list | no status field appears on any member row |
| Never-seen member | a member who has never renewed a session | the admin reads the member list | that member reports the last-seen recorded when they accepted their invitation |
| List pending invites | an org with a pending invitation | an admin reads the invitation list | the pending invitation is listed |
| Viewer forbidden — members | a viewer | they read the member list | the request is forbidden |
| Viewer forbidden — invites | a viewer | they read the invitation list | the request is forbidden |
| Viewer forbidden — role change | a viewer | they change another member's role | the request is forbidden |
| Viewer forbidden — revoke | a viewer | they revoke a pending invitation | the request is forbidden |
| Role change takes effect | an admin and a viewer in the same org | the admin promotes the viewer to admin | the promoted member's own profile subsequently reports the admin role |
| Self role change refused | an admin | they change their own role | the request is refused and their role is unchanged |
| Last admin protected | an org with exactly one admin | that admin's role is changed by any route | the change is refused and the org still has an admin |
| Concurrent mutual demotion | an org with exactly two admins | each demotes the other at the same time | exactly one admin remains; the org is never left with zero |
| Revoke kills the token | a pending invitation | an admin revokes it | the invitation token no longer works for acceptance |
| Revoke is pending-only | an invitation that was already accepted | an admin revokes it | the request is refused as not found |
| Org isolation — members | two organisations | an admin of one reads members | only their own organisation's members are returned |
| Org isolation — invites | two organisations | an admin of one reads invitations, or revokes another org's invitation | only their own invitations are visible; the other org's invitation is not found |
| Last seen advances on renewal | a member with a live session | their session is renewed | last-seen advances and last-login does not |
| Password login advances both | a member | they log in with their password | both last-seen and last-login advance |
| Disclosure is present | a member on the account screen | they look at it | a labelled control names activity as its subject, for a viewer as well as an admin |
| Disclosure states the facts | a member on the account screen | they open that control | the wording names both recorded times, says admins can see the activity time, and states that nothing else about their use is recorded |
| Disclosure is reachable without a mouse | a member using only a keyboard | they move to the control and activate it | the wording is revealed and is available to assistive technology |
| Disclosure is not a setting | a member reading it | they look for a way to turn the recording off | there is none, and none is implied |
| Contract published | the feature is complete | the published API contract is inspected | it documents the member list, invitation list, role change and revoke, including their forbidden and refusal responses |
| Gates pass | the touched scope | the backend lint and test gates run | both pass with the database up and no database-test skips |

## Out of scope (v1)

- Multi-organisation, SSO, audit log, bulk invitation. Note the cost of leaving the audit log out:
  revoking an invitation erases every trace that it existed — who was invited, to what role, and
  that it was withdrawn. That history cannot be recovered later, so the audit surface, whenever it
  lands, starts from the day it ships.
- Removing a user — that is DMI-102, already delivered; this feature only keeps the role-change
  half of the last-admin invariant.
- Reading a single invitation by its token before acceptance — that is DMI-86.
- Changing the error responses of invitation creation — that is DMI-77.
- The admin surface that consumes these endpoints — the member table, the role control, the revoke
  action. That is DMI-90. The **one** web change in scope here is the activity disclosure below.
- Exposing last-login to any reader; the audit surface that reads it is a later phase.
- Re-sending an invitation, or editing a pending invitation's role or email.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Decisions: `docs/adr/ADR-017-account-removal.md` (last-admin invariant, concurrency
  limitation, DMI-105 hardening), `docs/research/user-last-seen-tracking.md` (activity
  column constraints — note this feature records **both** last-login and last-seen, which
  supersedes the research doc's single-column recommendation).
