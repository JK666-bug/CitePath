import { FormEvent, useEffect, useState } from 'react'
import './App.css'
import { readJson } from './api'
import { Bar } from './Bar'

type Citation = {
  document_id: number
  filename: string
  page_number: number
}

type Course = {
  id: number
  name: string
  documents: { id: number; usable_page_count: number }[]
}

type Answer = {
  qa_id: number
  course_name: string
  answer: string
  cited_pages: Citation[]
  refused: boolean
}

export default function Ask({ courseId, username }: { courseId: number; username: string }) {
  const [course, setCourse] = useState<Course | null>(null)
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Answer | null>(null)

  useEffect(() => {
    fetch(`/api/courses/${courseId}`)
      .then(readJson)
      .then(setCourse)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [courseId])

  const usable = course?.documents.some((document) => document.usable_page_count > 0) ?? false

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult(null)
    const text = question.trim()
    if (!text) {
      setError('Write a question')
      return
    }
    setSubmitting(true)
    try {
      const payload = await readJson(
        await fetch(`/api/courses/${courseId}/questions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text }),
        }),
      )
      setResult(payload)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not answer')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page">
      <Bar username={username} />
      <header>
        <p className="eyebrow">Course question</p>
        <h1>{course?.name ?? 'Ask the lectures'}</h1>
        <p className="lead">Answers use only the PDFs in this course. If the notes do not support an answer, it will say so.</p>
      </header>
      {loading ? <p className="lead">Loading course…</p> : null}
      {course && !usable ? (
        <p className="card empty">
          This course has no material to cite. <a href={`/courses/${courseId}`}>Upload a PDF first</a>
        </p>
      ) : null}
      <form className="card" onSubmit={onSubmit}>
        <label>
          Question
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={5}
            placeholder="For example: Where do arrays store their items?"
          />
        </label>
        <div className="actions">
          <button type="submit" disabled={submitting || loading || !usable}>
            {submitting ? 'Searching the lectures…' : 'Ask'}
          </button>
          <a href={`/courses/${courseId}`}>Back to this course</a>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </form>
      {result ? (
        <section className="card result">
          <h2>{result.refused ? 'Cannot answer' : 'Answer'}</h2>
          {result.refused ? <p className="refused">The notes do not support an answer</p> : null}
          <p className="answer">{result.answer}</p>
          {result.cited_pages.length > 0 ? (
            <ul className="cites">
              {result.cited_pages.map((item) => (
                <li key={`${item.document_id}-${item.page_number}`}>
                  {item.filename} · page {item.page_number}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="meta">
            Record {result.qa_id} · {result.course_name}
          </p>
        </section>
      ) : null}
    </main>
  )
}
