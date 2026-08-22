import { createClassStringVisitor } from './class-strings.js'

const MESSAGE =
  '`{{token}}` is an arbitrary value. Use a named token: widths are `max-w-frame` or ' +
  '`max-w-form`, spacing is a scale step (`1 2 3 4 6 8 12 16 24`), type is a ' +
  '`text-title-*` / `text-body-*` / `text-caption-*` / `text-nav` token. Add the token to ' +
  '`frontend/src/index.css` if it does not exist yet.'

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Disallow arbitrary values in authored Tailwind class strings',
    },
    schema: [],
    messages: {
      arbitraryValue: MESSAGE,
    },
  },
  create(context) {
    return createClassStringVisitor(context, ({ node, utility }) => {
      if (!/\[.*\]/.test(utility)) return

      context.report({
        node,
        messageId: 'arbitraryValue',
        data: { token: utility },
      })
    })
  },
}
