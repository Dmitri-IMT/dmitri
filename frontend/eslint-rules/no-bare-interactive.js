const NATIVE_CONTROLS = new Set(['button', 'input', 'select', 'textarea'])

export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Require shared primitives instead of bare native controls',
    },
    schema: [],
    messages: {
      nativeControl:
        '`<{{name}}>` is a native control. Application screens compose the shared primitives — ' +
        '`Button` / `Input` / `Label` / `Select` from `@/components/ui/`, or a shared component ' +
        'under `@/components/` — so interactive state is specified in one place ' +
        '(`docs/ui/FOUNDATIONS.md` §Interaction states).',
    },
  },
  create(context) {
    return {
      JSXOpeningElement(node) {
        if (node.name.type !== 'JSXIdentifier') return
        if (!NATIVE_CONTROLS.has(node.name.name)) return

        context.report({
          node,
          messageId: 'nativeControl',
          data: { name: node.name.name },
        })
      },
    }
  },
}
