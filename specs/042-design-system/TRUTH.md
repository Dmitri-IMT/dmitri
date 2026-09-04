# TRUTH — Design system v2 and the restyle onto it

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

## Narrative

The web app's visual language was decided screen by screen. DMI-131 researched a replacement and
`docs/ui/FOUNDATIONS.md` records the decision: one type family, one accent, severity carried as a
bold word rather than a colour, a fixed table rhythm, a top bar with no sidebar, and a settled
vocabulary. Nothing in the running product uses it yet.

This feature makes Foundations true. It replaces the tokens, regenerates the shared controls,
adopts the vocabulary, and restyles every existing screen onto the result. It removes the retired
decisions rather than layering over them — the old fonts, the zero radius, the severity palette
and the decorative ornament all leave in the same pass.

Two changes go beyond restyling because the owner directed them. The scan type and the network a
box watches are decided **per box**, so they move onto the box itself: Devices becomes a list of
boxes, and each box gets a detail page that owns its network, its scan type, and the button that
runs a scan now. `FOUNDATIONS.md` §Scan settings, which places that block on the Scans page, is
corrected as part of this work.

The reader is a non-technical business owner. The product interprets; it does not present raw data
for triage.

## Business rules

- **Foundations is the source of truth for the look.** Where a screen and `FOUNDATIONS.md`
  disagree, the document wins. Where `FOUNDATIONS.md` and `ADR-008` or `SCREENS.md` disagree,
  `FOUNDATIONS.md` wins.
- **Severity has no hue.** Critical, High, Medium and Low are a bold word in primary ink, in a
  table cell and a section heading alike. No chip, pill, tag, dot, badge, coloured text, coloured
  bar or coloured card edge, anywhere. The API taxonomy is unchanged.
- **One accent, never severity.** The accent marks the primary action, the active nav item and the
  focus ring, and nothing else.
- **The vocabulary is settled.** *Vulnerability* replaces *finding* for the reader. *Network*
  replaces *Hosts* and *Devices* replaces *Agents*, in the nav, in page titles, in copy and in the
  URL. A ***device*** **is the Dmitri box** — the unit installed on site that runs the scans, listed
  under the `Devices` nav item. A thing found *on* the customer's network is a ***machine***; those
  live under `Network` and are never called devices. Decided by the owner 2026-09-02; it settles a
  contradiction between `FOUNDATIONS.md` §Vocabulary and the v4 exemplar in Foundations' favour.
- **Nothing renders without data behind it.** A column, panel or section whose data the product
  cannot supply today is not drawn — not drawn empty, and not drawn with placeholder marks.
- **Absent, not disabled.** An affordance a role cannot use is not rendered. The single carve-out
  is an action the person may take but has not yet supplied the input for.
- **Only shared controls are interactive.** A screen composes controls; it never hand-rolls a
  native one. Every interactive control declares rest, hover, focus-visible, active and disabled.
- **No scan type is stored.** The product has no per-box default scan type. The screen opens on
  Standard, the selection is a preview that never survives leaving the screen, and no copy claims
  a default exists. Storing one is DMI-133.
- **The scan type and the watched network belong to one box.** Both are chosen on that box, never
  globally, because a customer may run several boxes on several networks.
- **Never certify safety.** The product describes what needs attention. It never claims the
  network is safe.
- **A machine is named by what the record carries.** The attention table on Home identifies a
  machine by its address, because a vulnerability record carries no hostname. A friendlier name is
  a later improvement, not a placeholder to draw now.
- **Real content only.** Real hostnames, real CVE identifiers, real addresses. No placeholder data
  in shipped screens.
- **One theme.** Light only, desktop only. No theme toggle and no mobile layout.

## User stories

1. As a business owner, I want every screen to look like one product, so that I trust what it
   tells me.
2. As a business owner, I want severity stated in words, so that I understand the ranking without
   learning a colour code.
3. As a business owner with boxes at more than one site, I want to see all my boxes in one list,
   so that I know each one is reporting.
4. As an admin, I want to choose which network a given box watches, on that box, so that I do not
   have to guess which box a setting applies to.
5. As an admin, I want to choose the scan type for a given box and run a scan immediately with it,
   so that I can check a site without waiting for the daily scan.
6. As an admin, I want a box that has stopped answering to stay in my list and say how long it has
   been quiet, so that nothing disappears without telling me.
7. As a viewer, I want to read everything and be shown no controls I cannot use, so that the
   screen never misleads me about what I can do.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Severity reads as a word | A vulnerability of any severity in any table or heading | The screen renders | The severity is a bold word in primary ink, and no chip, pill, badge, dot or severity-coloured element appears anywhere on the screen |
