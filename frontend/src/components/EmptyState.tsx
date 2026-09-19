import type { ReactNode } from 'react'

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
      role="status"
      data-testid={testId}
      className="flex flex-col items-center gap-6 px-4 py-16 text-center"
    >
      <div className="flex max-w-prose flex-col items-center gap-6">
        <h2 id={testId + '-heading'} className="text-title-sm">
          {heading}
        </h2>
        <p className="text-body-md text-muted-foreground">{body}</p>
        {action}
        {note}
      </div>
    </div>
  )
}

export default EmptyState
