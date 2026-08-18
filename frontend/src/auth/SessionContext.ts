import { createContext } from 'react'
import type { components } from '@/types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type LoginRequest = components['schemas']['LoginRequest']
type AcceptInviteRequest = components['schemas']['AcceptInviteRequest']

export type SessionStatus = 'booting' | 'authenticated' | 'anonymous'

export interface SessionContextValue {
  status: SessionStatus
  user: UserProfileResponse | null
  signIn: (credentials: LoginRequest) => Promise<void>
  signOut: () => Promise<void>
  acceptInvitation: (request: AcceptInviteRequest) => Promise<void>
  deleteAccount: () => Promise<void>
}

// Separate from SessionProvider so that file exports components only: a module that
// exports both a component and a context loses Vite Fast Refresh and reloads the page
// on every edit (react-refresh/only-export-components).
export const SessionContext = createContext<SessionContextValue | null>(null)
