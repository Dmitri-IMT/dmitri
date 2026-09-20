import path from 'node:path'
import { ESLint, RuleTester } from 'eslint'
import { describe, expect, it } from 'vitest'
import rule from './no-dark-variant.js'

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

function darkVariantMessage(token) {
  return (
    `\`${token}\` uses the \`dark:\` variant. \`docs/ui/FOUNDATIONS.md\` §Theme: one light ` +
    'theme ships and `dark:` is never authored — the variant is neutralised in ' +
    '`frontend/src/index.css`. Drop the prefix and style the light theme only.'
  )
}

ruleTester.run('no-dark-variant', rule, {
  valid: [
    '<div className="bg-card text-ink" />',
    "cn('hover:bg-muted focus-visible:ring-2')",
    '<div className="dark-mode-note" />',
    '<div className="data-[theme=dark]:bg-card" />',
    '<div data-testid="dark:bg-card" />',
    'const note = "dark:bg-card"',
  ],
  invalid: [
    {
      code: '<div className="dark:bg-card" />',
      errors: [{ message: darkVariantMessage('dark:bg-card') }],
    },
    {
      code: 'const view = <div className={`dark:bg-card ${extra}`} />',
      errors: [{ message: darkVariantMessage('dark:bg-card') }],
    },
    {
      code: "cn('hover:dark:text-ink')",
      errors: [{ message: darkVariantMessage('hover:dark:text-ink') }],
    },
    {
      code: "cva('dark:aria-invalid:ring-destructive/40')",
      errors: [
        {
          message: darkVariantMessage('dark:aria-invalid:ring-destructive/40'),
        },
      ],
    },
  ],
})

describe('the src/components/ui exemption', () => {
  const eslint = new ESLint({
    cwd: path.resolve(import.meta.dirname, '..'),
  })

  it('leaves the rule off for the generated primitives', async () => {
    const config = await eslint.calculateConfigForFile(
      'src/components/ui/button.tsx',
    )

    expect(config.rules['local/no-dark-variant']).toBeUndefined()
  })

  it('leaves the rule off while the application supports a dark theme', async () => {
    const config = await eslint.calculateConfigForFile('src/pages/Hosts.tsx')

    expect(config.rules['local/no-dark-variant']).toBeUndefined()
  })
})
