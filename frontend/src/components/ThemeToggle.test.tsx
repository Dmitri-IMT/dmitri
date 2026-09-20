import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/renderWithProviders'
import ThemeToggle, { THEME_STORAGE_KEY } from './ThemeToggle'

describe('ThemeToggle', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dmitri-dark')
    localStorage.removeItem(THEME_STORAGE_KEY)
  })

  afterEach(() => {
    document.documentElement.classList.remove('dmitri-dark')
    localStorage.removeItem(THEME_STORAGE_KEY)
  })

  it('toggles the persisted night mode', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />)

    const toggle = screen.getByRole('button', { name: 'Ativar modo noturno' })
    await user.click(toggle)

    expect(document.documentElement).toHaveClass('dmitri-dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(
      screen.getByRole('button', { name: 'Ativar modo claro' }),
    ).toBeInTheDocument()
  })
})
