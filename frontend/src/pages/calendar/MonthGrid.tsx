import { dateKey } from '../../shared/format'
import type { Task } from '../course/types'

export default function MonthGrid({
  month,
  selected,
  tasks,
  onSelect,
}: {
  month: Date
  selected: string
  tasks: Task[]
  onSelect: (date: string) => void
}) {
  const first = new Date(
    month.getFullYear(),
    month.getMonth(),
    1,
    12,
  )

  const offset =
    (first.getDay() + 6) % 7

  const dates = Array.from(
    { length: 42 },
    (_, index) =>
      new Date(
        month.getFullYear(),
        month.getMonth(),
        1 - offset + index,
        12,
      ),
  )

  return (
    <table
      className="month-grid"
      aria-label={
        new Intl.DateTimeFormat(
          'en-US',
          {
            month: 'long',
            year: 'numeric',
          },
        ).format(month)
      }
    >
      <thead>
        <tr>
          {[
            'Mon',
            'Tue',
            'Wed',
            'Thu',
            'Fri',
            'Sat',
            'Sun',
          ].map((day) => (
            <th
              key={day}
              scope="col"
            >
              {day}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {Array.from(
          { length: 6 },
          (_, row) => (
            <tr key={row}>
              {dates
                .slice(
                  row * 7,
                  row * 7 + 7,
                )
                .map((date) => {
                  const key = dateKey(date)

                  const dayTasks =
                    tasks.filter(
                      (task) =>
                        task.date === key,
                    )

                  return (
                    <td
                      key={key}
                      className={
                        `${
                          date.getMonth() !==
                          month.getMonth()
                            ? 'outside-month'
                            : ''
                        } ${
                          selected === key
                            ? 'selected-date'
                            : ''
                        }`
                      }
                    >
                      <button
                        type="button"
                        className="calendar-date-button"
                        aria-pressed={
                          selected === key
                        }
                        aria-label={
                          new Intl.DateTimeFormat(
                            'en-US',
                            {
                              dateStyle: 'full',
                            },
                          ).format(date) +
                          `, ${dayTasks.length} tasks`
                        }
                        onClick={() =>
                          onSelect(key)
                        }
                      >
                        <span
                          className={
                            `calendar-date-number ${
                              key === dateKey()
                                ? 'is-today'
                                : ''
                            }`
                          }
                          aria-current={
                            key === dateKey()
                              ? 'date'
                              : undefined
                          }
                        >
                          {date.getDate()}
                        </span>

                        <span className="calendar-cell-tasks">
                          {dayTasks
                            .slice(0, 2)
                            .map((task) => (
                              <span
                                className={
                                  `calendar-task type-${task.kind.toLowerCase()} ${
                                    task.status ===
                                    'Completed'
                                      ? 'is-completed'
                                      : ''
                                  }`
                                }
                                key={task.id}
                              >
                                <strong>
                                  {task.title}
                                </strong>

                                <small>
                                  Demo · {task.kind}
                                </small>
                              </span>
                            ))}

                          {dayTasks.length >
                            2 && (
                            <small className="more-tasks">
                              +{dayTasks.length - 2}
                              {' '}more
                            </small>
                          )}
                        </span>
                      </button>
                    </td>
                  )
                })}
            </tr>
          ),
        )}
      </tbody>
    </table>
  )
}