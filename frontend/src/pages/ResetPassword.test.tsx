import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes, useLocation, useNavigate } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { getAccessToken } from '@/api/tokenStore'
import Login from './Login'
import ResetPassword from './ResetPassword'

const baseURL = 'http://localhost:8000/api/v1'
const VALID = 'a-long-enough-password'

function failBootRefresh() {
  server.use(
    http.post(
      `${baseURL}/auth/refresh`,
      () => new HttpResponse(null, { status: 401 }),
    ),
  )
}

function captureResetRequests() {
  const bodies: unknown[] = []
  server.use(
    http.post(`${baseURL}/auth/reset-password`, async ({ request }) => {
      bodies.push(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return bodies
}

function respond(status: number, code: string) {
  server.use(
    http.post(`${baseURL}/auth/reset-password`, () =>
      HttpResponse.json({ error: { code, message: 'nope' } }, { status }),
    ),
  )
}

function LocationProbe() {
  const location = useLocation()
  const navigate = useNavigate()
  return (
    <div>
      <div data-testid="location-probe">{location.pathname}</div>
      <button type="button" onClick={() => void navigate(-1)}>
        Go back
      </button>
    </div>
  )
}

function renderResetApp(route = '/reset-password?token=live-token') {
  return renderWithProviders(
    <>
      <LocationProbe />
      <Routes>
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<div>forgot-route</div>} />
      </Routes>
    </>,
    { route },
  )
}

async function submit(password = VALID, confirmation = VALID) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('New password'), password)
  await user.type(screen.getByLabelText('Confirm new password'), confirmation)
  await user.click(screen.getByTestId('reset-submit'))
  return user
}

describe('ResetPassword', () => {
  it('renders the idle form with a token, focuses New password, and uses new-password autocomplete', async () => {
    failBootRefresh()
    renderResetApp()

    expect(await screen.findByTestId('reset-idle')).toBeInTheDocument()
    expect(screen.getByTestId('reset-form')).toBeInTheDocument()
    expect(screen.queryByTestId('top-bar')).toBeNull()
    await waitFor(() =>
      expect(screen.getByTestId('reset-password')).toHaveFocus(),
    )
    expect(screen.getByTestId('reset-password')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByTestId('reset-confirm')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )

    const idle = within(screen.getByTestId('reset-idle'))
    const interactive = [
      ...idle.queryAllByRole('button'),
      ...idle.queryAllByRole('link'),
      ...idle.queryAllByRole('textbox'),
    ]
    expect(interactive.length).toBeGreaterThan(0)
    for (const el of interactive) {
      expect(el).toBeEnabled()
      expect(el).not.toHaveAttribute('aria-disabled', 'true')
    }
  })

  it('never renders the token anywhere in the DOM', async () => {
    failBootRefresh()
    const { container } = renderResetApp('/reset-password?token=secret-token')

    await screen.findByTestId('reset-form')
    expect(container.innerHTML).not.toContain('secret-token')
  })

  it('renders the dead state with zero requests when the token is absent', async () => {
    failBootRefresh()
    const bodies = captureResetRequests()
    renderResetApp('/reset-password')

    expect(await screen.findByTestId('reset-dead')).toBeInTheDocument()
    expect(screen.queryByTestId('reset-form')).toBeNull()
    await waitFor(() =>
      expect(screen.getByText('This link has expired.')).toHaveFocus(),
    )
    expect(bodies).toEqual([])
  })

  it('routes Request a new link to /forgot-password', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderResetApp('/reset-password')

    await user.click(await screen.findByTestId('reset-request'))

    await screen.findByText('forgot-route')
  })

  it('renders the mismatch error and issues zero requests', async () => {
    failBootRefresh()
    const bodies = captureResetRequests()
    renderResetApp()

    await submit(VALID, 'a-different-password')

    await waitFor(() =>
      expect(screen.getByTestId('reset-confirm-error')).toHaveTextContent(
        "Those two passwords don't match.",
      ),
    )
    expect(bodies).toEqual([])
    expect(screen.getByTestId('reset-confirm')).toHaveFocus()
    expect(screen.getByTestId('reset-form')).toBeInTheDocument()
  })

  it('sends exactly { token, new_password } and never the confirmation', async () => {
    failBootRefresh()
    const bodies = captureResetRequests()
    renderResetApp()

    await submit()

    await screen.findByTestId('login-form')
    expect(bodies).toEqual([{ token: 'live-token', new_password: VALID }])
  })

  it('creates no session on 204 and replaces the route with Login showing the success status', async () => {
    failBootRefresh()
    renderResetApp()

    await submit()

    await screen.findByTestId('login-form')
    expect(screen.getByTestId('login-success')).toHaveTextContent(
      'Password set. Sign in with your new password.',
    )
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
    expect(getAccessToken()).toBeNull()
  })

  it('replaces the reset entry so going back never returns to the form', async () => {
    failBootRefresh()
    renderResetApp()

    const user = await submit()
    await screen.findByTestId('login-form')

    await user.click(screen.getByRole('button', { name: 'Go back' }))

    expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
    expect(screen.queryByTestId('reset-form')).toBeNull()
    expect(screen.queryByTestId('reset-idle')).toBeNull()
  })

  it('keeps the form and shows the policy error beside New password on 400', async () => {
    failBootRefresh()
    respond(400, 'password_policy_violation')
    renderResetApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('reset-password-error')).toHaveTextContent(
        "That password isn't strong enough. Try a longer one that isn't based on a name or a date.",
      ),
    )
    expect(screen.getByTestId('reset-form')).toBeInTheDocument()
    expect(screen.getByTestId('reset-password')).toHaveFocus()
    expect(screen.getByTestId('reset-password')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('removes the form and renders the dead state on 410 invalid_reset_token', async () => {
    failBootRefresh()
    respond(410, 'invalid_reset_token')
    renderResetApp()

    await submit()

    expect(await screen.findByTestId('reset-dead')).toBeInTheDocument()
    expect(screen.queryByTestId('reset-form')).toBeNull()
    expect(screen.getByTestId('reset-request')).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })

  it('recovers from a network failure with the approved error and both values preserved', async () => {
    failBootRefresh()
    server.use(
      http.post(`${baseURL}/auth/reset-password`, () => HttpResponse.error()),
    )
    renderResetApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('reset-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.getByTestId('reset-password')).toHaveValue(VALID)
    expect(screen.getByTestId('reset-confirm')).toHaveValue(VALID)
    expect(screen.getByTestId('reset-submit')).toBeEnabled()
    expect(screen.getByTestId('reset-submit')).toHaveTextContent('Set password')
    expect(screen.queryByTestId('reset-dead')).toBeNull()
  })

  it('recovers from a 500 the same way', async () => {
    failBootRefresh()
    server.use(
      http.post(
        `${baseURL}/auth/reset-password`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderResetApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('reset-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.getByTestId('reset-form')).toBeInTheDocument()
  })

  it('disables the action in flight and issues no second request', async () => {
    failBootRefresh()
    let requestCount = 0
    server.use(
      http.post(`${baseURL}/auth/reset-password`, async () => {
        requestCount += 1
        await delay(50)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderResetApp()

    const user = await submit()

    const button = screen.getByTestId('reset-submit')
    expect(button).toHaveTextContent('Setting your password…')
    expect(button).toBeDisabled()
    await user.click(button)

    await screen.findByTestId('login-form')
    expect(requestCount).toBe(1)
  })

  it('keeps a settled message while editing and clears it when the next submit begins', async () => {
    failBootRefresh()
    respond(400, 'password_policy_violation')
    renderResetApp()

    const user = await submit()
    await waitFor(() =>
      expect(
        screen.getByTestId('reset-password-error'),
      ).not.toBeEmptyDOMElement(),
    )

    await user.type(screen.getByTestId('reset-password'), 'x')
    expect(screen.getByTestId('reset-password-error')).not.toBeEmptyDOMElement()

    await user.type(screen.getByTestId('reset-confirm'), 'x')
    server.use(
      http.post(
        `${baseURL}/auth/reset-password`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    )
    await user.click(screen.getByTestId('reset-submit'))

    await screen.findByTestId('login-form')
  })
})
