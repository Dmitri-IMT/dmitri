import { createContext, useEffect, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { login, logout, refresh } from '@/api/auth'
import { getCurrentUser } from '@/api/users'
import { clearAccessToken, getAccessToken } from '@/api/tokenStore'
import { onSessionExpired } from '@/api/authEvents'
import type { components } from '@/types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type LoginRequest = components['schemas']['LoginRequest']

type SessionStatus = 'booting' | 'authenticated' | 'anonymous'

interface SessionContextValue {
  status: SessionStatus
  user: UserProfileResponse | null
  signIn: (credentials: LoginRequest) => Promise<void>
  signOut: () => Promise<void>
}

export const SessionContext = createContext<SessionContextValue | null>(null)

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

  async function signIn(credentials: LoginRequest): Promise<void> {
    await login(credentials)
    setEnabled(true)
    await queryClient.invalidateQueries({ queryKey: ['session'] })
    navigate('/', { replace: true })
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
  }

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  )
}
