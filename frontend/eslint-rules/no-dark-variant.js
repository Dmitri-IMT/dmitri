import { createClassStringVisitor } from './class-strings.js'

const DARK_VARIANT = /(?:^|:)dark:/

export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow the dark: variant in authored class strings',
    },
    schema: [],
    messages: {
      darkVariant:
        '`{{token}}` uses the `dark:` variant. `docs/ui/FOUNDATIONS.md` §Theme: one light ' +
        'theme ships and `dark:` is never authored — the variant is neutralised in ' +
        '`frontend/src/index.css`. Drop the prefix and style the light theme only.',
    },
  },
  create(context) {
    return createClassStringVisitor(context, ({ node, token }) => {
      if (!DARK_VARIANT.test(token)) return

      context.report({ node, messageId: 'darkVariant', data: { token } })
    })
  },
}
