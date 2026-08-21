import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes, useLocation } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { RequireAdmin } from './RequireAdmin'

const baseURL = 'http://localhost:8000/api/v1'

function LocationProbe() {
  return <div data-testid="pathname">{useLocation().pathname}</div>
}

function renderGuardedRoute() {
  return renderWithProviders(
    <>
      <Routes>
        <Route element={<RequireAdmin />}>
          <Route path="/users" element={<div>Users and invites</div>} />
        </Route>
      </Routes>
      <LocationProbe />
    </>,
    { route: '/users' },
  )
}

describe('RequireAdmin', () => {
  it('renders the guarded route for an admin', async () => {
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(adminProfile)),
    )
    renderGuardedRoute()

    expect(await screen.findByText('Users and invites')).toBeInTheDocument()
    expect(screen.queryByTestId('not-found')).not.toBeInTheDocument()
  })

  it('renders NotFound in place for a viewer, leaving the URL unchanged', async () => {
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )
    renderGuardedRoute()

    expect(await screen.findByTestId('not-found')).toHaveTextContent(
      "That page doesn't exist.",
    )
    expect(screen.queryByText('Users and invites')).not.toBeInTheDocument()
    expect(screen.getByTestId('pathname')).toHaveTextContent('/users')
  })

  it('renders nothing while booting, so NotFound never flashes for an admin', () => {
    server.use(
      http.get(`${baseURL}/users/me`, async () => {
        await delay('infinite')
        return HttpResponse.json(adminProfile)
      }),
    )
    renderGuardedRoute()

    expect(screen.queryByTestId('not-found')).not.toBeInTheDocument()
    expect(screen.queryByText('Users and invites')).not.toBeInTheDocument()
  })

  it('fails closed when the profile never loads and the user stays null', async () => {
    server.use(
      http.get(
        `${baseURL}/users/me`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderGuardedRoute()

    expect(await screen.findByTestId('not-found')).toBeInTheDocument()
    expect(screen.queryByText('Users and invites')).not.toBeInTheDocument()
  })
})
