//用户和登录状态
import { ApiError, request } from './request'

export type User = {
  id: number
  username: string
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await request<User>('/api/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }

    throw error
  }
}

export async function logout(): Promise<void> {
  await request<{ ok: boolean }>('/api/logout', {
    method: 'POST',
  })
}