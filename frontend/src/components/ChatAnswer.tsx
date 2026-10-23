import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'

type Block =
  | { kind: 'paragraph'; lines: string[] }
  | { kind: 'bullets' | 'steps'; items: string[] }

const BULLET = /^\s*[-*]\s+(.*)$/
const STEP = /^\s*\d+[.)]\s+(.*)$/
const INLINE = /\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g

function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  for (const line of text.split('\n')) {
    const bullet = BULLET.exec(line)
    const step = bullet ? null : STEP.exec(line)
    const last = blocks.at(-1)
    if (bullet || step) {
      const kind = bullet ? 'bullets' : 'steps'
      const item = (bullet ?? step)![1]
      if (last?.kind === kind) last.items.push(item)
      else blocks.push({ kind, items: [item] })
    } else if (line.trim() === '') {
      blocks.push({ kind: 'paragraph', lines: [] })
    } else if (last?.kind === 'paragraph') {
      last.lines.push(line.trim())
    } else {
      blocks.push({ kind: 'paragraph', lines: [line.trim()] })
    }
  }
  return blocks.filter(
    (block) => block.kind !== 'paragraph' || block.lines.length > 0,
  )
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let cursor = 0
  for (const match of text.matchAll(INLINE)) {
    const index = match.index
    if (index > cursor) nodes.push(text.slice(cursor, index))
    if (match[1] !== undefined) {
      nodes.push(<strong key={index}>{match[1]}</strong>)
    } else {
      nodes.push(
        <Button
          key={index}
          asChild
          variant="link"
          className="h-auto p-0 text-body-md"
        >
          <a
            data-testid="assistant-source-link"
            href={match[3]}
            target="_blank"
            rel="noreferrer noopener"
          >
            {match[2]}
          </a>
        </Button>,
      )
    }
    cursor = index + match[0].length
  }
  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}

export default function ChatAnswer({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-2 text-body-md">
      {toBlocks(text).map((block, index) => {
        if (block.kind === 'paragraph') {
          return <p key={index}>{renderInline(block.lines.join(' '))}</p>
        }
        const items = block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInline(item)}</li>
        ))
        return block.kind === 'steps' ? (
          <ol key={index} className="list-decimal pl-4">
            {items}
          </ol>
        ) : (
          <ul key={index} className="list-disc pl-4">
            {items}
          </ul>
        )
      })}
    </div>
  )
}
