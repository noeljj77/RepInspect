import { ApiError, apiFetch, apiPost } from './client'

export interface User {
  id: string
  email: string
  display_name: string
  created_at: string
}

export interface LoginInput {
  email: string
  password: string
}

export interface RegisterInput extends LoginInput {
  display_name: string
}

/** The logged-in user, or null when there is no valid session. */
export async function getCurrentUser(): Promise<User | null> {
  try {
    return await apiFetch<User>('/api/auth/me')
  } catch (error) {
    // 401 just means "not logged in"; it is an answer, not a failure.
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export const login = (input: LoginInput) => apiPost<User>('/api/auth/login', input)
export const register = (input: RegisterInput) => apiPost<User>('/api/auth/register', input)
export const logout = () => apiPost<void>('/api/auth/logout')
