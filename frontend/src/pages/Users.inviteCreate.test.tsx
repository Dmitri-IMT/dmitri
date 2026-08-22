import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import {
  createdInvite,
  pendingInvite,
  recentMember,
  selfMember,
} from '@/test/mswHandlers'
import { baseURL, directory } from '@/test/usersHarness'
import type { PendingInvite } from '@/test/usersHarness'
import Users from '@/pages/Users'

describe('Users invite creation', () => {
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
