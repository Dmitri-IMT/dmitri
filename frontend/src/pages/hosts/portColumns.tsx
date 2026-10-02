import type { DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'
import type { MessageKey } from '@/i18n/messages'

type HostPort = components['schemas']['HostPort']

export function portColumns(
  t: (key: MessageKey) => string,
): DataTableColumn<HostPort>[] {
  return [
    {
      key: 'service',
      label: t('common.service'),
      width: 'w-17/50',
      render: (port) => (
        <>
          <span className="block truncate" title={port.service}>
            {port.service}
          </span>
          <span className="block truncate font-mono text-muted-foreground">
            {port.port}
          </span>
          <span className="block text-body-sm text-muted-foreground">
            {t(
              port.observed_in_latest_scan === true
                ? 'scans.currentPort'
                : port.observed_in_latest_scan === false
                  ? 'scans.historicalPort'
                  : 'scans.unknownPort',
            )}
          </span>
        </>
      ),
    },
    {
      key: 'protocol',
      label: t('common.protocol'),
      width: 'w-7/50',
      render: (port) => port.protocol,
    },
    {
      key: 'version',
      label: t('common.version'),
      width: 'w-3/10',
      render: (port) =>
        port.version ? (
          <span className="block truncate" title={port.version}>
            {port.version}
          </span>
        ) : (
          <EmptyMark />
        ),
    },
    {
      key: 'last_seen_at',
      label: t('common.lastSeen'),
      width: 'w-11/50',
      render: (port) => <Timestamp value={port.last_seen_at} />,
    },
  ]
}
