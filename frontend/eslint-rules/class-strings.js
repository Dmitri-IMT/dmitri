const CLASS_CALLEES = new Set(['cn', 'clsx', 'twMerge', 'cva'])

function isClassNameAttribute(node) {
  return (
    node.type === 'JSXAttribute' &&
    node.name.type === 'JSXIdentifier' &&
    node.name.name === 'className'
  )
}

function isClassUtilityCall(node) {
  return (
    node.type === 'CallExpression' &&
    node.callee.type === 'Identifier' &&
    CLASS_CALLEES.has(node.callee.name)
  )
}

function isAuthoredClassString(sourceCode, node) {
  return sourceCode
    .getAncestors(node)
    .some(
      (ancestor) =>
        isClassNameAttribute(ancestor) || isClassUtilityCall(ancestor),
    )
}

function stringValue(node) {
  if (node.type === 'Literal') {
    return typeof node.value === 'string' ? node.value : null
  }

  return node.value.cooked ?? node.value.raw
}

export function utilityFromClassToken(token) {
  let normalized = token
  if (normalized.startsWith('!')) normalized = normalized.slice(1)
  if (normalized.startsWith('-')) normalized = normalized.slice(1)

  let depth = 0
  let segmentStart = 0
  let utility = normalized

  for (let index = 0; index < normalized.length; index += 1) {
    const character = normalized[index]

    if (character === '[' || character === '(') {
      depth += 1
    } else if (character === ']' || character === ')') {
      depth = Math.max(0, depth - 1)
    } else if (character === ':' && depth === 0) {
      segmentStart = index + 1
      utility = normalized.slice(segmentStart)
    }
  }

  return utility
}

export function createClassStringVisitor(context, visitToken) {
  const sourceCode = context.sourceCode

  function inspect(node) {
    if (!isAuthoredClassString(sourceCode, node)) return

    const value = stringValue(node)
    if (value === null) return

    for (const token of value.split(/\s+/)) {
      if (!token) continue
      visitToken({ node, token, utility: utilityFromClassToken(token) })
    }
  }

  return {
    Literal: inspect,
    TemplateElement: inspect,
  }
}
