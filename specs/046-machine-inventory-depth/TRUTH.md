# TRUTH — Deepened machine inventory

> Linear: DMI-135. Supersedes `specs/042-design-system/DESIGN.md` §16 for the four items
> that spec deliberately fenced out for want of data, and closes its §17 Q2.

## Narrative

An owner opens Network to answer three questions: *what is this thing, how bad is it, and is
this new?* Today the screen cannot answer any of them.

It names a machine's vendor — `Hikvision` — when what the owner recognises is `Camera`. It
counts open ports, which is a fact about the scan rather than a fact the owner can act on. It
knows when a problem was detected in *this* scan, but not when it first appeared, so nothing on
the screen distinguishes a problem found tonight from one that has been open since July. Home's
attention table names machines by address, because a problem carries no machine name at all.

The list also miscounts. Machines quiet for a while collapse behind one row that says how many
are quiet — but that number is computed over the twenty machines on the page you are looking at.
On a network of forty-five machines the same group appears on more than one page, each time with
a different number, and none of them is the truth.

This feature deepens what the inventory knows, so the screens can answer the owner's questions
without a second request and without lying about the count.

## Business rules

- Every machine has a **type**, classified automatically from its vendor and the services it is
  running. A machine that cannot be classified has the type **unknown**, and the screen draws no
  guess for it.
- The type vocabulary is exactly: router, computer, camera, storage, TV, phone, printer, sensor,
  unknown. There is no tenth type.
- A machine's **vulnerability count** is the number of problems still present in that machine's
  most recent scan. Nobody marks a problem resolved by hand; a problem is open until a scan stops
  finding it.
- A problem has a life across scans, not only within one. It carries the moment it **first
  appeared**, the moment it was **last seen**, and — once a scan no longer finds it — the moment
  it was **fixed**. Finding the same problem again never changes when it first appeared.
- A service on a machine carries the moment it was **last seen**, so a service that has closed
  can be told apart from one still open.
- A machine is **quiet** when it was last seen more than **7 days** ago. Quiet is a property of
  the whole inventory, not of a page.
- A problem names its machine by that machine's **current** name. When the machine cannot be
  identified, the problem names the machine's address instead.
- Vendor and the count of open ports remain true and remain available; they belong on the
  machine's own page, not in the list.

## User stories

1. As an owner, I want to see that a machine is a camera and not a server, so that I know what I
   am looking at.
2. As an owner, I want to see how many vulnerabilities a machine has before I open it, so that I
   can choose what to deal with first.
3. As an owner, I want to see when a problem first appeared, so that I know whether it is new.
4. As an owner, I want Home to name the machine, so that I do not have to recognise an address.
5. As an owner, I want the count of machines I have not seen recently to be true for my whole
   network, so that I can trust it.
6. As an owner, I want to sort my machines by how many vulnerabilities they have, so that the
   worst machine on my network is the first row I read.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|---|---|---|---|
| Type from vendor and services | A machine whose vendor and open services indicate a camera | The inventory is listed | Its type is `camera` |
| Type unknown | A machine nothing can classify | The inventory is listed | Its type is `unknown`, and the screen shows no guessed type |
| Type vocabulary is closed | Any machine at all | The inventory is listed | Its type is one of the nine named types and nothing else |
| Vulnerability count | A machine with three problems present in its latest scan | The inventory is listed | Its vulnerability count is 3 |
| Count follows the latest scan | A machine whose latest scan finds one of its three earlier problems | The inventory is listed | Its vulnerability count is 1 |
| First seen survives re-detection | A problem detected in an earlier scan and detected again in a later one | The problem is read | Its first-seen moment is unchanged |
| First seen is set once | A problem never seen before | Its scan completes | Its first-seen moment equals that scan's moment |
| A fixed problem is stamped | A machine's problem that its latest scan no longer finds | That scan completes | The problem carries the moment it was fixed and is no longer counted as open |
| Service last seen | A machine whose service appeared in an earlier scan and not in the latest | The machine is read | That service carries the earlier scan's moment as its last seen |
| Quiet is whole-inventory | An inventory of 45 machines, 6 of them quiet, listed 20 to a page | The first page is read | The quiet group reports 6 |
| Quiet threshold | A machine last seen 8 days ago, and one last seen 6 days ago | The inventory is listed | The first is quiet, the second is not |
| Quiet machines leave the list | An inventory containing quiet machines | A page of the inventory is read | The listed machines are all active, and the quiet ones are absent from that page |
| The quiet group pages | An inventory with more quiet machines than fit one page | The quiet group is opened and paged | Each page returns its own quiet machines, and the active list is unaffected |
| Sorting by vulnerability count | An inventory of 45 machines across three pages | The inventory is sorted by vulnerability count, descending | The first row is the machine with the most open problems on the whole network, not on one page |
| Home names the machine | A problem whose machine has a name | Home renders it | The machine's current name shows |
| Home falls back to the address | A problem whose machine cannot be identified | Home renders it | The machine's address shows in its place |
| Renaming a machine | A machine with an older problem, renamed since that problem appeared | Home renders that problem | The machine's current name shows, not the earlier one |
| Nothing is stamped retroactively | An inventory that existed before this feature | The migration runs | No machine is given a type and no problem is given a first-seen moment until the next scan supplies one |

## Out of scope (v1)

- A machine-type vocabulary beyond the nine named above.
- Letting a person edit a machine's type or its name. Classification is automatic.
- Vendor enrichment from an external service. The vendor name already arrives with the scan.
- Any change to the severity taxonomy.
- A person-facing action to mark a problem resolved. A scan decides.
- Making the quiet threshold an owner setting. It is fixed at 7 days.
- **The security screen** — the current security level of a network, its worst offenders, and how
  its security changes over time. This feature lands the dates that screen will need and draws
  none of it. It is a separate issue with its own spec.
- Search, filters and column pickers on Network, which remain out of scope from 042.

## Overrides of `specs/042-design-system`

Recorded here so the next reader does not restore the older rule from a spec that shipped:

| 042 said | This spec says | Why |
|---|---|---|
| §16: machine type, vulnerability counts, service last-seen and vulnerability first-seen are out of scope — "No data." | All four are in scope. | The data now exists. |
| §6.1: no machine-type column, no per-machine vulnerability count. | Both are drawn — replacing `Vendor` and `Services` respectively. | The table's meaning per column improves without the table growing. |
| §6.1: the numeric column right-aligns. | Every column is left-aligned; numbers keep tabular figures. | Owner's decision, 2026-09-07. |
| §6.3: quiet is more than 14 days. | Quiet is more than 7 days. | Owner's decision, 2026-09-07. |
| §17 Q2, still open: accept the page-local quiet grouping? | No. The split is server-side. | The page-local count is wrong on any network above one page. |

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- Approved mockup: https://claude.ai/code/artifact/cbf8db53-4813-4040-b44f-f94489e92ad2
