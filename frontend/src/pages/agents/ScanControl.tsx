import { useRef } from 'react'
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
  const focusStatusOnMount = useRef(false)

  async function triggerScan() {
    const outcome = await scanCommand.trigger()
    if (outcome === 'followed') {
      focusStatusOnMount.current = true
    } else if (outcome === 'subnet-stale') {
      onSubnetStale()
    }
  }

  function receiveStatus(node: HTMLDivElement | null) {
    if (!node || !focusStatusOnMount.current) return
    focusStatusOnMount.current = false
    node.focus()
  }

  if (scanCommand.following) {
    return (
      <div className="flex justify-end">
        <CommandStatus
          ref={receiveStatus}
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
