import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type IndustrialService = components['schemas']['IndustrialServiceView']
type ModbusUnit = components['schemas']['ModbusUnitView']
type AddressRange = components['schemas']['ModbusAddressRangeView']

function words(value: string): string {
  return value.replaceAll('_', ' ')
}

function identification(unit: ModbusUnit): string | null {
  const identity = unit.identification
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
  return range.exception_code == null
    ? words(range.status)
    : `${words(range.status)} (exception ${range.exception_code})`
}

function Unit({ unit, t }: { unit: ModbusUnit; t: ReturnType<typeof useI18n>['t'] }) {
  const identity = identification(unit)

  return (
    <section
      data-testid={`modbus-unit-${unit.unit_id}`}
      className="flex flex-col gap-3 border-t border-dashed border-border pt-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-body-md font-medium">{t('common.unit', { id: unit.unit_id })}</h4>
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
          {t('common.noAddressRanges')}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full table-fixed text-left text-caption-md">
            <caption className="sr-only">
              {t('common.addressSpace')}
            </caption>
            <thead>
              <tr className="border-b border-dashed border-border text-muted-foreground uppercase">
                <th className="w-1/3 pr-4 font-normal">{t('common.addressSpace')}</th>
                <th className="w-1/4 pr-4 font-normal">{t('common.range')}</th>
                <th className="font-normal">{t('common.result')}</th>
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
    </section>
  )
}

function IndustrialServices({ services }: { services: IndustrialService[] }) {
  const { t } = useI18n()
  if (services.length === 0) {
    return (
      <p data-testid="no-industrial-services" className="text-body-md">
        {t('common.noIndustrialServices')}
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
              <dt className="text-muted-foreground">{t('common.evidence')}</dt>
              <dd>{service.evidence_sources.join(', ') || 'Not reported'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t('common.mappingSource')}</dt>
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
            service.units.map((unit) => <Unit key={unit.unit_id} unit={unit} t={t} />)
          )}
        </article>
      ))}
    </div>
  )
}

export default IndustrialServices
