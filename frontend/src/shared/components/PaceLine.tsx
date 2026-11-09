import {
  addDays,
  dateKey,
  daysBetween,
  duration,
  percent,
  prettyDate,
} from '../format'

import { DEMO_WEEKLY_MINUTES } from '../../pages/course/demo'

import type {
  CourseConfig,
  StudyPlan,
  Task,
} from '../../pages/course/types'

export function taskTotals(tasks: Task[]) {
  const total = tasks.reduce(
    (sum, task) => sum + task.minutes,
    0,
  )

  const done = tasks
    .filter(
      (task) => task.status === 'Completed',
    )
    .reduce(
      (sum, task) => sum + task.minutes,
      0,
    )

  return {
    total,
    done,
    remaining: total - done,
    progress: percent(done, total),
  }
}

export function ProgressTrack({
  label,
  done,
  total,
  unavailable = false,
}: {
  label: string
  done: number
  total: number
  unavailable?: boolean
}) {
  const progress = percent(done, total)

  return (
    <div className="progress-track">
      <div>
        <span>{label}</span>

        <strong>
          {unavailable ? '—' : `${progress}%`}
        </strong>
      </div>

      {unavailable ? (
        <p className="muted small">
          Waiting for connected plan data.
        </p>
      ) : (
        <>
          <div
            className="progress-rail"
            role="progressbar"
            aria-label={label}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
          >
            <span
              style={{
                width: `${progress}%`,
              }}
            />
          </div>

          <small className="muted">
            {duration(done)} of {duration(total)}
            {' '}completed
          </small>
        </>
      )}
    </div>
  )
}

export default function PaceLine({
  plan,
  config,
  compact = false,
}: {
  plan: StudyPlan
  config: CourseConfig
  compact?: boolean
}) {
  const { remaining } =
    taskTotals(plan.tasks)

  const target = addDays(
    config.deadline,
    -config.earlyDays,
  )

  const forecast = addDays(
    dateKey(),
    Math.ceil(remaining / (DEMO_WEEKLY_MINUTES / 7)),
  )

  const span = Math.max(
    1,
    daysBetween(
      plan.start,
      config.deadline,
    ),
  )

  const position = (date: string) =>
    Math.min(
      100,
      Math.max(
        0,
        (daysBetween(plan.start, date) /
          span) *
          100,
      ),
    )

  const late = forecast > target

  return (
    <section
      className={
        `pace-line ${compact ? 'compact' : ''}`
      }
      aria-label="Schedule outlook"
    >
      <div className="pace-heading">
        <span
          className={
            `badge ${late ? 'warning' : ''}`
          }
        >
          {late
            ? 'Needs attention'
            : 'On schedule'}
        </span>

        <small>
          Finish {config.earlyDays} days early
        </small>
      </div>

      <p className="pace-summary">
        Estimated finish{' '}
        <strong>
          {prettyDate(forecast)}
        </strong>
      </p>

      <div className="pace-axis">
        <span
          className="pace-elapsed"
          style={{
            width:
              `${position(dateKey())}%`,
          }}
        />

        <span
          className="pace-today"
          style={{
            left:
              `${position(dateKey())}%`,
          }}
          title="Today"
        />

        <span
          className="pace-target"
          style={{
            left: `${position(target)}%`,
          }}
          title={
            `Target: ${prettyDate(target)}`
          }
        />

        <span
          className="pace-deadline"
          title={
            `Deadline: ` +
            prettyDate(config.deadline)
          }
        />
      </div>

      <div className="pace-labels">
        <span>
          {prettyDate(plan.start)}
        </span>

        <span>
          Target {prettyDate(target)}
        </span>

        <span>
          Due {prettyDate(config.deadline)}
        </span>
      </div>

      {!compact && (
        <p className="muted small">
          Sample outlook uses a fixed demo budget of
          {' '}{duration(DEMO_WEEKLY_MINUTES)} per week.
        </p>
      )}
    </section>
  )
}