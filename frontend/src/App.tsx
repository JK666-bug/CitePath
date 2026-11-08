import {
  useEffect,
  useState,
} from 'react'

import LoginPage from './unLogin/login/LoginPage'
import RegisterPage from './unLogin/register/RegisterPage'

import { getCurrentUser } from './shared/session'
import type { User } from './shared/session'

import { messageOf } from './shared/request'

import {
  Link,
  navigate,
  useLocation,
} from './shared/router'

import { StudyProvider } from './shared/StudyProvider'

import {
  Empty,
  Loading,
} from './shared/components/UI'

import AppLayout from './layout/AppLayout'

import CoursesPage from './pages/courses/CoursesPage'
import CourseEditorPage from './pages/courseEditor/CourseEditorPage'
import CalendarPage from './pages/calendar/CalendarPage'
import CoursePage from './pages/course/CoursePage'

import PracticePage from './pages/practice/PracticePage'
import PracticeSessionPage from './pages/practice/PracticeSessionPage'
import ChapterReportPage from './pages/practice/ChapterReportPage'

function Redirect({
  to,
}: {
  to: string
}) {
  useEffect(() => {
    navigate(to, true)
  }, [to])

  return (
    <Loading text="Opening your page…" />
  )
}

function ProtectedPages() {
  const { path } = useLocation()

  if (
    [
      '/',
      '/login',
      '/register',
    ].includes(path)
  ) {
    return <Redirect to="/courses" />
  }

  if (path === '/courses') {
    return <CoursesPage />
  }

  if (path === '/courses/new') {
    return (
      <CourseEditorPage key="new" />
    )
  }

  if (path === '/calendar') {
    return <CalendarPage />
  }

  if (path === '/practice') {
    return <PracticePage />
  }

  const edit = path.match(
    /^\/courses\/(demo|[1-9]\d*)\/edit$/,
  )

  if (edit) {
    return (
      <CourseEditorPage
        key={edit[1]}
        courseId={edit[1]}
      />
    )
  }

  const course = path.match(
    /^\/courses\/(demo|[1-9]\d*)(?:\/(plan|info|qa|ask))?$/,
  )

  if (course) {
    if (
      !course[2] ||
      course[2] === 'ask'
    ) {
      return (
        <Redirect
          to={
            `/courses/${course[1]}/${
              course[2] === 'ask'
                ? 'qa'
                : 'plan'
            }`
          }
        />
      )
    }

    return (
      <CoursePage
        key={course[1]}
        courseId={course[1]}
        tab={course[2]}
      />
    )
  }

  const practice = path.match(
    /^\/practice\/(demo|[1-9]\d*)\/([a-zA-Z0-9_-]+)(\/report)?$/,
  )

  if (practice) {
    return practice[3] ? (
      <ChapterReportPage
        courseId={practice[1]}
        chapterId={practice[2]}
      />
    ) : (
      <PracticeSessionPage
        key={
          `${practice[1]}-${practice[2]}`
        }
        courseId={practice[1]}
        chapterId={practice[2]}
      />
    )
  }

  return (
    <Empty title="Page not found">
      <Link href="/courses">
        Back to my courses
      </Link>
    </Empty>
  )
}

export default function App() {
  const [user, setUser] = useState<
    User | null | undefined
  >(undefined)

  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  const { path } = useLocation()

  useEffect(() => {
    let active = true

    setError('')
    setUser(undefined)

    getCurrentUser()
      .then((value) => {
        if (active) {
          setUser(value)
        }
      })
      .catch((reason) => {
        if (active) {
          setError(messageOf(reason))
        }
      })

    return () => {
      active = false
    }
  }, [attempt])

  useEffect(() => {
    function expired() {
      setUser(null)
      navigate('/login', true)
    }

    window.addEventListener(
      'citepath:session-expired',
      expired,
    )

    return () => {
      window.removeEventListener(
        'citepath:session-expired',
        expired,
      )
    }
  }, [])

  if (error) {
    return (
      <div className="auth-page">
        <section className="auth-status">
          <h1>
            Unable to open CitePath
          </h1>

          <p role="alert">{error}</p>

          <button
            className="auth-submit"
            onClick={() =>
              setAttempt(
                (value) => value + 1,
              )
            }
          >
            Try again
          </button>
        </section>
      </div>
    )
  }

  if (user === undefined) {
    return (
      <div className="auth-page">
        <Loading />
      </div>
    )
  }

  if (!user) {
    if (path === '/register') {
      return <RegisterPage />
    }

    if (path === '/login') {
      return <LoginPage />
    }

    return <Redirect to="/login" />
  }

  return (
    <StudyProvider
      key={user.id}
      userId={user.id}
    >
      <AppLayout
        username={user.username}
        onSignOut={() => {
          setUser(null)
          navigate('/login', true)
        }}
      >
        <ProtectedPages />
      </AppLayout>
    </StudyProvider>
  )
}