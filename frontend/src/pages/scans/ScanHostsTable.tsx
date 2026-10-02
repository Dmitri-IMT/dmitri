import DataTable, { type DataTableColumn } from '@/components/DataTable'
import EmptyMark from '@/components/EmptyMark'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type ScanHostView = components['schemas']['ScanHostView']

function machineName(host: ScanHostView): string {
  return host.hostname !== '' ? host.hostname : host.ip
}

function buildColumns(
  t: ReturnType<typeof useI18n>['t'],
): DataTableColumn<ScanHostView>[] {
  return [
    {
      key: 'hostname',
      label: t('common.machine'),
      width: 'w-6/25',
      render: (host) => {
        const name = machineName(host)
        return (
          <span className="block truncate" title={name}>
            {name}
          </span>
        )
      },
    },
    {
      key: 'ip',
      label: t('common.address'),
      width: 'w-9/50',
      render: (host) => (
        <span className="block truncate font-mono" title={host.ip}>
          {host.ip}
        </span>
      ),
    },
    {
      key: 'mac',
      label: t('common.mac'),
      width: 'w-11/50',
      render: (host) =>
        host.mac ? (
          <span className="block truncate font-mono" title={host.mac}>
            {host.mac}
          </span>
        ) : (
          <EmptyMark />
        ),
    },
    {
      key: 'vendor',
      label: t('common.vendor'),
      width: 'w-11/50',
      render: (host) => (
        <span className="block truncate" title={host.vendor}>
          {host.vendor}
        </span>
      ),
    },
    {
      key: 'ports',
      label: t('common.services'),
      width: 'w-7/50',
      align: 'right',
      render: (host) => {
        const open = host.ports.filter((port) => port.state === 'open').length
        const filtered = host.ports.filter(
          (port) => port.state === 'filtered',
        ).length
        return (
          <span className="block tabular-nums">
            {t('scans.openPorts')}: {open}
            {filtered > 0 && `, ${t('scans.filteredPorts')}: ${filtered}`}
          </span>
        )
      },
    },
  ]
}

function ScanHostsTable({ hosts }: { hosts: ScanHostView[] }) {
  const { t } = useI18n()
  return (
    <DataTable
      columns={buildColumns(t)}
      rows={hosts}
      rowId={(host) => host.host_id}
      testId="scan-hosts-table"
      caption={t('common.machinesSeen')}
      rowAction={{
        kind: 'link',
        to: (host) => `/network/${host.host_id}`,
        label: (host) => `Open ${machineName(host)}`,
      }}
    />
  )
}

export default ScanHostsTable
