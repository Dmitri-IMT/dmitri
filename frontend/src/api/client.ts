import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { apiClient, authClient } from './instances'
import { clearAccessToken, getAccessToken } from './tokenStore'
import { refresh } from './auth'
import { emitSessionExpired } from './authEvents'

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

function performRefresh(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = refresh()
      .then((response) => response.access_token)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.response?.config as RetryableRequestConfig | undefined
    if (error.response?.status !== 401 || !config || config._retry) {
      return Promise.reject(error)
    }
    config._retry = true
    try {
      const token = await performRefresh()
      config.headers.set('Authorization', `Bearer ${token}`)
      return apiClient(config)
    } catch (refreshError) {
      clearAccessToken()
      emitSessionExpired()
      return Promise.reject(refreshError)
    }
  },
)

export { apiClient, authClient }
