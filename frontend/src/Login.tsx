import { FormEvent, useState } from 'react'
import './App.css'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (!username.trim() || !password) {
      setError('Enter your username and password')
      return
    }
    setSubmitting(true)
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        setError(typeof payload.detail === 'string' ? payload.detail : 'Sign-in failed')
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
        <h1>Sign in and continue this course</h1>
        <p className="lead">Choose a course you already uploaded, or start a new one and add lecture PDFs. Questions use only your own materials.</p>
      </section>
      <section className="auth-panel">
        <form className="card auth-card" onSubmit={onSubmit}>
          <header>
            <p className="eyebrow">Welcome back</p>
            <h1>Sign in</h1>
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
          <button type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
          {error ? <p className="error">{error}</p> : null}
          <p className="switch">
            No account yet? <a href="/register">Create one</a>
          </p>
        </form>
      </section>
    </main>
  )
}
