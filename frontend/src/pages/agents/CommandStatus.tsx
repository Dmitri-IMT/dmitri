import type { Ref } from 'react'
import { Link, useLocation } from 'react-router'
import AdminOnly from '@/components/AdminOnly'
import Timestamp from '@/components/Timestamp'
import { Button } from '@/components/ui/button'
import { commandStatusLabel } from '@/lib/commandStatus'
import { fromHere } from '@/lib/navFrom'
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
  const location = useLocation()
  const done = command?.status === 'done'
  const retryable =
    command?.status === 'failed' || command?.status === 'expired'

  return (
    <div
      ref={ref}
      data-testid="agents-command-status"
      role="status"
      aria-live="polite"
      tabIndex={-1}
      className={
        command
          ? 'flex flex-col items-end gap-2 text-right'
          : 'text-body-sm text-muted-foreground'
      }
    >
      {!command ? (
        'Starting…'
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span data-testid="agents-status" className="text-body-md">
              {commandStatusLabel(command.status)}
            </span>
            {done && command.scan_id && (
              <Button asChild>
                <Link
                  to={`/scans/${command.scan_id}`}
                  state={fromHere(location)}
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
        </>
      )}
    </div>
  )
}

export default CommandStatus
