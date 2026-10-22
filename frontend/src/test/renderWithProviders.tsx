import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SessionProvider } from '@/auth/SessionProvider'
import ToastProvider from '@/components/Toast'

function initialEntry(
  route: string,
  state: unknown,
): string | { pathname: string; search: string; state: unknown } {
  if (state === undefined) return route
  const q = route.indexOf('?')
  if (q === -1) return { pathname: route, search: '', state }
  return {
    pathname: route.slice(0, q),
    search: route.slice(q),
    state,
  }
}

export function renderWithProviders(
  ui: ReactElement,
  {
    route = '/',
    state,
    toastDuration,
  }: { route?: string; state?: unknown; toastDuration?: number } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter initialEntries={[initialEntry(route, state)]}>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <ToastProvider duration={toastDuration}>{ui}</ToastProvider>
        </SessionProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}
