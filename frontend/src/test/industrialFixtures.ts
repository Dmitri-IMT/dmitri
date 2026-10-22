import type { components } from '@/types/openapi'

type IndustrialService = components['schemas']['IndustrialServiceView']
type OpcUaRead = Extract<
  components['schemas']['ScanHostView']['industrial_services'][number],
  { protocol: 'opcua_tcp' }
>

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

export const confirmedOpcUaService: OpcUaRead = {
  protocol: 'opcua_tcp',
  port: 4840,
  confidence: 'confirmed',
  evidence_sources: ['opcua_inspection'],
  observation: {
    schema_version: 1,
    inventory_phase: {
      status: 'completed',
      reason_codes: [],
      truncated: false,
      observed_at: '2026-10-22T00:00:00Z',
    },
    identity: {
      application_name: '<img src=x onerror=alert(1)>',
      application_uri: null,
      product_uri: null,
      application_type: 'Server',
    },
    certificate_sha256: 'CERTIFICATE_SENTINEL_MUST_NOT_RENDER',
    endpoints: [
      {
        endpoint_url: 'opc.tcp://secret.invalid/path?token=hidden',
        security_policy_uri: 'http://opcfoundation.org/UA/SecurityPolicy#None',
        security_mode: 'None',
        transport_profile_uri: 'urn:transport',
        security_level: 0,
        user_token_count: 1,
        user_token_types: ['Anonymous'],
        target_matches: true,
      },
    ],
    mapping: {
      phase: {
        status: 'partial',
        reason_codes: ['node_limit'],
        truncated: true,
        observed_at: '2026-10-22T00:00:00Z',
      },
      nodes: [
        {
          node_id: 'ns=2;s=temperature',
          depth: 1,
          node_class: 'Variable',
          browse_name: '<b>Temp</b>',
          display_name: '<script>bad</script>',
          data_type: 'Float',
          value_read_status: 'Good',
        },
      ],
      references_observed: 1,
      value_reads_attempted: 1,
      selected_endpoint_index: 0,
      anonymous_session_activated: true,
      browse_succeeded: false,
      application_value_read_succeeded: null,
      value_good_count: 1,
      security_mode: { value: 'None', source: 'get_endpoints', status: 'Good' },
      security_policy: {
        value: 'None',
        source: 'get_endpoints',
        status: 'Good',
      },
    },
  },
}
