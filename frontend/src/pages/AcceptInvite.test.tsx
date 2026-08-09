import { StrictMode } from 'react'
import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes, useLocation } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { getAccessToken } from '@/api/tokenStore'
import {
  liveInvite,
  validLoginResponse,
  viewerProfile,
} from '@/test/mswHandlers'
import { useSession } from '@/auth/useSession'
import Login from './Login'
import AcceptInvite from './AcceptInvite'

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

function captureLookups() {
  const bodies: unknown[] = []
  server.use(
    http.post(`${baseURL}/invites/lookup`, async ({ request }) => {
      bodies.push(await request.json())
      return HttpResponse.json(liveInvite)
    }),
  )
  return bodies
}

function captureAccepts() {
  const bodies: unknown[] = []
  server.use(
    http.post(`${baseURL}/invites/accept`, async ({ request }) => {
      bodies.push(await request.json())
      return HttpResponse.json(validLoginResponse, { status: 201 })
    }),
  )
  return bodies
}

function respondToAccept(status: number, code: string) {
  server.use(
    http.post(`${baseURL}/invites/accept`, () =>
      HttpResponse.json({ error: { code, message: 'nope' } }, { status }),
    ),
  )
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-probe">{location.pathname}</div>
}

function HomeStub() {
  const { user } = useSession()
  return <div data-testid="home-stub">{user?.email ?? 'no profile'}</div>
}

function renderInviteApp(route = '/invite?token=live-token', strict = false) {
  const tree = (
    <>
      <LocationProbe />
      <Routes>
        <Route path="/invite" element={<AcceptInvite />} />
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<HomeStub />} />
      </Routes>
    </>
  )
  return renderWithProviders(strict ? <StrictMode>{tree}</StrictMode> : tree, {
    route,
  })
}

async function submit(password = VALID, confirmation = VALID) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Password'), password)
  await user.type(screen.getByLabelText('Confirm password'), confirmation)
  await user.click(screen.getByTestId('invite-submit'))
  return user
}

