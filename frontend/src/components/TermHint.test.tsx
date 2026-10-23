import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import TermHint from './TermHint'
import { renderWithProviders } from '@/test/renderWithProviders'

it('opens on click, closes on Escape and returns focus to the term', async () => {
  const user = userEvent.setup()
  renderWithProviders(
    <TermHint term="cvss" label="CVSS">
      <p>General severity.</p>
    </TermHint>,
  )
  const trigger = screen.getByRole('button', { name: 'CVSS' })
  await user.hover(trigger)
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  await user.click(trigger)
  expect(screen.getByRole('tooltip')).toHaveTextContent('General severity.')
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})
it('keeps only one hint open across separate terms', async () => {
  const user = userEvent.setup()
  renderWithProviders(
    <>
      <TermHint term="one" label="One">
        First
      </TermHint>
      <TermHint term="two" label="Two">
        Second
      </TermHint>
    </>,
  )
  await user.click(screen.getByRole('button', { name: 'One' }))
  await user.click(screen.getByRole('button', { name: 'Two' }))
  expect(screen.queryByTestId('term-hint-one')).not.toBeInTheDocument()
  expect(screen.getByTestId('term-hint-two')).toBeVisible()
})
it('opens with the keyboard and dismisses outside', async () => {
  const user = userEvent.setup()
  renderWithProviders(
    <>
      <TermHint term="one" label="One">
        First
      </TermHint>
      <p>Outside</p>
    </>,
  )
  await user.tab()
  await user.keyboard('{Enter}')
  expect(screen.getByRole('tooltip')).toBeVisible()
  await user.click(screen.getByText('Outside'))
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
})
