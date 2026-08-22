# Tasks — Frontend Foundations guardrails and the UI defects they prevent (`035-frontend-guardrails-and-ui-fixes`)

9 tasks. **Unblocked now: #1, #8, #9**

> **This feature is not a Python feature.** Its blast radius is `frontend/`, `docs/`, `.claude/`
> and one backend file. Spawn the agents named per task — `test-engineer` and `code-reviewer`
> write pytest and gate on `uv run ruff check`, neither of which exists in `frontend/`.
>
> | Tasks | Test agent | Review agent | Gate |
> |---|---|---|---|
> | #2 #3 #4 #5 #6 #7 | `frontend-test-engineer` | `frontend-code-reviewer` | `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build` from `frontend/` |
> | #9 | `test-engineer` | `code-reviewer` | `./database.sh` **first**, then `uv run ruff check src tests` + `uv run pytest` from `backend/`. Expect **665 passed / 0 skipped** — a non-zero skip count means the database was down and the run proves nothing. **Never `uv run ruff format`** |
> | #1 #8 | none — documentation | `frontend-code-reviewer` (#1), `code-reviewer` (#8) | no code gate; see each task's Success Criteria |

> **Ordering is a business rule, not a preference** (`TRUTH.md` Narrative). Tasks #1–#3 are the
> guardrails; no UI fix (#4–#7) may start until all three are Done. #8 and #9 are outside that
> rule and may run at any time — see `ARCHITECTURE.md` §10, Phases R and B.

> **`npm run build` and `frontend/package.json` are NOT touched by any task.** The postbuild
> bundle assertion that once required them was withdrawn with the `/styleguide` page
> (`ARCHITECTURE.md` §6). A task that edits either has gone out of scope.

---

## Task 1: Write the rules down — `SCREENS.md` §Foundations and the three agent artifacts
- **Description**: The written half of the guardrails, per `ARCHITECTURE.md` §9 and `DESIGN.md` §2 and §14. Add to `docs/ui/SCREENS.md` §Foundations: a **§Interaction states** subsection (cursor, hover, focus-visible, active, disabled specified for every interactive element; only shared components may be interactive), a **§Proportion and containers** subsection (the named containers are the only layout widths; a card sizes to its content, never to its column), a **type-scale table** stating the raw framework sizes are not part of the scale, and a line in §Building rules pointing at the four lint rules as the enforcement. Then apply the **twelve** amendments in `DESIGN.md` §14.1–§14.12 — these are sections this feature deliberately overturns, including §14.9 (the nav is centred, permanently), §14.11 (strike the stale `400`/`401` open question) and §14.12 (the `/login` title is `Sign in`). Finally update the three agent artifacts in `ARCHITECTURE.md` §9's table: `frontend-conventions/SKILL.md`, `frontend-code-reviewer.md` (the Foundations checklist, including that a reviewer never widens an exemption to make a gate pass), and `frontend-design-agent.md` (a rendered preview is mandatory; ASCII alone is no longer an approvable design). Reference `docs/ui/SCREENS.md` **by section and quoted phrase, never by line number** — DMI-107's `:1478` / `:1493` citations are already stale.
- **Absorbed**: `ARCHITECTURE.md` §10's G1 and G6 are one task. Both are pure documentation, neither can carry a test, and both are the same act — writing down the rules the later tasks are built and reviewed under. Splitting them costs a second coder→tester→reviewer cycle to land prose.
- **Dependencies**: —
- **Target Files**: [`docs/ui/SCREENS.md`, `.claude/skills/frontend-conventions/SKILL.md`, `.claude/agents/frontend-code-reviewer.md`, `.claude/agents/frontend-design-agent.md`]
- **Tests**: **None, and this is the justified exception.** The deliverable is prose read by humans and agents; no artifact executes. The reviewer gates on the Success Criteria below, not on a suite. Do not invent a test that asserts a prompt.
- **Success Criteria**:
  1. `grep -c cursor docs/ui/SCREENS.md` is **non-zero** — it is currently 0 across 1630 lines, which is the measured gap `TRUTH.md`'s narrative names.
  2. §Foundations contains both new subsections and the type-scale table, and the type-scale table lists the named tokens and states the raw framework sizes are excluded.
  3. All **twelve** `DESIGN.md` §14 amendments are applied. §LOGIN's title row reads `Sign in`; its network-error row still reads `Couldn't reach Dmitri. Try again in a moment.` and is **not** changed.
  4. §SETTINGS no longer lists the `400`/`401` question as open (§14.11).
  5. `frontend-code-reviewer.md` names all four `local/*` rules, their exemption globs, and the never-widen-an-exemption rule.
  6. `frontend-design-agent.md` requires a rendered preview built from the real tokens and typefaces, and states `TRUTH.md` rule 13 — the visual check is performed by the human.
  7. No line-number citations of `SCREENS.md` are introduced anywhere.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: `Disclosure` component, built complete, and `Settings` adopts it
- **Description**: Add `frontend/src/components/Disclosure.tsx` per `ARCHITECTURE.md` §7.5 and `DESIGN.md` §8, and replace the bare `<button>` at `frontend/src/pages/Settings.tsx:212` with it. Built on Radix `Collapsible` (`radix-ui`, already a dependency), so `Collapsible.Trigger` is a component and needs no lint exemption. **Path is `components/`, not `components/ui/`** — that exemption is for vendored shadcn source only, and our own new interactive component must not be the one piece of the product the new rules never check. Props: `label: string`, `children: ReactNode`, `testId: string`, `defaultOpen?: boolean`. **Built complete on first write** — every interactive state in §7.5's table is delivered now: `cursor-pointer` (Tailwind v4 preflight sets `cursor: default` on `<button>`, which is exactly why the current control affords nothing), `hover:underline hover:text-foreground`, `focus-visible:ring-3 focus-visible:ring-ring/50 outline-none`, `active:translate-y-px`, and caret rotation via `group-data-[state=open]:rotate-90` on a `lucide-react` `ChevronRight`. No disabled state — a disclosure is never permission-gated. The `data-testid` `settings-activity-info` is **renamed** to `settings-activity-disclosure` per `DESIGN.md` §13; the caret gains `settings-activity-caret`. This task runs **before** the lint rules so that when `local/no-bare-interactive` is enabled in Task 3 it finds zero violations and no commit is ever knowingly red (`TRUTH.md` rule 9).
- **Dependencies**: Task 1
- **Target Files**: [`frontend/src/components/Disclosure.tsx`, `frontend/src/components/Disclosure.test.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Settings.test.tsx`]
- **Tests**: `frontend/src/components/Disclosure.test.tsx` (new) — mirror `ConfirmByTyping.test.tsx`. Proves: collapsed by default; click and `{Enter}`/`{Space}` each flip `aria-expanded`; the note is `aria-controls`-linked and revealed on expand; the trigger carries `cursor-pointer` and `hover:underline`. `Settings.test.tsx` is updated for the renamed testid — the rename is deliberate and is called out so it is not discovered in a red run.
- **Success Criteria**:
  1. `frontend/src/components/Disclosure.tsx` exists. **It is not under `components/ui/`.**
  2. Every state in `ARCHITECTURE.md` §7.5's table is present in the source: pointer cursor, hover underline **and** foreground colour, focus-visible ring, active translate, caret rotation.
  3. `grep -n '<button' frontend/src/pages/Settings.tsx` returns **nothing**.
  4. `Disclosure.test.tsx` covers keyboard activation by both `{Enter}` and `{Space}`, not click alone — AC "Disclosure works by keyboard".
  5. The focus ring is intact while expanded — AC "Disclosure caret".
  6. No new dependency is added to `frontend/package.json`.
  7. The full frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: The four lint rules, the container tokens, and clearing all 33 violations
- **Description**: The enforcement half of the guardrails, per `ARCHITECTURE.md` §3, §4 and §5. Write four local ESLint rule modules under `frontend/eslint-rules/` over one shared tokenizer, register them as an **inline plugin object** in `frontend/eslint.config.js` (flat config accepts one; **no dependency is installed**), and clear every violation they find **in the same commit** (`TRUTH.md` rule 9). `no-restricted-syntax` was evaluated and rejected — see §3.1; do not substitute it. The shared tokenizer `class-strings.js` is the whole false-positive defence: a node is an authored class string only inside a `className` JSX attribute or a `cn`/`clsx`/`twMerge`/`cva` call, and each token is split on `:` **only at bracket depth 0**, judging the **last** segment. That is what keeps `has-data-[icon=inline-end]:pr-2` and `group-data-[state=open]:rotate-90` from being mistaken for arbitrary values, and keeps `data-testid`, `aria-describedby` and `lib/copy.ts` invisible to the rules. Exemptions are **exactly** `TRUTH.md` rule 8 and nothing more: `src/components/ui/**` (vendored), `src/**/*.test.{ts,tsx}`, `src/test/**`. `frontend/eslint-rules/` sits outside `src/`, so it is outside both `eslint src` and `prettier --check src` — **do not widen either script**; a wider `prettier --check` is a repo-wide formatter run by another name.
- **Absorbed**: (a) **`ARCHITECTURE.md` §10's G2, the `index.css` tokens** — three config constants with no branching, untestable alone, merged into their first consumer, which is the width clearing in this same task. (b) **U2 and U3 in full**, and the width third of U1 — `ARCHITECTURE.md` §5 requires the three `max-w-[45rem]` values land at their **final** widths here, because clearing them to an interim value first would be temporary code, which `.claude/CLAUDE.md` forbids. `AppShell` therefore reaches 1120px and `AuthShell` reaches 384px in this task, which is why two UI acceptance criteria are gated here rather than in Phase U.
- **Dependencies**: Task 1, Task 2
- **Target Files**: [`frontend/eslint-rules/index.js`, `frontend/eslint-rules/class-strings.js`, `frontend/eslint-rules/no-arbitrary-utility.js`, `frontend/eslint-rules/no-raw-type-size.js`, `frontend/eslint-rules/spacing-scale.js`, `frontend/eslint-rules/no-bare-interactive.js`, `frontend/eslint-rules/no-arbitrary-utility.test.js`, `frontend/eslint-rules/no-raw-type-size.test.js`, `frontend/eslint-rules/spacing-scale.test.js`, `frontend/eslint-rules/no-bare-interactive.test.js`, `frontend/eslint.config.js`, `frontend/src/index.css`, `frontend/src/components/TopBar.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/components/AuthShell.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/ForgotPassword.tsx`, `frontend/src/pages/ResetPassword.tsx`, `frontend/src/pages/AcceptInvite.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/components/TopBar.test.tsx`]
- **Tests**: Four `RuleTester` suites, one per rule, run by Vitest — `frontend/vitest.config.ts` sets no `include`, so its default glob already picks up `eslint-rules/*.test.js`. **Do not add a projects/workspace split for four rule tests.** Each suite carries the must-report and must-**not**-report cases in `ARCHITECTURE.md` §12.1's table verbatim. `spacing-scale.test.js` is the **only** proof for the AC "Off-scale spacing rejected" — the tree has zero spacing violations, so a fixture is the sole evidence.
- **Success Criteria**:
  1. `npm run lint` exits **zero** on the whole tree, having cleared all **33** pre-existing violations: 29 raw type sizes, 3 arbitrary widths, and the 1 native control (already gone in Task 2).
  2. The 29 `text-sm` become `text-body-md` across the 5 pages in `ARCHITECTURE.md` §3.4's table. **Computed font size is unchanged at 14px** — AC "Type-token swap is invisible".
  3. **The arithmetic holds: 35 raw sizes exist, 29 are cleared, 6 remain inside `components/ui/`.** This proves the exemption scope is right rather than convenient. If a rule fires somewhere unexpected, fix the tokenizer or the code — **never the glob**.
  4. `--container-frame: 70rem`, `--container-form: 24rem` and `--text-nav: 0.6875rem` are declared **inside the existing `@theme inline` block**, none in `:root`. A `:root`-only custom property registers in no theme namespace and generates **no utility** — `max-w-frame` would silently do nothing.
  5. **`--container-prose` is not declared.** Tailwind resolves `max-w-*` from `--max-width-*` before `--container-*`, and it ships `--max-width-prose: 65ch`; declaring `--container-prose` would emit no working max-width utility and an implementer writing `max-w-prose` would silently get 546px. If a narrower column ever returns it comes back as `--container-page` or `--max-width-prose-col`.
  6. `AppShell` is `max-w-frame` — AC "Content column matches the bar". `AuthShell` is `max-w-form` — AC "Sign-in card proportion", 384px. `TopBar`'s frame is `max-w-frame`.
  7. **The nine existing `max-w-prose` call sites are untouched**, including `Settings.tsx:227,244`. They bind at 65ch and are a reading measure, not a layout container.
  8. Each rule's message is the one specified: `no-raw-type-size` names the replacement token (`text-sm` → "Use `text-body-md` (same 14px)") and says so explicitly when no token matches.
  9. `<a>` is **not** reported by `no-bare-interactive` — deliberate, per §3.6.
  10. `frontend/package.json` gains **no dependency**, and its `build` script is not touched.
  11. The full frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 4: Top bar — one frame, permanently centred navigation
- **Description**: Per `ARCHITECTURE.md` §7.1 and `DESIGN.md` §4. The bar row becomes a **three-column grid, `grid grid-cols-[1fr_auto_1fr]`**, with three direct children: the wordmark (`justify-self-start`), the `<nav>` (`justify-self-center`) and `Log out` (`justify-self-end`). **Remove the existing wrapper that groups the wordmark with the nav** — they are now siblings in different columns. `navLinkClass` changes `text-body-md` → `text-nav` (11px). The nav's own inter-item gap stays `gap-4` (16px). The wordmark stays `font-title text-title-xs` — already correct, do not touch it. Horizontal padding stays `px-4`. **Do not centre the nav with `justify-between` or `mx-auto` in a flex row**: either centres it in the space the wordmark and button leave over, so it drifts whenever `Log out` changes width or `Users` appears for an admin and vanishes for a viewer. The grid pins it to the frame's true centre. Centring is the **standing default for all future destinations**, not a treatment for the current item count — `docs/ui/SCREENS.md` §App shell reverted centring on 2026-08-07 and Task 1 reverses that reversal with this different justification.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/components/TopBar.tsx`, `frontend/src/components/TopBar.test.tsx`]
- **Tests**: `TopBar.test.tsx` (touch) — nav links carry `text-nav`; the frame carries `max-w-frame`; the wordmark keeps `text-title-xs`.
- **Success Criteria**:
  1. Nav items compute to **11px** and the wordmark to **16px** in the title face — ACs "Top bar proportion" and "Wordmark unchanged".
  2. The nav is centred **on the bar**, via the `1fr auto 1fr` grid — AC "Top bar proportion".
  3. Rendering with a fourth destination leaves the nav still centred and items not pushed left — AC "Navigation stays centred as it grows".
  4. **No `gap-8` anywhere in this file.** The wordmark→nav distance is emergent under a centred nav, not a specified measurement — a test asserting a fixed value there asserts something the layout no longer promises. `TRUTH.md`'s original 32px criterion was replaced for exactly this reason.
  5. `Users` stays **absent** for viewers rather than disabled; `Log out` stays a `ghost` button; the active-item treatment is untouched.
  6. The full frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 3

## Task 5: `Ornament` becomes a vector lozenge rule
- **Description**: Per `STRUCTURAL_REEVAL.md`, `ARCHITECTURE.md` §§7.3–7.4 and
  `DESIGN.md` §5.6. The human approved the three-SVG amendment on 2026-08-22.
  Implement one `data-testid="ornament"` and `aria-hidden` flex row with
  `w-full items-center gap-2 text-muted-foreground`; two `h-px flex-1` rule SVGs with
  `viewBox="0 0 1 1"`, `preserveAspectRatio="none"`, `focusable="false"` and a
  `1 × 1 currentColor` rectangle; and one fixed `size-3 shrink-0` lozenge SVG
  with `viewBox="0 0 12 12"`, `focusable="false"`, no aspect-ratio override and
  one `currentColor` diamond path. No child has a title or role. `AuthShell`
  groups the wordmark and mark in a tokenized `w-full px-6` wrapper with
  `gap-2`; the outer `gap-4` separates the group from the card. The filled
  vector lozenge stays between two hairline rule segments, sizes by its
  container, and uses no Unicode ornament glyph.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/components/Ornament.tsx`,
  `frontend/src/components/Ornament.test.tsx`, `frontend/src/components/AuthShell.tsx`,
  `.claude/docs/frontend/screens.md`]. One implementation owner owns the complete
  four-file patch and runs targeted Prettier on the three frontend files. The code-map
  change replaces only the stale Unicode Ornament row with full-width vector-lozenge
  text. `frontend/src/pages/Home.tsx` and `frontend/src/pages/home/**` remain outside
  the file fence.
- **Tests**: `frontend/src/components/Ornament.test.tsx` — mirror
  `Timestamp.test.tsx`. Prove the root's `data-testid`, hidden, `w-full` and muted
  flex contract; exactly three direct vectors in rule/lozenge/rule order; both rules'
  class, view box, non-uniform aspect ratio, focusability and `1 × 1 currentColor`
  rectangle; the lozenge's fixed class, view box, default aspect ratio, focusability
  and `currentColor` path; no title or role; and no rendered `'\u2766'`. Use that
  escaped string literal, not a literal glyph or `String.fromCodePoint`.
- **Success Criteria**:
  1. DESIGN, ARCHITECTURE and this task state the same approved three-SVG
     contract.
  2. The mark is inline vector artwork, the code-map Ornament row describes the
     full-width vector lozenge without a glyph, and a literal repository search for
     `❦` returns no match outside `specs/` — AC "Mark is a vector".
  3. **Neither Home file is edited.** Both existing call sites inherit the same
     no-prop component.
  4. The Ornament root explicitly carries `w-full`, so the auth mark fills the 336px
     card-content measure with `gap-2` inside the brand group and `gap-4` before the
     card. On Home it fills the existing parent content box. The lozenge stays square
     while only the rules stretch.
  5. The implementation owner runs targeted Prettier on the three frontend target files; no
     hand-format pass substitutes for formatter output.
  6. One reviewer confirms the file fence and literal-source search, then the exact
     frontend gate passes:
     `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build`.
  7. The reviewer inspects the real auth and Home surfaces for visible hairlines,
     auth alignment/rhythm and an undistorted lozenge. A jsdom geometry stub is not a
     substitute.
- **Status**: COMPLETED
- **Review Rejections**: 1
- **Structural Re-evaluation**:
  [`STRUCTURAL_REEVAL.md`](STRUCTURAL_REEVAL.md) — three-SVG amendment approved
  by the human on 2026-08-22. Rejection 1 after reset found the missing root
  `w-full` and the stale glyph entry in `.claude/docs/frontend/screens.md`.

## Task 6: `/settings` reordered — identity first, password behind a modal
- **Description**: Per `ARCHITECTURE.md` §7.6 and §7.7 and `DESIGN.md` §6 and §7. `Settings.tsx` becomes a composer with four sections in this order: **Your details** (new `pages/settings/AccountDetails.tsx`, read-only, renders `user.email` and `user.role` from `useSession()`), **Change your password** (a `Button` trigger opening the modal), **Activity** (heading on its own line above the `Disclosure` row from Task 2), **Leave this organization** (unchanged). The entire password form moves into new `pages/settings/PasswordDialog.tsx`: the three `Input`/`Label` pairs, the three field-level error regions, the form-level error region, the submit button, the success region, and `handleSubmit` with its `wrong_current_password` / `password_policy_violation` branches — **behaviour preserved verbatim, only the container changes**. **`DialogShell` already exists** at `frontend/src/components/DialogShell.tsx` with `size` variants, `locked`, `initialFocusRef` and focus restoration, and `ConfirmByTyping` already consumes it. DMI-107's wording "a shared modal shell extracted from `ConfirmByTyping`" is **stale** — that extraction already landed. **Do not write a new shell and do not re-extract one.** Use `<DialogShell size="sm">` (384px, the right measure for a three-field form) and mirror `pages/users/InviteDialog.tsx`. `autoFocus` is removed from what becomes the modal's first field and **nothing replaces it** — no field is focused on page load. Error regions stay **always rendered and empty when clean**; a conditionally-mounted live region is never announced. Wrong current password is **`400`**, not `401`, and always was — the frontend already branches on it correctly at `Settings.tsx:65`; nothing about that changes.
- **Dependencies**: Task 2, Task 3
- **Target Files**: [`frontend/src/pages/Settings.tsx`, `frontend/src/pages/settings/AccountDetails.tsx`, `frontend/src/pages/settings/PasswordDialog.tsx`, `frontend/src/pages/Settings.test.tsx`, `frontend/src/App.test.tsx`]
- **Tests**: `Settings.test.tsx` (touch) — on load, email and role are visible with no interaction and `document.activeElement` is `document.body`; sections appear in the order details → password → activity → leave; the change-password trigger opens a dialog containing all three fields; dismissing it returns focus to the trigger. **Every existing leave-organization case must survive unchanged.**
- **Success Criteria**:
  1. Signed-in email and role are visible without any interaction, and **no field has focus** — AC "Identity is visible first".
  2. Sections read: your details → change-password trigger → activity → leaving the organization — AC "Settings order".
  3. Activating the change-password control opens a modal containing all three password fields — AC "Password form is behind a trigger".
  4. Dismissing the modal returns focus to the control that opened it — AC "Focus returns". This uses `DialogShell`'s existing `onCloseAutoFocus`; **nothing new is written for it**.
  5. **`frontend/src/components/DialogShell.tsx` and `frontend/src/components/ConfirmByTyping.tsx` are NOT modified.** The leave-organization confirmation behaves identically to before — AC "Existing confirmation unchanged".
  6. The Activity heading is on its own line above the disclosure row — AC "Activity heading".
  7. "Your details" is **read-only** — no display-name editing, no self-profile update call. Open question C3 stays open.
  8. `Settings.tsx:227,244`'s two `max-w-prose` usages are **kept exactly as they are**.
  9. The full frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 3

## Task 7: `/login` uses the shared network-error string
- **Description**: Per `ARCHITECTURE.md` §7.8 and `DESIGN.md` §10. `frontend/src/lib/copy.ts:13` already exports `SERVICE_ERROR = "Couldn't reach Dmitri. Try again in a moment."` — the exact `SCREENS.md` §LOGIN string — and `Settings.tsx`, `AcceptInvite.tsx`, `ResetPassword.tsx` and `ForgotPassword.tsx` all import it. `Login.tsx:58` is the only call site that hardcodes a different string. Add `SERVICE_ERROR` to the existing `@/lib/copy` import and use it. **No new string is written and `lib/copy.ts` is not touched** — this is a call site joining the four that were already right. Classified as a **violation**, not a contradiction, under `TRUTH.md` rules 14–15: the specification was right and one call site broke it, so no amendment is needed. The title at `Login.tsx:86` is **not** touched — that half was a contradiction, resolved in the code's favour, and `SCREENS.md` §LOGIN is amended in Task 1 instead.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/pages/Login.tsx`, `frontend/src/pages/Login.test.tsx`]
- **Tests**: `Login.test.tsx` (touch) — **line 159 currently asserts the hardcoded literal, so the source change alone turns the suite red.** The assertion must reference the imported `SERVICE_ERROR`, **not a second copy of the string** — a test that repeats the literal is how the two drifted apart in the first place.
- **Success Criteria**:
  1. The sign-in network error shows the shared string, read from the one shared constant — AC "One network-error string, not two".
  2. `grep -n "reach the server" frontend/src/` returns **nothing**.
  3. `frontend/src/lib/copy.ts` is **not modified**.
  4. `Login.tsx:86`'s title still reads `Sign in`.
  5. `Login.test.tsx` asserts the imported constant, not a repeated literal.
  6. The full frontend gate passes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: The `remediate` skill — feedback becomes classified work
- **Description**: New `.claude/skills/remediate/SKILL.md`, per `ARCHITECTURE.md` §9 and §12.5. It turns free-text human feedback into pipeline work. Per item it classifies: **violation** — the specification was right and the code broke it → write a task directly; or **contradiction** — the specification itself must change → write a proposed amendment against the feature's `TRUTH.md` / `DESIGN.md` and **stop at a human approval gate**. No task is written for a contradiction until the amendment is approved (`TRUTH.md` rule 15). Structure mirrors `.claude/skills/refine-specs/` — `SKILL.md` only, no `REFERENCE.md`. **This task is deliberately outside the guardrails-before-fixes ordering rule** (`ARCHITECTURE.md` §10, Phase R): the skill acts on work already shipped, and nothing in the four UI defects touches it, so blocking five visible fixes behind it would apply the rule where its reason does not reach.
- **Dependencies**: —
- **Tests**: **None, and this is the second justified exception.** The deliverable is an agent workflow, not code; no artifact executes. But untestable is not unprovable — the proof is the two worked examples below, checked against a known answer, plus the human walkthrough in criterion 4.
- **Target Files**: [`.claude/skills/remediate/SKILL.md`]
- **Success Criteria**:
  1. The skill states the classification test as **one question a reader can apply**: *does the specification already require this behaviour, or does it explicitly decide otherwise?*
  2. It carries **both** worked examples in full — input feedback, cited section, classification, output:
     - *"the activity disclosure does not look clickable"* → cites `TRUTH.md` business rule 1 → **violation** → a task, written directly, no approval step.
     - *"the navigation should be centred on the bar"* → cites `docs/ui/SCREENS.md` §App shell, which decided left-adjacent on 2026-08-07 → **contradiction** → a written amendment naming §App shell and what it would change, then **stop**. The second is not hypothetical: it is what happened on 2026-08-21, and `DESIGN.md` §14.9 is the amendment it should have produced. That is what makes it checkable.
  3. The gate wording names the **target document and section** and states **what would change** before asking for approval. An amendment nobody can review is not a gate.
  4. A human walks both examples through the skill at review and confirms the classification. **Accepted on 2026-08-22:** the operator confirmed both outputs — activity disclosure → violation → direct task; centred navigation → contradiction → named amendment and stop before task creation.
  5. No `REFERENCE.md` is created.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Backend — the CORS allowlist fails closed
- **Description**: Per `ARCHITECTURE.md` §8. `backend/src/api/core/config.py:54-57`'s `cors_allowed_origins` default becomes `""` (empty), with a comment recording why: the previous default trusted a developer workstation and a placeholder domain nobody owns, which — combined with `allow_credentials=True` — made a missing environment variable a silent exposure. **`backend/src/api/middleware.py` needs no change**: `build_cors_middleware_kwargs` already filters empty entries, so `""` yields `allow_origins: []` and Starlette emits no `access-control-allow-origin` header for any origin. **The load-bearing detail:** `backend/tests/conftest.py` sets `env_file = None` and never sets `CORS_ALLOWED_ORIGINS`, so `test_cors_headers.py` and `test_auth_wiring.py` pass today **only because the default trusts `http://localhost:5173`**. The fix is not to weaken the default — it is for the suite to configure the origin it asserts on, exactly as it already does for `JWT_SIGNING_SECRET`: add `os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")` beside the existing calls and **before** `from api.core.config import Settings`. This strengthens the tests: they now assert against an origin they set, rather than a production default that happened to include a laptop. Option 1 (a required field with no default) was rejected — `Settings()` is constructed with only `DATABASE_URL` and `JWT_SIGNING_SECRET` in `conftest.py`, and a required field makes every such construction raise, for no additional safety. **Independent of both other phases; may run at any time.**
- **Dependencies**: —
- **Target Files**: [`backend/src/api/core/config.py`, `backend/tests/conftest.py`, `backend/tests/test_settings.py`, `backend/tests/test_middleware.py`, `backend/tests/test_cors_headers.py`, `backend/.env.example`]
- **Tests**: `test_settings.py` — `Settings().cors_allowed_origins == ""` when unset, replacing the current line-142 assertion. `test_middleware.py` — a new case proving `build_cors_middleware_kwargs(Settings(CORS_ALLOWED_ORIGINS=""))["allow_origins"] == []`; this is the fail-closed proof. `test_cors_headers.py` — a new case: a preflight with `Origin: http://localhost:9999` returns **no** `access-control-allow-origin` header; the existing three cases keep asserting 204 with no body headers. `test_auth_wiring.py` is **untouched and must keep passing** on the `conftest.py` fixture.
- **Success Criteria**:
  1. With no allowed-origins configuration the API permits **no** origin at all — never a developer workstation — AC "Fails closed when absent".
  2. A preflight from a foreign origin carries no allow-origin header — AC "Foreign origin refused".
  3. A preflight from the configured origin still returns **204 with no body headers** — AC "Configured origin served"; the existing preflight behaviour does not regress.
  4. **No host the team does not control appears in any default** — AC "Placeholder host gone".
  5. **`backend/src/api/middleware.py` is NOT modified**, and `NoContentCorsMiddleware` is left alone.
  6. **`contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts`, `docs/adr/ADR-005-security-model.md` and `specs/014-frontend-scaffold/ARCHITECTURE.md` are NOT touched**, even though the placeholder host also appears in them. A documented example server URL is not a default that grants trust; the ADR and the old spec are historical records.
  7. `./database.sh` first, then `uv run ruff check src tests` and `uv run pytest` both pass — **665 passed / 0 skipped**. A non-zero database-test skip count means the database was down and the run proves nothing; re-run or say so. **Never `uv run ruff format`.**
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
  #1 ──▶ #2 ──▶ #3 ──┬──▶ #4   TopBar
  docs   Disclosure  │        (grid, text-nav)
         rules       ├──▶ #5   Ornament
                     │
                     ├──▶ #6   Settings   (also needs #2)
                     │
                     └──▶ #7   Login copy

  #8  remediate skill   — independent, no dependents (Phase R)
  #9  backend CORS      — independent, no dependents (Phase B)
```

**The guardrail fence:** #1, #2 and #3 are the guardrails. No UI fix (#4–#7) may start until all
three are Done — `TRUTH.md` Narrative, "ordering is a rule, not a preference". #8 and #9 sit
outside that fence by the scoping decision recorded there and in `ARCHITECTURE.md` §10.

**Why #2 precedes #3**, inverting `ARCHITECTURE.md` §10's G3→G5 edge: `local/no-bare-interactive`
fires on `Settings.tsx:212`, so the rule cannot be enabled while the bare button is still there
without a knowingly-red commit (`TRUTH.md` rule 9). Building `Disclosure` first means the rule
finds zero violations the moment it lands. `Disclosure` needs none of the new tokens, so nothing
blocks it.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Write the rules down — `SCREENS.md` §Foundations and the three agent artifacts | PENDING |
| 2 | `Disclosure` component, built complete, and `Settings` adopts it | PENDING |
| 3 | The four lint rules, the container tokens, and clearing all 33 violations | PENDING |
| 4 | Top bar — one frame, permanently centred navigation | PENDING |
| 5 | `Ornament` becomes a vector lozenge rule | IN_PROGRESS |
| 6 | `/settings` reordered — identity first, password behind a modal | PENDING |
| 7 | `/login` uses the shared network-error string | PENDING |
| 8 | The `remediate` skill — feedback becomes classified work | PENDING |
| 9 | Backend — the CORS allowlist fails closed | PENDING |
