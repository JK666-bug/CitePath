import { X } from 'lucide-react'
import type { Task } from '../course/types'

import {
  duration,
  parseDate,
} from '../../shared/format'

import { Link } from '../../shared/router'
import { Sources } from '../../shared/components/UI'

export default function DayOverview({
  date,
  tasks,
  courseName,
  onClose,
  onComplete,
}: {
  date: string
  tasks: Task[]
  courseName: string
  onClose: () => void
  onComplete: (id: string) => void
}) {
  return (
    <aside
      className="day-overview"
      aria-label="Selected day overview"
    >
      <header>
        <div>
          <p className="eyebrow">
            Day overview
          </p>

          <h2>
            {new Intl.DateTimeFormat(
              'en-US',
              {
                weekday: 'long',
                month: 'short',
                day: 'numeric',
              },
            ).format(parseDate(date))}
          </h2>
        </div>

        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close day overview"
        >
          <X size={16} />
        </button>
      </header>

      <p className="muted small">
        {tasks.length} tasks
        {' · '}
        {duration(
          tasks.reduce(
            (sum, task) =>
              sum + task.minutes,
            0,
          ),
        )}{' '}
        planned
      </p>

      {!tasks.length && (
        <p className="day-empty muted">
          Nothing scheduled. A little
          breathing room for your day.
        </p>
      )}

      <div className="day-task-list">
        {tasks.map((task) => (
          <article
            key={task.id}
            className="day-task"
          >
            <div className="actions spread">
              <span className="badge">
                {task.kind}
              </span>

              <small className="muted">
                {duration(task.minutes)}
              </small>
            </div>

            <h3>{task.title}</h3>

            <p className="muted small">
              {courseName}
            </p>

            <Sources
              sources={task.sources}
            />

            <p className="small muted">
              {task.status}
            </p>

            <div className="actions">
              {task.kind === 'Practice' ? (
                <Link
                  className="button small"
                  href={
                    `/practice/demo/${task.chapterId}`
                  }
                >
                  Open practice
                </Link>
              ) : (
                <button
                  className="button small secondary"
                  disabled={
                    task.status ===
                    'Completed'
                  }
                  onClick={() =>
                    onComplete(task.id)
                  }
                >
                  {task.status === 'Completed'
                    ? 'Completed'
                    : 'Mark complete'}
                </button>
              )}

              <Link
                className="small"
                href={
                  '/courses/demo/plan?task=' +
                  encodeURIComponent(
                    task.id,
                  )
                }
              >
                View in plan
              </Link>
            </div>
          </article>
        ))}
      </div>
    </aside>
  )
}