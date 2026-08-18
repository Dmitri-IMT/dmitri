import axios from 'axios'

const apiUrl = import.meta.env.VITE_API_URL

if (!apiUrl) {
  throw new Error('VITE_API_URL is required')
}

const baseURL = `${apiUrl}/api/v1`

export const apiClient = axios.create({ baseURL })

export const authClient = axios.create({ baseURL, withCredentials: true })
