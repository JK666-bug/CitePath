import type { CSSProperties } from 'react'

import type { CourseSummary } from './api'
import type { StudyPlan } from '../course/types'

import { decodeBrief } from '../courseEditor/brief'
import { Link } from '../../shared/router'

import {
  dateKey,
  daysBetween,
  duration,
  prettyDate,
} from '../../shared/format'

import PaceLine, {
  taskTotals,
} from '../../shared/components/PaceLine'

export default function CourseCard({
  course,
  plan,
  index = 0,
  demo = false,
}: {
  course: CourseSummary
  plan?: StudyPlan
  index?: number
  demo?: boolean
}) {
  const config =
    decodeBrief(course.student_brief)

  const id = demo
    ? 'demo'
    : String(course.id)

  const totals = plan
    ? taskTotals(plan.tasks)
    : null

  const today = plan?.tasks
    .filter(
      (task) =>
        task.date === dateKey() &&
        task.status !== 'Completed',
    )
    .reduce(
      (sum, task) => sum + task.minutes,
      0,
    )

  const next =
    plan?.tasks
      .filter(
        (task) =>
          task.status !== 'Completed',
      )
      .slice()
      .sort((a, b) =>
        a.date.localeCompare(b.date),
      )
      .slice(0, 3) || []

  const colors = [
    '#aa8e72',
    '#9b8caf',
    '#ba9391',
    '#a89b77',
  ]

  return (
    <article
      className="course-card"
      style={
        {
          '--course-accent':
            colors[index % colors.length],
        } as CSSProperties
      }
    >
      <div className="course-card-top">
        <div>
          <span className="course-color" />

          <h2>
            <Link
              href={`/courses/${id}/plan`}
            >
              {course.name}
            </Link>
          </h2>

          <span className="badge">
            {demo
              ? 'Interface demo'
              : 'Plan pending'}
          </span>
        </div>

        <div
          className="course-ring"
          style={
            {
              '--progress':
                `${totals?.progress || 0}%`,
            } as CSSProperties
          }
          aria-label={
            totals
              ? `${totals.progress}% of planned time completed`
              : 'Progress unavailable'
          }
        >
          <span>
            {totals
              ? `${totals.progress}%`
              : '—'}
          </span>
        </div>
      </div>

      <p className="course-deadline">
        Deadline{' '}
        <strong>
          {prettyDate(config.deadline)}
        </strong>

        {config.deadline && (
          <>
            {' · '}
            {daysBetween(
              dateKey(),
              config.deadline,
            ) < 0
              ? 'Past due'
              : `${daysBetween(
                  dateKey(),
                  config.deadline,
                )} days left`}
          </>
        )}
      </p>

      <div className="course-metrics">
        <div>
          <small>Today’s suggestion</small>
          <strong>
            {today === undefined
              ? '—'
              : today
                ? duration(today)
                : 'Rest day'}
          </strong>
        </div>

        <div>
          <small>Total study time</small>
          <strong>
            {totals
              ? duration(totals.total)
              : '—'}
          </strong>
        </div>

        <div>
          <small>Remaining</small>
          <strong>
            {totals
              ? duration(totals.remaining)
              : '—'}
          </strong>
        </div>

        <div>
          <small>Scheduled remaining</small>
          <strong>
            {totals
              ? duration(totals.remaining)
              : '—'}
          </strong>
        </div>
      </div>

      {plan ? (
        <>
          <PaceLine
            plan={plan}
            config={config}
            compact
          />

          <div className="course-categories">
            {(
              [
                'Reading',
                'Practice',
                'Review',
              ] as const
            ).map((kind) => {
              const tasks =
                plan.tasks.filter(
                  (task) =>
                    task.kind === kind,
                )

              return (
                <div key={kind}>
                  <span>{kind}</span>
                  <small>
                    {
                      tasks.filter(
                        (task) =>
                          task.status ===
                          'Completed',
                      ).length
                    }
                    /{tasks.length}
                  </small>
                </div>
              )
            })}
          </div>

          <div className="course-next">
            <p className="eyebrow">
              Up next
            </p>

            {next.length ? (
              next.map((task) => (
                <div key={task.id}>
                  <small>
                    {prettyDate(task.date)}
                  </small>
                  <span>{task.title}</span>
                </div>
              ))
            ) : (
              <p className="muted small">
                All planned tasks are complete.
              </p>
            )}
          </div>
        </>
      ) : (
        <div className="course-plan-pending">
          <p>
            {course.document_count}{' '}
            {course.document_count === 1
              ? 'material'
              : 'materials'}{' '}
            saved
          </p>

          <p className="muted small">
            Study time and progress will appear
            when the planning service is
            connected.
          </p>
        </div>
      )}

      <div className="actions">
        <Link
          className="button small"
          href={`/courses/${id}/plan`}
        >
          View plan
        </Link>

        <Link
          className="button small secondary"
          href={`/courses/${id}/info`}
        >
          Course information
        </Link>
      </div>
    </article>
  )
}