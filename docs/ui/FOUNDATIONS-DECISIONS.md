# UI Foundations — decisions appendix

> **History. Superseded values appear here on purpose.** Nothing on this page is binding.
> The binding sheet is [`FOUNDATIONS.md`](FOUNDATIONS.md); the full argument is
> [`DESIGN-SYSTEM-RESEARCH.md`](DESIGN-SYSTEM-RESEARCH.md).

## Retired 2026-09-02 (DMI-131)

These were the Foundations decisions in `SCREENS.md` before the revamp. Each is now dead; the
reasoning is kept so nobody re-argues it from scratch.

- **IM Fell English for all titles, never below 16px** *(2026-07-13)* — the brand face, chosen to
  carry an engraving direction natively. Retired: one friendly sans differentiated by weight and
  size beats a second family, and the 16px floor was distorting the scale.
- **IBM Plex Mono for all non-title text** *(2026-07-13)* — vintage-computer lineage, legible at
  13px. Retired: mono prose plus square corners is the dev-tool look the product is leaving; mono
  is now quarantined to technical data. IBM Plex Sans was the named escape hatch and was never
  taken.
- **`--text-nav` at 11px** *(2026-07-13)* — a small letterspaced nav label. Retired: the fix for a
  quiet nav is more contrast, not smaller type. Nav is body size, marked by weight.
- **Warm paper palette** — `--paper #FAF8F4`, `--card #FFFFFF` 1.06 apart, `--ink #1A1917`,
  `--ink-muted #6B6862`, `--rule #E5E0D8`, `--edge #8C8880` *(2026-07-13)*. Separation was carried
  by warmth. Retired for a near-white canvas with pure-white cards separated by a hairline.
- **`--radius: 0`, blocky over roundy** *(2026-07-13)* — hard edges on cards, buttons, badges and
  inputs. Retired with the shadcn preset move from `radix-nova` to `radix-maia`: the brief is a
  consumer product, not a dense dashboard.
- **Deep purple `#7C3AED` as the sole accent** *(2026-07-13, locked during the build)* — 5.37:1 on
  paper. Retired for `#4F46E5` indigo-600 (6.29:1 on white). The *rule* survived the change: one
  accent, used sparingly, never carrying severity.
- **Severity hexes** — critical `#B91C1C` red, high `#C2410C` orange, medium `#A16207` amber, low
  `#1D4ED8` blue, informational `#6B6862` *(2026-07-13, "the only unfilled values in Foundations")*.
  All AA on `--paper`, and all retired: there is now no severity hue anywhere, on text or on a
  surface. Blue's carve-out from the no-blue rule went with them. The pill tints and borders live
  in [`specs/research/dmi-131-references.md`](../../specs/research/dmi-131-references.md).
- **Severity badges, pills and coloured card edges** — retired outright. Severity is a bold `--ink`
  word.
- **The `Ornament` component** *(2026-07-13)* — a filled lozenge on a broken hairline, inline SVG,
  on Home and the auth screens. Cut: an empty state shows its destination, or shows nothing.
- **Dashed rules** as a separator idiom *(2026-07-13)* — retired for a solid hairline, or no line
  where spacing already separates.
- **The nav-centring saga** — centred *2026-07-31*, reverted to left-adjacent *2026-08-07*, centred
  again and made permanent *2026-08-21 (DMI-107)*. The 2026-08-07 reversal treated centring as a
  workaround for a lone link and undid it as soon as a second item arrived. The settled reason is
  that the nav is the product's spine, not that it currently holds N items — so the count is no
  longer an argument either way. **This survives the revamp**: the nav is still centred on the
  `1fr auto 1fr` grid, and the consequence is still that there is no specified wordmark→nav gap.
- **`▲▼` glyph sort markers** and **`h-8` as the universal control height** *(build-era)* — retired
  for Lucide icons sized off the type scale, and for generous default controls with density zoned
  into tables.
