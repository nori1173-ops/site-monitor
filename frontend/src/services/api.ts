import axios from 'axios'
import { fetchAuthSession } from 'aws-amplify/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_ENDPOINT,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(async (config) => {
  try {
    const session = await fetchAuthSession()
    const token = session.tokens?.idToken?.toString()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    // no-op: unauthenticated request
  }
  if (sessionStorage.getItem('adminAuth') === 'true') {
    config.headers['X-Admin-Auth'] = btoa('admin:SecurePassword123')
  }
  return config
})

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

export default api
