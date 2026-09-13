import type { components } from '@/types/openapi'

type IndustrialService = components['schemas']['IndustrialServiceView']

export const confirmedModbusService: IndustrialService = {
  protocol: 'modbus_tcp',
  port: 502,
  confidence: 'confirmed',
  evidence_sources: ['tcp-port', 'pymodbus'],
  mapping_source: 'generic_baseline',
  units: [
    {
      id: 1,
      unit_id: 1,
      status: 'responding',
      exception_code: null,
      error: null,
      identification: {
        vendor_name: 'Schneider Electric',
        product_code: 'TM221CE16T',
        major_minor_revision: 'V1.0',
        objects: {},
        truncated: false,
      },
      identification_sources: ['pymodbus-fc43'],
      address_ranges: [
        {
          address_space: 'holding_register',
          start_address: 0,
          count: 4,
          status: 'readable',
          observed_at: '2026-09-10T22:17:51Z',
        },
        {
          address_space: 'coil',
          start_address: 8,
          count: 4,
          status: 'illegal_address',
          exception_code: 2,
          observed_at: '2026-09-10T22:17:52Z',
        },
      ],
    },
  ],
}
