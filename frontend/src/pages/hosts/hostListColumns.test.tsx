import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import DataTable from '@/components/DataTable'
import { hostListColumns } from '@/pages/hosts/hostListColumns'
import { hostFixtures } from '@/test/mswHandlers'
import { renderWithProviders } from '@/test/renderWithProviders'

const now = new Date('2026-09-04T12:00:00Z')

const staleHost = {
  ...hostFixtures[0],
  last_seen_at: '2026-07-01T12:00:00.000Z',
}

function renderColumns(quiet: boolean) {
  renderWithProviders(
    <DataTable
      columns={hostListColumns(now, quiet)}
      rows={[staleHost]}
      rowId={(host) => host.host_id}
      testId="column-probe"
      caption="Column probe"
    />,
  )
}

describe('hostListColumns', () => {
  it('does not show a quiet weeks line when the caller marks the group active', async () => {
    renderColumns(false)

    const activeRow = await screen.findByTestId(
      `column-probe-row-${staleHost.host_id}`,
    )
    expect(
      within(activeRow).queryByText(/Not seen for/i),
    ).not.toBeInTheDocument()
  })

  it('shows the quiet weeks line when the caller marks the group quiet', async () => {
    renderColumns(true)

    const quietRow = await screen.findByTestId(
      `column-probe-row-${staleHost.host_id}`,
    )
    expect(within(quietRow).getByText(/Not seen for/i)).toBeInTheDocument()
  })
})
