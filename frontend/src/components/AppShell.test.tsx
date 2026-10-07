import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { renderWithProviders } from '@/test/renderWithProviders'
import AppShell from './AppShell'

describe('AppShell', () => {
  it('hides the assistant button on routes without a direct context', async () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<p>Page content</p>} />
        </Route>
      </Routes>,
    )

    await screen.findByTestId('top-bar')
    expect(screen.queryByRole('button', { name: /assistant/i })).toBeNull()
  })

  it('renders the assistant button on a scan detail route', async () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/scans/:scanId" element={<p>Scan content</p>} />
        </Route>
      </Routes>,
      { route: '/scans/scan-1' },
    )

    await screen.findByTestId('top-bar')
    expect(
      await screen.findByRole('button', { name: /assistant/i }),
    ).toBeInTheDocument()
  })
})
