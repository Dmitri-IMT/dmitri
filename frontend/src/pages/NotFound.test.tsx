import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import NotFound from './NotFound'

describe('NotFound', () => {
  it('renders the not-found copy verbatim and a real link back to Home', () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>,
    )

    expect(screen.getByText("That page doesn't exist.")).toBeInTheDocument()

    const homeLink = screen.getByRole('link', { name: 'Go to Home' })
    expect(homeLink).toBeInTheDocument()
    expect(homeLink).toHaveAttribute('href', '/')
    expect(homeLink).toHaveAttribute('data-testid', 'not-found-home')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
