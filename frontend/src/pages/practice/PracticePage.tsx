import {
  Link,
  navigate,
  useLocation,
} from '../../shared/router'

import { useStudy } from '../../shared/StudyProvider'

import {
  DemoNotice,
  Empty,
  Notice,
  PageHeader,
} from '../../shared/components/UI'

import './practice.css'

export default function PracticePage() {
  const { demo, courses } = useStudy()
  const { search } = useLocation()

  const filter =
    search.get('course') || 'all'

  return (
    <div className="practice-page">
      <PageHeader
        eyebrow="Practice with evidence"
        title="Chapter practice"
        subtitle="Check your understanding, review weak concepts, and return to your plan."
        actions={
          <label>
            <span className="sr-only">
              Filter practice by course
            </span>

            <select
              className="cp-select"
              value={filter}
              onChange={(event) =>
                navigate(
                  '/practice?course=' +
                    encodeURIComponent(
                      event.target.value,
                    ),
                )
              }
            >
              <option value="all">
                All real courses
              </option>

              {courses.map((course) => (
                <option
                  key={course.id}
                  value={course.id}
                >
                  {course.name}
                </option>
              ))}

              <option value="demo">
                Interface demo course
              </option>
            </select>
          </label>
        }
      />

      {filter === 'demo' ? (
        <>
          <DemoNotice />

          <div className="practice-grid">
            {demo.plan.chapters.map(
              (chapter, index) => {
                const session =
                  demo.sessions[chapter.id]

                const last =
                  session?.history.at(-1)

                return (
                  <article
                    key={chapter.id}
                    className="panel practice-chapter"
                  >
                    <p className="eyebrow">
                      Chapter {index + 1}
                      {' · '}
                      Interface demo
                    </p>

                    <h2>{chapter.title}</h2>

                    <p className="muted small">
                      {chapter.concepts.join(
                        ' · ',
                      )}
                    </p>

                    <div className="actions">
                      <span className="badge">
                        {session
                          ? session.status
                          : 'Not started'}
                      </span>

                      {session && (
                        <small className="muted">
                          Round {session.round}
                          {' / 2'}
                        </small>
                      )}
                    </div>

                    {last && (
                      <p className="chapter-score">
                        Last score
                        <strong>
                          {last.score}%
                        </strong>
                      </p>
                    )}

                    <div className="actions">
                      <Link
                        className="button small"
                        href={
                          `/practice/demo/${chapter.id}`
                        }
                      >
                        {!session
                          ? 'Start practice'
                          : session.status ===
                              'Answering'
                            ? 'Continue practice'
                            : 'View result'}
                      </Link>

                      {last && (
                        <Link
                          className="button small secondary"
                          href={
                            `/practice/demo/${chapter.id}/report`
                          }
                        >
                          View report
                        </Link>
                      )}
                    </div>
                  </article>
                )
              },
            )}
          </div>
        </>
      ) : (
        <>
          <Notice>
            The current backend does not expose
            the practice module yet. No
            questions or scores are generated
            for real courses in this interface.
          </Notice>

          <Empty title="No connected practice sessions">
            <p>
              Practice sessions will appear
              here after the existing B module
              is connected.
            </p>

            <div className="actions centered">
              <Link
                className="button secondary"
                href="/practice?course=demo"
              >
                Try the fixed interface demo
              </Link>
            </div>
          </Empty>
        </>
      )}
    </div>
  )
}