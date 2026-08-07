import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import ForgotPassword from './ForgotPassword'

const baseURL = 'http://localhost:8000/api/v1'

function failBootRefresh() {
  server.use(
    http.post(
      `${baseURL}/auth/refresh`,
      () => new HttpResponse(null, { status: 401 }),
    ),
  )
}

function captureRequests() {
  const bodies: unknown[] = []
  server.use(
    http.post(`${baseURL}/auth/forgot-password`, async ({ request }) => {
      bodies.push(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return bodies
}

function renderForgotApp() {
  return renderWithProviders(
    <Routes>
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/login" element={<div>login-route</div>} />
    </Routes>,
    { route: '/forgot-password' },
  )
}

async function submitAddress(address: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Email'), address)
  await user.click(screen.getByTestId('forgot-submit'))
  return user
}

describe('ForgotPassword', () => {
  it('renders the idle form for an anonymous visitor after a failing boot refresh', async () => {
    failBootRefresh()
    renderForgotApp()

    expect(await screen.findByTestId('forgot-idle')).toBeInTheDocument()
    expect(screen.getByTestId('forgot-form')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Log out' })).toBeNull()
    expect(screen.queryByTestId('top-bar')).toBeNull()
    expect(screen.getByTestId('forgot-error')).toBeEmptyDOMElement()

    const interactive = [
      ...screen.queryAllByRole('button'),
      ...screen.queryAllByRole('link'),
      ...screen.queryAllByRole('textbox'),
    ]
    for (const element of interactive) {
      expect(element).toBeEnabled()
      expect(element).not.toHaveAttribute('aria-disabled', 'true')
    }
  })

  it('focuses Email on mount', async () => {
    failBootRefresh()
    renderForgotApp()

    await waitFor(() =>
      expect(screen.getByTestId('forgot-email')).toHaveFocus(),
    )
  })

  it('sends exactly { email } and replaces the form with the confirmation', async () => {
    failBootRefresh()
    const bodies = captureRequests()
    renderForgotApp()

    await submitAddress('ana@northwind.example')

    await screen.findByTestId('forgot-success')
    expect(bodies).toEqual([{ email: 'ana@northwind.example' }])
    expect(screen.queryByTestId('forgot-form')).toBeNull()
    expect(screen.queryByTestId('forgot-email')).toBeNull()
  })

  it('renders the same confirmation for a known and an unknown address, apart from the address', async () => {
    failBootRefresh()
    const known = renderForgotApp()
    await submitAddress('ana@northwind.example')
    const knownText = (
      await screen.findByTestId('forgot-success')
    ).textContent?.replace('ana@northwind.example', '{email}')
    known.unmount()

    renderForgotApp()
    await submitAddress('nobody@example.com')
    const unknownText = (
      await screen.findByTestId('forgot-success')
    ).textContent?.replace('nobody@example.com', '{email}')

    expect(unknownText).toBe(knownText)
    expect(knownText).toContain('Check your email.')
  })

  it('focuses the confirmation heading and offers only Back to sign in', async () => {
    failBootRefresh()
    renderForgotApp()

    await submitAddress('ana@northwind.example')

    await screen.findByTestId('forgot-success')
    await waitFor(() =>
      expect(screen.getByText('Check your email.')).toHaveFocus(),
    )
    expect(screen.getByTestId('forgot-back')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('disables the action in flight and issues no second request', async () => {
    failBootRefresh()
    let requestCount = 0
    server.use(
      http.post(`${baseURL}/auth/forgot-password`, async () => {
        requestCount += 1
        await delay(50)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderForgotApp()

    const user = await submitAddress('ana@northwind.example')

    const submit = screen.getByTestId('forgot-submit')
    expect(submit).toHaveTextContent('Sending…')
    expect(submit).toBeDisabled()
    await user.click(submit)

    await screen.findByTestId('forgot-success')
    expect(requestCount).toBe(1)
  })

  it('recovers from a network failure with the approved error, the typed email, and a usable action', async () => {
    failBootRefresh()
    server.use(
      http.post(`${baseURL}/auth/forgot-password`, () => HttpResponse.error()),
    )
    renderForgotApp()

    await submitAddress('ana@northwind.example')

    await waitFor(() =>
      expect(screen.getByTestId('forgot-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.getByTestId('forgot-email')).toHaveValue(
      'ana@northwind.example',
    )
    expect(screen.getByTestId('forgot-submit')).toBeEnabled()
    expect(screen.getByTestId('forgot-submit')).toHaveTextContent(
      'Send reset link',
    )
    expect(screen.getByTestId('forgot-email')).toHaveFocus()
    expect(screen.queryByTestId('forgot-success')).toBeNull()
  })

  it('recovers from a 500 the same way', async () => {
    failBootRefresh()
    server.use(
      http.post(
        `${baseURL}/auth/forgot-password`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderForgotApp()

    await submitAddress('ana@northwind.example')

    await waitFor(() =>
      expect(screen.getByTestId('forgot-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )
    expect(screen.queryByTestId('forgot-success')).toBeNull()
  })

  it('clears a settled error only when the next submit begins', async () => {
    failBootRefresh()
    server.use(
      http.post(`${baseURL}/auth/forgot-password`, () => HttpResponse.error()),
    )
    renderForgotApp()

    const user = await submitAddress('ana@northwind.example')
    await waitFor(() =>
      expect(screen.getByTestId('forgot-error')).toHaveTextContent(
        "Couldn't reach Dmitri. Try again in a moment.",
      ),
    )

    await user.type(screen.getByTestId('forgot-email'), 'x')
    expect(screen.getByTestId('forgot-error')).toHaveTextContent(
      "Couldn't reach Dmitri. Try again in a moment.",
    )

    server.use(
      http.post(
        `${baseURL}/auth/forgot-password`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    )
    await user.click(screen.getByTestId('forgot-submit'))
    await screen.findByTestId('forgot-success')
  })

  it('routes Back to sign in to /login', async () => {
    failBootRefresh()
    const user = userEvent.setup()
    renderForgotApp()

    await user.click(await screen.findByTestId('forgot-back'))

    await screen.findByText('login-route')
  })
})
