import type { components } from '@/types/openapi'

type CommandDetail = components['schemas']['CommandDetail']
type CommandStatus = components['schemas']['CommandStatus']

const COMMAND_STATUS_LABELS: Record<CommandStatus, string> = {
  queued: 'Queued',
  delivered: 'Sent to the Pi',
  running: 'Scanning…',
  uploading: 'Uploading results…',
  done: 'Done',
  failed: 'Scan failed',
  cancelled: 'Scan stopped',
  expired: 'Not picked up',
}

export function commandStatusLabel(status: CommandStatus): string {
  return COMMAND_STATUS_LABELS[status]
}

export function isTerminalCommandStatus(
  status: CommandStatus | undefined,
): boolean {
  if (status === undefined) return false
  switch (status) {
    case 'done':
    case 'failed':
    case 'cancelled':
    case 'expired':
      return true
    case 'queued':
    case 'delivered':
    case 'running':
    case 'uploading':
      return false
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

export function isSettledCommand(command: CommandDetail | undefined): boolean {
  if (command === undefined || !isTerminalCommandStatus(command.status)) {
    return false
  }
  return command.status !== 'cancelled' || command.has_results
}
