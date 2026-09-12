# DESIGN — PR #144 web UI: retroactive review and target states (DMI-158)

> **Retroactive.** PR #144 shipped web UI with no DESIGN.md. This document records the UI **as
> built** on `feature/ia-implementation` (`git diff main...HEAD -- frontend`), reviews it against
> [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md) and
> [`docs/ui/SCREENS.md`](../../docs/ui/SCREENS.md), and states the **target** that Phase 4
> remediation builds to. It does not re-decide FOUNDATIONS. Where this document and FOUNDATIONS
> disagree, FOUNDATIONS wins and this document is the bug.
>
> **Gate.** Per TRUTH business rule 1, no item here is implemented until its part has a D1–D7
> decision. Every deviation is marked **to confirm in Phase 1 code review**.

**Rendered preview (target states):** https://claude.ai/code/artifact/0beb0454-171d-4d43-8e09-7e8e0f63123d
— built from FOUNDATIONS values with Inter and Geist Mono. The ASCII below is structural only.

**Visual check (TRUTH business rule 13):** _pending — record the human decision and date here._

---

## 1. Screen flow

No new routes. Three existing screens gain surfaces.

```
/scans ──row──► /scans/:scanId  (SCAN DETAIL)
                 ├─ status failed      → ScanFailedNotice only (no AI, no industrial)
                 ├─ status unfinished  → ScanUnfinishedNotice only
                 └─ status completed   → [NEW] AI overview card        (ScanAIAnalysis)
                                          severity cards  ──row──► in-place FindingPanel [CHANGED: risk]
                                          [NEW] Industrial services card (only if any host has one)
                                          Machines seen

/network ──row──► /hosts/:hostId (NETWORK DETAIL)
                 Vulnerabilities ──row──► in-place FindingPanel [CHANGED: risk]
                 Services running on this machine
                 [NEW] Industrial services card (always rendered, as built)
                 Scan history ──row──► /scans/:scanId
```

| Surface | Reached by | Data |
|---|---|---|
| AI overview | Opening a completed scan | `GET /api/v1/scans/{scan_id}/analysis` → `ScanAIAnalysisResponse` (`status`: `pending` · `processing` · `completed` · `failed` · `unavailable`; `analysis: ScanAIAnalysis \| null`). Separate query, polls every 3s while `pending`/`processing`. |
| Industrial services (scan) | Opening a completed scan with ≥1 host where `industrial_services.length > 0` | `ScanDetailResponse.hosts[].industrial_services: ModbusTcpServicePayload[]` — no extra request |
| Industrial services (machine) | Opening a machine | `HostDetailResponse.industrial_services` — no extra request |
| Risk in vulnerability panel | Expanding a vulnerability row on either screen | `FindingRecord.risk_score`, `exploitability`, `confidence`, `risk_rationale` |

Backend semantics that drive the UI (`backend/src/api/services/ai/read.py`): `unavailable` when AI
is off **or** the scan failed; `pending` when AI is on and no job record exists yet.

---

## 2. As-built mockups (1440px target, 1120px frame)

### 2.1 SCAN DETAIL, completed scan — as built

```text
┌──────────────────────────── max-w-frame ─────────────────────────────┐
│ ← Back                                                                │
│ Scan · yesterday 21:40                                     title-lg   │
│ NSPi · 192.168.0.0/24 · 12 machines · 3 vulnerabilities    strip      │
│                                                         (gap 12)      │
│ ┌ Card ── scan-ai-* ──────────────────────────────────────────────┐   │ ◄ NEW, above epicenter
│ │ AI overview                                                     │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                         (gap 12)      │
│ ┌ Card ── High ───────────────────────────────── findings-high ───┐   │
│ │ Vulnerability · Machine · Port · CVE · Severity                 │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                         (gap 12)      │
│ ┌ Card ── Industrial services ─────────── scan-industrial-services┐   │ ◄ NEW, conditional
│ └─────────────────────────────────────────────────────────────────┘   │
│ ┌ Card ── Machines seen ──────────────────────────────────────────┐   │
└───────────────────────────────────────────────────────────────────────┘
```

The page column is `ReadDetailGate`'s `gap-12`. The AI card is the first child after the strip.
Its query starts after the scan query resolves and renders `null` while loading, so when it
arrives it pushes the vulnerability cards down.

### 2.2 AI overview — states as built

**Disabled / not configured / failed scan** (`status: unavailable`)

```text
(nothing rendered — no card, no testid; polling stops)
```

Correct for TRUTH "AI disabled": no error, results unaffected. The one GET still fires; the
provider is not called (backend).

**First load** (`query.isPending`) — `null`. No skeleton.

