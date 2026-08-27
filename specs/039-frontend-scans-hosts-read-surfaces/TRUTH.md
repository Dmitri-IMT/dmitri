# TRUTH — Scans and Hosts read surfaces

Domain language and verifiable behaviour only. No file paths, no endpoints, no code.

Issue: **DMI-88**. Screen specs: `docs/ui/SCREENS.md` §§ SCAN LIST, SCAN DETAIL, HOST INVENTORY,
HOST DETAIL, AGENTS, and § Foundations — the source of truth for all copy and layout. Roadmap:
`docs/roadmap/FRONTEND.md` milestone 5 (read half).

## Narrative

Every read endpoint the pilot needs already exists, and nothing renders them. Home deliberately
shows one verdict and the items that need attention; it is not where anyone investigates. These
are the four screens where an operator actually reads a result: the run log, one scan's findings,
the inventory of machines, and one machine's exposure.

This is the bulk of the product surface a pilot user touches between scans, and it is the first
part of the product that is honestly a set of tables. It is also where the shared table, empty
and loading treatments stop being a Foundations promise and become code — every table-led screen
after this one inherits what this feature builds.

The backend is complete and unblocked. The three read-path defects that would have made these
screens lie — hosts dropped past row 20, a failed scan with no readable reason, and a scan whose
devices could not be linked to a host — are all fixed and shipped. Nothing here is blocked.

## Definitions

| Term | Meaning |
|------|---------|
| **Scan** | One run against one network, with a status, a time, and — once it finishes — counts of what it found. |
| **Unfinished scan** | A scan that has been accepted but has not produced a result yet. It has no counts, and it is not "clean". |
| **Failed scan** | A scan the Pi took and could not complete. It carries a recorded reason. |
| **Host** | A machine discovered on the network. Hosts are **cumulative** — the inventory is everything ever found, not what the last scan saw. |
| **Finding** | A vulnerability or exposure observed on a host during a scan, with a severity and, usually, a CVE and a score. |
| **Highest severity** | The worst severity among a scan's or a host's findings. Absent when there are none. |
| **Agents surface** | The place the scanning device and its trigger will live. In this feature it exists and explains itself; it does not yet act. |

## Business rules

**Access**

1. All four read surfaces are readable by **both** roles. Nothing here is admin-only, and no
   control on these screens is hidden by role.

**The run log (scan list)**

2. Scans are listed newest first, one page at a time, and the ordering is fixed — the run log is
   read chronologically and offers no other ordering.
3. An unfinished scan shows its state **in place of** its counts. It must never render as a
   finished scan with nothing found, because that reads as "clean" about a scan that has not
   looked yet.
4. A failed scan shows a plain-language reason, never a raw error code.
5. Every row navigates as a whole to that scan.

**One scan (scan detail)**

6. The findings are the point of the page; the hosts are context. A scan's findings and hosts
   arrive together with the scan — reading one scan is one request, and opening a finding fetches
   nothing.
7. Findings are ordered worst-first.
8. A finding opens **in place**, revealing what it is, what to do, the evidence, its references
   and its score. It does not navigate. A host row opens its ports the same way.
9. A finished scan with no findings says so in words and lets the host table carry the page. It
   never shows an empty findings table.
10. A failed scan's failure **is** the page: the reason is shown and the empty findings and host
    tables are suppressed entirely.
11. An unfinished scan says it is still running and does not present an absence of findings as an
    answer.
12. A host row links to that host's page.
13. The screen may be entered with one finding named, in which case that finding is opened and
    brought into view. An unrecognised or absent name renders the page normally.

**The inventory (host list)**

14. Hosts are listed one page at a time, and every page after the first is complete and correct.
15. The default ordering is most-recently-seen first. The operator may reorder by host name,
    vendor, address, or last-seen, in either direction; ordering is decided by the server, not by
    re-sorting the page in hand.
16. Changing the ordering returns to the first page — a page number means nothing across two
    different orderings.
17. A machine may have no recorded hardware address, and a machine may have no name. Both render
    as an explicit absence, not as a hidden column or a blank cell. The machine is real; one
    identifier is not observable.
18. Every row navigates as a whole to that host.

**One host (host detail)**

19. The page shows what the machine exposes: its identity, its findings, its open ports, and the
    scans it has appeared in.
20. Findings for a host are a **separate** read, filtered to that host, and are presented exactly
    as they are on a scan — same row, same in-place panel.
21. A host with no open ports says so positively; it never shows an empty ports table.
22. A scan-history row navigates to that scan.

**Every table-led screen**

23. Three states, no exceptions: a designed regular state, a designed empty state, and a designed
    error state with a retry. A table never renders bare.
24. An empty state on these screens **explains** and offers no action, because the action that
    would fill them — running a scan — does not exist yet. It gains its call to action when the
    trigger is built, and not before. A button must not name an action its destination cannot
    perform.
