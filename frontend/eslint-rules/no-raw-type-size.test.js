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

function noMatchingTokenMessage(token, px) {
  return (
    `\`${token}\` is a framework size and no scale token matches ${px}px. Pick the nearest ` +
    '`text-title-*` / `text-body-*` / `text-caption-*` token, or add one to ' +
    '`frontend/src/index.css`.'
  )
}

ruleTester.run('no-raw-type-size', rule, {
  valid: [
    '<div className="text-body-md" />',
    '<div className="text-body-sm" />',
    '<div className="text-title-sm" />',
    '<div className="text-caption-md" />',
    "cn('text-title-xs')",
    "cn('text-body-sm/6')",
    "cva('text-muted-foreground')",
    '<div data-testid="text-sm" />',
    'const copy = "text-lg"',
  ],
  invalid: [
    {
      code: '<div className="text-sm" />',
      errors: [
        {
          message:
            '`text-sm` is a framework size, not a scale token. Use `text-body-sm` (same 14px).',
        },
      ],
    },
    {
      code: "cn('text-xs')",
      errors: [{ message: noMatchingTokenMessage('text-xs', 12) }],
    },
    {
      code: "cn('text-base')",
      errors: [{ message: noMatchingTokenMessage('text-base', 16) }],
    },
    {
      code: "cn('text-xl')",
      errors: [{ message: noMatchingTokenMessage('text-xl', 20) }],
    },
    {
      code: "cva('text-lg')",
      errors: [{ message: noMatchingTokenMessage('text-lg', 18) }],
    },
    {
      code: '<div className="md:text-2xl" />',
      errors: [{ message: noMatchingTokenMessage('text-2xl', 24) }],
    },
    {
      code: "twMerge('leading-none text-sm/6')",
      errors: [
        {
          message:
            '`text-sm` is a framework size, not a scale token. Use `text-body-sm` (same 14px).',
        },
      ],
    },
  ],
})
