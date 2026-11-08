import {
  useEffect,
  useState,
} from 'react'

import {
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

import { useStudy } from '../../shared/StudyProvider'

import {
  Link,
  navigate,
  useLocation,
} from '../../shared/router'

import {
  dateKey,
  parseDate,
} from '../../shared/format'

import {
  DemoNotice,
  Notice,
  PageHeader,
} from '../../shared/components/UI'

import PaceLine, {
  ProgressTrack,
  taskTotals,
} from '../../shared/components/PaceLine'

import { decodeBrief } from '../courseEditor/brief'

import MonthGrid from './MonthGrid'
import DayOverview from './DayOverview'

import './calendar.css'

function validDate(
  value: string | null,
) {
  if (
    !value ||
    !/^\d{4}-\d{2}-\d{2}$/.test(value)
  ) {
    return ''
  }

  return dateKey(parseDate(value)) === value
    ? value
    : ''
}

export default function CalendarPage() {
  const {
    demo,
    courses,
    completeTask,
  } = useStudy()

  const { search } = useLocation()

  const selected =
    validDate(search.get('date'))

  const filter =
    search.get('course') || 'all'

  const demoMode = filter === 'demo'

  const [month, setMonth] = useState(
    () =>
      selected
        ? parseDate(selected)
        : new Date(),
  )

  useEffect(() => {
    if (selected) {
      setMonth(parseDate(selected))
    }
  }, [selected])

  const tasks = demoMode
    ? demo.plan.tasks
    : []

  const todayTasks = tasks.filter(
    (task) =>
      task.date === dateKey(),
  )

  const todayTotals =
    taskTotals(todayTasks)

  function update(values: {
    date?: string
    course?: string
  }) {
    const next =
      new URLSearchParams(search)

    for (
      const [key, value]
      of Object.entries(values)
    ) {
      if (value) {
        next.set(key, value)
      } else {
        next.delete(key)
      }
    }

    navigate(
      `/calendar${
        next.size ? `?${next}` : ''
      }`,
    )
  }

  return (
    <div className="calendar-page">
      <PageHeader
        eyebrow="One day at a time"
        title="Study calendar"
        subtitle="Reading, practice, and review in one clear view."
      />

      {demoMode ? (
        <DemoNotice />
      ) : (
        <Notice>
          Real courses will appear here once
          the planning service is connected.
          {' '}
          <Link href="/calendar?course=demo">
            Preview the sample calendar
          </Link>.
        </Notice>
      )}

      <div className="calendar-progress">
        <section className="panel">
          <ProgressTrack
            label="Today’s study pace"
            unavailable={!demoMode}
            done={todayTotals.done}
            total={todayTotals.total}
          />

          {demoMode ? (
            <small className="muted">
              Target: complete today’s
              scheduled tasks.
            </small>
          ) : (
            <small className="muted">
              No connected plan data.
            </small>
          )}
        </section>

        <section className="panel">
          <h2 className="calendar-pace-title">
            Overall schedule outlook
          </h2>

          {demoMode ? (
            <PaceLine
              plan={demo.plan}
              config={decodeBrief(
                demo.course.student_brief,
              )}
              compact
            />
          ) : (
            <ProgressTrack
              label="Overall study pace"
              unavailable
              done={0}
              total={0}
            />
          )}
        </section>
      </div>

      <section className="calendar-toolbar">
        <div className="actions">
          <button
            className="icon-button"
            aria-label="Previous month"
            onClick={() => {
              setMonth((current) =>
                new Date(
                  current.getFullYear(),
                  current.getMonth() - 1,
                  1,
                  12,
                ),
              )

              update({ date: '' })
            }}
          >
            <ChevronLeft size={17} />
          </button>

          <h2>
            {new Intl.DateTimeFormat(
              'en-US',
              {
                month: 'long',
                year: 'numeric',
              },
            ).format(month)}
          </h2>

          <button
            className="icon-button"
            aria-label="Next month"
            onClick={() => {
              setMonth((current) =>
                new Date(
                  current.getFullYear(),
                  current.getMonth() + 1,
                  1,
                  12,
                ),
              )

              update({ date: '' })
            }}
          >
            <ChevronRight size={17} />
          </button>

          <button
            className="button small secondary"
            onClick={() => {
              setMonth(new Date())
              update({ date: dateKey() })
            }}
          >
            Today
          </button>
        </div>

        <label className="calendar-filter">
          <span className="sr-only">
            Filter courses
          </span>

          <select
            className="cp-select"
            value={filter}
            onChange={(event) =>
              update({
                course:
                  event.target.value,
                date: '',
              })
            }
          >
            <option value="all">
              All real courses
            </option>

            {courses.map((course) => (
              <option
                key={course.id}
                value={String(course.id)}
              >
                {course.name}
              </option>
            ))}

            <option value="demo">
              Interface demo course
            </option>
          </select>
        </label>
      </section>

      <div
        className={
          `calendar-workspace ${
            selected
              ? 'has-overview'
              : ''
          }`
        }
      >
        <div className="calendar-board">
          <MonthGrid
            month={month}
            selected={selected}
            tasks={tasks}
            onSelect={(date) => {
              setMonth(parseDate(date))

              update({
                date:
                  selected === date
                    ? ''
                    : date,
              })
            }}
          />
        </div>

        {selected && (
          <DayOverview
            date={selected}
            tasks={tasks.filter(
              (task) =>
                task.date === selected,
            )}
            courseName={demo.course.name}
            onClose={() =>
              update({ date: '' })
            }
            onComplete={completeTask}
          />
        )}
      </div>
    </div>
  )
}