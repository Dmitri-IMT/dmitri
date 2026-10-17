import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import HostDetail from '@/pages/HostDetail'
import LocationProbe from '@/test/LocationProbe'
import { baseURL, hostDetail } from '@/test/hostsHarness'
import { hostDetailFixtures, viewerProfile } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import { signedInAs } from '@/test/usersHarness'

const HOST = hostDetailFixtures[0]

function renderHost() {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/network/:hostId" element={<HostDetail />} />
        <Route path="/network" element={<div data-testid="network-route" />} />
      </Routes>
      <LocationProbe />
    </>,
    { route: `/network/${HOST.host_id}` },
  )
}

describe('HostDelete', () => {
  it('deletes the machine and returns to the network', async () => {
    hostDetail(HOST, [])
    const requests: string[] = []
    server.use(
      http.delete(`${baseURL}/hosts/:hostId`, ({ params }) => {
        requests.push(String(params.hostId))
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderHost()

    await user.click(await screen.findByTestId('host-delete-trigger'))
    expect(screen.getByTestId('host-delete-dialog')).toHaveTextContent(
      `Delete ${HOST.hostname || HOST.ip}?`,
    )
    await user.click(screen.getByTestId('host-delete-confirm'))

    expect(await screen.findByTestId('network-route')).toBeInTheDocument()
    expect(screen.getByTestId('toast')).toHaveTextContent(
      `${HOST.hostname || HOST.ip} was deleted.`,
    )
    expect(requests).toEqual([HOST.host_id])
  })

  it('has no delete control for a viewer', async () => {
    signedInAs(viewerProfile)
    hostDetail(HOST, [])
    renderHost()

    expect(
      await screen.findByRole('heading', { name: 'Scan history' }),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('host-delete')).not.toBeInTheDocument()
  })
})
