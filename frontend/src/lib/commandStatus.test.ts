import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { commandStatusLabel, isTerminalCommandStatus } from './commandStatus'

type CommandStatus = components['schemas']['CommandStatus']

const EXPECTED_LABELS: Record<CommandStatus, string> = {
  queued: 'Queued',
  delivered: 'Sent to the Pi',
  running: 'Scanning…',
  uploading: 'Uploading results…',
  done: 'Done',
  failed: 'Scan failed',
  cancelled: 'Scan stopped',
  expired: 'Not picked up',
}

describe('commandStatusLabel', () => {
  it('maps every command status to a label and nothing else', () => {
    for (const status of Object.keys(EXPECTED_LABELS) as CommandStatus[]) {
      expect(commandStatusLabel(status)).toBe(EXPECTED_LABELS[status])
    }
  })

  it('distinguishes failed commands from expired commands', () => {
    expect(commandStatusLabel('failed')).not.toBe(commandStatusLabel('expired'))
  })
})

describe('isTerminalCommandStatus', () => {
  it.each<CommandStatus>(['done', 'failed', 'cancelled', 'expired'])(
    'returns true for %s',
    (status) => {
      expect(isTerminalCommandStatus(status)).toBe(true)
    },
  )

  it.each<CommandStatus | undefined>([
    'queued',
    'delivered',
    'running',
    'uploading',
    undefined,
  ])('returns false for %s', (status) => {
    expect(isTerminalCommandStatus(status)).toBe(false)
  })
})
