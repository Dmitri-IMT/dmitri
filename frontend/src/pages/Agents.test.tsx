import { afterEach, describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { focusManager } from '@tanstack/react-query'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  agentDetail,
  agentsFail,
  baseURL,
  commandRefused,
  noAgents,
  withActiveCommand,
} from '@/test/agentsHarness'
import { defaultAgent, defaultCommand, viewerProfile } from '@/test/mswHandlers'
import { server } from '@/test/setup'
import { signedInAs } from '@/test/usersHarness'
import Agents from './Agents'

function expectClosingNoteLinks() {
  const scansLink = screen.getByRole('link', { name: 'Scans' })
  const hostsLink = screen.getByRole('link', { name: 'Hosts' })
  for (const [link, href, testId] of [
    [scansLink, '/scans', 'agents-scans-link'],
    [hostsLink, '/hosts', 'agents-hosts-link'],
  ] as const) {
    expect(link).toHaveAttribute('href', href)
    expect(link).toHaveAttribute('data-testid', testId)
    expect(link).toHaveAttribute('data-variant', 'link')
    expect(link).toHaveClass(
      'cursor-pointer',
      'text-primary',
      'text-body-md',
      'hover:underline',
      'focus-visible:ring-3',
      'focus-visible:underline',
      'active:not-aria-[haspopup]:translate-y-px',
    )
    expect(link).not.toHaveAttribute('aria-disabled')
  }
}

function isApprovedAgentsTestId(id: string) {
  if (id === 'toast') return true
  return /^agents-(page|loading|blank|blank-note|error|error-retry|note|scans-link|hosts-link|card|identity|name|presence|network|network-change|chooser|chooser-confirm|chooser-option-[a-z0-9]+|scan-now|retry|pill|command-status|view-scan)$/.test(
    id,
  )
}

function assertApprovedAgentsTestIds(root: HTMLElement) {
  const ids = [...root.querySelectorAll('[data-testid]')]
    .map((el) => el.getAttribute('data-testid')!)
    .filter((id) => id.startsWith('agents-') || id === 'toast')
  for (const id of ids) {
    expect(isApprovedAgentsTestId(id)).toBe(true)
  }
}

afterEach(() => {
  focusManager.setFocused(undefined)
})

