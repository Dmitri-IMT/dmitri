import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { pendingInvite, recentMember, selfMember } from '@/test/mswHandlers'
import { baseURL, directory } from '@/test/usersHarness'
import type { OrgMember } from '@/test/usersHarness'
import Users from '@/pages/Users'

describe('Users role change', () => {
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
})
