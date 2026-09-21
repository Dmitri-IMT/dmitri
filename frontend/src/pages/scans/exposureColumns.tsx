import AttentionWord from '@/components/AttentionWord'
import type { DataTableColumn } from '@/components/DataTable'
import type { components } from '@/types/openapi'

type ExposureRead = components['schemas']['ExposureRead']
type ExposureRole = components['schemas']['ExposureRole']
type ExposureConfidence = components['schemas']['ExposureConfidence']

const ROLE_LABEL: Record<ExposureRole, string> = {
  administration: 'Administration',
  data_store: 'Data store',
  file_sharing: 'File sharing',
  remote_access: 'Remote access',
  proxy: 'Proxy',
  api: 'API',
  device_control: 'Device control',
  discovery: 'Discovery',
  media: 'Media',
  general_service: 'General service',
  unknown: 'Unknown',
}

const CONFIDENCE_LABEL: Record<ExposureConfidence, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
}

export function exposureEndpoint(exposure: ExposureRead): string {
  return `${exposure.ip}:${exposure.port}/${exposure.protocol}`
}

export function exposureColumns(): DataTableColumn<ExposureRead>[] {
  return [
    {
      key: 'endpoint',
      label: 'Endpoint',
      width: 'w-1/4',
      render: (exposure) => (
        <span
          className="block truncate font-mono"
          title={exposureEndpoint(exposure)}
        >
          {exposureEndpoint(exposure)}
        </span>
      ),
    },
    {
      key: 'service',
      label: 'Observed service',
      width: 'w-1/5',
      render: (exposure) => (
        <span className="block truncate" title={exposure.observed_service}>
          {exposure.observed_service}
        </span>
      ),
    },
    {
      key: 'role',
      label: 'Role',
      width: 'w-1/5',
      render: (exposure) => ROLE_LABEL[exposure.role],
    },
    {
      key: 'attention',
      label: 'Attention',
      width: 'w-1/5',
      render: (exposure) => <AttentionWord attention={exposure.attention} />,
    },
    {
      key: 'confidence',
      label: 'Confidence',
      width: 'w-3/20',
      render: (exposure) => CONFIDENCE_LABEL[exposure.confidence],
    },
  ]
}