**Pending / processing** — `scan-ai-pending`, `aria-live="polite"`

```text
┌ Card ─────────────────────────────────────────────── scan-ai-pending ┐
│ AI overview                                               title-sm   │
│ The scan is complete. We're organizing the results into a simpler    │
│ explanation. The technical results below are ready now.   muted      │
└──────────────────────────────────────────────────────────────────────┘
```

Polls every 3s with no upper bound. If no job is ever enqueued (e.g. a scan completed before AI
was turned on), the backend returns `pending` forever and the card never resolves.

**Loading indicator (Q6 — proposed, maintainer to confirm).** The design system has no spinner or
card-level loading primitive: `LoadingSkeleton` renders static `<tbody>` bars for `DataTable` only,
and no screen uses a Lucide loader icon yet. Proposal: Lucide `LoaderCircle` (`size-4`,
`text-muted-foreground`, `animate-spin`, `aria-hidden`) inline before the pending sentence. FOUNDATIONS
§Motion allows it — a generating analysis is a rare state the reader should notice, and the global
`prefers-reduced-motion` block in `index.css` stops the rotation. The `aria-live` text stays the
accessible status. Alternative: static skeleton text bars inside the card (needs a new shared
primitive, since `LoadingSkeleton` is table-only).

**Completed** — `scan-ai-completed`

```text
┌ Card ───────────────────────────────────────────── scan-ai-completed ┐
│ AI overview                                               title-sm   │
│ A plain-language interpretation of this scan's recorded evidence.    │ body-sm muted
│                                                           (gap 6)    │
│ Uma vulnerabilidade precisa de atenção.                   title-xs   │ ◄ prose in pt-BR
│ Um equipamento possui software que deve ser revisado.     body-md    │
│                                                                      │
│ What to do first                                          title-xs   │
│  1. Peça a revisão do equipamento                          semibold  │
│     Solicite que um profissional confirme e atualize o serviço.      │
│     High priority                                         caption    │
│                                                                      │
│ Why these vulnerabilities matter                          title-xs   │
│  OpenSSH signal handler race condition   (title from scan.findings)  │
│  O software observado pode conter uma falha conhecida.               │
│  O serviço está acessível pela rede.                                 │
│  Recommended action: Confirme a versão antes de realizar alterações. │
│  ─────────────────────────── border-t rule between items ──────────  │
│                                                                      │
│ › Show assessment details and limitations    scan-ai-details-toggle  │
│   (collapsed: overall_assessment · "What this scan cannot confirm")  │
└──────────────────────────────────────────────────────────────────────┘
```

`status: completed` with `analysis: null` renders `null` silently.

**Failed** (`status: failed`) — `scan-ai-failed`

```text
┌ Card ─────────────────────────────────────────────── scan-ai-failed ┐
│ AI overview unavailable                                   title-sm  │
│ We couldn't prepare the plain-language overview. This does not     │
│ affect the technical scan results below.                  muted     │
└─────────────────────────────────────────────────────────────────────┘
```

**Read error** (GET `/analysis` fails; `retry: false`) — `scan-ai-error`

```text
┌ Card ──────────────────────────────────────────────── scan-ai-error ┐
│ AI overview                                                         │
│ We couldn't load the plain-language overview. The      [Try again]  │ ◄ button in card body
│ technical scan results below are still available.                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Industrial services — as built

Services arrive inside the page's own response, so **loading** and **error** are the page's
`ReadDetailGate` states (`host-detail` / `scan-detail` loading skeleton, "Couldn't load this
machine." / "Couldn't load this scan." + Retry). The component has no own loading or error state.

**Machine detail, empty** — always rendered

```text
┌ Card ── Industrial services ─────────────────────────────────────────┐
│ No industrial services were detected on this machine.                │ no-industrial-services
└──────────────────────────────────────────────────────────────────────┘
```

**Scan detail, empty** — card not rendered (`ScanIndustrialServices` returns `null`, and
`ScanDetail` guards the card).

**Populated** (scan detail shown; machine detail is the same block without the host heading)

```text
┌ Card ── Industrial services ───────────────── scan-industrial-services ┐
│ ┌ section ─────────────────────────── scan-industrial-host-{hostId} ┐  │
│ │ plc-line-2                                    h3 title-xs          │  │
│ │ 192.168.0.87                                  mono caption muted   │  │
│ │ ┌ article ─────────────────────────────── industrial-service-502 ┐ │  │
│ │ │ Modbus TCP · port 502         h3 title-xs          CONFIRMED   │ │  │ ◄ h3 under h3
│ │ │ Evidence              Mapping source     (sm:grid-cols-2)      │ │  │
│ │ │ tcp-port, pymodbus    generic baseline                         │ │  │ ◄ internal ids
│ │ │ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ border-dashed ┄┄┄┄┄┄┄┄┄┄┄┄┄┄ modbus-unit-1 ┄┄ │ │  │
│ │ │ Unit 1                                            RESPONDING   │ │  │
│ │ │ Schneider Electric · TM221CE16T · V1.0                         │ │  │
│ │ │ {unit.error — raw backend string, if any}                      │ │  │
│ │ │ ADDRESS SPACE        RANGE      RESULT     (hand-rolled table) │ │  │
│ │ │ holding register     0–3        readable · 2 non-zero · min 0 ·│ │  │
│ │ │                                 max 42                         │ │  │
│ │ │ coil                 8–11       illegal address (exception 2)  │ │  │
│ │ │ 2 controlled write validations recorded.                       │ │  │
│ │ └────────────────────────────────────────────────────────────────┘ │  │
│ └─── border-b rule, pb-8 ────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.4 Vulnerability panel, risk — as built

