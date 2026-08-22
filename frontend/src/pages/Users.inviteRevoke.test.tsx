import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { pendingInvite, recentMember, selfMember } from '@/test/mswHandlers'
import { baseURL, directory } from '@/test/usersHarness'
import type { PendingInvite } from '@/test/usersHarness'
import Users from '@/pages/Users'

describe('Users invite revoke', () => {
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
})
