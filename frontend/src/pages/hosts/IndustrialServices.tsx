import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'
import Disclosure from '@/components/Disclosure'
import type { MessageKey } from '@/i18n/messages/catalog.types'

type IndustrialService =
  components['schemas']['ScanHostView']['industrial_services'][number]
type OpcUaService = Extract<IndustrialService, { protocol: 'opcua_tcp' }>
type ModbusUnit = components['schemas']['ModbusUnitView']
type AddressRange = components['schemas']['ModbusAddressRangeView']
type OpcUaEndpoint = NonNullable<
  OpcUaService['observation']
>['endpoints'][number]
const POLICY_NONE = 'http://opcfoundation.org/UA/SecurityPolicy#None'
const POLICY_BASIC256SHA256 =
  'http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256'

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

function policyLabel(uri: string, t: ReturnType<typeof useI18n>['t']): string {
  if (uri === POLICY_NONE) return t('industrial.opcua.policyNone')
  if (uri === POLICY_BASIC256SHA256)
    return t('industrial.opcua.policyBasic256Sha256')
  return t('industrial.opcua.unknownPolicy')
}

function isConsistentEndpoint(endpoint: OpcUaEndpoint): boolean {
  if (endpoint.user_token_types.length === 0) return false
  if (endpoint.security_policy_uri === POLICY_NONE)
    return endpoint.security_mode === 'None'
  if (endpoint.security_policy_uri === POLICY_BASIC256SHA256)
    return endpoint.security_mode !== 'None'
  return false
}

