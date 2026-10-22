import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { baseURL, agentDetail } from '@/test/agentsHarness'
import { defaultAgent, viewerProfile } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { signedInAs } from '@/test/usersHarness'
import { server } from '@/test/setup'
import type { components } from '@/types/openapi'
import { LanguageProvider } from '@/i18n/LanguageProvider'
import DeviceDetail from './DeviceDetail'

type Availability = components['schemas']['AgentUpdateAvailability']
type Operation = components['schemas']['UpdateOperationView']

const agentRoute = `/devices/${defaultAgent.agent_id}`
const release = {
  release_id: '33333333-3333-4333-8333-333333333333',
  package: 'hardware-agent',
  upstream_version: '1.0.6',
  package_version: '1.0.6-1',
  architecture: 'arm64',
  suite: 'stable',
  sha256: 'a'.repeat(64),
  size_bytes: 100,
  required_protocol_version: 1,
  required_updater_version: 1,
  published_at: '2026-10-01T00:00:00Z',
  release_notes: 'Security and reliability fixes.',
} satisfies components['schemas']['ReleaseSummary']

const available: Availability = {
  availability: 'available',
  release,
  catalogue_checked_at: '2026-10-19T12:00:00Z',
  catalogue_valid_until: '2026-10-26T12:00:00Z',
  device_readiness: 'ready',
}

const requestedOperation: Operation = {
  update_id: '44444444-4444-4444-8444-444444444444',
  agent_id: defaultAgent.agent_id,
  release_id: release.release_id,
  previous_version: '1.0.5',
  previous_package_version: '1.0.5-1',
  target_version: '1.0.6',
  target_package_version: '1.0.6-1',
  observed_version: null,
  observed_package_version: null,
  phase: 'requested',
  local_outcome: null,
  error_code: null,
  actor_display_snapshot: 'admin@example.test',
  requested_at: '2026-10-20T12:00:00Z',
  claimed_at: null,
  local_completed_at: null,
  confirmed_at: null,
  last_contact_at: null,
}

afterEach(() => {
  localStorage.removeItem('dmitri-language')
})

function mockAvailability(value: Availability) {
  server.use(
    http.get(`${baseURL}/agents/:agentId/updates/availability`, () =>
      HttpResponse.json(value),
    ),
  )
}

async function renderDeviceDetail(
  toastDuration?: number,
  expandUpdateSection = true,
) {
  const rendered = renderWithProviders(
    <LanguageProvider>
      <Routes>
        <Route path="/devices/:agentId" element={<DeviceDetail />} />
      </Routes>
    </LanguageProvider>,
    { route: agentRoute, toastDuration },
  )
  if (expandUpdateSection) {
    fireEvent.click(await screen.findByTestId('agent-update-toggle'))
  }
  return rendered
}

