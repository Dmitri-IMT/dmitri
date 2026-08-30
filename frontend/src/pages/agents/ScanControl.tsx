import { useLayoutEffect, useRef, useState } from 'react'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'
import CommandStatus from './CommandStatus'
import type { ScanCommand } from '@/hooks/useScanCommand'

function ScanControl({
  scanCommand,
  hasTarget,
  autoFocus,
  onSubnetStale,
}: {
  scanCommand: ScanCommand
  hasTarget: boolean
  autoFocus: boolean
  onSubnetStale: () => void
}) {
  const statusRef = useRef<HTMLDivElement>(null)
  const [focusEpoch, setFocusEpoch] = useState(0)

  useLayoutEffect(() => {
    if (focusEpoch === 0) return
    statusRef.current?.focus()
  }, [focusEpoch])

  async function triggerScan() {
    const outcome = await scanCommand.trigger()
    if (outcome === 'followed') {
      setFocusEpoch((epoch) => epoch + 1)
    } else if (outcome === 'subnet-stale') {
      onSubnetStale()
    }
  }

  if (scanCommand.following) {
    return (
      <div className="flex justify-end">
        <CommandStatus
          ref={statusRef}
          command={scanCommand.command}
          triggering={scanCommand.triggering}
          onRetry={() => void triggerScan()}
        />
      </div>
    )
  }

  if (!hasTarget) return null

  return (
    <AdminOnly>
      <div className="flex justify-end">
        <Button
          type="button"
          autoFocus={autoFocus}
          disabled={scanCommand.triggering}
          onClick={() => void triggerScan()}
          data-testid="agents-scan-now"
        >
          {scanCommand.triggering ? 'Starting…' : 'Scan now'}
        </Button>
      </div>
    </AdminOnly>
  )
}

export default ScanControl
