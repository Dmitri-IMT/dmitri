import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { validLoginResponse } from '@/test/mswHandlers'
import { getAccessToken } from '@/api/tokenStore'
import { SessionProvider } from '@/auth/SessionProvider'
import Login from './Login'

const baseURL = 'http://localhost:8000/api/v1'

function failBootRefresh() {
  server.use(
    http.post(
      `${baseURL}/auth/refresh`,
      () => new HttpResponse(null, { status: 401 }),
    ),
  )
}

function LocationProbe() {
  const location = useLocation()
  return (
    <>
      <span data-testid="location-url">{`${location.pathname}${location.search}`}</span>
      <span data-testid="location-state">
        {JSON.stringify(location.state ?? null)}
      </span>
    </>
  )
}

function renderLoginApp(state?: { passwordReset: boolean }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<div>home-route</div>} />
          </Routes>
          <LocationProbe />
        </SessionProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('Login', () => {
  it('establishes a session and lands on / with valid credentials (AC 1)', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderLoginApp()

    await user.type(
      await screen.findByLabelText('Email'),
      'ana@northwind.example',
    )
    await user.type(
      screen.getByLabelText('Password'),
      'correct horse battery staple',
    )
    await user.click(screen.getByTestId('login-submit'))

    await screen.findByText('home-route')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    expect(getAccessToken()).toBe(validLoginResponse.access_token)
  })

  it('shows the credential-mismatch copy on a 401, stays on /login, leaves no token, and keeps the typed password (AC 2)', async () => {
    failBootRefresh()
    server.use(
      http.post(
        `${baseURL}/auth/login`,
        () => new HttpResponse(null, { status: 401 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<Login />)

    await user.type(
      await screen.findByLabelText('Email'),
      'ana@northwind.example',
    )
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByTestId('login-submit'))

    expect(
      await screen.findByText("That email and password don't match."),
    ).toBeInTheDocument()
    expect(screen.getByTestId('login-form')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveValue('wrong-password')
    expect(screen.getByTestId('login-submit')).toBeEnabled()
    expect(getAccessToken()).toBeNull()
  })

  it('shows "Signing in…" and disables the button while in flight, and a second Enter cannot double-submit (AC 3)', async () => {
    failBootRefresh()
    let loginCallCount = 0
    server.use(
      http.post(`${baseURL}/auth/login`, async () => {
        loginCallCount += 1
        await delay('infinite')
        return HttpResponse.json(validLoginResponse)
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Login />)

    const emailField = await screen.findByLabelText('Email')
    const passwordField = screen.getByLabelText('Password')
    const submitButton = screen.getByTestId('login-submit')
    expect(submitButton).toBeEnabled()

    await user.type(emailField, 'ana@northwind.example')
    await user.type(passwordField, 'correct horse battery staple')
    await user.click(submitButton)

    const inFlightButton = await screen.findByRole('button', {
      name: 'Signing in…',
    })
    expect(inFlightButton).toBeDisabled()

    await user.click(passwordField)
    await user.keyboard('{Enter}')

    expect(loginCallCount).toBe(1)
    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled()
  })

  it("shows the can't-reach-the-server copy on a true network error, not the credential string (AC 4)", async () => {
    failBootRefresh()
    server.use(http.post(`${baseURL}/auth/login`, () => HttpResponse.error()))
    const user = userEvent.setup()
    renderWithProviders(<Login />)

    await user.type(
      await screen.findByLabelText('Email'),
      'ana@northwind.example',
    )
    await user.type(
      screen.getByLabelText('Password'),
      'correct horse battery staple',
    )
    await user.click(screen.getByTestId('login-submit'))

    expect(
      await screen.findByText(
        "Can't reach the server. Check your connection and try again.",
      ),
    ).toBeInTheDocument()
  })

  it('renders the alert region pre-mounted and empty before any error, so it can be announced later', async () => {
    failBootRefresh()
    renderWithProviders(<Login />)

    const errorRegion = await screen.findByRole('alert')
    expect(errorRegion).toHaveTextContent('')
    expect(errorRegion).toHaveAttribute('data-testid', 'login-error')
  })

  it('renders the data-testids the design names as stable anchors', async () => {
    failBootRefresh()
    renderWithProviders(<Login />)

    expect(await screen.findByTestId('login-form')).toBeInTheDocument()
    expect(screen.getByTestId('login-email')).toBeInTheDocument()
    expect(screen.getByTestId('login-password')).toBeInTheDocument()
    expect(screen.getByTestId('login-submit')).toBeInTheDocument()
    expect(screen.getByTestId('login-error')).toBeInTheDocument()
  })

  it('autofocuses email, renders the idle copy verbatim, and links to /forgot-password', async () => {
    failBootRefresh()
    renderWithProviders(<Login />)

    const emailField = await screen.findByLabelText('Email')
    expect(emailField).toHaveFocus()
    expect(
      screen.getByText('Sign in', { selector: 'span' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Forgot password?' }),
    ).toHaveAttribute('href', '/forgot-password')
  })

  it('renders no reset-success status on a normal visit', async () => {
    failBootRefresh()
    renderWithProviders(<Login />)

    await screen.findByTestId('login-form')
    expect(screen.queryByTestId('login-success')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('renders the approved reset-success status from router state and clears it from history', async () => {
    failBootRefresh()
    renderLoginApp({ passwordReset: true })

    const successRegion = await screen.findByTestId('login-success')
    expect(successRegion).toHaveTextContent(
      'Password set. Sign in with your new password.',
    )
    expect(successRegion).toHaveAttribute('role', 'status')
    expect(screen.getByRole('status')).toBe(successRegion)

    await waitFor(() =>
      expect(screen.getByTestId('location-state')).toHaveTextContent('null'),
    )
    expect(screen.getByTestId('location-url')).toHaveTextContent(/^\/login$/)
    expect(successRegion).toBeInTheDocument()
  })

  it('gives the reset-success status focus, after which Tab reaches Email then Password', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderLoginApp({ passwordReset: true })

    const successRegion = await screen.findByTestId('login-success')
    await waitFor(() => expect(successRegion).toHaveFocus())

    await user.tab()
    expect(await screen.findByLabelText('Email')).toHaveFocus()
    await user.tab()
    expect(screen.getByLabelText('Password')).toHaveFocus()
  })

  it('submits on Enter from the email field', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderWithProviders(<Login />)

    const emailField = await screen.findByLabelText('Email')
    await user.type(emailField, 'ana@northwind.example')
    await user.type(
      screen.getByLabelText('Password'),
      'correct horse battery staple',
    )
    await user.type(emailField, '{Enter}')

    await waitFor(() =>
      expect(screen.queryByTestId('login-form')).not.toBeInTheDocument(),
    )
  })

  it('submits on Enter from the password field', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderWithProviders(<Login />)

    await user.type(
      await screen.findByLabelText('Email'),
      'ana@northwind.example',
    )
    await user.type(
      screen.getByLabelText('Password'),
      'correct horse battery staple{Enter}',
    )

    await waitFor(() =>
      expect(screen.queryByTestId('login-form')).not.toBeInTheDocument(),
    )
  })

  it('redirects to / without ever rendering the form when already authenticated on boot', async () => {
    renderLoginApp()

    await screen.findByText('home-route')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
  })

  it('renders no form and no labelled fields while status is booting', async () => {
    server.use(
      http.post(`${baseURL}/auth/refresh`, async () => {
        await delay('infinite')
        return HttpResponse.json(validLoginResponse)
      }),
    )
    const bootRequestMatched = new Promise<void>((resolve) => {
      server.events.on('request:start', ({ request }) => {
        if (request.url === `${baseURL}/auth/refresh`) {
          resolve()
        }
      })
    })
    renderLoginApp()

    await bootRequestMatched
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    server.events.removeAllListeners()
  })
})
