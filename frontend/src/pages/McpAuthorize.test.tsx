import { afterEach, describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import McpAuthorize from './McpAuthorize'
import Login from './Login'

const baseURL = 'http://localhost:8000/api/v1'
const requestToken = 'a'.repeat(43)
const authorization = {
  client_name: 'Local Codex',
  email: 'member@example.test',
  organization: 'NSPi organization',
  redirect_uri: 'http://127.0.0.1:8917/callback',
  scope: 'dmitri:read',
}

function renderAuthorization() {
  server.use(
    http.get(`${baseURL}/mcp/authorization`, () =>
      HttpResponse.json(authorization),
    ),
  )
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/mcp/authorize" element={<McpAuthorize />} />
        <Route path="/login" element={<Login />} />
      </Routes>
      <LocationProbe />
    </>,
    { route: `/mcp/authorize?request=${requestToken}` },
  )
}

afterEach(() => window.history.replaceState(null, '', '/'))

describe('MCP consent', () => {
  it('shows the account, organization, client and read-only disclosure before approval', async () => {
    const user = userEvent.setup()
    const decisions: unknown[] = []
    server.use(
      http.post(`${baseURL}/mcp/authorization`, async ({ request }) => {
        decisions.push(await request.json())
        return HttpResponse.json({ redirect_url: '#approved' })
      }),
    )
    renderAuthorization()

    expect(await screen.findByText('NSPi organization')).toBeVisible()
    expect(screen.getByText('member@example.test')).toBeVisible()
    expect(screen.getByText('Local Codex')).toBeVisible()
    expect(screen.getByText(authorization.redirect_uri)).toBeVisible()
    expect(
      screen.getByText(/It cannot change your data or control devices/),
    ).toBeVisible()
    expect(screen.getByText(/model provider/)).toBeVisible()
    expect(decisions).toEqual([])

    await user.click(screen.getByRole('button', { name: 'Allow read access' }))
    await waitFor(() =>
      expect(decisions).toEqual([
        { request_token: requestToken, approve: true },
      ]),
    )
    await waitFor(() => expect(window.location.hash).toBe('#approved'))
  })

  it('can decline and reports a failed decision through a toast', async () => {
    const user = userEvent.setup()
    const decisions: unknown[] = []
    server.use(
      http.post(`${baseURL}/mcp/authorization`, async ({ request }) => {
        decisions.push(await request.json())
        return new HttpResponse(null, { status: 409 })
      }),
    )
    renderAuthorization()
    await user.click(await screen.findByRole('button', { name: 'Decline' }))
    await waitFor(() =>
      expect(decisions).toEqual([
        { request_token: requestToken, approve: false },
      ]),
    )
    expect(await screen.findByTestId('toast')).toHaveTextContent(
      "Couldn't complete this connection. Try again.",
    )
    expect(screen.getByTestId('mcp-authorization')).not.toHaveTextContent(
      "Couldn't complete this connection",
    )
  })

  it('keeps the authorization request through sign-in', async () => {
    let signedIn = false
    server.use(
      http.post(`${baseURL}/auth/refresh`, () =>
        signedIn
          ? HttpResponse.json({
              access_token: 'web-token',
              token_type: 'bearer',
              expires_in: 900,
            })
          : new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${baseURL}/auth/login`, () => {
        signedIn = true
        return HttpResponse.json({
          access_token: 'web-token',
          token_type: 'bearer',
          expires_in: 900,
        })
      }),
    )
    renderAuthorization()
    const user = userEvent.setup()
    await user.type(
      await screen.findByLabelText('Email'),
      'member@example.test',
    )
    await user.type(screen.getByLabelText('Password'), 'long-enough-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('NSPi organization')).toBeVisible()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/mcp/authorize',
    )
  })
})