function Unit({
  unit,
  t,
}: {
  unit: ModbusUnit
  t: ReturnType<typeof useI18n>['t']
}) {
  const identity = identification(unit)

  return (
    <section
      data-testid={`modbus-unit-${unit.unit_id}`}
      className="flex flex-col gap-3 border-t border-dashed border-border pt-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-body-md font-medium">
          {t('common.unit', { id: unit.unit_id })}
        </h4>
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
            <caption className="sr-only">{t('common.addressSpace')}</caption>
            <thead>
              <tr className="border-b border-dashed border-border text-muted-foreground uppercase">
                <th className="w-1/3 pr-4 font-normal">
                  {t('common.addressSpace')}
                </th>
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

function OpcUa({ service }: { service: OpcUaService }) {
  const { t } = useI18n()
  const observation = service.observation
  const mapping = observation?.mapping
  const inventory = observation?.inventory_phase
  const confirmedValueReads =
    mapping?.application_value_read_succeeded === true &&
    mapping.value_good_count > 0 &&
    mapping.nodes.some((node) => node.value_read_status === 'Good')
  const valueReadResult =
    mapping?.application_value_read_succeeded === false
      ? false
      : confirmedValueReads
        ? true
        : null
  const anonymousEligible = (endpoint: OpcUaEndpoint) =>
    endpoint.security_policy_uri === POLICY_NONE &&
    endpoint.security_mode === 'None' &&
    endpoint.user_token_types.includes('Anonymous')
  const endpoints = observation?.endpoints ?? []
  const hasAnonymousEndpoint = endpoints.some(anonymousEligible)
  const hasSecureEndpoint = endpoints.some(
    (endpoint) =>
      isConsistentEndpoint(endpoint) && endpoint.security_mode !== 'None',
  )
  const hasUnknownConfiguration = endpoints.some(
    (endpoint) => !isConsistentEndpoint(endpoint),
  )
  const hasAuthenticationRequiredEndpoint = endpoints.some(
    (endpoint) =>
      endpoint.security_policy_uri === POLICY_NONE &&
      endpoint.security_mode === 'None' &&
      endpoint.user_token_types.length > 0 &&
      !endpoint.user_token_types.includes('Anonymous'),
  )
  const fact = (
    value: boolean | null | undefined,
    yes: MessageKey,
    no: MessageKey,
  ) => (value == null ? t('industrial.opcua.notTested') : t(value ? yes : no))

  if (service.confidence === 'suspected')
    return (
      <article data-testid={`industrial-opcua-${service.port}`}>
        <h3 className="text-title-xs">
          {t('industrial.opcua.title', { port: service.port })}
        </h3>
        <p>{t('industrial.opcua.unconfirmed')}</p>
      </article>
    )
  if (!observation || observation.inventory_phase.status === 'failed')
    return (
      <article data-testid={`industrial-opcua-${service.port}`}>
        <h3 className="text-title-xs">
          {t('industrial.opcua.title', { port: service.port })}
        </h3>
        <p>{t('industrial.opcua.detailsUnavailable')}</p>
      </article>
    )

  return (
    <article
      data-testid={`industrial-opcua-${service.port}`}
      className="flex flex-col gap-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-title-xs">
          {t('industrial.opcua.title', { port: service.port })}
        </h3>
        <span className="text-caption-md uppercase text-muted-foreground">
          {t('industrial.opcua.confirmed')}
        </span>
      </div>
      {hasAnonymousEndpoint && <p>{t('industrial.opcua.advertised')}</p>}
      {!hasAnonymousEndpoint &&
        endpoints.length > 0 &&
        hasSecureEndpoint &&
        !hasUnknownConfiguration && <p>{t('industrial.opcua.secureOnly')}</p>}
      {hasAuthenticationRequiredEndpoint && (
        <p>{t('industrial.opcua.authenticationRequired')}</p>
      )}
      {hasUnknownConfiguration && (
        <p>{t('industrial.opcua.configurationUnknown')}</p>
      )}
      <dl className="grid gap-2 text-caption-md sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">
            {t('industrial.opcua.session')}
          </dt>
          <dd>
            {fact(
              mapping?.anonymous_session_activated,
              'industrial.opcua.sessionAccepted',
              'industrial.opcua.sessionDenied',
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('industrial.opcua.browse')}
          </dt>
          <dd>
            {fact(
              mapping?.browse_succeeded,
              'industrial.opcua.browseCompleted',
              'industrial.opcua.browseDenied',
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('industrial.opcua.valueReads')}
          </dt>
          <dd>
            {fact(
              valueReadResult,
              'industrial.opcua.readSucceeded',
              'industrial.opcua.readDenied',
            )}{' '}
            ({mapping?.value_good_count ?? 0})
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('industrial.opcua.endpoints')}
          </dt>
          <dd>
            {observation.endpoints.length} ·{' '}
            {t('industrial.opcua.secureInventory')}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t('industrial.opcua.mapping')}
          </dt>
          <dd>
            {mapping
              ? t(`industrial.opcua.phase.${mapping.phase.status}`)
              : t('industrial.opcua.mappingNotRequested')}
          </dd>
        </div>
        {inventory && (
          <div>
            <dt className="text-muted-foreground">
              {t('industrial.opcua.inventory')}
            </dt>
            <dd>
              {t(`industrial.opcua.phase.${inventory.status}`)}
              {(inventory.status === 'partial' ||
                inventory.truncated ||
                inventory.reason_codes.length > 0) && (
                <>
                  {inventory.truncated && inventory.status !== 'partial' && (
                    <> {t('industrial.opcua.partial')}</>
                  )}
                  {inventory.reason_codes.map((reason) => (
                    <span key={reason}>
                      {' '}
                      {t(`industrial.opcua.reason.${reason}` as MessageKey)}
                    </span>
                  ))}
                </>
              )}
            </dd>
          </div>
        )}
      </dl>
      <Disclosure
        label={t('industrial.opcua.details')}
        testId={`opcua-details-${service.port}`}
        caretTestId={`opcua-details-caret-${service.port}`}
      >
        <div className="flex flex-col gap-4 pt-2">
          {observation.identity && (
            <dl className="grid gap-2 text-caption-md sm:grid-cols-2">
              {(
                [
                  'application_name',
                  'application_uri',
                  'product_uri',
                  'application_type',
                ] as const
              ).map(
                (field) =>
                  observation.identity?.[field] && (
                    <div key={field}>
                      <dt className="text-muted-foreground">
                        {t(`industrial.opcua.identity.${field}`)}
                      </dt>
                      <dd className="break-words">
                        {observation.identity?.[field]}
                      </dd>
                    </div>
                  ),
              )}
            </dl>
          )}
          {endpoints.length > 0 && (
            <div className="flex flex-col gap-3">
              {endpoints.map((endpoint, index) => (
                <dl
                  key={index}
                  className="grid gap-2 border-t border-dashed border-border pt-3 text-caption-md sm:grid-cols-2"
                >
                  <div>
                    <dt className="text-muted-foreground">
                      {t('industrial.opcua.endpointPolicy')}
                    </dt>
                    <dd>{policyLabel(endpoint.security_policy_uri, t)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">
                      {t('industrial.opcua.endpointMode')}
                    </dt>
                    <dd>
                      {t(`industrial.opcua.mode.${endpoint.security_mode}`)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">
                      {t('industrial.opcua.endpointTokens')}
                    </dt>
                    <dd>
                      {endpoint.user_token_types
                        .map((token) => t(`industrial.opcua.token.${token}`))
                        .join(', ') ||
                        t('industrial.opcua.unknownConfiguration')}
                    </dd>
                  </div>
                </dl>
              ))}
            </div>
          )}
          {mapping && (
            <>
              {(mapping.phase.status === 'partial' ||
                mapping.phase.truncated ||
                mapping.phase.reason_codes.length > 0) && (
                <p className="text-caption-md">
                  {t('industrial.opcua.partial')}
                  {mapping.phase.reason_codes.map((reason) => (
                    <span key={reason}>
                      {' '}
                      · {t(`industrial.opcua.reason.${reason}` as MessageKey)}
                    </span>
                  ))}
                </p>
              )}
              {confirmedValueReads && (
                <p className="text-caption-md">
                  {t('industrial.opcua.sampleReadNote')}
                </p>
              )}
              <div className="overflow-x-auto">
                <table className="w-full table-fixed text-left text-caption-md">
                  <caption className="sr-only">
                    {t('industrial.opcua.nodes')}
                  </caption>
                  <thead>
                    <tr className="border-b border-dashed border-border text-muted-foreground uppercase">
                      <th className="pr-4 font-normal">
                        {t('industrial.opcua.name')}
                      </th>
                      <th className="pr-4 font-normal">
                        {t('industrial.opcua.nodeId')}
                      </th>
                      <th className="pr-4 font-normal">
                        {t('industrial.opcua.dataType')}
                      </th>
                      <th className="font-normal">
                        {t('industrial.opcua.readResult')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {mapping.nodes.slice(0, 64).map((node, index) => (
                      <tr
                        key={`${node.node_id}-${index}`}
                        className="h-row border-b border-border last:border-b-0"
                      >
                        <td className="break-words pr-4">
                          {(node.display_name || node.browse_name || '—').slice(
                            0,
                            256,
                          )}
                        </td>
                        <td className="break-all pr-4 font-mono">
                          {node.node_id.slice(0, 256)}
                        </td>
                        <td className="break-words pr-4">
                          {node.data_type?.slice(0, 128) || '—'}
                        </td>
                        <td>
                          {node.value_read_status
                            ? t(
                                `industrial.opcua.readStatus.${node.value_read_status}` as MessageKey,
                              )
                            : t('industrial.opcua.notTested')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </Disclosure>
    </article>
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
      {services.map((service) =>
        service.protocol === 'opcua_tcp' ? (
          <OpcUa
            key={`${service.protocol}-${service.port}`}
            service={service}
          />
        ) : (
          <article
            key={`${service.protocol}-${service.port}`}
            data-testid={`industrial-service-${service.port}`}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-title-xs">
                Modbus TCP · port {service.port}
              </h3>
              <span className="text-caption-md uppercase text-muted-foreground">
                {service.confidence}
              </span>
            </div>

            <dl className="grid gap-2 text-caption-md sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">
                  {t('common.evidence')}
                </dt>
                <dd>{service.evidence_sources.join(', ') || 'Not reported'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">
                  {t('common.mappingSource')}
                </dt>
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
              service.units.map((unit) => (
                <Unit key={unit.unit_id} unit={unit} t={t} />
              ))
            )}
          </article>
        ),
      )}
    </div>
  )
}

export default IndustrialServices
