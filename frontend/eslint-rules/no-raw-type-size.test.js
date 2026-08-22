import { RuleTester } from 'eslint'
import { describe, it } from 'vitest'
import rule from './no-raw-type-size.js'

RuleTester.describe = describe
RuleTester.it = it
RuleTester.itOnly = it.only

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
})

ruleTester.run('no-raw-type-size', rule, {
  valid: [
    '<div className="text-body-md" />',
    '<div className="text-title-sm" />',
    '<div className="text-caption-md" />',
    "cn('text-nav')",
    "cva('text-muted-foreground')",
    '<div className="text-destructive" />',
    '<div data-testid="text-sm" />',
    'const copy = "text-lg"',
  ],
  invalid: [
    {
      code: '<div className="text-sm" />',
      errors: [
        {
          message:
            '`text-sm` is a framework size, not a scale token. Use `text-body-md` (same 14px).',
        },
      ],
    },
    {
      code: "cn('text-xs')",
      errors: [
        {
          message:
            '`text-xs` is a framework size, not a scale token. Use `text-caption-md` (same 12px).',
        },
      ],
    },
    {
      code: "cva('text-lg')",
      errors: [
        {
          message:
            '`text-lg` is a framework size and no scale token matches 18px. Pick the nearest ' +
            '`text-title-*` / `text-body-*` / `text-caption-*` token, or add one to ' +
            '`frontend/src/index.css`.',
        },
      ],
    },
    {
      code: "twMerge('leading-none text-sm/6')",
      errors: [
        {
          message:
            '`text-sm` is a framework size, not a scale token. Use `text-body-md` (same 14px).',
        },
      ],
    },
  ],
})
