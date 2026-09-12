import type { components } from '@/types/openapi'

type ModbusService = components['schemas']['ModbusTcpServicePayload']
type ModbusUnit = components['schemas']['ModbusUnitPayload']
type AddressRange = components['schemas']['ModbusAddressRangePayload']

function words(value: string): string {
  return value.replaceAll('_', ' ')
}

function identification(unit: ModbusUnit): string | null {
  const identity = unit.device_identification
  if (!identity) return null

  return (
    [
      identity.vendor_name,
      identity.product_name,
      identity.model_name,
      identity.product_code,
      identity.major_minor_revision,
    ]
      .filter(
        (value, index, values) => value && values.indexOf(value) === index,
      )
      .join(' · ') || null
  )
}

function rangeSummary(range: AddressRange): string {
  if (range.status !== 'readable') {
    return range.exception_code == null
      ? words(range.status)
      : `${words(range.status)} (exception ${range.exception_code})`
  }

  const facts = ['readable']
  if (range.nonzero_count != null) {
    facts.push(`${range.nonzero_count} non-zero`)
  }
  if (range.value_min != null && range.value_max != null) {
    facts.push(`min ${range.value_min}`, `max ${range.value_max}`)
  }
  return facts.join(' · ')
}

function Unit({ unit }: { unit: ModbusUnit }) {
  const identity = identification(unit)

  return (
    <section
      data-testid={`modbus-unit-${unit.unit_id}`}
      className="flex flex-col gap-3 border-t border-dashed border-border pt-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-body-md font-medium">Unit {unit.unit_id}</h4>
        <span className="text-caption-md uppercase text-muted-foreground">
          {words(unit.status)}
        </span>
      </div>

      {identity && <p className="text-body-md">{identity}</p>}
      {unit.error && (
        <p className="text-caption-md text-muted-foreground">{unit.error}</p>
      )}

      {unit.address_ranges.length === 0 ? (
        <p className="text-caption-md text-muted-foreground">
          No address ranges were mapped.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full table-fixed text-left text-caption-md">
            <caption className="sr-only">
              Address ranges mapped for Modbus unit {unit.unit_id}
            </caption>
            <thead>
              <tr className="border-b border-dashed border-border text-muted-foreground uppercase">
                <th className="w-1/3 pr-4 font-normal">Address space</th>
                <th className="w-1/4 pr-4 font-normal">Range</th>
                <th className="font-normal">Result</th>
              </tr>
            </thead>
            <tbody>
              {unit.address_ranges.map((range) => (
                <tr
                  key={`${range.address_space}-${range.start_address}-${range.count}`}
                  className="h-row border-b border-border last:border-b-0"
                >
                  <td className="pr-4">{words(range.address_space)}</td>
                  <td className="pr-4 font-mono">
                    {range.start_address}–
                    {range.start_address + range.count - 1}
                  </td>
                  <td>{rangeSummary(range)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {unit.validations.length > 0 && (
        <p className="text-caption-md text-muted-foreground">
          {unit.validations.length} controlled write validation
          {unit.validations.length === 1 ? '' : 's'} recorded.
        </p>
      )}
    </section>
  )
}

function IndustrialServices({ services }: { services: ModbusService[] }) {
  if (services.length === 0) {
    return (
      <p data-testid="no-industrial-services" className="text-body-md">
        No industrial services were detected on this machine.
      </p>
    )
  }

  return (
    <div data-testid="industrial-services" className="flex flex-col gap-6">
      {services.map((service) => (
        <article
          key={`${service.protocol}-${service.port}`}
          data-testid={`industrial-service-${service.port}`}
          className="flex flex-col gap-4"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-title-xs">Modbus TCP · port {service.port}</h3>
            <span className="text-caption-md uppercase text-muted-foreground">
              {service.confidence}
            </span>
          </div>

          <dl className="grid gap-2 text-caption-md sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Evidence</dt>
              <dd>{service.evidence_sources.join(', ') || 'Not reported'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Mapping source</dt>
              <dd>
                {service.mapping_source
                  ? words(service.mapping_source)
                  : 'Not mapped'}
              </dd>
            </div>
          </dl>

          {service.units.length === 0 ? (
            <p className="text-body-md text-muted-foreground">
              No Modbus units responded.
            </p>
          ) : (
            service.units.map((unit) => <Unit key={unit.unit_id} unit={unit} />)
          )}
        </article>
      ))}
    </div>
  )
}

export default IndustrialServices
