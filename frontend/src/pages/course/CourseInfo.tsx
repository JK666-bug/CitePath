import { useState } from 'react'
import type { FormEvent } from 'react'
import { FileText } from 'lucide-react'

import type {
  CourseDetail,
  Material,
} from './types'

import { decodeBrief } from '../courseEditor/brief'
import { numberMaterials } from './materials'

import MaterialPicker, {
  fileKey,
} from '../courseEditor/MaterialPicker'

import {
  deleteMaterial,
  duplicateMessage,
  uploadMaterial,
} from './api'

import { useStudy } from '../../shared/StudyProvider'
import { messageOf } from '../../shared/request'
import { prettyDate } from '../../shared/format'

import {
  Modal,
  Notice,
} from '../../shared/components/UI'

export default function CourseInfo({
  courseId,
  course,
}: {
  courseId: string
  course: CourseDetail
}) {
  const {
    loadCourse,
    refreshCourses,
  } = useStudy()

  const config =
    decodeBrief(course.student_brief)

  const demo = courseId === 'demo'
  const materials = numberMaterials(course.documents)

  const [files, setFiles] =
    useState<File[]>([])

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] =
    useState('')

  const [remove, setRemove] =
    useState<Material | null>(null)

  async function reload() {
    await loadCourse(course.id)
    await refreshCourses()
  }

  async function upload(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (busy || demo) return

    setError('')
    setMessage('')

    if (
      !files.length ||
      files.some(
        (file) =>
          !file.name
            .toLowerCase()
            .endsWith('.pdf') ||
          !file.size,
      )
    ) {
      setError(
        'Choose one or more non-empty PDF files.',
      )
      return
    }

    setBusy(true)
    const duplicates: string[] = []
    let saved = 0

    try {
      for (const file of files) {
        setMessage(
          `Uploading and processing ${file.name}…`,
        )

        const result = await uploadMaterial(
          course.id,
          file,
        )

        if (result.duplicate) {
          duplicates.push(
            duplicateMessage(
              file.name,
              result.filename,
            ),
          )
        } else {
          saved += 1
        }

        setFiles((current) =>
          current.filter(
            (item) =>
              fileKey(item) !==
              fileKey(file),
          ),
        )
      }

      const parts: string[] = []

      if (saved > 0) {
        parts.push(
          'Materials saved. A new study plan requires the planning service, which is not connected yet.',
        )
      }

      if (duplicates.length) {
        parts.push(duplicates.join(' '))
      }

      setMessage(parts.join(' '))
    } catch (reason) {
      setMessage('')

      setError(
        `${messageOf(reason)} Check the material list before manually retrying; a failed response may still have saved a file.`,
      )
    } finally {
      try {
        await reload()
      } catch (reason) {
        setError(messageOf(reason))
      }

      setBusy(false)
    }
  }

  async function confirmDelete() {
    if (!remove || busy || demo) return

    setBusy(true)
    setError('')
    setMessage('')

    try {
      await deleteMaterial(
        course.id,
        remove.id,
      )

      await reload()

      setMessage(
        'Material removed. Any future plan using it will need to be regenerated.',
      )
    } catch (reason) {
      setError(messageOf(reason))
    } finally {
      setBusy(false)
      setRemove(null)
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <h2>Course settings</h2>

        <dl className="course-facts">
          <div>
            <dt>Learning deadline</dt>
            <dd>
              {prettyDate(
                config.deadline,
                true,
              )}
            </dd>
          </div>

          <div>
            <dt>Finish early by</dt>
            <dd>
              {config.deadline
                ? `${config.earlyDays} days`
                : 'Not set'}
            </dd>
          </div>

          <div>
            <dt>Materials</dt>
            <dd>
              {course.documents.length}
              {' '}PDFs
            </dd>
          </div>
        </dl>

        <h3>Goals and study note</h3>

        <p className="course-note">
          {config.note ||
            'No additional note.'}
        </p>
      </section>

      {error && (
        <Notice tone="error">
          {error}
        </Notice>
      )}

      {message && (
        <Notice>{message}</Notice>
      )}

      <section className="panel">
        <h2>Course materials</h2>

        {materials.length ? (
          <ul className="materials-list">
            {materials.map(
              (material) => (
                <li key={material.id}>
                  <FileText
                    size={18}
                    strokeWidth={1.4}
                  />

                  <div>
                    <strong>
                      {material.filename}
                    </strong>

                    <p>
                      Doc {material.displayNumber}
                      {' · '}
                      {material.page_count}
                      {' '}pages
                      {' · '}
                      {material.usable_page_count}
                      {' '}usable pages
                    </p>
                  </div>

                  <span className="badge">
                    {material.ingest_status ===
                    'complete'
                      ? 'Ready'
                      : material.ingest_status ===
                          'pending'
                        ? 'Processing'
                        : 'Unavailable'}
                  </span>

                  <button
                    className="button small danger"
                    disabled={busy || demo}
                    onClick={() =>
                      setRemove(material)
                    }
                  >
                    Delete
                  </button>
                </li>
              ),
            )}
          </ul>
        ) : (
          <p className="muted">
            No materials uploaded yet.
          </p>
        )}

        {demo ? (
          <p className="muted small">
            Sample PDF references are
            illustrative. This demo does not
            contain real PDF files.
          </p>
        ) : (
          <form
            className="stack"
            onSubmit={upload}
            noValidate
          >
            <MaterialPicker
              files={files}
              onChange={setFiles}
              disabled={busy}
            />

            <div className="actions">
              <button
                className="button"
                disabled={
                  busy || !files.length
                }
              >
                {busy
                  ? 'Processing materials…'
                  : 'Upload materials'}
              </button>

              <small className="muted">
                Only upload status is
                available; no analysis
                percentage is estimated.
              </small>
            </div>
          </form>
        )}
      </section>

      <Modal
        open={Boolean(remove)}
        title="Delete course material?"
        closeable={!busy}
        onClose={() => setRemove(null)}
      >
        <p>
          Delete {remove?.filename}?
          Future questions will no longer be
          able to cite this material.
        </p>

        <div className="actions">
          <button
            className="button danger"
            disabled={busy}
            onClick={confirmDelete}
          >
            {busy
              ? 'Deleting…'
              : 'Delete material'}
          </button>

          <button
            className="button secondary"
            disabled={busy}
            onClick={() => setRemove(null)}
          >
            Cancel
          </button>
        </div>
      </Modal>
    </div>
  )
}
