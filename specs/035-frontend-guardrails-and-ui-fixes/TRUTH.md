# TRUTH — Frontend Foundations guardrails and the UI defects they prevent

> Source: **DMI-107** (validated by @guilhermeronca on 2026-08-18), plus one folded-in
> backend item from the issue's 2026-08-21 comment — see **Scope note** below.
>
> **Approved at the specification gate by @guilhermeronca on 2026-08-22**, after a refine pass
> that changed five things. Recorded here because three of them reverse DMI-107 itself, and a
> reader who only has the issue would otherwise think the specs had drifted:
>
> 1. **The `/styleguide` page is cut.** DMI-107 asked for it; the rendered preview now serves the
>    same need. See business rules 10–11 and `ARCHITECTURE.md` §6.
> 2. **The `remediate` skill stays**, but no longer blocks the UI fixes — see the ordering note in
>    the Narrative and `ARCHITECTURE.md` §10, Phase R.
> 3. **The `/login` network-error string is folded in** as a violation; the shared constant already
>    exists and four other screens use it.
> 4. **The `/login` title `Sign in` wins** over `SCREENS.md` §LOGIN, which is amended instead
>    (`DESIGN.md` §14.12). This one is a contradiction, resolved in the code's favour.
> 5. Four factual defects in the specs were corrected — most consequentially, a clean tree needs
>    **33** violations cleared, not 32.

## Narrative

The web frontend shipped visible quality defects: a nav crowded against the wordmark, a
720px-wide login card that reads as a letterbox, a disclosure control with no click
affordance, and a Settings page that opens on a password form with no indication of which
account is signed in.

The visual direction is not the problem and does not change. The problem is a gap in the
written foundations. `SCREENS.md` §Foundations specifies every **static** property
exhaustively and says nothing about **interactive state** or **proportion** — `cursor`
appears zero times in its 1630 lines, `hover` twice and only about revealing truncated IDs.
Every defect landed in those two gaps.

The evidence separates the two kinds of rule cleanly. The spacing scale — mechanical and
enumerable — was obeyed **100%**: zero violations. The rules needing judgement or tooling
were not: **29** raw `text-sm` in application code instead of the scale token, **3**
arbitrary width values, and **1** bare native button in application code, which is exactly
the control that feels broken.

Compounding it, nothing in this repo renders a pixel. The test runner is jsdom and the
design agent writes ASCII mockups, which cannot express proportion, type size or
affordance. Designs were approved that nobody could actually see.

This feature closes both gaps in the written foundations, makes the mechanical rules
machine-enforced, gives the human real pixels to approve before code exists, and only then
fixes the defects under the new rules.

**Ordering is a rule, not a preference.** Every guardrail is complete before any UI fix
starts. The UI fixes are built under the new rules and checked by the new gate — that is
the reason the two halves are one feature rather than two.

*Scoped 2026-08-22.* The rule binds the guardrails the UI fixes actually stand on: the
written foundations, the tokens, the linted rules, the cleared violations, the shared
disclosure, and the agent instructions that govern the code being written. It does **not**
bind the feedback-classification skill of rules 14–15, which acts on work already shipped
and which nothing in the four UI defects touches. That skill is in scope for this feature
and runs independently, like the configuration item. The rule is unchanged where its reason
reaches; it is not extended past it.

## Scope note — one folded-in backend item

DMI-107 is fenced to the frontend. A comment on the issue reports a **backend** defect and
explicitly says it may deserve its own issue. **Guilherme decided on 2026-08-21 to fold it
in.** It is therefore in scope here, and this feature consequently owes **both** layer
gates rather than the frontend gate alone.

The defect: the allowed-origins setting carries a default that trusts a developer
workstation plus a placeholder domain nobody owns. If the environment variable is ever
missing, the API comes up trusting a laptop instead of refusing to serve — it fails
**open**, silently. Combined with credentialed cross-origin requests, that is a real
exposure. The deployed service was already corrected by hand; what remains is the code
default that made it easy to get wrong.

## Business rules

### Foundations — the written rules

1. **Every interactive element declares its full interactive state.** Cursor, hover,
   focus-visible, active and disabled are each specified. An element the user can act on
   and which looks identical under the pointer is a defect, not a style preference.
2. **Only shared UI primitives may be interactive.** Application screens compose
   primitives; they do not hand-roll a native control. This is what makes rule 1
   enforceable in one place instead of at every call site.
3. **Containers have names, and the names are the only widths.** A layout width is one of
   the named containers — the outer frame, the form column — never an ad-hoc
   measurement. *Amended 2026-08-21: a separate prose column was specified and then
   removed when the shell was resolved to a single frame; see rule 3a.*
3a. **The shell is one frame, and the navigation is centred in it.** The top bar's
   contents and the page content beneath it share the same width, so the wordmark and the
   page title start on the same vertical. Navigation items are centred on the bar and grow
   symmetrically from its centre as destinations are added; centring is the standing
   default, not a treatment for any particular number of items.
