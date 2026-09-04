import type { components } from '@/types/openapi'

type CommandStatus = components['schemas']['CommandStatus']

const COMMAND_STATUS_LABELS: Record<CommandStatus, string> = {
  queued: 'Queued',
  delivered: 'Sent to the Pi',
  running: 'Scanning…',
  uploading: 'Uploading results…',
  done: 'Done',
  failed: 'Scan failed',
  expired: 'Not picked up',
}

export function commandStatusLabel(status: CommandStatus): string {
  return COMMAND_STATUS_LABELS[status]
}

export function isTerminalCommandStatus(
  status: CommandStatus | undefined,
): boolean {
  return status === 'done' || status === 'failed' || status === 'expired'
}
