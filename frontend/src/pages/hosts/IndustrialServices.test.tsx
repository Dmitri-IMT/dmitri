import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import IndustrialServices from './IndustrialServices'
import {
  confirmedModbusService,
  confirmedOpcUaService,
} from '@/test/industrialFixtures'
import { catalog as ptCatalog } from '@/i18n/messages/pt-BR'
import { catalog as ruCatalog } from '@/i18n/messages/ru'

describe('IndustrialServices', () => {
  it('explains when no industrial protocol was detected', () => {
    render(<IndustrialServices services={[]} />)
    expect(screen.getByTestId('no-industrial-services')).toHaveTextContent(
      'No industrial services were detected',
    )
  })

  it('shows Modbus evidence, identity and read-only mapping summaries', () => {
    render(<IndustrialServices services={[confirmedModbusService]} />)

    const service = screen.getByTestId('industrial-service-502')
    expect(service).toHaveTextContent('Modbus TCP · port 502')
    expect(service).toHaveTextContent('confirmed')
    expect(service).toHaveTextContent('tcp-port, pymodbus')
    expect(service).toHaveTextContent('generic baseline')
    expect(service).toHaveTextContent('Schneider Electric · TM221CE16T · V1.0')

    const table = within(service).getByRole('table', {
      name: 'Address space',
    })
    expect(table).toHaveTextContent('holding register')
    expect(table).toHaveTextContent('0–3')
    expect(table).toHaveTextContent('readable')
    expect(table).toHaveTextContent('illegal address (exception 2)')
    expect(table).not.toHaveTextContent('0, 10, 0, 42')
  })

  it('dispatches OPC UA without treating announcement, session, Browse and Value as the same fact', async () => {
    const user = (await import('@testing-library/user-event')).default.setup()
    render(
      <IndustrialServices
        services={[confirmedModbusService, confirmedOpcUaService]}
      />,
    )
    const service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent('Anonymous access advertised')
    expect(service).toHaveTextContent('Anonymous session accepted')
    expect(service).toHaveTextContent('Browse not confirmed')
    expect(service).toHaveTextContent('Not tested (1)')
    expect(service).not.toHaveTextContent('secret.invalid')
    expect(service).not.toHaveTextContent('token=hidden')
    expect(service).not.toHaveTextContent(
      'CERTIFICATE_SENTINEL_MUST_NOT_RENDER',
    )
    await user.click(
      within(service).getByRole('button', { name: 'Show observed details' }),
    )
    expect(
      within(service).getByRole('table', { name: 'Observed nodes' }),
    ).toHaveTextContent('<script>bad</script>')
    expect(service.querySelector('script')).toBeNull()
    expect(service).toHaveTextContent('node limit reached')
    expect(screen.getByTestId('industrial-service-502')).toHaveTextContent(
      'Schneider Electric',
    )
  })

  it('keeps UA-only and unreadable observations distinct from Modbus and from a negative result', () => {
    const unreadable = { ...confirmedOpcUaService, observation: null }
    render(<IndustrialServices services={[unreadable]} />)
    expect(screen.getByTestId('industrial-opcua-4840')).toHaveTextContent(
      'OPC UA details are unavailable',
    )
    expect(screen.getByTestId('industrial-opcua-4840')).not.toHaveTextContent(
      'Modbus',
    )
    expect(
      screen.queryByTestId('no-industrial-services'),
    ).not.toBeInTheDocument()
  })

  it('keeps the disclosure closed and operable by keyboard with an accessible relationship', async () => {
    const user = (await import('@testing-library/user-event')).default.setup()
    render(<IndustrialServices services={[confirmedOpcUaService]} />)

    const trigger = screen.getByRole('button', {
      name: 'Show observed details',
    })
    const panelId = trigger.getAttribute('aria-controls')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(panelId).toBeTruthy()
    expect(document.getElementById(panelId!)).not.toBeVisible()

    trigger.focus()
    await user.keyboard('{Enter}')
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(document.getElementById(panelId!)).toBeVisible()
    await user.keyboard(' ')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows secure-only inventory and denied or untested outcomes without exposing endpoint data', async () => {
    const secureOnly = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        endpoints: [
          {
            ...confirmedOpcUaService.observation!.endpoints[0],
            endpoint_url: 'opc.tcp://secure-secret.invalid/private',
            security_policy_uri:
              'http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256',
            security_mode: 'SignAndEncrypt' as const,
            user_token_types: ['UserName' as const],
          },
        ],
        mapping: {
          ...confirmedOpcUaService.observation!.mapping!,
          phase: {
            status: 'skipped' as const,
            reason_codes: ['security_configuration_required' as const],
            truncated: false,
            observed_at: '2026-10-22T00:00:00Z',
          },
          anonymous_session_activated: null,
          browse_succeeded: null,
          application_value_read_succeeded: null,
          value_good_count: 0,
        },
      },
    }
    render(<IndustrialServices services={[secureOnly]} />)

    const service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent(
      'Secure endpoint advertised; mapping unavailable in this version',
    )
    expect(service).toHaveTextContent('Not tested')
    expect(service).toHaveTextContent('Not tested')
    expect(service).toHaveTextContent('security configuration required')
    expect(service).toHaveTextContent(
      '1 · Secure endpoints are included in inventory',
    )
    expect(service).not.toHaveTextContent('secure-secret.invalid')
    const user = (await import('@testing-library/user-event')).default.setup()
    await user.click(
      within(service).getByRole('button', { name: 'Show observed details' }),
    )
    expect(service).toHaveTextContent('Security policy')
    expect(service).toHaveTextContent('Basic256Sha256')
    expect(service).toHaveTextContent('Security mode')
    expect(service).toHaveTextContent('Sign and encrypt')
    expect(service).toHaveTextContent('User token types')
    expect(service).toHaveTextContent('User name')
    expect(service).not.toHaveTextContent('opcfoundation.org')
    expect(service).not.toHaveTextContent(
      'CERTIFICATE_SENTINEL_MUST_NOT_RENDER',
    )
  })

  it('distinguishes authentication requirements from secure transport and unknown endpoint policy', () => {
    const endpoint = confirmedOpcUaService.observation!.endpoints[0]
    const authRequired = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        endpoints: [
          {
            ...endpoint,
            security_mode: 'None' as const,
            user_token_types: ['UserName' as const],
          },
        ],
        mapping: null,
      },
    }
    const unknown = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        endpoints: [
          {
            ...endpoint,
            security_policy_uri: 'https://example.invalid/policy#PrivatePolicy',
          },
        ],
        mapping: null,
      },
    }
    const { unmount } = render(<IndustrialServices services={[authRequired]} />)
    let service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent(
      'Authentication required by advertised endpoint',
    )
    expect(service).not.toHaveTextContent('Secure endpoint advertised')
    expect(service).toHaveTextContent('User name')
    unmount()

    render(<IndustrialServices services={[unknown]} />)
    service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent(
      'Endpoint security configuration is unknown or inconsistent',
    )
    expect(service).toHaveTextContent('Unknown policy')
    expect(service).not.toHaveTextContent('example.invalid')
    expect(service).not.toHaveTextContent('PrivatePolicy')
  })

  it('lists security facts for both anonymous and secure endpoints in a mixed inventory', async () => {
    const endpoints = confirmedOpcUaService.observation!.endpoints
    const secureEndpoint = {
      ...endpoints[0],
      security_policy_uri:
        'http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256',
      security_mode: 'SignAndEncrypt' as const,
      user_token_types: ['UserName' as const],
    }
    render(
      <IndustrialServices
        services={[
          {
            ...confirmedOpcUaService,
            observation: {
              ...confirmedOpcUaService.observation!,
              endpoints: [endpoints[0], secureEndpoint],
            },
          },
        ]}
      />,
    )
    const service = screen.getByTestId('industrial-opcua-4840')
    const user = (await import('@testing-library/user-event')).default.setup()
    await user.click(
      within(service).getByRole('button', { name: 'Show observed details' }),
    )
    expect(service).toHaveTextContent('Anonymous access advertised')
    expect(service).toHaveTextContent(
      '2 · Secure endpoints are included in inventory',
    )
    expect(service).toHaveTextContent('None')
    expect(service).toHaveTextContent('Anonymous')
    expect(service).toHaveTextContent('Basic256Sha256')
    expect(service).toHaveTextContent('Sign and encrypt')
    expect(service).toHaveTextContent('User name')
  })

  it('distinguishes inventory-only observations from a denied anonymous session', () => {
    const inventoryOnly = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        mapping: null,
      },
    }
    const { unmount } = render(
      <IndustrialServices services={[inventoryOnly]} />,
    )
    const inventory = screen.getByTestId('industrial-opcua-4840')
    expect(inventory).toHaveTextContent('Mapping not requested')
    expect(inventory).toHaveTextContent('Anonymous access advertised')
    expect(inventory).toHaveTextContent('Not tested')
    unmount()

    const denied = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        mapping: {
          ...confirmedOpcUaService.observation!.mapping!,
          phase: {
            status: 'partial' as const,
            reason_codes: ['anonymous_denied' as const],
            truncated: false,
            observed_at: '2026-10-22T00:00:00Z',
          },
          anonymous_session_activated: false,
          browse_succeeded: null,
          application_value_read_succeeded: null,
          value_good_count: 0,
        },
      },
    }
    render(<IndustrialServices services={[denied]} />)
    const deniedService = screen.getByTestId('industrial-opcua-4840')
    expect(deniedService).toHaveTextContent('Anonymous session denied')
    expect(deniedService).toHaveTextContent('Not tested')
    expect(deniedService).toHaveTextContent('anonymous access denied')
    expect(deniedService).not.toHaveTextContent(
      'This confirms anonymous read capability for the observed sample only.',
    )
  })

  it('shows inventory timeout and limits when mapping was not requested', () => {
    const inventoryTimeout = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        inventory_phase: {
          status: 'timed_out' as const,
          reason_codes: ['endpoint_limit' as const],
          truncated: true,
          observed_at: '2026-10-22T00:00:00Z',
        },
        endpoints: [],
        mapping: null,
      },
    }
    render(<IndustrialServices services={[inventoryTimeout]} />)
    const service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent('Timed out')
    expect(service).toHaveTextContent('Partial sample')
    expect(service).toHaveTextContent('endpoint limit reached')
    expect(service).toHaveTextContent('Mapping not requested')
    expect(service).not.toHaveTextContent('anonymous read capability')
  })

  it('shows partial inventory status and localized reasons without mapping', () => {
    const partialInventory = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        inventory_phase: {
          status: 'partial' as const,
          reason_codes: ['endpoint_limit' as const],
          truncated: false,
          observed_at: '2026-10-22T00:00:00Z',
        },
        mapping: null,
      },
    }
    render(<IndustrialServices services={[partialInventory]} />)
    const service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent('Partial')
    expect(service).toHaveTextContent('endpoint limit reached')
    expect(service).toHaveTextContent('Mapping not requested')
    expect(service).not.toHaveTextContent('anonymous read capability')
  })

  it('makes a successful Value-read claim only when its success flag and count agree', async () => {
    const user = (await import('@testing-library/user-event')).default.setup()
    const inconsistent = {
      ...confirmedOpcUaService,
      observation: {
        ...confirmedOpcUaService.observation!,
        mapping: {
          ...confirmedOpcUaService.observation!.mapping!,
          application_value_read_succeeded: true,
          value_good_count: 0,
        },
      },
    }
    const { rerender } = render(
      <IndustrialServices services={[inconsistent]} />,
    )
    let service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent('Not tested (0)')
    await user.click(
      within(service).getByRole('button', { name: 'Show observed details' }),
    )
    expect(service).not.toHaveTextContent(
      'This confirms anonymous read capability for the observed sample only.',
    )

    const successful = {
      ...inconsistent,
      observation: {
        ...inconsistent.observation,
        mapping: {
          ...inconsistent.observation.mapping!,
          value_good_count: 1,
        },
      },
    }
    rerender(<IndustrialServices services={[successful]} />)
    service = screen.getByTestId('industrial-opcua-4840')
    expect(service).toHaveTextContent('Anonymous Value read succeeded (1)')
    expect(service).toHaveTextContent(
      'This confirms anonymous read capability for the observed sample only.',
    )
  })

  it('uses valid Unicode in Portuguese and Russian OPC UA labels', () => {
    expect(ptCatalog['industrial.opcua.unconfirmed']).toBe(
      'Serviço OPC UA não confirmado',
    )
    expect(
      (
        ptCatalog['industrial.opcua.title'] as (
          v: Record<string, string | number>,
        ) => string
      )({ port: 4840 }),
    ).toBe('OPC UA · porta 4840')
    expect(ruCatalog['industrial.opcua.unconfirmed']).toBe(
      'Служба OPC UA не подтверждена',
    )
    expect(
      (
        ruCatalog['industrial.opcua.title'] as (
          v: Record<string, string | number>,
        ) => string
      )({ port: 4840 }),
    ).toBe('OPC UA · порт 4840')
  })
})
