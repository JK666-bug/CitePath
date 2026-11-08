//登录页面
import { useState } from 'react'
import type { FormEvent } from 'react'
import AuthLayout from '../../shared/auth/AuthLayout'
import AuthField from '../../shared/auth/AuthField'
import { login } from './api'

type LoginErrors = {
  username?: string
  password?: string
}

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<LoginErrors>({})
  const [serverError, setServerError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (submitting) return

    const name = username.trim()
    const nextErrors: LoginErrors = {}

    if (!name) {
      nextErrors.username = 'Please enter your username.'
    }

    if (!password) {
      nextErrors.password = 'Please enter your password.'
    }

    setErrors(nextErrors)
    setServerError('')

    if (Object.keys(nextErrors).length > 0) {
      const firstInvalid = nextErrors.username
        ? 'login-username'
        : 'login-password'

      document.getElementById(firstInvalid)?.focus()
      return
    }

    setSubmitting(true)

    try {
      await login({
        username: name,
        password,
      })

      window.location.replace('/courses')
    } catch (error) {
      setServerError(
        error instanceof Error
          ? error.message
          : 'Unable to sign in. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout mode="login">
      <h2 className="auth-form-title">Sign in</h2>

      <form onSubmit={handleSubmit} noValidate>
        <AuthField
          id="login-username"
          label="Username"
          value={username}
          onChange={(value) => {
            setUsername(value)

            setErrors((current) => ({
              ...current,
              username: undefined,
            }))

            setServerError('')
          }}
          autoComplete="username"
          error={errors.username}
          disabled={submitting}
        />

        <AuthField
          id="login-password"
          label="Password"
          type="password"
          value={password}
          onChange={(value) => {
            setPassword(value)

            setErrors((current) => ({
              ...current,
              password: undefined,
            }))

            setServerError('')
          }}
          autoComplete="current-password"
          error={errors.password}
          disabled={submitting}
        />

        {serverError ? (
          <p
            className="auth-server-error"
            role="alert"
          >
            {serverError}
          </p>
        ) : null}

        <button
          className="auth-submit"
          type="submit"
          disabled={submitting}
          aria-busy={submitting}
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  )
}