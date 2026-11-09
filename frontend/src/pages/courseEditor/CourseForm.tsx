import type { CourseConfig } from '../course/types'
import { Link } from '../../shared/router'
export type CourseFormValue =
  CourseConfig & {
    name: string
  }

export default function CourseForm({
  value,
  onChange,
  errors,
  disabled,
}: {
  value: CourseFormValue
  onChange: (
    value: CourseFormValue,
  ) => void
  errors: Record<string, string>
  disabled: boolean
}) {
  function error(key: string) {
    return errors[key] ? (
      <span
        id={`course-${key}-error`}
        className="field-error"
        role="alert"
      >
        {errors[key]}
      </span>
    ) : null
  }

  return (
    <div className="form-grid">
      <label className="field full">
        <span>Course name</span>

        <input
          id="course-name"
          value={value.name}
          maxLength={255}
          disabled={disabled}
          aria-invalid={
            Boolean(errors.name)
          }
          aria-describedby={
            errors.name
              ? 'course-name-error'
              : undefined
          }
          onChange={(event) =>
            onChange({
              ...value,
              name: event.target.value,
            })
          }
          placeholder="e.g. Algorithms & Data Structures"
        />

        {error('name')}
      </label>

      <label className="field">
        <span>Learning deadline</span>

        <input
          id="course-deadline"
          type="date"
          value={value.deadline}
          disabled={disabled}
          aria-invalid={
            Boolean(errors.deadline)
          }
          aria-describedby={
            errors.deadline
              ? 'course-deadline-error'
              : undefined
          }
          onChange={(event) =>
            onChange({
              ...value,
              deadline:
                event.target.value,
            })
          }
        />

        {error('deadline')}
      </label>


      <label className="field">
        <span>
          Finish early by (days)
        </span>

        <input
          id="course-earlyDays"
          type="number"
          min="0"
          step="1"
          value={value.earlyDays}
          disabled={disabled}
          aria-invalid={
            Boolean(errors.earlyDays)
          }
          aria-describedby={
            errors.earlyDays
              ? 'course-earlyDays-error'
              : undefined
          }
          onChange={(event) =>
            onChange({
              ...value,
              earlyDays: Number(
                event.target.value,
              ),
            })
          }
        />

        {error('earlyDays')}
      </label>

      <div className="editor-help full">
        <strong>Time for review</strong>
        <p>
          All courses share the time you set in{' '}
          <Link href="/settings">Study&nbsp;availability</Link>.
        </p>
      </div>

      <label className="field full">
        <span>
          Goals, background, and important dates
        </span>

        <textarea
          id="course-note"
          rows={4}
          value={value.note}
          disabled={disabled}
          maxLength={9000}
          onChange={(event) =>
            onChange({
              ...value,
              note: event.target.value,
            })
          }
          placeholder="Tell us about your goal, current knowledge, exam date, and assignment deadlines."
        />

        {error('note')}

        <small className="muted">
          Your original note is preserved with
          the course settings.
        </small>
      </label>
    </div>
  )
}