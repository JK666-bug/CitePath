import { FormEvent, useState } from 'react'
import './App.css'

export default function Register() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (username.trim().length < 2) {
      setError('Username must be 2 to 32 characters')
      return
    }
    if (password.length < 6) {
      setError('Password must be 6 to 72 characters')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setSubmitting(true)
    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        setError(typeof payload.detail === 'string' ? payload.detail : 'Registration failed')
        return
      }
      window.location.assign('/courses')
    } catch {
      setError('Cannot reach the server')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth">
      <section className="auth-brand">
        <p className="mark">CitePath</p>
        <h1>Start with one course</h1>
        <p className="lead">Create an account, upload PDFs, then ask questions about that course.</p>
      </section>
      <section className="auth-panel">
        <form className="card auth-card" onSubmit={onSubmit}>
          <header>
            <p className="eyebrow">New account</p>
            <h1>Create account</h1>
          </header>
          <label>
            Username
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <label>
            Confirm password
            <input
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
          {error ? <p className="error">{error}</p> : null}
          <p className="switch">
            Already have an account? <a href="/">Sign in</a>
          </p>
        </form>
      </section>
    </main>
  )
}
