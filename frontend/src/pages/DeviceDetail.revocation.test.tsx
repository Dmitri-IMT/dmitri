import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import DeviceDetail from '@/pages/DeviceDetail'
import { baseURL } from '@/test/agentsHarness'
import { defaultAgent, viewerProfile } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { signedInAs } from '@/test/usersHarness'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

const route = `/devices/${defaultAgent.agent_id}`

function renderDetail() {
  return renderWithProviders(
    <Routes>
      <Route path="/devices/:agentId" element={<DeviceDetail />} />
    </Routes>,
    { route },
  )
}

function revocationServer(initial: AgentDetail = defaultAgent) {
  let agent = { ...initial }
  let revokeRequests = 0
  let restoreRequests = 0
  server.use(
    http.get(`${baseURL}/agents`, () => HttpResponse.json({ data: [agent] })),
    http.get(`${baseURL}/agents/:agentId`, () => HttpResponse.json(agent)),
    http.post(`${baseURL}/agents/:agentId/revoke`, () => {
      revokeRequests += 1
      agent = { ...agent, revoked_at: new Date().toISOString() }
      return HttpResponse.json(agent)
    }),
    http.post(`${baseURL}/agents/:agentId/restore`, () => {
      restoreRequests += 1
      agent = { ...agent, online: false, revoked_at: null }
      return HttpResponse.json(agent)
    }),
  )
  return {
    revokeRequests: () => revokeRequests,
    restoreRequests: () => restoreRequests,
  }
}

describe('DeviceDetail revocation', () => {
  it('cancels revoke without sending a request', async () => {
    const requests = revocationServer()
    const user = userEvent.setup()
    renderDetail()

    await user.click(await screen.findByTestId('device-revoke-trigger'))
    const dialog = screen.getByTestId('device-revoke-dialog')
    expect(within(dialog).getByTestId('device-revoke-confirm')).toHaveFocus()
    await user.click(within(dialog).getByTestId('device-revoke-cancel'))

    expect(requests.revokeRequests()).toBe(0)
    expect(screen.queryByTestId('device-revoke-dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('device-revoke-trigger')).toHaveFocus()
  })

  it('revokes, re-reads, hides device controls, and restores', async () => {
    const requests = revocationServer()
    const user = userEvent.setup()
    renderDetail()

    await user.click(await screen.findByTestId('device-revoke-trigger'))
    await user.click(screen.getByTestId('device-revoke-confirm'))

    expect(await screen.findByTestId('device-revoked')).toBeInTheDocument()
    expect(screen.getByTestId('agents-presence')).toHaveTextContent('Revoked')
    expect(screen.getByTestId('agents-presence')).toHaveFocus()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-network-change'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('device-restore')).toBeInTheDocument()
    expect(screen.getByTestId('toast')).toHaveTextContent(
      `${defaultAgent.display_name} was revoked.`,
    )
    expect(requests.revokeRequests()).toBe(1)

    await user.click(screen.getByTestId('device-restore'))

    await waitFor(() =>
      expect(screen.getByTestId('agents-presence')).toHaveTextContent(
        'Offline',
      ),
    )
    expect(screen.getByTestId('agents-presence')).toHaveFocus()
    expect(screen.getByTestId('device-revoke-trigger')).toBeInTheDocument()
    expect(screen.getByTestId('agents-scan-now')).toBeInTheDocument()
    expect(screen.getByTestId('agents-network-change')).toBeInTheDocument()
    expect(screen.getByTestId('toast')).toHaveTextContent(
      `${defaultAgent.display_name} was restored. It reconnects on its next hourly attempt, within the hour.`,
    )
    expect(requests.restoreRequests()).toBe(1)
  })

  it('closes an open network chooser when the device becomes revoked', async () => {
    revocationServer()
    const user = userEvent.setup()
    renderDetail()

    await user.click(await screen.findByTestId('agents-network-change'))
    expect(screen.getByTestId('agents-chooser')).toBeInTheDocument()
    await user.click(screen.getByTestId('device-revoke-trigger'))
    await user.click(screen.getByTestId('device-revoke-confirm'))

    expect(await screen.findByTestId('device-revoked')).toBeInTheDocument()
    expect(screen.queryByTestId('agents-chooser')).not.toBeInTheDocument()
    expect(screen.getByTestId('agents-network')).toBeInTheDocument()
  })

  it('shows revoke and restore failures beside their actions', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(
        `${baseURL}/agents/:agentId/revoke`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    const first = renderDetail()

    await user.click(await screen.findByTestId('device-revoke-trigger'))
    await user.click(screen.getByTestId('device-revoke-confirm'))
    expect(await screen.findByTestId('device-revoke-error')).toHaveTextContent(
      "Couldn't revoke this device. Try again.",
    )
    first.unmount()

    const revoked = {
      ...defaultAgent,
      revoked_at: new Date().toISOString(),
    }
    server.resetHandlers()
    revocationServer(revoked)
    server.use(
      http.post(
        `${baseURL}/agents/:agentId/restore`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderDetail()

    await user.click(await screen.findByTestId('device-restore'))
    expect(await screen.findByTestId('device-restore-error')).toHaveTextContent(
      "Couldn't restore this device. Try again.",
    )
  })

  it('uses disabled progress states', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${baseURL}/agents/:agentId/revoke`, async () => {
        await delay('infinite')
        return HttpResponse.json(defaultAgent)
      }),
    )
    renderDetail()

    await user.click(await screen.findByTestId('device-revoke-trigger'))
    await user.click(screen.getByTestId('device-revoke-confirm'))

    expect(screen.getByTestId('device-revoke-confirm')).toBeDisabled()
    expect(screen.getByTestId('device-revoke-confirm')).toHaveTextContent(
      'Revoking…',
    )
    expect(screen.queryByTestId('device-revoke-cancel')).not.toBeInTheDocument()
  })

  it('shows viewers the revoked explanation without mutation actions', async () => {
    signedInAs(viewerProfile)
    revocationServer({
      ...defaultAgent,
      revoked_at: new Date().toISOString(),
    })
    renderDetail()

    expect(await screen.findByTestId('device-revoked-body')).toHaveTextContent(
      'Ask your admin to restore it.',
    )
    expect(screen.queryByTestId('device-restore')).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('device-revoke-trigger'),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('agents-scan-now')).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('agents-network-change'),
    ).not.toBeInTheDocument()
  })
})
