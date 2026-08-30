import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { commandStatusPill, isTerminalCommandStatus } from './commandStatus'

type CommandStatus = components['schemas']['CommandStatus']

const EXPECTED_STATUS_PILLS: Record<
  CommandStatus,
  { tone: 'running' | 'failed' | 'neutral'; label: string }
> = {
  queued: { tone: 'running', label: 'Queued' },
  delivered: { tone: 'running', label: 'Sent to the Pi' },
  running: { tone: 'running', label: 'Scanning…' },
  uploading: { tone: 'running', label: 'Uploading results…' },
  done: { tone: 'neutral', label: 'Done' },
  failed: { tone: 'failed', label: 'Scan failed' },
  expired: { tone: 'failed', label: 'Not picked up' },
}

describe('commandStatusPill', () => {
  it('maps every command status to its pill presentation', () => {
    for (const status of Object.keys(
      EXPECTED_STATUS_PILLS,
    ) as CommandStatus[]) {
      expect(commandStatusPill(status)).toEqual(EXPECTED_STATUS_PILLS[status])
    }
  })

  it('distinguishes failed commands from expired commands', () => {
    expect(commandStatusPill('failed').label).not.toBe(
      commandStatusPill('expired').label,
    )
  })
})

describe('isTerminalCommandStatus', () => {
  it.each<CommandStatus>(['done', 'failed', 'expired'])(
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
