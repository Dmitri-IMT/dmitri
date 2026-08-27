import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import Agents from './Agents'

describe('Agents', () => {
  it('renders the title, subtitle and device statement with no controls', () => {
    renderWithProviders(<Agents />)

    expect(screen.getByRole('heading', { name: 'Agents' })).toBeInTheDocument()
    expect(
      screen.getByText('The Dmitri box on your network.'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('agents-note')).toHaveTextContent(
      'Scanning is set up on the Pi itself.',
    )

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
})
