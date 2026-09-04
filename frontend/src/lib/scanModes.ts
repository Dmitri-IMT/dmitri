import type { components } from '@/types/openapi'

type ScanMode = components['schemas']['ScanMode']

export const SCAN_MODE_ORDER: readonly ScanMode[] = [
  'quick',
  'standard',
  'extensive',
  'max',
  'nspi',
]

export const SCAN_MODE_LABEL: Record<ScanMode, string> = {
  quick: 'Quick',
  standard: 'Standard',
  extensive: 'Extensive',
  nspi: 'NSPi',
  max: 'Max',
}

export const SCAN_MODE_DESCRIPTION: Record<ScanMode, string> = {
  quick:
    'Checks the 1000 most-used connection points on each device for known vulnerabilities. About 2–5 minutes.',
  standard:
    'Same 1000 connection points, and also inspects the common services — file sharing, remote login, web — for weak settings. About 5–10 minutes.',
  extensive:
    'Checks the 10,000 most-used connection points, adds certificate and encryption checks, and reports lower-severity problems as well. About 20–35 minutes.',
  max: 'Checks every connection point on every device and reports everything it finds, however small. 45 minutes or more.',
  nspi: 'For networks with industrial equipment: checks the control-system connection points (Modbus, OPC UA, EtherNet/IP) plus Windows remote-access ones. About 20–30 minutes.',
}

export const DEFAULT_SCAN_MODE: ScanMode = 'standard'