describe('AcceptInvite', () => {
  it('renders the dead state with zero lookups when the token is absent', async () => {
    failBootRefresh()
    const lookups = captureLookups()
    renderInviteApp('/invite')

    expect(await screen.findByTestId('invite-dead')).toBeInTheDocument()
    expect(screen.queryByTestId('invite-form')).toBeNull()
    await waitFor(() =>
      expect(screen.getByText('This invite has expired.')).toHaveFocus(),
    )
    expect(lookups).toEqual([])
  })

  it('renders the signed-in block for an authenticated visitor with no lookup or accept requests', async () => {
    const lookups = captureLookups()
    const accepts = captureAccepts()
    renderInviteApp()

    expect(await screen.findByTestId('invite-signed-in')).toBeInTheDocument()
    expect(screen.queryByTestId('invite-form')).toBeNull()
    expect(screen.queryByTestId('invite-password')).toBeNull()
    await waitFor(() =>
      expect(screen.getByText("You're already signed in.")).toHaveFocus(),
    )
    expect(lookups).toEqual([])
    expect(accepts).toEqual([])
  })

  it('signs out from the signed-in block and returns to Login', async () => {
    const matched: string[] = []
    server.events.on('request:match', ({ request }) => {
      matched.push(request.url)
    })
    const user = userEvent.setup()
    renderInviteApp()

    const signOutButton = await screen.findByTestId('invite-sign-out')
    expect(matched.some((url) => url.endsWith('/invites/lookup'))).toBe(false)
    await user.click(signOutButton)

    await screen.findByTestId('login-form')
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/login')
    expect(matched.some((url) => url.endsWith('/auth/logout'))).toBe(true)
    server.events.removeAllListeners()
  })

  it('renders the loading card and issues no lookup while the session is booting', async () => {
    const lookups = captureLookups()
    server.use(
      http.post(`${baseURL}/auth/refresh`, async () => {
        await delay(200)
        return HttpResponse.json(validLoginResponse)
      }),
    )
    renderInviteApp()

    expect(await screen.findByTestId('invite-loading')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.queryByTestId('invite-form')).toBeNull()
    expect(lookups).toEqual([])
  })

  it('posts exactly { token } and renders the org and role greeting without any email', async () => {
    failBootRefresh()
    const lookups = captureLookups()
    const { container } = renderInviteApp()

    expect(await screen.findByTestId('invite-ready')).toHaveTextContent(
      "You've been invited to Northwind Security with the viewer role. Pick a password and you're in.",
    )
    expect(lookups).toEqual([{ token: 'live-token' }])
    expect(container.innerHTML).not.toContain(liveInvite.email)
    expect(container.innerHTML).not.toContain('live-token')
    expect(screen.queryByLabelText('Email')).toBeNull()
    await waitFor(() =>
      expect(screen.getByTestId('invite-password')).toHaveFocus(),
    )
    expect(screen.getByTestId('invite-password')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByTestId('invite-confirm')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
  })

  it('performs one effective lookup under StrictMode', async () => {
    failBootRefresh()
    const lookups = captureLookups()
    renderInviteApp('/invite?token=live-token', true)

    await screen.findByTestId('invite-form')
    expect(lookups).toEqual([{ token: 'live-token' }])
  })

  it('renders the dead state without a retry control on lookup 410', async () => {
    failBootRefresh()
    server.use(
      http.post(`${baseURL}/invites/lookup`, () =>
        HttpResponse.json(
          { error: { code: 'invalid_invite_token', message: 'gone' } },
          { status: 410 },
        ),
      ),
    )
    renderInviteApp()

    expect(await screen.findByTestId('invite-dead')).toBeInTheDocument()
    expect(screen.queryByTestId('invite-form')).toBeNull()
    expect(screen.queryByTestId('invite-retry')).toBeNull()
  })

  it('offers Retry as the only path back after a lookup service failure', async () => {
    failBootRefresh()
    server.use(
      http.post(`${baseURL}/invites/lookup`, () => HttpResponse.error()),
    )
    const user = userEvent.setup()
    renderInviteApp()

    expect(await screen.findByTestId('invite-error')).toHaveTextContent(
      "Couldn't reach Dmitri. Try again in a moment.",
    )
    expect(screen.queryByTestId('invite-dead')).toBeNull()
    expect(screen.queryByTestId('invite-form')).toBeNull()

    server.use(
      http.post(`${baseURL}/invites/lookup`, () =>
        HttpResponse.json(liveInvite),
      ),
    )
    await user.click(screen.getByTestId('invite-retry'))

    await screen.findByTestId('invite-form')
  })

  it('renders the mismatch error and issues zero accept calls', async () => {
    failBootRefresh()
    const accepts = captureAccepts()
    renderInviteApp()

    await submit(VALID, 'a-different-password')

    await waitFor(() =>
      expect(screen.getByTestId('invite-confirm-error')).toHaveTextContent(
        "Those two passwords don't match.",
      ),
    )
    expect(accepts).toEqual([])
    expect(screen.getByTestId('invite-confirm')).toHaveFocus()
    expect(screen.getByTestId('invite-form')).toBeInTheDocument()
  })

  it('posts exactly { token, password } and never the lookup email', async () => {
    failBootRefresh()
    const accepts = captureAccepts()
    renderInviteApp()

    await submit()

    await screen.findByTestId('home-stub')
    expect(accepts).toEqual([{ token: 'live-token', password: VALID }])
  })

  it('stores the token, refreshes the profile, and lands on Home without ever rendering Login on 201', async () => {
    failBootRefresh()
    server.use(
      http.get(`${baseURL}/users/me`, () => HttpResponse.json(viewerProfile)),
    )
    renderInviteApp()

    await submit()

    expect(await screen.findByTestId('home-stub')).toHaveTextContent(
      viewerProfile.email,
    )
    expect(screen.queryByTestId('login-form')).toBeNull()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
    expect(getAccessToken()).toBe(validLoginResponse.access_token)
  })

  it('keeps the form and shows the policy error beside Password on 400', async () => {
    failBootRefresh()
    respondToAccept(400, 'password_policy_violation')
    renderInviteApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('invite-password-error')).toHaveTextContent(
        "That password isn't strong enough. Try a longer one that isn't based on a name or a date.",
      ),
    )
    expect(screen.getByTestId('invite-form')).toBeInTheDocument()
    expect(screen.getByTestId('invite-password')).toHaveFocus()
  })

  it('keeps the form and offers Login on 400 email_already_registered', async () => {
    failBootRefresh()
    respondToAccept(400, 'email_already_registered')
    renderInviteApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('invite-account-error')).toHaveTextContent(
        'That address already has an account. Sign in instead.',
      ),
    )
    expect(screen.getByTestId('invite-sign-in')).toHaveAttribute(
      'href',
      '/login',
    )
    expect(screen.getByTestId('invite-form')).toBeInTheDocument()
    expect(screen.getByTestId('invite-password')).toHaveValue(VALID)
    expect(screen.getByTestId('invite-confirm')).toHaveValue(VALID)
  })

  it('renders the same dead state and removes the form on accept 410', async () => {
    failBootRefresh()
    respondToAccept(410, 'invalid_invite_token')
    renderInviteApp()

    await submit()

    expect(await screen.findByTestId('invite-dead')).toBeInTheDocument()
    expect(screen.queryByTestId('invite-form')).toBeNull()
    expect(screen.queryByTestId('invite-retry')).toBeNull()
  })

  it('recovers from an accept network failure with a usable form and no false success', async () => {
    failBootRefresh()
    server.use(
      http.post(`${baseURL}/invites/accept`, () => HttpResponse.error()),
    )
    renderInviteApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('invite-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.getByTestId('invite-form')).toBeInTheDocument()
    expect(screen.queryByTestId('invite-dead')).toBeNull()
    expect(screen.getByTestId('invite-submit')).toBeEnabled()
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/invite')
  })

  it('recovers from a 500 the same way', async () => {
    failBootRefresh()
    server.use(
      http.post(
        `${baseURL}/invites/accept`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderInviteApp()

    await submit()

    await waitFor(() =>
      expect(screen.getByTestId('invite-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.queryByTestId('invite-dead')).toBeNull()
  })

  it('disables the action in flight and issues no second accept request', async () => {
    failBootRefresh()
    let requestCount = 0
    server.use(
      http.post(`${baseURL}/invites/accept`, async () => {
        requestCount += 1
        await delay(50)
        return HttpResponse.json(validLoginResponse, { status: 201 })
      }),
    )
    renderInviteApp()

    const user = await submit()

    const button = screen.getByTestId('invite-submit')
    expect(button).toHaveTextContent('Creating your account…')
    expect(button).toBeDisabled()
    await user.click(button)

    await screen.findByTestId('home-stub')
    expect(requestCount).toBe(1)
  })

  it('keeps a settled message while editing and clears it when the next submit begins', async () => {
    failBootRefresh()
    respondToAccept(400, 'password_policy_violation')
    renderInviteApp()

    const user = await submit()
    await waitFor(() =>
      expect(
        screen.getByTestId('invite-password-error'),
      ).not.toBeEmptyDOMElement(),
    )

    await user.type(screen.getByTestId('invite-password'), 'x')
    expect(
      screen.getByTestId('invite-password-error'),
    ).not.toBeEmptyDOMElement()

    await user.type(screen.getByTestId('invite-confirm'), 'x')
    server.use(
      http.post(`${baseURL}/invites/accept`, () =>
        HttpResponse.json(validLoginResponse, { status: 201 }),
      ),
    )
    await user.click(screen.getByTestId('invite-submit'))

    await screen.findByTestId('home-stub')
  })
})
