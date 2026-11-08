//登录请求
import { request } from '../../shared/request'
import type { User } from '../../shared/session'

export type LoginInput = {
  username: string
  password: string
}

export function login(input: LoginInput): Promise<User> {
  return request<User>('/api/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })
}