4. **A card sizes to its content, never to its column.** A short form in a wide column is
   a narrow card centred in that column, not a wide card. This is the rule the login
   letterbox broke.
5. **Type sizes come from the named scale.** The raw framework size utilities are not part
   of the scale, and using one is a violation even when it happens to render the same
   pixels.

### Enforcement

6. **A mechanical rule is enforced by the linter, not by memory.** Any rule that can be
   decided by reading the source text is a lint failure the moment it is written. The
   spacing scale proves the point: it was obeyed perfectly because it is enumerable, while
   every judgement rule drifted.
7. **The enforcement adds no dependency.** It lives in the existing lint configuration.
8. **The shared UI primitives are exempt from the authored-style rules, and only they.**
   They are vendored third-party source, and the rules exist to govern the code this team
   writes. Test files are exempt for the same reason — a native button in a test is a
   fixture, not a shipped control.
9. **Enforcement and remediation land together.** The change that adds a rule also clears
   every violation that rule finds, so no commit is ever knowingly red.

### Seeing the pixels

10–11. **Withdrawn 2026-08-22.** DMI-107 required a development-only page that renders the
    whole design system in one look, and required it absent from the production build.
    Guilherme withdrew both at the refine gate: the rendered preview of rule 12 already
    serves the "judge it in one look" need — it is what option C was chosen from — and the
    human check of rule 13 already catches drift across the five real screens. A second
    surface, plus a build-time bundle assertion, was not worth its cost to the one person it
    served. Rules 12–17 keep their numbers so existing citations stay valid.
12. **A design is approved as rendered pixels, not as ASCII.** A design document carries a
    rendered preview built from the real tokens and the real typefaces.
13. **The visual check is performed by a human, and it closes every frontend feature.**
    No agent signs off on how something looks.

### Feedback re-entering the pipeline

14. **Human feedback is classified before it becomes work.** Each item is either a
    **violation** — the specification was right and the code broke it, which becomes a
    task — or a **contradiction** — the specification itself must change, which becomes a
    proposed specification amendment requiring human approval *before* any task is
    written.
15. **A contradiction never silently becomes a task.** Approval of the amendment is a gate.

### Configuration safety

16. **A security-relevant setting fails closed.** When it is absent, the system refuses or
    permits nothing; it never falls back to a permissive value. Misconfiguration must look
    like a broken product, which gets noticed, rather than a quietly permissive one, which
    does not.
17. **No default names a host nobody controls.**

## User stories

1. As the product owner, I approve a rendered preview instead of ASCII art, so that
   proportion mistakes are caught before code exists.
2. As the product owner, I type my complaints in plain words and get correctly-classified
   tasks back, so that feedback re-enters the pipeline without me writing specifications.
3. As an agent, I get a lint error the moment I write an off-token value, so that the rule
   is enforced rather than remembered.
4. As a member, I see which account I am signed in as on the settings screen, so that I
   know whose password I am about to change.
5. As a member, I can tell that the activity disclosure is something I can click, so that
   I do not mistake it for a label.
6. As a member signing in, the sign-in card reads as a portrait card rather than a
   letterbox band, so that the screen looks finished.
7. As an operator, an environment missing its allowed-origins configuration refuses
   cross-origin callers outright, so that a missing variable cannot silently trust a
   developer's workstation.

## Acceptance criteria (verifiable)

### Guardrails

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Arbitrary width rejected | application source containing an arbitrary-value width utility | the frontend lint gate runs | it exits non-zero and names the arbitrary-value rule |
| Raw type size rejected | application source containing a raw framework size utility | the frontend lint gate runs | it exits non-zero and points at the scale token to use instead |
| Off-scale spacing rejected | application source containing a spacing step outside the scale | the frontend lint gate runs | it exits non-zero and names the spacing rule |
| Native control rejected in a screen | a native button element in an application screen | the frontend lint gate runs | it exits non-zero |
| Native control allowed in a primitive | the same element inside the shared UI primitives | the frontend lint gate runs | it passes |
| Native control allowed in a test | the same element inside a test file | the frontend lint gate runs | it passes |
| Tree is clean | the repository at the head of this feature | the frontend lint gate runs | it exits zero — all **33** pre-existing violations are cleared: 29 raw type sizes, 3 arbitrary widths, and the 1 native control. The 32 in the narrative are the mechanical ones; the 33rd needs the shared disclosure to exist first, so it is cleared with that, not with a token swap |
| Type-token swap is invisible | the 29 raw type-size occurrences replaced by the scale token | the screens render | computed font size is unchanged at 14px |
| Violation is not gated | the feedback *"the activity disclosure does not look clickable"* — a behaviour business rule 1 already requires | the remediation flow runs | the item is classified as a **violation** and a task is written directly, with no approval step |
| Contradiction is gated | the feedback *"the navigation should be centred on the bar"* — a behaviour `SCREENS.md` §App shell explicitly decided otherwise on 2026-08-07 | the remediation flow runs | the item is classified as a **contradiction**, a written amendment against the named section is proposed, and **no task is written** until a human approves it |
| Both classes are demonstrated, not described | the finished remediation skill | it is read | it carries these two items as worked examples, each showing the input feedback, the section cited, the classification, and the output — so the classification test is checkable against a known answer rather than trusted |
| The gate wording is fixed | a contradiction is classified | the flow stops | it states which document and section the amendment targets, and what it would change, before asking for approval — an amendment nobody can review is not a gate |

