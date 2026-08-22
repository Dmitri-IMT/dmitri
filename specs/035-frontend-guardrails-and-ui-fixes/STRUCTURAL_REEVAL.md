# Structural re-evaluation — Task 5 `Ornament`

> **Decision recorded 2026-08-22:** the human approved the three-SVG amendment. Task 5 is `IN_PROGRESS`; **Review Rejections** is **1** in the reset execution cycle.

## 1. Symptom

Task 5 reached four reviewer rejections without changing its product intent. Every rejection stopped at `npm run format:check` in `frontend/src/components/Ornament.test.tsx`; the first also found formatting in `Ornament.tsx` and a literal forbidden glyph in the test source.

| Review | Reviewer evidence | Remediation outcome |
| --- | --- | --- |
| 1 | Prettier rejected both Task 5 files. The test also contained a literal `❦`, contrary to the source-search invariant. Lint, typecheck, 332 tests and build otherwise passed. | The component was hand-formatted. A separate test owner replaced the literal with `\u2766` and hand-formatted the test. |
| 2 | The exact gate still stopped at `format:check` on `Ornament.test.tsx`. Typecheck, 332 tests and build passed when run separately. | Another test owner tried to reproduce Prettier output by inspection. |
| 3 | `format:check` still rejected the test. The reviewer captured Prettier's canonical output: it preserves `'\u2766'` and collapses the rule rectangle's `fill` assertion to one line. | The next fix changed `'\u2766'` to `String.fromCodePoint(0x2766)` even though the rejection was the remaining multiline assertion. |
| 4 | The same multiline `toHaveAttribute('fill', 'currentColor')` assertion still failed `format:check`. | Structural re-evaluation triggered; no further code change is allowed yet. |

**Post-approval rejection 1:** the real `/login` surface showed that the Ornament root
shrink-wrapped its children because the contract did not explicitly require `w-full`; the
approved 336px auth measure and Home width inheritance therefore did not hold. The same
review's literal source search found the stale glyph in
`.claude/docs/frontend/screens.md`. These are contract-fence omissions, not a change to the
approved vector design.

The production component present at re-evaluation time was already a three-SVG vector lozenge rule. Its test exercised that structure and had no literal forbidden glyph, but still contained the rejected multiline assertion. Approval selects the structure; it does not waive the remaining implementation, formatter, test or visual gates.

## 2. Root cause

### 2.1 True design/specification issue

`DESIGN.md` §5.6 and `ARCHITECTURE.md` §7.4 described different implementations before Task 5 started:

- DESIGN specified one SVG without a `viewBox`, a fixed 11px lozenge, and a paper-coloured knockout.
- ARCHITECTURE and TASKS specified a flex row of three SVGs, a tokenized 12px lozenge, and two real `gap-2` breaks.
- DESIGN retained the operator-reviewed 336px auth content measure, `gap-2` wordmark-to-mark rhythm, `gap-4` brand-group-to-card rhythm and muted colour. ARCHITECTURE/TASKS omitted those requirements and scoped Task 5 away from `AuthShell.tsx`.

This is a material structural contradiction. None of the four reviews found or resolved it: all four rejected formatting/process defects before a visual or design-contract review. Review silence therefore cannot be treated as approval of either geometry.

The invariant that does **not** change is the intended visual design: a filled vector lozenge centred between two hairline rule segments, decorative and sized by its container, with no Unicode ornament glyph. `TRUTH.md` and `SCREENS.md` remain valid.

`DESIGN.md` §5.6 now carries the approved three-SVG amendment. It preserves the operator-reviewed auth measure, rhythm and colour while replacing only the conflicting SVG composition.

### 2.2 Process and decomposition failure

The four review cycles were not caused by an architectural difficulty in SVG rendering. They were caused by the work contract:

1. Source and test work had separate owners, so no single owner was accountable for the complete formatter-ready patch.
2. Remediation agents were forbidden to run the formatter and guessed its output by inspection.
3. The review finding was not converted into an exact, closed fix list. Review 3 supplied canonical output, but the next fix changed the escape expression instead of the reported multiline assertion.
4. The source-search invariant and the behavioral test were treated as competing requirements. They are compatible: the test can assert `'\u2766'`; the captured Prettier output proves that Prettier preserves this escape while a literal source search does not match it.
5. Review was repeatedly restarted before the previous formatter finding was demonstrated closed.

This is a decomposition and verification failure. Adding another abstraction, test helper, Unicode conversion call, or review agent would not fix it.

## 3. Revised plan

### 3.1 Decision recorded

On 2026-08-22, the human selected **APPROVE THREE-SVG AMENDMENT**. The authoritative
branch is the three-SVG contract below plus the missing auth measure/rhythm work. The
earlier single-SVG, 11px, paper-knockout alternative is rejected. No hybrid is allowed.

### 3.2 One implementation owner

With approval recorded, one implementation owner owns the complete Task 5 patch. Do not split source formatting, test formatting, or rejection remediation across agents.

For the approved three-SVG branch, the exact file fence is:

- `frontend/src/components/Ornament.tsx`
- `frontend/src/components/Ornament.test.tsx`
- `frontend/src/components/AuthShell.tsx`
- `.claude/docs/frontend/screens.md` — replace only the stale Unicode Ornament row with
  full-width vector-lozenge text and no literal glyph.