25. A loading treatment stands in for a table body on first load only, never while refreshing
    something already on screen.
26. Times are relative within a week and absolute beyond it, with the exact value always
    available. Identifiers truncate rather than wrap.
27. Nothing on these screens refreshes itself on a timer. A scan that finishes while the operator
    is reading does not animate into place; that behaviour belongs with the trigger that starts
    the scan.

**The scanning device (agents)**

28. The product's navigation names its destinations, and one of them is where the scanning device
    lives. That destination exists, is reachable, and explains that scanning is configured on the
    device itself. It is complete as a statement of fact and gains the device's live state and the
    trigger later — it is not a placeholder to be discarded.

## User stories

1. As an operator, I want to browse past scans and open one, so that I can see what it found.
2. As an operator, I want a failed scan to tell me why it failed, so that I know whether to act on
   the device or simply try again.
3. As an operator reading a scan, I want to click a machine and land on its page, so that I can
   move from "this run" to "this thing" without searching for it.
4. As an operator, I want the inventory ordered the way I think about machines — by name, by
   vendor, by address — so that I can find a specific one.
5. As an operator on a host, I want its findings and its open ports on one page, so that I can see
   what it exposes and what is wrong with it together.
6. As an operator, I want a finding's CVE, score and references, so that I can verify the claim
   against a source outside this product.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Run log paginates | More scans than fit one page | The operator advances a page | The next page's rows are shown, disjoint from the first, and no scan is skipped |
| Unfinished scan in the log | A scan that has not produced a result | The run log renders | That row shows its running state instead of counts, and shows no severity |
| Failed scan reads plainly | A scan that failed with a recorded reason | The run log renders | The row reads as failed, and its scan page states the reason in plain language, never as a code |
| Row opens the scan | A run log with at least one scan | The operator activates a row | The scan's page opens |
| Findings worst first | A scan with findings of mixed severity | Its page renders | Findings are ordered worst-first |
| Finding opens in place | A scan page with a finding | The operator activates the finding row | Its description, remediation, evidence, references and score appear in place, and the page does not navigate |
| Named finding on entry | A scan page entered with one finding named | The page loads | That finding is open and in view, with no additional request |
| Unknown named finding | A scan page entered with a name matching no finding | The page loads | The page renders normally with nothing open |
| Clean scan | A finished scan with no findings | Its page renders | A sentence states every host came back clean; no empty findings table appears |
| Failed scan page | A scan that failed | Its page renders | The reason is the content; the findings and host tables are absent |
| Scan to host | A scan page listing machines | The operator activates a machine row | That host's page opens |
| Inventory paginates | More hosts than fit one page | The operator advances a page | The next page's rows are shown, disjoint from the first, and no host is skipped |
| Inventory reorders | An inventory of hosts with distinct names | The operator orders by name ascending | Rows come back in ascending name order and the view returns to the first page |
| Reordering is served | Any ordering is chosen | The rows are read | The ordering is the server's answer, not the visible page re-sorted |
| Absent identifiers | A host with no hardware address and no name | The inventory renders | Both read as an explicit absence, and the columns remain |
| Host findings are its own | A host with findings, in an installation that has others | Its page renders | Only that host's findings appear, each showing its CVE, score and reference links |
| Host with nothing open | A host with no open ports | Its page renders | A sentence says it exposes nothing; no empty ports table appears |
| History to scan | A host page listing the scans it appeared in | The operator activates a history row | That scan's page opens |
| Empty states | An installation where no scan has ever run | Each of the run log and the inventory renders | Each shows its own explanatory empty state, and neither offers an action |
| Error states | Any of the four reads fails | The screen renders | Plain copy names what could not be loaded and offers a retry that re-reads it |
| Missing scan or host | A scan or host identifier that does not exist | The page is opened | A distinct not-found line is shown with a way back to the list |
| Navigation | Any signed-in screen | The operator reads the navigation | The run log, the inventory and the device destination are all reachable from it |
| Device destination | The device destination | It is opened | It explains that scanning is configured on the device, and offers no trigger |

## Out of scope (v1)

- **No scan trigger and no live agent state.** The device destination explains itself and does
  nothing. Triggering, the status pill's lifecycle, and the caches refreshing when a scan
  completes all belong to the next issue.
- **No self-refreshing views.** Nothing polls.
- **No charts, metric cards, or dashboards** — excluded by decision, not by omission.
- **No LLM explainer panel.**
- **No free-text search** on any screen, and no filters on the run log, though the contract offers
  both. One Pi on one network does not produce a list you cannot read.
- **No ordering controls on the run log.**
- **No export, no bulk actions, no saved filters.**
- **No rework of the existing Users or Home screens** onto the shared treatments this feature
  introduces. That is a separate, tracked follow-up.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
