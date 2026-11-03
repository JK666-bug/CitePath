//注册请求
import { request } from '../../shared/request'
import type { User } from '../../shared/session'

export type RegisterInput = {
  username: string
  password: string
}

export function register(input: RegisterInput): Promise<User> {
  return request<User>('/api/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })
}