### UI fixes

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Top bar proportion | the top bar at 1440px | it renders | the wordmark sits at the frame's left edge, the navigation is **centred on the bar** with 16px between items, and nav items compute to 11px |
| Content column matches the bar | the same viewport | an inside-shell screen renders | the page content column is the **same width as the bar's contents**, so the wordmark and the page title share a left edge |
| Navigation stays centred as it grows | a fourth destination added to the bar | it renders | the navigation is still centred on the bar; items are not pushed left |
| Wordmark unchanged | the same viewport | the top bar renders | the wordmark is 16px in the title face |
| Sign-in card proportion | the sign-in screen at 1440px | it renders | the card is 384px wide and taller than it is wide |
| Identity is visible first | the settings screen | it loads | the signed-in email and role are visible without any interaction, and no field has focus |
| Settings order | the settings screen | it loads | the sections read: your details, then the change-password trigger, then activity, then leaving the organization |
| Password form is behind a trigger | the settings screen | the change-password control is activated | a modal opens containing the three password fields |
| Focus returns | that modal | it is dismissed | focus returns to the control that opened it |
| Existing confirmation unchanged | the leave-organization confirmation | it is opened and used | its behaviour is identical to before this feature |
| Disclosure affords a click | the activity disclosure | it is hovered | the cursor is a pointer and the label is underlined |
| Disclosure works by keyboard | the activity disclosure | it is activated by keyboard | its expanded state flips and the note is announced |
| Disclosure caret | the activity disclosure | it is expanded | the caret rotates and the focus ring is intact |
| Activity heading | the settings screen | the activity section renders | the heading is on its own line above the disclosure row |
| Mark is a vector | the auth screens | they render | the decorative mark is inline vector artwork, and no Unicode ornament glyph is used anywhere |
| One network-error string, not two | the sign-in screen | the server cannot be reached | the message is the shared service-error string every other screen already shows, read from the one shared constant rather than repeated in the screen |
| The sign-in title is settled | the written screen specification | it is read | it states the title the shipped screen uses, so the two no longer disagree and nobody re-opens it |

### Configuration safety

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Fails closed when absent | no allowed-origins configuration | the API starts | it either refuses to start or permits no origin at all — never a developer workstation |
| Foreign origin refused | a single production origin configured | a preflight arrives from a developer workstation origin | the response carries no allow-origin header |
| Configured origin served | the same configuration | a preflight arrives from the configured origin | it returns 204 with no body headers — the existing preflight behaviour does not regress |
| Placeholder host gone | the configuration source | it is read | no host the team does not control appears in any default |

### Gates

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Frontend gate | the finished feature | lint, format check, typecheck, tests and build run from the frontend | all pass |
| Backend gate | the finished feature | the backend lint and test suite run with the database up | all pass with zero database-test skips |

## Out of scope (v1)

- **No change to the visual direction.** Paper surface, IM Fell titles, IBM Plex Mono,
  purple accent and zero radius all stay exactly as they are.
- No dark mode, no theme toggle, no dark variants, no colour-scheme detection.
- No mobile or tablet layouts.
- No display-name editing and no self-profile update operation. Open question **C3** stays
  open; the details block is read-only and gains editing later.
- No change to the body type size, which stays 14px. The 11px size is navigation-only.
- No screenshot, visual-regression or browser-driven tests. No new runtime or development
  dependency.
- No agent-driven visual check. The visual check is performed by the human.
- No new screens. Scans, hosts, agents and the rest stay unbuilt.
- **No development-only design-system page.** Withdrawn 2026-08-22 — see business
  rules 10–11. No `/styleguide` route, no production-bundle assertion, and no change
  to the frontend build script.
- No password strength meter — it stays parked.
- No changes to the home screen beyond the shared mark it already uses.
- No hand-edits to the API contract or its generated types.
- No repository-wide formatter run.
- Beyond the one folded-in setting, no other configuration hardening. The silent-failure
  pattern elsewhere in configuration is a separate concern.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`

## Docs drift

- `docs/adr/ADR-005-security-model.md` §3 still names
  `https://app.vscanner.example.com` as the production CORS origin; code now has no trusted
  default and expects each deployment to supply its exact origins.
- `docs/architecture/ARCHITECTURE.md` §8 still lists example production and local origins,
  including `http://localhost:3000`; whether those remain target-state policy needs human
  authority before the document changes.
