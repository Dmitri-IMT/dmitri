import { describe, expect, it } from 'vitest'
import {
  DEFAULT_SCAN_MODE,
  SCAN_MODE_DESCRIPTION,
  SCAN_MODE_ORDER,
} from '@/lib/scanModes'

const FOUNDATIONS_DESCRIPTIONS = {
  quick:
    'Checks the 1000 most-used connection points on each device for known vulnerabilities. About 2–5 minutes.',
  standard:
    'Same 1000 connection points, and also inspects the common services — file sharing, remote login, web — for weak settings. About 5–10 minutes.',
  extensive:
    'Checks the 10,000 most-used connection points, adds certificate and encryption checks, and reports lower-severity problems as well. Duration depends on the services found and can exceed an hour.',
  max: 'Checks every connection point on every device and reports everything it finds, however small. 45 minutes or more.',
  nspi: 'For networks with industrial equipment: checks the control-system connection points (Modbus, OPC UA, EtherNet/IP) plus Windows remote-access ones. About 20–30 minutes.',
} as const

describe('scanModes', () => {
  it('lists the five tabs in Foundations order', () => {
    expect(SCAN_MODE_ORDER).toEqual([
      'quick',
      'standard',
      'extensive',
      'max',
      'nspi',
    ])
  })

  it('opens on Standard', () => {
    expect(DEFAULT_SCAN_MODE).toBe('standard')
  })

  it.each([['quick'], ['standard'], ['extensive'], ['max'], ['nspi']] as const)(
    'ships the %s description verbatim from FOUNDATIONS',
    (mode) => {
      expect(SCAN_MODE_DESCRIPTION[mode]).toBe(FOUNDATIONS_DESCRIPTIONS[mode])
    },
  )
})
