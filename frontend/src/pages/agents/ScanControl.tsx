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

type ScanMode = components['schemas']['ScanMode']
type NspiSubmode = components['schemas']['NspiSubmode']

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
  const [scanMode, setScanMode] = useState<ScanMode>('quick')
  const [nspiSubmode, setNspiSubmode] =
    useState<NspiSubmode>('inventory')

  useLayoutEffect(() => {
    if (focusEpoch === 0) return
    statusRef.current?.focus()
  }, [focusEpoch])

  async function triggerScan() {
    const selection: ScanSelection = {
      scanMode,
      ...(scanMode === 'nspi' ? { nspiSubmode } : {}),
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
      <div className="flex flex-wrap items-end justify-end gap-3">
        <label className="flex flex-col gap-1 text-caption-md">
          Scan mode
          <Select
            value={scanMode}
            onValueChange={(value) => setScanMode(value as ScanMode)}
          >
            <SelectTrigger aria-label="Scan mode" className="min-w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="quick">Quick</SelectItem>
              <SelectItem value="standard">Standard</SelectItem>
              <SelectItem value="extensive">Extensive</SelectItem>
              <SelectItem value="max">MAX</SelectItem>
              <SelectItem value="nspi">NSPi</SelectItem>
            </SelectContent>
          </Select>
        </label>
        {scanMode === 'nspi' && (
          <label className="flex flex-col gap-1 text-caption-md">
            NSPi submode
            <Select
              value={nspiSubmode}
              onValueChange={(value) =>
                setNspiSubmode(value as NspiSubmode)
              }
            >
              <SelectTrigger aria-label="NSPi submode" className="min-w-52">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inventory">Inventory</SelectItem>
                <SelectItem value="read_only_mapping">
                  Read-only mapping
                </SelectItem>
                <SelectItem value="active_validation" disabled>
                  Active validation (unavailable)
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
      </div>
    </AdminOnly>
  )
}

export default ScanControl
