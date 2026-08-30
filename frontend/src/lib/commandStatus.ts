import type { StatusPillTone } from '@/components/StatusPill'
import type { components } from '@/types/openapi'

type CommandStatus = components['schemas']['CommandStatus']

interface CommandStatusPill {
  tone: StatusPillTone
  label: string
}

const COMMAND_STATUS_PILLS: Record<CommandStatus, CommandStatusPill> = {
  queued: { tone: 'running', label: 'Queued' },
  delivered: { tone: 'running', label: 'Sent to the Pi' },
  running: { tone: 'running', label: 'Scanning…' },
  uploading: { tone: 'running', label: 'Uploading results…' },
  done: { tone: 'neutral', label: 'Done' },
  failed: { tone: 'failed', label: 'Scan failed' },
  expired: { tone: 'failed', label: 'Not picked up' },
}

export function commandStatusPill(status: CommandStatus): CommandStatusPill {
  return COMMAND_STATUS_PILLS[status]
}

export function isTerminalCommandStatus(
  status: CommandStatus | undefined,
): boolean {
  return status === 'done' || status === 'failed' || status === 'expired'
}
