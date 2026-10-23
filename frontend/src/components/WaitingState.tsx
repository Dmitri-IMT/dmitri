import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Props = {
  size: 'large' | 'small'
  stage: string
  detail: string
  startedAt: number
  progress?: { done: number; total: number }
  cancelLabel?: string
  onCancel?: () => void
  testId?: string
  cancelTestId?: string
}

const SQUARE_COLOURS = [
  'bg-ink',
  'bg-rule',
  'bg-edge',
  'bg-rule',
  'bg-ink',
  'bg-rule',
  'bg-edge',
  'bg-rule',
  'bg-ink',
] as const

function formatElapsed(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export default function WaitingState({
  size,
  stage,
  detail,
  startedAt,
  progress,
  cancelLabel,
  onCancel,
  testId,
  cancelTestId,
}: Props) {
  const [now, setNow] = useState(() => Date.now())
  const large = size === 'large'

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div
      data-testid={testId}
      className="flex flex-col gap-4 rounded-md border border-rule p-4"
    >
      <div className={cn('flex items-center', large ? 'gap-4' : 'gap-3')}>
        <div aria-hidden="true" className="grid shrink-0 grid-cols-3 gap-1">
          {SQUARE_COLOURS.map((colour, index) => (
            <span
              key={index}
              className={cn(
                'animate-grid-pulse rounded-xs motion-reduce:animate-none',
                large ? 'size-2' : 'size-1.5',
                colour,
              )}
              style={{ animationDelay: `${(index % 4) * 150}ms` }}
            />
          ))}
        </div>
        <div role="status" className="flex min-w-0 flex-1 flex-col gap-1">
          <p className={cn('text-body-md text-ink', large && 'font-semibold')}>
            {stage}
          </p>
          <p
            className={cn(
              'text-ink-muted',
              large ? 'text-body-sm' : 'text-caption-md',
            )}
          >
            {detail}
          </p>
        </div>
        <p
          aria-hidden="true"
          data-testid={testId ? `${testId}-elapsed` : undefined}
          className="shrink-0 text-caption-md text-ink-muted tabular-nums"
        >
          {formatElapsed(now - startedAt)}
        </p>
        {onCancel && cancelLabel && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            data-testid={cancelTestId}
            onClick={onCancel}
          >
            {cancelLabel}
          </Button>
        )}
      </div>
      {progress && progress.total > 0 && (
        <div aria-hidden="true" className="h-1.5 rounded-full bg-rule">
          <div
            className="h-1.5 rounded-full bg-ink"
            style={{
              width: `${Math.min(100, (progress.done / progress.total) * 100)}%`,
            }}
          />
        </div>
      )}
    </div>
  )
}
