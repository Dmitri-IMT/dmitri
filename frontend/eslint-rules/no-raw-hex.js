import { createClassStringVisitor } from './class-strings.js'

const RAW_COLOR = /#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/

export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow raw colour values in authored styles',
    },
    schema: [],
    messages: {
      rawColor:
        '`{{value}}` is a raw colour. `docs/ui/FOUNDATIONS.md` §Color: colour is a token — ' +
        'use `--canvas` / `--card` / `--ink` / `--ink-muted` / `--rule` / `--edge` / ' +
        '`--accent` / `--accent-foreground`, or add the token to `frontend/src/index.css`.',
    },
  },
  create(context) {
    return {
      ...createClassStringVisitor(context, ({ node, token }) => {
        if (!RAW_COLOR.test(token)) return

        context.report({ node, messageId: 'rawColor', data: { value: token } })
      }),
      JSXAttribute(node) {
        if (node.name.type !== 'JSXIdentifier') return
        if (node.name.name !== 'style' || !node.value) return

        const text = context.sourceCode.getText(node.value)
        if (!RAW_COLOR.test(text)) return

        context.report({
          node,
          messageId: 'rawColor',
          data: { value: RAW_COLOR.exec(text)[0] },
        })
      },
    }
  },
}