`frontend/src/pages/Home.tsx` and `frontend/src/pages/home/**` remain untouched. They inherit the shared component.

The owner applies the approved code, test and code-map changes, then runs targeted Prettier on only the three frontend files:

```text
npm exec prettier -- --write src/components/Ornament.tsx src/components/Ornament.test.tsx src/components/AuthShell.tsx
```

No hand-format pass substitutes for this command. This is targeted formatting, not a repository-wide formatter run.

### 3.3 Exact approved three-SVG contract

The approved contract is:

- `AuthShell` keeps its 384px `max-w-form` column and card.
- A tokenized `w-full px-6` brand wrapper groups the wordmark and `Ornament` with `gap-2`; the existing outer `gap-4` separates that group from the card. At the desktop measure, the mark is 336px wide and aligns with the card's content edges.
- `Ornament` takes no props and carries no outer margin.
- Its root has `data-testid="ornament"` and is an `aria-hidden="true"` flex row with `w-full items-center gap-2 text-muted-foreground`. `w-full` is explicit because an auto-width flex item shrink-wraps its children instead of consuming the measure supplied by AuthShell or Home.
- Direct children are rule SVG, lozenge SVG, rule SVG, in that order.
- Each rule SVG is `h-px flex-1`, has `viewBox="0 0 1 1"`, `preserveAspectRatio="none"`, `focusable="false"`, and one `1 × 1` rectangle filled with `currentColor`.
- The lozenge SVG is `size-3 shrink-0`, has `viewBox="0 0 12 12"` and `focusable="false"`, omits `preserveAspectRatio`, and contains one diamond path filled with `currentColor`.
- No child has a title or role. The real flex gaps replace the paper knockout, so the component has no paper-only constraint.
- On Home, the component fills the existing parent content box without a prop or call-site edit. Only the rule lengths respond to width; the lozenge does not distort.

### 3.4 Exact test and source-search contract

`Ornament.test.tsx` must prove the approved observable/structural contract without adding another helper:

1. root `data-testid="ornament"`, `aria-hidden="true"`, `w-full` and muted flex-row classes;
2. exactly three direct SVG children in rule/lozenge/rule order;
3. both rule SVG class, view-box, aspect-ratio, focusability, rectangle geometry and `currentColor` fill;
4. lozenge class, view-box, default aspect-ratio behavior, focusability, one path and `currentColor` fill;
5. no title or role; and
6. rendered text does not contain `'\u2766'`.

The assertion uses the escaped string literal `'\u2766'`, not a literal glyph and not `String.fromCodePoint`. This is behaviorally exact, satisfies the literal source search, and avoids an unnecessary runtime conversion. Targeted Prettier is authoritative for line wrapping.

A literal repo search for `❦` must return no match outside `specs/`. The specifications may name the removed glyph to state the invariant. The target fence includes `.claude/docs/frontend/screens.md`, whose stale glyph row must become full-width vector-lozenge text without reproducing the glyph.

## 4. Reviewer gate

One reviewer reviews the complete patch only after the implementation owner reports targeted formatting complete.

Approval requires all of the following, in order:

1. the recorded approval is present and ARCHITECTURE, DESIGN and Task 5 name the same three-SVG contract;
2. the diff is limited to the three frontend target files plus `.claude/docs/frontend/screens.md`, and does not touch either Home call site;
3. the literal `❦` source search has no match outside `specs/`;
4. from `frontend/`, the exact chained gate passes:
   `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build`;
5. the reviewer inspects the real auth and Home surfaces: the hairlines are visible, the lozenge stays square, the auth rule aligns to the 336px card-content measure, the two auth rhythm steps read correctly, and Home inherits the same mark without a call-site edit.

A failed formatter check is one closed finding: the implementation owner applies the formatter's exact output and demonstrates `format:check` passes before review restarts. No unrelated expression change is accepted as remediation.

## 5. Exact spec changes and decision record

This re-evaluation requires these spec changes:

- `DESIGN.md` §§5.5–5.6: uses the tokenized brand wrapper, requires the Ornament row to
  fill that measure with `w-full`, and keeps the approved three-SVG composition,
  operator-reviewed auth measure, rhythm and muted colour authoritative.
- `ARCHITECTURE.md` §§7.3–7.4: records the approved branch, adds `AuthShell` and the
  stale code-map row to Task 5's structural scope, and defines the exact
  DOM/aspect-ratio/accessibility/width contract.
- `ARCHITECTURE.md` §§10–12: keeps U4 executable, updates the target-file table, and
  makes the escaped-literal and `w-full` test assertions exact.
- `TASKS.md` Task 5 and status table: remain `IN_PROGRESS`, record **Review Rejections:
  1**, and use the corrected four-file/test/reviewer contract above.
- `TRUTH.md`: unchanged. Its vector/no-Unicode acceptance criterion is still correct.
- `SCREENS.md`: unchanged. Its lozenge-rule product intent is still correct.

### Human decision recorded

**APPROVE THREE-SVG AMENDMENT — selected 2026-08-22.** The human approved
`DESIGN.md` §5.6's three-SVG composition plus the preserved 336px auth measure,
`gap-2`/`gap-4` rhythm and muted colour. The earlier single-SVG, 11px,
paper-knockout branch is rejected. Task 5 remains `IN_PROGRESS`; **Review
Rejections** is now **1** after the post-approval width/source-search rejection.
Implementation must still satisfy §4 before review approval.
