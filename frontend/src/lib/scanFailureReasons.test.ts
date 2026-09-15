import { describe, expect, it } from 'vitest'
import { SCAN_FAILURE_REASONS, scanFailureReason } from './scanFailureReasons'

const PUBLISHED_CODES = [
  'agent_disconnected',
  'device_busy',
  'device_offline',
  'ingest_failed',
  'invalid_command',
  'result_unavailable',
  'scan_failed',
  'scan_timeout',
  'unknown',
]

const APPROVED: Record<(typeof PUBLISHED_CODES)[number], string> = {
  device_offline:
    "The Pi wasn't connected when the scan was requested. Check that it's powered on and online, then try again.",
  device_busy:
    'The Pi was already running another scan. Wait for it to finish, then try again.',
  agent_disconnected:
    "The Pi stopped responding while the scan was running. Check that it's powered on and online, then try again.",
  scan_failed:
    "The scan didn't finish on the Pi. Try again — if it keeps failing, contact support.",
  scan_timeout:
    'The scan ran on the Pi for longer than allowed and was stopped. Try again — if it keeps happening, contact support.',
  invalid_command:
    "The Pi couldn't read the scan request. Try again — if it keeps failing, contact support.",
  result_unavailable:
    'The scan ran but produced no results to upload. Try again.',
  ingest_failed:
    "The Pi finished the scan but couldn't upload the results. Check its network connection, then try again.",
  unknown: 'The scan failed. No further detail was reported.',
}

describe('scanFailureReasons', () => {
  it('covers exactly the nine published codes', () => {
    expect(Object.keys(SCAN_FAILURE_REASONS).sort()).toEqual(PUBLISHED_CODES)
  })

  it('returns the approved sentence for each published code', () => {
    for (const code of PUBLISHED_CODES) {
      expect(scanFailureReason(code)).toBe(APPROVED[code])
    }
  })

  it('falls back to the unknown sentence for an unpublished code or no code', () => {
    expect(scanFailureReason('warp_core_breach')).toBe(APPROVED.unknown)
    expect(scanFailureReason(null)).toBe(APPROVED.unknown)
    // `error_code` is optional on the generated types, so an absent field
    // arrives as `undefined` and must read the same as an absent reason.
    expect(scanFailureReason(undefined)).toBe(APPROVED.unknown)
  })

  it('keeps every sentence free of codes, scanner output, and stack traces', () => {
    for (const sentence of Object.values(SCAN_FAILURE_REASONS)) {
      for (const code of PUBLISHED_CODES) {
        expect(sentence).not.toContain(code)
      }
      expect(sentence).not.toContain('_')
      expect(sentence).not.toContain('nmap')
      expect(sentence).not.toContain('Traceback')
      expect(sentence.endsWith('.')).toBe(true)
    }
  })
})
