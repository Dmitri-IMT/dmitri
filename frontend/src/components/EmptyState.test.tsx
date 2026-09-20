import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from './EmptyState'

describe('EmptyState', () => {
  it('renders action and note slots independently when both are provided', () => {
    render(
      <EmptyState
        testId="blank"
        heading="Nothing here."
        body="There are no records yet."
        action={<button type="button">Do something</button>}
        note={<p>Additional context.</p>}
      />,
    )

    expect(
      screen.getByRole('button', { name: 'Do something' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Additional context.')).toBeInTheDocument()
    expect(screen.getByTestId('blank')).toHaveAttribute('role', 'status')
    expect(screen.getByRole('heading')).toHaveAttribute('id', 'blank-heading')
  })

  it('renders an action without requiring a note', () => {
    render(
      <EmptyState
        testId="blank"
        heading="Nothing here."
        body="There are no records yet."
        action={<button type="button">Do something</button>}
      />,
    )

    expect(
      screen.getByRole('button', { name: 'Do something' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Additional context.')).not.toBeInTheDocument()
  })

  it('renders a note without requiring an action', () => {
    render(
      <EmptyState
        testId="blank"
        heading="Nothing here."
        body="There are no records yet."
        note={<p>Additional context.</p>}
      />,
    )

    expect(screen.getByText('Additional context.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders no extra slot content when both slots are omitted', () => {
    render(
      <EmptyState
        testId="blank"
        heading="Nothing here."
        body="There are no records yet."
      />,
    )

    expect(screen.getByTestId('blank')).toHaveTextContent(
      'Nothing here.There are no records yet.',
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
