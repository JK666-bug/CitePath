import { useState } from 'react'

import {
  BookOpen,
  CalendarDays,
  FlaskConical,
  FolderOpen,
  LogOut,
  PencilLine,
  Plus,
} from 'lucide-react'

import { useStudy } from '../shared/StudyProvider'
import {
  Link,
  useLocation,
} from '../shared/router'

import { logout } from '../shared/session'
import { messageOf } from '../shared/request'

export default function Sidebar({
  username,
  onSignOut,
}: {
  username: string
  onSignOut: () => void
}) {
  const {
    courses,
    coursesLoading,
    coursesError,
    refreshCourses,
  } = useStudy()

  const { path } = useLocation()

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function signOut() {
    if (busy) return

    setBusy(true)
    setError('')

    try {
      await logout()
      onSignOut()
    } catch (reason) {
      setError(messageOf(reason))
      setBusy(false)
    }
  }

  const navigation = [
    {
      href: '/calendar',
      title: 'Study calendar',
      icon: CalendarDays,
      active: path === '/calendar',
    },
    {
      href: '/courses',
      title: 'My courses',
      icon: FolderOpen,
      active:
        path.startsWith('/courses'),
    },
    {
      href: '/practice',
      title: 'Chapter practice',
      icon: PencilLine,
      active:
        path.startsWith('/practice'),
    },
  ]

  const colors = [
    '#b68b6a',
    '#a394b5',
    '#b2a284',
    '#c0918c',
  ]

  return (
    <aside className="sidebar">
      <Link
        href="/courses"
        className="brand"
      >
        <span className="brand-mark">
          <BookOpen
            size={22}
            strokeWidth={1.5}
          />
        </span>

        <span>
          CitePath
          <small>
            Learning, with a path.
          </small>
        </span>
      </Link>

      <Link
        className="button new-course"
        href="/courses/new"
      >
        <Plus size={16} />
        New course
      </Link>

      <nav
        className="main-nav"
        aria-label="Main navigation"
      >
        {navigation.map((item) => (
          <Link
            className="nav-link"
            key={item.href}
            href={item.href}
            aria-current={
              item.active
                ? 'page'
                : undefined
            }
          >
            <item.icon
              size={18}
              strokeWidth={1.5}
            />

            {item.title}
          </Link>
        ))}
      </nav>

      <div className="sidebar-course-list">
        <p className="eyebrow">
          Your courses
          <span>{courses.length}</span>
        </p>

        {coursesLoading && (
          <p className="muted small">
            Loading courses…
          </p>
        )}

        {coursesError && (
          <div className="sidebar-error">
            <p role="alert">
              {coursesError}
            </p>

            <button
              className="text-button"
              onClick={() =>
                void refreshCourses()
              }
            >
              Retry
            </button>
          </div>
        )}

        {!coursesLoading &&
          !coursesError &&
          courses.length === 0 && (
            <p className="muted small">
              Your next learning path starts
              here.
            </p>
          )}

        <nav aria-label="Course navigation">
          {courses.map((course, index) => (
            <Link
              className="nav-link course-nav-link"
              key={course.id}
              href={
                `/courses/${course.id}/plan`
              }
              aria-current={
                path.startsWith(
                  `/courses/${course.id}/`,
                )
                  ? 'page'
                  : undefined
              }
            >
              <i
                style={{
                  background:
                    colors[
                      index % colors.length
                    ],
                }}
              />

              <span>{course.name}</span>
            </Link>
          ))}
        </nav>
      </div>

      <Link
        className="nav-link demo-nav"
        href="/courses/demo/plan"
        aria-current={
          path.includes('/demo')
            ? 'page'
            : undefined
        }
      >
        <FlaskConical size={17} />
        Interface demo
      </Link>

      <footer className="sidebar-account">
        <div className="account-name">
          <span className="avatar">
            {Array.from(username)[0]
              ?.toUpperCase() || 'U'}
          </span>

          <span>
            {username}
            <small>Your study space</small>
          </span>
        </div>

        <button
          className="icon-button"
          aria-label={
            busy
              ? 'Signing out'
              : 'Sign out'
          }
          disabled={busy}
          onClick={signOut}
        >
          <LogOut size={17} />
        </button>

        {error && (
          <p
            className="sidebar-error"
            role="alert"
          >
            {error}
          </p>
        )}
      </footer>
    </aside>
  )
}