import { useLayoutEffect, useRef, useState } from 'react'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import CommandStatus from './CommandStatus'
import type { ScanCommand, ScanSelection } from '@/hooks/useScanCommand'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type ScanMode = components['schemas']['ScanMode']
type NspiSubmode = components['schemas']['NspiSubmode']

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
  const [nspiSubmode, setNspiSubmode] = useState<NspiSubmode>('inventory')

  useLayoutEffect(() => {
    if (focusEpoch === 0) return
    statusRef.current?.focus()
  }, [focusEpoch])

  async function triggerScan() {
    const selection: ScanSelection = {
      scanMode: selectedMode,
      ...(selectedMode === 'nspi' ? { nspiSubmode } : {}),
    }
    const outcome = await scanCommand.trigger(selection)
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
        {selectedMode === 'nspi' && (
          <label className="flex flex-col gap-1 text-caption-md">
            NSPi submode
            <Select
              value={nspiSubmode}
              onValueChange={(value) => setNspiSubmode(value as NspiSubmode)}
            >
              <SelectTrigger aria-label="NSPi submode" className="min-w-52">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inventory">Inventory</SelectItem>
                <SelectItem value="read_only_mapping">
                  Read-only mapping
                </SelectItem>
              </SelectContent>
            </Select>
          </label>
        )}
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
