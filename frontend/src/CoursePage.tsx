import { FormEvent, useEffect, useState } from 'react'
import './App.css'
import { readJson } from './api'
import { Bar } from './Bar'

type Material = {
  id: number
  filename: string
  page_count: number
  usable_page_count: number
}

type Course = {
  id: number
  name: string
  student_brief: string
  documents: Material[]
}

export default function CoursePage({ courseId, username }: { courseId: number; username: string }) {
  const [course, setCourse] = useState<Course | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    const payload = await readJson(await fetch(`/api/courses/${courseId}`))
    setCourse(payload)
  }

  useEffect(() => {
    load()
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [courseId])

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (!file) {
      setError('Choose a PDF')
      return
    }
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Upload a PDF file')
      return
    }
    const body = new FormData()
    body.append('file', file)
    setUploading(true)
    try {
      await readJson(
        await fetch(`/api/courses/${courseId}/documents`, { method: 'POST', body }),
      )
      setFile(null)
      setFileKey((value) => value + 1)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function remove(documentId: number, filename: string) {
    if (!window.confirm(`Delete “${filename}”? Later questions will not cite it.`)) return
    setError('')
    try {
      await readJson(
        await fetch(`/api/courses/${courseId}/documents/${documentId}`, { method: 'DELETE' }),
      )
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not delete')
    }
  }

  return (
    <main className="page">
      <Bar username={username} />
      {loading ? <p className="lead">Loading course…</p> : null}
      {course ? (
        <div className="stack">
          <div className="title-row">
            <header>
              <p className="eyebrow">Course</p>
              <h1>{course.name}</h1>
            </header>
            <a className="button-link" href={`/courses/${course.id}/ask`}>
              Ask about this course
            </a>
          </div>
          <p className="brief">{course.student_brief}</p>
          <form className="card" onSubmit={onUpload}>
            <label>
              Add a PDF
              <span className="file-picker">
                <input
                  key={fileKey}
                  className="visually-hidden"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                {file ? file.name : 'Choose a PDF'}
              </span>
            </label>
            <button type="submit" disabled={uploading}>
              {uploading ? 'Saving…' : 'Upload'}
            </button>
          </form>
          <section className="card">
            <h2>Materials</h2>
            {course.documents.length === 0 ? <p className="empty">No PDFs yet.</p> : null}
            <ul className="file-list">
              {course.documents.map((document) => (
                <li key={document.id} className="file-row">
                  <div>
                    <strong>{document.filename}</strong>
                    <span className="meta">
                      {`${document.page_count} ${document.page_count === 1 ? 'page' : 'pages'}, ${document.usable_page_count} can be cited`}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => remove(document.id, document.filename)}
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
    </main>
  )
}
