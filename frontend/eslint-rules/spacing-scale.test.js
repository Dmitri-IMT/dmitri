import { RuleTester } from 'eslint'
import { describe, it } from 'vitest'
import rule from './spacing-scale.js'

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

function offScaleMessage(token) {
  return (
    `\`${token}\` is off the spacing scale. \`SCREENS.md\` §Spacing permits only ` +
    "`1 2 3 4 6 8 12 16 24` on Tailwind's 4px base."
  )
}

ruleTester.run('spacing-scale', rule, {
  valid: [
    '<div className="p-6" />',
    "cn('gap-4')",
    "cva('mx-auto')",
    '<div className="p-px" />',
    '<div className="p-[13px]" />',
    '<div aria-describedby="gap-7" />',
    'const copy = "p-5"',
  ],
  invalid: [
    {
      code: '<div className="p-5" />',
      errors: [{ message: offScaleMessage('p-5') }],
    },
    {
      code: "cn('gap-7')",
      errors: [{ message: offScaleMessage('gap-7') }],
    },
    {
      code: "cva('mt-2.5')",
      errors: [{ message: offScaleMessage('mt-2.5') }],
    },
    {
      code: '<div className="has-data-[icon=inline-end]:pr-5" />',
      errors: [{ message: offScaleMessage('pr-5') }],
    },
  ],
})
