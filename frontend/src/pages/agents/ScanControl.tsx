import { useLayoutEffect, useRef, useState } from 'react'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'
import CommandStatus from './CommandStatus'
import type { ScanCommand } from '@/hooks/useScanCommand'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type ScanMode = components['schemas']['ScanMode']

function ScanControl({
  agent,
  scanCommand,
  selectedMode,
  hasTarget,
  autoFocus,
  onSubnetStale,
}: {
  agent: AgentDetail
  scanCommand: ScanCommand
  selectedMode: ScanMode
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
    const outcome = await scanCommand.trigger(selectedMode)
    if (outcome === 'followed') {
      setFocusEpoch((epoch) => epoch + 1)
    } else if (outcome === 'subnet-stale') {
      onSubnetStale()
    }
  }

  if (scanCommand.following) {
    return (
      <CommandStatus
        ref={statusRef}
        command={scanCommand.command}
        triggering={scanCommand.triggering}
        onRetry={() => void triggerScan()}
      />
    )
  }

  if (!hasTarget) return null

  return (
    <AdminOnly>
      <div className="flex flex-col items-start gap-2">
        <Button
          type="button"
          autoFocus={autoFocus}
          disabled={scanCommand.triggering}
          onClick={() => void triggerScan()}
          data-testid="agents-scan-now"
        >
          {scanCommand.triggering ? 'Starting…' : 'Scan now'}
        </Button>
        {!agent.online && (
          <p className="text-body-md text-muted-foreground">
            This box is offline. A scan will start when it reconnects.
          </p>
        )}
      </div>
    </AdminOnly>
  )
}

export default ScanControl
