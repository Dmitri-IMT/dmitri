import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import Timestamp from './Timestamp'

afterEach(() => {
  cleanup()
})

const NOW = new Date('2026-07-29T12:00:00.000Z')
const DAY_MS = 24 * 60 * 60 * 1000

describe('Timestamp', () => {
  it('renders relative text just inside the 7-day boundary', () => {
    const value = new Date(NOW.getTime() - (7 * DAY_MS - 1000)).toISOString()

    render(<Timestamp value={value} now={NOW} />)

    expect(screen.getByText('7 days ago')).toBeInTheDocument()
  })

  it('renders an absolute date once the value reaches the 7-day boundary', () => {
    const value = new Date(NOW.getTime() - 7 * DAY_MS).toISOString()

    render(<Timestamp value={value} now={NOW} />)

    expect(screen.queryByText(/days ago$/)).not.toBeInTheDocument()
    expect(
      screen.getByText(/^[A-Z][a-z]{2} \d{1,2}, \d{2}:\d{2}$/),
    ).toBeInTheDocument()
  })

  it('carries the exact value in the title attribute', () => {
    const value = new Date(NOW.getTime() - 2 * DAY_MS).toISOString()

    render(<Timestamp value={value} now={NOW} />)

    const element = screen.getByText('2 days ago')

    expect(element).toHaveAttribute('title', new Date(value).toLocaleString())
  })
})
