---
type: Module
title: frontend authored-source guardrails
description: The local ESLint plugin that enforces named Tailwind width, type and spacing tokens and shared interactive primitives in authored application source.
resource: frontend/eslint.config.js
tags: [frontend, eslint, tailwind, design-system, accessibility]
timestamp: 2026-08-22T00:00:00Z
---

# frontend authored-source guardrails

## Purpose

`frontend/eslint.config.js` loads the repository-local plugin in `frontend/eslint-rules/` and makes
four UI-foundation rules errors for authored application source. The rules turn the width, type,
spacing and shared-control decisions in `docs/ui/SCREENS.md` into the normal frontend lint gate.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| authored-source ESLint block | Enables all four `local/*` rules for `src/**/*.{ts,tsx}` while exempting the vendored `src/components/ui/**`, tests and the test harness. | `frontend/eslint.config.js:29` |
| local plugin | Exports `no-arbitrary-utility`, `no-raw-type-size`, `spacing-scale` and `no-bare-interactive` under one plugin object. | `frontend/eslint-rules/index.js:6` |
| `createClassStringVisitor()` | Visits string literals and static template segments only when they occur under `className` or a recognized class-composition call (`cn`, `clsx`, `twMerge`, `cva`), then supplies normalized class tokens to a rule. | `frontend/eslint-rules/class-strings.js:58` |
| `utilityFromClassToken()` | Removes leading important/negative markers and top-level variant prefixes without treating colons inside bracket/parenthesis expressions as variants. | `frontend/eslint-rules/class-strings.js:33` |
| `no-arbitrary-utility` | Rejects bracket-valued authored utilities and points the author to a named width, spacing or type token in `src/index.css`. | `frontend/eslint-rules/no-arbitrary-utility.js:20` |
| `no-raw-type-size` | Rejects Tailwind's framework text sizes; suggests the equal-size named token where one exists and otherwise requires an explicit scale decision. | `frontend/eslint-rules/no-raw-type-size.js:37` |
| `spacing-scale` | Restricts margin, padding, gap and space utilities to `0`, `1`, `2`, `3`, `4`, `6`, `8`, `12`, `16`, `24`, `px` or `auto`; bracket values are left to `no-arbitrary-utility`. | `frontend/eslint-rules/spacing-scale.js:34` |
| `no-bare-interactive` | Rejects native `<button>`, `<input>`, `<select>` and `<textarea>` elements in application screens so shared primitives own interactive states. | `frontend/eslint-rules/no-bare-interactive.js:18` |

## How it connects

- The named container and type tokens live in `frontend/src/index.css`; their rendered use is mapped
  by [screens](./screens.md).
- The binding human authority is [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md), especially its
  Typography, Spacing and rhythm, Proportion and containers, and Building rules sections.
- [`frontend-conventions`](../../skills/frontend-conventions/SKILL.md), the frontend design agent and
  the frontend reviewer tell agents how to apply and review the same four foundations; ESLint is the
  executable backstop.

## Notes / gotchas

- The exemption boundary is deliberate: vendored shadcn primitives may contain their native control,
  while application screens must compose those primitives. Test code and the test harness are not
  product UI and are also outside the four local rules.
- The class rules inspect authored static strings, including strings inside the recognized composition
  calls. They do not attempt to evaluate arbitrary runtime expressions.
- These rules report only; they do not auto-fix a design choice or widen the approved token sets.

# Citations

[1] [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md)
[2] [specs/035-frontend-guardrails-and-ui-fixes/ARCHITECTURE.md](../../../specs/035-frontend-guardrails-and-ui-fixes/ARCHITECTURE.md)
