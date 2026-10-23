import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/setup'
import type { AIChatHistoryEntry } from '@/api/ai'
import GlobalAssistant from './GlobalAssistant'

const api = 'http://localhost:8000/api/v1'
const scopeId = '00000000-0000-4000-8000-000000000001'
const conversationId = '00000000-0000-4000-8000-000000000002'
const saved: AIChatHistoryEntry = {
  message_id: '00000000-0000-4000-8000-000000000003',
  conversation_id: conversationId,
  question: 'My earlier question',
  answer: 'The earlier answer is still here.',
  uncertainties: [],
  referenced_finding_ids: [],
  created_at: '2026-10-23T12:00:00Z',
}

it('restores a saved chat from the clock, starts a separate chat with the pencil, and retains both after remount', async () => {
  const user = userEvent.setup()
  const messages = [saved]
  server.use(
    http.get(`${api}/ai/chat/conversations`, () =>
      HttpResponse.json({
        data: messages.map((message) => ({
          conversation_id: message.conversation_id,
          title: message.question,
          updated_at: message.created_at,
        })),
        has_more: false,
      }),
    ),
    http.get(`${api}/ai/chat/history`, ({ request }) =>
      HttpResponse.json({
        data: messages.filter(
          (message) =>
            message.conversation_id ===
            new URL(request.url).searchParams.get('conversation_id'),
        ),
        has_more: false,
      }),
    ),
    http.post(`${api}/ai/chat`, async ({ request }) => {
      const body = (await request.json()) as {
        question: string
        conversation_id: string
      }
      const message = {
        ...saved,
        ...body,
        message_id: crypto.randomUUID(),
        answer: 'The new answer is saved.',
      }
      messages.push(message)
      return HttpResponse.json(message)
    }),
  )
  const view = renderWithProviders(<GlobalAssistant />, {
    route: `/scans/${scopeId}`,
  })
  await user.click(screen.getByTestId('top-bar-assistant'))
  expect(screen.queryByText('This scan')).not.toBeInTheDocument()
  expect(screen.queryByText('Scan evidence')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Saved chats' }))
  await user.click(
    await screen.findByRole('button', { name: /My earlier question/ }),
  )
  expect(await screen.findByText(saved.answer)).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'New chat' }))
  expect(screen.queryByText(saved.answer)).not.toBeInTheDocument()
  await user.type(screen.getByLabelText('Your question'), 'My new question')
  await user.click(screen.getByRole('button', { name: 'Ask' }))
  expect(await screen.findByText('The new answer is saved.')).toBeVisible()
  expect(messages[1].conversation_id).not.toBe(conversationId)
  await user.click(screen.getByRole('button', { name: 'Close' }))
  await user.click(screen.getByTestId('top-bar-assistant'))
  expect(await screen.findByText('The new answer is saved.')).toBeVisible()
  view.unmount()
  renderWithProviders(<GlobalAssistant />, { route: `/scans/${scopeId}` })
  await user.click(screen.getByTestId('top-bar-assistant'))
  await user.click(screen.getByRole('button', { name: 'Saved chats' }))
  expect(
    await screen.findByRole('button', { name: /My earlier question/ }),
  ).toBeVisible()
  await user.click(
    await screen.findByRole('button', { name: /My new question/ }),
  )
  expect(await screen.findByText('The new answer is saved.')).toBeVisible()
})

it('keeps an answer running when the modal closes and shows the submitted question immediately', async () => {
  const user = userEvent.setup()
  let finish!: () => void
  const completed = new Promise<void>((resolve) => {
    finish = resolve
  })
  let calls = 0
  server.use(
    http.post(`${api}/ai/chat`, async ({ request }) => {
      calls++
      const body = (await request.json()) as {
        question: string
        conversation_id: string
      }
      await completed
      return HttpResponse.json({
        ...saved,
        ...body,
        answer: 'The answer finished while closed.',
      })
    }),
  )
  renderWithProviders(<GlobalAssistant />, { route: `/scans/${scopeId}` })
  await user.click(screen.getByTestId('top-bar-assistant'))
  await user.type(screen.getByLabelText('Your question'), 'Keep this question')
  await user.click(screen.getByRole('button', { name: 'Ask' }))
  expect(
    within(screen.getByTestId('chat-transcript')).getByText(
      'Keep this question',
    ),
  ).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Close' }))
  finish()
  await user.click(screen.getByTestId('top-bar-assistant'))
  expect(
    await screen.findByText('The answer finished while closed.'),
  ).toBeVisible()
  expect(calls).toBe(1)
})

it('does not insert a failed old question into a new chat draft', async () => {
  const user = userEvent.setup()
  let fail!: () => void
  const failed = new Promise<void>((resolve) => {
    fail = resolve
  })
  server.use(
    http.post(`${api}/ai/chat`, async () => {
      await failed
      return new HttpResponse(null, { status: 502 })
    }),
  )
  renderWithProviders(<GlobalAssistant />, { route: `/scans/${scopeId}` })
  await user.click(screen.getByTestId('top-bar-assistant'))
  await user.type(screen.getByLabelText('Your question'), 'My old question')
  await user.click(screen.getByRole('button', { name: 'Ask' }))
  await user.click(screen.getByRole('button', { name: 'New chat' }))
  fail()
  expect(await screen.findByTestId('toast')).toBeVisible()
  expect(screen.getByLabelText('Your question')).toHaveValue('')
})
