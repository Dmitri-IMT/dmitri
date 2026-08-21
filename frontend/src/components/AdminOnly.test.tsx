import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { useSession } from '@/auth/useSession'
import AdminOnly from './AdminOnly'

const baseURL = 'http://localhost:8000/api/v1'

function SessionProbe() {
  const { status, user } = useSession()
  return (
    <div data-testid="session-probe">{`${status} ${user?.email ?? 'none'}`}</div>
  )
}

function renderGuarded() {
  return renderWithProviders(
    <>
      <AdminOnly>
        <button type="button">Invite user</button>
      </AdminOnly>
      <SessionProbe />
    </>,
  )
}

describe('AdminOnly', () => {
  it('renders its children for an admin', async () => {
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(adminProfile)),
    )
    renderGuarded()

    expect(
      await screen.findByRole('button', { name: 'Invite user' }),
    ).toBeInTheDocument()
  })

  it('renders nothing at all for a viewer', async () => {
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )
    renderGuarded()

    await screen.findByText(`authenticated ${viewerProfile.email}`)
    expect(
      screen.queryByRole('button', { name: 'Invite user' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Invite user')).not.toBeInTheDocument()
  })

  it('fails closed while the user is still null', () => {
    server.use(
      http.get(`${baseURL}/users/me`, async () => {
        await delay('infinite')
        return HttpResponse.json(adminProfile)
      }),
    )
    renderGuarded()

    expect(
      screen.queryByRole('button', { name: 'Invite user' }),
    ).not.toBeInTheDocument()
  })
})
