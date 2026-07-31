import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/test/setup'
import { criticalFinding, highFinding } from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import FindingDeck from './FindingDeck'

type FindingRecord = components['schemas']['FindingRecord']

function renderDeck(findings: FindingRecord[], extra?: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      {extra}
      <FindingDeck findings={findings} />
    </QueryClientProvider>,
  )
  return {
    ...utils,
    rerenderDeck: (nextFindings: FindingRecord[]) =>
      utils.rerender(
        <QueryClientProvider client={queryClient}>
          {extra}
          <FindingDeck findings={nextFindings} />
        </QueryClientProvider>,
      ),
  }
}

describe('FindingDeck', () => {
  it('steps forward and back through every card, tracking "{i} of {n}", and removes the spent end-stop arrow rather than disabling it (AC 18)', async () => {
    const user = userEvent.setup()
    renderDeck([criticalFinding, highFinding])

    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('1 of 2')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2023-38408 on 192\.168\.1\.42\./,
    )
    expect(screen.queryByTestId('home-deck-prev')).toBeNull()
    const next = screen.getByRole('button', { name: 'Next finding' })
    expect(next).toBeEnabled()
    expect(next).not.toHaveAttribute('aria-disabled', 'true')

    await user.click(next)
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('2 of 2')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2017-5638 on 192\.168\.1\.42\./,
    )
    expect(screen.queryByTestId('home-deck-next')).toBeNull()
    const previous = screen.getByRole('button', { name: 'Previous finding' })
    expect(previous).toBeEnabled()
    expect(previous).not.toHaveAttribute('aria-disabled', 'true')

    await user.click(previous)
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('1 of 2')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2023-38408 on 192\.168\.1\.42\./,
    )
    expect(screen.queryByTestId('home-deck-prev')).toBeNull()
    expect(screen.getByRole('button', { name: 'Next finding' })).toBeEnabled()
  })

  it('does not wrap: ArrowLeft on the first card and ArrowRight on the last leave position and card unchanged, proven via the keyboard since the end-stop button no longer exists (AC 18)', async () => {
    const user = userEvent.setup()
    renderDeck([criticalFinding, highFinding])

    await user.click(screen.getByTestId('home-deck'))
    await user.keyboard('{ArrowLeft}')
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('1 of 2')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2023-38408 on 192\.168\.1\.42\./,
    )
    expect(screen.queryByTestId('home-deck-prev')).toBeNull()

    await user.keyboard('{ArrowRight}')
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('2 of 2')

    await user.keyboard('{ArrowRight}')
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('2 of 2')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2017-5638 on 192\.168\.1\.42\./,
    )
    expect(screen.queryByTestId('home-deck-next')).toBeNull()
  })

  it('keeps the vacated end-stop slot as an aria-hidden, non-interactive placeholder rather than collapsing the row, and skips it in tab order (AC 18)', async () => {
    const user = userEvent.setup()
    const { container } = renderDeck([criticalFinding, highFinding])

    expect(screen.queryByTestId('home-deck-prev')).toBeNull()
    const placeholders = container.querySelectorAll('[aria-hidden="true"]')
    expect(placeholders).toHaveLength(1)
    expect(placeholders[0]).not.toHaveAttribute('tabindex')

    await user.tab()
    expect(screen.getByTestId('home-deck')).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Next finding' })).toHaveFocus()
  })

  it('steps only via arrow keys while the deck holds focus, and ignores an ArrowRight dispatched with focus elsewhere', async () => {
    const user = userEvent.setup()
    renderDeck(
      [criticalFinding, highFinding],
      <button type="button">Outside</button>,
    )

    await user.click(screen.getByRole('button', { name: 'Outside' }))
    await user.keyboard('{ArrowRight}')
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('1 of 2')

    await user.click(screen.getByTestId('home-deck'))
    await user.keyboard('{ArrowRight}')
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('2 of 2')

    await user.keyboard('{ArrowLeft}')
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('1 of 2')
  })

  it('renders the card alone with exactly one finding, with no arrows and no position line', () => {
    renderDeck([criticalFinding])

    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2023-38408 on 192\.168\.1\.42\./,
    )
    expect(
      screen.queryByRole('button', { name: 'Previous finding' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Next finding' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId('home-deck-position')).not.toBeInTheDocument()
  })

  it('renders nothing when there are no findings', () => {
    const { container } = renderDeck([])

    expect(container).toBeEmptyDOMElement()
  })

  it('marks the card region aria-live="polite" so stepping is announced', () => {
    renderDeck([criticalFinding, highFinding])

    expect(screen.getByTestId('home-deck-card')).toHaveAttribute(
      'aria-live',
      'polite',
    )
  })

  it('resets the index to the first card when the underlying findings array changes', async () => {
    const user = userEvent.setup()
    const { rerenderDeck } = renderDeck([criticalFinding, highFinding])

    await user.click(screen.getByRole('button', { name: 'Next finding' }))
    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('2 of 2')

    rerenderDeck([highFinding, criticalFinding])

    expect(screen.getByTestId('home-deck-position')).toHaveTextContent('1 of 2')
    expect(screen.getByTestId('home-deck-card')).toHaveTextContent(
      /CVE-2017-5638 on 192\.168\.1\.42\./,
    )
  })

  it('issues no request while stepping through every card, forward and back past both ends, by keyboard and by click (AC 18)', async () => {
    const user = userEvent.setup()
    let requestCount = 0
    const countRequest = () => {
      requestCount += 1
    }
    server.events.on('request:match', countRequest)

    try {
      renderDeck([criticalFinding, highFinding])

      await user.click(screen.getByTestId('home-deck'))
      await user.keyboard(
        '{ArrowRight}{ArrowRight}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowRight}',
      )
      await user.click(screen.getByRole('button', { name: 'Previous finding' }))
      await user.click(screen.getByRole('button', { name: 'Next finding' }))

      expect(requestCount).toBe(0)
    } finally {
      server.events.removeAllListeners()
    }
  })
})
