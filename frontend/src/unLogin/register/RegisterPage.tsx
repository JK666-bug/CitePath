//注册页面
import { useState } from 'react'
import type { FormEvent } from 'react'
import AuthLayout from '../../shared/auth/AuthLayout'
import AuthField from '../../shared/auth/AuthField'
import { register } from './api'

type RegisterErrors = {
  username?: string
  password?: string
  confirmPassword?: string
}

export default function RegisterPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [errors, setErrors] = useState<RegisterErrors>({})
  const [serverError, setServerError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function clearError(field: keyof RegisterErrors) {
    setErrors((current) => ({
      ...current,
      [field]: undefined,
    }))

    setServerError('')
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (submitting) return

    const name = username.trim()
    const nextErrors: RegisterErrors = {}

    const usernameLength = Array.from(name).length
    const passwordLength = Array.from(password).length

    if (!name) {
      nextErrors.username = 'Please enter a username.'
    } else if (usernameLength < 2 || usernameLength > 32) {
      nextErrors.username =
        'Your username must contain 2–32 characters.'
    } else if (/\s/.test(name)) {
      nextErrors.username =
        'Your username cannot contain spaces.'
    }

    if (!password) {
      nextErrors.password = 'Please enter a password.'
    } else if (passwordLength < 6 || passwordLength > 72) {
      nextErrors.password =
        'Your password must contain 6–72 characters.'
    }

    if (!confirmPassword) {
      nextErrors.confirmPassword =
        'Please confirm your password.'
    } else if (confirmPassword !== password) {
      nextErrors.confirmPassword =
        'Your passwords do not match.'
    }

    setErrors(nextErrors)
    setServerError('')

    if (Object.keys(nextErrors).length > 0) {
      const firstInvalid = nextErrors.username
        ? 'register-username'
        : nextErrors.password
          ? 'register-password'
          : 'register-confirm-password'

      document.getElementById(firstInvalid)?.focus()
      return
    }

    setSubmitting(true)

    try {
      await register({
        username: name,
        password,
      })

      window.location.replace('/courses')
    } catch (error) {
      setServerError(
        error instanceof Error
          ? error.message
          : 'Unable to create your account. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout mode="register">
      <h2 className="auth-form-title">
        Create an account
      </h2>

      <form onSubmit={handleSubmit} noValidate>
        <AuthField
          id="register-username"
          label="Username"
          value={username}
          onChange={(value) => {
            setUsername(value)
            clearError('username')
          }}
          autoComplete="username"
          error={errors.username}
          disabled={submitting}
        />

        <AuthField
          id="register-password"
          label="Password"
          type="password"
          value={password}
          onChange={(value) => {
            setPassword(value)
            clearError('password')
            clearError('confirmPassword')
          }}
          autoComplete="new-password"
          error={errors.password}
          disabled={submitting}
        />

        <AuthField
          id="register-confirm-password"
          label="Confirm password"
          type="password"
          value={confirmPassword}
          onChange={(value) => {
            setConfirmPassword(value)
            clearError('confirmPassword')
          }}
          autoComplete="new-password"
          error={errors.confirmPassword}
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
          {submitting
            ? 'Creating account…'
            : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  )
}