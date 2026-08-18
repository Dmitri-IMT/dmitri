import { useEffect, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { acceptInvite, login, logout, refresh } from '@/api/auth'
import { deleteCurrentUser, getCurrentUser } from '@/api/users'
import { clearAccessToken, getAccessToken } from '@/api/tokenStore'
import { onSessionExpired } from '@/api/authEvents'
import {
  SessionContext,
  type SessionContextValue,
  type SessionStatus,
} from '@/auth/SessionContext'
import type { components } from '@/types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type LoginRequest = components['schemas']['LoginRequest']
type AcceptInviteRequest = components['schemas']['AcceptInviteRequest']

async function bootSession(): Promise<UserProfileResponse> {
  if (!getAccessToken()) {
    await refresh()
  }
  return getCurrentUser()
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [enabled, setEnabled] = useState(true)

  const query = useQuery({
    queryKey: ['session'],
    queryFn: bootSession,
    retry: false,
    enabled,
  })

  function clearSession() {
    clearAccessToken()
    setEnabled(false)
  }

  // Deliberately dependency-free. The session query stays mounted while anonymous, and
  // a mounted useQuery re-registers its cache entry on every render — including the
  // render that navigates to /login. Removing once (inside clearSession, or from an
  // effect keyed on `enabled`) is therefore undone by the next render, which leaves a
  // stale session entry in the cache. This re-asserts the removal after each render.
  useEffect(() => {
    if (!enabled) {
      queryClient.removeQueries({ queryKey: ['session'] })
    }
  })

  useEffect(
    () =>
      onSessionExpired(() => {
        clearSession()
        navigate('/login', { replace: true })
      }),
    [queryClient, navigate],
  )

  async function enterSession(): Promise<void> {
    setEnabled(true)
    await queryClient.invalidateQueries({ queryKey: ['session'] })
    navigate('/', { replace: true })
  }

  async function signIn(credentials: LoginRequest): Promise<void> {
    await login(credentials)
    await enterSession()
  }

  async function acceptInvitation(request: AcceptInviteRequest): Promise<void> {
    await acceptInvite(request)
    await enterSession()
  }

  async function signOut(): Promise<void> {
    try {
      await logout()
    } catch {
      clearAccessToken()
    } finally {
      clearSession()
      navigate('/login', { replace: true })
    }
  }

  async function deleteAccount(): Promise<void> {
    await deleteCurrentUser()
    clearSession()
    navigate('/login', { replace: true, state: { accountDeleted: true } })
  }

  const status: SessionStatus = !enabled
    ? 'anonymous'
    : query.isPending
      ? 'booting'
      : query.isSuccess
        ? 'authenticated'
        : 'anonymous'

  const value: SessionContextValue = {
    status,
    user: query.data ?? null,
    signIn,
    signOut,
    acceptInvitation,
    deleteAccount,
  }

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  )
}