```text
┌ finding-panel-{id} ─────────────────────────────────────────────────────┐
│ RISK SCORE     81.25 / 100                             │ CVE            │
│                Confidence: confirmed                   │ CVE-2024-6387  │
│                Exploitability index: 0.97 / 1          │ CVSS           │
│                severity=high, confidence=confirmed     │ 8.1            │
│ WHAT IT IS     A timing flaw in the remote-login …     │ SEEN ON        │
│ WHAT TO DO     Update OpenSSH to 9.8 or later.         │ ssh · 22/tcp   │
└─────────────────────────────────────────────────────────┴───────────────┘
```

Risk is the **first** row. With no score it reads "Not calculated" on every vulnerability.

---

## 3. Conformance review

All items: **to confirm in Phase 1 code review**. Severity: **H** breaks a TRUTH criterion or a
binding rule visibly · **M** binding rule, lower impact · **L** polish.

### 3.1 AI overview (`frontend/src/pages/scans/ScanAIAnalysis.tsx`, `pages/ScanDetail.tsx`)

| # | Sev | Location | Rule broken | Required change |
|---|---|---|---|---|
| A1 | H | `backend/src/api/services/ai/prompts.py` `SYSTEM_PROMPT` ("Write all explanatory prose in Brazilian Portuguese") → rendered in `ScanAIAnalysis` | Copy is interface design; one language per screen. The UI is English; the analysis arrives in pt-BR. | Analysis prose must be in the UI language (English). Record in the AI ADR (Q2). |
| A2 | H | `ScanAIAnalysis.tsx:73-87` + `read.py` returns `pending` when no record exists | TRUTH "AI never hides results" holds, but the state never ends: unbounded 3s polling and a permanent "organizing" card for scans with no job. | Backend returns `unavailable` (or `failed`) when no job exists and none will run; UI keeps polling only while a job exists. Confirm root cause in Phase 1. |
| A3 | H | `ScanAIAnalysis.tsx:105-106` — `completed` with `analysis: null` returns `null` | TRUTH "AI provider fails → clear failed state". A completed-but-empty record silently vanishes. | Treat `completed && analysis == null` as the failed state. |
| A4 | M | `ScanDetail.tsx:74-77` — AI card placed before the severity groups | SCREENS.md §SCAN DETAIL: epicenter is the vulnerabilities; layout order is strip → vulnerabilities → machines. The async card also shifts the epicenter after load. | Move the card after the severity groups (or the "No vulnerabilities" line), before Industrial services. Amend SCREENS.md §SCAN DETAIL layout in Phase 6. See Q1. |
| A5 | M | `ScanAIAnalysis.tsx:54-66` — `Try again` button in `CardContent`, `justify-between` | FOUNDATIONS §Cards: a button in a card is a small outlined button **in the card footer**, never in the body. §Copy: buttons are verb + noun. | Footer, `variant="outline" size="sm"`, copy `Reload overview`, testid `scan-ai-retry`. |
| A6 | M | `ScanAIAnalysis.tsx:116-118` subtitle "A plain-language interpretation…" | §Copy: helper text on demand, not by default; labels over paragraphs. | Delete. |
| A7 | M | `ScanAIAnalysis.tsx:122` `text-title-xs` on a `<p>` (executive summary) | §Type: title tokens are for titles. | `text-body-md font-semibold`. |
| A8 | M | `ScanAIAnalysis.tsx` card body uses `gap-6`, `gap-3`, `gap-4`, `gap-2` | §Spacing rule 4: at most three vertical steps (intra-group, inter-group, inter-section). | Intra-group `2`, inter-group `4`, sections inside the card `6`. Replace `gap-3` with `2`. |
| A9 | L | `ScanAIAnalysis.tsx:163` `border-t border-rule` between explanations | House style: group by spacing, fewer lines. | Remove the rule; the step-4 gap separates items. |
| A10 | L | `PRIORITY_LABEL` "High priority" / "Medium priority" / "Low priority" | §Vocabulary: one word per concept. *High/Medium/Low* are severity words; reusing them for action priority invites confusion. | `Do this now` / `Do this soon` / `When you can` / `Later` (maps `immediate`/`high`/`medium`/`low`). |
| A11 | L | Pending/failed/error copy: "We…", "technical scan results below" | §Copy: plain, no product voice; "below" becomes wrong after A4. | Replace per §6. |
| A12 | L | `ScanAIAnalysis.tsx:166-167` fallback `'Recorded vulnerability'` | Unreachable if `validation.py` holds (ids must be in context) — dead branch. | Confirm in Phase 1; drop the item instead of inventing a title if the id is unknown. |
| A13 | — | AI-written text may say *finding*, *device* for a machine, or certify safety | §Vocabulary and "Never certify safety" apply to every string on the page, generated or not. | Prompt must carry the vocabulary and the no-safety-claim rule. Belongs in the AI ADR (Phase 3). |

