import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import AttentionWord from '@/components/AttentionWord'

describe('AttentionWord', () => {
  it.each([
    ['informational', 'For awareness'],
    ['review', 'Needs review'],
    ['priority', 'Priority review'],
  ] as const)('renders %s as neutral attention copy', (attention, label) => {
    render(<AttentionWord attention={attention} />)

    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.queryByText(/severity|cvss/i)).not.toBeInTheDocument()
  })
})