describe('Device update section', () => {
  it('starts collapsed, shows an available update badge, and sits between scan and history', async () => {
    agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
    mockAvailability(available)
    await renderDeviceDetail(undefined, false)

    const scanNow = await screen.findByTestId('agents-scan-now')
    const updateSection = await screen.findByTestId('agent-update-section')
    const scanHistory = screen.getByTestId('device-scan-history')
    const toggle = screen.getByTestId('agent-update-toggle')

    expect(
      scanNow.compareDocumentPosition(updateSection) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0)
    expect(
      updateSection.compareDocumentPosition(scanHistory) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(
      screen.getByTestId('agent-update-available-badge'),
    ).toHaveTextContent('Update available')
    expect(screen.getByTestId('agent-update-content')).toHaveAttribute(
      'data-state',
      'closed',
    )

    await userEvent.setup().click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('agent-update-content')).toHaveAttribute(
      'data-state',
      'open',
    )
  })

  it.each([
    [
      'availability',
      'updates/availability',
      'Could not load update availability.',
    ],
    ['history', 'updates', 'Could not load update history.'],
  ])(
    'shows %s read errors in a toast only',
    async (_name, endpoint, message) => {
      server.use(
        http.get(`${baseURL}/agents/:agentId/${endpoint}`, () =>
          HttpResponse.json({}, { status: 503 }),
        ),
      )
      agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
      await renderDeviceDetail()

      expect(await screen.findByTestId('toast')).toHaveTextContent(message)
      expect(
        within(screen.getByTestId('agent-update-section')).queryByText(message),
      ).not.toBeInTheDocument()
    },
  )

  it('keeps a successful request visible when its history refetch fails', async () => {
    agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
    mockAvailability(available)
    let listCalls = 0
    server.use(
      http.post(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json(requestedOperation, { status: 202 }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () =>
        HttpResponse.json(requestedOperation),
      ),
      http.get(`${baseURL}/agents/:agentId/updates`, () => {
        listCalls += 1
        return listCalls === 1
          ? HttpResponse.json({ data: [] })
          : HttpResponse.json({}, { status: 503 })
      }),
    )
    const user = userEvent.setup()
    await renderDeviceDetail()

    await user.click(await screen.findByTestId('agent-update-trigger'))
    await user.click(
      screen.getByRole('button', { name: 'Confirm update to version 1.0.6' }),
    )

    expect(await screen.findByTestId('agent-update-current')).toHaveTextContent(
      'Request accepted',
    )
    expect(
      await screen.findByTestId('agent-update-history-item'),
    ).toHaveTextContent('Request accepted')
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Could not load update history.',
    )
  })

  it('notifies operation read failures while preserving persisted status and deduplicating manual refresh', async () => {
    const active = {
      ...requestedOperation,
      phase: 'installing',
    } satisfies Operation
    let operationFails = true
    let operationCalls = 0
    agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
    server.use(
      http.get(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json({ data: [active] }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () => {
        operationCalls += 1
        return operationFails
          ? HttpResponse.json({}, { status: 503 })
          : HttpResponse.json({ ...active, phase: 'verifying' })
      }),
    )
    mockAvailability(available)
    const user = userEvent.setup()
    await renderDeviceDetail()

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Could not update the remote status of this operation.',
    )
    expect(screen.getByTestId('agent-update-current')).toHaveTextContent(
      'Installing',
    )
    expect(screen.getByTestId('agent-update-history-item')).toHaveTextContent(
      'Installing',
    )

    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    await user.click(screen.getByRole('button', { name: 'Refresh status' }))
    expect(await screen.findByTestId('agent-update-current')).toHaveTextContent(
      'Installing',
    )
    expect(
      screen.queryByText('Could not refresh update status. Try again.'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()

    operationFails = false
    await user.click(screen.getByRole('button', { name: 'Refresh status' }))
    await waitFor(() => expect(operationCalls).toBeGreaterThanOrEqual(3))
    expect(screen.getByTestId('agent-update-current')).toHaveTextContent(
      'Verifying',
    )
    await waitFor(() =>
      expect(screen.queryByTestId('toast')).not.toBeInTheDocument(),
    )
    operationFails = true
    await user.click(screen.getByRole('button', { name: 'Refresh status' }))
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'Could not update the remote status of this operation.',
    )
  })

  it('continues five second operation polling after a failed first read and recovers from history state', async () => {
    vi.useFakeTimers()
    try {
      const active = {
        ...requestedOperation,
        phase: 'installing',
      } satisfies Operation
      const recovered = { ...active, phase: 'verifying' } satisfies Operation
      let operationCalls = 0
      agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
      server.use(
        http.get(`${baseURL}/agents/:agentId/updates`, () =>
          HttpResponse.json({ data: [active] }),
        ),
        http.get(`${baseURL}/agent-updates/:updateId`, () => {
          operationCalls += 1
          return operationCalls < 4
            ? HttpResponse.json({}, { status: 503 })
            : HttpResponse.json(recovered)
        }),
      )
      mockAvailability(available)
      await renderDeviceDetail(60000, false)

      for (
        let attempt = 0;
        attempt < 100 && operationCalls === 0;
        attempt += 1
      ) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(50)
        })
      }
      fireEvent.click(screen.getByTestId('agent-update-toggle'))
      expect(operationCalls).toBe(1)
      expect(screen.getByTestId('agent-update-current')).toHaveTextContent(
        'Installing',
      )
      expect(screen.getByTestId('toast')).toHaveTextContent(
        'Could not update the remote status of this operation.',
      )

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000)
      })
      expect(operationCalls).toBe(2)
      expect(screen.getAllByTestId('toast')).toHaveLength(1)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000)
      })
      expect(operationCalls).toBe(3)
      expect(screen.getAllByTestId('toast')).toHaveLength(1)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000)
      })
      expect(operationCalls).toBe(4)
      expect(screen.getByTestId('agent-update-current')).toHaveTextContent(
        'Verifying',
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('confirms the selected release with one idempotency key and never calls scan actions', async () => {
    const user = userEvent.setup()
    agentDetail({
      ...defaultAgent,
      observed_version: '1.0.5',
      observed_package_version: '1.0.5-1',
      version_observed_at: '2026-10-19T12:00:00Z',
    })
    mockAvailability(available)
    let updateCalls = 0
    const keys: string[] = []
    let requestBody: unknown
    let savedOperation: Operation | null = null
    const scanCalls: string[] = []
    server.use(
      http.post(`${baseURL}/agents/:agentId/updates`, async ({ request }) => {
        updateCalls += 1
        keys.push(request.headers.get('Idempotency-Key') ?? '')
        requestBody = await request.json()
        if (updateCalls === 1) {
          return HttpResponse.json(
            {
              error: {
                code: 'temporarily_unavailable',
                message: '',
                details: {},
              },
            },
            { status: 503 },
          )
        }
        savedOperation = requestedOperation
        return HttpResponse.json(requestedOperation, { status: 202 })
      }),
      http.get(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json({ data: savedOperation ? [savedOperation] : [] }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () =>
        HttpResponse.json(requestedOperation),
      ),
      http.post(`${baseURL}/agents/:agentId/commands`, () => {
        scanCalls.push('start')
        return HttpResponse.json({}, { status: 202 })
      }),
      http.post(`${baseURL}/commands/:commandId/cancel`, () => {
        scanCalls.push('cancel')
        return HttpResponse.json({}, { status: 202 })
      }),
    )

    await renderDeviceDetail()
    await user.click(await screen.findByTestId('agent-update-trigger'))
    expect(
      await screen.findByRole('heading', { name: 'Update this device?' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Update “DMITRI-NSPI-01” to version 1.0.6?'),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Confirm update to version 1.0.6' }),
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      'The update request could not be completed',
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Confirm update to version 1.0.6' }),
    )

    expect(await screen.findByTestId('agent-update-current')).toHaveTextContent(
      'Request accepted',
    )
    expect(requestBody).toEqual({
      release_id: release.release_id,
      expected_observed_version: '1.0.5',
    })
    expect(updateCalls).toBe(2)
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBe(keys[0])
    expect(scanCalls).toEqual([])
  })

  it('keeps viewers read-only and still shows the section for a revoked device', async () => {
    signedInAs(viewerProfile)
    agentDetail({
      ...defaultAgent,
      revoked_at: '2026-10-19T12:00:00Z',
      observed_version: '1.0.5',
    })
    mockAvailability({ ...available, device_readiness: 'revoked' })
    await renderDeviceDetail()

    expect(
      await screen.findByTestId('agent-update-section'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'This revoked device is read-only and cannot be updated.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('agent-update-trigger')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTestId('device-revoked')).toBeInTheDocument(),
    )
  })

  it('does not offer an update while the device is offline and does not promise a queue', async () => {
    agentDetail({ ...defaultAgent, observed_version: '1.0.5', online: false })
    mockAvailability({ ...available, device_readiness: 'offline' })
    await renderDeviceDetail()

    expect(
      await screen.findByText('Offline', { selector: 'dd' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('This device is offline. An update will not be queued.'),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('agent-update-trigger')).not.toBeInTheDocument()
  })

  it('keeps local success separate from remote confirmation', async () => {
    const awaiting = {
      ...requestedOperation,
      phase: 'awaiting_confirmation',
      local_outcome: 'succeeded',
      observed_version: '1.0.6',
      observed_package_version: '1.0.6-1',
      local_completed_at: '2026-10-20T12:10:00Z',
    } satisfies Operation
    server.use(
      http.get(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json({ data: [awaiting] }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () =>
        HttpResponse.json(awaiting),
      ),
    )
    await renderDeviceDetail()

    const current = await screen.findByTestId('agent-update-current')
    expect(current).toHaveTextContent('Awaiting confirmation')
    expect(current).toHaveTextContent('Installed and healthy locally')
    expect(current).toHaveTextContent(
      'Local installation succeeded. Waiting for remote confirmation.',
    )
    expect(current).toHaveTextContent('Device contact has not been reported.')
    expect(current).not.toHaveTextContent('Confirmed')
    expect(current).not.toHaveTextContent('%')
  })

  it('refreshes device version and update availability at explicit refresh and terminal success', async () => {
    const completed = {
      ...requestedOperation,
      phase: 'succeeded',
      local_outcome: 'succeeded',
      observed_version: '1.0.6',
      observed_package_version: '1.0.6-1',
      confirmed_at: '2026-10-20T12:10:00Z',
    } satisfies Operation
    let agent: components['schemas']['AgentDetail'] = {
      ...defaultAgent,
      observed_version: '1.0.5',
      observed_package_version: '1.0.5-1',
      active_update_id: requestedOperation.update_id,
    }
    let operation = requestedOperation
    let updateCompleted = false
    let detailCalls = 0
    let availabilityCalls = 0
    agentDetail(agent)
    server.use(
      http.get(`${baseURL}/agents/:agentId`, () => {
        detailCalls += 1
        return HttpResponse.json(agent)
      }),
      http.get(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json({ data: [operation] }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () =>
        HttpResponse.json(operation),
      ),
      http.get(`${baseURL}/agents/:agentId/updates/availability`, () => {
        availabilityCalls += 1
        return HttpResponse.json(
          updateCompleted
            ? {
                ...available,
                availability: 'up_to_date',
                release: null,
                device_readiness: 'ready',
              }
            : {
                ...available,
                availability: 'available',
                device_readiness: 'busy',
              },
        )
      }),
    )
    const user = userEvent.setup()
    await renderDeviceDetail()

    expect(
      await screen.findByText('1.0.5', { selector: 'dd' }),
    ).toBeInTheDocument()
    const detailsAfterLoad = detailCalls
    const availabilityAfterLoad = availabilityCalls
    await user.click(screen.getByRole('button', { name: 'Refresh status' }))
    await waitFor(() => expect(detailCalls).toBeGreaterThan(detailsAfterLoad))
    expect(availabilityCalls).toBeGreaterThan(availabilityAfterLoad)

    updateCompleted = true
    operation = completed
    agent = {
      ...agent,
      observed_version: '1.0.6',
      observed_package_version: '1.0.6-1',
      active_update_id: null,
    }
    await user.click(screen.getByRole('button', { name: 'Refresh status' }))

    await waitFor(() =>
      expect(
        screen.getAllByText('1.0.6', { selector: 'dd' }).length,
      ).toBeGreaterThan(0),
    )
    expect(
      await screen.findByText('Up to date', { selector: 'dd' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('agent-update-current')).toHaveTextContent(
      'Confirmed',
    )
    await waitFor(() =>
      expect(detailCalls).toBeGreaterThan(detailsAfterLoad + 1),
    )
    await waitFor(() =>
      expect(availabilityCalls).toBeGreaterThan(availabilityAfterLoad + 1),
    )
  })

  it.each([
    ['requested', 'Request accepted'],
    ['preparing', 'Preparing'],
    ['installing', 'Installing'],
    ['verifying', 'Verifying'],
    ['awaiting_confirmation', 'Awaiting confirmation'],
    ['recovering', 'Recovering'],
    ['succeeded', 'Confirmed'],
    ['failed', 'Failed'],
    ['expired', 'Expired'],
    ['rolled_back', 'Previous version restored'],
    ['needs_intervention', 'Assisted intervention required'],
  ] as const)('shows operation phase %s as text', async (phase, label) => {
    const operation = { ...requestedOperation, phase } satisfies Operation
    server.use(
      http.get(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json({ data: [operation] }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () =>
        HttpResponse.json(operation),
      ),
    )
    await renderDeviceDetail()
    expect(await screen.findByTestId('agent-update-current')).toHaveTextContent(
      label,
    )
  })

  it('localizes update controls in Portuguese', async () => {
    localStorage.setItem('dmitri-language', 'pt-BR')
    agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
    mockAvailability(available)
    await renderDeviceDetail()

    expect(await screen.findByText('Atualização do agente')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Atualizar dispositivo' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Pronto para atualizar')).toBeInTheDocument()
  })

  it.each([
    ['available', 'ready', true],
    ['up_to_date', 'ready', false],
    ['unknown', 'unknown', false],
    ['unavailable', 'ready', false],
    ['available', 'offline', false],
    ['available', 'bootstrap_required', false],
    ['available', 'revoked', false],
    ['available', 'busy', false],
  ] as const)(
    'only offers a request for available and ready devices (%s/%s)',
    async (state, readiness, canUpdate) => {
      agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
      mockAvailability({
        ...available,
        availability: state,
        device_readiness: readiness,
        release: state === 'available' ? release : null,
      })
      await renderDeviceDetail()

      await screen.findByTestId('agent-update-section')
      if (canUpdate) {
        expect(
          await screen.findByTestId('agent-update-trigger'),
        ).toBeInTheDocument()
      } else {
        await waitFor(() =>
          expect(
            screen.queryByTestId('agent-update-trigger'),
          ).not.toBeInTheDocument(),
        )
      }
    },
  )

  it('moves focus into confirmation, traps keyboard focus, and restores focus on Escape', async () => {
    const user = userEvent.setup()
    agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
    mockAvailability(available)
    await renderDeviceDetail()
    const trigger = await screen.findByTestId('agent-update-trigger')
    await user.click(trigger)

    const confirm = await screen.findByRole('button', {
      name: 'Confirm update to version 1.0.6',
    })
    expect(confirm).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Back' })).toHaveFocus()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('renders operation history and Russian copy without replacing persisted state on request error', async () => {
    localStorage.setItem('dmitri-language', 'ru')
    const failed = {
      ...requestedOperation,
      phase: 'rolled_back',
      local_outcome: 'rolled_back',
      error_code: 'install_failed',
      observed_version: '1.0.5',
    } satisfies Operation
    server.use(
      http.get(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json({ data: [failed] }),
      ),
      http.get(`${baseURL}/agent-updates/:updateId`, () =>
        HttpResponse.json(failed),
      ),
      http.post(`${baseURL}/agents/:agentId/updates`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'temporarily_unavailable',
              message: '',
              details: {},
            },
          },
          { status: 503 },
        ),
      ),
    )
    agentDetail({ ...defaultAgent, observed_version: '1.0.5' })
    mockAvailability(available)
    await renderDeviceDetail()

    expect(await screen.findByText('Обновление агента')).toBeInTheDocument()
    expect(
      await screen.findByTestId('agent-update-history-item'),
    ).toHaveTextContent('Предыдущая версия восстановлена')
    const user = userEvent.setup()
    await user.click(screen.getByTestId('agent-update-trigger'))
    await user.click(screen.getByRole('button', { name: /1\.0\.6/ }))
    expect(await screen.findByTestId('toast')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(
      within(screen.getByTestId('agent-update-section')).queryByText(
        'The update request could not be completed',
      ),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('agent-update-history-item')).toHaveTextContent(
      'Предыдущая версия восстановлена',
    )
  })
})
