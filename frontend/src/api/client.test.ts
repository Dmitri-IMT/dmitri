import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { apiClient, authClient } from './client'
import { getAccessToken, setAccessToken } from './tokenStore'
import { onSessionExpired } from './authEvents'
import { validLoginResponse } from '@/test/mswHandlers'

const baseURL = 'http://localhost:8000/api/v1'

describe('apiClient interceptor', () => {
  beforeEach(() => {
    setAccessToken('expired-token')
  })

  it('performs exactly one refresh on a 401 and retries the original request', async () => {
    let hostsCallCount = 0
    let refreshCallCount = 0
    server.use(
      http.get(`${baseURL}/hosts`, () => {
        hostsCallCount += 1
        if (hostsCallCount === 1) {
          return new HttpResponse(null, { status: 401 })
        }
        return HttpResponse.json([])
      }),
      http.post(`${baseURL}/auth/refresh`, () => {
        refreshCallCount += 1
        return HttpResponse.json(validLoginResponse)
      }),
    )

    const response = await apiClient.get('/hosts')

    expect(response.status).toBe(200)
    expect(refreshCallCount).toBe(1)
    expect(hostsCallCount).toBe(2)
    expect(getAccessToken()).toBe(validLoginResponse.access_token)
  })

  it('clears the token store and emits a session-expired event when refresh also fails, without a second refresh', async () => {
    let refreshCallCount = 0
    server.use(
      http.get(
        `${baseURL}/hosts`,
        () => new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${baseURL}/auth/refresh`, () => {
        refreshCallCount += 1
        return new HttpResponse(null, { status: 401 })
      }),
    )

    const onExpired = vi.fn()
    const unsubscribe = onSessionExpired(onExpired)

    await expect(apiClient.get('/hosts')).rejects.toBeTruthy()

    expect(getAccessToken()).toBeNull()
    expect(onExpired).toHaveBeenCalledTimes(1)
    expect(refreshCallCount).toBe(1)

    unsubscribe()
  })

  it('single-flights concurrent 401s into exactly one refresh, retrying every queued request', async () => {
    let hostsCallCount = 0
    let refreshCallCount = 0
    server.use(
      http.get(`${baseURL}/hosts`, () => {
        hostsCallCount += 1
        if (hostsCallCount <= 3) {
          return new HttpResponse(null, { status: 401 })
        }
        return HttpResponse.json([])
      }),
      http.post(`${baseURL}/auth/refresh`, () => {
        refreshCallCount += 1
        return HttpResponse.json(validLoginResponse)
      }),
    )

    const results = await Promise.all([
      apiClient.get('/hosts'),
      apiClient.get('/hosts'),
      apiClient.get('/hosts'),
    ])

    expect(results.every((response) => response.status === 200)).toBe(true)
    expect(refreshCallCount).toBe(1)
  })

  it('scopes credentials so the business client sends none and the auth client sends withCredentials', async () => {
    const businessConfigs: boolean[] = []
    const authConfigs: boolean[] = []
    apiClient.interceptors.request.use((config) => {
      businessConfigs.push(Boolean(config.withCredentials))
      return config
    })
    authClient.interceptors.request.use((config) => {
      authConfigs.push(Boolean(config.withCredentials))
      return config
    })

    await apiClient.get('/hosts')
    await authClient.post('/auth/login', { email: 'a@b.com', password: 'pw' })

    expect(businessConfigs).toEqual([false])
    expect(authConfigs).toEqual([true])
  })
})