| Nav names the domains | Any signed-in screen | The top bar renders | The nav reads Home · Scans · Network · Devices · Users · Settings, the active item is bold with no underline, and there is no sidebar |
| Viewers do not see Users | A signed-in viewer | Any screen renders | The Users nav item is absent, not disabled |
| The vocabulary is adopted | Any screen that lists vulnerabilities | The screen renders | The reader-facing word is "Vulnerability"; the word "finding" appears nowhere the reader can see |
| Routes follow the names | A signed-in user | They open the Network list or the Devices list | The address is `/network` or `/devices`; `/hosts` and `/agents` are no longer routes |
| The browser names the product | Any screen | The page loads | The browser tab reads "Dmitri" |
| Rows are one height | A table with rows of differing content length | The table renders | Every row is the same fixed height, and long values truncate rather than wrap |
| A whole row navigates | A table row representing a record with a detail screen | The row is clicked or activated by keyboard | The detail screen opens; there is no trailing "View" column |
| A quiet machine stays and says so | A machine last seen more than two weeks ago | The network list renders | Its row is muted, carries a second line reading how many weeks it has been quiet, and sits inside a collapsed "Not seen recently (N)" group at the bottom of the table that expands on activation |
| Home states the count | At least one vulnerability needing attention | Home renders | The page title states how many things need attention, and the attention table lists them with vulnerability, machine and severity |
| Home stays quiet when clear | No vulnerability needs attention | Home renders | The title reads "Nothing needs your attention", no attention table is drawn, and no empty card stands in its place |
| Boxes are listed | An organisation with more than one box | The Devices list renders | Every box appears as a row with its name, the network it watches, its status and when it last reported |
| A box with no network says so | A box whose network has never been chosen | The Devices list renders | Its network cell reads that no network has been chosen yet, in muted ink, with no error styling |
| A box owns its settings | A box detail screen | It renders | The screen shows that box's watched network with a control to change it, a scan-type control listing the five real scan types with a one-line description of the selected one, and a control to scan now |
| Scan now uses the selected type | An admin on a box detail screen | They select a scan type and scan now | The scan runs with the selected type, and nothing about the box is changed |
| Scan type never persists by accident | An admin who selected a scan type without running anything | They leave the screen and return | The selection has reverted to the starting selection, Standard |
| No default is claimed | Any box detail screen | It renders | No text names a stored or daily default scan type, because the product does not store one yet |
| Viewers cannot configure a box | A viewer on a box detail screen | It renders | The watched network and scan type are readable, and the change, select and scan controls are absent |
| Scanning is unavailable without a network | A box whose network has never been chosen | An admin opens its detail screen | The network chooser is open and the scan-now control is absent until a network is saved |
| A running scan reports where it started | An admin who started a scan from a box detail screen | The command is accepted | The status of that command replaces the scan-now control on the same screen and takes keyboard focus |
| Every control shows it is a control | Any interactive control on any screen | The pointer rests on it, or it takes keyboard focus | The cursor is a pointer and a visible change occurs; on focus a visible ring is drawn |
| Motion respects the reader | A reader whose system requests reduced motion | Any animated element renders | The animation is suppressed |
| No screen scrolls sideways | Any screen at 1280px and at 1440px | It renders | The page body does not scroll horizontally; wide tables scroll inside their own container |
| Nothing renders without data | Any screen | It renders | No column, panel or section is drawn for data the product cannot supply, and no placeholder mark stands in for missing data |

## Out of scope (v1)

- **What a screen provides** beyond the restyle. Home's, Settings' and the information
  architecture's feature sets stay on their own issues (DMI-110, DMI-117, DMI-123, DMI-127).
- **Scan duration** and a new-versus-known result for a scan. There is no such data today, so the
  Scans table ships without those columns.
- **Attributing a scan to the box that produced it.** Follows in its own issue; until it lands, a
  box detail screen shows no scan history and the scans table has no box column.
- **Machine type classification** (router, camera, printer), a per-machine count of open
  vulnerabilities, when a service was last seen, and when a vulnerability was first seen. The
  network list and network detail ship without those columns.
- **The Home events panel and the Home activity log.** No data feeds them today.
- **The daily scan default** — the "Use this scan type" control, its confirmation, and the line
  naming the current default. That is DMI-133.
- **Multi-box scan scheduling**, per-box notification, and any per-box setting beyond the watched
  network and the scan type.
- **Dark theme, tablet and mobile layouts, and per-page browser titles.**
- **Backend and hardware-agent changes.** This feature does not alter any API contract.

## Docs drift (orchestrator docs-sync, 2026-09-04)

- **`docs/ui/SCREENS.md` may still describe pre-042 routes and components** — Task 12 updated
  `FOUNDATIONS.md` / `FOUNDATIONS-DECISIONS.md` as the visual authority; a full `SCREENS.md` sweep
  was out of scope for this sync.
- **`docs/roadmap/FRONTEND.md` and other human KB pages** may still say "Hosts" / "Agents" as screen
  names — API paths remain `/hosts` and `/agents`; only the SPA route labels changed.


## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- Visual source of truth: `docs/ui/FOUNDATIONS.md`; visual exemplar:
  `docs/ui/mockups/dmi-131-mockups-v4.html`; placement decision:
  `https://claude.ai/code/artifact/4757cf70-c4bf-4363-a737-60b764005f13`
