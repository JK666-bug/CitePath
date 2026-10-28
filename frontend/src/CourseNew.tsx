import { FormEvent, useState } from 'react'
import './App.css'
import { readJson } from './api'
import { Bar } from './Bar'

export default function CourseNew({ username }: { username: string }) {
  const [name, setName] = useState('')
  const [brief, setBrief] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [createdId, setCreatedId] = useState<number | null>(null)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const courseName = name.trim()
    const text = brief.trim()
    if (!courseName) {
      setError('Enter a course name')
      return
    }
    if (!text) {
      setError('Write your goals and dates in one paragraph')
      return
    }
    const pdfs = files.filter((file) => file.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length !== files.length) {
      setError('Upload PDF files only')
      return
    }
    setSubmitting(true)
    try {
      const response = await fetch('/api/courses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: courseName, student_brief: text }),
      })
      const course = await readJson(response)
      setCreatedId(course.id)
      for (const file of pdfs) {
        const body = new FormData()
        body.append('file', file)
        const uploaded = await fetch(`/api/courses/${course.id}/documents`, {
          method: 'POST',
          body,
        })
        await readJson(uploaded)
      }
      window.location.assign(`/courses/${course.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page">
      <Bar username={username} />
      <header>
        <p className="eyebrow">CitePath</p>
        <h1>New course</h1>
        <p className="lead">Name the course and write your study note. You can upload PDFs now or add them later.</p>
      </header>
      <form className="card" onSubmit={onSubmit}>
        <label>
          Course name
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Study note
          <textarea
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            rows={6}
            placeholder="For example: I want to master sorting and hashing by 20 November, with 6 hours a week."
          />
        </label>
        <label>
          Lecture PDFs
          <span className="file-picker">
            <input
              className="visually-hidden"
              type="file"
              accept="application/pdf,.pdf"
              multiple
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
            {files.length > 0 ? files.map((file) => file.name).join(', ') : 'You can choose more than one PDF'}
          </span>
        </label>
        <div className="actions">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Saving…' : 'Create course'}
          </button>
          <a href="/courses">Back</a>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {createdId ? <a href={`/courses/${createdId}`}>Open this course</a> : null}
      </form>
    </main>
  )
}
