//登录注册公用外观
import type { ReactNode } from 'react'
import {
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  PencilLine,
  Route,
  Sprout,
  SquareCheck,
} from 'lucide-react'
import './auth.css'

type AuthLayoutProps = {
  mode: 'login' | 'register'
  children: ReactNode
}

export default function AuthLayout({
  mode,
  children,
}: AuthLayoutProps) {
  const isRegister = mode === 'register'

  return (
    <div className="auth-page">
      <div className="auth-window">
        <main className="auth-main">
          <section
            className="auth-story"
            aria-label="About CitePath"
          >
            <a className="auth-wordmark" href="/">
              <span className="auth-logo" aria-hidden="true">
                <BookOpen size={22} strokeWidth={1.6} />
              </span>

              <span>CitePath</span>
            </a>

            <h1>
              Make every step of learning
              <br />
              leave its own <span>path</span>.
            </h1>

            <div
              className="auth-sample"
              aria-label="Sample study plan"
            >
              <div className="auth-sample-header">
                <span className="auth-sample-heading">
                  <CalendarDays
                    size={16}
                    strokeWidth={1.6}
                    aria-hidden="true"
                  />

                  My study schedule
                </span>

                <small>Sample plan</small>
              </div>

              <div className="auth-week" aria-hidden="true">
                {[
                  ['Mon', '2'],
                  ['Tue', '3'],
                  ['Wed', '4'],
                  ['Thu', '5'],
                  ['Fri', '6'],
                  ['Sat', '7'],
                  ['Sun', '8'],
                ].map(([day, date], index) => (
                  <div
                    key={day}
                    className={
                      index === 2
                        ? 'auth-week-day is-today'
                        : 'auth-week-day'
                    }
                  >
                    <span>{day}</span>
                    <strong>{date}</strong>
                  </div>
                ))}
              </div>

              <div className="auth-example-task">
                <span
                  className="auth-task-symbol"
                  aria-hidden="true"
                >
                  <BookOpen size={17} strokeWidth={1.6} />
                </span>

                <div className="auth-task-content">
                  <small>Algorithm Design · Reading</small>

                  <strong>
                    Start with binary trees, from this chapter
                  </strong>

                  <span className="auth-source">
                    L6.pdf · pp. 2–4
                  </span>
                </div>

                <span className="auth-task-time">
                  35 min
                </span>
              </div>

              <div className="auth-example-task">
                <span
                  className="auth-task-symbol is-lilac"
                  aria-hidden="true"
                >
                  <PencilLine size={17} strokeWidth={1.6} />
                </span>

                <div className="auth-task-content">
                  <small>Chapter practice</small>

                  <strong>
                    Once you've read it, try answering
                  </strong>
                </div>

                <ArrowUpRight
                  className="auth-task-arrow"
                  size={16}
                  strokeWidth={1.6}
                  aria-hidden="true"
                />
              </div>
            </div>

            <div className="auth-benefits">
              <span>
                <Route
                  size={15}
                  strokeWidth={1.6}
                  aria-hidden="true"
                />
                Planned
              </span>

              <span>
                <SquareCheck
                  size={15}
                  strokeWidth={1.6}
                  aria-hidden="true"
                />
                Evidence
              </span>

              <span>
                <Sprout
                  size={15}
                  strokeWidth={1.6}
                  aria-hidden="true"
                />
                Progress
              </span>
            </div>
          </section>

          <section
            className="auth-form-panel"
            aria-label={
              isRegister ? 'Create an account' : 'Sign in'
            }
          >
            <div className="auth-form-container">
              {children}

              <div className="auth-switch">
                <span>
                  {isRegister
                    ? 'Already have an account?'
                    : 'New to CitePath?'}
                </span>

                <a
                  href={isRegister ? '/login' : '/register'}
                >
                  {isRegister
                    ? 'Sign in'
                    : 'Create an account'}
                </a>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}