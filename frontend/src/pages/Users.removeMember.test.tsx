import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithProviders } from '@/test/renderWithProviders'
import { otherMember, recentMember, selfMember } from '@/test/mswHandlers'
import { baseURL, directory } from '@/test/usersHarness'
import type { OrgMember } from '@/test/usersHarness'
import Users from '@/pages/Users'

describe('Users member removal', () => {
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
})
