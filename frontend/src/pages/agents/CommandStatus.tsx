import type { Ref } from 'react'
import { Link } from 'react-router'
import AdminOnly from '@/components/AdminOnly'
import StatusPill from '@/components/StatusPill'
import Timestamp from '@/components/Timestamp'
import { Button } from '@/components/ui/button'
import { commandStatusPill } from '@/lib/commandStatus'
import { scanFailureReason } from '@/lib/scanFailureReasons'
import type { components } from '@/types/openapi'

type CommandDetail = components['schemas']['CommandDetail']

function CommandStatus({
  command,
  triggering,
  onRetry,
  ref,
}: {
  command: CommandDetail | null
  triggering: boolean
  onRetry: () => void
  ref?: Ref<HTMLDivElement>
}) {
  if (!command) {
    return (
      <div
        ref={ref}
        data-testid="agents-command-status"
        className="text-body-sm text-muted-foreground"
        role="status"
        aria-live="polite"
        tabIndex={-1}
      >
        Starting…
      </div>
    )
  }

  const pill = commandStatusPill(command.status)
  const done = command.status === 'done'
  const retryable = command.status === 'failed' || command.status === 'expired'

  return (
    <div
      ref={ref}
      data-testid="agents-command-status"
      className="flex flex-col items-end gap-2 text-right"
      role="status"
      aria-live="polite"
      tabIndex={-1}
    >
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span data-testid="agents-pill">
          <StatusPill tone={pill.tone} label={pill.label} />
        </span>
        {done && command.scan_id && (
          <Button asChild>
            <Link
              to={`/scans/${command.scan_id}`}
              data-testid="agents-view-scan"
            >
              View scan
            </Link>
          </Button>
        )}
        {retryable && (
          <AdminOnly>
            <Button
              type="button"
              disabled={triggering}
              onClick={onRetry}
              data-testid="agents-retry"
            >
              {triggering ? 'Starting…' : 'Retry'}
            </Button>
          </AdminOnly>
        )}
      </div>
      {done && command.completed_at && (
        <p className="text-body-sm text-muted-foreground">
          Finished <Timestamp value={command.completed_at} />.
        </p>
      )}
      {command.status === 'failed' && (
        <p className="max-w-prose text-body-sm text-muted-foreground">
          {scanFailureReason(command.error_code)}
        </p>
      )}
      {command.status === 'expired' && (
        <p className="max-w-prose text-body-sm text-muted-foreground">
          The Pi never picked up the scan. Check that it's powered on and
          connected to the network.
        </p>
      )}
    </div>
  )
}

export default CommandStatus