Conforming as built: severity has no hue anywhere in the card; `unavailable` renders nothing
(absent, not disabled); no `dark:`; `Disclosure` is a shared component; `aria-live` on pending;
the failed state shows no partial analysis.

### 3.2 Industrial services (`pages/hosts/IndustrialServices.tsx`, `pages/scans/ScanIndustrialServices.tsx`, `pages/HostDetail.tsx`, `pages/ScanDetail.tsx`)

| # | Sev | Location | Rule broken | Required change |
|---|---|---|---|---|
| I1 | H | `IndustrialServices.tsx:7-9 words()`, `:140`, `:146`, `:33-34`, `:58`, `:133` | §Audience: the product interprets, not raw data for triage; zero training. `tcp-port, pymodbus`, `generic baseline`, `illegal address (exception 2)`, `CONFIRMED` are internal identifiers with underscores swapped for spaces. | Map every enum to plain words (§6). Move `evidence_sources`, `mapping_source` and the address-range table behind a `Disclosure` "Show technical details". |
| I2 | H | `IndustrialServices.tsx:63-65` renders `unit.error` verbatim | §Copy: real, plain content; no raw backend strings. | Do not render `error`. Unit status word carries the meaning (`Error` → "Didn't answer correctly"). |
| I3 | M | `IndustrialServices.tsx:104-107` "N controlled write validation(s) recorded." | Zero training; ADR-018 active Modbus safety makes a write a sensitive fact. Ambiguous and alarming. | Plain sentence (§6). Wording to confirm against ADR-018. |
| I4 | M | `IndustrialServices.tsx:53,78` `border-dashed border-border` | FOUNDATIONS has no dashed rule; group by surface and spacing. | Remove the dashed borders; separate units with step `4`. |
| I5 | M | `IndustrialServices.tsx:72-100` hand-rolled `<table>`, `text-caption-md` cells, uppercase `font-normal` headers | §Interaction/§Tables: tables are shared components (`DataTable` owns 56px rows and header style); dense cells are `text-body-sm`. | Use the shared table primitive with `DataTable` header treatment; cells `text-body-sm`; sentence-case headers. |
| I6 | M | `IndustrialServices.tsx:137` `sm:grid-cols-2` | §Theme: desktop only, no responsive breakpoints. | Removed with I1 (moves into the disclosure); if kept, plain `grid-cols-2`. |
| I7 | M | `ScanIndustrialServices.tsx:26` host `h3` + `IndustrialServices.tsx:131` service `h3` + unit `h4` | Heading hierarchy (a11y): service is a child of host on scan detail. | Service heading level is a prop: `h3` on machine detail, `h4` on scan detail. |
| I8 | M | `HostDetail.tsx:55-62` card always rendered; `ScanDetail.tsx:107-118` card hidden when empty | Consistency; FOUNDATIONS "a panel carries no trailing empty row"; noise on every office machine. | Omit the card on machine detail when `industrial_services` is empty (Q3). `no-industrial-services` is then removed. |
| I9 | M | `HostDetail.tsx`, `ScanDetail.tsx` new cards | SCREENS.md §SCAN DETAIL and §NETWORK DETAIL layouts do not list the section. | Amend SCREENS.md in Phase 6 (order: … services → industrial services → scan history; … vulnerabilities → AI overview → industrial services → machines seen). |
| I10 | L | `ScanIndustrialServices.tsx:23` `border-b border-rule pb-8` between hosts | Fewer lines; parent owns space. | Remove border and `pb-8`; container `gap-8` already separates hosts. |
| I11 | L | `IndustrialServices.tsx:131` "Modbus TCP · port 502" — port in sans | §Type: port is data, set in mono. | "Modbus on port `502`", port in `font-mono`. |

