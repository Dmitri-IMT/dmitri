import { StrictMode, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { viewerProfile } from '@/test/mswHandlers'
import { getAccessToken, setAccessToken } from '@/api/tokenStore'
import { readApiError } from '@/api/apiError'
import { emitSessionExpired } from '@/api/authEvents'
import { SessionProvider } from './SessionProvider'
import { useSession } from './useSession'
import { RequireSession } from './RequireSession'

const baseURL = 'http://localhost:8000/api/v1'

function SessionProbe() {
  const { status, user, signOut, deleteAccount } = useSession()
  const [deleteError, setDeleteError] = useState<string | null>(null)
  if (status === 'booting') return null
  if (status === 'anonymous') return <div>Login form</div>
  return (
    <div>
      <div>Signed in as {user?.role}</div>
      <button onClick={() => void signOut()}>Log out</button>
      <button
        onClick={() => {
          deleteAccount().catch((error: unknown) => {
            const { status, code } = readApiError(error)
            setDeleteError(`delete-rejected ${status} ${code}`)
          })
        }}
      >
        Delete account
      </button>
      {deleteError ? <div>{deleteError}</div> : null}
    </div>
  )
}

function LoginStateProbe() {
  const state = useLocation().state as { accountDeleted?: boolean } | null
  return (
    <div>{state?.accountDeleted ? 'account-deleted-state' : 'no-state'}</div>
  )
}

function BackProbe() {
  const navigate = useNavigate()
  return <button onClick={() => navigate(-1)}>Go back</button>
}

function renderNavigableApp(queryClient: QueryClient) {
  return render(
    <MemoryRouter initialEntries={['/first', '/']} initialIndex={1}>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <Routes>
            <Route path="/first" element={<div>first-route</div>} />
            <Route path="/" element={<SessionProbe />} />
            <Route
              path="/login"
              element={
                <>
                  <div>login-route</div>
                  <LoginStateProbe />
                  <BackProbe />
                </>
              }
            />
          </Routes>
        </SessionProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function newQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

describe('SessionProvider', () => {
  it('never renders the login form when the boot refresh succeeds (AC 6)', async () => {
    renderWithProviders(<SessionProbe />)

    expect(screen.queryByText('Login form')).not.toBeInTheDocument()
    await screen.findByText('Signed in as admin')
    expect(screen.queryByText('Login form')).not.toBeInTheDocument()
  })

  it('exposes the role from GET /users/me, never a role decoded from the token (AC 8)', async () => {
    const tokenClaimingAdmin = `header.${btoa(JSON.stringify({ role: 'admin' }))}.signature`
    setAccessToken(tokenClaimingAdmin)
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )

    renderWithProviders(<SessionProbe />)

    await screen.findByText('Signed in as viewer')
  })

  it('signs out on a succeeding logout: fires POST /auth/logout, clears the token, empties the cache, navigates to /login with replace (AC 20)', async () => {
    const queryClient = newQueryClient()
    const seen: string[] = []
    server.events.on('request:match', ({ request }) => {
      seen.push(request.url)
    })

    renderNavigableApp(queryClient)
    await screen.findByText('Signed in as admin')

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    await screen.findByText('login-route')
    expect(seen.some((url) => url.endsWith('/auth/logout'))).toBe(true)
    expect(getAccessToken()).toBeNull()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)

    await userEvent.click(screen.getByRole('button', { name: 'Go back' }))
    await screen.findByText('first-route')
    expect(screen.queryByText('Signed in as admin')).not.toBeInTheDocument()

    server.events.removeAllListeners()
  })

  it('signs out on a failing logout too: clears the token, empties the cache, navigates to /login regardless (AC 20)', async () => {
    server.use(
      http.post(
        `${baseURL}/auth/logout`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    const queryClient = newQueryClient()
    const seen: string[] = []
    server.events.on('request:match', ({ request }) => {
      seen.push(request.url)
    })

    renderNavigableApp(queryClient)
    await screen.findByText('Signed in as admin')

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    await screen.findByText('login-route')
    expect(seen.some((url) => url.endsWith('/auth/logout'))).toBe(true)
    expect(getAccessToken()).toBeNull()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)

    server.events.removeAllListeners()
  })

  it('deletes the account: fires DELETE /users/me, clears the token, empties the cache, navigates to /login with the accountDeleted state', async () => {
    const queryClient = newQueryClient()
    const seen: string[] = []
    server.events.on('request:match', ({ request }) => {
      seen.push(`${request.method} ${request.url}`)
    })

    renderNavigableApp(queryClient)
    await screen.findByText('Signed in as admin')

    await userEvent.click(
      screen.getByRole('button', { name: 'Delete account' }),
    )

    await screen.findByText('login-route')
    await screen.findByText('account-deleted-state')
    expect(seen.some((entry) => entry === `DELETE ${baseURL}/users/me`)).toBe(
      true,
    )
    expect(getAccessToken()).toBeNull()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)

    server.events.removeAllListeners()
  })

  it('propagates a failing account deletion to the caller and leaves the session intact', async () => {
    server.use(
      http.delete(`${baseURL}/users/me`, () =>
        HttpResponse.json(
          { error: { code: 'last_admin', message: 'nope' } },
          { status: 409 },
        ),
      ),
    )
    const queryClient = newQueryClient()

    renderNavigableApp(queryClient)
    await screen.findByText('Signed in as admin')
    setAccessToken('test-access-token')

    await userEvent.click(
      screen.getByRole('button', { name: 'Delete account' }),
    )

    await screen.findByText('delete-rejected 409 last_admin')
    expect(screen.getByText('Signed in as admin')).toBeInTheDocument()
    expect(screen.queryByText('login-route')).not.toBeInTheDocument()
    expect(getAccessToken()).toBe('test-access-token')
  })

  it('clears the token, empties the cache and navigates to /login when a session-expired event reaches the mounted provider', async () => {
    const queryClient = newQueryClient()

    renderNavigableApp(queryClient)
    await screen.findByText('Signed in as admin')

    emitSessionExpired()

    await screen.findByText('login-route')
    expect(getAccessToken()).toBeNull()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
  })

  it('renders no protected content and no navigation while booting', () => {
    server.use(
      http.post(`${baseURL}/auth/refresh`, async () => {
        await delay('infinite')
        return HttpResponse.json({
          access_token: 'never-resolves',
          token_type: 'bearer',
          expires_in: 3600,
        })
      }),
    )

    render(
      <MemoryRouter initialEntries={['/']}>
        <QueryClientProvider client={newQueryClient()}>
          <SessionProvider>
            <Routes>
              <Route element={<RequireSession />}>
                <Route path="/" element={<div>protected-content</div>} />
              </Route>
              <Route path="/login" element={<div>login-route</div>} />
            </Routes>
          </SessionProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )

    expect(screen.queryByText('protected-content')).not.toBeInTheDocument()
    expect(screen.queryByText('login-route')).not.toBeInTheDocument()
  })

  it('issues exactly one POST /auth/refresh on boot under StrictMode', async () => {
    let refreshCount = 0
    server.use(
      http.post(`${baseURL}/auth/refresh`, () => {
        refreshCount += 1
        return HttpResponse.json({
          access_token: 'strict-mode-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      }),
    )

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/']}>
          <QueryClientProvider client={newQueryClient()}>
            <SessionProvider>
              <SessionProbe />
            </SessionProvider>
          </QueryClientProvider>
        </MemoryRouter>
      </StrictMode>,
    )

    await screen.findByText('Signed in as admin')
    expect(refreshCount).toBe(1)
  })

  it('establishes a session from invite acceptance: stores the token, refetches /users/me, and replaces /invite with / without rendering Login', async () => {
    server.use(
      http.post(
        `${baseURL}/auth/refresh`,
        () => new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${baseURL}/invites/accept`, () =>
        HttpResponse.json(
          {
            access_token: 'invite-access-token',
            token_type: 'bearer',
            expires_in: 3600,
          },
          { status: 201 },
        ),
      ),
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )

    function InviteProbe() {
      const { acceptInvitation } = useSession()
      return (
        <button
          onClick={() =>
            void acceptInvitation({
              token: 'live-token',
              password: 'x'.repeat(12),
            })
          }
        >
          Accept invite
        </button>
      )
    }

    render(
      <MemoryRouter initialEntries={['/first', '/invite']} initialIndex={1}>
        <QueryClientProvider client={newQueryClient()}>
          <SessionProvider>
            <Routes>
              <Route path="/first" element={<div>first-route</div>} />
              <Route path="/invite" element={<InviteProbe />} />
              <Route path="/" element={<SessionProbe />} />
              <Route
                path="/login"
                element={
                  <>
                    <div>login-route</div>
                    <BackProbe />
                  </>
                }
              />
            </Routes>
          </SessionProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )

    await userEvent.click(
      await screen.findByRole('button', { name: 'Accept invite' }),
    )

    await screen.findByText('Signed in as viewer')
    expect(getAccessToken()).toBe('invite-access-token')
    expect(screen.queryByText('login-route')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
    await screen.findByText('login-route')
    await userEvent.click(screen.getByRole('button', { name: 'Go back' }))
    await screen.findByText('first-route')
  })

  it('establishes a session from signIn through the same sequence: refetches /users/me and replaces /login with /', async () => {
    server.use(
      http.post(
        `${baseURL}/auth/refresh`,
        () => new HttpResponse(null, { status: 401 }),
      ),
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )

    function SignInProbe() {
      const { signIn } = useSession()
      return (
        <button
          onClick={() =>
            void signIn({
              email: 'viewer@dmitri.dev',
              password: 'x'.repeat(12),
            })
          }
        >
          Sign in
        </button>
      )
    }

    render(
      <MemoryRouter initialEntries={['/first', '/login']} initialIndex={1}>
        <QueryClientProvider client={newQueryClient()}>
          <SessionProvider>
            <Routes>
              <Route path="/first" element={<div>first-route</div>} />
              <Route path="/login" element={<SignInProbe />} />
              <Route
                path="/"
                element={
                  <>
                    <SessionProbe />
                    <BackProbe />
                  </>
                }
              />
            </Routes>
          </SessionProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )

    await userEvent.click(
      await screen.findByRole('button', { name: 'Sign in' }),
    )

    await screen.findByText('Signed in as viewer')
    expect(getAccessToken()).toBe('test-access-token')

    await userEvent.click(screen.getByRole('button', { name: 'Go back' }))
    await screen.findByText('first-route')
  })

  it('throws when used outside a SessionProvider', () => {
    function Consumer() {
      useSession()
      return null
    }

    expect(() => render(<Consumer />)).toThrow(
      'useSession must be used within a SessionProvider',
    )
  })
})
