import { describe, expect, it } from 'vitest'
import { MACHINE_TYPE_LABELS } from '@/lib/machineType'

describe('MACHINE_TYPE_LABELS', () => {
  it('draws unknown as absent', () => {
    expect(MACHINE_TYPE_LABELS.unknown).toBeNull()
  })

  it('names the known machine kinds', () => {
    expect(MACHINE_TYPE_LABELS.camera).toBe('Camera')
    expect(MACHINE_TYPE_LABELS.router).toBe('Router')
  })
})