Conforming: vocabulary *machine* used correctly; empty copy is one reassuring sentence; IP in mono;
`overflow-x-auto` around the table; no severity hue.

### 3.3 Vulnerability panel risk (`pages/scans/FindingPanel.tsx`)

| # | Sev | Location | Rule broken | Required change |
|---|---|---|---|---|
| R1 | H | `FindingPanel.tsx:54` renders `risk_rationale` (`severity=low, confidence=tentative`) | Zero training; plain words over vectors. A `key=value` string is a machine format. | Do not render `risk_rationale`. |
| R2 | M | `FindingPanel.tsx:43-57` risk is the first row of the main column | Panel epicenter is "What it is" / "What to do". CVE and CVSS already live in the right margin. | Move to the right margin as a `RISK` block, after `CVSS`. Target layout ("What it is" / "What to do" main column, reference margin) approved by Guilherme Ronca on 2026-09-12 via artifact comment. |
| R3 | M | `FindingPanel.tsx:46-48` "Not calculated" on every unscored vulnerability | Absent, not disabled — the panel omits CVE/CVSS when absent; risk should match. | Omit the block when `risk_score == null`. Update `FindingPanel.test.tsx` (it asserts "Not calculated"). |
| R4 | L | `toFixed(2)` → "81.25 / 100", "Exploitability index: 0.97 / 1" | False precision; "exploitability index" is analyst vocabulary. | `81 of 100` (rounded integer); drop the exploitability line; confidence as one capitalised word under the score. |
| R5 | L | `<p>` elements inside `<dd>` after a bare text node | Structure; inconsistent with neighbouring rows. | Resolved by R2 (block of `<p>` like CVE/CVSS). |

Pre-existing, **not** introduced by PR #144, out of scope: `Disclosure` caret `size-3` (icon rule
allows `size-4`/`size-5` only); `outline` button uses `--rule` not `--edge` (FOUNDATIONS §Color).

---

## 4. Required target states (TRUTH acceptance criteria)

Vertical rhythm on SCAN DETAIL: intra-group `2`, inter-group `4` (inside cards) / `8` (between
severity cards), inter-section `12` (unchanged). AI card: `Card` padding step `6` (primitive
default), inner sections `6`, inner groups `4`, lines `2`.

| TRUTH scenario | Target | Status as built |
|---|---|---|
| **AI disabled** — all results show; AI area shows no error; no provider call | `unavailable` → `null`. One GET is acceptable; no card, no testid. | Conforms (UI). Provider call: backend test. |
| **AI provider fails** — results show; clear failed state; no partial analysis | `failed`, **or** `completed` with `analysis: null` → `scan-ai-failed`. Never render any `analysis` field in this state. | Partly — A3. |
| **Results always visible** | AI card never replaces or precedes the epicenter; it sits after the severity groups, so vulnerabilities render first and never shift. | Partly — A4. |
| Pending ends | Pending only while a job exists; otherwise `unavailable`/`failed`. | No — A2. |

### Target: SCAN DETAIL, completed, AI completed

```text
┌──────────────────────────── max-w-frame ─────────────────────────────┐
│ ← Back                                                                │
│ Scan · yesterday 21:40                                                │
│ NSPi · 192.168.0.0/24 · 12 machines · 3 vulnerabilities               │
│                                                         step 12       │
│ ┌ High ────────────────────────────────────────── findings-high ──┐   │ epicenter first
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                         step 12       │
│ ┌ AI overview ─────────────────────────────── scan-ai-completed ──┐   │
│ │ One machine needs attention soon.            body-md semibold   │   │
│ │ pi-lab runs an older remote-login service with a known weakness.│   │
│ │                                                  step 6         │   │
│ │ What to do first                                 title-xs       │   │
│ │  1. Update the remote-login software on pi-lab                  │   │
│ │     Ask whoever looks after pi-lab to install the latest updates│   │
│ │     Do this now                                  caption muted  │   │
│ │                                                  step 6         │   │
│ │ Why these vulnerabilities matter                                │   │
│ │  OpenSSH signal handler race condition                          │   │
│ │  …explanation · why it matters · Recommended action: …          │   │
│ │                                  (step 4 between items, no rule)│   │
│ │ › Show assessment details and limitations                       │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│ ┌ Industrial services ────────────────── scan-industrial-services ┐   │
│ ┌ Machines seen ──────────────────────────────────────────────────┐   │
└───────────────────────────────────────────────────────────────────────┘
```

