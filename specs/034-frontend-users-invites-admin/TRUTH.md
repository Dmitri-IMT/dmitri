# TRUTH — Users and invites admin surface

Domain language and verifiable behaviour only. No file paths, no endpoints, no code.

Issue: **DMI-90**. Screen spec: `docs/ui/SCREENS.md` § USERS & INVITES (source of truth for all
copy). Decision record: `docs/adr/ADR-017-account-removal.md`.

## Narrative

The pilot organisation needs more than one account, and today the only way to add one is a raw
API call. This is the screen where an admin invites a colleague, sees who is already in, fixes a
role set wrong, revokes an invite sent to the wrong address, and removes someone who has left.

It is the product's **first genuinely admin-only surface**. Every earlier screen is readable by
both roles, so until now the rule that viewers never see actions they cannot take has had nothing
to bite on. This screen is where that rule becomes real code and a real test.

The backend for all of it already exists. Nothing here is blocked; this is the frontend catching
up to a contract that shipped.

## Definitions

| Term | Meaning |
|------|---------|
| **Member** | A person with an account in the organisation. Has a role and a last-seen time. |
| **Pending invite** | An issued, unaccepted, unexpired invitation. Has an email and a role, but no account and no last-seen time. |
| **Person row** | One row of the table — either a member or a pending invite. The table shows both kinds. |
| **Own row** | The signed-in admin's own member row. |
| **Status** | Derived, not stored: a member reads "Active", a pending invite reads "Invited — expires in N days". |

## Business rules

**Access**

1. The surface is admin-only. A viewer sees **neither** the `Users` nav item **nor** the route: the
   nav item is absent from the page, and navigating directly to the route yields the ordinary
   not-found page, never an access-denied message. A viewer must not be able to learn the surface
   exists.
2. **Absent, not disabled — this governs permission, not progress.** No control a viewer lacks
   permission to use is ever rendered greyed out; it is not rendered at all. A control the admin
   *is* permitted to use may be greyed while it waits for required input — the removal confirm
   button is greyed, unclickable and out of the tab order until the typed address matches. The two
   are different rules and only the first is about roles.

**The table**

3. Members and pending invites are shown in **one** table with the columns *Person · Role · Status ·
   Last seen*. They are fetched as two separate lists and merged for display only.
4. Members are listed first, in the order the members list already returns them (most recently
   active first, never-recorded last), then pending invites, soonest to expire first. The two kinds
   are never interleaved.
5. A pending invite shows no last-seen value. A member whose last-seen time was never recorded
   reads **"Not recorded yet"** — a distinct third case, meaning the product has no measurement,
   not that the person is inactive.
6. When the signed-in admin is the **only** person in the organisation — no other member and no
   pending invite — the table chrome is dropped and a single line says so. The screen is never
   truly empty, because the admin reading it is in the organisation; showing column headings over
   one inert row would be chrome asserting more than it holds. The invite action stays, because it
   is the exact action this state calls for.
7. If **either** list fails to load, the whole table shows its error state with a retry, and no
   rows at all. A member list silently missing its pending invites would read as a complete answer
   to "who can reach our data" while being a wrong one.

**Row actions**

8. A member's role is changed from a dropdown on their row, confirmed by a single click in a
   dialog naming the person and the new role. A role change is reversible in two clicks, so it is
   not confirmed by typing.
9. A member is removed by confirming with the **target's own email address, typed exactly**.
   Removal is permanent and ends that person's session immediately. Typing is reserved for actions
   that cannot be undone.
10. A pending invite can be **revoked but not re-roled**. Its role is plain text, not a dropdown —
   fixing a wrong role on an invite means revoking it and issuing a new one.
11. The **own row carries neither a Remove action nor a role control.** An admin leaves the
    organisation from Settings instead, and cannot demote themselves at all.
12. Rules 10 and 11 together make a zero-admin organisation unreachable from this screen: the person
    performing any write here always survives it as an admin.
13. A successful role change, removal or revocation raises a **toast naming the person and what
    happened**, and the table refreshes. The row alone is too weak a signal — a role cell changing,
    or a row quietly vanishing, is indistinguishable from a mis-click.
14. Each row action has exactly **one** failure message and a retry. No message is written for a
    refusal this screen cannot provoke.

**Inviting**

15. Inviting opens a dialog holding the email and role. On success the same dialog becomes a
    confirmation carrying the **copyable invite link**. The invitee is also emailed, but the link
    is the guarantee: a security product's one-time login link is structurally indistinguishable
    from phishing and will sometimes land in spam.
