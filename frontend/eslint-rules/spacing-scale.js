import { createClassStringVisitor } from './class-strings.js'

const ALLOWED_VALUES = new Set([
  '0',
  '1',
  '2',
  '3',
  '4',
  '6',
  '8',
  '12',
  '16',
  '24',
  'px',
  'auto',
])

const MARGIN_OR_PADDING = /^(?:m|p)(?:t|r|b|l|x|y|s|e)?-(.+)$/
const GAP_OR_SPACE = /^(?:gap|gap-x|gap-y|space-x|space-y)-(.+)$/

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Require the documented spacing scale in authored class strings',
    },
    schema: [],
    messages: {
      offScale:
        '`{{token}}` is off the spacing scale. `docs/ui/FOUNDATIONS.md` §Spacing permits only ' +
        "`1 2 3 4 6 8 12 16 24` on Tailwind's 4px base.",
    },
  },
  create(context) {
    return createClassStringVisitor(context, ({ node, utility }) => {
      if (utility.includes('[')) return

      const match =
        MARGIN_OR_PADDING.exec(utility) ?? GAP_OR_SPACE.exec(utility)
      if (!match || ALLOWED_VALUES.has(match[1])) return

      context.report({
        node,
        messageId: 'offScale',
        data: { token: utility },
      })
    })
  },
}
