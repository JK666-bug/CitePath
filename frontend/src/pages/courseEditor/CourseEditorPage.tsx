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
  daysBetween,
  parseDate,
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

import { createCourse, updateCourse } from './api'

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
  const existingCourse = isDemo ? undefined : course

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

  const brief = encodeBrief(value)
  const settingsChanged =
    !existingCourse ||
    value.name.trim() !== existingCourse.name ||
    brief !== encodeBrief(decodeBrief(existingCourse.student_brief))
  const shouldSaveSettings = createdId === null && settingsChanged
  const nothingToSave = !shouldSaveSettings && files.length === 0
  const retryBlocked = Boolean(createdId && error && !retryChecked)

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (busy || uncertainCreate || retryBlocked || nothingToSave) return

    const next: Record<string, string> = {}

    // A materials-only upload also works for older courses with past deadlines.
    if (shouldSaveSettings) {
      const today = dateKey()
      if (!value.name.trim()) {
        next.name = 'Please enter a course name.'
      }

      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(value.deadline) ||
        dateKey(parseDate(value.deadline)) !== value.deadline ||
        value.deadline < today
      ) {
        next.deadline = 'Choose today or a future date.'
      }

      if (
        !Number.isInteger(value.earlyDays) ||
        value.earlyDays < 0 ||
        (!next.deadline && value.earlyDays > daysBetween(today, value.deadline))
      ) {
        next.earlyDays =
          'Choose a whole number that keeps your target date on or after today.'
      }

      if (Array.from(brief).length > 10000) {
        next.note =
          'Your course settings and note are too long. Please shorten your note.'
      }
    }

    if (files.some((file) => !file.name.toLowerCase().endsWith('.pdf'))) {
      next.files = 'Please choose PDF files only.'
    } else if (files.some((file) => file.size === 0)) {
      next.files = 'Empty files cannot be uploaded.'
    }

    setErrors(next)
    const firstError = Object.keys(next)[0]
    if (firstError) {
      document.getElementById(`course-${firstError}`)?.focus()
      return
    }

    setBusy(true)
    setOpen(true)
    setError('')
    setStatus(shouldSaveSettings ? 'Saving course settings…' : 'Uploading course materials…')

    let id = existingCourse?.id ?? createdId
    let settingsSaved = false
    let added = 0
    const duplicates: string[] = []

    try {
      if (isDemo) {
        editDemo(value.name.trim(), value)
        setStatus('Sample study time and dates have been recalculated.')
        return
      }

      if (id === null) {
        const created = await createCourse(value.name.trim(), brief)
        id = created.id
        setCreatedId(id)
        settingsSaved = true
      } else if (existingCourse && shouldSaveSettings) {
        await updateCourse(id, value.name.trim(), brief)
        settingsSaved = true
      }

      for (const file of files) {
        setStatus(`Uploading and processing ${file.name}…`)
        const result = await uploadMaterial(id, file)
        if (result.duplicate) {
          duplicates.push(duplicateMessage(file.name, result.filename))
        } else {
          added += 1
        }

        // Keep only unfinished uploads in the picker if a later request fails.
        const key = fileKey(file)
        setFiles((current) => current.filter((item) => fileKey(item) !== key))
        if (!existingCourse) {
          setUploaded((current) => [...current, key])
        }
      }

      const messages = [...duplicates]
      if (added > 0) {
        messages.unshift(`${added} PDF ${added === 1 ? 'file' : 'files'} uploaded.`)
      }
      if (settingsSaved) messages.unshift('Course settings saved.')
      setStatus(messages.join(' '))
    } catch (reason) {
      if (
        id === null &&
        reason instanceof ApiError &&
        (reason.status === 0 || reason.status >= 500)
      ) {
        setUncertainCreate(true)
      }

      setRetryChecked(false)
      setError(`${messageOf(reason)} Check the saved course and materials before retrying.`)
      const saved = []
      if (settingsSaved) saved.push('Course settings were saved.')
      if (added > 0) {
        saved.push(`${added} PDF ${added === 1 ? 'file was' : 'files were'} uploaded.`)
      }
      setStatus(saved.join(' ') || 'Some changes could not be confirmed.')
    } finally {
      if (!isDemo) {
        const [details] = await Promise.allSettled([
          id === null ? Promise.resolve() : loadCourse(id),
          refreshCourses(),
        ])
        if (details.status === 'rejected') {
          setStatus((current) =>
            `${current} Reopen the course to refresh its details.`,
          )
        }
      }
      setBusy(false)
    }
  }

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
          disabled={busy || createdId !== null}
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
            <MaterialPicker
              files={files}
              onChange={setFiles}
              disabled={busy}
            />
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
              uncertainCreate ||
              retryBlocked ||
              nothingToSave
            }
          >
            {busy
              ? 'Saving…'
              : isDemo
                ? 'Save and update sample plan'
                : createdId
                  ? 'Upload remaining materials'
                  : existingCourse
                    ? settingsChanged
                      ? 'Save changes'
                      : 'Upload materials'
                    : 'Save course'}
          </button>

          <span className="muted small">
            {isDemo
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
