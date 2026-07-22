import axios from 'axios'

const baseURL = `${import.meta.env.VITE_API_URL}/api/v1`

export const apiClient = axios.create({ baseURL })

export const authClient = axios.create({ baseURL, withCredentials: true })