describe('Agents', () => {
  it('renders the agent, permanent Pi sentence and ready trigger', async () => {
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-card')).toBeInTheDocument()
    const identity = screen.getByTestId('agents-identity')
    const name = screen.getByTestId('agents-name')
    const presence = screen.getByTestId('agents-presence')
    const network = screen.getByTestId('agents-network')
    const note = screen.getByTestId('agents-note')

    expect(identity).toContainElement(name)
    expect(identity).toContainElement(presence)
    expect(name).toHaveTextContent('DMITRI-NSPI-01')
    expect(presence).toHaveTextContent('Online')
    expect(network).toHaveTextContent('Scanning: Ethernet · 192.168.0.0/24')
    for (const ordinaryRead of [presence, network, note]) {
      expect(ordinaryRead).toHaveClass('text-body-md')
      expect(ordinaryRead).not.toHaveClass('text-body-sm')
    }
    expect(screen.getByTestId('agents-scan-now')).toBeEnabled()
    expect(note).toHaveTextContent('Scanning is set up on the Pi itself.')
    expectClosingNoteLinks()
    assertApprovedAgentsTestIds(screen.getByTestId('agents-page'))
  })

  it('renders the card-shaped loading state before the first agent read', async () => {
    let release!: () => void
    const pending = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get(`${baseURL}/agents`, async () => {
        await pending
        return HttpResponse.json({ data: [defaultAgent] })
      }),
    )

    renderWithProviders(<Agents />)

    const loading = screen.getByTestId('agents-loading')
    expect(loading).toHaveClass(
      'border',
      'border-border',
      'bg-card',
      'p-6',
      'gap-6',
    )
    const bars = loading.querySelectorAll('[aria-hidden="true"]')
    expect(bars).toHaveLength(3)
    expect(bars[0]).toHaveClass('h-6', 'w-1/3')
    expect(bars[1]).toHaveClass('h-4', 'w-2/5')
    expect(bars[2]).toHaveClass('h-4', 'w-1/2')
    expect(
      loading.querySelectorAll('button, a, input, [tabindex]'),
    ).toHaveLength(0)
    expect(screen.getByTestId('agents-note')).toHaveTextContent(
      'Scanning is set up on the Pi itself.',
    )
    expectClosingNoteLinks()
    assertApprovedAgentsTestIds(screen.getByTestId('agents-page'))
    release()
    expect(await screen.findByTestId('agents-card')).toBeInTheDocument()
  })

  it('requires a reported network choice without free text', async () => {
    const user = userEvent.setup()
    agentDetail({ ...defaultAgent, target_subnet: null })
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-chooser')).toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(
      screen.getByLabelText('Ethernet · 192.168.0.0/24'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

    await user.click(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    )
    await user.click(screen.getByTestId('agents-chooser-confirm'))

    expect(await screen.findByTestId('agents-scan-now')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTestId('agents-scan-now')).toHaveFocus(),
    )
    expect(screen.getByTestId('agents-network')).toHaveTextContent(
      'Scanning: Wi-Fi · 10.12.0.0/16',
    )

    await user.click(screen.getByTestId('agents-network-change'))
    expect(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    ).toBeChecked()
    expect(screen.getByLabelText('Ethernet · 192.168.0.0/24')).not.toBeChecked()
  })

  it('uses the PATCH response without a second agent-detail read', async () => {
    const user = userEvent.setup()
    let detailReads = 0
    server.use(
      http.get(`${baseURL}/agents`, () =>
        HttpResponse.json({
          data: [{ ...defaultAgent, target_subnet: null }],
        }),
      ),
      http.get(`${baseURL}/agents/:agentId`, () => {
        detailReads += 1
        return HttpResponse.json({ ...defaultAgent, target_subnet: null })
      }),
      http.patch(`${baseURL}/agents/:agentId`, () =>
        HttpResponse.json({
          ...defaultAgent,
          target_subnet: '10.12.0.0/16',
        }),
      ),
    )
    renderWithProviders(<Agents />)

    await user.click(
      await screen.findByLabelText(
        'Wi-Fi · 10.12.0.0/16 (internet connection)',
      ),
    )
    await user.click(screen.getByTestId('agents-chooser-confirm'))

    expect(await screen.findByTestId('agents-network')).toHaveTextContent(
      'Scanning: Wi-Fi · 10.12.0.0/16',
    )
    expect(detailReads).toBe(1)
  })

  it('starts each chooser session from the latest reported server target', async () => {
    const user = userEvent.setup()
    let detailReads = 0
    server.use(
      http.get(`${baseURL}/agents/:agentId`, () => {
        detailReads += 1
        return HttpResponse.json({
          ...defaultAgent,
          target_subnet: detailReads === 1 ? '192.168.0.0/24' : '10.12.0.0/16',
        })
      }),
    )
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-network')).toHaveTextContent(
      'Scanning: Ethernet · 192.168.0.0/24',
    )
    fireEvent.focus(window)
    focusManager.setFocused(true)
    await waitFor(() =>
      expect(screen.getByTestId('agents-network')).toHaveTextContent(
        'Scanning: Wi-Fi · 10.12.0.0/16',
      ),
    )

    await user.click(screen.getByTestId('agents-network-change'))

    expect(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    ).toBeChecked()
    expect(screen.getByLabelText('Ethernet · 192.168.0.0/24')).not.toBeChecked()
  })

  it('opens with no selection when the latest target is not reported', async () => {
    const user = userEvent.setup()
    agentDetail({
      ...defaultAgent,
      target_subnet: '172.16.0.0/16',
    })
    renderWithProviders(<Agents />)

    await user.click(await screen.findByTestId('agents-network-change'))

    expect(screen.getByLabelText('Ethernet · 192.168.0.0/24')).not.toBeChecked()
    expect(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    ).not.toBeChecked()
    expect(screen.getByTestId('agents-chooser-confirm')).toBeDisabled()
  })

  it('preserves an open chooser draft across a background agent read', async () => {
    const user = userEvent.setup()
    const thirdSubnet = {
      interface: 'usb0',
      cidr: '172.16.0.0/16',
      is_default_route: false,
    }
    let detailReads = 0
    server.use(
      http.get(`${baseURL}/agents/:agentId`, () => {
        detailReads += 1
        return HttpResponse.json({
          ...defaultAgent,
          target_subnet: detailReads === 1 ? '192.168.0.0/24' : '10.12.0.0/16',
          available_subnets: [...defaultAgent.available_subnets, thirdSubnet],
        })
      }),
    )
    renderWithProviders(<Agents />)

    await user.click(await screen.findByTestId('agents-network-change'))
    await user.click(screen.getByLabelText('usb0 · 172.16.0.0/16'))
    fireEvent.focus(window)
    focusManager.setFocused(true)
    await waitFor(() => expect(detailReads).toBeGreaterThan(1))

    expect(screen.getByLabelText('usb0 · 172.16.0.0/16')).toBeChecked()
    expect(
      screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
    ).not.toBeChecked()
  })

  it.each([
    [409, 'device_offline', "Couldn't reach the Pi; nothing changed."],
    [
      422,
      'subnet_not_reported',
      "The Pi doesn't report that network any more; nothing changed.",
    ],
  ])(
    'keeps the chooser and stored target after a %s %s refusal',
    async (status, code, copy) => {
      const user = userEvent.setup()
      server.use(
        http.patch(`${baseURL}/agents/:agentId`, () =>
          HttpResponse.json(
            { error: { code, message: code, details: {} } },
            { status },
          ),
        ),
      )
      renderWithProviders(<Agents />)

      await user.click(await screen.findByTestId('agents-network-change'))
      await user.click(
        screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
      )
      const confirm = screen.getByTestId('agents-chooser-confirm')
      await user.click(confirm)

      expect(await screen.findByTestId('toast')).toHaveTextContent(copy)
      expect(confirm).toHaveFocus()
      const describedBy = confirm.getAttribute('aria-describedby')
      expect(describedBy).not.toBeNull()
      expect(document.getElementById(describedBy!)).toHaveTextContent(copy)
      expect(document.getElementById(describedBy!)).toHaveAttribute(
        'aria-live',
        'polite',
      )
      expect(document.getElementById(describedBy!)).toHaveAttribute(
        'role',
        'status',
      )
      expect(screen.getByTestId('agents-chooser')).toBeInTheDocument()
      expect(
        screen.getByLabelText('Wi-Fi · 10.12.0.0/16 (internet connection)'),
      ).toBeChecked()
      expect(confirm).toBeEnabled()
      expect(screen.getByTestId('agents-network')).toHaveTextContent(
        'Scanning: Ethernet · 192.168.0.0/24',
      )
      expect(screen.queryByText(code)).not.toBeInTheDocument()

      await user.click(screen.getByLabelText('Ethernet · 192.168.0.0/24'))
      expect(confirm).not.toHaveAttribute('aria-describedby')
      expect(document.getElementById(describedBy!)).toBeEmptyDOMElement()
    },
  )

  it('disables stale chooser confirmation after a refusal refreshes the subnet list', async () => {
    const user = userEvent.setup()
    let detailReads = 0
    let patchCalls = 0
    server.use(
      http.get(`${baseURL}/agents/:agentId`, () => {
        detailReads += 1
        return HttpResponse.json({
          ...defaultAgent,
          available_subnets:
            detailReads === 1 ? defaultAgent.available_subnets : [],
        })
      }),
      http.patch(`${baseURL}/agents/:agentId`, () => {
        patchCalls += 1
        return HttpResponse.json(
          {
            error: {
              code: 'subnet_not_reported',
              message: 'stale subnet',
              details: {},
            },
          },
          { status: 422 },
        )
      }),
    )
    renderWithProviders(<Agents />)

    await user.click(await screen.findByTestId('agents-network-change'))
    const confirm = screen.getByTestId('agents-chooser-confirm')
    await user.click(confirm)

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "The Pi doesn't report that network any more; nothing changed.",
    )
    await waitFor(() => expect(confirm).toBeDisabled())
    await user.click(confirm)
    expect(patchCalls).toBe(1)
  })

  it('supports change and keeps the trigger while offline', async () => {
    const user = userEvent.setup()
    agentDetail({ ...defaultAgent, online: false })
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-scan-now')).toBeEnabled()
    expect(screen.getByTestId('agents-presence')).toHaveTextContent('Offline')
    await user.click(screen.getByTestId('agents-network-change'))
    expect(screen.getByTestId('agents-chooser')).toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Ethernet · 192.168.0.0/24')).toBeChecked()
  })

  it('hides an old terminal command when the first-run chooser owns the card', async () => {
    withActiveCommand(
      { ...defaultCommand, status: 'failed' },
      { ...defaultAgent, target_subnet: null },
    )
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-chooser')).toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-command-status'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-pill')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-retry')).not.toBeInTheDocument()
  })

  it('hides the complete followed-command slot while choosing', async () => {
    const user = userEvent.setup()
    withActiveCommand({ ...defaultCommand, status: 'failed' })
    renderWithProviders(<Agents />)

    expect(
      await screen.findByTestId('agents-command-status'),
    ).toBeInTheDocument()
    expect(await screen.findByTestId('agents-retry')).toBeInTheDocument()
    await user.click(screen.getByTestId('agents-network-change'))

    expect(screen.getByTestId('agents-chooser')).toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-command-status'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-pill')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-retry')).not.toBeInTheDocument()
  })

  it('replaces old terminal controls with the chooser after a stale retry refusal', async () => {
    const user = userEvent.setup()
    withActiveCommand({ ...defaultCommand, status: 'expired' })
    commandRefused(422, 'subnet_not_reported')
    renderWithProviders(<Agents />)

    await user.click(await screen.findByTestId('agents-retry'))

    expect(await screen.findByTestId('agents-chooser')).toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-command-status'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-pill')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-retry')).not.toBeInTheDocument()
    expect(screen.getByTestId('toast')).toHaveTextContent(
      "The Pi doesn't report that network any more. Pick the network to scan again.",
    )
  })

  it('omits device actions for a viewer', async () => {
    signedInAs(viewerProfile)
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-card')).toBeInTheDocument()
    expect(screen.getByTestId('agents-network')).toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-network-change'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-chooser')).not.toBeInTheDocument()
  })

  it('shows a viewer the unchosen-network direction without device controls', async () => {
    signedInAs(viewerProfile)
    withActiveCommand(defaultCommand, {
      ...defaultAgent,
      target_subnet: null,
    })
    renderWithProviders(<Agents />)

    await screen.findByTestId('agents-card')
    const presence = screen.getByTestId('agents-presence')
    const network = screen.getByTestId('agents-network')
    const note = screen.getByTestId('agents-note')
    expect(network).toHaveTextContent(
      'No network chosen yet. Ask your admin to choose one.',
    )
    for (const ordinaryRead of [presence, network, note]) {
      expect(ordinaryRead).toHaveClass('text-body-md')
      expect(ordinaryRead).not.toHaveClass('text-body-sm')
    }
    expectClosingNoteLinks()
    expect(screen.getByTestId('agents-command-status')).toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-network-change'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-chooser')).not.toBeInTheDocument()
  })

  it('renders the no-device blank without an action', async () => {
    noAgents()
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-blank')).toHaveTextContent(
      'No Pi connected yet.',
    )
    expect(screen.getByTestId('agents-blank-note')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(screen.getByTestId('agents-note')).toHaveTextContent(
      'Scanning is set up on the Pi itself.',
    )
    expectClosingNoteLinks()
    assertApprovedAgentsTestIds(screen.getByTestId('agents-page'))
  })

  it('retries a first-load failure', async () => {
    const user = userEvent.setup()
    agentsFail()
    renderWithProviders(<Agents />)

    expect(await screen.findByTestId('agents-error')).toHaveTextContent(
      "Couldn't load the agents.",
    )
    expectClosingNoteLinks()
    assertApprovedAgentsTestIds(screen.getByTestId('agents-page'))
    agentDetail(defaultAgent)
    await user.click(screen.getByTestId('agents-error-retry'))
    expect(await screen.findByTestId('agents-card')).toBeInTheDocument()
  })
})