### Target: AI states

```text
Disabled (unavailable)   Pending                         Failed                             Read error
(no card)                ┌ AI overview ───────────────┐  ┌ AI overview ────────────────────┐ ┌ AI overview ─────────────┐
                         │ Preparing a plain-language │  │ The overview couldn't be        │ │ Couldn't load the        │
                         │ overview of this scan.     │  │ prepared for this scan. The     │ │ overview.                │
                         └─ scan-ai-pending ──────────┘  │ vulnerabilities above are       │ │        [Reload overview] │ footer, outline sm
                                                         │ complete and don't depend on it.│ └─ scan-ai-error ──────────┘
                                                         └─ scan-ai-failed ────────────────┘    button: scan-ai-retry
```

Failed has no action: there is no regenerate endpoint, so the action is absent. The next step is
the sentence pointing at the results.

### Target: Industrial service block (scan detail; machine detail omits the host heading)

```text
┌ Industrial services ─────────────────────────────── scan-industrial-services ┐
│ plc-line-2                                    h3 title-xs                     │
│ 192.168.0.87                                  mono caption muted              │
│                                               step 4                          │
│ Modbus on port 502 · Confirmed                h4 title-xs, 502 mono           │ industrial-service-502
│ Unit 1 · Responding · Schneider Electric TM221CE16T V1.0        body-md       │ modbus-unit-1
│ One test write was made and undone on this controller.          body-sm muted │ (only if validations)
│ › Show technical details                             industrial-details-toggle-502
│   Found by       Port check, Modbus reply                                     │
│   Addresses read on unit 1                                                    │
│   Area               Addresses   Result                (shared table, 56px)   │
│   Holding registers  0–3         Readable · 2 of 4 set · values 0 to 42       │
│   Coils              8–11        Not available on this controller             │
└───────────────────────────────────────────────────────────────────────────────┘
```

Machine detail, empty: **no card** (Q3). Loading and error: page-level, unchanged.

### Target: vulnerability panel

```text
│ WHAT IT IS   A timing flaw in the remote-login …   │ CVE            │
│ WHAT TO DO   Update OpenSSH to 9.8 or later.       │ CVE-2024-6387  │
│                                                    │ CVSS  8.1      │
│                                                    │ RISK           │ findings-panel-risk-{id}
│                                                    │ 81 of 100      │ (absent when risk_score null)
│                                                    │ Confirmed      │
```

### Keyboard and focus

No new focus targets beyond: `scan-ai-details-toggle` (Enter/Space toggles), `scan-ai-retry`
(Enter/Space refetches; if the card is replaced, focus returns to the document body, no forced
move), `industrial-details-toggle-{port}` (Enter/Space toggles). Tab order follows the
DOM order in §4. No focus is moved when the AI card changes state; `aria-live="polite"` on the
card announces pending → completed/failed.

---

## 5. Decision-dependent UI

| Decision outcome | UI consequence |
|---|---|
| **D1 — any provider** | No provider or model name is shown today; none is required unless D2 requires disclosure. Copy stays provider-neutral ("AI overview"). |
| **D2 — full context as built, or reduced context** | No UI change beyond §4. |
| **D2 — off by default, per-organisation opt-in** | Off → `unavailable` → no card (no nag on scan detail). Opt-in control lives on **SETTINGS**, admin only, **absent for viewers**. Shape: one `Switch` row. Label `Plain-language AI overviews`; one line under it naming what leaves the product (exact line comes from the ADR, e.g. `Sends vulnerability titles, services and machine names from each scan to {provider}.`); turning it on requires a confirm dialog: title `Turn on AI overviews?`, body = the same data line, buttons `Turn on overviews` / `Keep off`. Blocked on a settings contract field — no endpoint exists. Needs its own SETTINGS spec amendment before build. |
| **D2 — disclosure required on the result** | Add a caption in the AI card footer: `Written by an AI model from this scan's results. Check the vulnerabilities above before acting.` testid `scan-ai-provenance`. |
| **D3** | No UI change, provided the status union stays `pending · processing · completed · failed · unavailable`. |
| **D7 / AI part removed** | Delete `ScanAIAnalysis.tsx` + test, `getScanAnalysis`, `queryKeys.scans.analysis`, the MSW `/analysis` handler, regenerate `openapi.d.ts`. SCAN DETAIL returns to SCREENS.md as written. |
| **D6 — this PR wins** | §3.2 changes apply; SCREENS.md amended (I9); overlapping issue rescoped to point here. |
| **D6 — in-progress issue wins** | Delete `IndustrialServices.tsx` + test, `ScanIndustrialServices.tsx`, `test/industrialFixtures.ts`, the `industrial_services` fixture fields, the two cards; that issue's DESIGN.md owns the surface and inherits §3.2 findings. |
| **D6 — merge both** | This document's §4 industrial target is the baseline the other issue's DESIGN.md must match. |
| **Risk context** (part 1, rides with D6) | Kept → R1–R5. Removed → revert `FindingPanel.tsx` and delete `FindingPanel.test.tsx`. |
| D4, D5 | No web UI. |

