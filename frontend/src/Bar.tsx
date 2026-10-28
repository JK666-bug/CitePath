export function Bar({ username }: { username: string }) {
  async function logout() {
    await fetch('/api/logout', { method: 'POST' })
    window.location.assign('/')
  }

  return (
    <header className="bar">
      <a className="mark" href="/courses">
        CitePath
      </a>
      <nav>
        <a href="/courses">My courses</a>
      </nav>
      <span className="who">{username}</span>
      <button type="button" className="secondary" onClick={logout}>
        Sign out
      </button>
    </header>
  )
}
