import { createClassStringVisitor } from './class-strings.js'

const RAW_TYPE = /^text-(xs|sm|base|lg|xl|[2-9]xl)$/

const TYPE_SIZES = {
  'text-xs': { px: 12 },
  'text-sm': { px: 14, replacement: 'text-body-sm' },
  'text-base': { px: 16 },
  'text-lg': { px: 18 },
  'text-xl': { px: 20 },
  'text-2xl': { px: 24 },
  'text-3xl': { px: 30 },
  'text-4xl': { px: 36 },
  'text-5xl': { px: 48 },
  'text-6xl': { px: 60 },
  'text-7xl': { px: 72 },
  'text-8xl': { px: 96 },
  'text-9xl': { px: 128 },
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Require named type-scale tokens in authored class strings',
    },
    schema: [],
    messages: {
      useToken:
        '`{{token}}` is a framework size, not a scale token. Use `{{replacement}}` (same {{px}}px).',
      noMatchingToken:
        '`{{token}}` is a framework size and no scale token matches {{px}}px. Pick the nearest ' +
        '`text-title-*` / `text-body-*` / `text-caption-*` token, or add one to ' +
        '`frontend/src/index.css`.',
    },
  },
  create(context) {
    return createClassStringVisitor(context, ({ node, utility }) => {
      const token = utility.split('/', 1)[0]
      if (!RAW_TYPE.test(token)) return

      const size = TYPE_SIZES[token]
      const messageId = size.replacement ? 'useToken' : 'noMatchingToken'
      context.report({
        node,
        messageId,
        data: {
          token,
          px: size.px,
          replacement: size.replacement,
        },
      })
    })
  },
}
