import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import LanguageSelect from '@/components/LanguageSelect'
import { LANGUAGE_STORAGE_KEY, LanguageProvider } from './LanguageProvider'

describe('language preference', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('defaults to English and offers Portuguese and Cyrillic Russian', async () => {
    render(
      <LanguageProvider>
        <LanguageSelect />
      </LanguageProvider>,
    )

    const select = screen.getByRole('combobox', { name: 'Idioma' })
    expect(select).toHaveTextContent('English')

    await userEvent.setup().click(select)
    expect(
      screen.getByRole('option', { name: 'Português' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Русский' })).toBeInTheDocument()
  })

  it('persists the selected language', async () => {
    render(
      <LanguageProvider>
        <LanguageSelect />
      </LanguageProvider>,
    )

    const user = userEvent.setup()
    await user.click(screen.getByRole('combobox', { name: 'Idioma' }))
    await user.click(screen.getByRole('option', { name: 'Русский' }))

    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('ru')
  })
})
