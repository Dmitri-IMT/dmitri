import DataTable from '@/components/DataTable'
import { portColumns } from '@/pages/hosts/portColumns'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type HostPort = components['schemas']['HostPort']

function HostPortsTable({ ports }: { ports: HostPort[] }) {
  const { t } = useI18n()
  if (ports.length === 0) {
    return (
      <p data-testid="host-no-ports" className="text-body-md">
        {t('common.noServices')}
      </p>
    )
  }

  return (
    <DataTable
      columns={portColumns(t)}
      rows={ports}
      rowId={(port) => `${port.port}/${port.protocol}`}
      testId="host-ports-table"
      caption={t('common.servicesRunning')}
    />
  )
}

export default HostPortsTable