---

## 6. Copy

| Element | As built | Target |
|---|---|---|
| AI card heading (all states) | `AI overview` · failed: `AI overview unavailable` | `AI overview` in every state |
| AI completed subtitle | `A plain-language interpretation of this scan's recorded evidence.` | *(deleted)* |
| AI pending | `The scan is complete. We're organizing the results into a simpler explanation. The technical results below are ready now.` | `Preparing a plain-language overview of this scan.` |
| AI failed | `We couldn't prepare the plain-language overview. This does not affect the technical scan results below.` | `The overview couldn't be prepared for this scan. The vulnerabilities above are complete and don't depend on it.` |
| AI read error | `We couldn't load the plain-language overview. The technical scan results below are still available.` | `Couldn't load the overview.` |
| AI read error button | `Try again` | `Reload overview` |
| AI sections | `What to do first` · `Why these vulnerabilities matter` · `Recommended action: ` · `What this scan cannot confirm` | unchanged |
| AI disclosure | `Show assessment details and limitations` | unchanged |
| AI priority | `Immediate` · `High priority` · `Medium priority` · `Low priority` | `Do this now` · `Do this soon` · `When you can` · `Later` |
| AI unknown vulnerability | `Recorded vulnerability` | *(item omitted)* |
| AI prose language | pt-BR (generated) | English (Q2) |
| Industrial card heading | `Industrial services` | unchanged |
| Industrial empty (machine) | `No industrial services were detected on this machine.` | *(card omitted, Q3)* |
| Service heading | `Modbus TCP · port 502` | `Modbus on port 502` |
| Confidence | `confirmed` / `suspected` (uppercase) | `Confirmed` / `Possible` (after heading, ` · `) |
| Evidence label / values | `Evidence` · `tcp-port, pymodbus` | in disclosure: `Found by` · mapped words; unknown source → `Other check` (mapping list to confirm with backend) |
| Mapping source | `Mapping source` · `generic baseline` / `Not mapped` | *(dropped from owner view — to confirm; engineering detail)* |
| No units | `No Modbus units responded.` | `The service is open, but no controller answered.` |
| Unit line | `Unit 1` + `RESPONDING` + identity joined by ` · ` | `Unit 1 · {status} · {vendor product revision}` |
| Unit status | `responding` · `exception` · `timeout` · `error` · `skipped` | `Responding` · `Refused the request` · `Didn't answer in time` · `Didn't answer correctly` · `Not checked` |
| Unit error | raw `unit.error` | *(not rendered)* |
| No ranges | `No address ranges were mapped.` | `No addresses were read.` |
| Table caption | `Address ranges mapped for Modbus unit 1` | `Addresses read on unit 1` |
| Table headers | `Address space` · `Range` · `Result` | `Area` · `Addresses` · `Result` |
| Address space | `coil` · `discrete input` · `holding register` · `input register` | `Coils` · `Discrete inputs` · `Holding registers` · `Input registers` |
| Range result | `readable · 2 non-zero · min 0 · max 42` | `Readable · 2 of 4 set · values 0 to 42` |
| Range status | `illegal address (exception 2)` · `illegal function` · `timeout` · `error` · `skipped` | `Not available on this controller` · `Not supported by this controller` · `Didn't answer in time` · `Couldn't be read` · `Not checked` |
| Validations | `2 controlled write validations recorded.` | `One test write was made and undone on this controller.` / `{N} test writes were made and undone on this controller.` — wording to confirm against ADR-018 |
| Panel risk label | `Risk score` | `Risk` |
| Panel risk value | `81.25 / 100` · null: `Not calculated` | `81 of 100` · null: *(block omitted)* |
| Panel confidence | `Confidence: confirmed` | `Confirmed` · `Probable` · `Tentative` → `Confirmed` · `Likely` · `Possible` |
| Panel exploitability | `Exploitability index: 0.97 / 1` | *(dropped)* |
| Panel rationale | raw `risk_rationale` | *(not rendered)* |

