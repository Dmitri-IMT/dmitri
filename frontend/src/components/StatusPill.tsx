import { cn } from '@/lib/utils'

export type StatusPillTone = 'running' | 'failed' | 'neutral'

const TONE_CLASS: Record<StatusPillTone, string> = {
  running: 'border-input text-muted-foreground',
  failed: 'border-sev-critical text-sev-critical',
  neutral: 'border-border text-muted-foreground',
}

type StatusPillProps = {
  tone: StatusPillTone
  label: string
}

function StatusPill({ tone, label }: StatusPillProps) {
  return (
    <span
      className={cn(
        'inline-flex h-8 items-center border px-2 text-body-md',
        TONE_CLASS[tone],
      )}
    >
      {label}
    </span>
  )
}

export default StatusPill
