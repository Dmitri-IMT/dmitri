---
name: remediate
description: >-
  Classifies free-text human feedback as a specification violation or contradiction and returns
  it to the document-driven pipeline. Use when reviewing shipped work, processing product or
  design feedback, or when the user says /remediate, "turn this feedback into work", or
  "classify this feedback".
user-invocable: true
argument-hint: "Feedback and the relevant specs/NNN-feature-slug path"
---

# Remediate feedback (`/remediate`)

Turn feedback about shipped work into specification-backed pipeline work. Process each feedback
item separately. Preserve the operator's words verbatim. Do not implement application code.

## Classification workflow

1. Read the feature's `TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`, and `INTEGRATION.md` when present.
   Read the cited stable document or ADR when it owns the decision. Inspect existing code only to
   establish whether it follows the specification.
2. Cite the controlling document and named section or rule, and quote the decisive phrase. Cite
   `docs/ui/SCREENS.md` by section and phrase, never by line number. Decide from evidence, not taste.
3. Ask one question exactly:

   *Does the specification already require this behaviour, or does it explicitly decide otherwise?*

4. Classify and act:
   - **Violation:** the specification already requires the behaviour and the code breaks it. Write
     a task directly in the active feature's `TASKS.md`; no approval step applies.
   - **Contradiction:** satisfying the feedback would change a specification decision. Draft an
     amendment to the owning `TRUTH.md` or `DESIGN.md`, then stop at the gate below. Write no task.
   - If the specification is silent, do not invent authority. Use the contradiction path because
     the specification must first gain a decision; name the owning section in the proposed addition.

For a direct task, include the verbatim feedback, cited authority, required behaviour, target files,
and observable success criteria in the repository's canonical task shape.

## Contradiction amendment and stop gate

Write the proposal before asking for approval:

- **Feedback:** verbatim input.
- **Target:** exact document and named section or rule.
- **Current decision:** the decisive text and its effect.
- **Proposed amendment:** replacement or addition, including the behaviour that would change.
- **Consequences:** other specification statements or acceptance criteria that must change with it.

Then ask:

> Approve this amendment to `[target document]` `[named section]`, changing `[current behaviour]`
> to `[proposed behaviour]`? Until you approve it, I will not write a task.

**STOP.** Do not write or imply a task, edit application code, or continue the pipeline. After
explicit approval, apply the approved specification amendment first, then write the implementation
task from the amended authority. Rejection or revision stays in the amendment step.

## Worked example — violation

- **Input feedback:** "the activity disclosure does not look clickable"
- **Cited authority:** feature `TRUTH.md`, business rule 1: "Every interactive element declares its
  full interactive state"; an actionable element that looks identical under the pointer is a defect.
- **Classification:** **violation**. The specification already requires pointer and hover affordance;
  the rendered disclosure breaks it.
- **Output — write directly to `TASKS.md`, with no approval step:**

  **Task: Make the activity disclosure visibly clickable**
  - **Description:** Make the shared disclosure trigger declare its required pointer and hover
    affordance while preserving its focus-visible, active, disabled, and keyboard behaviour.
  - **Authority:** `TRUTH.md` business rule 1.
  - **Target Files:** `frontend/src/components/Disclosure.tsx` and its behaviour test.
  - **Success Criteria:** Hovering the activity disclosure shows a pointer cursor and underlines the
    label; focus and keyboard expansion continue to work.

## Worked example — contradiction

- **Input feedback:** "the navigation should be centred on the bar"
- **Cited authority:** at the time of the feedback, `docs/ui/SCREENS.md` §App shell said **"The nav
  is left-adjacent"**, recording that centring was reverted on 2026-08-07.
- **Classification:** **contradiction**. Centring cannot be implemented without reversing that
  explicit design decision.
- **Output — proposed amendment:**
  - **Feedback:** "the navigation should be centred on the bar"
  - **Target:** `docs/ui/SCREENS.md` §App shell, drafted through the feature's `DESIGN.md`.
  - **Current decision:** navigation is left-adjacent; the 2026-08-07 decision treated centring as
    transitional and reverted it when a second item arrived.
  - **Proposed amendment:** replace that decision with navigation permanently centred on the bar's
    centre line, growing symmetrically as destinations are added. Use a three-column `1fr auto 1fr`
    bar so unequal edge controls cannot move the navigation off-centre.
  - **Consequences:** remove the fixed wordmark-to-navigation gap promise and update affected
    `TRUTH.md` criteria. This is the amendment recorded by `DESIGN.md` §14.9 on 2026-08-21.

> Approve this amendment to `docs/ui/SCREENS.md` §App shell, changing navigation from
> left-adjacent (decided 2026-08-07) to permanently centred on the bar with symmetric growth and no
> fixed wordmark-to-navigation gap? Until you approve it, I will not write a task.

**STOP. No task is written before approval.**
