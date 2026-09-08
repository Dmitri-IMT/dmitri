import DataTable from '@/components/DataTable'
import { portColumns } from '@/pages/hosts/portColumns'
import type { components } from '@/types/openapi'

type Port = components['schemas']['Port']

function HostPortsTable({ ports }: { ports: Port[] }) {
  if (ports.length === 0) {
    return (
      <p data-testid="host-no-ports" className="text-body-md">
        No services are running on this machine.
      </p>
    )
  }

  return (
    <DataTable
      columns={portColumns}
      rows={ports}
      rowId={(port) => `${port.port}/${port.protocol}`}
      testId="host-ports-table"
      caption="Services running on this machine"
    />
  )
}

export default HostPortsTable
