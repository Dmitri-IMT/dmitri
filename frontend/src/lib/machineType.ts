import type { components } from '@/types/openapi'

type MachineType = components['schemas']['MachineType']

export const MACHINE_TYPE_LABELS: Record<MachineType, string | null> = {
  router: 'Router',
  computer: 'Computer',
  camera: 'Camera',
  storage: 'Storage',
  tv: 'TV',
  phone: 'Phone',
  printer: 'Printer',
  sensor: 'Sensor',
  unknown: null,
}
