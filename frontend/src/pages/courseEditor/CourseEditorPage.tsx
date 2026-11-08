import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  useCourse,
  useStudy,
} from '../../shared/StudyProvider'

import { Link } from '../../shared/router'

import {
  ApiError,
  messageOf,
} from '../../shared/request'

import {
  addDays,
  dateKey,
} from '../../shared/format'

import {
  DemoNotice,
  Loading,
  Notice,
  PageHeader,
} from '../../shared/components/UI'

import type { CourseDetail } from '../course/types'
import {
  duplicateMessage,
  uploadMaterial,
} from '../course/api'

import { createCourse } from './api'

import {
  decodeBrief,
  encodeBrief,
} from './brief'

import CourseForm from './CourseForm'
import type { CourseFormValue } from './CourseForm'

import MaterialPicker, {
  fileKey,
} from './MaterialPicker'

import AnalysisDialog from './AnalysisDialog'
import './courseEditor.css'

function Editor({
  course,
  courseId,
}: {
  course?: CourseDetail
  courseId?: string
}) {
  const isDemo = courseId === 'demo'
  const realEdit =
    Boolean(course && !isDemo)

  const {
    editDemo,
    refreshCourses,
    loadCourse,
  } = useStudy()

  const [value, setValue] =
    useState<CourseFormValue>(() => ({
      name: course?.name || '',
      ...(course
        ? decodeBrief(
            course.student_brief,
          )
        : {
            deadline: addDays(
              dateKey(),
              30,
            ),
            weeklyHours: 6,
            earlyDays: 2,
            note: '',
          }),
    }))

  const [files, setFiles] =
    useState<File[]>([])

  const [errors, setErrors] =
    useState<Record<string, string>>({})

  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const [createdId, setCreatedId] =
    useState<number | null>(null)

  const [uploaded, setUploaded] =
    useState<string[]>([])

  const [
    uncertainCreate,
    setUncertainCreate,
  ] = useState(false)

  const [retryChecked, setRetryChecked] =
    useState(false)

  async function save(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (
      busy ||
      realEdit ||
      uncertainCreate
    ) {
      return
    }

    const next: Record<string, string> = {}

    if (!value.name.trim()) {
      next.name =
        'Please enter a course name.'
    }

    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(
        value.deadline,
      ) ||
      value.deadline < dateKey()
    ) {
      next.deadline =
        'Choose today or a future date.'
    }

    if (
      !Number.isFinite(
        value.weeklyHours,
      ) ||
      value.weeklyHours < 0.5 ||
      value.weeklyHours > 168
    ) {
      next.weeklyHours =
        'Enter a weekly study time between 0.5 and 168 hours.'
    }

    if (
      !Number.isInteger(
        value.earlyDays,
      ) ||
      value.earlyDays < 0 ||
      (
        value.deadline &&
        addDays(
          value.deadline,
          -value.earlyDays,
        ) < dateKey()
      )
    ) {
      next.earlyDays =
        'Choose a whole number that keeps your target date on or after today.'
    }

    if (
      files.some(
        (file) =>
          !file.name
            .toLowerCase()
            .endsWith('.pdf'),
      )
    ) {
      next.files =
        'Please choose PDF files only.'
    }

    if (
      files.some(
        (file) => file.size === 0,
      )
    ) {
      next.files =
        'Empty files cannot be uploaded.'
    }

    const brief = encodeBrief({
      deadline: value.deadline,
      weeklyHours: value.weeklyHours,
      earlyDays: value.earlyDays,
      note: value.note,
    })

    if (
      Array.from(brief).length > 10000
    ) {
      next.note =
        'Your course settings and note are too long. Please shorten your note.'
    }

    setErrors(next)

    if (Object.keys(next).length) {
      document
        .getElementById(
          `course-${Object.keys(next)[0]}`,
        )
        ?.focus()

      return
    }

    setBusy(true)
    setOpen(true)
    setError('')
    setStatus('Saving course settings…')

    let id = createdId

    try {
      if (isDemo) {
        editDemo(
          value.name.trim(),
          value,
        )

        setStatus(
          'Sample study time and dates have been recalculated.',
        )
      } else {
        if (!id) {
          const result =
            await createCourse(
              value.name.trim(),
              brief,
            )

          id = result.id
          setCreatedId(id)
        }

        const duplicates: string[] = []

        for (const file of files) {
          if (
            uploaded.includes(
              fileKey(file),
            )
          ) {
            continue
          }

          setStatus(
            `Uploading and processing ${file.name}…`,
          )

          const result =
            await uploadMaterial(id, file)

          if (result.duplicate) {
            duplicates.push(
              duplicateMessage(
                file.name,
                result.filename,
              ),
            )
          }

          setUploaded((current) => [
            ...current,
            fileKey(file),
          ])
        }

        await loadCourse(id)
        await refreshCourses()

        setStatus(
          duplicates.length
            ? `Course settings saved. ${duplicates.join(' ')} Automatic analysis is awaiting the planning service.`
            : 'Course settings and selected PDF materials have been saved. Automatic analysis is awaiting the planning service.',
        )
      }
    } catch (reason) {
      if (
        !id &&
        reason instanceof ApiError &&
        (
          reason.status === 0 ||
          reason.status >= 500
        )
      ) {
        setUncertainCreate(true)
      }

      setRetryChecked(false)

      setError(
        `${messageOf(reason)} A request may have reached the server. Check My courses and saved materials before retrying.`,
      )

      setStatus(
        id
          ? 'The course already exists. Do not create it again.'
          : 'Please verify whether a course was created before starting another request.',
      )

      await refreshCourses()
    } finally {
      setBusy(false)
    }
  }

  const retryBlocked = Boolean(
    createdId &&
    error &&
    !retryChecked,
  )

  return (
    <div className="course-editor-page">
      <PageHeader
        eyebrow={
          course
            ? 'Course settings'
            : 'A new learning path'
        }
        title={
          course
            ? 'Edit course'
            : 'Create a course'
        }
        subtitle="Keep your materials, goals, and available time together."
        actions={
          <Link
            className="button secondary"
            href={
              courseId
                ? `/courses/${courseId}/info`
                : '/courses'
            }
          >
            Back
          </Link>
        }
      />

      {isDemo && <DemoNotice />}

      {realEdit && (
        <Notice>
          The current backend supports reading
          course settings but has no update
          endpoint. These settings are
          read-only here. You can manage PDF
          materials in Course information.
        </Notice>
      )}

      <form
        className="panel editor-form stack"
        noValidate
        onSubmit={save}
      >
        <CourseForm
          value={value}
          onChange={(next) => {
            setValue(next)
            setErrors({})
          }}
          errors={errors}
          disabled={
            busy ||
            realEdit ||
            createdId !== null
          }
        />

        <section>
          <h2>Course materials</h2>

          {course && (
            <p className="muted small">
              {course.documents.length}
              {' '}materials already saved.
              {' '}
              <Link
                href={
                  `/courses/${courseId}/info`
                }
              >
                View materials
              </Link>
            </p>
          )}

          {isDemo ? (
            <p className="muted">
              This demo uses fixed sample
              materials. Upload your own PDFs
              through a real course.
            </p>
          ) : (
            !realEdit && (
              <MaterialPicker
                files={files}
                onChange={setFiles}
                disabled={busy}
              />
            )
          )}

          {errors.files && (
            <p
              className="field-error"
              role="alert"
            >
              {errors.files}
            </p>
          )}
        </section>

        {error && (
          <Notice tone="error">
            {error}
          </Notice>
        )}

        {createdId && error && (
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={retryChecked}
              onChange={(event) =>
                setRetryChecked(
                  event.target.checked,
                )
              }
            />
            I checked saved materials and
            removed files that were already
            uploaded.
          </label>
        )}

        {createdId && (
          <p className="muted small">
            Course #{createdId} is saved.
            {' '}{uploaded.length} upload
            requests have completed.
            {' '}
            <Link
              href={
                `/courses/${createdId}/info`
              }
              target="_blank"
              rel="noreferrer"
            >
              Check saved materials
            </Link>
          </p>
        )}

        {uncertainCreate && (
          <Notice>
            <Link href="/courses">
              Check My courses before starting
              a new request.
            </Link>
          </Notice>
        )}

        <div className="actions">
          <button
            className="button"
            type="submit"
            disabled={
              busy ||
              realEdit ||
              uncertainCreate ||
              retryBlocked
            }
          >
            {busy
              ? 'Saving…'
              : isDemo
                ? 'Save and update sample plan'
                : createdId
                  ? 'Retry remaining uploads'
                  : 'Save course'}
          </button>

          <span className="muted small">
            {realEdit
              ? 'Saving requires a course update endpoint.'
              : isDemo
                ? 'Saved locally in this browser.'
                : 'Saved to your account.'}
          </span>
        </div>
      </form>

      <AnalysisDialog
        open={open}
        busy={busy}
        status={status}
        error={error}
        demo={isDemo}
        courseId={
          createdId
            ? String(createdId)
            : courseId || ''
        }
        onClose={() => setOpen(false)}
      />
    </div>
  )
}

function ExistingEditor({
  courseId,
}: {
  courseId: string
}) {
  const {
    course,
    error,
    retry,
  } = useCourse(courseId)

  if (error) {
    return (
      <Notice tone="error">
        {error}{' '}
        <button
          className="text-button"
          onClick={retry}
        >
          Try again
        </button>
      </Notice>
    )
  }

  if (!course) {
    return (
      <Loading text="Loading course settings…" />
    )
  }

  return (
    <Editor
      course={course}
      courseId={courseId}
    />
  )
}

export default function CourseEditorPage({
  courseId,
}: {
  courseId?: string
}) {
  return courseId ? (
    <ExistingEditor courseId={courseId} />
  ) : (
    <Editor />
  )
}