---

## 7. data-testid list

| testid | Element | As built | Target |
|---|---|---|---|
| `scan-ai-pending` | AI card, pending/processing | yes | keep |
| `scan-ai-completed` | AI card, completed | yes | keep |
| `scan-ai-failed` | AI card, failed (+ completed with null analysis) | yes | keep, widen condition |
| `scan-ai-error` | AI card, read error | yes | keep |
| `scan-ai-retry` | `Reload overview` button | — | **add** |
| `scan-ai-details-toggle` | details disclosure trigger | yes | keep |
| `scan-ai-details-caret` | disclosure caret | yes | keep |
| `scan-ai-provenance` | provenance caption | — | add **only** if D2 requires |
| `scan-industrial-services` | industrial card body, scan detail | yes | keep |
| `scan-industrial-host-{hostId}` | host section | yes | keep |
| `industrial-services` | services list | yes | keep |
| `industrial-service-{port}` | one service | yes | keep |
| `industrial-details-toggle-{port}` | `Show technical details` | — | **add** |
| `modbus-unit-{unitId}` | one unit | yes | keep |
| `no-industrial-services` | machine-detail empty line | yes | **remove** (Q3 accepted) |
| `findings-panel-risk-{findingId}` | risk block in panel margin | — | **add** |

## Files implementers touch

| Path | Change |
|---|---|
| `frontend/src/pages/scans/ScanAIAnalysis.tsx` | A3, A5–A12; copy |
| `frontend/src/pages/scans/ScanAIAnalysis.test.tsx` | new states, copy, `scan-ai-retry`, completed-null → failed |
| `frontend/src/pages/ScanDetail.tsx` | A4 order |
| `frontend/src/pages/ScanDetail.test.tsx` | order and industrial copy |
| `frontend/src/pages/hosts/IndustrialServices.tsx` | I1–I7, I11; copy |
| `frontend/src/pages/hosts/IndustrialServices.test.tsx` | copy, disclosure, no raw ids |
| `frontend/src/pages/scans/ScanIndustrialServices.tsx` | I7, I10 |
| `frontend/src/pages/HostDetail.tsx` / `HostDetail.test.tsx` | I8 |
| `frontend/src/pages/scans/FindingPanel.tsx` / `FindingPanel.test.tsx` | R1–R5 |
| `frontend/src/test/industrialFixtures.ts`, `frontend/src/test/mswHandlers.ts` | fixture updates only |
| `backend/src/api/services/ai/prompts.py`, `backend/src/api/services/ai/read.py` | A1, A2, A13 — owned by ARCHITECTURE.md, listed here for traceability |
| `docs/ui/SCREENS.md` | I9 and A4 layout amendments (Phase 6) |

---

## Out of scope

- New AI surfaces (chat, reports, Home summary) — TRUTH §Out of scope.
- The SETTINGS opt-in screen build (only its shape is noted under D2; it needs a contract and a
  SETTINGS amendment first).
- Pre-existing `Disclosure` caret size and outline-button border token.
- Linking industrial host headings to machine detail.

## Open questions (approval gate)

1. **Q1 — AI card position.** Recommended: after the vulnerability groups (A4). Alternative: keep
   it first and amend SCREENS.md to make the overview the scan-detail epicenter. Maintainer to pick.
2. **Q2 — Analysis language.** English to match the UI (recommended), or localise the whole app.
   Belongs in the AI ADR.
3. **Q3 — Empty industrial card on machine detail.** **Decided 2026-09-12 (Guilherme Ronca, artifact comment): omit the card when `industrial_services` is empty** (matches scan detail). `no-industrial-services` is removed.
4. **Q4 — Validation-write copy.** Needs ADR-018 owner to confirm what a "controlled write
   validation" does to the controller before the sentence ships.
5. **Q5 — `evidence_sources` vocabulary.** The set of values is open strings; backend to publish
   the list so each maps to plain words.
6. **Blocked on contract:** D2 opt-in has no settings endpoint.
7. **Q6 — AI pending loading indicator.** Maintainer asked for one (artifact comment, 2026-09-12). Proposed: Lucide `LoaderCircle` spinning, reduced-motion safe. Alternative: new card skeleton primitive. Maintainer to pick.

## Approved target states (artifact comments, Guilherme Ronca, 2026-09-12)

- AI overview **completed** card as mocked — approved ("clean").
- AI overview **failed** card with `Couldn't load the overview.` and footer `Reload overview` — approved.
- Machine detail **empty** industrial state: no card (Q3).
- Vulnerability panel layout: "What it is" / "What to do" main column, risk in the margin (R2).
