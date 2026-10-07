import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { renderWithProviders } from '@/test/renderWithProviders'
import AppShell from './AppShell'

describe('AppShell', () => {
  it('renders the floating assistant button on any route', async () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<p>Page content</p>} />
        </Route>
      </Routes>,
    )

    await screen.findByTestId('top-bar')
    expect(
      await screen.findByRole('button', { name: /assistant/i }),
    ).toBeInTheDocument()
  })
})
