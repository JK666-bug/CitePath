import type { Task } from './types'

import {
  duration,
  prettyDate,
} from '../../shared/format'

import { Link } from '../../shared/router'

import {
  Modal,
  Sources,
} from '../../shared/components/UI'

export default function TaskDetails({
  task,
  onClose,
  onComplete,
}: {
  task: Task | null
  onClose: () => void
  onComplete: (id: string) => void
}) {
  return (
    <Modal
      open={Boolean(task)}
      title="Task details"
      onClose={onClose}
    >
      {task && (
        <div className="stack">
          <span className="badge">
            {task.kind}
          </span>

          <h3>{task.title}</h3>

          <p className="muted">
            {prettyDate(task.date, true)}
            {' · '}
            {duration(task.minutes)}
            {' · '}
            {task.status}
          </p>

          <div>
            <strong>Concepts</strong>

            <p className="muted">
              {task.concepts.join(' · ')}
            </p>
          </div>

          <div>
            <strong>
              Reading source
            </strong>

            <Sources
              sources={task.sources}
            />
          </div>

          <div className="actions">
            {task.kind === 'Practice' ? (
              <Link
                className="button"
                href={
                  `/practice/demo/${task.chapterId}`
                }
              >
                Open chapter practice
              </Link>
            ) : (
              <button
                className="button"
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
          </div>
        </div>
      )}
    </Modal>
  )
}