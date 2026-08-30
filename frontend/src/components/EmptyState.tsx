import type { ReactNode } from 'react'
import Ornament from '@/components/Ornament'

type EmptyStateProps = {
  heading: string
  body: string
  testId: string
  action?: ReactNode
  note?: ReactNode
}

function EmptyState({ heading, body, testId, action, note }: EmptyStateProps) {
  return (
    <div
      data-testid={testId}
      className="flex flex-col items-center gap-6 py-16 text-center"
    >
      <div className="flex max-w-prose flex-col items-center gap-6">
        <h2 className="font-title text-title-sm">{heading}</h2>
        <p className="text-body-md text-muted-foreground">{body}</p>
        {action}
        {note}
      </div>
      <div className="w-24">
        <Ornament />
      </div>
    </div>
  )
}

export default EmptyState
