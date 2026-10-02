import { describe, expect, it } from 'vitest'
import { evidenceLimitKey } from './evidenceCompleteness'

describe('evidenceLimitKey', () => {
  it('adds a limit line for partial and unknown evidence only', () => {
    expect(evidenceLimitKey('partial')).toBe('ai.partialLimit')
    expect(evidenceLimitKey('unknown')).toBe('ai.unknownLimit')
    expect(evidenceLimitKey('complete')).toBeNull()
  })
})
