import {
  BookOpen,
  PencilLine,
  RotateCcw,
} from 'lucide-react'

import type { CourseDetail } from './types'
import { decodeBrief } from '../courseEditor/brief'

import { useStudy } from '../../shared/StudyProvider'

import {
  Link,
  navigate,
  useLocation,
} from '../../shared/router'

import {
  duration,
  prettyDate,
} from '../../shared/format'

import {
  PlanningUnavailable,
  Sources,
} from '../../shared/components/UI'

import PaceLine, {
  ProgressTrack,
  taskTotals,
} from '../../shared/components/PaceLine'

import TaskDetails from './TaskDetails'

export default function CoursePlan({
  courseId,
  course,
}: {
  courseId: string
  course: CourseDetail
}) {
  const {
    demo,
    completeTask,
  } = useStudy()

  const { search } = useLocation()

  if (courseId !== 'demo') {
    return <PlanningUnavailable />
  }

  const plan = demo.plan

  const config =
    decodeBrief(course.student_brief)

  const totals = taskTotals(plan.tasks)

  const selected =
    plan.tasks.find(
      (task) =>
        task.id === search.get('task'),
    ) || null

  return (
    <div className="stack">
      <div className="course-plan-overview">
        <section className="panel">
          <h2>Your course progress</h2>

          <ProgressTrack
            label="Planned study time completed"
            done={totals.done}
            total={totals.total}
          />

          <div className="plan-stats">
            <div>
              <small>Total estimate</small>
              <strong>
                {duration(totals.total)}
              </strong>
            </div>

            <div>
              <small>Remaining</small>
              <strong>
                {duration(totals.remaining)}
              </strong>
            </div>

            <div>
              <small>Tasks completed</small>
              <strong>
                {plan.tasks.filter((task) => task.status === 'Completed').length}
                {' / '}{plan.tasks.length}
              </strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Schedule outlook</h2>

          <PaceLine
            plan={plan}
            config={config}
          />
        </section>
      </div>

      <div className="plan-version">
        <p className="muted small">
          Plan v{plan.version}
          {' · '}
          {plan.reason}
        </p>

        <Link
          className="button small secondary"
          href="/calendar?course=demo"
        >
          View in calendar
        </Link>
      </div>

      {plan.chapters.map(
        (chapter, chapterIndex) => (
          <section
            className="panel chapter-section"
            key={chapter.id}
          >
            <header>
              <div>
                <p className="eyebrow">
                  Chapter {chapterIndex + 1}
                </p>

                <h2>{chapter.title}</h2>

                <p className="muted small">
                  {chapter.concepts.join(' · ')}
                </p>
              </div>

              <Sources
                materials={course.documents}
                sources={chapter.sources}
              />
            </header>

            <div className="plan-task-list">
              {plan.tasks
                .filter(
                  (task) =>
                    task.chapterId ===
                    chapter.id,
                )
                .map((task) => {
                  const Icon =
                    task.kind === 'Reading'
                      ? BookOpen
                      : task.kind === 'Practice'
                        ? PencilLine
                        : RotateCcw

                  return (
                    <article
                      className={
                        `plan-task ${
                          task.status ===
                          'Completed'
                            ? 'completed'
                            : ''
                        }`
                      }
                      key={task.id}
                    >
                      <span
                        className={
                          `task-symbol ` +
                          task.kind.toLowerCase()
                        }
                      >
                        <Icon
                          size={17}
                          strokeWidth={1.5}
                        />
                      </span>

                      <div className="plan-task-body">
                        <button
                          className="task-title"
                          onClick={() =>
                            navigate(
                              '/courses/demo/plan?task=' +
                                encodeURIComponent(
                                  task.id,
                                ),
                            )
                          }
                        >
                          {task.title}
                        </button>

                        <p className="muted small">
                          {prettyDate(task.date)}
                          {' · '}
                          {duration(task.minutes)}
                          {' · '}
                          Step{' '}
                          {plan.tasks.findIndex(
                            (item) =>
                              item.id === task.id,
                          ) + 1}
                        </p>
                      </div>

                      <span className="badge">
                        {task.status}
                      </span>

                      {task.kind ===
                      'Practice' ? (
                        <Link
                          className="button small secondary"
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
                            completeTask(task.id)
                          }
                        >
                          {task.status ===
                          'Completed'
                            ? 'Done'
                            : 'Mark complete'}
                        </button>
                      )}
                    </article>
                  )
                })}
            </div>
          </section>
        ),
      )}

      <TaskDetails
        task={selected}
        materials={course.documents}
        onClose={() =>
          navigate('/courses/demo/plan')
        }
        onComplete={completeTask}
      />
    </div>
  )
}
