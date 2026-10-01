import type { RefObject } from 'react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import AdminOnly from '@/components/AdminOnly'
import Timestamp from '@/components/Timestamp'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { commandStatusLabel } from '@/lib/commandStatus'
import { fromHere } from '@/lib/navFrom'
import { scanFailureReason } from '@/lib/scanFailureReasons'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import type { components } from '@/types/openapi'

type CommandDetail = components['schemas']['CommandDetail']

function CommandStatus({
  command,
  triggering,
  cancelling,
  deviceName,
  onCancel,
  onRetry,
  ref,
}: {
  command: CommandDetail | null
  triggering: boolean
  cancelling: boolean
  deviceName: string
  onCancel: () => void
  onRetry: () => void
  ref?: RefObject<HTMLDivElement | null>
}) {
  const location = useLocation()
  const [stopDialogOpen, setStopDialogOpen] = useState(false)
  const done = command?.status === 'done'
  const stoppable =
    command?.status === 'delivered' || command?.status === 'running'
  const retryable =
    command?.status === 'failed' ||
    command?.status === 'expired' ||
    command?.status === 'cancelled'
  const cancelledWithResults =
    command?.status === 'cancelled' && command.has_results
  const showScanLink = done || cancelledWithResults

  function confirmStop() {
    onCancel()
    setStopDialogOpen(false)
  }

  return (
    <div
      ref={ref}
      data-testid="agents-command-status"
      role="status"
      aria-live="polite"
      tabIndex={-1}
      className={
        command
          ? 'flex flex-col items-start gap-2 text-left'
          : 'text-body-sm text-muted-foreground'
      }
    >
      {!command ? (
        'Starting…'
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-start gap-2">
            <span data-testid="agents-status" className="text-body-md">
              {cancelling ? 'Stopping…' : commandStatusLabel(command.status)}
            </span>
            {stoppable && !cancelling && (
              <AdminOnly>
                <Dialog open={stopDialogOpen} onOpenChange={setStopDialogOpen}>
                  <DialogTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      data-testid="agents-stop-scan"
                    >
                      Stop scan
                    </Button>
                  </DialogTrigger>
                  <DialogContent
                    data-testid="agents-stop-dialog"
                    onCloseAutoFocus={(event) => {
                      event.preventDefault()
                      ref?.current?.focus()
                    }}
                  >
                    <DialogHeader>
                      <DialogTitle>
                        Stop the {SCAN_MODE_LABEL[command.scan_mode]} scan on{' '}
                        {deviceName}?
                      </DialogTitle>
                      <DialogDescription>
                        The Pi stops within a few seconds and saves what it
                        found so far.
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="flex-row justify-end">
                      <DialogClose asChild>
                        <Button type="button" variant="outline">
                          Keep scanning
                        </Button>
                      </DialogClose>
                      <Button
                        type="button"
                        onClick={confirmStop}
                        data-testid="agents-stop-confirm"
                      >
                        Stop scan
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </AdminOnly>
            )}
            {showScanLink && command.scan_id && (
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
          {cancelledWithResults && (
            <p className="max-w-prose text-body-sm text-muted-foreground">
              You stopped this scan. Results found before the stop were saved.
            </p>
          )}
        </>
      )}
    </div>
  )
}

export default CommandStatus
