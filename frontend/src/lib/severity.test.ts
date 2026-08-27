import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { bySeverityDesc } from './severity'

type Severity = components['schemas']['Severity']

interface FindingStub {
  id: string
  severity: Severity
}

describe('bySeverityDesc', () => {
  it('orders findings from critical through low', () => {
    const findings: FindingStub[] = [
      { id: 'low', severity: 'low' },
      { id: 'high', severity: 'high' },
      { id: 'medium', severity: 'medium' },
      { id: 'critical', severity: 'critical' },
    ]

    expect(findings.sort(bySeverityDesc).map(({ id }) => id)).toEqual([
      'critical',
      'high',
      'medium',
      'low',
    ])
  })

  it('keeps the input order when severities tie', () => {
    const findings: FindingStub[] = [
      { id: 'first-critical', severity: 'critical' },
      { id: 'low', severity: 'low' },
      { id: 'second-critical', severity: 'critical' },
    ]

    expect(findings.sort(bySeverityDesc).map(({ id }) => id)).toEqual([
      'first-critical',
      'second-critical',
      'low',
    ])
  })
})
