import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { adminProfile, viewerProfile } from '@/test/mswHandlers'
import { FirstScanCta, FirstScanNote } from './FirstScanCta'

const baseURL = 'http://localhost:8000/api/v1'

function renderFor(profile: typeof adminProfile | typeof viewerProfile) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
  renderWithProviders(
    <>
      <FirstScanCta />
      <FirstScanNote />
    </>,
  )
}

describe('first-scan affordances', () => {
  it('shows only the Devices link to an admin', async () => {
    renderFor(adminProfile)

    const link = await screen.findByRole('link', { name: 'Run first scan' })
    expect(link).toHaveAttribute('href', '/devices')
    expect(screen.getByTestId('first-scan-cta')).toBe(link)
    expect(screen.queryByTestId('first-scan-note')).not.toBeInTheDocument()
  })

  it('shows only the admin-direction note to a viewer', async () => {
    renderFor(viewerProfile)

    expect(await screen.findByTestId('first-scan-note')).toHaveTextContent(
      'Ask your admin to run the first scan.',
    )
    expect(screen.queryByTestId('first-scan-cta')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
