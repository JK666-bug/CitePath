import { useStudy } from '../../shared/StudyProvider'
import { Link } from '../../shared/router'

import {
  DemoNotice,
  Empty,
  PageHeader,
  Sources,
} from '../../shared/components/UI'

import './practice.css'

export default function ChapterReportPage({
  courseId,
  chapterId,
}: {
  courseId: string
  chapterId: string
}) {
  const { demo } = useStudy()

  if (courseId !== 'demo') {
    return (
      <Empty title="Reports are not connected yet">
        <Link href="/practice">
          Back to chapter practice
        </Link>
      </Empty>
    )
  }

  const chapter =
    demo.plan.chapters.find(
      (item) => item.id === chapterId,
    )

  const session =
    demo.sessions[chapterId]

  const last =
    session?.history.at(-1)

  if (
    !chapter ||
    !session ||
    !last
  ) {
    return (
      <Empty title="No report yet">
        <p>
          Submit a sample practice round to
          see the chapter report.
        </p>

        <Link href="/practice?course=demo">
          Back to sample practice
        </Link>
      </Empty>
    )
  }

  const status =
    session.status === 'Answering'
      ? 'Round 2 in progress'
      : session.status === 'Review required'
        ? 'Review before round 2'
        : last.passed
          ? `Passed in round ${last.round}`
          : 'Ended after round 2 · Not yet passed'

  return (
    <div className="practice-session">
      <PageHeader
        eyebrow="Sample chapter report"
        title={chapter.title}
        subtitle={demo.course.name}
        actions={
          <Link
            className="button secondary"
            href="/courses/demo/plan"
          >
            Back to plan
          </Link>
        }
      />

      <DemoNotice />

      <section className="panel stack">
        <span
          className={
            `badge ${
              last.passed
                ? ''
                : 'warning'
            }`
          }
        >
          {status}
        </span>

        <h2>Round summary</h2>

        <div className="report-rounds">
          {([1, 2] as const).map(
            (round) => {
              const result =
                session.history.find(
                  (item) =>
                    item.round === round,
                )

              return (
                <div key={round}>
                  <small>
                    Round {round}
                  </small>

                  <strong>
                    {result
                      ? `${result.score}%`
                      : session.round ===
                            round &&
                          session.status ===
                            'Answering'
                        ? 'In progress'
                        : 'Not taken'}
                  </strong>

                  <span className="muted small">
                    {result
                      ? result.passed
                        ? 'Passed'
                        : 'Below pass mark'
                      : 'No score recorded'}
                  </span>
                </div>
              )
            },
          )}
        </div>

        <p className="muted small">
          Round scores are reported separately.
          A first-round score is not averaged
          with a second-round score.
        </p>
      </section>

      <section className="panel stack">
        <h2>
          {last.passed
            ? 'Concepts checked'
            : 'Concepts to reinforce'}
        </h2>

        <p>
          {chapter.concepts.join(' · ')}
        </p>

        <Sources
          materials={demo.course.documents}
          sources={chapter.sources}
        />

        <p className="muted">
          {last.passed
            ? 'No remaining weak concepts are reported by this fixed sample result.'
            : 'The fixed demo associates incorrect answers with this chapter’s sample concepts. The real practice module supplies the actual weak-concept mapping.'}
        </p>
      </section>

      <section className="panel stack">
        <h2>
          What changed in your plan?
        </h2>

        <p>{demo.plan.reason}</p>

        <small className="muted">
          Plan v{demo.plan.version}.
          Completed tasks remain preserved.
        </small>

        <div className="actions">
          <Link
            className="button"
            href="/courses/demo/plan"
          >
            View updated plan
          </Link>

          <Link
            className="button secondary"
            href="/calendar?course=demo"
          >
            View calendar
          </Link>

          <Link
            className="button secondary"
            href={
              `/practice/demo/${chapterId}`
            }
          >
            {session.status === 'Answering'
              ? 'Continue practice'
              : 'View result'}
          </Link>
        </div>
      </section>
    </div>
  )
}
