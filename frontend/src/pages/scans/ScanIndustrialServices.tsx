import IndustrialServices from '@/pages/hosts/IndustrialServices'
import type { components } from '@/types/openapi'

type ScanHost = components['schemas']['ScanHostView']

function machineName(host: ScanHost): string {
  return host.hostname || host.ip
}

function ScanIndustrialServices({ hosts }: { hosts: ScanHost[] }) {
  const industrialHosts = hosts.filter(
    (host) => host.industrial_services.length > 0,
  )

  if (industrialHosts.length === 0) return null

  return (
    <div data-testid="scan-industrial-services" className="flex flex-col gap-8">
      {industrialHosts.map((host) => (
        <section
          key={host.host_id}
          data-testid={`scan-industrial-host-${host.host_id}`}
          className="flex flex-col gap-4 border-b border-rule pb-8 last:border-b-0 last:pb-0"
        >
          <div>
            <h3 className="text-title-xs">{machineName(host)}</h3>
            <p className="font-mono text-caption-md text-muted-foreground">
              {host.ip}
            </p>
          </div>
          <IndustrialServices services={host.industrial_services} />
        </section>
      ))}
    </div>
  )
}

export default ScanIndustrialServices
