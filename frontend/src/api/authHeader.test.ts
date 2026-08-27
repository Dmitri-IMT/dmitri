import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse, type JsonBodyType } from 'msw'
import { server } from '@/test/setup'

// `apiClient` is one shared Axios instance and `./client` attaches the auth interceptors
// to it as a side effect. So a module that bypasses `./client` still *appears* to send
// the token as long as anything else in the same module graph imported it. Each test
// therefore resets the registry and imports exactly one resource module, which is the
// only way to prove that module reaches the interceptors on its own.
const baseURL = 'http://localhost:8000/api/v1'

function captureAuthorization(path: string, body: JsonBodyType) {
  const seen: (string | null)[] = []
  server.use(
    http.get(`${baseURL}${path}`, ({ request }) => {
      seen.push(request.headers.get('Authorization'))
      return HttpResponse.json(body)
    }),
  )
  return seen
}

function captureAuthorizationPost(path: string) {
  const seen: (string | null)[] = []
  server.use(
    http.post(`${baseURL}${path}`, ({ request }) => {
      seen.push(request.headers.get('Authorization'))
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return seen
}

const userProfile = {
  user_id: '11111111-1111-4111-8111-111111111111',
  email: 'admin@example.com',
  role: 'admin',
}
const emptyPage = { data: [], total: 0, page: 1 }

afterEach(() => {
  vi.resetModules()
})

describe('every resource module reaches the auth interceptor on its own', () => {
  it('users.ts sends the bearer token', async () => {
    vi.resetModules()
    const seen = captureAuthorization('/users/me', userProfile)
    const { setAccessToken } = await import('./tokenStore')
    const { getCurrentUser } = await import('./users')

    setAccessToken('token-abc')
    await getCurrentUser()

    expect(seen).toEqual(['Bearer token-abc'])
  })

  it('scans.ts sends the bearer token', async () => {
    vi.resetModules()
    const seen = captureAuthorization('/scans', emptyPage)
    const { setAccessToken } = await import('./tokenStore')
    const { getLatestScan } = await import('./scans')

    setAccessToken('token-def')
    await getLatestScan()

    expect(seen).toEqual(['Bearer token-def'])
  })

  it('findings.ts sends the bearer token', async () => {
    vi.resetModules()
    const seen = captureAuthorization('/findings', emptyPage)
    const { setAccessToken } = await import('./tokenStore')
    const { listFindings } = await import('./findings')

    setAccessToken('token-ghi')
    await listFindings({
      scan_id: '22222222-2222-4222-8222-222222222222',
      severity: 'critical',
      per_page: 100,
    })

    expect(seen).toEqual(['Bearer token-ghi'])
  })

  it('passwords.ts sends the bearer token', async () => {
    vi.resetModules()
    const seen = captureAuthorizationPost('/auth/change-password')
    const { setAccessToken } = await import('./tokenStore')
    const { changePassword } = await import('./passwords')

    setAccessToken('token-jkl')
    await changePassword({
      current_password: 'old-long-enough-password', // pragma: allowlist secret
      new_password: 'new-long-enough-password', // pragma: allowlist secret
    })

    expect(seen).toEqual(['Bearer token-jkl'])
  })

  it('sends no Authorization header while signed out', async () => {
    vi.resetModules()
    const seen = captureAuthorization('/users/me', userProfile)
    const { getCurrentUser } = await import('./users')

    await getCurrentUser()

    expect(seen).toEqual([null])
  })
})
