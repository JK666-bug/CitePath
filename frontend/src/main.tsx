import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './App.css'
import Ask from './Ask.tsx'
import CourseNew from './CourseNew.tsx'
import CoursePage from './CoursePage.tsx'
import Courses from './Courses.tsx'
import Login from './Login.tsx'
import Register from './Register.tsx'

type User = { id: number; username: string }

function pathOf() {
  return window.location.pathname.replace(/\/+$/, '') || '/'
}

function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const path = pathOf()

  useEffect(() => {
    fetch('/api/me')
      .then(async (response) => {
        if (!response.ok) {
          setUser(null)
          return
        }
        setUser(await response.json())
      })
      .catch(() => setUser(null))
  }, [])

  if (user === undefined) {
    return (
      <main className="page">
        <p className="lead">Opening…</p>
      </main>
    )
  }

  if (!user) {
    return path === '/register' ? <Register /> : <Login />
  }

  if (path === '/' || path === '/register') {
    window.location.replace('/courses')
    return (
      <main className="page">
        <p className="lead">Opening…</p>
      </main>
    )
  }

  if (path === '/courses') return <Courses username={user.username} />
  if (path === '/courses/new') return <CourseNew username={user.username} />

  const ask = path.match(/^\/courses\/(\d+)\/ask$/)
  if (ask) return <Ask courseId={Number(ask[1])} username={user.username} />

  const course = path.match(/^\/courses\/(\d+)$/)
  if (course) return <CoursePage courseId={Number(course[1])} username={user.username} />

  return <Courses username={user.username} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