- **The 720px prose column** *(specified, then removed 2026-08-21)* — once the bar and content
  shared one frame there was nothing left for it to measure. Still true.

## DMI-131 review rounds (all 2026-09-02)

Six owner reviews in one day, plus a closing pass. Each row is what the round decided or rejected.

**Round 1 — rendered comparison page.**
Chose `radix-maia` over `nova`, **Inter Variable** as the face (Figtree and Nunito not pursued;
OpenAI Sans unlicensable), and **`#4F46E5` indigo-600** as the accent over `#1D4ED8` (collides with
the old severity blue) and `#533AFD`. Rejected the **urgency-group wording** (*Fix now / Fix soon /
Good to know / All clear*) — Critical/High/Medium/Low are "more impactful" and match the API.
Rejected the **header-only primary action** ("this is bad"): placement is decided per screen.
Adopted the shadcn MCP server and rejected `design.md` as a second token format.

**Round 2 — the screen map.**
Settled the nav renames **Hosts → Network**, **Agents → Devices** (Users left open, keeps its
name). Home's job is **the work board**, not a scan launcher. Cut the **Scans mode switcher**
("serves no purpose") — mode is a column. Confirmed the **engraving ornament** and the three
"Dmitri scans your network…" paragraphs are cut. Parked Settings for DMI-110.

**Round 3 — full-screen mockups v1.**
**No coloured severity text in tables**: *"I don't like colored text on the table, bold is fine."*
Settled the chrome — bold active nav with a bold hover, the bare **"Dmitri"** wordmark, the user's
**name and no avatar**, summary strips aligned to their table. Grew `text-title-sm` 20px → 22px.
Allowed **a small outlined button in a card footer**, and put a list screen's own action **below
the table, bottom-right**. Grew the copy list: *Finding* → **Vulnerability**, *Open ports* → a
plain services phrase, *"Seen in these scans"* rejected, explanatory copy under a control deleted.

**Round 4 — mockups v2.**
**Rejected severity-varying cards outright** — all four patterns (full coloured outline, ink
eyebrow, tinted header band, coloured icon) and the colour ramp behind them. Settled **pagination**
on the shadcn `Pagination` shape, the **ghost borderless select** in a table cell, the Home gap to
the Events/Activity row at **step 12**, and **no trailing empty row** on a panel.

**Round 5 — mockups v3.**
**Restored an arrow on the back link** (Lucide `arrow-left` + "Back") — the owner had disliked the
previous rendering, not arrows. Made pagination **icon-only**. Settled the Home attention board's
empty state as **nothing rendered at all**. Added a **Remove action on every Users row**. Moved
scan modes onto the **Scans page** (presentation still open at this point). Added the
**column-gap rule** — `Port` next to `CVE` no closer than step 6.

**Round 6 — mockups v4, approved in full.**
**Scan settings** settled as **tabs + a one-line description** with a secondary "Use this scan
type" button; radio cards and the selectable list rejected. The five scan-type descriptions and
the confirm-dialog copy approved verbatim. The **manual scan trigger moved to the Scans page as
"Scan now"**, overturning the earlier "`Start scan` lives only on the Devices screen". The
**Network list page** approved as drawn. The **silent-device treatment** (muted row + collapsed
"Not seen recently (N)" group) approved.

**Closing pass.**
Confirmed the **56px fixed row height** ("set default to 2" meant one fixed height for every row).
Deferred the **per-device start scan** to future work — candidate follow-up epic *"Personalize
scans"*.

## Still open

| Open item | Where |
| --- | --- |
| Final wording for the services heading, and a replacement for *"Seen in these scans"* | [`FOUNDATIONS.md`](FOUNDATIONS.md) §Copy rules & vocabulary · research note §4.11 |
| Device naming fallback when no name is found | the Network screen issue |
| Whether the `Users` nav item keeps its name | not commented in review; keep "Users" |
