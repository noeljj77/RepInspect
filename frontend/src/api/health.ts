import { ApiError, apiFetch } from './client'

export interface HealthStatus {
  status: 'ok' | 'degraded'
  version: string
  database: 'ok' | 'unavailable'
}

export async function getHealth(): Promise<HealthStatus> {
  try {
    return await apiFetch<HealthStatus>('/api/health')
  } catch (error) {
    // A 503 still carries a useful body describing which part is down.
    if (error instanceof ApiError && error.status === 503) {
      return error.body as HealthStatus
    }
    throw error
  }
}