16. The link is shown **once**, and the confirmation says so. Dismissing the dialog refreshes the
    table so the new pending invite appears. A successful invite raises **no** toast — the dialog
    already is the confirmation, and must be dismissed deliberately.
17. Re-inviting is the likeliest repeat action here and is not treated as an edge case. Three
    outcomes are distinguished in copy:
    - the address already belongs to a member of this organisation,
    - the address already holds a live pending invite,
    - anything else.
    The first two lead to different admin actions — "nothing to do" versus "wait or reissue" — so
    they must not share a message. When an address is both, the already-a-member message wins.

## User stories

1. As an admin, I invite a colleague and hand them the link myself if the email is slow.
2. As an admin, I see who is in my organisation and at what role.
3. As an admin, I fix a role I set wrong, without fear of locking myself out.
4. As an admin, I revoke an invite I sent to the wrong address.
5. As an admin, I remove someone who has left the company, and their access ends immediately.
6. As a viewer, I never learn this surface exists.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Viewer: no nav item | a signed-in viewer | the app shell renders | the `Users` nav item is **absent from the DOM** — not present and disabled |
| Viewer: no route | a signed-in viewer | they navigate directly to the Users route | the ordinary not-found page renders, and no part of the Users surface does |
| Admin: nav item works | a signed-in admin | the app shell renders | the `Users` nav item is present and navigates to the Users screen |
| Role gating is absence | either role | any screen renders | no affordance is present-but-greyed **because of the viewer's role**; role-gated controls are absent or fully live |
| One merged table | an org with two members and one pending invite | the screen loads | one table renders three rows — members first, the pending invite last |
| Pending has no last-seen | an org with a pending invite | the screen loads | that row's Last seen cell reads `—` and its Status reads that it is invited and when it expires |
| Never-recorded member | a member whose last-seen time was never recorded | the screen loads | that row's Last seen cell reads "Not recorded yet", and the row sorts below members that have one |
| Only person in the org | an admin whose org has no other member and no pending invite | the screen loads | the table chrome is absent, one line says they are the only person here, and the invite action is still present |
| Partial load failure | the members list loads and the invites list fails | the screen loads | the whole table shows its error state with a retry, and **no rows render** |
| Own row is inert | a signed-in admin | the table renders | their own row shows no Remove action and no role dropdown; their role is plain text |
| Pending row cannot be re-roled | a pending invite row | the table renders | its role is plain text with no dropdown, and its only action is revoke |
| Role change asks once | an admin and another member | the admin picks a new role from that member's dropdown | a dialog names the person and the new role and asks for a single confirming click — it does not ask them to type anything |
| Role change succeeds | the role-change dialog is confirmed | the request succeeds | a toast names the person and their new role, and the table refreshes without a full page reload |
| Remove requires the exact address | an admin removing another member | they open the remove confirmation | the confirm action stays inert until the target's exact email is typed; a mistyped address never fires the request |
| Remove succeeds | a confirmed removal | the request succeeds | a toast names the removed person, and their row is gone without a full page reload |
| Revoke succeeds | a pending invite | the admin revokes it | a toast names the invited address, and the row is gone without a full page reload |
| Row action failure | any row action | the request fails | one plain failure message and a retry render — no message mentioning a refusal this screen cannot cause |
| Invite shows a link | an admin | they invite a new address successfully | the dialog shows a copyable link alongside the confirmation, and says the link is shown only once |
| Invite refreshes the table | a successful invite | the dialog is dismissed | the table refreshes and the new pending invite is present |
| Invite raises no toast | a successful invite | the dialog is showing the confirmation | no toast is raised — the dialog is the confirmation |
| Re-invite: already a member | an address belonging to an existing member | the admin invites it | the message specific to that case renders, not a generic failure |
| Re-invite: already invited | an address holding a live pending invite | the admin invites it | a **distinct** message for that case renders |
| Gate | the touched scope | the frontend gate runs | lint, typecheck, test and build all pass, and every request and response type comes from the generated contract types |

## Out of scope (v1)

- **Self-removal.** An admin leaving the organisation is Settings' job, already shipped.
- No bulk invite, no CSV import, no org settings screen.
- No SSO or identity-provider surfaces.
- No copy for refusals this screen cannot provoke — specifically, changing your own role and
  demoting the last admin. Both remain backend guards against direct API calls.
- No optimistic updates: every mutation refreshes the lists from the server rather than guessing.
- No search, filter, sort controls, or pagination on the table.
- No profile fields on a row beyond email, role, status and last seen.
- No audit record of who changed or removed whom.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
