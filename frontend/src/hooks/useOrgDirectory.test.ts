import { act, createElement, type ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { delay, http, HttpResponse } from 'msw'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { server } from '@/test/setup'
import {
  adminProfile,
  otherMember,
  pendingInvite,
  selfMember,
} from '@/test/mswHandlers'
import { SessionContext } from '@/auth/SessionContext'
import { useOrgDirectory } from './useOrgDirectory'

const baseURL = 'http://localhost:8000/api/v1'

const session = {
  status: 'authenticated' as const,
  user: adminProfile,
  signIn: async () => {},
  signOut: async () => {},
  acceptInvitation: async () => {},
  deleteAccount: async () => {},
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(SessionContext.Provider, { value: session }, children),
    )
  }
}

function renderOrgDirectory() {
  return renderHook(() => useOrgDirectory(), { wrapper: createWrapper() })
}

describe('useOrgDirectory', () => {
  it('reports loading while the reads are in flight, exposing nothing but the state', async () => {
    server.use(
      http.get(`${baseURL}/users`, async () => {
        await delay('infinite')
        return HttpResponse.json({ data: [] })
      }),
    )

    const { result } = renderOrgDirectory()

    expect(result.current.state).toBe('loading')
    expect(Object.keys(result.current)).toEqual(['state'])
  })

  it('reports error with no rows when the member list fails', async () => {
    server.use(
      http.get(
        `${baseURL}/users`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )

    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current).not.toHaveProperty('rows')
    expect(result.current).not.toHaveProperty('isPending')
    expect(result.current).not.toHaveProperty('isError')
  })

  it('reports error with no rows when the invite list fails', async () => {
    server.use(
      http.get(
        `${baseURL}/invites`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    )

    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current).not.toHaveProperty('rows')
  })

  it('lets error win over loading while the other read is still pending', async () => {
    server.use(
      http.get(
        `${baseURL}/users`,
        () => new HttpResponse(null, { status: 500 }),
      ),
      http.get(`${baseURL}/invites`, async () => {
        await delay('infinite')
        return HttpResponse.json({ data: [] })
      }),
    )

    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('error'))
  })

  it('reports blank when the caller is the only person', async () => {
    server.use(
      http.get(`${baseURL}/users`, () =>
        HttpResponse.json({ data: [selfMember] }),
      ),
      http.get(`${baseURL}/invites`, () => HttpResponse.json({ data: [] })),
    )

    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('blank'))
  })

  it('reports ready with members before invites once anyone else exists', async () => {
    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('ready'))
    if (result.current.state !== 'ready') throw new Error('unreachable')
    expect(result.current.rows.map((row) => row.id)).toEqual([
      selfMember.user_id,
      otherMember.user_id,
      pendingInvite.invite_id,
    ])
    expect(result.current.rows[0]).toMatchObject({
      kind: 'member',
      isSelf: true,
    })
    expect(result.current.rows[2]).toMatchObject({ kind: 'invite' })
  })

  it('reports ready when a pending invite is the only other person', async () => {
    server.use(
      http.get(`${baseURL}/users`, () =>
        HttpResponse.json({ data: [selfMember] }),
      ),
    )

    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('ready'))
  })

  it('refetches both reads on retry', async () => {
    let memberCalls = 0
    let inviteCalls = 0
    server.use(
      http.get(`${baseURL}/users`, () => {
        memberCalls += 1
        if (memberCalls === 1) return new HttpResponse(null, { status: 500 })
        return HttpResponse.json({ data: [selfMember, otherMember] })
      }),
      http.get(`${baseURL}/invites`, () => {
        inviteCalls += 1
        return HttpResponse.json({ data: [pendingInvite] })
      }),
    )

    const { result } = renderOrgDirectory()

    await waitFor(() => expect(result.current.state).toBe('error'))
    if (result.current.state !== 'error') throw new Error('unreachable')
    const { retry } = result.current

    await act(async () => {
      retry()
    })

    await waitFor(() => expect(result.current.state).toBe('ready'))
    expect(memberCalls).toBe(2)
    expect(inviteCalls).toBe(2)
  })
})
