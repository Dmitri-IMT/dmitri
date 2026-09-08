import { RuleTester } from 'eslint'
import { describe, it } from 'vitest'
import rule from './no-bare-interactive.js'

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

function nativeControlMessage(name) {
  return (
    `\`<${name}>\` is a native control. Application screens compose the shared primitives — ` +
    '`Button` / `Input` / `Label` / `Select` from `@/components/ui/`, or a shared component ' +
    'under `@/components/` — so interactive state is specified in one place ' +
    '(`docs/ui/FOUNDATIONS.md` §Interaction states).'
  )
}

ruleTester.run('no-bare-interactive', rule, {
  valid: [
    '<Button />',
    '<Collapsible.Trigger />',
    '<a href="/settings">Settings</a>',
    '<div onClick={() => {}}>Open</div>',
  ],
  invalid: [
    {
      code: '<button type="button">Save</button>',
      errors: [{ message: nativeControlMessage('button') }],
    },
    {
      code: '<input name="email" />',
      errors: [{ message: nativeControlMessage('input') }],
    },
    {
      code: '<select><option>One</option></select>',
      errors: [{ message: nativeControlMessage('select') }],
    },
    {
      code: '<textarea />',
      errors: [{ message: nativeControlMessage('textarea') }],
    },
  ],
})
