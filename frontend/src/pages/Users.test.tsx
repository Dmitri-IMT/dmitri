import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  adminProfile,
  createdInvite,
  otherMember,
  pendingInvite,
  recentMember,
  selfMember,
  viewerProfile,
} from '@/test/mswHandlers'
import type { components } from '@/types/openapi'
import App from '@/App'
import Users from './Users'

type OrgMember = components['schemas']['OrgMember']
type PendingInvite = components['schemas']['PendingInvite']

const baseURL = 'http://localhost:8000/api/v1'

function directory(members: OrgMember[], invites: PendingInvite[]) {
  server.use(
    http.get(`${baseURL}/users`, () => HttpResponse.json({ data: members })),
    http.get(`${baseURL}/invites`, () => HttpResponse.json({ data: invites })),
  )
}

function signedInAs(profile: components['schemas']['UserProfileResponse']) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}

describe('Users', () => {
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

  it('opens the role dropdown from its trigger and offers both roles', async () => {
    directory([selfMember, recentMember], [])
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    const trigger = await screen.findByTestId(
      `row-role-${recentMember.user_id}`,
    )
    expect(trigger).toHaveAccessibleName(`Role for ${recentMember.email}`)
    expect(trigger).toHaveTextContent('Viewer')

    await user.click(trigger)
    expect(
      await screen.findByRole('option', { name: 'Admin' }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('option', { name: 'Admin' }))

    const dialog = await screen.findByTestId('role-dialog')
    expect(
      within(dialog).getByRole('heading', {
        name: `Make ${recentMember.email} an admin?`,
      }),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText(
        "They'll be able to run scans and invite people.",
      ),
    ).toBeInTheDocument()
    expect(within(dialog).queryAllByRole('textbox')).toHaveLength(0)
    expect(within(dialog).queryAllByRole('searchbox')).toHaveLength(0)
    expect(within(dialog).getByTestId('role-error')).toBeEmptyDOMElement()
  })

  it('changes the role, raises the toast and refetches both lists', async () => {
    let members: OrgMember[] = [selfMember, recentMember]
    let memberFetches = 0
    let inviteFetches = 0
    server.use(
      http.get(`${baseURL}/users`, () => {
        memberFetches += 1
        return HttpResponse.json({ data: members })
      }),
      http.get(`${baseURL}/invites`, () => {
        inviteFetches += 1
        return HttpResponse.json({ data: [pendingInvite] })
      }),
      http.patch(`${baseURL}/users/:userId`, async ({ request }) => {
        const body = (await request.json()) as { role: OrgMember['role'] }
        members = members.map((member) =>
          member.user_id === recentMember.user_id
            ? { ...member, role: body.role }
            : member,
        )
        return HttpResponse.json({ ...recentMember, role: body.role })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-role-${recentMember.user_id}`),
    )
    await user.click(await screen.findByRole('option', { name: 'Admin' }))
    await user.click(await screen.findByTestId('role-confirm'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `${recentMember.email} is now an admin.`,
    )
    await waitFor(() =>
      expect(screen.queryByTestId('role-dialog')).not.toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(
        screen.getByTestId(`row-role-${recentMember.user_id}`),
      ).toHaveTextContent('Admin'),
    )
    expect(memberFetches).toBe(2)
    expect(inviteFetches).toBe(2)
  })

  it('names the demotion and its consequence, and says so in the toast', async () => {
    const adminMember: OrgMember = { ...recentMember, role: 'admin' }
    directory([selfMember, adminMember], [])
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-role-${adminMember.user_id}`),
    )
    await user.click(await screen.findByRole('option', { name: 'Viewer' }))

    const dialog = await screen.findByTestId('role-dialog')
    expect(
      within(dialog).getByRole('heading', {
        name: `Make ${adminMember.email} a viewer?`,
      }),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText(
        "They'll only be able to see scans, hosts and findings.",
      ),
    ).toBeInTheDocument()

    await user.click(within(dialog).getByTestId('role-confirm'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `${adminMember.email} is now a viewer.`,
    )
  })

  it('cancels without issuing a request, leaving the role unchanged', async () => {
    directory([selfMember, recentMember], [])
    let patchCalls = 0
    server.use(
      http.patch(`${baseURL}/users/:userId`, () => {
        patchCalls += 1
        return HttpResponse.json(recentMember)
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-role-${recentMember.user_id}`),
    )
    await user.click(await screen.findByRole('option', { name: 'Admin' }))
    await user.click(
      within(await screen.findByTestId('role-dialog')).getByRole('button', {
        name: 'Cancel',
      }),
    )

    await waitFor(() =>
      expect(screen.queryByTestId('role-dialog')).not.toBeInTheDocument(),
    )
    expect(patchCalls).toBe(0)
    expect(
      screen.getByTestId(`row-role-${recentMember.user_id}`),
    ).toHaveTextContent('Viewer')
  })

  it('shows one failure message with a retry that succeeds', async () => {
    directory([selfMember, recentMember], [])
    let failed = false
    server.use(
      http.patch(`${baseURL}/users/:userId`, () => {
        if (failed) return HttpResponse.json({ ...recentMember, role: 'admin' })
        failed = true
        return new HttpResponse(null, { status: 500 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-role-${recentMember.user_id}`),
    )
    await user.click(await screen.findByRole('option', { name: 'Admin' }))
    await user.click(await screen.findByTestId('role-confirm'))

    const dialog = await screen.findByTestId('role-dialog')
    await waitFor(() =>
      expect(within(dialog).getByTestId('role-error')).toHaveTextContent(
        "Couldn't change that role.",
      ),
    )
    expect(
      within(dialog).getAllByText("Couldn't change that role."),
    ).toHaveLength(1)
    expect(within(dialog).queryByText(/last admin/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/yourself/i)).not.toBeInTheDocument()

    await user.click(within(dialog).getByTestId('role-confirm'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `${recentMember.email} is now an admin.`,
    )
  })

  it('locks the dialog while the change is in flight', async () => {
    directory([selfMember, recentMember], [])
    server.use(
      http.patch(`${baseURL}/users/:userId`, async () => {
        await delay('infinite')
        return HttpResponse.json(recentMember)
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-role-${recentMember.user_id}`),
    )
    await user.click(await screen.findByRole('option', { name: 'Admin' }))
    await user.click(await screen.findByTestId('role-confirm'))

    const dialog = await screen.findByTestId('role-dialog')
    await waitFor(() =>
      expect(within(dialog).getByTestId('role-confirm')).toHaveTextContent(
        'Changing…',
      ),
    )
    expect(
      within(dialog).queryByRole('button', { name: 'Cancel' }),
    ).not.toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.getByTestId('role-dialog')).toBeInTheDocument()
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
  it("leaves the confirm inert for a mistyped address and for the admin's own, firing no request", async () => {
    directory([selfMember, recentMember, otherMember], [])
    let deleteCalls = 0
    server.use(
      http.delete(`${baseURL}/users/:userId`, () => {
        deleteCalls += 1
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-remove-${recentMember.user_id}`),
    )

    const dialog = await screen.findByTestId('confirm-by-typing-dialog')
    expect(
      within(dialog).getByRole('heading', {
        name: `Remove ${recentMember.email}?`,
      }),
    ).toBeInTheDocument()

    const input = within(dialog).getByLabelText(
      `Type ${recentMember.email} to confirm.`,
    )
    const submit = within(dialog).getByTestId('confirm-by-typing-submit')

    await user.type(input, 'sam@northwind.exampl')
    await user.click(submit)
    expect(deleteCalls).toBe(0)

    await user.clear(input)
    await user.type(input, selfMember.email)
    await user.click(submit)
    expect(deleteCalls).toBe(0)
    expect(screen.getByTestId('confirm-by-typing-dialog')).toBeInTheDocument()
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()

    await user.clear(input)
    await user.type(input, recentMember.email)
    expect(submit).toBeEnabled()
  })

  it('removes the member, raises the toast and refetches both lists', async () => {
    let members: OrgMember[] = [selfMember, recentMember, otherMember]
    let memberFetches = 0
    let inviteFetches = 0
    server.use(
      http.get(`${baseURL}/users`, () => {
        memberFetches += 1
        return HttpResponse.json({ data: members })
      }),
      http.get(`${baseURL}/invites`, () => {
        inviteFetches += 1
        return HttpResponse.json({ data: [] })
      }),
      http.delete(`${baseURL}/users/:userId`, ({ params }) => {
        members = members.filter((member) => member.user_id !== params.userId)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-remove-${recentMember.user_id}`),
    )
    const dialog = await screen.findByTestId('confirm-by-typing-dialog')
    await user.type(
      within(dialog).getByTestId('confirm-by-typing-input'),
      recentMember.email,
    )
    await user.click(within(dialog).getByTestId('confirm-by-typing-submit'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `${recentMember.email} was removed.`,
    )
    await waitFor(() =>
      expect(
        screen.queryByTestId('confirm-by-typing-dialog'),
      ).not.toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(
        screen.queryByTestId(`user-row-${recentMember.user_id}`),
      ).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId('user-row-self')).toBeInTheDocument()
    expect(memberFetches).toBe(2)
    expect(inviteFetches).toBe(2)
  })

  it('shows one removal failure message with a retry that succeeds', async () => {
    let members: OrgMember[] = [selfMember, recentMember, otherMember]
    let failed = false
    server.use(
      http.get(`${baseURL}/users`, () => HttpResponse.json({ data: members })),
      http.get(`${baseURL}/invites`, () => HttpResponse.json({ data: [] })),
      http.delete(`${baseURL}/users/:userId`, ({ params }) => {
        if (!failed) {
          failed = true
          return new HttpResponse(null, { status: 500 })
        }
        members = members.filter((member) => member.user_id !== params.userId)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-remove-${recentMember.user_id}`),
    )
    const dialog = await screen.findByTestId('confirm-by-typing-dialog')
    expect(
      within(dialog).getByTestId('confirm-by-typing-error'),
    ).toBeEmptyDOMElement()

    await user.type(
      within(dialog).getByTestId('confirm-by-typing-input'),
      recentMember.email,
    )
    await user.click(within(dialog).getByTestId('confirm-by-typing-submit'))

    await waitFor(() =>
      expect(
        within(dialog).getByTestId('confirm-by-typing-error'),
      ).toHaveTextContent("Couldn't remove that person."),
    )
    expect(
      within(dialog).getAllByText("Couldn't remove that person."),
    ).toHaveLength(1)
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()

    await user.click(within(dialog).getByTestId('confirm-by-typing-submit'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `${recentMember.email} was removed.`,
    )
  })

  it('names the invited address, confirms in one click and offers no text input', async () => {
    directory([selfMember], [pendingInvite])
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-revoke-${pendingInvite.invite_id}`),
    )

    const dialog = await screen.findByTestId('revoke-dialog')
    expect(
      within(dialog).getByRole('heading', {
        name: `Revoke the invite to ${pendingInvite.email}?`,
      }),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText(
        'Their link stops working immediately. You can invite them again later.',
      ),
    ).toBeInTheDocument()
    expect(within(dialog).queryAllByRole('textbox')).toHaveLength(0)
    expect(within(dialog).queryAllByRole('searchbox')).toHaveLength(0)
    expect(within(dialog).getByTestId('revoke-error')).toBeEmptyDOMElement()

    await user.click(within(dialog).getByTestId('revoke-confirm'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `The invite to ${pendingInvite.email} was revoked.`,
    )
  })

  it('revokes the invite, raises the toast and refetches both lists', async () => {
    let invites: PendingInvite[] = [pendingInvite]
    let memberFetches = 0
    let inviteFetches = 0
    server.use(
      http.get(`${baseURL}/users`, () => {
        memberFetches += 1
        return HttpResponse.json({ data: [selfMember, recentMember] })
      }),
      http.get(`${baseURL}/invites`, () => {
        inviteFetches += 1
        return HttpResponse.json({ data: invites })
      }),
      http.delete(`${baseURL}/invites/:inviteId`, ({ params }) => {
        invites = invites.filter(
          (invite) => invite.invite_id !== params.inviteId,
        )
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-revoke-${pendingInvite.invite_id}`),
    )
    await user.click(
      within(await screen.findByTestId('revoke-dialog')).getByTestId(
        'revoke-confirm',
      ),
    )

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `The invite to ${pendingInvite.email} was revoked.`,
    )
    await waitFor(() =>
      expect(screen.queryByTestId('revoke-dialog')).not.toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(
        screen.queryByTestId(`user-row-${pendingInvite.invite_id}`),
      ).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId('user-row-self')).toBeInTheDocument()
    expect(memberFetches).toBe(2)
    expect(inviteFetches).toBe(2)
  })

  it('shows one revoke failure message with a retry that succeeds', async () => {
    let invites: PendingInvite[] = [pendingInvite]
    let failed = false
    server.use(
      http.get(`${baseURL}/users`, () =>
        HttpResponse.json({ data: [selfMember] }),
      ),
      http.get(`${baseURL}/invites`, () =>
        HttpResponse.json({ data: invites }),
      ),
      http.delete(`${baseURL}/invites/:inviteId`, ({ params }) => {
        if (!failed) {
          failed = true
          return new HttpResponse(null, { status: 500 })
        }
        invites = invites.filter(
          (invite) => invite.invite_id !== params.inviteId,
        )
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-revoke-${pendingInvite.invite_id}`),
    )
    const dialog = await screen.findByTestId('revoke-dialog')
    await user.click(within(dialog).getByTestId('revoke-confirm'))

    await waitFor(() =>
      expect(within(dialog).getByTestId('revoke-error')).toHaveTextContent(
        "Couldn't revoke that invite.",
      ),
    )
    expect(
      within(dialog).getAllByText("Couldn't revoke that invite."),
    ).toHaveLength(1)
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()

    await user.click(within(dialog).getByTestId('revoke-confirm'))

    expect(await screen.findByTestId('toast')).toHaveTextContent(
      `The invite to ${pendingInvite.email} was revoked.`,
    )
  })

  it('reads Revoking… while the revoke is in flight', async () => {
    directory([selfMember], [pendingInvite])
    server.use(
      http.delete(`${baseURL}/invites/:inviteId`, async () => {
        await delay('infinite')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(
      await screen.findByTestId(`row-revoke-${pendingInvite.invite_id}`),
    )
    const dialog = await screen.findByTestId('revoke-dialog')
    await user.click(within(dialog).getByTestId('revoke-confirm'))

    await waitFor(() =>
      expect(within(dialog).getByTestId('revoke-confirm')).toHaveTextContent(
        'Revoking…',
      ),
    )
    expect(
      within(dialog).queryByRole('button', { name: 'Cancel' }),
    ).not.toBeInTheDocument()
  })

  it('preselects Viewer and reads Creating… while the invite is in flight', async () => {
    directory([selfMember], [])
    server.use(
      http.post(`${baseURL}/invites`, async () => {
        await delay('infinite')
        return HttpResponse.json(createdInvite, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    const dialog = await screen.findByTestId('invite-dialog')
    expect(within(dialog).getByTestId('invite-role')).toHaveTextContent(
      'Viewer',
    )
    expect(within(dialog).getByTestId('invite-error')).toBeEmptyDOMElement()

    await user.type(
      within(dialog).getByLabelText('Email'),
      'new@northwind.example',
    )
    await user.click(within(dialog).getByTestId('invite-submit'))

    await waitFor(() =>
      expect(within(dialog).getByTestId('invite-submit')).toHaveTextContent(
        'Creating…',
      ),
    )
  })

  it('names the two roles plainly and explains them in a note above the control', async () => {
    directory([selfMember], [])
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    const dialog = await screen.findByTestId('invite-dialog')

    const note = within(dialog).getByTestId('invite-role-note')
    expect(note).toHaveTextContent(
      'A viewer can see scans, hosts and findings. An admin can also run scans and invite people.',
    )
    expect(within(dialog).getByTestId('invite-role')).toHaveAttribute(
      'aria-describedby',
      note.id,
    )

    await user.click(within(dialog).getByTestId('invite-role'))
    expect(
      (await screen.findAllByRole('option')).map(
        (option) => option.textContent,
      ),
    ).toEqual(['Viewer', 'Admin'])
  })

  it('shows the link built from the returned token, copies it, and raises no toast', async () => {
    directory([selfMember], [])
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    const dialog = await screen.findByTestId('invite-dialog')
    await user.click(within(dialog).getByTestId('invite-role'))
    await user.click(await screen.findByRole('option', { name: /^Admin/ }))
    await user.type(
      within(dialog).getByLabelText('Email'),
      'new@northwind.example',
    )
    await user.click(within(dialog).getByTestId('invite-submit'))

    const created = await screen.findByTestId('invite-created')
    expect(within(created).getByTestId('invite-link')).toHaveTextContent(
      `${window.location.origin}/invite?token=${createdInvite.invite_token}`,
    )
    expect(
      within(created).getByText("This is the only time you'll see this link.", {
        exact: false,
      }),
    ).toBeInTheDocument()
    expect(
      within(created).getByText('new@northwind.example', { exact: false }),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()

    await user.click(within(created).getByTestId('invite-copy'))
    expect(within(created).getByTestId('invite-copy')).toHaveTextContent(
      'Copied',
    )
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
  })

  it('closes on Done and refetches the table with the new pending invite', async () => {
    let invites: PendingInvite[] = []
    server.use(
      http.get(`${baseURL}/users`, () =>
        HttpResponse.json({ data: [selfMember, recentMember] }),
      ),
      http.get(`${baseURL}/invites`, () =>
        HttpResponse.json({ data: invites }),
      ),
      http.post(`${baseURL}/invites`, () => {
        invites = [pendingInvite]
        return HttpResponse.json(createdInvite, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    await user.type(
      within(await screen.findByTestId('invite-dialog')).getByLabelText(
        'Email',
      ),
      pendingInvite.email,
    )
    await user.click(screen.getByTestId('invite-submit'))
    await user.click(await screen.findByTestId('invite-done'))

    await waitFor(() =>
      expect(screen.queryByTestId('invite-dialog')).not.toBeInTheDocument(),
    )
    expect(
      await screen.findByTestId(`user-row-${pendingInvite.invite_id}`),
    ).toHaveTextContent(pendingInvite.email)
    expect(screen.queryByTestId('toast')).not.toBeInTheDocument()
  })

  it('resets to an empty form when inviting someone else', async () => {
    directory([selfMember], [])
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    const dialog = await screen.findByTestId('invite-dialog')
    await user.click(within(dialog).getByTestId('invite-role'))
    await user.click(await screen.findByRole('option', { name: /^Admin/ }))
    await user.type(
      within(dialog).getByLabelText('Email'),
      'new@northwind.example',
    )
    await user.click(within(dialog).getByTestId('invite-submit'))

    await user.click(await screen.findByTestId('invite-again'))

    expect(screen.queryByTestId('invite-created')).not.toBeInTheDocument()
    expect(await screen.findByLabelText('Email')).toHaveValue('')
    expect(screen.getByTestId('invite-role')).toHaveTextContent('Viewer')
  })

  it('tells an existing member apart from a waiting invite, keeping the form', async () => {
    directory([selfMember], [])
    let attempt = 0
    server.use(
      http.post(`${baseURL}/invites`, () => {
        attempt += 1
        return attempt === 1
          ? HttpResponse.json(
              { error: { code: 'email_already_member', message: 'member' } },
              { status: 400 },
            )
          : HttpResponse.json(
              { error: { code: 'invite_already_pending', message: 'pending' } },
              { status: 409 },
            )
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    const dialog = await screen.findByTestId('invite-dialog')
    const email = within(dialog).getByLabelText('Email')
    await user.type(email, recentMember.email)
    await user.click(within(dialog).getByTestId('invite-submit'))

    await waitFor(() =>
      expect(within(dialog).getByTestId('invite-error')).toHaveTextContent(
        'That person is already in your organization.',
      ),
    )
    expect(email).toHaveValue(recentMember.email)
    expect(within(dialog).getByTestId('invite-submit')).toHaveTextContent(
      'Create invite link',
    )

    await user.clear(email)
    await user.type(email, 'ana@northwind.example')
    await user.click(within(dialog).getByTestId('invite-submit'))

    await waitFor(() =>
      expect(within(dialog).getByTestId('invite-error')).toHaveTextContent(
        'That address already has an invite waiting. Revoke it first if you need to send a new one.',
      ),
    )
    expect(email).toHaveValue('ana@northwind.example')
  })

  it('falls back to one generic message with a retry that succeeds', async () => {
    directory([selfMember], [])
    let failed = false
    server.use(
      http.post(`${baseURL}/invites`, () => {
        if (failed) return HttpResponse.json(createdInvite, { status: 201 })
        failed = true
        return new HttpResponse(null, { status: 500 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<Users />)

    await user.click(await screen.findByTestId('invite-open'))
    const dialog = await screen.findByTestId('invite-dialog')
    await user.type(
      within(dialog).getByLabelText('Email'),
      'new@northwind.example',
    )
    await user.click(within(dialog).getByTestId('invite-submit'))

    await waitFor(() =>
      expect(within(dialog).getByTestId('invite-error')).toHaveTextContent(
        "Couldn't create the invite.",
      ),
    )
    expect(within(dialog).getByTestId('invite-submit')).toHaveTextContent(
      'Try again',
    )

    await user.click(within(dialog).getByTestId('invite-submit'))

    expect(await screen.findByTestId('invite-created')).toBeInTheDocument()
  })
})
