import AttentionWord from '@/components/AttentionWord'
import type { DataTableColumn } from '@/components/DataTable'
import type { MessageKey } from '@/i18n/messages'
import type { components } from '@/types/openapi'

type ExposureRead = components['schemas']['ExposureRead']
type ExposureRole = components['schemas']['ExposureRole']
type ExposureConfidence = components['schemas']['ExposureConfidence']

const ROLE_LABEL: Record<ExposureRole, MessageKey> = {
  administration: 'scans.exposureRoleAdministration',
  data_store: 'scans.exposureRoleDataStore',
  file_sharing: 'scans.exposureRoleFileSharing',
  remote_access: 'scans.exposureRoleRemoteAccess',
  proxy: 'scans.exposureRoleProxy',
  api: 'scans.exposureRoleApi',
  device_control: 'scans.exposureRoleDeviceControl',
  discovery: 'scans.exposureRoleDiscovery',
  media: 'scans.exposureRoleMedia',
  general_service: 'scans.exposureRoleGeneralService',
  unknown: 'scans.exposureRoleUnknown',
}

const CONFIDENCE_LABEL: Record<ExposureConfidence, MessageKey> = {
  low: 'scans.exposureConfidenceLow',
  medium: 'scans.exposureConfidenceMedium',
  high: 'scans.exposureConfidenceHigh',
}

export function exposureEndpoint(exposure: ExposureRead): string {
  return `${exposure.ip}:${exposure.port}/${exposure.protocol}`
}

export function exposureColumns(
  t: (key: MessageKey, variables?: Record<string, string | number>) => string,
): DataTableColumn<ExposureRead>[] {
  return [
    {
      key: 'endpoint',
      label: t('scans.exposureEndpoint'),
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
      label: t('scans.exposureObservedService'),
      width: 'w-1/5',
      render: (exposure) => (
        <span className="block truncate" title={exposure.observed_service}>
          {exposure.observed_service}
        </span>
      ),
    },
    {
      key: 'role',
      label: t('scans.exposureRole'),
      width: 'w-1/5',
      render: (exposure) => t(ROLE_LABEL[exposure.role]),
    },
    {
      key: 'attention',
      label: t('scans.exposureAttention'),
      width: 'w-1/5',
      render: (exposure) => <AttentionWord attention={exposure.attention} />,
    },
    {
      key: 'confidence',
      label: t('common.confidence'),
      width: 'w-3/20',
      render: (exposure) => t(CONFIDENCE_LABEL[exposure.confidence]),
    },
  ]
}
