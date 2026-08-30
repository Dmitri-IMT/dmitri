import { useEffect, useRef, useState } from 'react'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'
import CommandStatus from './CommandStatus'
import type { ScanCommand } from '@/hooks/useScanCommand'

function ScanControl({
  scanCommand,
  hasTarget,
}: {
  scanCommand: ScanCommand
  hasTarget: boolean
}) {
  const statusRef = useRef<HTMLDivElement | null>(null)
  const [focusRequest, setFocusRequest] = useState(0)

  useEffect(() => {
    if (focusRequest === 0) return
    statusRef.current
      ?.querySelector<HTMLElement>('[data-testid="agents-command-status"]')
      ?.focus()
  }, [focusRequest])

  async function triggerAndFocus() {
    const result = await scanCommand.trigger()
    if (result.outcome === 'followed') {
      setFocusRequest((request) => request + 1)
    }
  }

  if (scanCommand.following) {
    return (
      <div ref={statusRef} className="flex justify-end">
        <CommandStatus
          command={scanCommand.command}
          triggering={scanCommand.triggering}
          onRetry={() => void triggerAndFocus()}
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
          disabled={scanCommand.triggering}
          onClick={() => void triggerAndFocus()}
          data-testid="agents-scan-now"
        >
          {scanCommand.triggering ? 'Starting…' : 'Scan now'}
        </Button>
      </div>
    </AdminOnly>
  )
}

export default ScanControl
