import { RuleTester } from 'eslint'
import { describe, it } from 'vitest'
import rule from './no-raw-hex.js'

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

function rawColorMessage(value) {
  return (
    `\`${value}\` is a raw colour. \`docs/ui/FOUNDATIONS.md\` §Color: colour is a token — ` +
    'use `--canvas` / `--card` / `--ink` / `--ink-muted` / `--rule` / `--edge` / ' +
    '`--accent` / `--accent-foreground`, or add the token to `frontend/src/index.css`.'
  )
}

ruleTester.run('no-raw-hex', rule, {
  valid: [
    '<div className="bg-card text-ink" />',
    "cn('border-rule')",
    "cva('text-accent-foreground')",
    "<div style={{ color: 'var(--ink)' }} />",
    '<div style={{ color: tint }} />',
    "cn('bg-accent/10')",
    'const swatch = "#4f46e5"',
    '<div data-testid="#4f46e5" />',
  ],
  invalid: [
    {
      code: '<div className="bg-[#fff]" />',
      errors: [{ message: rawColorMessage('bg-[#fff]') }],
    },
    {
      code: "cn('text-[#4f46e5]')",
      errors: [{ message: rawColorMessage('text-[#4f46e5]') }],
    },
    {
      code: "cva('shadow-[0_0_0_2px_#0f172a80]')",
      errors: [{ message: rawColorMessage('shadow-[0_0_0_2px_#0f172a80]') }],
    },
    {
      code: "cn('bg-[rgb(15,23,42)]')",
      errors: [{ message: rawColorMessage('bg-[rgb(15,23,42)]') }],
    },
    {
      code: "<div style={{ color: '#0f172a' }} />",
      errors: [{ message: rawColorMessage('#0f172a') }],
    },
    {
      code: "<div style={{ background: 'rgba(15, 23, 42, 0.4)' }} />",
      errors: [{ message: rawColorMessage('rgba(') }],
    },
    {
      code: '<div style={{ borderColor: `hsl(220 13% 91%)` }} />',
      errors: [{ message: rawColorMessage('hsl(') }],
    },
  ],
})
