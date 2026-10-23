import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { useState } from 'react'
import ProblemsTable from './ProblemsTable'
import { criticalFinding } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'
const findings = Array.from({ length: 7 }, (_, i) => ({
  ...criticalFinding,
  finding_id: `finding-${i}`,
  title: `Problem ${i}`,
  risk_score: i * 10,
  demonstrated: i === 0,
}))
function Table({ deep = null }: { deep?: string | null }) {
  const [open, setOpen] = useState(deep)
  return (
    <ProblemsTable
      findings={findings}
      openFindingId={open}
      onOpenFindingChange={setOpen}
    />
  )
}
it('orders by risk, shows five rows and reveals the rest', async () => {
  const user = userEvent.setup()
  renderWithProviders(<Table />)
  const table = screen.getByTestId('problems-table')
  expect(within(table).getAllByRole('row')).toHaveLength(6)
  expect(within(table).getAllByRole('row')[1]).toHaveTextContent('Problem 6')
  await user.click(screen.getByRole('button', { name: 'Show 2 more' }))
  expect(within(table).getAllByRole('row')).toHaveLength(8)
  await user.click(screen.getByTestId('problems-table-sort-risk'))
  expect(within(table).getAllByRole('row')[1]).toHaveTextContent('Problem 0')
})
it('opens a deep-linked finding outside the first five', () => {
  renderWithProviders(<Table deep="finding-0" />)
  expect(screen.getByTestId('problems-table-panel-finding-0')).toBeVisible()
  expect(screen.getByTestId('finding-tech-toggle')).toHaveAttribute(
    'aria-expanded',
    'false',
  )
})
it('filters to confirmed evidence with the select', async () => {
  const user = userEvent.setup()
  renderWithProviders(<Table />)
  await user.click(screen.getByRole('combobox'))
  await user.click(screen.getByRole('option', { name: 'Confirmed only' }))
  expect(
    within(screen.getByTestId('problems-table')).getAllByRole('row'),
  ).toHaveLength(2)
  expect(screen.getByTestId('problems-table-row-finding-0')).toBeVisible()
})

it('limits long machine labels and keeps their full accessible name and hover text', () => {
  const name = 'dmitri-sim-dev-target-1.dmitri-sim-dev_default'
  renderWithProviders(
    <ProblemsTable
      findings={[{ ...criticalFinding, host_hostname: name }]}
      openFindingId={null}
      onOpenFindingChange={() => {}}
    />,
  )
  const link = screen.getByRole('link', { name })
  expect(link).toHaveTextContent('dmitri-sim-dev-target...')
  expect(link.textContent).toHaveLength(24)
  expect(link).toHaveAttribute('title', name)
  expect(link).toHaveClass('max-w-full')
  expect(link.firstElementChild).toHaveClass('truncate')
})
