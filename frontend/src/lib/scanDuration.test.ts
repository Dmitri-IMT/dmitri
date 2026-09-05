import { describe, expect, it } from 'vitest'
import { formatScanDuration } from './scanDuration'

describe('formatScanDuration', () => {
  it('renders seconds under one minute', () => {
    expect(formatScanDuration(45)).toBe('45s')
    expect(formatScanDuration(59)).toBe('59s')
  })

  it('renders whole minutes from 60 seconds', () => {
    expect(formatScanDuration(60)).toBe('1 min')
    expect(formatScanDuration(500)).toBe('8 min')
  })

  it('returns null when duration is absent', () => {
    expect(formatScanDuration(null)).toBeNull()
    expect(formatScanDuration(undefined)).toBeNull()
  })
})
