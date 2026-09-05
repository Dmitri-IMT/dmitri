# TRUTH — Attribute every scan to the box that ran it, and record its duration

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

Issue: **DMI-134**. Screen language and table rules: `docs/ui/FOUNDATIONS.md` (device vs machine,
tables, EmptyMark, Timestamp). Approved layout that this feature completes: `specs/042-design-system/DESIGN.md`
§4 Scans, §5 Scan detail, §9 Device detail. Roadmap context: `docs/architecture/ARCHITECTURE.md`
§6 scan list and ingest.

## Narrative

An owner with boxes at two sites cannot tell which box ran a scan. The run log has a time, a
mode, and counts. It has no box. A box's own page has scan controls and no history. Duration is
the same gap: scan-type copy says "about 5–10 minutes" and a finished run never says how long
it actually took.

The producing box is already known at ingest. It is not returned on the scan the owner reads.
Commanded runs know the box even earlier, when the command is handed to that box. Some older
runs have a command and can inherit the box from it. The rest correctly have no box.

Duration is how long the box spent scanning, reported with the result. It is not queue time and
not command-channel time. A failed or unfinished run has no duration.

This feature makes those two facts readable: the run log names the box and the duration, a box's
page lists the scans it ran, and one scan's summary strip includes duration. It does not invent
sameness across findings, change the daily schedule, or guess a box for a run that never had one.

## Definitions

| Term | Meaning |
|------|---------|
| **Box** | The Dmitri device that scans a customer's network. Owner-facing word. Never a machine on that network. |
| **Scan** | One run against one network. It may be unfinished, failed, or completed. |
| **Producing box** | The box that this scan belongs to. Absent when the run was never tied to a box. |
| **Duration** | How long the box spent scanning, in whole seconds, only for a completed run that reported it. |
| **Unattributed scan** | A scan with no producing box. The owner sees nothing in the Box cell. That is correct, not an error. |

## Business rules

**Belonging**

1. A scan belongs to at most one box.
2. A commanded scan belongs to that box as soon as the command is given to the box, including
   while the run is unfinished.
3. When results arrive, the uploading box must be the producing box already recorded. A mismatch
   is refused. The scan does not change owner.
4. A completed scan that arrived without a command belongs to the box that uploaded it.
5. A scan with no command and no recorded box stays unattributed.
6. Existing scans that have a command and no box inherit that command's box, once. Existing
   scans with neither stay unattributed. No other backfill.

**Duration**

7. Duration is the box's own scan time in whole seconds. It is not time spent queued or waiting
   to be delivered.
8. A completed scan that reported that time exposes it. A completed scan that did not report it
   has no duration.
9. A failed scan has no duration. An unfinished scan has no duration.
10. Owners do not see a raw second count. Under 60 seconds the copy is `45s`. At 60 seconds or
    more the copy is whole minutes, `8 min`. There is no hours form.

**Reading**

11. The scan list and the scan detail both carry the producing box (id and current display name)
    and duration. A missing box or duration is unknowable, not zero.
12. The scan list can be limited to one box. Only that box's scans return, including unfinished
    ones that already belong to it.
13. The Box cell shows the box's current display name, not its identifier. The name is read at
    display time. The whole row opens that scan. The Box cell is not a nested link. An
    unattributed scan shows `—`. The owner opens a box from Devices.
14. Duration `—` is used whenever rule 8 or 9 says there is no duration. The Duration column
    still exists.

**Scans list**

15. Columns, in order: When, Box, Mode, Status, Duration, Machines, Vulnerabilities, Highest
    severity. A whole row still opens that scan.

**Scan detail**

16. The summary strip adds Duration as a fifth entry beside Mode, Network, Machines seen, and
    Vulnerabilities. This screen does not show a Box field.

**Device detail**

17. The box's page lists the scans that belong to that box. Each row opens that scan. Pagination
    matches the run log.
18. Columns of that history table, in order: When, Mode, Status, Duration. The table says that a
    scan ran and how it ran. Machines, Vulnerabilities and Severity are absent: those belong to
    the scan, which the row opens. Box is absent: every row is the same box.
19. Blank copy when the box has no scans: `No scans from this box yet.`

**Roles**

20. Reading box, duration, the filtered run log, and the box's history is available to both
    admin and viewer.

## User stories

1. As an owner with boxes at two sites, I open a box and see the scans it ran, so that I know
   that site is covered.
2. As an owner, I see how long a completed scan took, so that the scan-type descriptions mean
   something.
3. As an owner, I see which box produced a row on the run log, so that I can tell two sites
   apart.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Ingest stamps the box | A signed result from a box | The scan is stored | The producing box is that box |
| Commanded run without a prior command row | A scheduled-style or unrequested upload from a box, with no command | The scan is read back | The producing box is still that box |
| Completed duration | A completed scan that reported its run time | The scan is read | Duration equals that reported time in whole seconds |
| Failed duration | A failed scan | The scan is read | Duration is absent and the cell is `—` |
| Filter by box | The run log is limited to one box | Scans are listed | Only that box's scans return |
| Unattributed history | A pre-existing scan with no command | It is read | The producing box is absent and nothing errors |
| Stub already belongs | A commanded scan has been given to a box and not yet finished | The run log is limited to that box | The unfinished scan is in the list |
| Ingest mismatch | A commanded scan belongs to box A | Box B uploads results for it | The upload is refused; the owner does not change |
| Backfill from command | An old completed scan has a command and no box | After the one-time repair | The producing box is the command's box |
| No invented box | An old scan has no command | After the one-time repair | The producing box stays absent |
| Scans list Box | A completed attributed scan | The owner opens the run log | The Box cell is the display name; the row opens that scan |
| Scans list Duration | A completed scan with reported time 45 seconds | The owner opens the run log | The Duration cell is `45s` |
| Scans list Duration minutes | A completed scan with reported time 500 seconds | The owner opens the run log | The Duration cell is `8 min` |
| Scan detail Duration | A completed scan with a duration | The owner opens that scan | The summary strip includes Duration |
| Device history empty | A box that has never produced a scan | The owner opens the box | The copy is `No scans from this box yet.` |
| Device history columns | A box with at least one scan | The owner opens the box | The history table has exactly the columns When, Mode, Status, Duration, in that order |
| Device history row opens the scan | A box with at least one scan | The owner activates a history row | That scan's page opens |

## Out of scope (v1)

- A new-versus-known result column ("2 new vulnerabilities" / "Nothing new"). Sameness of
  findings across scans is undecided and stays on DMI-70.
- Any change to the daily scan schedule or a stored default scan type. That is DMI-133.
- Inventing a box for a scan that has no command.
- A duration for a failed or unfinished scan.
- Hardware-agent TUI screens, local past-scans, or a TUI upload path.
- Showing a Box field on scan detail.
- Renaming the owner-facing word Box, or renaming the identifier the product already uses for a
  box in its records (`agent_id`).
- Changing status copy (`Complete` vs `Completed`).

## Open questions

None. The one open question — the device-detail scan history column set — was decided at the
2026-09-05 visual review against the rendered preview: When, Mode, Status, Duration (rule 18).

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- Layout this completes: `specs/042-design-system/DESIGN.md` §4, §5, §9
