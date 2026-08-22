import type { ReactNode } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import LocationProbe from '@/test/LocationProbe'
import { adminProfile } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import Settings from '@/pages/Settings'
import Login from '@/pages/Login'

type UserProfileResponse = components['schemas']['UserProfileResponse']

export const baseURL = 'http://localhost:8000/api/v1'
export const CURRENT = 'old-long-enough-password'
export const NEXT = 'new-long-enough-password'
export const ACTIVITY_NOTE =
  "Your organization's admins can see when you last used Dmitri and when you last signed in. We record only these times — not what you viewed or did."
export const LAST_ADMIN_REFUSAL =
  "You're the only admin. Make someone else an admin first, then you can leave."
export const GENERIC_LEAVE_FAILURE = "Couldn't delete your account."

export function signedInAs(profile: UserProfileResponse) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}

export function captureChangeRequests() {
  const bodies: unknown[] = []
  server.use(
    http.post(`${baseURL}/auth/change-password`, async ({ request }) => {
      bodies.push(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return bodies
}

export function countRefreshes() {
  const calls: number[] = []
  server.use(
    http.post(`${baseURL}/auth/refresh`, () => {
      calls.push(1)
      return HttpResponse.json({
        access_token: 'refreshed-token',
        token_type: 'bearer',
        expires_in: 3600,
      })
    }),
  )
  return calls
}

export function captureDeleteRequests() {
  const urls: string[] = []
  server.use(
    http.delete(`${baseURL}/users/me`, ({ request }) => {
      urls.push(request.url)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return urls
}

export function refuseDelete(status: number, code: string) {
  const urls: string[] = []
  server.use(
    http.delete(`${baseURL}/users/me`, ({ request }) => {
      urls.push(request.url)
      return HttpResponse.json({ error: { code, message: 'nope' } }, { status })
    }),
  )
  return urls
}

export function respond(status: number, code: string) {
  server.use(
    http.post(`${baseURL}/auth/change-password`, () =>
      HttpResponse.json({ error: { code, message: 'nope' } }, { status }),
    ),
  )
}

function renderAt(login: ReactNode) {
  return renderWithProviders(
    <>
      <LocationProbe />
      <Routes>
        <Route path="/settings" element={<Settings />} />
        <Route path="/login" element={login} />
      </Routes>
    </>,
    { route: '/settings' },
  )
}

export function renderSettings() {
  return renderAt(<div data-testid="login-route" />)
}

// The arrival-note assertions need the real Login screen, not the route stub.
export function renderSettingsWithLogin() {
  return renderAt(<Login />)
}

export async function openPassword() {
  const user = userEvent.setup()
  await user.click(await screen.findByTestId('settings-password-trigger'))
  await screen.findByTestId('settings-password-dialog')
  return user
}

export async function submit(
  current = CURRENT,
  next = NEXT,
  confirmation = NEXT,
) {
  const user = await openPassword()
  await user.type(screen.getByLabelText('Current password'), current)
  await user.type(screen.getByLabelText('New password'), next)
  await user.type(screen.getByLabelText('Confirm new password'), confirmation)
  await user.click(screen.getByTestId('settings-submit'))
  return user
}

export async function openLeave() {
  const user = userEvent.setup()
  await user.click(await screen.findByTestId('settings-leave-trigger'))
  await screen.findByTestId('confirm-by-typing-dialog')
  return user
}

export async function confirmLeave(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByTestId('confirm-by-typing-input'),
    adminProfile.email,
  )
  await user.click(screen.getByTestId('confirm-by-typing-submit'))
}
