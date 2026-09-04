import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, useLocation } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/test/setup'
import { SessionProvider } from '@/auth/SessionProvider'
import App from './App'
import indexHtml from '../index.html?raw'

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
  return <div data-testid="location-probe">{location.pathname}</div>
}

function renderApp(route: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter initialEntries={[route]}>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <LocationProbe />
          <App />
        </SessionProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('redirects to /login on a failing boot refresh, and Home never renders (AC 5)', async () => {
    failBootRefresh()
    renderApp('/')

    expect(screen.queryByTestId('home-verdict')).not.toBeInTheDocument()
    await screen.findByTestId('login-form')
    expect(screen.queryByTestId('home-verdict')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
  })

  it('lands on Home on a successful boot refresh, and the login form is never rendered (AC 6)', async () => {
    renderApp('/')

    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    await screen.findByTestId('home-verdict')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
  })

  it('lands on / after a successful sign-in from /login (AC 1)', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderApp('/login')

    await user.type(
      await screen.findByLabelText('Email'),
      'ana@northwind.example',
    )
    await user.type(
      screen.getByLabelText('Password'),
      'correct horse battery staple',
    )
    await user.click(screen.getByTestId('login-submit'))

    await screen.findByTestId('home-verdict')
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
  })

  it('signed in, renders not-found with the top bar intact for an unknown path, without rewriting the URL, and returns home via not-found-home (AC 19)', async () => {
    const user = userEvent.setup()
    renderApp('/no-such-route')

    await screen.findByTestId('not-found')
    expect(screen.getByTestId('top-bar')).toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/no-such-route',
    )

    await user.click(screen.getByRole('link', { name: 'Go to Home' }))

    await screen.findByTestId('home-verdict')
    expect(screen.queryByTestId('not-found')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
  })

  it('renders /forgot-password while anonymous, without redirecting to Login', async () => {
    failBootRefresh()
    renderApp('/forgot-password')

    await screen.findByTestId('forgot-form')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/forgot-password',
    )
  })

  it('renders /reset-password while anonymous, without redirecting to Login', async () => {
    failBootRefresh()
    renderApp('/reset-password?token=live-token')

    await screen.findByTestId('reset-form')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/reset-password',
    )
  })

  it('renders /invite while anonymous, without redirecting to Login', async () => {
    failBootRefresh()
    renderApp('/invite?token=live-token')

    await screen.findByTestId('invite-form')
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/invite')
  })

  it('redirects an anonymous visitor from /settings to /login without flashing Settings', async () => {
    failBootRefresh()
    renderApp('/settings')

    expect(screen.queryByTestId('settings-details')).not.toBeInTheDocument()
    await screen.findByTestId('login-form')
    expect(screen.queryByTestId('settings-details')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
  })

  it('renders /settings inside the app shell for an authenticated visitor', async () => {
    renderApp('/settings')

    await screen.findByTestId('settings-details')
    expect(screen.getByTestId('top-bar')).toBeInTheDocument()
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/settings')
  })

  it.each([
    ['/network', 'network-page'],
    ['/devices', 'devices-page'],
    [`/devices/${'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'}`, 'device-detail'],
  ])('resolves %s inside the app shell', async (route, testId) => {
    renderApp(route)

    await screen.findByTestId(testId)
    expect(screen.getByTestId('top-bar')).toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(route)
  })

  it.each(['/hosts', '/agents'])(
    'renders not-found for the retired route %s, with no redirect',
    async (route) => {
      renderApp(route)

      await screen.findByTestId('not-found')
      expect(screen.getByTestId('location-probe')).toHaveTextContent(route)
    },
  )

  it('names the product in the browser title', () => {
    expect(indexHtml).toContain('<title>Dmitri</title>')
  })

  it('signed out, an unknown path lands on /login (AC 19)', async () => {
    failBootRefresh()
    renderApp('/no-such-route')

    await screen.findByTestId('login-form')
    expect(screen.queryByTestId('not-found')).not.toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
  })
})
