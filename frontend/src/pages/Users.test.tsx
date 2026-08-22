import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  adminProfile,
  otherMember,
  pendingInvite,
  recentMember,
  selfMember,
  viewerProfile,
} from '@/test/mswHandlers'
import { baseURL, directory, signedInAs } from '@/test/usersHarness'
import App from '@/App'
import Users from '@/pages/Users'

describe('Users directory table', () => {
  it('renders every row kind, members before invites', async () => {
    directory([selfMember, recentMember, otherMember], [pendingInvite])
    renderWithProviders(<Users />)

    const table = await screen.findByTestId('users-table')

    const own = screen.getByTestId('user-row-self')
    expect(within(own).getByText(selfMember.email)).toBeInTheDocument()
    expect(
      within(own).getByTestId(`row-role-text-${selfMember.user_id}`),
    ).toHaveTextContent('Admin')
    expect(
      screen.queryByTestId(`row-role-${selfMember.user_id}`),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId(`row-remove-${selfMember.user_id}`),
    ).not.toBeInTheDocument()

    const other = screen.getByTestId(`user-row-${recentMember.user_id}`)
    expect(
      within(other).getByTestId(`row-role-${recentMember.user_id}`),
    ).toBeInTheDocument()
    expect(
      within(other).getByTestId(`row-remove-${recentMember.user_id}`),
    ).toHaveTextContent('Remove')
    expect(
      within(other).getByTestId(`row-status-${recentMember.user_id}`),
    ).toHaveTextContent('Active')

    expect(
      screen.getByTestId(`row-last-seen-${otherMember.user_id}`),
    ).toHaveTextContent('Not recorded yet')

    const invite = screen.getByTestId(`user-row-${pendingInvite.invite_id}`)
    expect(
      within(invite).getByTestId(`row-last-seen-${pendingInvite.invite_id}`),
    ).toHaveTextContent('—')
    expect(
      within(invite).getByTestId(`row-role-text-${pendingInvite.invite_id}`),
    ).toHaveTextContent('Viewer')
    expect(
      within(invite).getByTestId(`row-revoke-${pendingInvite.invite_id}`),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId(`row-remove-${pendingInvite.invite_id}`),
    ).not.toBeInTheDocument()

    const rows = within(within(table).getAllByRole('rowgroup')[1]).getAllByRole(
      'row',
    )
    expect(rows.map((row) => row.dataset.testid)).toEqual([
      'user-row-self',
      `user-row-${recentMember.user_id}`,
      `user-row-${otherMember.user_id}`,
      `user-row-${pendingInvite.invite_id}`,
    ])
  })

  it('renders admins above viewers even when the server lists them last', async () => {
    directory([otherMember, recentMember, selfMember], [])
    renderWithProviders(<Users />)

    const table = await screen.findByTestId('users-table')
    const rows = within(within(table).getAllByRole('rowgroup')[1]).getAllByRole(
      'row',
    )

    expect(rows.map((row) => row.dataset.testid)).toEqual([
      'user-row-self',
      `user-row-${recentMember.user_id}`,
      `user-row-${otherMember.user_id}`,
    ])
  })

  it('carries a title on the cells that truncate, so a clipped value stays readable', async () => {
    directory([selfMember, recentMember], [pendingInvite])
    renderWithProviders(<Users />)

    await screen.findByTestId('users-table')

    const row = screen.getByTestId(`user-row-${recentMember.user_id}`)
    expect(within(row).getByText(recentMember.email)).toHaveAttribute(
      'title',
      recentMember.email,
    )
    const status = screen.getByTestId(`row-status-${pendingInvite.invite_id}`)
    expect(status).toHaveAttribute('title', status.textContent)
  })

  it('renders four column headings plus a screen-reader-only actions header', async () => {
    directory([selfMember, otherMember], [])
    renderWithProviders(<Users />)

    const table = await screen.findByTestId('users-table')
    const headers = within(table).getAllByRole('columnheader')
    expect(headers).toHaveLength(5)
    expect(headers.slice(0, 4).map((header) => header.textContent)).toEqual([
      'Person',
      'Role',
      'Status',
      'Last seen',
    ])
    expect(within(headers[4]).getByText('Actions')).toHaveClass('sr-only')
  })

  it('shows headings over skeleton cells while loading, with no invite action', async () => {
    server.use(
      http.get(`${baseURL}/users`, async () => {
        await delay('infinite')
        return HttpResponse.json({ data: [] })
      }),
      http.get(`${baseURL}/invites`, async () => {
        await delay('infinite')
        return HttpResponse.json({ data: [] })
      }),
    )
    renderWithProviders(<Users />)

    const loading = await screen.findByTestId('users-loading')
    expect(
      within(loading)
        .getAllByRole('columnheader')
        .slice(0, 4)
        .map((header) => header.textContent),
    ).toEqual(['Person', 'Role', 'Status', 'Last seen'])
    expect(screen.queryByTestId('invite-open')).not.toBeInTheDocument()
  })

  it('renders the blank state with the invite action and no table chrome', async () => {
    directory([selfMember], [])
    renderWithProviders(<Users />)

    expect(await screen.findByTestId('users-blank')).toHaveTextContent(
      "You're the only person here.",
    )
    expect(screen.queryByTestId('users-table')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByTestId('invite-open')).toBeInTheDocument()
  })

  it('renders the error state with no rows and no invite action', async () => {
    server.use(
      http.get(
        `${baseURL}/users`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )
    renderWithProviders(<Users />)

    expect(await screen.findByTestId('users-error')).toBeInTheDocument()
    expect(screen.getByTestId('users-error-retry')).toBeInTheDocument()
    expect(screen.queryAllByRole('row')).toHaveLength(0)
    expect(screen.queryByTestId('invite-open')).not.toBeInTheDocument()
  })

  it('refetches when Try again is clicked', async () => {
    let failed = false
    server.use(
      http.get(`${baseURL}/users`, () => {
        if (failed)
          return HttpResponse.json({ data: [selfMember, otherMember] })
        failed = true
        return new HttpResponse(null, { status: 500 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('users-error-retry'))

    expect(await screen.findByTestId('users-table')).toBeInTheDocument()
    expect(screen.getByTestId('user-row-self')).toBeInTheDocument()
  })

  it('routes an admin to the screen and a viewer to the not-found page', async () => {
    signedInAs(adminProfile)
    const admin = renderWithProviders(<App />, { route: '/users' })
    expect(await screen.findByTestId('users-table')).toBeInTheDocument()
    admin.unmount()

    signedInAs(viewerProfile)
    renderWithProviders(<App />, { route: '/users' })
    expect(await screen.findByTestId('not-found')).toBeInTheDocument()
    expect(screen.queryByTestId('users-table')).not.toBeInTheDocument()
    expect(screen.queryByTestId('users-loading')).not.toBeInTheDocument()
    expect(screen.queryByTestId('invite-open')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Users' }),
    ).not.toBeInTheDocument()
  })
})
