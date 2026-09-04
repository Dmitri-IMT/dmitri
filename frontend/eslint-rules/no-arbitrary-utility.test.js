import { RuleTester } from 'eslint'
import { describe, it } from 'vitest'
import rule from './no-arbitrary-utility.js'

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

function arbitraryValueMessage(token) {
  return (
    `\`${token}\` is an arbitrary value. Use a named token: widths are \`max-w-frame\` or ` +
    '`max-w-form`, spacing is a scale step (`1 2 3 4 6 8 12 16 24`), type is a ' +
    '`text-title-*` / `text-body-*` / `text-caption-*` token. Add the token to ' +
    '`frontend/src/index.css` if it does not exist yet.'
  )
}

ruleTester.run('no-arbitrary-utility', rule, {
  valid: [
    '<div className="has-data-[icon=inline-end]:pr-2" />',
    "cn('group-data-[state=open]:rotate-90')",
    "cva('[&_svg]:size-4')",
    "twMerge('in-data-[slot=button-group]:rounded-lg')",
    "clsx('not-aria-[haspopup]:translate-y-px')",
    `cn("[&_svg:not([class*='size-'])]:size-4")`,
    '<div className="max-w-prose" />',
    '<div className="max-w-page" />',
    '<div className="max-w-frame max-w-form" />',
    '<div data-testid="a-[b]" />',
    'const copy = "A non-class string containing a-[b] brackets"',
  ],
  invalid: [
    {
      code: '<div className="max-w-[45rem]" />',
      errors: [{ message: arbitraryValueMessage('max-w-[45rem]') }],
    },
    {
      code: "cn('p-[13px]')",
      errors: [{ message: arbitraryValueMessage('p-[13px]') }],
    },
    {
      code: 'const view = <div className={`grid-cols-[1fr_auto] ${layout}`} />',
      errors: [{ message: arbitraryValueMessage('grid-cols-[1fr_auto]') }],
    },
    {
      code: '<div className="md:max-w-[45rem]" />',
      errors: [{ message: arbitraryValueMessage('max-w-[45rem]') }],
    },
    {
      code: "cva('base', { variants: { width: { wide: 'max-w-[45rem]' } } })",
      errors: [{ message: arbitraryValueMessage('max-w-[45rem]') }],
    },
  ],
})
