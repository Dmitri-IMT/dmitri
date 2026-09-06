# TRUTH — Home events, activity log, and attention paging

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

Issue: **DMI-136**. Screen language: device vs machine, Foundations pagination (icon-only previous/next, names “Previous page” / “Next page”). Approved Home layout this completes: `specs/042-design-system/DESIGN.md` §3 and §16, v4 exemplar.

## Narrative

Home already tells an owner what needs attention. It cannot tell them that a box went quiet, that a person has not signed in, that a new machine appeared, or what happened recently. A long vulnerability list also fills the screen and pushes those panels out of view. This feature feeds Events and Activity for real, and pages the attention table so both panels stay reachable.

Events are the current situation. Activity is a log of things that happened. They are not the same list.

## Definitions

| Term | Meaning |
|------|---------|
| **Device / box** | The Dmitri box that scans a network. Never a machine on that network. |
| **Machine** | A host on the customer’s network. |
| **Attention** | Critical and high vulnerabilities from the latest scan, plus the existing failed-scan and stale-coverage notices in the title block. |
| **Event** | A derived, current-state fact: a box offline beyond three days, a member who has not signed in for sixty days, a machine first seen recently. Not stored. |
| **Activity** | A stored, newest-first log of named happenings in the organisation. |
| **Actor** | The person who caused an activity row, when a person caused it. A box ingest has no human actor. |

## Business rules

**Attention paging**

1. The attention table shows one short page of critical-then-high vulnerabilities from the latest scan, newest first inside each severity, then the next severity. Order holds across pages.
2. Page size is a constant. The owner cannot choose a larger page. A typical laptop still shows Events and Activity under the table.
3. Pagination uses the same control as other lists: icon-only previous and next, accessible names “Previous page” and “Next page”, no Previous/Next words. It is hidden when everything fits on one page.
4. Changing the attention page does not reset Events or Activity pages, and does not hide those panels.
5. The title count stays honest: it uses the full attention total plus the notice extras, not the number of rows on the current page.
6. Medium and low vulnerabilities stay off Home.

**Events (derived)**

7. Events are computed from current records. They are not written to a log.
8. A box is an offline event when it is not live and its last-seen time is older than **3 days**. Last-seen prefers a live connection when one exists. This is not the stale-coverage notice (age of the last completed scan).
9. A member is an idle event when they have not **signed in** for more than **60 days**. Session refresh without a sign-in does not count as signed in.
10. A machine is a new-machine event when it was first seen inside the recent window (**7 days**), **except** on the organisation's first completed scan. That scan establishes the baseline of what is on the network; it reports no new machines. Copy uses *machine*, not *device*.
11. Both admin and viewer see the same events, including idle members named by email or display name. Home is not the member directory.
12. Empty Events still render the panel empty state. The page does not break.

**Activity (stored)**

13. The log records, each with a time: scan started, scan finished, scan failed, machine first seen, role changed, member invited, unused invite withdrawn, member removed, account deleted.
13a. The baseline exception in rule 10 applies to the log as well: the first completed scan writes no machine-first-seen rows. Its scan rows are still written.
14. When a person caused the row, the log keeps who they were at that moment (email or name). After that person is deleted, the row remains.
14a. A row's time is when Dmitri recorded the fact, not a time reported by a box. A scan that runs overnight and reaches Dmitri at 06:12 is logged at 06:12. A box clock can be wrong; the log must still read in order.
15. A box-driven scan row has no human actor.
16. Writes happen in the same change that caused the fact. A hard delete inserts the row first, then deletes the person or invite.
17. Admin and viewer see the **same rows** (same kinds, same times, same total). Viewer wording must not name an action a viewer cannot take (invite, change role, remove someone). Scan and machine rows use the same wording for both roles. Account deleted is allowed for both (a viewer may leave).
18. Newest first. Paginated with the same Foundations control; hidden when the log fits on one page. Independent of attention and Events paging.
19. Empty Activity still renders the panel empty state.

**Home composition**

20. When nothing needs attention, the table is not drawn. Events and Activity move up under the title.
21. First-run (no scan yet) still shows Events and Activity if they have rows; it does not invent attention rows.
22. A viewer sees the Home feed. They do not get a second, redacted set of hidden kinds.
23. The privacy disclosure in Settings must describe what this feature records and who can see it. Today it promises that only admins see sign-in times and that Dmitri records no actions. Both stop being true, so the copy changes with the feature.

## User stories

1. As an owner, I see that a box stopped reporting, so that I notice before a scan is silently missed.
2. As an owner, I see a new machine appear on my network, so that I can ask whether it belongs.
3. As an owner, I see what happened recently without asking anyone.
4. As an owner, I page through attention items on Home, so that a long list does not push Events and Activity off the screen.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Scan start and finish | A scan starts and finishes | The activity log is read | Both rows appear, newest first |
| Box clock is wrong | A box reports a finished scan with a time earlier than when the scan was started | The activity log is read | The finished row still reads above the started row |
| Role change names people | An admin changes a member’s role | The activity log is read | The row names the actor and the target for an admin; a viewer sees the same row with wording that does not name invite/role/remove actions |
| Box offline | A box last seen more than 3 days ago and not live | Home renders | The offline event shows with the correct day count |
| Member idle | A member has not signed in for more than 60 days | Home renders | The idle event shows |
| New machine | A machine first seen yesterday, on a later scan | Home renders | The new-machine event shows |
| Baseline scan is quiet | The organisation's first completed scan finds 40 machines | Home renders | No new-machine events appear, and Activity holds the scan rows but no machine rows for that scan |
| No events | No derived events and no activity | Home renders | Both panels show their empty state; the page does not break |
| Attention overflow | More attention items than one page | Home renders | Only one page of rows; pagination appears |
| Last attention page | The owner opens the last attention page | Home renders | Events and Activity remain on screen without a wall of rows above them |
| Short attention list | One page or fewer of attention items | Home renders | Pagination is not shown |
| Independent paging | Events is on page 2 | The owner changes attention page | Events stays on page 2 |
| Viewer parity | An invite and a role change exist | A viewer opens Home | Those activity rows are present; copy does not name actions they cannot take |
| Privacy copy is honest | The Settings privacy disclosure is open | A member reads it | It says every member can see sign-in recency and the organisation change log, and that Dmitri does not record what a member viewed |
| Delete survives | An admin removes a member | The member row is gone | Activity still has the removal row |
| Invite withdrawn | An unused invite is revoked | The invite is gone | Activity still records that the invitation is no longer outstanding |

## Out of scope (v1)

- Email or push notification of any event.
- A compliance audit trail, retention, or archival policy.
- Configurable thresholds or page sizes.
- Infinite scroll or a virtualized table.
- Moving paginated attention to a different screen.
- URL-synced page numbers.
- Medium or low vulnerabilities on Home.
- Backfilling activity from history that was already deleted.
- Hardware-agent or TUI changes.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- Layout this completes: `specs/042-design-system/DESIGN.md` §3, §16
